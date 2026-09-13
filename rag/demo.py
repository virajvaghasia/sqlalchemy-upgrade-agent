"""Phase 6, Step 4 — the public demo's logic: one question in, a cited answer out.

The Gradio page (`space/app.py`) is a thin wrapper around `answer()`. The logic
lives here, inside the tested package, so the demo is covered by the same suite
as everything it reuses.

WHAT THE DEMO RUNS, AND WHAT IT DOES NOT

- **Retrieval is exactly the graded path**: `index.retrieve` with hybrid BM25,
  twin collapse and the seat-5 reranker. The only change is where dense search
  runs: `RAG_DENSE=memory` instead of Qdrant, and that was gated against the
  golden baseline before it was allowed here (`D102`: broken 0, moved 0).
- **The prompt is the shipped one**: `ask.SYSTEM` and `ask.build_prompt`.
- **The generator is NOT the measured one.** The 0.42 end to end was measured
  with `qwen2.5-coder:7b`, which NVIDIA's API does not serve. The demo uses
  `nvidia/nemotron-3-ultra-550b-a55b`, the one model measured with this prompt
  (`D99`–`D101`), and the page says so.

RATE LIMITS ARE A CHOICE, NOT A MEASUREMENT

A public page spends Viraj's free NVIDIA credits. The two numbers below bound
that spend; they were picked, not derived, and changing them changes nothing
this repo has measured.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request

from rag import ask

MODEL = "nvidia/nemotron-3-ultra-550b-a55b"
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
KEY_VAR = "NVIDIA_API_KEY"

GLOBAL_PER_HOUR = 60        # chosen: every visitor together, per rolling hour
SESSION_MIN_SECONDS = 20    # chosen: one visitor cannot fire questions back to back
MAX_QUESTION_CHARS = 500    # the longest golden question is well under this

NOT_THE_MEASURED_MODEL = (
    "Answers here are written by `nvidia/nemotron-3-ultra-550b-a55b`. The project's measured "
    "end-to-end score (0.42 on the lab machine) is for `qwen2.5-coder:7b`, which this hosting "
    "cannot run, so that number does not describe these answers. Retrieval is the graded path."
)


class RateLimiter:
    """A rolling-hour global cap plus a minimum gap per session. `clock` is
    injectable so the tests need no sleeping."""

    def __init__(self, per_hour: int = GLOBAL_PER_HOUR, gap: float = SESSION_MIN_SECONDS,
                 clock=time.monotonic):
        self.per_hour, self.gap, self.clock = per_hour, gap, clock
        self.calls: list[float] = []
        self.last: dict[str, float] = {}
        self.lock = threading.Lock()

    def check(self, session: str) -> str | None:
        """None if allowed (and the call is recorded), else the reason it is not."""
        with self.lock:
            now = self.clock()
            self.calls = [t for t in self.calls if now - t < 3600]
            if len(self.calls) >= self.per_hour:
                return "The demo's hourly question limit is reached. Please try again later."
            last = self.last.get(session)
            if last is not None and now - last < self.gap:
                return f"Please wait {self.gap - (now - last):.0f} seconds before asking again."
            self.calls.append(now)
            self.last[session] = now
            return None


def nvidia_post(messages: list[dict], key: str, timeout: int = 180) -> dict:
    body = {"model": MODEL, "temperature": ask.TEMPERATURE, "max_tokens": 8192,
            "messages": messages}
    request = urllib.request.Request(
        NVIDIA_URL, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def answer(question: str, *, key: str | None, session: str, limiter: RateLimiter,
           retrieve=None, post=nvidia_post) -> dict:
    """Question in, {'answer', 'sources', 'refused', 'error'} out. Never raises
    for a visitor's input or a remote failure; the page shows `error` instead."""
    question = (question or "").strip()
    if not question:
        return {"error": "Ask a question about upgrading SQLAlchemy 1.4 code to 2.0."}
    if len(question) > MAX_QUESTION_CHARS:
        return {"error": f"Please keep the question under {MAX_QUESTION_CHARS} characters."}
    if not key:
        return {"error": f"The demo is not configured: the {KEY_VAR} secret is missing."}
    if retrieve is None:
        from rag import index
        retrieve = lambda q: index.retrieve(q, limit=ask.DEFAULT_K)

    hits = retrieve(question)
    sources = [{"n": n, "version": h.payload["sqlalchemy_version"],
                "path": h.payload["source_path"],
                "heading": " > ".join(h.payload["heading_path"]) or "(no heading)",
                "text": h.payload["text"]} for n, h in enumerate(hits, 1)]
    blocked = limiter.check(session)
    if blocked:
        return {"error": blocked, "sources": sources}
    messages = [{"role": "system", "content": ask.SYSTEM},
                {"role": "user", "content": ask.build_prompt(question, hits)}]
    try:
        data = post(messages, key)
    except (urllib.error.URLError, TimeoutError) as exc:
        return {"error": f"The answer model did not respond ({type(exc).__name__}). "
                         "The sources below were still found.", "sources": sources}
    text = (data["choices"][0]["message"].get("content") or "").strip()
    return {"answer": text, "sources": sources, "refused": ask.refused(text), "error": None}


def render(result: dict) -> str:
    """Markdown for the page: the answer, then every source it could cite."""
    parts = []
    if result.get("error"):
        parts.append(f"**{result['error']}**")
    if result.get("answer"):
        parts.append(result["answer"])
    if result.get("sources"):
        parts.append("---\n\n### Sources\n")
        for s in result["sources"]:
            parts.append(f"<details><summary>[{s['n']}] SQLAlchemy {s['version']} — "
                         f"{s['path']} — {s['heading']}</summary>\n\n```\n{s['text']}\n```\n\n</details>")
    parts.append(f"\n---\n\n<sub>{NOT_THE_MEASURED_MODEL}</sub>")
    return "\n\n".join(parts)
