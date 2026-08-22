"""
Phase 1, Step 3a — turn 3284 chunks into 3284 vectors.

    uv sync --extra embed                       # once, per machine
    uv run python -m rag.embed                  # embed everything, auto device
    uv run python -m rag.embed --device cpu     # force a device
    uv run python -m rag.embed --limit 200      # smoke test before the real run
    uv run python -m rag.embed --batch-size 8   # if memory is tight

Writes `corpus/embeddings.npy` (float32, one row per chunk) and
`corpus/embeddings.ids.json` (the chunk id for each row). Both are generated, so
both are gitignored. `corpus/EMBED_STATS.json` IS committed — it records what
model produced the vectors, on what device, at what speed.

WHY A FILE RATHER THAN WRITING STRAIGHT INTO QDRANT

`study/09-DECISIONS.md` D36. Embedding is the expensive step; loading is not. A
file decouples them, which buys three things:

  - **Portability.** The lab PC and this Mac cannot route to each other. A file
    can be copied by hand; a running Qdrant on the wrong machine cannot.
  - **Resumability.** A failure halfway through costs the remaining chunks, not
    the whole run.
  - **Honesty about what the index is.** Writing directly makes the index a side
    effect of a process. A file makes it an *input*, which can be inspected,
    diffed and re-loaded without re-running anything.

WHY THE MODEL REVISION IS PINNED, NOT JUST THE NAME

"BGE-M3" names a HuggingFace repository, and repositories move. Two halves of a
corpus embedded by different revisions are **not comparable at all** — cosine
similarity between them is noise, not degradation. So the revision is pinned the
same way `verify_2_0.PIN` pins SQLAlchemy 2.0.51, and a mismatch warns loudly
rather than silently producing an index that is subtly two things at once.

The same reasoning covers `NORMALIZE` and the stored dtype. All three are
recorded in EMBED_STATS.json so a future run can be checked against this one
instead of assumed compatible.

WHAT IS DELIBERATELY NOT DONE

BGE-M3 can emit dense, sparse and ColBERT representations. This uses
**sentence-transformers, which gives dense only** — and that is the point. Phase
1 is meaning-search only (D04); sparse vectors are half of hybrid search, which
is a Phase 3 fix for a problem Step 5 has not yet demonstrated. Choosing the
library that cannot do it is cheaper than choosing the one that can and
remembering not to.
"""

from __future__ import annotations

import json
import os
import sys
import time

from rag import corpus

VECTORS_PATH = corpus.CORPUS_DIR / "embeddings.npy"
IDS_PATH = corpus.CORPUS_DIR / "embeddings.ids.json"
STATS_PATH = corpus.CORPUS_DIR / "EMBED_STATS.json"
CHUNKS_PATH = corpus.CORPUS_DIR / "chunks.jsonl"

MODEL_ID = "BAAI/bge-m3"

# Resolved on the first run (2026-08-14) and pinned here. Setting it to None
# makes the script resolve whatever HuggingFace currently serves and print what
# to paste back — deliberate, because a placeholder hash typed by hand would be
# worse than an honest blank.
#
# TO MOVE IT: set to None, run, paste the reported hash, and RE-EMBED EVERYTHING.
# A half-and-half index is not degraded, it is meaningless — vectors from two
# revisions are not in the same space. Same discipline as verify_2_0.PIN.
MODEL_REVISION: str | None = "5617a9f61b028005a4858fdac845db406aefb181"

# Cosine similarity on unit-length vectors is a dot product, and Qdrant's COSINE
# distance expects that. Recorded in the stats because a run that normalized and
# a run that did not produce indexes that cannot be mixed — silently, since the
# search still returns results.
NORMALIZE = True

# BGE-M3 accepts 8192 tokens. Our chunks do not need it: TARGET is 1800
# characters and the p99 chunk is 2451, so ~700 tokens covers almost everything.
# Attention cost grows with the square of sequence length, so leaving the window
# at 8192 would pay for capacity no chunk uses. 2048 is chosen with headroom for
# the oversized code blocks; anything longer is truncated and COUNTED, because a
# silent truncation is a chunk that says something other than what it says.
MAX_SEQ_LENGTH = 2048

DEFAULT_BATCH_SIZE = 16


def pick_device(requested: str | None) -> str:
    """
    Auto-detect unless told. Order is deliberate: an accelerator if one exists,
    CPU only as a fallback that is honest about being slow.

    torch is imported *after* the explicit-request check, not before, so an
    explicit `--device` needs no torch at all. That is not tidiness — CI runs
    `uv sync --frozen` without `--extra embed`, so torch is absent there, and
    this is what lets the device logic be tested rather than only run.
    """
    if requested:
        return requested

    import torch

    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def load_chunks(limit: int | None) -> list[dict]:
    if not CHUNKS_PATH.exists():
        sys.exit(
            f"no {CHUNKS_PATH.relative_to(corpus.REPO_ROOT)} — run "
            "`uv run python -m rag.chunk` first (it is generated, not committed)"
        )
    chunks = [json.loads(line) for line in CHUNKS_PATH.read_text().splitlines()]
    return chunks[:limit] if limit else chunks


def embedding_input(chunk: dict) -> str:
    """
    What actually gets embedded — the heading path, then the text.

    The path is prepended because **headings are context**, and a chunk reading
    "this was removed in 2.0" is meaningless without the heading naming what
    "this" is. The chunker already carries the ancestry; this is where it earns
    its keep. Without it the embedding represents an orphaned paragraph.

    Sphinx roles stay raw. Stripping them for embed was measured 2026-08-22 and
    **rejected** (`D69`): recall@5 fell 0.64 → 0.58 and broke two baseline hits.
    """
    path = " > ".join(chunk["heading_path"])
    return f"{path}\n\n{chunk['text']}" if path else chunk["text"]


def peak_memory(device: str) -> dict:
    """Whatever the device can honestly report, in MiB."""
    import torch

    out: dict[str, float] = {}
    if device == "cuda":
        out["torch_peak_mib"] = round(torch.cuda.max_memory_allocated() / 2**20, 1)
    elif device == "mps":
        # Unified memory: there is no separate VRAM pool to read, so this is
        # what torch has handed out rather than a hardware ceiling.
        current = getattr(torch.mps, "current_allocated_memory", None)
        if current:
            out["torch_allocated_mib"] = round(current() / 2**20, 1)
    try:
        import resource

        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # macOS reports bytes, Linux reports kibibytes.
        out["process_peak_rss_mib"] = round(
            (rss / 2**20 if sys.platform == "darwin" else rss / 1024), 1
        )
    except Exception:                                    # pragma: no cover
        pass
    return out


def main() -> None:
    argv = sys.argv[1:]

    def flag(name: str, cast, default=None):
        return cast(argv[argv.index(name) + 1]) if name in argv else default

    device_arg = flag("--device", str)
    limit = flag("--limit", int)
    batch_size = flag("--batch-size", int, DEFAULT_BATCH_SIZE)

    import numpy as np
    from sentence_transformers import SentenceTransformer

    device = pick_device(device_arg)
    chunks = load_chunks(limit)
    texts = [embedding_input(c) for c in chunks]

    print(f"model    {MODEL_ID}  revision={MODEL_REVISION or '(unpinned)'}")
    print(f"device   {device}   batch_size={batch_size}   max_seq_length={MAX_SEQ_LENGTH}")
    print(f"chunks   {len(chunks)}   {sum(len(t) for t in texts)} chars")

    load_started = time.perf_counter()
    model = SentenceTransformer(
        MODEL_ID,
        revision=MODEL_REVISION,
        device=device,
    )
    model.max_seq_length = MAX_SEQ_LENGTH
    load_seconds = time.perf_counter() - load_started
    print(f"loaded in {load_seconds:.1f}s")

    # Report the revision actually in use, so an unpinned run tells you what to
    # pin rather than leaving you to find it.
    resolved = getattr(getattr(model, "model_card_data", None), "base_model_revision", None)

    # How many chunks the window truncates. Counted rather than hoped about: a
    # truncated chunk is embedded as something other than what it says, and the
    # index gives no hint that it happened.
    tokenizer = model.tokenizer
    lengths = [len(tokenizer.encode(t, add_special_tokens=True)) for t in texts]
    truncated = sum(1 for n in lengths if n > MAX_SEQ_LENGTH)
    print(f"tokens   max={max(lengths)}  mean={sum(lengths) // len(lengths)}  "
          f"truncated={truncated}")

    started = time.perf_counter()
    vectors = model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=NORMALIZE,
        convert_to_numpy=True,
        show_progress_bar=True,
    )
    seconds = time.perf_counter() - started

    vectors = vectors.astype("float32")
    np.save(VECTORS_PATH, vectors)
    IDS_PATH.write_text(json.dumps([c["id"] for c in chunks]) + "\n")

    stats = {
        "generated_by": "rag/embed.py",
        "model": MODEL_ID,
        "revision": MODEL_REVISION or resolved,
        "revision_pinned": MODEL_REVISION is not None,
        "normalize": NORMALIZE,
        "dtype": "float32",
        "max_seq_length": MAX_SEQ_LENGTH,
        "dim": int(vectors.shape[1]),
        "n_vectors": int(vectors.shape[0]),
        "tokens": {"max": max(lengths), "mean": sum(lengths) // len(lengths),
                   "truncated": truncated},
        "run": {
            "device": device,
            "batch_size": batch_size,
            "load_seconds": round(load_seconds, 1),
            "encode_seconds": round(seconds, 1),
            "chunks_per_second": round(len(chunks) / seconds, 1),
            "peak_memory": peak_memory(device),
            "complete": limit is None,
        },
    }
    # A partial run must not overwrite the record of a full one — the stats file
    # is what later steps trust to describe the index.
    if limit is None:
        STATS_PATH.write_text(json.dumps(stats, indent=2) + "\n")
    else:
        print("\n--limit run: EMBED_STATS.json left alone", file=sys.stderr)

    print(f"\nvectors  {vectors.shape[0]} x {vectors.shape[1]}  float32  "
          f"-> {VECTORS_PATH.relative_to(corpus.REPO_ROOT)}")
    print(f"encode   {seconds:.1f}s   {len(chunks) / seconds:.1f} chunks/s")
    for key, value in stats["run"]["peak_memory"].items():
        print(f"memory   {key} = {value}")
    if not MODEL_REVISION:
        print(f"\nUNPINNED. Set MODEL_REVISION in rag/embed.py to: {resolved}", file=sys.stderr)


if __name__ == "__main__":
    main()
