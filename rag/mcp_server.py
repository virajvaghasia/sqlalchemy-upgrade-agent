"""The tools in `rag/tools.py`, served over the Model Context Protocol.

    sqla-upgrade mcp                     # after `uv sync --extra mcp --extra embed`
    uv run python -m rag.mcp_server      # the same thing

An MCP client (an editor, a coding assistant, any agent framework that speaks
the protocol) starts this as a subprocess and talks to it over stdin/stdout.
A client configuration looks like:

    {"mcpServers": {"sqlalchemy-upgrade": {
        "command": "uv",
        "args": ["run", "--directory", "/path/to/this/repo", "sqla-upgrade", "mcp"]}}}

WHAT IT EXPOSES

    search_docs          the SQLAlchemy 1.4 and 2.0 documentation, through the
                         same retrieval path the golden set grades
    check_api            does this symbol exist in real SQLAlchemy 2.0.51, and
                         what is its signature
    get_function_source  the source of a callable in that pinned release

WHY THIS FILE IS THIN

It holds no logic. Each tool is a call into `rag/tools.py`, which is what the
agent loop (`rag/agent.py`) calls too. (The local 7B agent is offered the first
two only; an MCP client is usually a stronger model and gets all three.) A second implementation behind the
protocol would drift from the one that was measured, and the numbers in this
repo would stop describing what an MCP client actually gets.

The docstring of each function below is sent to the client as the tool's
description, so it is written for the model that will decide whether to call it.

Dense search runs in memory here (`RAG_DENSE=memory`) unless the environment
says otherwise: a tool server started by an editor has no Qdrant beside it. The
in-memory path returns the same top five as Qdrant on all 100 golden questions.
"""

from __future__ import annotations

import os

from mcp.server.mcpserver import MCPServer

from rag import tools
from rag.index import DENSE_ENV

server = MCPServer(
    "sqlalchemy-upgrade",
    instructions=(
        "Tools for upgrading Python code from SQLAlchemy 1.4 to 2.0. Use search_docs to find "
        "what the documentation says, and check_api before recommending a call, to confirm it "
        "exists in SQLAlchemy 2.0."
    ),
)


@server.tool()
def search_docs(query: str, k: int = 5) -> list[dict]:
    """Search the SQLAlchemy 1.4 and 2.0 documentation (migration guide, ORM, Core,
    tutorial, FAQ, error reference). Returns up to `k` passages, best first, each
    with a chunk id, its source and its full text. Use it for "what replaced X",
    "why does Y warn", or an error message pasted from a traceback."""
    return tools.search_docs(query, k=max(1, min(k, 20)))


@server.tool()
def check_api(symbol: str, package: str = "sqlalchemy") -> dict:
    """Check whether a dotted name exists in SQLAlchemy 2.0.51 (or in alembic, with
    package="alembic"), by importing the real library. Returns `exists` and, when
    it does, the signature. `exists: false` is an answer, not an error: it means
    the API was removed or never existed. Example symbol:
    "sqlalchemy.orm.Query.from_self"."""
    return tools.check_api(symbol, package=package)


@server.tool()
def get_function_source(symbol: str, package: str = "sqlalchemy") -> dict:
    """Return the source code of a callable in SQLAlchemy 2.0.51 (or alembic), read
    from the installed library rather than from the documentation. Use it when the
    docs describe a behaviour and the exact implementation matters."""
    return tools.get_function_source(symbol, package=package)


def main() -> None:
    os.environ.setdefault(DENSE_ENV, "memory")
    server.run("stdio")


if __name__ == "__main__":
    main()
