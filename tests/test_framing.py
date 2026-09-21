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


def row(i, answer, answerable=True, present=True):
    return {"id": i, "answer": answer, "answerable": answerable,
            "answer_in_prompt": present}


REFUSE = ask.REFUSAL_OPENING + " this."


def test_cells_separate_the_three_rows_a_single_refusal_count_hides():
    """Refusing with the page present is the defect; refusing with it absent is
    honest; answering an unanswerable item is a fabrication. One number would
    add a fix in the first row to a cost in the other two."""
    c = framing.cells([
        row("p1", REFUSE), row("p2", "ans [1]"),
        row("a1", "ans [1]", present=False), row("a2", REFUSE, present=False),
        row("u1", "invented", answerable=False, present=False),
        row("u2", REFUSE, answerable=False, present=False)])
    assert (c["present"], c["over_refused"]) == (2, ["p1"])
    assert (c["absent"], c["absent_answered"]) == (2, ["a1"])
    assert (c["unanswerable"], c["fabricated"]) == (2, ["u1"])


def test_a_willingness_shift_shows_as_fixes_in_one_row_and_breaks_in_another():
    """The Mac's run in miniature: B answers a page-present item A refused (a
    fix) AND a page-absent item A refused (not a fix -- declining was honest)
    AND an unanswerable one (a fabrication). If `flips` scored all three as
    'answered more = better', the cost would read as a gain."""
    a = [row("p", REFUSE), row("x", REFUSE, present=False),
         row("u", REFUSE, answerable=False, present=False)]
    b = [row("p", "ans [1]"), row("x", "ans", present=False),
         row("u", "invented", answerable=False, present=False)]
    f = framing.flips(a, b)
    assert f["present"] == (["p"], [])
    assert f["absent"] == ([], ["x"])
    assert f["unanswerable"] == ([], ["u"])


def test_flips_pair_by_id_and_skip_items_missing_from_one_arm():
    """D61: a paired comparison over two item sets is two averages."""
    f = framing.flips([row("p", REFUSE), row("only_a", REFUSE)],
                      [row("p", "ans [1]")])
    assert f["present"] == (["p"], [])


def test_select_items_keeps_the_answerable_slice_and_appends_unanswerable():
    """`--n` must mean what it meant for the runs already saved, or the
    page-present row stops being comparable with them."""
    golden = [{"id": "g1", "answerable": True}, {"id": "g2", "answerable": False},
              {"id": "g3", "answerable": True}, {"id": "g4", "answerable": True}]
    assert [i["id"] for i in framing.select_items(golden, 2)] == ["g1", "g3", "g2"]


def test_report_says_so_when_fabrication_was_not_measured(capsys):
    """The first Mac run had zero unanswerable rows and its table looked
    complete. An unmeasured column must not read as a zero."""
    framing.report({"A_block": [row("p", REFUSE)],
                    "B_conversation": [row("p", "ans [1]")]})
    assert "fabrication NOT measured" in capsys.readouterr().out
