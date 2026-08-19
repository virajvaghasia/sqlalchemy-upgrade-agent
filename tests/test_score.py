"""What the Phase 2 scorer must not get wrong.

The scorer is the ruler. A bent ruler does not announce itself — it produces
plausible numbers that are wrong in the same direction every time, and every
Phase 3 decision is then made against them.

These run on hand-written chunks and an injected retriever, so they work in CI
where `corpus/chunks.jsonl` is absent (it is generated, not committed — D11)
and Qdrant is not running.
"""

import json

import pytest

from rag import score


def _chunk(cid, heading, text):
    return {"id": cid, "heading_path": list(heading), "text": text}


# A cross-version duplicate pair: same heading, same text, different tag.
# These are the 437 whose vectors are byte-identical (D58).
PAIR_A = _chunk("c00001", ["Errors", "QueuePool"], "the pool timed out")
PAIR_B = _chunk("c09001", ["Errors", "QueuePool"], "the pool timed out")
# Same text, DIFFERENT heading — the 31 that are NOT identical, and must not
# be treated as interchangeable.
OTHER = _chunk("c05000", ["Tutorial", "Connections"], "the pool timed out")
UNRELATED = _chunk("c02000", ["ORM", "Session"], "sessions are not thread safe")
CHUNKS = {c["id"]: c for c in (PAIR_A, PAIR_B, OTHER, UNRELATED)}


# --- what counts as a hit (D58) --------------------------------------------

def test_a_duplicate_under_the_other_version_counts_as_a_hit():
    """The two copies have identical vectors, so no ranker can prefer one.
    Scoring the miss would measure the corpus, not retrieval."""
    item = {"answerable": True, "answer_chunks": ["c00001"]}
    assert score.rank_of_first_hit(["c09001"], item, CHUNKS) == 1


def test_same_text_under_a_different_heading_is_not_a_hit():
    """The heading path is embedded with the text, so these have different
    vectors — 0 of 31 identical. Treating them as the same chunk would excuse a
    real ranking miss."""
    item = {"answerable": True, "answer_chunks": ["c00001"]}
    assert score.rank_of_first_hit(["c05000"], item, CHUNKS) is None


def test_version_sensitive_items_opt_out_of_the_permissive_rule():
    """When the version IS the answer (D10), the other copy is a miss. Without
    this, the permissive default would quietly excuse the exact failure the
    version skew was kept in the corpus to study."""
    item = {"answerable": True, "answer_chunks": ["c00001"], "version_sensitive": True}
    assert score.rank_of_first_hit(["c09001"], item, CHUNKS) is None
    assert score.rank_of_first_hit(["c00001"], item, CHUNKS) == 1


def test_rank_is_one_based_and_none_means_not_retrieved_at_all():
    """None and 'ranked low' are different facts — rank 6 was a wrong constant,
    rank 23 was search finding nothing (R4.3)."""
    item = {"answerable": True, "answer_chunks": ["c00001"]}
    assert score.rank_of_first_hit(["c02000", "c05000", "c00001"], item, CHUNKS) == 3
    assert score.rank_of_first_hit(["c02000", "c05000"], item, CHUNKS) is None


def test_duplicate_slots_counts_the_wasted_slot():
    assert score.duplicate_slots(["c00001", "c09001", "c02000"], CHUNKS, 5) == 1
    assert score.duplicate_slots(["c00001", "c02000"], CHUNKS, 5) == 0
    # counted within the headline k only — a duplicate at rank 8 costs nothing
    # when the prompt only sees five
    assert score.duplicate_slots(["c00001", "c02000", "c09001"], CHUNKS, 2) == 0


# --- D06 enforced in code, not just documented -----------------------------

def test_validate_refuses_an_item_no_human_verified():
    items = [{"id": "g1", "question": "q", "provenance": "github",
              "answerable": False, "verified_by": None}]
    problems = score.validate(items, CHUNKS)
    assert any("D06" in p for p in problems)


def test_validate_catches_an_answer_chunk_that_is_not_in_the_index():
    """A golden set naming a chunk id that no longer exists scores 0 forever and
    looks like a retrieval failure."""
    items = [{"id": "g1", "question": "q", "provenance": "github", "answerable": True,
              "answer_chunks": ["c99999"], "answer_note": "n", "verified_by": "human"}]
    assert any("not in the index" in p for p in score.validate(items, CHUNKS))


def test_validate_requires_a_note_on_verified_answerable_items():
    items = [{"id": "g1", "question": "q", "provenance": "github", "answerable": True,
              "answer_chunks": ["c00001"], "answer_note": "  ", "verified_by": "human"}]
    assert any("answer_note" in p for p in score.validate(items, CHUNKS))


def test_a_clean_item_produces_no_problems():
    items = [{"id": "g1", "question": "q", "provenance": "breakages", "answerable": True,
              "answer_chunks": ["c00001"], "answer_note": "read it", "verified_by": "human"}]
    assert score.validate(items, CHUNKS) == []


# --- aggregation ------------------------------------------------------------

def test_mrr_counts_a_miss_as_zero_not_as_omitted():
    """Averaging 1/rank over only the questions that were found is a different
    and much kinder number. Two items, one at rank 2, one missed: 0.5/2 = 0.25."""
    rows = [{"answerable": True, "rank": 2, "rank_strict": 2, "dup_slots": 0},
            {"answerable": True, "rank": None, "rank_strict": None, "dup_slots": 0}]
    assert score.aggregate(rows)["mrr"] == pytest.approx(0.25)


def test_recall_at_k_is_a_slice_of_one_deep_retrieval():
    rows = [{"answerable": True, "rank": r, "rank_strict": r, "dup_slots": 0}
            for r in (1, 4, 6, None)]
    a = score.aggregate(rows)
    assert a["recall"][1] == pytest.approx(0.25)
    assert a["recall"][5] == pytest.approx(0.50)
    assert a["recall"][10] == pytest.approx(0.75)
    assert a["not_found_at_depth"] == 1


# --- the statistics the numbers are reported with (D61) ---------------------

def test_wilson_matches_the_interval_phase_2_was_planned_against():
    """PHASE-2.md and D61 both quote ±0.131 at n=50, p=0.6. If this constant
    moves, the argument for reporting flipped items instead of a recall delta
    moves with it."""
    assert score.wilson_half_width(0.6, 50) == pytest.approx(0.131, abs=0.001)


def test_mcnemar_puts_the_bar_at_six_clean_fixes():
    """D61's headline claim, pinned. Six fixes with no regressions is a result;
    eight fixes with two regressions is not."""
    assert score.mcnemar_exact(6, 0) < 0.05
    assert score.mcnemar_exact(5, 0) > 0.05
    assert score.mcnemar_exact(8, 2) > 0.05
    assert score.mcnemar_exact(0, 0) == 1.0


# --- end to end, with retrieval injected ------------------------------------

def test_score_items_runs_without_qdrant():
    items = [{"id": "g1", "question": "pool", "provenance": "github", "answerable": True,
              "answer_chunks": ["c00001"], "answer_note": "n", "verified_by": "human"},
             {"id": "g2", "question": "nothing", "provenance": "github",
              "answerable": False, "verified_by": "human"}]
    rows = score.score_items(items, CHUNKS, retrieve=lambda q: ["c09001", "c02000"])
    assert rows[0]["rank"] == 1           # permissive: the duplicate counts
    assert rows[0]["rank_strict"] is None  # strict: it does not
    assert rows[1]["rank"] is None         # unanswerable items have no rank


def test_the_committed_golden_file_parses_and_is_shaped_right():
    """The file ships as a skeleton. It must still be valid JSON with the keys
    the scorer reads, or Phase 2 starts with a broken artefact."""
    data = json.loads(score.GOLDEN_PATH.read_text())
    assert "_README" in data and isinstance(data["items"], list)
    for it in data["items"]:
        assert set(("id", "question", "provenance", "answerable")) <= set(it)
        assert it["provenance"] in score.PROVENANCE


# --- end to end against the real stack -------------------------------------
#
# Everything above injects a retriever, which is what lets the suite run in CI.
# That leaves the real path -- live Qdrant, the real 3284 chunks, report() --
# executed by nobody. This repo has been bitten by exactly that before: a step
# marked done because the code looked right and was never run. So this one runs
# it, and skips where the stack is absent rather than being deleted.

def _stack_available() -> bool:
    if not score.CHUNKS_PATH.exists():
        return False
    try:
        from rag import index
        index.retrieve("ping", limit=1)
        return True
    except Exception:
        return False


requires_stack = pytest.mark.skipif(
    not _stack_available(), reason="needs corpus/chunks.jsonl and a running Qdrant")


@requires_stack
def test_end_to_end_against_live_retrieval():
    """The whole path: real chunks, real search, aggregate, report, compare.

    Asserts shape rather than scores -- the scores depend on the index and are
    not this test's business. What it catches is the path being broken at all.
    """
    chunks = score.load_chunks()
    items = [{"id": "s1", "question": "what replaces Query.from_self() in SQLAlchemy 2.0?",
              "provenance": "breakages", "answerable": True, "answer_chunks": ["c01542"],
              "answer_note": "smoke", "verified_by": "human"},
             {"id": "s2", "question": "engine.has_table() no longer exists, what is the replacement?",
              "provenance": "breakages", "answerable": False, "verified_by": "human"}]
    assert score.validate(items, chunks) == []

    rows = score.score_items(items, chunks)
    assert len(rows) == 2
    assert len(rows[0]["hits"]) == score.DEPTH
    assert rows[0]["rank"] == 1, "the tidy phrasing should still put c01542 first"
    assert rows[1]["rank"] is None, "an unanswerable item has no rank"

    a = score.aggregate(rows)
    assert a["n_answerable"] == 1 and a["recall"][5] == 1.0
    score.report(rows)                                   # must not raise
    score.compare(rows, [dict(r, rank=None) for r in rows])


@requires_stack
def test_phrasing_alone_can_push_the_answer_out_of_the_index():
    """D60's hardest evidence, pinned so it cannot quietly stop being true.

    Two phrasings of one question, one answer chunk. The corpus-vocabulary
    version retrieves it at rank 1; the way a stuck developer would type it does
    not retrieve it in twenty. This is why the probe questions are a labelled
    subset and never the benchmark.
    """
    chunks = score.load_chunks()
    tidy = {"id": "t", "question": "what replaces Query.from_self() in SQLAlchemy 2.0?",
            "provenance": "breakages", "answerable": True, "answer_chunks": ["c01542"],
            "answer_note": "n", "verified_by": "human"}
    rough = dict(tidy, id="r", provenance="github",
                 question="my old query.from_self() call blew up after upgrading, whats the new way")
    rows = score.score_items([tidy, rough], chunks)
    assert rows[0]["rank"] == 1
    assert rows[1]["rank"] is None or rows[1]["rank"] > rows[0]["rank"]
