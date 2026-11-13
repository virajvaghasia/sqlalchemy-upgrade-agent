"""The `sqla-upgrade` command: one entry point, three things to do with it.

    sqla-upgrade ask "why can't I call engine.execute any more?"
    sqla-upgrade serve        # the web page on http://127.0.0.1:7860
    sqla-upgrade mcp          # the tools over the Model Context Protocol, on stdio

Each subcommand hands off to the module that owns the behaviour. `serve` and
`mcp` import their libraries only when chosen, so `ask` works without the
`serve` or `mcp` extras installed, and a missing extra is reported as the
command to run rather than as a traceback.
"""

from __future__ import annotations

import argparse
import sys


def _need(extra: str, exc: ImportError) -> None:
    sys.exit(
        f"`sqla-upgrade {extra}` needs the `{extra}` extra ({exc.name} is not installed):\n"
        f"    uv sync --extra {extra} --extra embed"
    )


def _ask(args: argparse.Namespace) -> None:
    from rag import ask

    ask.ask(
        args.question, k=args.k, version=args.version, retrieval_only=args.retrieval_only, show_prompt=args.show_prompt
    )


def _serve(args: argparse.Namespace) -> None:
    import os

    try:
        import uvicorn

        from rag import server
    except ImportError as exc:
        _need("serve", exc)
    host = args.host or os.environ.get("HOST", "127.0.0.1")
    port = args.port or int(os.environ.get("PORT", "7860"))
    uvicorn.run(server.app, host=host, port=port)


def _mcp(_args: argparse.Namespace) -> None:
    try:
        from rag import mcp_server
    except ImportError as exc:
        _need("mcp", exc)
    mcp_server.main()


def build_parser() -> argparse.ArgumentParser:
    from rag import ask

    parser = argparse.ArgumentParser(
        prog="sqla-upgrade",
        description="Answers about upgrading SQLAlchemy 1.4 code to 2.0, written only from "
        "the SQLAlchemy documentation and cited.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    a = sub.add_parser("ask", help="ask one question at the terminal (needs Qdrant and Ollama)")
    a.add_argument("question")
    a.add_argument("--k", type=int, default=ask.DEFAULT_K, help="how many passages go in the prompt")
    a.add_argument("--version", help="only passages from this SQLAlchemy release, e.g. 2.0.51")
    a.add_argument("--retrieval-only", action="store_true", help="print the passages, skip the model")
    a.add_argument("--show-prompt", action="store_true", help="print what the model was sent")
    a.set_defaults(run=_ask)

    s = sub.add_parser("serve", help="serve the web page")
    s.add_argument("--host", help="default 127.0.0.1, or $HOST")
    s.add_argument("--port", type=int, help="default 7860, or $PORT")
    s.set_defaults(run=_serve)

    m = sub.add_parser("mcp", help="serve the tools over the Model Context Protocol (stdio)")
    m.set_defaults(run=_mcp)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.run(args)


if __name__ == "__main__":
    main()
