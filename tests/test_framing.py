"""Phase 6 Step 1 — source framing. No model, no Qdrant: `run` takes its
retriever and generator as arguments."""
import types

from rag import ask, framing


def hit(cid="c1", text="body"):
    return types.SimpleNamespace(payload={
        "chunk_id": cid, "text": text, "heading_path": ["Migration"],
        "sqlalchemy_version": "2.0.51", "source_path": "migration_20.rst"})


def test_arm_A_is_the_shipped_prompt_verbatim_not_a_copy():
    """If this file rewrote the prompt, the experiment would measure the
    rewrite. `ask.build_prompt` is called."""
    msgs = framing.as_block("how do I migrate?", [hit()])
    assert msgs[-1]["content"] == ask.build_prompt("how do I migrate?", [hit()])
    assert msgs[0]["content"] == ask.SYSTEM


def test_arm_B_changes_the_shape_and_nothing_else():
    """Three changes and no others, so a difference is attributable: question
    first and alone, an assistant turn asking for the pages, the pages as the
    RESULT. Same system prompt, same passages, same numbering."""
    q = "how do I migrate?"
    a, b = framing.as_block(q, [hit()]), framing.as_conversation(q, [hit()])
    assert a[0]["content"] == b[0]["content"], "same system prompt"
    assert [t["role"] for t in b] == ["system", "user", "assistant", "user"]
    assert b[1]["content"] == f"QUESTION: {q}"
    # the passage text survives into arm B unchanged
    assert "body" in b[-1]["content"] and "[1]" in b[-1]["content"]


def test_the_assistant_turn_is_written_not_generated():
    """Arm B costs one model call, same as arm A. If the assistant turn were
    generated the arms would differ by a whole extra generation and the
    comparison would be about tool loops rather than framing."""
    calls = []
    framing.run([{"id": "g1", "question": "q", "answerable": True,
                  "answer_chunks": ["c1"]}],
                chunks={"c1": {"chunk_id": "c1", "text": "body",
                               "heading_path": ["Migration"]}},
                retrieve=lambda q: [hit()],
                gen=lambda m: calls.append(m) or "an answer [1]",
                log=lambda *a: None)
    assert len(calls) == 2, "one call per arm, not three"


def test_retrieval_happens_once_and_both_arms_see_the_same_hits():
    """Two lookups of one query is how a framing difference becomes a
    retrieval difference."""
    seen = []
    framing.run([{"id": "g1", "question": "q", "answerable": True,
                  "answer_chunks": ["c1"]}],
                chunks={"c1": {"chunk_id": "c1", "text": "body",
                               "heading_path": ["Migration"]}},
                retrieve=lambda q: seen.append(q) or [hit()],
                gen=lambda m: "an answer [1]", log=lambda *a: None)
    assert seen == ["q"], "retrieved once, not once per arm"


def test_both_arms_are_read_by_the_same_refusal_detector():
    """Every Phase 4 instrument is a prefix test on ask.REFUSAL_OPENING (D76).
    If arm B's system prompt drifted, refusals would stop being comparable."""
    for build in framing.ARMS.values():
        assert ask.SYSTEM in build("q", [hit()])[0]["content"]


def test_report_counts_only_items_whose_page_was_present(capsys):
    """D72's defect is refusing WITH the page in hand. An item whose page never
    arrived is retrieval's problem and must not land in this column."""
    out = {"A_block": [
        {"id": "a", "answerable": True, "answer_in_prompt": True,
         "answer": ask.REFUSAL_OPENING + " this."},
        {"id": "b", "answerable": True, "answer_in_prompt": False,
         "answer": ask.REFUSAL_OPENING + " this."}]}
    framing.report(out)
    printed = capsys.readouterr().out
    assert "1" in printed.split("A_block")[1][:40]
