"""Entry point for the deployed bundle. The server itself is `rag/server.py`.

    DEMO_GENERATOR=ollama PYTHONPATH=. uv run --extra serve python space/web.py
    # then open http://127.0.0.1:7860

Kept as a file of its own because the Modal host (`modal_app.py`) and the bundle
built by `build.py` both start the page as `web:app`. From a checkout,
`sqla-upgrade serve` does the same thing.
"""

from rag.server import app, main  # noqa: F401  (`app` is what the hosts import)

if __name__ == "__main__":
    main()
