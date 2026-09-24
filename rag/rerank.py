"""
Cross-encoder rerank — seat-5 promotion only (Phase 3, lever 3).

A full `CrossEncoder` reorder of the hybrid top-20 **raises** recall@5
(57 → 60) and also **breaks ten** items hybrid already had (flips matter,
not averages). Hybrid-heavy RRF with the CE list is a no-op once
weighted safely. Freeze-head fill always keeps broken > 0 until head=5
(identity).

What survives a sweep on the 100-item set (Mac, 2026-08-21):

    replace only hybrid seat 5 with the best CE-scored chunk from ranks 6..10
    when (score_tail − score_seat5) ≥ 0.8

Measured: **1 fixed** (`g017`), **0 broken**, recall@5 57 → 58. Absents stay 17
— a reranker cannot invent a page.

Model: `BAAI/bge-reranker-base` (the bge-reranker family; base fits Mac +
leaves room for Ollama on the 3060). Full replace and deeper tails were measured
and rejected, not forgotten.
"""

from __future__ import annotations

from typing import Any, Sequence

# Pinned like embed.MODEL_REVISION — changing it means re-measure, not retune.
MODEL_ID = "BAAI/bge-reranker-base"

# The line above said "pinned" from 2026-08-21 and nothing was: CrossEncoder got
# the model id and no revision, so every load took whatever `main` pointed at.
# Found 2026-09-12 building the CI gate, where it stops being cosmetic -- a
# fresh runner downloads `main`, and a new upload could flip `g017` (this
# lever's only fix) with no code change, and the gate would blame the PR.
# This is the snapshot every seat-5 reranker measurement was taken with: it is the only one
# in the Mac's Hugging Face cache, and refs/main there names it.
MODEL_REVISION = "2cfc18c9415c912f9d8155881c133215df768a70"

# How many hybrid hits must be on the desk before promotion can see a tail.
CANDIDATE_DEPTH = 20

# Promote from ranks 6..TAIL_END inclusive (1-based). Wider tails re-broke items.
TAIL_END = 10

# Minimum CE logits gap (best-of-tail minus seat 5) to allow the swap.
MARGIN = 0.8

_MODEL = None


def get_model():
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import CrossEncoder
        from rag import embed

        _MODEL = CrossEncoder(MODEL_ID, revision=MODEL_REVISION,
                              device=embed.pick_device(None))
    return _MODEL


def reset_model() -> None:
    """Tests only."""
    global _MODEL
    _MODEL = None


def passage_text(payload: dict) -> str:
    # Probe that set MARGIN/TAIL_END scored `text` only. Heading is already in
    # the hybrid ranking; adding it here changed nothing useful and would
    # silently invalidate the measured constants.
    return payload.get("text") or ""


def ce_scores(query: str, points: Sequence[Any]) -> list[float]:
    if not points:
        return []
    pairs = [(query, passage_text(p.payload)) for p in points]
    raw = get_model().predict(pairs, show_progress_bar=False)
    return [float(s) for s in raw]


def promote_seat5(
    points: Sequence[Any],
    scores: Sequence[float],
    *,
    margin: float = MARGIN,
    tail_end: int = TAIL_END,
) -> list[Any]:
    """Swap hybrid seat 5 with the best CE-scored hit in ranks 6..tail_end.

    No-op when the list is shorter than `tail_end`, or the margin is not met.
    Pure function of scores — unit-tested without loading the model.
    """
    points = list(points)
    n = len(points)
    if n < 6 or len(scores) != n:
        return points
    end = min(tail_end, n)  # 1-based inclusive
    if end < 6:
        return points

    seat5_i = 4
    tail_is = range(5, end)  # 0-based indices for ranks 6..end
    best_i = max(tail_is, key=lambda i: scores[i])
    if scores[best_i] - scores[seat5_i] < margin:
        return points

    out = points[:4] + [points[best_i]]
    rest = [p for i, p in enumerate(points) if i != best_i and i >= 4]
    return out + rest


def rerank(query: str, points: Sequence[Any]) -> list[Any]:
    """Score with the cross-encoder and apply the measured promotion rule."""
    points = list(points)
    if len(points) < 6:
        return points
    return promote_seat5(points, ce_scores(query, points))
