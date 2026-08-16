"""
Settle D32 — is BGE-M3 the right embedding model, or just the one we picked?

    uv run python -m rag.compare_embedders            # run the comparison
    uv run python -m rag.compare_embedders --models BAAI/bge-m3

`study/09-DECISIONS.md` **D32** has said "chosen, never benchmarked" since the
roadmap. **D37** said the comparison had to wait until there was something to
score against. Step 5 built that, so this is the tool that empties the entry.

THE METRIC, AND WHY IT NEEDS NO HUMAN VERDICTS

Answer quality cannot be scored here: D06 reserves that for a person, and the
19 verdicts in `deliverables/FAILURES.md` are still open. **Retrieval quality
can be**, mechanically:

    For each probe question with a known symbol, at what RANK does the first
    chunk containing that symbol appear?

That is objective. `rag/probe.py` already pairs each question with the exact
string that must be retrieved for the answer to be findable at all, and
`corpus/chunks.jsonl` says which chunks contain it. No opinion enters.

Reported per model:

    recall@5    of the questions, how many put a containing chunk in the top 5
    recall@10   the same at 10
    MRR         mean reciprocal rank — 1/rank of the first hit, averaged.
                Rewards being right at rank 1 over rank 5, which recall@5
                cannot see.
    unfound     questions where NO chunk with the symbol exists at all. These
                are the corpus ceiling (D45) and are excluded from the scores,
                because no model can move them.

WHAT THIS DOES NOT MEASURE

Whether the *answers* get better. A model that retrieves the right chunk more
often should produce better answers, but "should" is the word doing the work
and Phase 2 is where that gets tested. This measures retrieval, and says so.
"""

from __future__ import annotations

import json
import sys
import time

from rag import chunk as chunk_mod
from rag import embed as embed_mod
from rag import probe

# A deliberate spread rather than two near-neighbours: 568M against 22M, 1024
# dimensions against 384. If the small one is close, the large one is not
# earning its VRAM — which is the whole question D32 asks.
MODELS = [
    ("BAAI/bge-m3", None),
    ("sentence-transformers/all-MiniLM-L6-v2", None),
]

TOP = 10


def load_chunks() -> list[dict]:
    if not chunk_mod.CHUNKS_PATH.exists():
        sys.exit("no corpus/chunks.jsonl — run `uv run python -m rag.chunk` first")
    return [json.loads(l) for l in chunk_mod.CHUNKS_PATH.read_text().splitlines()]


def score(model_id: str, revision: str | None, chunks: list[dict]) -> dict:
    import numpy as np
    from sentence_transformers import SentenceTransformer

    device = embed_mod.pick_device(None)
    started = time.perf_counter()
    model = SentenceTransformer(model_id, revision=revision, device=device)
    model.max_seq_length = min(embed_mod.MAX_SEQ_LENGTH, model.max_seq_length)
    load_seconds = time.perf_counter() - started

    texts = [embed_mod.embedding_input(c) for c in chunks]
    started = time.perf_counter()
    vectors = model.encode(texts, batch_size=8, normalize_embeddings=True,
                           convert_to_numpy=True, show_progress_bar=False).astype("float32")
    encode_seconds = time.perf_counter() - started

    questions = [(q, sym) for q, _, sym in probe.QUESTIONS if sym]
    ranks: list[int | None] = []
    unfound = 0

    for question, symbol in questions:
        # Which chunks contain the symbol at all? If none, it is the ceiling.
        containing = {i for i, c in enumerate(chunks) if symbol.lower() in c["text"].lower()}
        if not containing:
            unfound += 1
            continue
        qv = model.encode([question], normalize_embeddings=True,
                          convert_to_numpy=True)[0].astype("float32")
        order = np.argsort(-(vectors @ qv))
        rank = next((r for r, i in enumerate(order, 1) if int(i) in containing), None)
        ranks.append(rank)

    scored = [r for r in ranks if r is not None]
    return {
        "model": model_id,
        "dim": int(vectors.shape[1]),
        "params_m": round(sum(p.numel() for p in model.parameters()) / 1e6),
        "load_seconds": round(load_seconds, 1),
        "encode_seconds": round(encode_seconds, 1),
        "chunks_per_second": round(len(chunks) / encode_seconds, 1),
        "questions_scored": len(scored),
        "unfound_ceiling": unfound,
        "recall_at_5": round(sum(1 for r in scored if r <= 5) / len(scored), 3),
        "recall_at_10": round(sum(1 for r in scored if r <= TOP) / len(scored), 3),
        "mrr": round(sum(1 / r for r in scored) / len(scored), 3),
        "median_rank": sorted(scored)[len(scored) // 2],
        "worst_rank": max(scored),
    }


def main() -> None:
    argv = sys.argv[1:]
    models = MODELS
    if "--models" in argv:
        models = [(m, None) for m in argv[argv.index("--models") + 1].split(",")]

    chunks = load_chunks()
    print(f"{len(chunks)} chunks, "
          f"{len([1 for _, _, s in probe.QUESTIONS if s])} questions with a known symbol\n")

    rows = []
    for model_id, revision in models:
        print(f"scoring {model_id} ...", file=sys.stderr)
        rows.append(score(model_id, revision, chunks))

    head = ("model", "dim", "params", "chunks/s", "R@5", "R@10", "MRR", "median", "worst")
    print(f"{head[0]:<42} {head[1]:>5} {head[2]:>7} {head[3]:>9} "
          f"{head[4]:>6} {head[5]:>6} {head[6]:>6} {head[7]:>7} {head[8]:>6}")
    for r in rows:
        print(f"{r['model']:<42} {r['dim']:>5} {r['params_m']:>6}M {r['chunks_per_second']:>9} "
              f"{r['recall_at_5']:>6} {r['recall_at_10']:>6} {r['mrr']:>6} "
              f"{r['median_rank']:>7} {r['worst_rank']:>6}")
    print(f"\n{rows[0]['unfound_ceiling']} question(s) excluded: no chunk in the corpus "
          f"contains the symbol at all — the ceiling (D45), which no model can move.")


if __name__ == "__main__":
    main()
