"""Phase 3 lever 1 — cross-version twin collapse at retrieve time."""

from __future__ import annotations

from types import SimpleNamespace

from rag import dedup


def _hit(version: str, heading: list[str], text: str, score: float = 0.9):
    return SimpleNamespace(
        score=score,
        payload={
            "sqlalchemy_version": version,
            "heading_path": heading,
            "text": text,
            "chunk_id": f"{version}:{heading[0]}",
            "source_path": "doc/build/x.rst",
        },
    )


def test_dedupe_collapses_a_cross_version_twin():
    h = ["Errors", "engine.execute"]
    t = "engine.execute is gone"
    points = [
        _hit("1.4.52", h, t, 0.99),
        _hit("2.0.51", h, t, 0.99),
        _hit("2.0.51", ["Other"], "something else", 0.80),
    ]
    out = dedup.dedupe_points(points, limit=2)
    assert len(out) == 2
    assert out[0].payload["sqlalchemy_version"] == "2.0.51"
    assert out[0].payload["text"] == t
    assert out[1].payload["text"] == "something else"


def test_dedupe_prefers_2_0_even_when_1_4_ranked_first():
    h = ["Session", "autobegin"]
    t = "Session begins on first use"
    # 1.4 first in the list (same score); preferred version must win the seat.
    points = [
        _hit("1.4.52", h, t, 0.95),
        _hit("2.0.51", h, t, 0.95),
    ]
    out = dedup.dedupe_points(points, limit=1)
    assert len(out) == 1
    assert out[0].payload["sqlalchemy_version"] == "2.0.51"


def test_dedupe_does_not_collapse_same_text_under_different_headings():
    """D58's second group: same text, different heading → different vectors."""
    t = "identical prose, different home"
    points = [
        _hit("2.0.51", ["Path A"], t, 0.9),
        _hit("2.0.51", ["Path B"], t, 0.89),
    ]
    out = dedup.dedupe_points(points, limit=2)
    assert len(out) == 2


def test_dedupe_fills_limit_after_dropping_twins():
    """Without over-fetch awareness: three unique keys after collapsing two twins."""
    points = [
        _hit("1.4.52", ["A"], "aa", 0.99),
        _hit("2.0.51", ["A"], "aa", 0.99),
        _hit("1.4.52", ["B"], "bb", 0.90),
        _hit("2.0.51", ["B"], "bb", 0.90),
        _hit("2.0.51", ["C"], "cc", 0.80),
    ]
    out = dedup.dedupe_points(points, limit=3)
    assert [p.payload["text"] for p in out] == ["aa", "bb", "cc"]
    assert all(p.payload["sqlalchemy_version"] == "2.0.51" for p in out)


def test_overfetch_scales_with_limit():
    assert dedup.overfetch_limit(5) >= 15
    assert dedup.overfetch_limit(20) >= 40
    assert dedup.overfetch_limit(100) <= 200


def test_dedup_key_matches_score_module():
    from rag import score
    chunk = {"heading_path": ["X"], "text": "y"}
    assert dedup.dedup_key(chunk) == score.dedup_key(chunk)
