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
- **The generator depends on where it runs, and the page says which.**
  `backend="ollama"` (a local run) uses `qwen2.5-coder:7b` through `ask.generate`,
  the generator the 0.42 was measured on. `backend="nvidia"` (a hosted page) uses
  `nvidia/nemotron-3-ultra-550b-a55b`, because NVIDIA's API serves no qwen; that
  model was measured with this prompt only on escalations (`D99`–`D101`), so the
  page says the 0.42 does not describe it.

RATE LIMITS ARE A CHOICE, NOT A MEASUREMENT

A public page spends Viraj's free NVIDIA credits. The two numbers below bound
that spend; they were picked, not derived, and changing them changes nothing
this repo has measured.
"""

from __future__ import annotations

import html
import json
import re
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

MEASURED_MODEL_NOTICE = (
    "Answers here are written by `qwen2.5-coder:7b` on Ollama, the generator the project measured: "
    "0.42 end to end on the lab machine and 0.43 on the Mac (D83), with the same retrieval and prompt."
)

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


def ollama_post(messages: list[dict], key: str | None) -> dict:
    """The measured generator, through `ask.generate` (same model, temperature and
    Ollama call the 0.42 was measured with), shaped like an OpenAI reply."""
    text, _ = ask.generate(messages[1]["content"])
    return {"choices": [{"message": {"content": text}}]}


def answer(question: str, *, key: str | None, session: str, limiter: RateLimiter,
           retrieve=None, post=nvidia_post, backend: str = "nvidia") -> dict:
    """Question in, {'answer', 'sources', 'refused', 'error'} out. Never raises
    for a visitor's input or a remote failure; the page shows `error` instead."""
    question = (question or "").strip()
    if not question:
        return {"error": "Ask a question about upgrading SQLAlchemy 1.4 code to 2.0."}
    if len(question) > MAX_QUESTION_CHARS:
        return {"error": f"Please keep the question under {MAX_QUESTION_CHARS} characters."}
    if backend == "ollama":
        post = ollama_post if post is nvidia_post else post
    elif not key:
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
    except SystemExit:
        # ask.generate exits when Ollama is unreachable -- right for a CLI,
        # wrong for a web page. SystemExit is not an Exception (CLAUDE.md traps).
        return {"error": "The local answer model (Ollama) is not running. The sources below were "
                         "still found.", "sources": sources}
    except (urllib.error.URLError, TimeoutError) as exc:
        return {"error": f"The answer model did not respond ({type(exc).__name__}). "
                         "The sources below were still found.", "sources": sources}
    text = (data["choices"][0]["message"].get("content") or "").strip()
    return {"answer": text, "sources": sources, "refused": ask.refused(text), "error": None}


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
    notice = MEASURED_MODEL_NOTICE if backend == "ollama" else NOT_THE_MEASURED_MODEL
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
    subscripts like `row[1]` (D79). Fenced blocks and inline code are left alone.
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
    notice = MEASURED_MODEL_NOTICE if backend == "ollama" else NOT_THE_MEASURED_MODEL
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
        "notice": MEASURED_MODEL_NOTICE if backend == "ollama" else NOT_THE_MEASURED_MODEL,
        "generator": "qwen2.5-coder:7b" if backend == "ollama" else MODEL,
        "seconds": round(seconds, 1),
    }
