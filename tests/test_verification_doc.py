"""`study/13-VERIFICATION.md` answers the questions `phases/PHASE-1.md` asks.

Two files, one list of questions, and nothing but discipline keeping them the
same — which is the arrangement this repo has watched fail before. If a
question is reworded in the phase file, the answer file is now answering a
question nobody asks, and no runnable block would notice: `check_runnable`
verifies commands and has no opinion about the prose around them.

So the questions are extracted from PHASE-1.md and required to appear verbatim
in the answers file. Reword one and this test says so.
"""

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
