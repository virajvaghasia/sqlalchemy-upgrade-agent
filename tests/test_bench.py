"""The latency report: its arithmetic, and its refusal to time a path that does not ship.

No model and no index: the staged retrieval and the reference are stand-ins.
"""

import pytest

from rag import bench


def test_percentile_is_nearest_rank_on_a_hundred_values():
    values = list(range(1, 101))
    assert bench.percentile(values, 50) == 50
    assert bench.percentile(values, 95) == 95
    assert bench.percentile(values, 100) == 100


def test_percentile_returns_a_measured_value_not_an_interpolation():
    assert bench.percentile([10.0, 20.0, 30.0, 40.0], 50) == 20.0
    assert bench.percentile([10.0, 20.0, 30.0, 40.0], 95) == 40.0


def test_percentile_of_nothing_is_an_error():
    with pytest.raises(ValueError):
        bench.percentile([], 50)


def _timed(question, limit):
    ms = {stage: float(n + 1) for n, stage in enumerate(bench.STAGES)}
    ms["total"] = sum(ms.values())
    return [f"c{question}"], ms


ITEMS = [{"id": f"g{n:03d}", "question": str(n)} for n in range(1, 5)]


def test_run_summarizes_every_stage_and_the_total():
    result = bench.run(ITEMS, 5, timed=_timed, reference=lambda q, k: [f"c{q}"], log=lambda *a: None)
    assert [r["id"] for r in result["rows"]] == ["g001", "g002", "g003", "g004"]
    assert set(result["summary"]) == {*bench.STAGES, "total"}
    assert result["summary"]["rerank"]["p50_ms"] == 5.0
    assert result["summary"]["total"]["p95_ms"] == 15.0


def test_run_stops_when_the_staged_path_disagrees_with_index_retrieve():
    with pytest.raises(SystemExit, match="no longer mirrors index.retrieve"):
        bench.run(ITEMS, 5, timed=_timed, reference=lambda q, k: ["something else"], log=lambda *a: None)
