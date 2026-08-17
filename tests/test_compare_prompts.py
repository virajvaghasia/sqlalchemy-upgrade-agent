"""
Pin the three D43 prompt variants.

These tests never call Ollama. They check the only thing that can silently
rot: that the three system prompts still differ in exactly one sentence, and
that B is still the string `rag.ask` actually ships. If someone edits
`ask.SYSTEM` and forgets this file, B stops being the shipped prompt and the
comparison quietly measures something else.
"""

from rag import ask, compare_prompts as cp


def test_b_is_the_shipped_prompt_not_a_copy():
    """
    B must BE ask.SYSTEM — the object identity check — AND ask.SYSTEM must still
    carry the last-resort wording D43 settled on.

    The identity half alone is worthless: `system_prompt("B")` returns
    `ask.SYSTEM`, so comparing the two is a string compared to itself and
    cannot fail. Mutation-checking caught exactly that (D25). The second half
    is what actually pins production, so editing the shipped clause without
    revisiting D43 breaks a test.
    """
    assert cp.system_prompt("B") is ask.SYSTEM
    assert "Prefer answering from what the sources do say" in ask.SYSTEM
    assert "only if the sources are genuinely silent" in ask.SYSTEM.lower()
    assert "say exactly" not in ask.SYSTEM, "that is prompt A's wording, not the shipped one"


def test_variants_differ_only_in_the_refusal_clause():
    """Strip the refusal sentence from each and the remainder must be identical."""
    a, b, c = (cp.system_prompt(v) for v in "ABC")
    strict = cp.REFUSAL_CLAUSES["A"]
    last_resort = (
        "Prefer answering from what the sources do say, even if they address the question "
        "indirectly. Only if the sources are genuinely silent on the topic, reply: "
        "\"The sources do not answer this.\" "
    )
    assert a.replace(strict, "") == c
    assert b.replace(last_resort, "") == c


def test_a_makes_refusal_the_exit_and_c_removes_it():
    a, c = cp.system_prompt("A"), cp.system_prompt("C")
    assert "say exactly" in a, "A must instruct the canned sentence"
    assert "The sources do not answer this" not in c, "C must grant no permission to refuse"
    assert len(c) < len(a) < len(cp.system_prompt("B"))


def test_both_question_kinds_are_present():
    """One answerable, one the corpus provably cannot answer — the point of the test."""
    kinds = [k.strip() for k, _ in cp.QUESTIONS]
    assert kinds == ["ANSWERABLE", "UNANSWERABLE"]


def test_unanswerable_question_is_a_real_corpus_hole():
    """
    The unanswerable question must actually be unanswerable, or C's failure
    proves nothing. `Session.execute`'s signature lives in the API reference,
    which D07 excluded — so no chunk carries the argument list.
    """
    import json
    from rag import corpus

    _, question = cp.QUESTIONS[1]
    assert "signature" in question and "Session.execute" in question

    path = corpus.REPO_ROOT / "corpus" / "chunks.jsonl"
    if not path.exists():          # corpus not built in this checkout
        return
    with open(path) as fh:
        hits = sum(1 for line in fh if ".. automethod:: Session.execute" in line)
    assert hits == 0, "if the API reference ever enters the corpus, D43's C cell changes meaning"


def test_refusal_detector_is_not_a_verdict():
    """`refused` reports a cell, and is deliberately blind to correctness (D46)."""
    assert cp.refused("The sources do not answer this.")
    assert cp.refused("the sources do not answer this")
    assert not cp.refused("You can no longer call engine.execute() because [1]...")
