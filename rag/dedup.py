"""
Cross-version duplicate collapse for retrieval (Phase 3, first lever).

874 of 3284 chunks are one half of a pair that shares `(heading_path, text)` —
the unit `rag/embed.py` embeds — and those pairs have **byte-identical vectors**
(D38, D58). Qdrant therefore returns both into adjacent top-k slots whenever
either is relevant. That wastes a prompt seat on a twin page.

Phase 2 measured the tax and refused to hide it (`slots_lost_to_duplicates`).
Phase 3 removes it at retrieve time: over-fetch, keep one copy per key, prefer
the 2.0.51 half because this product answers 1.4 → 2.0 upgrades (`D66`).

Scoring still uses the same `dedup_key` for "either twin is a hit" (`D58`).
"""

from __future__ import annotations

from typing import Any, Iterable

# Upgrade-agent default: when both halves are equally close, keep the 2.0 page.
PREFERRED_VERSION = "2.0.51"


def dedup_key(chunk: dict) -> tuple:
    """The unit that decides a vector, and therefore a duplicate.

    `rag/embed.py` prepends the heading path before embedding, so two chunks
    match iff BOTH their heading path and text match — measured: 437 such
    pairs, 437 of 437 with byte-identical vectors, against 31 same-text
    different-heading pairs of which 0 of 31 are identical (D58).
    """
    return (tuple(chunk["heading_path"]), chunk["text"])


def dedup_key_from_payload(payload: dict) -> tuple:
    return (tuple(payload["heading_path"]), payload["text"])


def prefer_point(a: Any, b: Any) -> Any:
    """Pick the preferred twin. Payloads must carry `sqlalchemy_version`."""
    va = a.payload.get("sqlalchemy_version")
    vb = b.payload.get("sqlalchemy_version")
    if va == PREFERRED_VERSION and vb != PREFERRED_VERSION:
        return a
    if vb == PREFERRED_VERSION and va != PREFERRED_VERSION:
        return b
    # Same version or neither preferred — keep the earlier (higher-ranked) one.
    return a


def dedupe_points(points: Iterable[Any], limit: int) -> list[Any]:
    """Collapse cross-version twins, preserving score order of first unique key.

    `points` must already be in descending score order. Walk the list once:
    the first time a `(heading_path, text)` key appears sets its rank; a later
    twin updates which version is kept (`PREFERRED_VERSION`) without changing
    that rank. Stop accepting *new* keys once `limit` distinct keys are held,
    but keep scanning so a preferred twin can still replace an earlier copy.
    """
    points = list(points)
    best: dict[tuple, Any] = {}
    order: list[tuple] = []
    for p in points:
        key = dedup_key_from_payload(p.payload)
        if key not in best:
            if len(order) >= limit:
                continue
            best[key] = p
            order.append(key)
        else:
            best[key] = prefer_point(best[key], p)
    return [best[k] for k in order]


def overfetch_limit(limit: int, factor: int = 3) -> int:
    """How many Qdrant hits to pull so dedupe can still fill `limit`.

    ~26% of the index is a twin half (D38). 3× is enough for top-20 with margin;
    capped so a huge k does not pull the whole collection.
    """
    return min(max(limit * factor, limit + 10), 200)
