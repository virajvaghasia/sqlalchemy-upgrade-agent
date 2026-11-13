"""The MCP server and the command that starts it. No model, no index, no subprocess.

The server holds no logic of its own, so what is worth pinning is narrow: the
three tools are the ones the agent uses, a call through the protocol reaches
`rag/tools.py` with the arguments the client sent, and each tool carries a
description (a tool with no description is one a model cannot choose).
"""

import asyncio
import json

import pytest

from rag import cli, mcp_server, toolcall, tools


def call(name, arguments):
    result = asyncio.run(mcp_server.server.call_tool(name, arguments))
    assert result.is_error is False, result
    return result


def text_of(result):
    return "".join(c.text for c in result.content)


def test_the_server_offers_every_tool_the_local_agent_is_offered_and_one_more():
    offered = {t.name for t in asyncio.run(mcp_server.server.list_tools())}
    assert offered == {"search_docs", "check_api", "get_function_source"}
    # The local agent's schema is the reference: a tool added there and forgotten
    # here would make "what the agent can do" and "what an MCP client can do"
    # disagree. `get_function_source` is the extra one: the 7B model is offered
    # two tools on purpose, and an MCP client is usually a stronger model.
    agents = {t["function"]["name"] for t in toolcall.TOOLS}
    assert agents == {"search_docs", "check_api"} and agents < offered


def test_every_tool_tells_the_model_what_it_is_for():
    for tool in asyncio.run(mcp_server.server.list_tools()):
        assert tool.description and len(tool.description) > 60, tool.name


def test_check_api_reaches_the_real_tool_with_the_clients_arguments(monkeypatch):
    seen = []

    def fake(symbol, package="sqlalchemy"):
        seen.append((symbol, package))
        return {"exists": False, "symbol": symbol}

    monkeypatch.setattr(tools, "check_api", fake)
    result = call("check_api", {"symbol": "sqlalchemy.orm.Query.from_self"})
    assert seen == [("sqlalchemy.orm.Query.from_self", "sqlalchemy")]
    # "It does not exist" is a normal result for the client, not a protocol error.
    assert json.loads(text_of(result))["exists"] is False


def test_search_docs_returns_passages_and_caps_how_many_a_client_can_ask_for(monkeypatch):
    asked = []

    def fake(query, k=5):
        asked.append(k)
        return [{"chunk_id": "c00001", "source": "changelog/migration_20.rst", "text": "Session.get"}]

    monkeypatch.setattr(tools, "search_docs", fake)
    result = call("search_docs", {"query": "where did Query.get go", "k": 500})
    assert asked == [20]
    assert "c00001" in text_of(result)


def test_get_function_source_passes_the_package_through(monkeypatch):
    seen = []
    monkeypatch.setattr(
        tools, "get_function_source", lambda symbol, package="sqlalchemy": seen.append(package) or {"exists": True}
    )
    call("get_function_source", {"symbol": "alembic.operations.Operations.create_table", "package": "alembic"})
    assert seen == ["alembic"]


# --- the command ---------------------------------------------------------------


def test_the_command_has_the_three_subcommands_and_requires_one():
    parser = cli.build_parser()
    assert parser.parse_args(["ask", "a question"]).question == "a question"
    assert parser.parse_args(["serve", "--port", "8000"]).port == 8000
    assert parser.parse_args(["mcp"]).command == "mcp"
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_ask_hands_the_question_and_flags_to_the_pipeline(monkeypatch):
    from rag import ask

    seen = {}
    monkeypatch.setattr(ask, "ask", lambda question, **kw: seen.update(question=question, **kw))
    cli.main(["ask", "why did engine.execute go", "--k", "8", "--retrieval-only"])
    assert seen == {
        "question": "why did engine.execute go",
        "k": 8,
        "version": None,
        "retrieval_only": True,
        "show_prompt": False,
    }


def test_the_default_k_is_the_shipped_one_not_a_second_copy():
    from rag import ask

    assert cli.build_parser().parse_args(["ask", "q"]).k == ask.DEFAULT_K
