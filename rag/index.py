"""
Phase 1, Step 3b — load the vectors into Qdrant.

    docker compose up -d qdrant                     # start the database
    uv run python -m rag.index                      # create + fill the collection
    uv run python -m rag.index --recreate           # drop it first
    uv run python -m rag.index --search "why can't I call engine.execute any more?"

Reads `corpus/embeddings.npy` and `corpus/chunks.jsonl`, both generated. Writes
nothing to the repo — the output of this step lives in a Docker volume, and
that is on purpose: losing it costs one re-run of this script, because the
vectors themselves are a file (D36) rather than something only the database has.

WHY A DATABASE AT ALL, WHEN A DOT PRODUCT ALREADY WORKS

`rag/embed.py` leaves 3284 unit vectors in a NumPy array, and searching them is
one line: `vectors @ query`. That genuinely works, and at this size it is fast.
So the honest answer to "why Qdrant" is not speed:

  - **Filtering.** Every chunk carries its SQLAlchemy version. Answering "only
    2.0 pages" means a filtered search, which a flat dot product cannot express
    without rebuilding the array per query. Phase 3 needs this.
  - **The payload travels with the vector.** Sources have to be printed next to
    the answer (Step 4), so the text must come back from the search rather than
    be looked up separately by an index that could drift.
  - **It stops being a script.** A dot product over an in-memory array is a
    thing one process can do. A database is a thing several processes and the
    Phase 5 agent can share.

**Speed is not the reason, at this scale.** Saying so is more defensible than
claiming a 3284-row array needed a vector database.

WHY THE COLLECTION NAME CONTAINS THE MODEL AND REVISION

`sqlalchemy-upgrade-agent-bge-m3-5617a9f6`, not `chunks`.

Vectors from two model revisions are not comparable — cosine between them is
noise, not degradation (D36). Qdrant has no collection-level metadata field to
record what produced a collection, so the fact is put where it cannot be
ignored: in the name. Re-embed with a different revision and you get a
different collection rather than a silently mixed one.

Same reasoning as declaring `image:` in Compose (D20) — make the wrong thing
inexpressible rather than merely discouraged.
"""

from __future__ import annotations

import json
import sys

from rag import corpus, embed

URL = "http://127.0.0.1:6333"
BATCH = 256


def collection_name(stats: dict) -> str:
    """Project name, model, and the first 8 of the revision that produced it."""
    model = stats["model"].split("/")[-1].lower().replace("_", "-")
    return f"sqlalchemy-upgrade-agent-{model}-{stats['revision'][:8]}"


def load_inputs():
    import numpy as np

    for path in (embed.VECTORS_PATH, embed.IDS_PATH, embed.STATS_PATH, embed.CHUNKS_PATH):
        if not path.exists():
            sys.exit(
                f"missing {path.relative_to(corpus.REPO_ROOT)} — run "
                "`uv run python -m rag.embed` first"
            )

    vectors = np.load(embed.VECTORS_PATH)
    ids = json.loads(embed.IDS_PATH.read_text())
    stats = json.loads(embed.STATS_PATH.read_text())
    chunks = {
        c["id"]: c
        for c in (json.loads(l) for l in embed.CHUNKS_PATH.read_text().splitlines())
    }

    # These three files are written by two different scripts at two different
    # times. If they have drifted, every citation would point at the wrong
    # source — and nothing downstream could tell, because the vectors would
    # still be valid vectors.
    if len(ids) != vectors.shape[0]:
        sys.exit(f"{len(ids)} ids but {vectors.shape[0]} vectors — re-run rag.embed")
    if stats["n_vectors"] != vectors.shape[0]:
        sys.exit(f"EMBED_STATS says {stats['n_vectors']}, file has {vectors.shape[0]}")
    missing = [i for i in ids if i not in chunks]
    if missing:
        sys.exit(f"{len(missing)} ids are not in chunks.jsonl — re-run rag.chunk then rag.embed")

    return vectors, ids, stats, chunks


def client():
    from qdrant_client import QdrantClient

    try:
        c = QdrantClient(url=URL, timeout=30)
        c.get_collections()
        return c
    except Exception as exc:
        sys.exit(f"cannot reach Qdrant at {URL}: {exc}\n  start it: docker compose up -d qdrant")


def build(recreate: bool) -> None:
    from qdrant_client import models

    vectors, ids, stats, chunks = load_inputs()
    name = collection_name(stats)
    c = client()

    exists = c.collection_exists(name)
    if exists and recreate:
        c.delete_collection(name)
        exists = False
    if not exists:
        c.create_collection(
            collection_name=name,
            vectors_config=models.VectorParams(
                size=int(vectors.shape[1]),
                # COSINE, and the vectors are already unit length (embed.NORMALIZE).
                # Normalizing twice is harmless; normalizing zero times is not, and
                # the failure is silent — search still returns results, ranked wrong.
                distance=models.Distance.COSINE,
            ),
        )
        print(f"created collection {name}  dim={vectors.shape[1]}  distance=COSINE")
    else:
        print(f"collection {name} exists  (--recreate to rebuild)")

    # An index on the version field, because filtering by it is the whole reason
    # this is a database rather than a dot product. Qdrant can filter without
    # one, by scanning; the index is what makes it not a scan.
    c.create_payload_index(
        collection_name=name,
        field_name="sqlalchemy_version",
        field_schema=models.PayloadSchemaType.KEYWORD,
        wait=True,
    )

    for start in range(0, len(ids), BATCH):
        window = ids[start:start + BATCH]
        c.upsert(
            collection_name=name,
            wait=True,
            points=models.Batch(
                # Qdrant point ids must be int or UUID, so the row number is the
                # id and the human-readable chunk id ("c00042") rides in the
                # payload. Row number is also the index into embeddings.npy,
                # which keeps the two representations trivially reconcilable.
                ids=list(range(start, start + len(window))),
                vectors=[vectors[start + n].tolist() for n in range(len(window))],
                payloads=[
                    {
                        "chunk_id": cid,
                        "sqlalchemy_version": chunks[cid]["sqlalchemy_version"],
                        "source_path": chunks[cid]["source_path"],
                        "heading_path": chunks[cid]["heading_path"],
                        "text": chunks[cid]["text"],
                        "n_chars": chunks[cid]["n_chars"],
                        # The character range in the source file. A retrieved
                        # passage you distrust is one you want to open at the
                        # original — PHASE-1.md Step 2 requires it, and without
                        # it a citation names a file but not a place in it.
                        "char_start": chunks[cid]["char_start"],
                        "char_end": chunks[cid]["char_end"],
                        "has_code": chunks[cid]["has_code"],
                    }
                    for cid in window
                ],
            ),
        )
        print(f"\r  upserted {min(start + BATCH, len(ids))}/{len(ids)}", end="", flush=True)
    print()

    # Step 3's stated gate: the count in the database matches the count of chunks.
    counted = c.count(collection_name=name, exact=True).count
    print(f"points in Qdrant: {counted}   vectors on disk: {vectors.shape[0]}")
    if counted != vectors.shape[0]:
        sys.exit("COUNT MISMATCH — the collection does not hold what was embedded")
    print("counts match")


_QUERY_MODEL = None


def query_vector(query: str) -> list[float]:
    """
    Embed one question, using the corpus's own settings.

    Every one of these must match `rag/embed.py` or the question lands in a
    different space from the vectors it is compared against — and the failure is
    silent, because search still returns results, merely ranked wrong. That is
    why they are read from `embed` rather than restated here.

    The model is cached in a module global: loading BGE-M3 takes ~5 seconds and
    a session asking several questions should pay that once.
    """
    global _QUERY_MODEL
    if _QUERY_MODEL is None:
        from sentence_transformers import SentenceTransformer

        _QUERY_MODEL = SentenceTransformer(
            embed.MODEL_ID, revision=embed.MODEL_REVISION, device=embed.pick_device(None)
        )
        _QUERY_MODEL.max_seq_length = embed.MAX_SEQ_LENGTH
    return _QUERY_MODEL.encode(
        [query], normalize_embeddings=embed.NORMALIZE, convert_to_numpy=True
    )[0].tolist()


def retrieve(
    query: str,
    limit: int = 5,
    version: str | None = None,
    *,
    dedupe: bool = True,
    hybrid: bool = True,
):
    """Top-`limit` hits. Shared by --search, rag.ask, and rag.score.

    Defaults (Phase 3):
      - `hybrid=True` — dense (Qdrant) + BM25 fused with dense-heavy RRF (`D67`)
      - `dedupe=True` — collapse cross-version twins, prefer 2.0.51 (`D66`)

    Pass `hybrid=False` / `dedupe=False` only to re-measure the earlier tax.
    """
    from qdrant_client import models
    from rag import dedup as dedup_mod

    _, _, stats, chunks = load_inputs()
    flt = (
        models.Filter(must=[models.FieldCondition(
            key="sqlalchemy_version", match=models.MatchValue(value=version))])
        if version else None
    )

    if hybrid:
        from rag import bm25 as bm25_mod
        from rag import hybrid as hybrid_mod

        # Each channel contributes CHANNEL_DEPTH; fusion + dedupe then cut to
        # `limit`. Over-fetch on dense still needed so twins can collapse.
        channel = hybrid_mod.CHANNEL_DEPTH
        dense_fetch = (
            channel if (version or not dedupe)
            else dedup_mod.overfetch_limit(channel)
        )
        dense_points = client().query_points(
            collection_name=collection_name(stats),
            query=query_vector(query),
            limit=dense_fetch,
            query_filter=flt,
            with_payload=True,
        ).points
        if dedupe and not version:
            dense_points = dedup_mod.dedupe_points(dense_points, channel)
        else:
            dense_points = dense_points[:channel]

        sparse_hits = bm25_mod.get_index().search(
            query, limit=channel, version=version
        )
        dense_ids = [p.payload["chunk_id"] for p in dense_points]
        sparse_ids = [h.chunk_id for h in sparse_hits]
        # Fuse to more than `limit` when dedupe still has to run on the merged
        # list — BM25 can re-introduce a twin the dense pass already dropped.
        fuse_n = (
            limit if (version or not dedupe)
            else dedup_mod.overfetch_limit(limit)
        )
        rrf_map = hybrid_mod.rrf_scores_map(dense_ids, sparse_ids)
        ordered = hybrid_mod.rrf_fuse(
            dense_ids, sparse_ids, limit=fuse_n
        )
        dense_by_id = {p.payload["chunk_id"]: p for p in dense_points}
        points = hybrid_mod.materialize_hits(
            ordered,
            dense_by_id=dense_by_id,
            chunks_by_id=chunks,
            rrf_scores=rrf_map,
        )
        if dedupe and not version:
            points = dedup_mod.dedupe_points(points, limit)
        else:
            points = points[:limit]
        return points

    # Dense-only path (Phase 1–2 measurement).
    fetch = limit if (version or not dedupe) else dedup_mod.overfetch_limit(limit)
    points = client().query_points(
        collection_name=collection_name(stats),
        query=query_vector(query),
        limit=fetch,
        query_filter=flt,
        with_payload=True,
    ).points
    if dedupe and not version:
        points = dedup_mod.dedupe_points(points, limit)
    else:
        points = points[:limit]
    return points


def search(
    query: str,
    limit: int = 5,
    version: str | None = None,
    *,
    hybrid: bool = True,
) -> None:
    hits = retrieve(query, limit=limit, version=version, hybrid=hybrid)
    mode = "hybrid" if hybrid else "dense"
    print(f"\n=== {query}" + (f"   [version={version}]" if version else "") + f"   [{mode}]")
    for rank, hit in enumerate(hits, 1):
        p = hit.payload
        head = " > ".join(p["heading_path"]) or "(none)"
        print(f"\n{rank}. {hit.score:.3f}  {p['sqlalchemy_version']}  {p['source_path']}")
        print(f"   {head}")
        print(f"   {p['text'][:200].strip()}...")


def main() -> None:
    argv = sys.argv[1:]
    if "--search" in argv:
        query = argv[argv.index("--search") + 1]
        version = argv[argv.index("--version") + 1] if "--version" in argv else None
        hybrid = "--dense-only" not in argv
        search(query, version=version, hybrid=hybrid)
    else:
        build(recreate="--recreate" in argv)


if __name__ == "__main__":
    main()
