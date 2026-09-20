"""What the answering step must not quietly lose.

Two properties, both easy to break without noticing:

- **The prompt must carry the version of every source.** Retrieval is
  deliberately unfiltered (D10), so 1.4 and 2.0 passages arrive together. If the
  version does not reach the model, it cannot report a disagreement it has no
  way to see.
- **Sources must always be printed.** An answer without them is indistinguishable
  from a lucky one, and Step 5 cannot diagnose a failure it cannot look at.

Nothing here calls Ollama or Qdrant. Prompt construction is a pure function of
the hits, which is most of what can go wrong.
"""

import types

import pytest

from rag import ask


def hit(n, version="2.0.51", heading=None, text=None):
    """A stand-in for a Qdrant point — only .payload and .score are used."""
    return types.SimpleNamespace(
        score=0.9 - n / 100,
        payload={
            "chunk_id": f"c{n:05d}",
            "sqlalchemy_version": version,
            "source_path": f"doc/build/core/file{n}.rst",
            "heading_path": heading if heading is not None else [f"Heading {n}"],
            "text": text or f"Body text number {n}.",
            "n_chars": 20,
            "has_code": False,
        },
    )


# --- the prompt ------------------------------------------------------------

def test_sources_are_numbered_from_one():
    """The model is told to cite [2]. If numbering starts at 0, every citation
    it produces points at the wrong source and the answer looks verifiable
    while being unverifiable."""
    prompt = ask.build_prompt("q?", [hit(1), hit(2), hit(3)])
    assert "[1]" in prompt and "[2]" in prompt and "[3]" in prompt
    assert "[0]" not in prompt


def test_every_source_carries_its_version():
    """Retrieval is unfiltered on purpose, so both releases arrive together. A
    prompt that drops the version asks the model to spot a version conflict
    using information it was never given."""
    prompt = ask.build_prompt("q?", [hit(1, version="1.4.52"), hit(2, version="2.0.51")])
    assert "SQLAlchemy 1.4.52" in prompt
    assert "SQLAlchemy 2.0.51" in prompt


def test_heading_path_reaches_the_model():
    """Same reason the chunker keeps it and the embedder prepends it: a passage
    saying "this was removed" needs the heading naming what "this" is."""
    prompt = ask.build_prompt("q?", [hit(1, heading=["Working with Engines", "Transactions"])])
    assert "Working with Engines > Transactions" in prompt


def test_full_chunk_text_is_included_not_a_preview():
    """The console prints a 180-character preview. The PROMPT must not — the
    model needs the whole passage to answer from it."""
    body = "x" * 1500
    prompt = ask.build_prompt("q?", [hit(1, text=body)])
    assert body in prompt


def test_the_question_appears_after_the_sources():
    """Ordering is deliberate: sources first, question last, so the question is
    the most recent thing in the context rather than buried above 2000 tokens
    of documentation."""
    prompt = ask.build_prompt("WHY IS THIS BROKEN", [hit(1)])
    assert prompt.index("WHY IS THIS BROKEN") > prompt.index("[1]")


def test_a_missing_heading_does_not_render_as_empty():
    prompt = ask.build_prompt("q?", [hit(1, heading=[])])
    assert "(no heading)" in prompt


# --- the settings that make answers comparable -----------------------------

def test_model_tag_is_pinned():
    """`:latest` would let two machines answer with different weights while
    reporting the same model — the same drift D16 and D36 exist to stop."""
    assert ":" in ask.MODEL and not ask.MODEL.endswith(":latest")


def test_temperature_is_zero():
    """Phase 2 has to score these answers. A system that answers the same
    question two different ways cannot be evaluated."""
    assert ask.TEMPERATURE == 0.0


@pytest.mark.parametrize("instruction", [
    "cite the source number",          # makes a claim checkable
    "do not answer this",              # the refusal option must exist — see below
    "version",                         # so a disagreement can be reported
])
def test_system_prompt_keeps_its_three_jobs(instruction):
    """The refusal clause is load-bearing and was measured, not assumed: without
    it the model invented a full method signature for Session.execute out of its
    own weights, because the corpus provably cannot answer that (D07). With it
    phrased strictly, it refused a question whose answer was in the prompt. The
    surviving wording is a last resort rather than an easy exit."""
    assert instruction.lower() in ask.SYSTEM.lower()


def test_refusal_is_narrowed_to_subject_and_must_name_what_was_sought():
    """
    Prompt D, shipped 2026-08-17 (D54).

    This used to assert the B wording — "prefer answering", "only if". B and the
    stricter A were then measured over 19 questions and refused the SAME 8, so
    D43 had chosen between two identical options (D52). D changes the mechanism:
    partial answers are the expected output, refusal narrows to SUBJECT rather
    than sufficiency, and a refusal must name what was looked for.
    """
    lowered = ask.SYSTEM.lower()
    assert "even partially" in lowered, "partial answers must be the expected output"
    assert "name the specific thing you looked for" in lowered, "refusal must require naming"
    assert "about the subject of the question at all" in lowered, "refusal is scoped to subject"
    assert "say exactly" not in lowered, "the A wording over-refused; see D43"
    assert "genuinely silent" not in lowered, "that is B's sufficiency test; see D52"


def test_a_refusal_with_a_citation_in_front_of_it_is_still_a_refusal():
    """Measured 2026-08-22. A prompt variant asking for a citation before every
    statement produced "[2] The sources do not answer this." on six items, and
    the bare prefix test scored every one as an ANSWER -- turning three refusals
    into apparent fixes in a paired comparison that then read p = 0.000.

    The instrument was broken by the very intervention it was measuring."""
    assert ask.refused("[2] The sources do not answer this.")
    assert ask.refused("[1][3] The sources do not answer this")
    assert ask.refused("  [2]  The sources do not answer this.")


def test_stripping_citations_does_not_turn_the_prefix_test_into_a_search():
    """The property the prefix test exists to protect: prompt D deliberately
    produces "here is the part the sources cover, and here is the part they do
    not", which is an ANSWER. A substring test would score it as a refusal and
    inflate the number in the flattering direction."""
    assert not ask.refused(
        "Use Session.get() [1]. The sources do not answer the second half.")
    assert not ask.refused("[1] Use Session.get(). The sources do not answer that.")


# --- D115: the citation reminder ships in the user turn -----------------------
#
# Phase 4 measured variant `H` and it was held (`D83`) because its REFUSAL effect
# did not reproduce across machines. Its CITATION effect did: uncited 65% -> 10%
# on the Mac and 43% -> 8% on the lab. `D115` ships it for that effect only, and
# these tests pin the shape so the thing that shipped cannot drift from the thing
# that was measured.

def test_the_citation_reminder_is_in_the_shipped_prompt():
    """`D73` measured 65% of answered questions citing nothing at all.

    The rule was already in SYSTEM and was ignored; moving the same words into
    the user turn, next to the ANSWER cue, is the whole of variant `H` (`D74`).
    """
    prompt = ask.build_prompt("q?", [hit(1)])
    assert ask.REMINDER in prompt
    assert "cite the source number" in prompt


def test_the_reminder_lands_before_the_answer_cue_not_after_it():
    """Anything after `ANSWER:` reads as the first words of the answer, so the
    model would be completing our sentence instead of obeying the instruction.
    `D74` is the measurement that position, not emphasis, is what worked."""
    prompt = ask.build_prompt("q?", [hit(1)])
    assert prompt.endswith("ANSWER:")
    assert prompt.count("ANSWER:") == 1
    assert prompt.index(ask.REMINDER) < prompt.index("ANSWER:")


def test_the_pre_D115_prompt_is_still_reachable():
    """Every figure taken before `D115` — `D72`'s 0.43, `D109`'s 11 of 30 — was
    measured on the prompt without this sentence. `compare_prompts` needs that
    exact prompt to stay reproducible as its control, or the historical arm
    silently becomes the new one and the comparison measures nothing."""
    shipped = ask.build_prompt("q?", [hit(1)])
    legacy = ask.build_prompt("q?", [hit(1)], reminder="")
    assert ask.REMINDER not in legacy
    assert legacy.endswith("ANSWER:")
    assert legacy != shipped
    assert legacy == shipped.replace(ask.REMINDER + "\n\n", "")


def test_the_system_prompt_did_not_change_when_H_shipped():
    """`H` is a user-turn change and nothing else (`PHASE4_VARIANTS["H"]` was
    `ask.SYSTEM` itself). If SYSTEM moves, this is no longer the `H` that two
    machines measured."""
    assert "Before answering:" not in ask.SYSTEM
    assert ask.REMINDER not in ask.SYSTEM
