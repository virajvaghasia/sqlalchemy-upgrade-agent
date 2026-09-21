"""
Hybrid retrieval: dense (Qdrant) + BM25, fused with RRF (Phase 3, lever 2).

Reciprocal Rank Fusion ignores raw scores and only looks at *ranks*:

    score(d) = Σ  1 / (k_channel + rank_channel(d))

That is the right combiner when the two channels are not on the same scale —
cosine similarity is roughly 0.3–0.7 here; BM25 scores are unbounded. Adding
them would let whichever channel shouts louder own the list.

Constants below were swept on the 100-item golden set (2026-08-21):

| kd | kb | recall@5 | fixed | broken |
|----|----|----------|-------|--------|
| 20 | 100 | 0.582 | 6 | **0** |
| **25** | **90** | **0.615** | **9** | **0** |
| 30 | 80 | 0.637 | 13 | 2 |

`kd=25, kb=90` is what ships: the densest *zero-regression* point. Higher
recall with broken items is a worse McNemar story (`D61`). `hybrid=False` on
`retrieve` keeps the dense-only path for re-measurement.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Iterable, Sequence

# Dense gets a stronger vote (smaller k → larger 1/(k+rank)). BM25 is the
# rescue channel, not co-equal — measured: equal k=60 broke five items.
RRF_K_DENSE = 25
RRF_K_SPARSE = 90

# How many hits each channel contributes before fusion. Must be ≥ DEPTH (20)
# used by the scorer; 50 leaves headroom for twins and for BM25 to surface a
# page dense buried past 20.
CHANNEL_DEPTH = 50


def rrf_fuse(
    dense_ids: Sequence[str],
    sparse_ids: Sequence[str],
    *,
    kd: int = RRF_K_DENSE,
    kb: int = RRF_K_SPARSE,
    limit: int = 20,
) -> list[str]:
    """Return chunk ids by descending RRF score, dense-heavy defaults."""
    scores: dict[str, float] = {}
    for rank, cid in enumerate(dense_ids, 1):
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (kd + rank)
    for rank, cid in enumerate(sparse_ids, 1):
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (kb + rank)
    return [cid for cid, _ in sorted(scores.items(), key=lambda kv: -kv[1])[:limit]]


def _payload_from_chunk(chunk: dict) -> dict:
    """Shape a chunks.jsonl row like a Qdrant payload."""
    return {
        "chunk_id": chunk["id"],
        "sqlalchemy_version": chunk["sqlalchemy_version"],
        "source_path": chunk["source_path"],
        "heading_path": chunk["heading_path"],
        "text": chunk["text"],
        "n_chars": chunk["n_chars"],
        "char_start": chunk["char_start"],
        "char_end": chunk["char_end"],
        "has_code": chunk["has_code"],
    }


def materialize_hits(
    ordered_ids: Sequence[str],
    *,
    dense_by_id: dict[str, Any],
    chunks_by_id: dict[str, dict],
    rrf_scores: dict[str, float] | None = None,
) -> list[Any]:
    """Build Qdrant-shaped hits so callers of `retrieve` stay unchanged.

    Prefer the live Qdrant point when dense already returned it (keeps its
    cosine score in `.score` for `--search` display). BM25-only rescues are
    synthesised from `chunks.jsonl`; their `.score` is the RRF contribution.
    """
    out: list[Any] = []
    for cid in ordered_ids:
        if cid in dense_by_id:
            hit = dense_by_id[cid]
            if rrf_scores is not None:
                # Surface the fused score without losing payload identity.
                hit = SimpleNamespace(score=rrf_scores[cid], payload=hit.payload)
            out.append(hit)
            continue
        chunk = chunks_by_id.get(cid)
        if chunk is None:
            continue
        score = rrf_scores[cid] if rrf_scores else 0.0
        out.append(SimpleNamespace(score=score, payload=_payload_from_chunk(chunk)))
    return out


def rrf_scores_map(
    dense_ids: Sequence[str],
    sparse_ids: Sequence[str],
    *,
    kd: int = RRF_K_DENSE,
    kb: int = RRF_K_SPARSE,
) -> dict[str, float]:
    scores: dict[str, float] = {}
    for rank, cid in enumerate(dense_ids, 1):
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (kd + rank)
    for rank, cid in enumerate(sparse_ids, 1):
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (kb + rank)
    return scores
