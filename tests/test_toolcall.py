"""Phase 5 Step 0 — the tool-call probe.

Every test runs with no server: `ask()` takes its transport as an argument for
the same reason `faithful.generate` does. A suite that needed Ollama would be
skipped in CI and would therefore pin nothing.
"""

import json

from rag import toolcall


def reply(tool=None, args=None, content=""):
    message = {"content": content}
    if tool is not None:
        message["tool_calls"] = [{"function": {"name": tool, "arguments": args}}]
    return {"message": message}


def test_a_call_on_the_tool_calls_channel_is_named_as_such():
    got = toolcall.classify(reply("check_api", {"symbol": "Query.from_self"}))
    assert got == {"outcome": "tool_calls", "tool": "check_api",
                   "arg": "Query.from_self"}


def test_stringified_arguments_are_parsed():
    """Some servers hand back `arguments` as a JSON string rather than an
    object. Counting that as malformed would blame the model for the
    transport."""
    got = toolcall.classify(
        reply("search_docs", json.dumps({"query": "from_self"})))
    assert got["outcome"] == "tool_calls" and got["arg"] == "from_self"


def test_prose_is_its_own_outcome_not_a_kind_of_invalid():
    """A model that answers in words understood the question and ignored the
    protocol; one that emits a broken call did not. The fixes differ -- a
    prompt versus a dead end -- so the counts must differ."""
    assert toolcall.classify(reply(content="You should use select()."))["outcome"] \
        == "prose"


def test_an_empty_reply_is_not_prose():
    assert toolcall.classify(reply())["outcome"] == "empty"


def test_a_tool_we_never_offered_is_not_valid():
    """The model inventing `search()` is a different defect from it filling our
    schema badly, and it must not be counted as a working call."""
    assert toolcall.classify(reply("search", {"query": "x"}))["outcome"] \
        == "unknown_tool"


def test_a_missing_or_blank_required_argument_is_not_valid():
    assert toolcall.classify(reply("check_api", {}))["outcome"] == "missing_arg"
    assert toolcall.classify(
        reply("check_api", {"symbol": "   "}))["outcome"] == "missing_arg"


def test_unparseable_arguments_are_reported_as_such():
    assert toolcall.classify(reply("search_docs", "{not json"))["outcome"] \
        == "unparseable_args"


def test_the_probe_set_is_labelled_by_construction():
    """The label has to be checkable from the question alone, or the `right
    tool` number is graded against labels this file invented. Human verification governs the
    golden set; this is an instrument, so the defence is that every check_api
    question names a symbol and asks whether it still exists."""
    for want, question in toolcall.PROBE:
        assert want in toolcall.REQUIRED_ARG
        if want == "check_api":
            assert any(w in question.lower() for w in
                       ("still", "removed", "renamed", "exist", "available")), question


def test_both_tools_are_offered_with_their_required_argument():
    names = {t["function"]["name"] for t in toolcall.TOOLS}
    assert names == set(toolcall.REQUIRED_ARG)
    for tool in toolcall.TOOLS:
        fn = tool["function"]
        assert fn["parameters"]["required"] == [toolcall.REQUIRED_ARG[fn["name"]]]


def test_ask_sends_the_tools_and_a_zero_temperature():
    sent = {}

    def transport(body, timeout=120):
        sent.update(body)
        return reply("search_docs", {"query": "x"})

    toolcall.ask("how do I migrate from_self?", transport=transport)
    assert sent["tools"] == toolcall.TOOLS
    assert sent["options"]["temperature"] == 0.0
    assert sent["stream"] is False


def test_a_call_in_the_content_field_is_counted_but_on_its_own_channel():
    """MEASURED 2026-09-11 and it is the whole Step 0 result: Ollama 0.34.0
    reports `capabilities: ['tools']` for qwen2.5-coder:7b and returns its
    calls as JSON text in `message.content`, never in `message.tool_calls`.

    Reading only `tool_calls` scored the first run **0 valid of 20** when every
    reply was a correct call. The channels stay separate rather than merging
    into one `valid`, because `tool_calls` is the protocol MCP speaks and this
    is text an agent has to parse itself."""
    got = toolcall.classify(reply(content=json.dumps(
        {"name": "check_api", "arguments": {"symbol": "Query.from_self"}})))
    assert got == {"outcome": "content_json", "tool": "check_api",
                   "arg": "Query.from_self"}


def test_json_in_content_that_is_not_one_of_our_tools_is_not_a_call():
    got = toolcall.classify(reply(content=json.dumps(
        {"name": "search", "arguments": {"query": "x"}})))
    assert got["outcome"] == "unknown_tool"


def test_prose_that_merely_contains_a_brace_is_still_prose():
    """The content channel must not turn a chatty answer into a call."""
    assert toolcall.classify(
        reply(content="Use select(). The {} syntax changed."))["outcome"] == "prose"


def test_a_json_list_in_content_is_not_a_call():
    assert toolcall.classify(reply(content="[1, 2, 3]"))["outcome"] == "prose"


def test_the_counts_are_computed_from_the_rows():
    """The arithmetic, pinned with a fake transport so it needs no server."""
    canned = {
        "Does A still exist?": reply("check_api", {"symbol": "A"}),
        "How do I do B?": reply(content=json.dumps(
            {"name": "search_docs", "arguments": {"query": "B"}})),
        "Why C?": reply(content="Because."),
    }
    got = toolcall.run([("check_api", "Does A still exist?"),
                        ("search_docs", "How do I do B?"),
                        ("search_docs", "Why C?")],
                       ask_one=lambda q: canned[q])
    assert (got["n"], got["usable"], got["native"], got["content"]) == (3, 2, 1, 1)
    assert (got["right"], got["labelled"]) == (2, 2)


def test_an_unreachable_call_costs_one_question_not_the_run():
    """The third module to need this. The first two learned it the expensive
    way -- a sweep that died at generation 150, and one that died at item 63
    of 64."""
    def boom(question):
        raise TimeoutError("timed out")

    got = toolcall.run([(None, "q1"), (None, "q2")], ask_one=boom)
    assert got["n"] == 2 and got["usable"] == 0
    assert all(r["outcome"].startswith("failed:") for r in got["rows"])


def test_unlabelled_questions_do_not_contribute_a_right_tool_rate():
    """The golden questions carry no tool label and must not be graded against
    one this file invented."""
    got = toolcall.run([(None, "anything")],
                       ask_one=lambda q: reply("search_docs", {"query": "x"}))
    assert got["labelled"] == 0 and got["right"] == 0


def test_a_call_followed_by_prose_is_still_a_call():
    """MEASURED 2026-09-11 inside the agent loop, not in the Step 0 probe.

    Single-turn probing got 120 replies that were pure JSON. In the loop the
    same model emits the call and then starts answering in the same field. The
    first classifier ran `json.loads` on the whole string, scored it `prose`,
    and **the loop never ran the tool the model had just asked for.**"""
    content = (json.dumps({"name": "search_docs",
                           "arguments": {"query": "from_self"}})
               + "\n\n[1] SQLAlchemy 2.0 Migration Guide says...")
    got = toolcall.classify(reply(content=content))
    assert got == {"outcome": "content_json", "tool": "search_docs",
                   "arg": "from_self"}


def test_prose_that_merely_starts_with_a_brace_is_still_prose():
    """raw_decode must not turn an answer into a call."""
    assert toolcall.classify(
        reply(content='{"a": 1} is the syntax'))["outcome"] == "prose"
