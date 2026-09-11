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
