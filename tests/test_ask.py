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
