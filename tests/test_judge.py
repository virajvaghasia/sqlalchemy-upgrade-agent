"""What the Phase 4 citation grader must not get wrong.

Same standard as the scorer: this produces numbers that Phase 4 decisions rest
on, so a plausible-but-wrong figure is worse than no figure.

Everything here runs on hand-written answers with an injected generator, so it
needs neither Ollama nor Qdrant.
"""

import contextlib
import io

import pytest

from rag import judge


# The g065 answer, in shape. It emitted an Alembic script calling
# `op.create_view` (which does not exist on alembic 1.19.1) next to
# `op.create_table` (which does), and carried no citation on the code block.
G065_SHAPE = """You can handle this with an Alembic migration.

```python
def upgrade():
    op.create_table("account", sa.Column("id", sa.Integer))
    op.create_view("account_v", "SELECT * FROM account")
```

That will create both objects in one revision."""


def test_a_code_block_with_no_citation_is_counted():
    """The machine-visible half of the g065 fabrication. Nothing here can know
    that op.create_view is invented -- that needs the real library, and
    tools/audit_golden_fullbar.py already runs 2.0.51. What it can see is
    executable-looking code with no source pointed at."""
    assert judge.uncited_code_blocks(G065_SHAPE) == 1


def test_a_cited_code_block_is_not_counted():
    answer = "Use the 2.0 form [2]:\n\n```python\nsession.get(User, 1)\n```\n"
    assert judge.uncited_code_blocks(answer) == 0


def test_a_citation_inside_the_block_counts():
    answer = "Do this:\n\n```python\n# see [3]\nsession.get(User, 1)\n```\n"
    assert judge.uncited_code_blocks(answer) == 0


def test_a_citation_three_paragraphs_earlier_does_not_launder_the_block():
    """Scoped deliberately. An answer that cites [2] up top and then emits an
    uncited script IS the g065 shape, and crediting the distant citation would
    hide exactly the case this exists for."""
    answer = ("The migration guide covers renames [2].\n\n"
              "Some more prose here about the session.\n\n"
              "Another paragraph entirely.\n\n"
              "```python\nop.create_view('v', 'SELECT 1')\n```\n")
    assert judge.uncited_code_blocks(answer) == 1


# --- the count probe.py structurally cannot produce -------------------------

def test_a_citation_pointing_past_the_last_source_is_out_of_range():
    """probe.py builds its citation set as {n for n in range(1, len(hits)+1)},
    so it only ever looks for numbers that exist -- an answer citing [7] with
    five sources contributes nothing there and reads as `uncited`. Two
    different defects: one model did not cite, the other cited a source it was
    never given."""
    r = judge.citation_report("The fix is documented [7].", n_sources=5)
    assert r["out_of_range"] == [7]
    assert r["in_range"] == []


def test_an_out_of_range_citation_is_not_also_reported_as_uncited():
    """If it were, the two counts would double-report the same answer and any
    total over them would be wrong."""
    r = judge.citation_report("The fix is documented [7].", n_sources=5)
    assert r["out_of_range"] and not r["uncited"]


def test_zero_is_out_of_range():
    """Sources are numbered from 1 in the prompt. [0] points at nothing."""
    assert judge.citation_report("see [0]", n_sources=5)["out_of_range"] == [0]


def test_a_valid_citation_is_in_range():
    r = judge.citation_report("Use Session.get [3].", n_sources=5)
    assert r["in_range"] == [3] and r["out_of_range"] == []


# --- the definitions that must not drift from probe.py ----------------------

def test_uncited_matches_probe_pys_threshold():
    """Both files answer 'did it cite anything'. If the word thresholds drift,
    the Phase 1 deliverable and the Phase 4 report disagree about the same
    answer, and neither is wrong on its own terms."""
    from rag import probe

    long_answer = " ".join(["word"] * (judge.MIN_WORDS_FOR_UNCITED + 1))
    assert judge.citation_report(long_answer, 5)["uncited"]
    assert probe.signals("q", None, [], long_answer)["uncited"]


def test_a_short_uncited_answer_is_not_flagged():
    """Three words with no citation is not a claim worth checking."""
    assert not judge.citation_report("Use Session.get.", 5)["uncited"]


def test_single_source_means_one_of_several():
    r = judge.citation_report("Only this one matters [2].", n_sources=5)
    assert r["single_source"]
    assert not judge.citation_report("Only this [1].", n_sources=1)["single_source"]


def test_the_refusal_detector_is_ask_pys_not_a_second_copy(monkeypatch):
    """Mutation. probe.py once held a second copy of a symbol test and it
    silenced the very signal it existed for. There is one refusal detector,
    beside the prompt clause that mandates the string."""
    from rag import ask

    monkeypatch.setattr(ask, "refused", lambda a: True)
    assert judge.citation_report("a perfectly normal answer [1]", 5)["refused"]


# --- aggregation ------------------------------------------------------------

def _row(**kw):
    base = judge.citation_report("Use Session.get [1].", n_sources=5)
    base.update(id="g001", provenance="breakages")
    base.update(kw)
    return base


def test_refusals_are_excluded_from_every_citation_rate():
    """An answer that declines has nothing to cite. Counting it as `uncited`
    would make the system look worse the more honest it got -- the same trap
    D62 refused to fall into for recall."""
    rows = [_row(refused=True, uncited=True), _row()]
    a = judge.aggregate(rows)
    assert a["n_refused"] == 1 and a["n_answered"] == 1
    assert a["uncited"] == 0, "the refusal must not contribute to the uncited count"


def test_coverage_is_the_fraction_of_prompt_sources_actually_used():
    r = judge.citation_report("Both of these [1] [2].", n_sources=5)
    assert r["coverage"] == 0.4


def test_coverage_of_a_refused_answer_does_not_drag_the_mean_down():
    rows = [_row(refused=True, coverage=0.0), _row(coverage=0.4)]
    assert judge.aggregate(rows)["mean_coverage"] == 0.4


def test_the_report_names_the_items_that_need_a_person():
    """A rate tells you the size; only an id tells you where to look. The two
    defects worth a human read are an invented source and uncited code."""
    rows = [_row(id="g065", uncited_code_blocks=1),
            _row(id="g042", out_of_range=[7])]
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        judge.report(rows, judge.aggregate(rows))
    text = out.getvalue()
    assert "g065" in text and "g042" in text


def test_judge_rows_retrieves_at_the_k_that_ships(monkeypatch):
    """Same rule as --refusals (D62): citation behaviour is a property of the
    configured system. Grading over score.py's DEPTH of 20 would describe a
    system nobody runs."""
    from rag import ask, index, score

    limits = []

    def fake_retrieve(q, limit=None, **kw):
        limits.append(limit)
        return []

    monkeypatch.setattr(index, "retrieve", fake_retrieve)
    monkeypatch.setattr(judge.ask, "build_prompt", lambda q, h: "prompt")
    judge.judge_rows([{"id": "g001", "question": "q"}], generate=lambda p: "answer [1]")
    assert limits == [ask.DEFAULT_K]
    assert ask.DEFAULT_K != score.DEPTH, (
        "if these ever coincide this test stops proving anything")


def test_judge_rows_accepts_both_generate_shapes(monkeypatch):
    """ask.generate returns (answer, timings); test fakes return a string."""
    from rag import index

    monkeypatch.setattr(index, "retrieve", lambda q, limit=None, **kw: [])
    monkeypatch.setattr(judge.ask, "build_prompt", lambda q, h: "prompt")
    item = [{"id": "g001", "question": "q"}]
    assert judge.judge_rows(item, generate=lambda p: "plain [1]")[0]["cited"] == [1]
    assert judge.judge_rows(item, generate=lambda p: ("tuple [2]", {}))[0]["cited"] == [2]


def test_the_report_survives_an_empty_run():
    """A guard, not a feature. `--limit 0`, or a golden file with nothing
    verified, used to crash on rows[0] while formatting the coverage line."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        judge.report([], judge.aggregate([]))
    assert "items asked" in out.getvalue()


def test_the_uncited_code_rate_is_over_answers_that_contain_code():
    """'3 of 4 answers with code cite nothing' and '3 of 91 answers' are
    different claims. The second divides the defect away."""
    rows = [_row(code_blocks=1, uncited_code_blocks=1), _row(code_blocks=0)]
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        judge.report(rows, judge.aggregate(rows))
    assert "100.0%" in out.getvalue(), "1 of the 1 answer with code, not 1 of 2"


def test_the_report_splits_by_provenance():
    """D73 left a mechanism open -- Phase 1's probe reported uncited on 3 of 11
    answered, this reports 31 of 48, and the bands do not overlap. D63 already
    proved phrasing decides retrieval; this split is what tests whether it also
    decides citing. Without it the next run costs another ~100 generations to
    ask the same question."""
    rows = [_row(id="g001", provenance="stackoverflow", uncited=True),
            _row(id="g002", provenance="migration_guide", uncited=False)]
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        judge.report(rows, judge.aggregate(rows))
    text = out.getvalue()
    assert "by provenance" in text
    assert "stackoverflow" in text and "migration_guide" in text


def test_the_provenance_split_excludes_refusals_like_every_other_rate():
    """Same rule as the headline counts: a declined answer has nothing to cite.
    Asserted on parsed fields rather than column positions, so reformatting the
    table cannot silently turn this into a test of whitespace."""
    rows = [_row(id="g001", provenance="stackoverflow", refused=True, uncited=True),
            _row(id="g002", provenance="stackoverflow", uncited=False),
            _row(id="g003", provenance="breakages", uncited=True)]
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        judge.report(rows, judge.aggregate(rows))
    line = next(l for l in out.getvalue().splitlines() if "stackoverflow" in l)
    answered, uncited, rate = line.split()[1:]
    assert (answered, uncited, rate) == ("1", "0", "0%"), (
        "the refused stackoverflow item must not appear in either column")


def test_a_single_provenance_prints_no_split():
    """One row of one group is not a comparison; printing it as a table implies
    a contrast that is not there."""
    rows = [_row(id="g001", provenance="breakages")]
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        judge.report(rows, judge.aggregate(rows))
    assert "by provenance" not in out.getvalue()


# --- groundedness: the deterministic half of faithfulness ---------------------
#
# The one Phase 4 defect prompt work could not move: fabrications sat at 2 under
# every wording tried (D74). g065 answered with `op.create_view`, which appears
# in no retrieved source and does not exist on alembic 1.19.1.

def test_a_call_absent_from_every_source_is_ungrounded():
    a = "See [1]:\n\n```python\nop.create_view('v', 'SELECT 1')\n```\n"
    assert judge.ungrounded_calls(a, ["nothing relevant here"]) == ["op.create_view"]


def test_a_call_present_in_a_source_is_grounded():
    a = "See [1]:\n\n```python\nsession.get(User, 1)\n```\n"
    assert judge.ungrounded_calls(a, ["use Session.get() to load by primary key"]) == []


def test_grounding_tolerates_the_docs_writing_the_class_where_the_answer_writes_the_instance():
    """Docs say `Session.get`; answers say `session.get`. Reporting that as a
    fabrication would measure capitalisation, not faithfulness."""
    a = "```python\nsession.execute(stmt)\n```"
    assert judge.ungrounded_calls(a, ["Session.execute() returns a Result"]) == []


def test_identifiers_from_the_question_are_not_fabrications():
    """A developer pasting their own broken code puts identifiers in the prompt
    that the docs will never contain. Flagging the model for echoing them back
    measures the questioner, not the answer."""
    a = "```python\nmy_helper.run_it()\n```"
    assert judge.ungrounded_calls(a, ["docs"], question="my_helper.run_it() fails") == []


def test_local_variables_are_not_api_calls():
    """subq, stmt, ua are the model's own names. Grounding them is meaningless,
    and counting them would bury the real signal in noise."""
    a = "```python\nsubq = select(User).subquery()\nstmt = subq\n```"
    assert "subq" not in judge.api_calls(a)
    assert "stmt" not in judge.api_calls(a)


def test_prose_mentions_are_not_counted_only_code():
    """Prose naming Query.from_self is usually discussing what the question
    asked about; code CALLING it is a claim about how to do the thing."""
    assert judge.api_calls("The Query.from_self() method was removed.") == []


def test_groundedness_is_not_a_claim_about_existence():
    """op.create_table is real and still ungrounded if no source mentions it —
    which is correct for a RAG metric: the answer is unsupported by the pages
    the system was given. Existence is audit_golden_fullbar's job, against the
    real library. Neither subsumes the other, and g065 fails both."""
    a = "```python\nop.create_table('t')\n```"
    assert judge.ungrounded_calls(a, ["unrelated source text"]) == ["op.create_table"]
