"""The custom demo page: a hand-designed front end over the tested `rag.demo` logic.

    DEMO_GENERATOR=ollama RAG_DENSE=memory PYTHONPATH=. uv run --with fastapi --with uvicorn python space/web.py
    # then open http://127.0.0.1:7860

Replaces the Gradio page's look, not its behaviour. Search, prompt, refusal
check, citation linking, source escaping-by-rendering and the generator notice
all come from `rag/demo.py` (covered by tests/test_demo.py); this file only
serves one HTML page and one JSON endpoint.
"""

import os
import pathlib
import time
import uuid

os.environ.setdefault("RAG_DENSE", "memory")   # must be set before rag.index is used

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402
from starlette.concurrency import run_in_threadpool  # noqa: E402

from rag import demo  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
BACKEND = os.environ.get("DEMO_GENERATOR", "nvidia")
# Limits exist because a hosted page spends API credits; a local Ollama run spends nothing.
LIMITER = demo.RateLimiter(per_hour=10**9, gap=0) if BACKEND == "ollama" else demo.RateLimiter()
# Langfuse tracing when its keys are set (the Modal `langfuse` secret); None otherwise.
TRACER = demo.langfuse_client()

# Same measured choice as space/app.py: four the measured model answered with a
# citation on the Mac, one it declines with the page in hand (D72), labelled.
EXAMPLES = [
    {"label": "query.get() moved", "q": "query(User).get(1) warns LegacyAPIWarning, where did get move to"},
    {"label": "backref deprecated?", "q": "backref= in relationship is deprecated what should I use instead"},
    {"label": "autocommit=True gone", "q": "Session(autocommit=True) is gone, what replaces autocommit mode"},
    {"label": "insert(values=) broke", "q": "insert().values() keyword constructor style for update/delete broke"},
    {"label": "engine.execute gone", "q": "engine.execute select gone AttributeError use connection instead",
     "declines": True},
]

app = FastAPI(title="sqlalchemy-upgrade-agent demo", docs_url=None, redoc_url=None)


def _key():
    if os.environ.get(demo.KEY_VAR):
        return os.environ[demo.KEY_VAR]
    try:
        from rag import faithful
        return faithful.env_key(demo.KEY_VAR)
    except Exception:
        return None


@app.get("/")
def index():
    return FileResponse(HERE / "static" / "index.html")


@app.get("/api/config")
def config():
    return {"examples": EXAMPLES, "generator": "qwen2.5-coder:7b" if BACKEND == "ollama" else demo.MODEL,
            "max_chars": demo.MAX_QUESTION_CHARS, "traced": TRACER is not None}


@app.post("/api/ask")
async def ask(request: Request):
    body = await request.json()
    session = str(body.get("session") or uuid.uuid4().hex)[:64]
    started = time.perf_counter()
    # The model call blocks for up to a minute; run it off the event loop.
    result = await run_in_threadpool(demo.answer, str(body.get("question", "")), key=_key(),
                                     session=session, limiter=LIMITER, backend=BACKEND,
                                     tracer=TRACER)
    return JSONResponse(demo.payload(result, BACKEND, time.perf_counter() - started))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "7860")))
