"""The web server: one page, one question endpoint, two health checks.

    sqla-upgrade serve                                   # after `uv sync --extra serve`
    DEMO_GENERATOR=ollama sqla-upgrade serve             # answer with the local model
    # then open http://127.0.0.1:7860

Everything that decides what an answer *is* lives in `rag/demo.py`: search,
prompt, refusal check, citation links, the rate limit. This file adds only what
a server owes its callers.

WHAT THE STATUS CODES MEAN

    200   answered, or declined. Declining is a correct result, not a failure.
    422   the question was empty, too long, or not a question about the docs
    429   rate limited; `Retry-After` says how many seconds to wait
    503   the answer model is unreachable, or no API key is configured

The JSON body has the same shape on every one of them, so the page can show the
sentence in `error` and the sources that were found, whatever the status. A
client that does not read bodies still gets a status it can act on.

WHAT IS LOGGED

One JSON line per question on the `sqla_upgrade.request` logger: a request id
(also returned in the `X-Request-ID` header and in the body), the status, the
outcome, the model that answered, and how long search and generation each
took. **The question text is not logged**, only its length: a visitor may paste
their own code into the box.

HEALTH

    /healthz   the process is up. Touches nothing, so it cannot be slow.
    /readyz    the corpus files are on disk and a generator is configured.
               Does not load the embedding model: readiness that takes a minute
               to answer is not a readiness check.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import pathlib
import sys
import time
import uuid

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from rag import demo, embed
from rag.index import DENSE_ENV

ROOT = pathlib.Path(__file__).resolve().parent.parent
# In a checkout the page is at space/static; in the deploy bundle (space/build.py)
# it sits beside the `rag` folder.
STATIC = next((d for d in (ROOT / "static", ROOT / "space" / "static") if d.is_dir()), ROOT / "space" / "static")

BACKEND = os.environ.get("DEMO_GENERATOR", "nvidia")
# Limits exist because a hosted page spends API credits; a local Ollama run spends nothing.
LIMITER = demo.RateLimiter(per_hour=10**9, gap=0) if BACKEND == "ollama" else demo.RateLimiter()
# Langfuse tracing when its keys are set; None otherwise.
TRACER = demo.langfuse_client()

# None means "what rag.demo does by default". Tests replace these with stand-ins,
# so the server is exercised with no model and no index.
RETRIEVE = None
POST = None

# What /readyz looks for. The same four files rag.index refuses to start without.
CORPUS_FILES = [embed.VECTORS_PATH, embed.IDS_PATH, embed.STATS_PATH, embed.CHUNKS_PATH]

STATUS_FOR = {
    "empty_question": 422,
    "question_too_long": 422,
    "not_a_lookup": 422,
    "rate_limited": 429,
    "not_configured": 503,
    "generator_unavailable": 503,
}

# A measured choice: four questions the measured model answered with a
# citation, one it declines with the page in hand, labelled.
EXAMPLES = [
    {"label": "query.get() moved", "q": "query(User).get(1) warns LegacyAPIWarning, where did get move to"},
    {"label": "backref deprecated?", "q": "backref= in relationship is deprecated what should I use instead"},
    {"label": "autocommit=True gone", "q": "Session(autocommit=True) is gone, what replaces autocommit mode"},
    {"label": "insert(values=) broke", "q": "insert().values() keyword constructor style for update/delete broke"},
    {
        "label": "engine.execute gone",
        "q": "engine.execute select gone AttributeError use connection instead",
        "declines": True,
    },
]

log = logging.getLogger("sqla_upgrade.request")
if not log.handlers:
    # uvicorn configures its own loggers and leaves the root one bare, so without a
    # handler here an INFO line would be dropped. The message is already JSON.
    _handler = logging.StreamHandler(sys.stderr)
    _handler.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(_handler)
    log.setLevel(logging.INFO)


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI):
    # The server searches in memory unless told otherwise: it has no Qdrant beside
    # it. Set when the server STARTS, not when this module is imported, so that
    # importing it (as the tests do) cannot switch another caller's search path.
    os.environ.setdefault(DENSE_ENV, "memory")
    yield


app = FastAPI(title="sqlalchemy-upgrade-agent", docs_url=None, redoc_url=None, lifespan=lifespan)


class AskRequest(BaseModel):
    """The one request body. Length limits are enforced in `demo.answer`, which
    owns the sentence the page shows; this only rejects a body of the wrong type."""

    question: str = ""
    session: str | None = None


def _key():
    if os.environ.get(demo.KEY_VAR):
        return os.environ[demo.KEY_VAR]
    try:
        from rag import faithful

        return faithful.env_key(demo.KEY_VAR)
    except Exception:
        return None


def _generator_configured() -> bool:
    return BACKEND == "ollama" or bool(_key())


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    checks = {"corpus": all(p.exists() for p in CORPUS_FILES), "generator": _generator_configured()}
    ready = all(checks.values())
    return JSONResponse(
        {"status": "ready" if ready else "not ready", "checks": checks}, status_code=200 if ready else 503
    )


@app.get("/api/config")
def config():
    return {
        "examples": EXAMPLES,
        "generator": "qwen2.5-coder:7b" if BACKEND == "ollama" else demo.MODEL,
        "max_chars": demo.MAX_QUESTION_CHARS,
        "traced": TRACER is not None,
    }


@app.post("/api/ask")
async def ask(body: AskRequest):
    request_id = uuid.uuid4().hex[:16]
    session = (body.session or uuid.uuid4().hex)[:64]
    started = time.perf_counter()
    stand_ins = {name: fn for name, fn in (("retrieve", RETRIEVE), ("post", POST)) if fn}
    # The model call blocks for up to a minute; run it off the event loop.
    result = await run_in_threadpool(
        demo.answer,
        body.question,
        key=_key(),
        session=session,
        limiter=LIMITER,
        backend=BACKEND,
        tracer=TRACER,
        **stand_ins,
    )
    seconds = time.perf_counter() - started
    payload = demo.payload(result, BACKEND, seconds)
    payload["request_id"] = request_id
    status = STATUS_FOR.get(result.get("code") or "", 200)
    headers = {"X-Request-ID": request_id}
    if result.get("retry_after"):
        headers["Retry-After"] = str(result["retry_after"])

    timings = result.get("timings") or {}
    log.info(
        json.dumps(
            {
                "event": "ask",
                "request_id": request_id,
                "status": status,
                "outcome": payload["status"],
                "code": result.get("code"),
                "model": payload["generator"],
                "sources": len(payload["sources"]),
                "question_chars": len(body.question),
                "retrieve_ms": timings.get("retrieve_ms"),
                "generate_ms": timings.get("generate_ms"),
                "total_ms": round(seconds * 1000),
            }
        )
    )
    return JSONResponse(payload, status_code=status, headers=headers)


def main() -> None:
    import uvicorn

    uvicorn.run(app, host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "7860")))


if __name__ == "__main__":
    main()
