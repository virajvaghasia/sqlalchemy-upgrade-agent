"""`study/13-VERIFICATION.md` answers the questions `phases/PHASE-1.md` asks.

Two files, one list of questions, and nothing but discipline keeping them the
same — which is the arrangement this repo has watched fail before. If a
question is reworded in the phase file, the answer file is now answering a
question nobody asks, and no runnable block would notice: `check_runnable`
verifies commands and has no opinion about the prose around them.

So the questions are extracted from PHASE-1.md and required to appear verbatim
in the answers file. Reword one and this test says so.
"""

import collections
import json
import pathlib
import re

from rag import corpus

REPO = pathlib.Path(corpus.REPO_ROOT)
PHASE = REPO / "phases" / "PHASE-1.md"
ANSWERS = REPO / "study" / "13-VERIFICATION.md"

# The Verification section lists the questions as `N. *"..."*`.
QUESTION = re.compile(r'^\d+\.\s+\*"(.+?)"\*\s*$', re.MULTILINE)


def verification_questions() -> list[str]:
    """The questions as PHASE-1.md states them, in order."""
    section = PHASE.read_text().split("## Verification", 1)[1]
    return QUESTION.findall(section)


def test_the_phase_asks_exactly_five_questions():
    """The gate is 'the five cold verification questions'. If that stops being
    five, both this file's name and PHASE-1.md's own prose are wrong."""
    assert len(verification_questions()) == 5


def test_every_question_is_answered_verbatim():
    """Each question appears word for word in the answers file. Rewording one
    in either file breaks this, which is the point — a near-miss paraphrase is
    how the two drift apart while both look fine."""
    answers = ANSWERS.read_text()
    for n, q in enumerate(verification_questions(), start=1):
        assert q in answers, f"Q{n} is not answered verbatim in {ANSWERS.name}: {q!r}"


def test_each_question_has_its_own_section_and_a_spoken_answer():
    """R5.1-R5.5 are one section per question, and each carries a 'Say this'
    block. The four-part shape is the file's whole claim; a section missing the
    spoken answer is the part an interview actually needs."""
    answers = ANSWERS.read_text()
    for n in range(1, 6):
        assert f"### R5.{n} Q{n} —" in answers, f"no section R5.{n} for Q{n}"
    assert answers.count("#### Say this") == 5
    assert answers.count("#### Do not say") == 5


def test_the_answers_file_does_not_claim_to_replace_the_gate():
    """The gate is 'cold, from memory, no notes' (PHASE-1.md). A file of model
    answers is only honest if it says reading it beforehand invalidates the
    sitting — otherwise it quietly converts a recall test into a recognition
    test and the phase's last gate stops measuring anything."""
    answers = ANSWERS.read_text()
    assert "cold, from memory, no notes" in answers
    assert "recognition" in answers


def test_the_spoken_run_carries_all_five_questions_as_headings():
    """R5.7 is the five answers said end to end, for rehearsing as one piece.
    It only works if it is complete -- four spoken answers and a gap is worse
    than no section, because the gap is invisible while reading aloud."""
    answers = ANSWERS.read_text()
    assert "### R5.7 The five, spoken end to end" in answers
    spoken = answers.split("### R5.7 The five, spoken end to end", 1)[1]
    for n, q in enumerate(verification_questions(), start=1):
        assert f"#### {n}. {q}" in spoken, f"R5.7 has no spoken answer for Q{n}"
    assert spoken.count("*Follow-up:*") == 5


def test_the_spoken_run_states_the_numbers_it_rests_on():
    """Every figure quoted in R5.7 is one this repo measured. If a chunker or
    corpus change moves one, the spoken answer becomes a confident wrong
    sentence -- the worst kind, because it is the one said out loud."""
    spoken = ANSWERS.read_text().split("### R5.7", 1)[1]
    stats = json.loads((REPO / "corpus" / "CHUNK_STATS.json").read_text())
    verdicts = json.loads((REPO / "deliverables" / "verdicts.json").read_text())
    counts = collections.Counter(
        v[0] for k, v in verdicts.items() if not k.startswith("_"))

    assert str(stats["n_chunks"]) in spoken, "R5.7 does not quote the chunk count"
    assert f"**{counts['CORRECT']} correct, {counts['PARTIAL']} partial," in spoken
    assert f"**{sum(counts.values())}** probe answers" in spoken
