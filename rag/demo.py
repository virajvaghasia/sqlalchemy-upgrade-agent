"""Phase 6, Step 4 — the public demo's logic: one question in, a cited answer out.

The Gradio page (`space/app.py`) is a thin wrapper around `answer()`. The logic
lives here, inside the tested package, so the demo is covered by the same suite
as everything it reuses.

WHAT THE DEMO RUNS, AND WHAT IT DOES NOT

- **Retrieval is exactly the graded path**: `index.retrieve` with hybrid BM25,
  twin collapse and the seat-5 reranker. The only change is where dense search
  runs: `RAG_DENSE=memory` instead of Qdrant, and that was gated against the
  golden baseline before it was allowed here (broken 0, moved 0).
- **The prompt is the shipped one**: `ask.SYSTEM` and `ask.build_prompt`.
- **The generator depends on where it runs, and the page says which.**
  `backend="ollama"` (a local run) uses `qwen2.5-coder:7b` through `ask.generate`,
  the generator the 0.42 was measured on. `backend="nvidia"` (a hosted page) uses
  `nvidia/nemotron-3-ultra-550b-a55b`, because NVIDIA's API serves no qwen; that
  model was measured on all 100 golden questions in Step 4d, and the page
  quotes those numbers, not the 0.42.

RATE LIMITS ARE A CHOICE, NOT A MEASUREMENT

A public page spends Viraj's free NVIDIA credits. The two numbers below bound
that spend; they were picked, not derived, and changing them changes nothing
this repo has measured.
"""

from __future__ import annotations

import contextlib
import html
import json
import math
import os
import re
import threading
import time
import urllib.error
import urllib.request

from rag import ask

# The page's generator. NOT the judge: `openai/gpt-oss-20b` grades Phase 6's
# answers, and a page that writes with its own grader is the self-scoring shape
# the local judge was chosen from a different family to avoid.
#
# Repointed 2026-09-16. The previous model, nvidia/nemotron-3-ultra-550b-a55b,
# began returning HTTP 404 "Specified function ... not found for account" on this
# key -- while still being listed by GET /v1/models. Measured that day: three
# models answered on the same key in the same minute and five 404'd, so it is
# per-model entitlement, not credits and not an outage.
# The sentence, on a second provider: a pinned id is a promise about a name,
# not a service.
# 2026-09-21: `deepseek-v4-flash-0731` left the NVIDIA catalog entirely -- `/v1/models` no longer
# lists it and the endpoint answers 410 Gone -- so the live demo stopped answering. Repointed to
# the model this project actually MEASURED (0.58 end to end, 91% faithful on all 100), which was dropped
# on 2026-09-16 only because it was briefly uncallable on this key and answers in ~1.3s again.
# The sentence, for the third time: a pinned id is a promise about a name, not a service.
# ORDERED FALLBACK. Two hosted models have now disappeared under this page (one to 404
# entitlement, one out of the catalog entirely), and each time the demo simply stopped
# answering until a human noticed. The page now walks this list and answers with the first
# model that responds, and SAYS WHICH ONE DID -- a fallback that quietly swaps the model
# behind an unchanged notice would be the measurement rule broken where a stranger reads.
# All three answered on 2026-09-21; only the first has been measured on this project.
MODELS = [
    "nvidia/nemotron-3-ultra-550b-a55b",      # measured here: 0.58 end to end, 91% faithful
    "nvidia/nemotron-3-super-120b-a12b",      # not measured
    "nvidia/nemotron-3.5-lightning-30b-a3b",  # not measured
]
MODEL = MODELS[0]
PREVIOUS_MODEL = "deepseek-ai/deepseek-v4-flash-0731"
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
KEY_VAR = "NVIDIA_API_KEY"

GLOBAL_PER_HOUR = 60        # chosen: every visitor together, per rolling hour
SESSION_MIN_SECONDS = 20    # chosen: one visitor cannot fire questions back to back
MAX_QUESTION_CHARS = 500    # the longest golden question is well under this

# Internal decision ids never appear in the notice a visitor reads. A visitor does
# not know what they are and never will, so a notice that cites one is showing its
# working to the wrong reader.
# WHETHER A QUESTION IS EVEN LOOKUP-SHAPED, decided before a model is called.
#
# Typing "Hello" used to cost 48 seconds, return five unrelated pages, and print the decline
# note -- which quotes a statistic about over-refusal ON REAL QUESTIONS. Attaching that to a
# greeting implies the documentation might have covered it. Three wrongs in one reply.
#
# The rule is deliberately dumb: a long sentence gets the benefit of the doubt, so does anything
# with code in it, and so does anything naming something in the library's vocabulary. A test
# asserts all 100 golden questions pass it, which is what makes the list defensible rather than
# invented -- only four of them are under 40 characters, and each names a term.
CODE_SHAPE = re.compile(r"[._()\[\]=]|\b\d+\.\d+\b")
TERMS = re.compile(
    r"sqlalchemy|session|query|engine|orm|relationship|backref|back_populates|select|insert|"
    r"update|delete|commit|rollback|flush|declarative|mapper|mapped|column|table|connection|"
    r"execute|autocommit|autobegin|autoflush|lazy|eager|joinedload|selectinload|subquery|join|"
    r"alembic|migrat|deprecat|warning|legacy|cursor|scalar|row|bind|metadata|schema|transaction|"
    r"yield_per|from_self|baked|hybrid|association|cascade|identity|detach|expire|pool|dialect|"
    r"psycopg|sqlite|postgres|mysql|python|import|attributeerror|typeerror|removedin|1\.4|2\.0",
    re.I)
MIN_SENTENCE = 40   # only 4 of the 100 golden questions are shorter, and all four name a term


def looks_like_a_lookup(question: str) -> bool:
    """Does this even name something the documentation could be searched for?"""
    q = (question or "").strip()
    return len(q) >= MIN_SENTENCE or bool(CODE_SHAPE.search(q)) or bool(TERMS.search(q))


NOT_A_LOOKUP = (
    "That does not look like a question about SQLAlchemy. Paste the error you got, or the 1.4 "
    "code that stopped working, and this will search the documentation for the page that covers "
    "it. The examples under the box are real questions it has been tested on."
)

MEASURED_MODEL_NOTICE = (
    "Answers here are written by `qwen2.5-coder:7b` on Ollama, the generator the project measured: "
    "0.42 end to end on the lab machine and 0.43 on the Mac, with the same retrieval and prompt."
)

# The two figures are Step 4d's end to end and Step 4g's faithfulness, judged on the pages
# exactly as the model saw them. A test re-derives both from
# deliverables/nemotron-all-phase6.json, so they cannot drift from the rows.
# Renamed from NOT_THE_MEASURED_MODEL on 2026-09-21: while the page served an unmeasured model that
# name was the point of the notice, and now that the page serves the measured one it would be false.
HOSTED_NOTICE = (
    f"Answers here are written by `{MODEL}`, and this project did measure that model: "
    f"0.58 end to end, with 91% of its answers judged fully supported by the pages it was given "
    f"(2026-09-13; supported is not the same as correct). The system of record is still "
    f"`qwen2.5-coder:7b`, which scores 0.42 end to end, and that is the model the other figures on "
    f"this page describe. Retrieval and the prompt are unchanged, so the five sources listed with this "
    f"answer are the "
    f"same ones every measurement used."
)


def hosted_notice(model: str | None = None) -> str:
    """The notice for whichever hosted model actually produced the answer.

    The first model in `MODELS` has measured figures and the notice quotes them.
    A fallback has none, and the notice says so plainly rather than leaving the
    reader to assume the numbers above describe it.
    """
    model = model or MODEL
    if model == MODEL:
        return HOSTED_NOTICE
    return (
        f"Answers here are written by `{model}`, and **that model has not been measured on this "
        f"project's question set**. It answered because `{MODEL}`, which was measured (0.58 end to "
        f"end), did not respond. The system of record is `qwen2.5-coder:7b` at 0.42 end to end, and "
        f"that is the model the other figures on this page describe. Retrieval and the prompt are "
        f"unchanged, so the five sources listed with this answer are the same ones every measurement "
        f"used."
    )


def langfuse_client():
    """The Langfuse client when its keys are in the environment, else None.

    Tracing is optional by design: tests, the lab and a local run have no keys and
    behave exactly as before. On Modal the keys come from the `langfuse` secret.
    Langfuse reads LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY and LANGFUSE_BASE_URL itself.
    """
    if not (os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY")):
        return None
    try:
        from langfuse import get_client
    except ImportError:
        return None
    return get_client()


def _observe(tracer, **kw):
    """A Langfuse observation, or a do-nothing stand-in when tracing is off."""
    return tracer.start_as_current_observation(**kw) if tracer else contextlib.nullcontext(None)


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
                # Round UP: rounding to nearest told a visitor with 0.4 s left to "wait 0 seconds".
                wait = max(1, math.ceil(self.gap - (now - last)))
                return f"Please wait {wait} second{'' if wait == 1 else 's'} before asking again."
            self.calls.append(now)
            self.last[session] = now
            return None


def nvidia_post(messages: list[dict], key: str, timeout: int = 180) -> dict:
    """One hosted call, trying each model in `MODELS` until one answers.

    The reply carries `_model`: which model produced it, so the page can name it.

    Successes AND failures are recorded (`rag/usage.py`): NVIDIA sends no
    rate-limit headers, so a 429 in that file is the only place "the limit was
    reached" is ever visible, and a 404 is how an entitlement disappears.
    """
    from rag import usage as usage_mod

    last = None
    for model in MODELS:
        body = {"model": model, "temperature": ask.TEMPERATURE, "max_tokens": 8192,
                "messages": messages}
        request = urllib.request.Request(
            NVIDIA_URL, data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = json.loads(response.read())
        except urllib.error.HTTPError as exc:
            usage_mod.record(model, None, "demo.nvidia_post", status=exc.code)
            last = exc
            continue
        except (urllib.error.URLError, TimeoutError) as exc:
            usage_mod.record(model, None, "demo.nvidia_post", status=None)
            last = exc
            continue
        if not (data.get("choices") or []):
            # 200 with no choices: seen on a live model, and indistinguishable from
            # success unless it is checked. Treat it as this model failing.
            last = ValueError(f"{model} returned no choices")
            continue
        usage_mod.record(model, data.get("usage"), "demo.nvidia_post")
        data["_model"] = model
        return data
    raise last if last is not None else RuntimeError("no hosted model configured")


def ollama_post(messages: list[dict], key: str | None) -> dict:
    """The measured generator, through `ask.generate` (same model, temperature and
    Ollama call the 0.42 was measured with), shaped like an OpenAI reply."""
    text, _ = ask.generate(messages[1]["content"])
    return {"choices": [{"message": {"content": text}}]}


def answer(question: str, *, key: str | None, session: str, limiter: RateLimiter,
           retrieve=None, post=nvidia_post, backend: str = "nvidia", tracer=None) -> dict:
    """Question in, {'answer', 'sources', 'refused', 'error'} out. Never raises
    for a visitor's input or a remote failure; the page shows `error` instead.

    With `tracer` (a Langfuse client, see `langfuse_client`) each question is one
    trace: `retrieve` (the five page ids) and `generate` (answer + token usage)."""
    question = (question or "").strip()
    if not question:
        return {"error": "Ask a question about upgrading SQLAlchemy 1.4 code to 2.0."}
    if len(question) > MAX_QUESTION_CHARS:
        return {"error": f"Please keep the question under {MAX_QUESTION_CHARS} characters."}
    if not looks_like_a_lookup(question):
        # No retrieval, no model call, no decline note: none of those would be true here.
        return {"error": NOT_A_LOOKUP}
    if backend == "ollama":
        post = ollama_post if post is nvidia_post else post
    elif not key:
        return {"error": f"The demo is not configured: the {KEY_VAR} secret is missing."}
    if retrieve is None:
        from rag import index
        retrieve = lambda q: index.retrieve(q, limit=ask.DEFAULT_K)

    model = "qwen2.5-coder:7b" if backend == "ollama" else MODEL
    with _observe(tracer, as_type="span", name="demo.answer",
                  input={"question": question, "backend": backend}) as root:
        result = _answer_traced(question, key, session, limiter, retrieve, post, tracer, root, model)
    if tracer:
        tracer.flush()   # a Modal container can stop minutes later; do not lose the trace
    return result


def _answer_traced(question, key, session, limiter, retrieve, post, tracer, root, model) -> dict:
    with _observe(tracer, as_type="retriever", name="retrieve", input=question) as r:
        hits = retrieve(question)
        if r:
            r.update(output=[h.payload.get("chunk_id") for h in hits])
    sources = [{"n": n, "version": h.payload["sqlalchemy_version"],
                "path": h.payload["source_path"],
                "heading": " > ".join(h.payload["heading_path"]) or "(no heading)",
                "text": h.payload["text"]} for n, h in enumerate(hits, 1)]
    blocked = limiter.check(session)
    if blocked:
        if root:
            root.update(output={"error": blocked}, level="WARNING")
        return {"error": blocked, "sources": sources}
    messages = [{"role": "system", "content": ask.SYSTEM},
                {"role": "user", "content": ask.build_prompt(question, hits)}]
    try:
        with _observe(tracer, as_type="generation", name="generate", model=model,
                      input=messages[1]["content"]) as g:
            data = post(messages, key)
            if g:
                usage = data.get("usage") or {}
                g.update(output=(data["choices"][0]["message"].get("content") or "").strip(),
                         usage_details={k: v for k, v in usage.items()
                                        if k in ("prompt_tokens", "completion_tokens") and isinstance(v, int)})
    except SystemExit:
        # ask.generate exits when Ollama is unreachable -- right for a CLI,
        # wrong for a web page. SystemExit is not an Exception.
        return {"error": "The local answer model (Ollama) is not running. The search still "
                         "ran, and its sources are listed with this message.", "sources": sources}
    except (urllib.error.URLError, TimeoutError) as exc:
        # Name the HTTP status when there is one. "HTTPError" alone cannot tell
        # 429 (rate limited, try later) from 404 (this account cannot call this
        # model) -- and on 2026-09-16 that difference cost an afternoon, because
        # the page said only "HTTPError" while the model had lost entitlement.
        code = getattr(exc, "code", None)
        detail = f"HTTP {code}" if code else type(exc).__name__
        return {"error": f"The answer model did not respond ({detail}). "
                         "The search still ran, and its sources are listed.", "sources": sources}
    text = (data["choices"][0]["message"].get("content") or "").strip()
    if root:
        root.update(output={"refused": ask.refused(text), "answer": text})
    # `_model` is set by nvidia_post when a fallback answered; the page names it.
    return {"answer": text, "sources": sources, "refused": ask.refused(text), "error": None,
            "model": data.get("_model", model)}


def render(result: dict, backend: str = "nvidia") -> str:
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
    notice = MEASURED_MODEL_NOTICE if backend == "ollama" else hosted_notice(result.get("model"))
    parts.append(f"\n---\n\n<sub>{notice}</sub>")
    return "\n\n".join(parts)


# --- the page's pieces ------------------------------------------------------
#
# `render` above returns one Markdown string and stays for callers that want
# that. The page shows the answer and the sources apart, so "[2]" in the answer
# is a link to card 2, and the cards the answer actually cited are marked.
# Everything here is DISPLAY ONLY: the measured answer text is never altered
# before `ask.refused` or any score reads it.

STATUS = {
    "answered": ("Answered from the sources", "#1f7a4d"),
    "declined": ("Declined: the sources do not cover this, so it did not guess", "#8a6d1f"),
    "error": ("Not answered", "#a33a3a"),
}

# Sphinx cross-references as the SQLAlchemy docs write them, e.g.
# :meth:`_orm.Query.from_self`, :class:`~sqlalchemy.engine.Row`,
# :paramref:`_orm.relationship.backref`, :ref:`some label <anchor>`.
SPHINX_ROLE = re.compile(r":(?:py:)?[a-z]+:`(~)?([^`<]+?)\s*(?:<[^>`]*>)?`")
FENCE = re.compile(r"(```.*?```)", re.S)
INLINE_CODE = re.compile(r"(`[^`\n]*`)")


def sphinx_name(match: re.Match) -> str:
    tilde, target = match.group(1), match.group(2).strip()
    target = re.sub(r"^_[a-z]+\.", "", target)          # _orm.Query -> Query
    return target.split(".")[-1] if tilde else target      # ~a.b.C -> C


def readable(text: str) -> str:
    """Sphinx roles in answer prose become inline code: :meth:`_orm.Query.get` -> `Query.get`."""
    return SPHINX_ROLE.sub(lambda m: f"`{sphinx_name(m)}`", text)


def link_citations(answer: str, n_sources: int) -> str:
    """[n] -> a link to source card n, outside code only, and only for n that exist.

    Uses `judge.CITATION`, the repo's one citation pattern, which already skips
    subscripts like `row[1]`. Fenced blocks and inline code are left alone.
    """
    from rag import judge

    def link(chunk: str) -> str:
        return judge.CITATION.sub(
            lambda m: f"[[{m.group(1)}]](#src-{m.group(1)})" if 1 <= int(m.group(1)) <= n_sources
            else m.group(0), chunk)

    # Order matters, and the first version had it wrong: a role's own backticks
    # (:meth:`_orm.Query.get`) look like an inline code span, so splitting out
    # inline code first hid every role from `readable`. Roles are converted
    # first (outside fenced blocks), then citations are linked outside code.
    out = []
    for part in FENCE.split(answer):
        if FENCE.fullmatch(part):
            out.append(part)
            continue
        out.append("".join(bit if INLINE_CODE.fullmatch(bit) else link(bit)
                           for bit in INLINE_CODE.split(readable(part))))
    return "".join(out)


def status(result: dict) -> str:
    if result.get("error"):
        return "error"
    return "declined" if result.get("refused") else "answered"


def render_answer(result: dict, backend: str = "nvidia") -> str:
    label, colour = STATUS[status(result)]
    parts = [f'<span style="display:inline-block;padding:3px 12px;border-radius:999px;'
             f'background:{colour};color:#fff;font-size:0.85em;font-weight:600">{label}</span>']
    if result.get("error"):
        parts.append(f"**{html.escape(result['error'])}**")
    if result.get("answer"):
        parts.append(link_citations(result["answer"], len(result.get("sources") or [])))
    notice = MEASURED_MODEL_NOTICE if backend == "ollama" else hosted_notice(result.get("model"))
    parts.append(f"<sub>{notice}</sub>")
    return "\n\n".join(parts)


def cited(result: dict) -> set[int]:
    from rag import judge
    return set(judge.citations(result.get("answer") or ""))


def render_sources(result: dict) -> str:
    """Numbered cards, anchored as #src-n. Every piece of source text is
    HTML-escaped: SQLAlchemy's docs contain literal `<...>` (doctest reprs,
    placeholders) that would otherwise be parsed as markup on the page."""
    sources = result.get("sources") or []
    if not sources:
        return ('<p style="opacity:.7;margin:.5em 0">The five documentation pages the answer is '
                'given will appear here, each one expandable.</p>')
    used = cited(result)
    cards = []
    for s in sources:
        v = html.escape(s["version"])
        badge = "#3b5bdb" if v.startswith("2.") else "#6c757d"
        mark = ('<span style="background:#1f7a4d;color:#fff;border-radius:6px;padding:1px 7px;'
                'font-size:.75em;margin-left:6px">cited</span>') if s["n"] in used else ""
        text = SPHINX_ROLE.sub(sphinx_name, s["text"])
        cards.append(
            f'<details id="src-{s["n"]}" style="border:1px solid rgba(128,128,128,.35);'
            'border-radius:10px;padding:10px 14px;margin:0 0 10px;scroll-margin-top:12px">'
            f'<summary style="cursor:pointer;line-height:1.5"><b>[{s["n"]}]</b> '
            f'<span style="background:{badge};color:#fff;border-radius:6px;padding:1px 7px;'
            f'font-size:.8em">SQLAlchemy {v}</span>{mark} {html.escape(s["heading"])}'
            f'<div style="opacity:.65;font-size:.85em;margin-top:2px">{html.escape(s["path"])}</div>'
            '</summary>'
            f'<pre style="white-space:pre-wrap;font-size:.85em;margin-top:10px">{html.escape(text)}</pre>'
            '</details>')
    return "".join(cards)


def payload(result: dict, backend: str, seconds: float) -> dict:
    """What the custom web page (space/static/index.html) receives as JSON.

    Citation links and Sphinx-role cleanup are done HERE, by the tested
    `link_citations`, not re-implemented in JavaScript: one rule, one home.
    The page renders `answer_md` as Markdown and sanitizes it before display.
    """
    sources = result.get("sources") or []
    used = cited(result)
    return {
        "status": status(result),
        "status_label": STATUS[status(result)][0],
        "error": result.get("error"),
        "answer_md": link_citations(result["answer"], len(sources)) if result.get("answer") else "",
        "sources": [{"n": s["n"], "version": s["version"], "path": s["path"], "heading": s["heading"],
                     "text": SPHINX_ROLE.sub(sphinx_name, s["text"]), "cited": s["n"] in used}
                    for s in sources],
        "notice": MEASURED_MODEL_NOTICE if backend == "ollama" else hosted_notice(result.get("model")),
        "generator": "qwen2.5-coder:7b" if backend == "ollama" else (result.get("model") or MODEL),
        "seconds": round(seconds, 1),
    }
