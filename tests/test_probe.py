"""The failure report must not quietly start grading itself.

`deliverables/FAILURES.md` is what Phase 3's before/after gets measured against.
If the script ever decides which of its own answers were correct, that number is
self-consistency rather than truth (D06, D46) — and every Phase 3 claim built on
it inherits the softness.

So these tests guard the boundary between *signal* and *verdict*, and the split
that makes a failure actionable (D45).
"""

import json
import types

import pytest

from rag import corpus, probe


def hit(text, version="2.0.51"):
    return types.SimpleNamespace(
        score=0.5,
        payload={
            "chunk_id": "c00001", "sqlalchemy_version": version,
            "source_path": "doc/build/core/x.rst", "heading_path": ["H"],
            "text": text, "n_chars": len(text), "has_code": False,
        },
    )


# --- the boundary that must not move ---------------------------------------

def test_no_expected_answers_are_stored():
    """Each question carries a question, a category, and a SYMBOL — a string
    that must appear in a retrieved chunk. Never an expected answer. Storing one
    would make this a golden set written by the wrong author (D06)."""
    for entry in probe.QUESTIONS:
        assert len(entry) == 3, f"a question grew a fourth field: {entry}"
        question, category, symbol = entry
        assert isinstance(question, str) and question.strip()
        assert category in probe.CATEGORIES
        assert symbol is None or isinstance(symbol, str)


def test_signals_contain_no_verdict():
    """`correct`, `wrong`, `score`, `grade` — none of these may appear. The
    script reports what is mechanically true and stops."""
    sig = probe.signals("q?", None, [hit("body")], "an answer [1]")
    forbidden = {"correct", "wrong", "grade", "verdict", "pass", "fail", "score"}
    assert not (forbidden & set(sig)), f"a verdict field appeared: {forbidden & set(sig)}"


# --- D45: the split that decides whether Phase 3 can help ------------------

def test_symbol_present_in_corpus_but_not_retrieved_is_a_retrieval_failure(monkeypatch):
    monkeypatch.setattr(probe, "corpus_chunk_count", lambda s: 6)
    sig = probe.signals("q?", "table_names", [hit("nothing relevant here")], "answer")
    assert sig["symbol_missing"] and sig["retrieval_failure"] and not sig["ceiling"]


def test_symbol_absent_from_the_whole_corpus_is_the_ceiling(monkeypatch):
    """No phase can fix this one — there is nothing to find."""
    monkeypatch.setattr(probe, "corpus_chunk_count", lambda s: 0)
    sig = probe.signals("q?", "has_table", [hit("nothing relevant here")], "answer")
    assert sig["ceiling"] and not sig["retrieval_failure"]


def test_the_two_are_mutually_exclusive(monkeypatch):
    """Reporting both would double-count a single failure in the summary."""
    for count in (0, 1, 12):
        monkeypatch.setattr(probe, "corpus_chunk_count", lambda s, c=count: c)
        sig = probe.signals("q?", "sym", [hit("no match")], "answer")
        assert not (sig["retrieval_failure"] and sig["ceiling"])


def test_a_retrieved_symbol_is_neither(monkeypatch):
    monkeypatch.setattr(probe, "corpus_chunk_count", lambda s: 6)
    sig = probe.signals("q?", "table_names", [hit("use inspect().get_table_names()")], "a [1]")
    assert not sig["symbol_missing"] and not sig["retrieval_failure"] and not sig["ceiling"]


# --- the other signals -----------------------------------------------------

def test_refusal_is_detected_by_the_exact_phrase_the_prompt_asks_for():
    sig = probe.signals("q?", None, [hit("x")], "The sources do not answer this.")
    assert sig["refused"]


def test_duplicate_slots_counts_repeats_not_distinct_texts():
    """D38: the same text at two versions occupies two of five slots."""
    same = "identical passage"
    sig = probe.signals("q?", None, [hit(same, "1.4.52"), hit(same, "2.0.51"), hit("other")],
                        "answer [1]")
    assert sig["duplicate_slots"] == 1
    assert sig["version_mixed"]


def test_short_answers_are_not_flagged_uncited():
    """A refusal has no citations and should not be reported as an uncited
    claim — that would make every correct refusal look like a failure."""
    sig = probe.signals("q?", None, [hit("x")], "The sources do not answer this.")
    assert not sig["uncited"]


def test_a_long_answer_with_no_citation_is_flagged():
    sig = probe.signals("q?", None, [hit("x")], " ".join(["word"] * 40))
    assert sig["uncited"]


# --- the report that was actually produced ---------------------------------

REPORT = probe.REPORT_PATH.read_text() if probe.REPORT_PATH.exists() else None
needs_report = pytest.mark.skipif(REPORT is None, reason="no FAILURES.md — run rag.probe")


@needs_report
def test_every_question_has_an_unverified_verdict_line():
    """Until a human reads them. If this count ever drops to zero because the
    script filled them in, D46 has been violated."""
    assert REPORT.count("**Verdict:** `UNVERIFIED`") == len(probe.QUESTIONS)


@needs_report
def test_the_report_shows_what_was_retrieved():
    """A failure you cannot see the sources for is not diagnosable, which is the
    whole reason this file exists rather than a summary table."""
    assert "### What was retrieved" in REPORT
    assert REPORT.count("### What was retrieved") == len(probe.QUESTIONS)


@needs_report
def test_the_report_states_that_signals_are_not_verdicts():
    assert "UNVERIFIED" in REPORT
    assert "not verdicts" in REPORT or "they are not verdicts" in REPORT.lower()
