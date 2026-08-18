"""The failure report must not quietly start grading itself.

`deliverables/FAILURES.md` is what Phase 3's before/after gets measured against.
If the script ever decides which of its own answers were correct, that number is
self-consistency rather than truth (D06, D46) — and every Phase 3 claim built on
it inherits the softness.

So these tests guard the boundary between *signal* and *verdict*, and the split
that makes a failure actionable (D45).
"""

import json
import re
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
def test_every_question_has_a_verdict_line():
    """
    One verdict line per question, and every value legal.

    This used to assert every line said `UNVERIFIED`, which was the right
    invariant while none had been judged and became false the moment they were
    (2026-08-17). What it was really protecting is that no verdict goes
    *missing* — a question silently losing its line would shrink the golden
    dataset without anything failing.
    """
    lines = re.findall(r"^\*\*Verdict:\*\* `(\w+)`", REPORT, flags=re.M)
    assert len(lines) == len(probe.QUESTIONS)
    assert set(lines) <= {"CORRECT", "WRONG", "PARTIAL", "UNVERIFIED"}


@needs_report
def test_the_report_matches_the_verdict_record():
    """
    `FAILURES.md` renders verdicts from `deliverables/verdicts.json`, so the two
    can drift: edit the markdown by hand and the next regeneration silently
    reverts it. This pins them together, and `tools.apply_verdicts --check` is
    the same assertion as a command.
    """
    if not probe.VERDICTS:
        pytest.skip("no verdict record yet")
    for num, (verdict, why) in probe.VERDICTS.items():
        assert f"**Verdict:** `{verdict}` — {why}" in REPORT, f"entry {num} out of sync"


@needs_report
def test_no_verdict_is_left_empty():
    """A verdict with no reasoning is not a judgement, it is a label."""
    for verdict, why in probe.VERDICTS.values():
        assert verdict == "UNVERIFIED" or len(why.split()) >= 8, why


@needs_report
def test_the_report_shows_what_was_retrieved():
    """A failure you cannot see the sources for is not diagnosable, which is the
    whole reason this file exists rather than a summary table."""
    assert "### What was retrieved" in REPORT
    assert REPORT.count("### What was retrieved") == len(probe.QUESTIONS)


@needs_report
def test_the_report_states_that_signals_are_not_verdicts():
    """
    The signal/verdict boundary must be stated in the file itself, not only in
    the code that writes it.

    The `UNVERIFIED` half of this dropped on 2026-08-17 when the verdicts were
    filled in — its absence is now correct rather than alarming. What still has
    to hold is that a reader is told the signals locate rather than decide, and
    that the verdicts came from a person.
    """
    assert "not verdicts" in REPORT or "they are not verdicts" in REPORT.lower()
    assert "verdicts are a human's" in REPORT


def test_symbol_matching_is_whole_symbol_not_substring():
    """
    `relation` must not match inside `relationship`.

    The naive check counted 798 chunks for `relation` when 0 document
    `orm.relation()` — turning a ceiling case into an apparent retrieval
    failure, and silencing `symbol_missing`, the signal whose whole job is
    telling those apart. Mutation-checked: reverting to `in` fails this.
    """
    assert not probe._contains("use relationship() instead", "relation")
    assert probe._contains("orm.relation() is gone", "relation")
    assert not probe._contains("bindparam is unrelated", "bind")
    # symbols ending in punctuation are self-delimiting
    assert probe._contains("row.keys() raises", "keys()")
    assert probe._contains("select(Issue.id)", "select(")


def test_recorded_symbol_counts_match_the_matcher():
    """
    FAILURES.md quotes a chunk count per symbol. If the matcher changes and the
    report is not regenerated, those numbers silently describe an older rule —
    which is exactly what happened to `relation` (798 recorded, 21 true).
    """
    if REPORT is None:
        pytest.skip("no FAILURES.md")
    for _q, _c, sym in probe.QUESTIONS:
        if not sym:
            continue
        n = probe.corpus_chunk_count(sym)
        assert f"symbol `{sym}` appears in **{n}** corpus chunks" in REPORT, sym
