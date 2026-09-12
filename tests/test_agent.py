"""Phase 5 Step 2 — the loop and its four failure paths.

Every test runs with no model and no tools: `run()` takes `generate` and
`call_tool` as arguments. A suite that needed Ollama would be skipped in CI and
would therefore pin nothing -- and the failure paths are the part most worth
pinning, because they are the part a demo never exercises.
"""

import json

from rag import agent, ask


def tool_reply(name, arg, channel="content"):
    """A tool call on either channel. The loop must not care which (D87).

    The argument key is the one the schema declares -- `symbol` for check_api,
    `query` for search_docs. Writing `{"x": arg}` here made every call classify
    as `missing_arg`, which is the classifier working correctly on a broken
    fixture."""
    from rag import toolcall
    blob = {"name": name, "arguments": {toolcall.REQUIRED_ARG[name]: arg}}
    if channel == "native":
        return {"message": {"content": "",
                            "tool_calls": [{"function": blob}]}}
    return {"message": {"content": json.dumps(blob)}}


def prose(text):
    return {"message": {"content": text}}


def scripted(*replies):
    it = iter(replies)
    return lambda messages: next(it)


# --- the happy path ----------------------------------------------------------

def test_a_two_tool_task_completes():
    """The roadmap's own bar for this phase: 2+ tool calls, then an answer."""
    got = agent.run(
        "how do I replace from_self?",
        generate=scripted(tool_reply("check_api", "Query.from_self"),
                          tool_reply("search_docs", "from_self 2.0"),
                          prose("Use a subquery [1].")),
        call_tool=lambda n, a: (
            ({"exists": False}, None) if n == "check_api"
            else ([{"chunk_id": "c01567", "text": "body"}], None)))
    assert got["stopped"] == "answered" and got["steps"] == 3
    assert got["answer"] == "Use a subquery [1]."
    assert [t["kind"] for t in got["trace"]] == ["tool", "tool", "answer"]


def test_the_loop_does_not_care_which_channel_the_call_arrived_on():
    """D87 measured qwen returning calls in `content` and gemma on
    `tool_calls`, and Round 17 may show that is an Ollama version fact. The
    loop reads `classify`, never either field, so it is correct either way --
    it was built while that measurement was still open."""
    for channel in ("content", "native"):
        got = agent.run("q", generate=scripted(
            tool_reply("check_api", "Session.get", channel=channel),
            prose("It exists [1].")),
            call_tool=lambda n, a: ({"exists": True}, None))
        assert got["stopped"] == "answered", channel
        assert got["trace"][0]["kind"] == "tool", channel


# --- failure path 1: the tool raised -----------------------------------------

def test_a_tool_failure_is_shown_to_the_model_rather_than_raised():
    """D75, fifth module. The retry is the next turn WITH THE ERROR VISIBLE,
    not a silent re-call: a model that cannot see the error cannot route
    around it."""
    seen = {}

    def generate(messages):
        seen["last"] = messages[-1]["content"]
        return prose("I cannot verify that.") if len(messages) > 2 \
            else tool_reply("check_api", "Nope.nope")

    got = agent.run("q", generate=generate,
                    call_tool=lambda n, a: (None, "timed out after 120s"))
    assert "timed out" in seen["last"]
    assert got["trace"][0]["kind"] == "tool_error"
    assert got["stopped"] == "answered"


def test_an_exception_inside_a_tool_becomes_the_error_path(monkeypatch):
    """Letting it propagate is the bug that killed a sweep at item 63 of 64.

    Monkeypatched rather than called for real: the first version of this test
    ran the live `search_docs`, which loads a 2.2GB embedder and needs Qdrant,
    and took 24 seconds inside a suite whose docstring promises no network."""
    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(agent.tools, "search_docs", boom)
    result, error = agent._default_tools("search_docs", "x")
    assert result is None and error == "RuntimeError: boom"


def test_an_unknown_tool_is_an_error_not_a_crash():
    result, error = agent._default_tools("no_such_tool", "x")
    assert result is None and "unknown tool" in error


# --- failure path 2: nothing came back ---------------------------------------

def test_an_empty_search_says_so_in_words_the_model_can_act_on():
    """An empty list may read as a formatting problem. `D70`'s 17 absents are
    the measured case where no reformulation helps, so the model has to be told
    plainly that nothing matched."""
    assert "no passages matched" in agent._observation("search_docs", [])


def test_a_missing_symbol_is_presented_as_an_answer_not_an_error():
    """D88's distinction, carried into what the model actually reads. `Query
    .from_self` not existing is THE most common true statement in this problem
    domain, and it must not look like a broken lookup."""
    text = agent._observation("check_api", {"exists": False})
    assert "NOT FOUND" in text and "definite answer, not an error" in text
    assert "failed" not in text


def test_a_real_tool_error_is_presented_as_a_failure():
    text = agent._observation("check_api", {"exists": False, "error": "timed out"})
    assert "failed" in text


# --- failure path 3: the loop repeating itself -------------------------------

def test_the_same_call_twice_ends_the_run():
    """Repeating a call cannot produce new information; it is the cheapest way
    for a loop to burn its budget looking busy."""
    got = agent.run("q", generate=scripted(
        tool_reply("check_api", "Session.get"),
        tool_reply("check_api", "Session.get")),
        call_tool=lambda n, a: ({"exists": True}, None))
    assert got["stopped"] == "repeated_call"
    assert ask.refused(got["answer"])


# --- failure path 4: the budget ----------------------------------------------

def test_an_exhausted_budget_declines_rather_than_guessing():
    """An agent that silently returns its best half-formed guess after four
    tool calls is indistinguishable downstream from one that knew the answer."""
    got = agent.run("q", generate=lambda m: tool_reply("search_docs", f"try {len(m)}"),
                    call_tool=lambda n, a: ([{"chunk_id": "c", "text": "t"}], None),
                    max_steps=3)
    assert got["stopped"] == "budget" and got["steps"] == 3
    assert ask.refused(got["answer"])


# --- the decline has to be the one Phase 4 can see ---------------------------

def test_the_agents_decline_is_the_string_phase_4_detects():
    """If the agent invents its own way of saying no, `--refusals`,
    `rag.judge` and `rag.faithful` all stop seeing declines and start scoring
    them as answers. Every Phase 4 instrument is a prefix test against
    `ask.REFUSAL_OPENING` (D76)."""
    assert agent.DECLINE.startswith(ask.REFUSAL_OPENING)
    assert ask.refused(agent.DECLINE)


def test_an_empty_model_reply_declines_rather_than_returning_nothing():
    got = agent.run("q", generate=scripted(prose("")),
                    call_tool=lambda n, a: (None, None))
    assert ask.refused(got["answer"])


def test_the_trace_records_every_step():
    """A trace nobody can read is how an agent's failures become
    unattributable -- the thing building tools first was meant to avoid."""
    got = agent.run("q", generate=scripted(
        tool_reply("search_docs", "a"), prose("done [1].")),
        call_tool=lambda n, a: ([{"chunk_id": "c", "text": "t"}], None))
    assert got["trace"][0]["tool"] == "search_docs"
    assert got["trace"][0]["arg"] == "a"
    assert "observation" in got["trace"][0]


# --- Step 3: the golden sweep ------------------------------------------------

ITEMS = [
    {"id": "g001", "question": "q one", "answerable": True,
     "answer_chunks": ["c001"], "provenance": "breakages"},
    {"id": "g002", "question": "q two", "answerable": False,
     "answer_chunks": [], "provenance": "github"},
]
# `heading_path` is required: `dedup_key` uses it, because the embedder
# prepends the heading before embedding and two chunks are the same vector
# only if both heading and text match (D58).
CHUNKS = {"c001": {"chunk_id": "c001", "text": "t",
                   "heading_path": ["Migration"]}}


def test_answer_in_prompt_uses_the_same_function_as_every_other_sweep():
    """`score.rank_of_first_hit`, not a private rule. `D85` is what happens
    when one metric grows two implementations: this column has to line up with
    `D72`'s table, not merely resemble it."""
    def run_one(question, call_tool=None):
        call_tool("search_docs", "x")             # the agent looked something up
        return {"answer": "an answer [1]", "steps": 2, "stopped": "answered",
                "trace": [{"kind": "tool", "tool": "search_docs"}]}

    import rag.agent as mod
    real = mod._default_tools
    mod._default_tools = lambda n, a: ([{"chunk_id": "c001", "text": "t"}], None)
    try:
        rows = agent.sweep(ITEMS, chunks=CHUNKS, run_one=run_one,
                           log=lambda *a: None)
    finally:
        mod._default_tools = real
    by_id = {r["id"]: r for r in rows}
    assert by_id["g001"]["answer_in_prompt"] is True
    # An unanswerable item can never have its answer in the prompt.
    assert by_id["g002"]["answer_in_prompt"] is False


def test_an_agent_that_never_searched_has_no_sources():
    """Zero is a measurement, not a gap: an answer with no lookup behind it is
    the thing `D73` was about, arriving by a different route."""
    def run_one(question, call_tool=None):
        return {"answer": "from memory", "steps": 1, "stopped": "answered",
                "trace": []}

    rows = agent.sweep(ITEMS, chunks=CHUNKS, run_one=run_one, log=lambda *a: None)
    assert all(r["n_sources"] == 0 for r in rows)
    assert all(r["answer_in_prompt"] is False for r in rows)


def test_one_broken_item_costs_one_item():
    """D75, and by now the rule rather than the exception."""
    def boom(question, call_tool=None):
        raise RuntimeError("boom")

    rows = agent.sweep(ITEMS, chunks=CHUNKS, run_one=boom, log=lambda *a: None)
    assert len(rows) == 2 and all(r["failed"] for r in rows)
    assert all("answer" not in r for r in rows)


def test_a_failed_row_is_neither_delivered_nor_a_fabrication():
    got = agent.summarise([
        {"id": "a", "answerable": True, "failed": True, "answer_in_prompt": False},
        {"id": "b", "answerable": True, "answer_in_prompt": True,
         "answer": "real [1]", "tools": ["search_docs"], "stopped": "answered"},
    ])
    assert got["delivered"] == 1 and got["failed"] == 1
    assert got["n_answerable"] == 2, "the failed item stays in the denominator (D61)"


def test_the_generation_columns_come_from_judge_not_a_second_copy():
    """`summarise` delegates to `judge._sweep_generation`. A private copy here
    is exactly the divergence `D85` had to unpick."""
    from rag import judge
    rows = [{"id": "a", "answerable": True, "answer_in_prompt": True,
             "answer": "x [1]", "tools": [], "stopped": "answered"}]
    assert agent.summarise(rows)["end_to_end"] == \
        judge._sweep_generation(rows)["end_to_end"]


def test_the_tool_use_counts_separate_none_one_and_several():
    """The phase's actual risk is the model stopping after one tool, so that
    has to be a column rather than something read out of traces later."""
    rows = [
        {"id": "a", "answerable": True, "answer_in_prompt": True, "answer": "x",
         "tools": [], "stopped": "answered"},
        {"id": "b", "answerable": True, "answer_in_prompt": True, "answer": "x",
         "tools": ["check_api"], "stopped": "answered"},
        {"id": "c", "answerable": True, "answer_in_prompt": True, "answer": "x",
         "tools": ["check_api", "search_docs"], "stopped": "answered"},
    ]
    got = agent.summarise(rows)
    assert (got["no_tool_call"], got["one_tool_only"], got["multi_tool"]) == (1, 1, 1)


def test_resume_skips_only_what_is_already_done():
    def run_one(question, call_tool=None):
        return {"answer": "a [1]", "steps": 1, "stopped": "answered", "trace": []}

    prior = {"rows": [{"id": "g001", "answerable": True, "answer": "old",
                       "answer_in_prompt": True, "n_sources": 1, "tools": [],
                       "stopped": "answered"}]}
    rows = agent.sweep(ITEMS, chunks=CHUNKS, run_one=run_one, resume=prior,
                       log=lambda *a: None)
    by_id = {r["id"]: r for r in rows}
    assert by_id["g001"]["answer"] == "old", "a done row is not re-run"
    assert by_id["g002"]["answer"] == "a [1]"


def test_the_system_prompt_is_overridable_and_defaults_to_the_shipped_one():
    """E1 needs to swap the system message without touching the loop.

    The default is `SYSTEM_MUSTCALL` since `D90` — Round 18 measured it fixing
    9 out-of-range citations and breaking 0 on the lab, 3 and 0 on the Mac.
    `SYSTEM` is kept as the measured control rather than deleted, because the
    comparison is only readable while both exist."""
    seen = {}

    def generate(messages):
        seen["system"] = messages[0]["content"]
        return prose("done")

    agent.run("q", generate=generate, call_tool=lambda n, a: (None, None))
    assert seen["system"] == agent.DEFAULT_SYSTEM

    agent.run("q", generate=generate, call_tool=lambda n, a: (None, None),
              system=agent.SYSTEM_MUSTCALL)
    assert seen["system"] == agent.SYSTEM_MUSTCALL


def test_the_candidate_changes_only_the_two_things_it_claims_to():
    """A variant that quietly changed the citation clause too would make any
    difference unattributable -- `D74` measured `I` being worse than `H`
    precisely because it carried a second instruction."""
    assert "MUST call a tool" in agent.SYSTEM_MUSTCALL
    assert "do not answer from memory" in agent.SYSTEM_MUSTCALL.lower()
    assert "You may call tools" not in agent.SYSTEM_MUSTCALL
    # unchanged in both
    for prompt in (agent.SYSTEM, agent.SYSTEM_MUSTCALL):
        assert "cite sources as [1], [2]" in prompt
        assert agent.DECLINE in prompt


def test_e1_interleaves_the_arms_per_item():
    """One sitting is not enough on its own (`D54`); the arms are interleaved
    per item so a machine that drifts over an hour drifts through both arms
    equally. `D89` makes that sharper — whether a tool is called disagrees 50%
    across machines, so it is not a quantity to measure twice at different
    times."""
    order = []

    def run_one(question, call_tool=None, system=None):
        order.append("B" if system == agent.SYSTEM_MUSTCALL else "A")
        return {"answer": "x", "steps": 1, "stopped": "answered", "trace": []}

    agent.e1(ITEMS[:1] + [dict(ITEMS[0], id="g003")], chunks=CHUNKS,
             run_one=run_one, log=lambda *a: None)
    assert order == ["A", "B", "A", "B"], "arms must alternate within each item"


def test_e1_reports_both_arms_over_the_same_items():
    def run_one(question, call_tool=None, system=None):
        return {"answer": "x [1]", "steps": 1, "stopped": "answered", "trace": []}

    got = agent.e1(ITEMS[:1], chunks=CHUNKS, run_one=run_one, log=lambda *a: None)
    assert set(got) == set(agent.E1_ARMS)
    assert [r["id"] for r in got["A_shipped"]] == [r["id"] for r in got["B_mustcall"]]


def test_the_chaining_count_in_the_report_is_derived(capsys):
    """It was the literal words "ZERO under both prompts on both machines", and
    the lab's own run printed that sentence directly above a column containing
    a 1. A count typed once into a script, contradicted by the data beside it —
    the measurement rule applies to scripts, not only to docs."""
    rows = {"A_shipped": [{"id": "a", "tools": ["x", "y"], "answer": "z",
                           "answer_in_prompt": True, "out_of_range": False}],
            "B_mustcall": [{"id": "a", "tools": ["x"], "answer": "z",
                            "answer_in_prompt": True, "out_of_range": False}]}
    agent.e1_report(rows)
    out = capsys.readouterr().out
    assert "1 of 2 runs" in out
    assert "ZERO under both prompts" not in out


def test_the_measured_control_prompt_is_kept_not_deleted():
    """Round 18's comparison is only readable while both prompts exist. A
    candidate that replaces its control leaves a number nobody can re-derive —
    which is what happened to Round 14's citation cells (`D85`)."""
    assert agent.SYSTEM != agent.SYSTEM_MUSTCALL
    assert agent.DEFAULT_SYSTEM is agent.SYSTEM_MUSTCALL
    assert set(agent.E1_ARMS.values()) == {agent.SYSTEM, agent.SYSTEM_MUSTCALL}
