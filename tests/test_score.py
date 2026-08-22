"""What the Phase 2 scorer must not get wrong.

The scorer is the ruler. A bent ruler does not announce itself — it produces
plausible numbers that are wrong in the same direction every time, and every
Phase 3 decision is then made against them.

These run on hand-written chunks and an injected retriever, so they work in CI
where `corpus/chunks.jsonl` is absent (it is generated, not committed — D11)
and Qdrant is not running.
"""

import contextlib
import io
import json
import warnings

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
    """Is the real stack reachable? Asked once, at import, and it must be SILENT.

    Two traps, both hit for real:

    1. `except BaseException`, not `except Exception`. rag/index.py calls
       sys.exit() when Qdrant is unreachable, and SystemExit does not inherit
       from Exception -- so `except Exception` never fires and pytest dies with
       INTERNALERROR instead of skipping.
    2. stderr is swallowed. With Qdrant down, qdrant_client writes a
       UserWarning to stderr during this probe. `tools/check_runnable.py`
       compares stdout+stderr of every `# runnable` block, so an unsuppressed
       warning here breaks the doc blocks that run pytest collection -- a test
       helper silently invalidating the documentation.
    """
    if not score.CHUNKS_PATH.exists():
        return False
    try:
        with warnings.catch_warnings(), contextlib.redirect_stderr(io.StringIO()):
            warnings.simplefilter("ignore")
            from rag import index
            index.retrieve("ping", limit=1)
        return True
    except BaseException:
        # BaseException, not Exception, and the difference is the whole point:
        # rag/index.py calls sys.exit() when Qdrant is unreachable, which raises
        # SystemExit -- and SystemExit does NOT inherit from Exception. With
        # `except Exception` this guard never fires, and pytest dies with
        # INTERNALERROR instead of skipping. Found the first time Qdrant was
        # actually down, which is the only time the guard matters.
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

    rows = score.score_items(items, chunks, hybrid=False, rerank=False)
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

    Two phrasings of one question, one answer chunk. Under **dense-only** search
    the corpus-vocabulary version retrieves it at rank 1; the way a stuck
    developer would type it does not retrieve it in twenty. That gap is why the
    probe questions are a labelled subset and never the benchmark — and why
    Phase 3 added BM25 (`D67`). This test keeps `hybrid=False` so the original
    failure mode stays visible after hybrid ships as the default.
    """
    chunks = score.load_chunks()
    tidy = {"id": "t", "question": "what replaces Query.from_self() in SQLAlchemy 2.0?",
            "provenance": "breakages", "answerable": True, "answer_chunks": ["c01542"],
            "answer_note": "n", "verified_by": "human"}
    rough = dict(tidy, id="r", provenance="github",
                 question="my old query.from_self() call blew up after upgrading, whats the new way")
    rows = score.score_items([tidy, rough], chunks, hybrid=False, rerank=False)
    assert rows[0]["rank"] == 1
    assert rows[1]["rank"] is None or rows[1]["rank"] > rows[0]["rank"]


# --- refusals (D62) --------------------------------------------------------
#
# The refusal section is the one that needs generation, so it is also the one
# most easily faked into looking right. These inject both collaborators.

class _FakeHit:
    def __init__(self, cid):
        self.payload = {
            "chunk_id": cid,
            "heading_path": CHUNKS[cid]["heading_path"],
            "text": CHUNKS[cid]["text"],
            "source_path": "doc/build/x.rst",
            "sqlalchemy_version": "2.0.51",
        }
        self.score = 0.5


def _refusal_rows(items, answers, hits_for):
    """Run refusal_rows with canned retrieval and canned generation."""
    return score.refusal_rows(
        items, CHUNKS,
        generate=lambda prompt: answers.pop(0),
        retrieve=lambda q: [_FakeHit(c) for c in hits_for(q)],
    )


REFUSAL = "The sources do not answer this. I looked for has_table."


def test_a_refusal_is_detected_by_the_opening_the_prompt_mandates():
    """The detector must be the SAME string the SYSTEM clause demands. If the
    prompt is reworded and this is not, every real refusal reads as an answer."""
    from rag import ask
    assert ask.REFUSAL_OPENING in ask.SYSTEM, (
        "the refusal detector no longer matches the sentence the prompt asks for")
    assert ask.refused(REFUSAL)
    assert ask.refused("  " + REFUSAL)          # leading whitespace is not an answer
    assert not ask.refused("Use inspect(engine).has_table() [1].")


def test_mentioning_the_sources_mid_answer_is_not_a_refusal():
    """Prompt D deliberately produces 'here is the part they cover, and here is
    the part they do not'. That is an ANSWER. A substring test would count it as
    a refusal and silently inflate refusal accuracy."""
    from rag import ask
    partial = ("Use connection.execute() [1]. The sources do not answer the "
               "second half of your question about pooling.")
    assert not ask.refused(partial)


def test_an_unanswerable_item_that_gets_answered_is_counted_as_fabricated():
    items = [{"id": "g001", "question": "has_table?", "answerable": False}]
    rows = _refusal_rows(items, ["Use inspect(engine).has_table() [1]."],
                         lambda q: ["c02000"])
    assert rows[0]["refused"] is False
    assert rows[0]["answerable"] is False


def test_an_over_refusal_is_split_by_whether_the_answer_was_in_the_prompt():
    """The distinction the whole section exists for. Same word, two defects:
    refusing with the chunk present is generation's fault (Q18/Q19); refusing
    with it absent is honest, and retrieval's fault."""
    got = {"id": "g010", "question": "pool timeout?", "answerable": True,
           "answer_chunks": ["c00001"]}
    missed = {"id": "g011", "question": "pool timeout?", "answerable": True,
              "answer_chunks": ["c00001"]}

    with_answer = _refusal_rows([got], [REFUSAL], lambda q: ["c00001", "c02000"])
    assert with_answer[0]["refused"] and with_answer[0]["answer_in_prompt"] is True

    without = _refusal_rows([missed], [REFUSAL], lambda q: ["c02000"])
    assert without[0]["refused"] and without[0]["answer_in_prompt"] is False


def test_answer_in_prompt_honours_the_duplicate_rule():
    """D58 applies here too: the cross-version twin is the same vector, so a
    refusal with the twin in the prompt is still a refusal with the answer in
    the prompt. Scoring it strictly would blame retrieval for generation's bug."""
    item = {"id": "g012", "question": "pool timeout?", "answerable": True,
            "answer_chunks": ["c00001"]}
    rows = _refusal_rows([item], [REFUSAL], lambda q: ["c09001"])  # the twin
    assert rows[0]["answer_in_prompt"] is True


def test_refusals_are_never_folded_into_recall():
    """D62's actual requirement. If the two were averaged, a system that refused
    everything would score better as it got more useless."""
    out = io.StringIO()
    rows = [
        {"id": "g001", "answerable": False, "refused": True, "answer_in_prompt": False},
        {"id": "g002", "answerable": True, "refused": True, "answer_in_prompt": True},
        {"id": "g003", "answerable": True, "refused": False, "answer_in_prompt": True},
    ]
    with contextlib.redirect_stdout(out):
        score.report_refusals(rows)
    text = out.getvalue()
    assert "REFUSALS" in text
    # Not "the word recall is absent" -- the header says "not averaged into
    # recall" on purpose. The requirement is that no recall FIGURE is printed
    # here, so the two can never be read as one score.
    assert "recall@" not in text, "refusal section must not print a recall figure"
    assert "MRR" not in text
    assert "g002" in text, "the generation-defect item must be named, not just counted"
    assert "1/1" in text, "correct refusal on the one unanswerable item"


def test_the_refusal_section_names_fabrications():
    """A fabrication on an unanswerable item is the worst cell in the table and
    must be named, because it is the one that needs a person to look."""
    out = io.StringIO()
    rows = [{"id": "g001", "answerable": False, "refused": False,
             "answer_in_prompt": False}]
    with contextlib.redirect_stdout(out):
        score.report_refusals(rows)
    assert "g001" in out.getvalue()
    assert "FABRICATED" in out.getvalue()


def test_refusals_are_scored_at_the_k_that_ships_not_at_the_retrieval_depth(monkeypatch):
    """Everything else here takes DEPTH=20 and slices it, because depth is free
    (D59). Refusal is different: it is a property of the system as configured,
    and D54 measured that k=10 buys two over-fires and a fabrication. Scoring
    refusals at 20 would report the behaviour of a system nobody runs.

    This drives the REAL default path -- retrieve=None -- because that is the
    one that ships. Passing a fake retriever would prove nothing about it.
    """
    from rag import ask, index

    limits = []

    def fake_retrieve(q, limit=None, **kw):
        limits.append(limit)
        return []

    monkeypatch.setattr(index, "retrieve", fake_retrieve)
    score.refusal_rows(
        [{"id": "g001", "question": "q", "answerable": False}],
        CHUNKS,
        generate=lambda prompt: REFUSAL,
    )
    assert limits == [ask.DEFAULT_K]
    assert ask.DEFAULT_K != score.DEPTH, (
        "if these ever coincide this test stops proving anything")
