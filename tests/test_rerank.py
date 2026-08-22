"""Seat-5 CE promotion — pure logic tests, no model download."""

from __future__ import annotations

from types import SimpleNamespace

from rag import rerank


def _pts(*ids):
    return [SimpleNamespace(payload={"chunk_id": i, "text": i, "heading_path": []}) for i in ids]


def test_promote_noop_when_margin_not_met():
    points = _pts("a", "b", "c", "d", "e", "f", "g", "h", "i", "j")
    # seat5=e score 5; best of 6..10 is f at 5.5 — gap 0.5 < 0.8
    scores = [9, 8, 7, 6, 5, 5.5, 4, 3, 2, 1]
    out = rerank.promote_seat5(points, scores, margin=0.8, tail_end=10)
    assert [p.payload["chunk_id"] for p in out] == list("abcdefghij")


def test_promote_swaps_seat5_when_margin_met():
    points = _pts("a", "b", "c", "d", "e", "f", "g", "h", "i", "j")
    # seat5=e at 5; g at 6.0 → gap 1.0 ≥ 0.8; g is within ranks 6..10
    scores = [9, 8, 7, 6, 5, 4, 6.0, 3, 2, 1]
    out = rerank.promote_seat5(points, scores, margin=0.8, tail_end=10)
    ids = [p.payload["chunk_id"] for p in out]
    assert ids[:5] == ["a", "b", "c", "d", "g"]
    assert "e" in ids[5:]
    assert "f" in ids[5:]


def test_promote_ignores_tail_past_tail_end():
    points = _pts("a", "b", "c", "d", "e", "f", "g", "h", "i", "j")
    # j would win on score but rank 10 with tail_end=9 means ranks 6..9 only
    scores = [9, 8, 7, 6, 5, 4, 4, 4, 4, 100]
    out = rerank.promote_seat5(points, scores, margin=0.8, tail_end=9)
    assert [p.payload["chunk_id"] for p in out][:5] == list("abcde")


def test_promote_noop_on_short_list():
    points = _pts("a", "b", "c")
    out = rerank.promote_seat5(points, [1, 2, 3], margin=0.0, tail_end=10)
    assert [p.payload["chunk_id"] for p in out] == list("abc")


def test_constants_match_measured_zero_regression_point():
    assert rerank.MODEL_ID == "BAAI/bge-reranker-base"
    assert rerank.MARGIN == 0.8
    assert rerank.TAIL_END == 10
    assert rerank.CANDIDATE_DEPTH == 20
