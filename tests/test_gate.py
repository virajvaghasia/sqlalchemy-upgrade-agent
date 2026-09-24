"""Phase 6 — the CI quality gate. Pure logic: no Qdrant, no model."""
import json

import pytest

from rag import gate


def row(i, rank, answerable=True, hits=None):
    return {"id": i, "rank": rank, "answerable": answerable,
            "hits": hits or [f"{i}-c{n}" for n in range(20)]}


def test_one_broken_item_blocks_even_when_the_change_is_a_net_gain():
    """Round 14's rule and the reason: five fixes do not buy one lost answer
    without a human saying so."""
    base = [row("g1", 3)] + [row(f"f{n}", None) for n in range(5)]
    now = [row("g1", 9)] + [row(f"f{n}", 1) for n in range(5)]
    result = gate.paired(base, now)
    assert result["broken"] == ["g1"] and len(result["fixed"]) == 5
    assert gate.blocked(result)


def test_rank_6_is_broken_and_rank_5_is_not():
    """The boundary is the prompt's k: what matters is what reaches the model."""
    assert gate.paired([row("g", 5)], [row("g", 5)])["broken"] == []
    assert gate.paired([row("g", 5)], [row("g", 6)])["broken"] == ["g"]


def test_fixes_alone_pass():
    result = gate.paired([row("g", None)], [row("g", 2)])
    assert result["fixed"] == ["g"] and not gate.blocked(result)


def test_deleting_the_item_you_broke_does_not_pass():
    """The ruler cannot be moved by the thing being graded."""
    result = gate.paired([row("g1", 1), row("g2", 1)], [row("g1", 1)])
    assert result["missing"] == ["g2"]
    assert any("ruler changed" in r for r in gate.blocked(result))


def test_relabelling_an_item_unanswerable_does_not_hide_a_break():
    result = gate.paired([row("g", 1)], [row("g", None, answerable=False)])
    assert result["relabelled"] == ["g"] and result["broken"] == []
    assert gate.blocked(result)


def test_new_items_are_unpaired_not_broken():
    result = gate.paired([row("g1", 1)], [row("g1", 1), row("g2", None)])
    assert result["unpaired"] == ["g2"] and not gate.blocked(result)


def test_unanswerable_items_never_count_as_broken():
    base = [row("u", None, answerable=False)]
    assert not gate.blocked(gate.paired(base, base))


def test_moved_separates_reshuffled_rankings_from_nothing_changing():
    """Found on both sides with a different top 5 is not a failure, and it is
    the first line to read when a gate result surprises -- a backend drift and
    a code change both show up here before they flip anything."""
    same = row("g", 2)
    shuffled = dict(same, hits=list(reversed(same["hits"])))
    assert gate.paired([same], [shuffled])["moved"] == ["g"]
    assert gate.paired([same], [same])["moved"] == []


def test_main_exits_nonzero_and_writes_the_job_summary(tmp_path, monkeypatch, capsys):
    """A gate that prints BLOCKED and exits 0 is a comment, not a gate."""
    (tmp_path / "base.json").write_text(json.dumps({"rows": [row("g", 1)]}))
    (tmp_path / "pr.json").write_text(json.dumps({"rows": [row("g", 7)]}))
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setattr("sys.argv", ["gate", "--baseline", str(tmp_path / "base.json"),
                                     "--rows", str(tmp_path / "pr.json")])
    with pytest.raises(SystemExit) as exit_:
        gate.main()
    assert exit_.value.code == 1
    assert "BLOCKED" in capsys.readouterr().out
    assert "broken       1  g" in summary.read_text()


def test_main_exits_zero_when_nothing_is_lost(tmp_path, monkeypatch):
    (tmp_path / "b.json").write_text(json.dumps({"rows": [row("g", 1)]}))
    monkeypatch.setattr("sys.argv", ["gate", "--baseline", str(tmp_path / "b.json"),
                                     "--rows", str(tmp_path / "b.json")])
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    with pytest.raises(SystemExit) as exit_:
        gate.main()
    assert exit_.value.code == 0


def test_relabelling_the_other_way_is_not_a_free_fix():
    """Flipping an unanswerable item to answerable while its page ranks 1 would
    read as a fix bought by editing the ruler."""
    result = gate.paired([row("g", None, answerable=False)], [row("g", 1)])
    assert result["relabelled"] == ["g"] and result["fixed"] == []


def test_unanswerable_items_are_never_moved_either():
    """They have no answer page, so a reshuffled top 5 says nothing about them."""
    u = row("u", None, answerable=False)
    assert gate.paired([u], [dict(u, hits=list(reversed(u["hits"])))])["moved"] == []
