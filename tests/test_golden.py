"""The bench that helps build the golden set must never help *verify* it.

`D06` is the load-bearing rule in Phase 2: the golden dataset is hand-verified,
never auto-generated. A helper that made items easier to add would be a net loss
if it could also mark one verified — the whole point of the ruler is that a
person looked.

So the tests here are mostly about what `rag/golden.py` refuses to do.

They run on temp files, so they need neither `corpus/chunks.jsonl` (generated,
not committed — D11) nor Qdrant.
"""

import json

import pytest

from rag import golden, score


@pytest.fixture
def bench(tmp_path, monkeypatch):
    """A golden file in a temp dir, with rag.golden pointed at it."""
    path = tmp_path / "golden.json"
    path.write_text(json.dumps({"_README": ["test"], "items": []}))
    monkeypatch.setattr(score, "GOLDEN_PATH", path)
    return path


def items(path):
    return json.loads(path.read_text())["items"]


# --- D06, enforced rather than documented ----------------------------------

def test_added_items_are_never_marked_verified(bench):
    """The one thing this tool must not be able to do."""
    golden.add("why does session.query fail now?", "github", None, answerable=True)
    it = items(bench)[0]
    assert it["verified_by"] is None
    assert it["verified_on"] is None


def test_an_added_item_does_not_pass_the_scorer(bench):
    """End to end with score.validate: whatever this tool writes must still be
    rejected until a person edits it. If this ever passes, the bench has
    quietly become the verifier."""
    golden.add("q", "github", None, answerable=True)
    problems = score.validate(items(bench), {})
    assert any("D06" in p for p in problems)


def test_provenance_is_constrained_to_the_scorer_s_set(bench):
    """A typo'd provenance would silently create a new bucket and break the
    with/without-breakages split D60 depends on."""
    with pytest.raises(SystemExit):
        golden.add("q", "twitter", None, answerable=True)
    assert items(bench) == []


# --- ids and shape ----------------------------------------------------------

def test_ids_increment_and_do_not_collide(bench):
    for q in ("one", "two", "three"):
        golden.add(q, "github", None, answerable=True)
    assert [i["id"] for i in items(bench)] == ["g001", "g002", "g003"]


def test_ids_survive_a_gap_rather_than_reusing_a_number(bench):
    """Reusing a deleted id would silently re-point any note that cited it."""
    golden.add("one", "github", None, answerable=True)
    golden.add("two", "github", None, answerable=True)
    data = json.loads(bench.read_text())
    data["items"] = [data["items"][1]]          # g001 deleted
    bench.write_text(json.dumps(data))
    golden.add("three", "github", None, answerable=True)
    assert [i["id"] for i in items(bench)] == ["g002", "g003"]


def test_unanswerable_items_carry_no_answer_chunks_field(bench):
    """score.validate rejects an unanswerable item that has answer_chunks set,
    so the bench must not create one."""
    golden.add("what does SQLAlchemy 2.1 change?", "github", None, answerable=False)
    it = items(bench)[0]
    assert it["answerable"] is False
    assert "answer_chunks" not in it


def test_answerable_items_start_with_an_empty_answer_chunks_list(bench):
    golden.add("q", "migration_guide", None, answerable=True)
    assert items(bench)[0]["answer_chunks"] == []


def test_the_readme_block_is_preserved_across_writes(bench):
    """The file's _README explains the verification procedure. A helper that
    dropped it would leave the next person with no instructions."""
    golden.add("q", "github", None, answerable=True)
    assert json.loads(bench.read_text())["_README"] == ["test"]
