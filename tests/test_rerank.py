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


def test_the_reranker_is_pinned_to_a_revision_and_the_load_uses_it(monkeypatch):
    """The comment said 'pinned' for three weeks while CrossEncoder got no
    revision. Assert the load, not the constant, or the same gap reopens."""
    import sys
    import types

    seen = {}

    class FakeCE:
        def __init__(self, model_id, **kw):
            seen.update(kw, model_id=model_id)

    from rag import embed

    monkeypatch.setitem(sys.modules, "sentence_transformers", types.SimpleNamespace(CrossEncoder=FakeCE))
    # CI's tests job installs no torch; pick_device(None) would import it.
    monkeypatch.setattr(embed, "pick_device", lambda requested: "cpu")
    rerank.reset_model()
    try:
        rerank.get_model()
    finally:
        rerank.reset_model()
    assert len(rerank.MODEL_REVISION) == 40
    assert seen["revision"] == rerank.MODEL_REVISION


def test_rerank_scores_only_the_passages_whose_scores_are_read(monkeypatch):
    """The promotion rule reads the scores of seat 5 and ranks 6..TAIL_END and nothing
    else. Scoring all 20 candidates spent 14 cross-encoder passes per question on numbers
    no line of code looked at, and the cross-encoder is most of a question's search time."""
    seen = []

    def fake_scores(query, points):
        seen.append([p.payload["chunk_id"] for p in points])
        return [0.0] * len(points)

    monkeypatch.setattr(rerank, "ce_scores", fake_scores)
    pts = _pts(*[f"c{n}" for n in range(1, 21)])
    rerank.rerank("q", pts)
    assert seen == [[f"c{n}" for n in range(5, rerank.TAIL_END + 1)]]


def test_scoring_fewer_passages_gives_the_same_order_as_scoring_all(monkeypatch):
    """Same scores per passage, so the same swap: every seat a best-of-tail can sit in,
    with and without the margin met, on lists of every length the rule handles."""
    for n in range(1, 21):
        pts = _pts(*[f"c{i}" for i in range(1, n + 1)])
        for best in range(6, 12):
            for gap in (0.0, rerank.MARGIN - 0.01, rerank.MARGIN, 5.0):
                score_of = {p.payload["chunk_id"]: (gap if i == best - 1 else 0.0) for i, p in enumerate(pts)}
                score_of["c5"] = 0.0
                monkeypatch.setattr(
                    rerank, "ce_scores", lambda q, ps, s=score_of: [s[p.payload["chunk_id"]] for p in ps]
                )
                want = rerank.promote_seat5(pts, [score_of[p.payload["chunk_id"]] for p in pts])
                assert rerank.rerank("q", pts) == want, (n, best, gap)
