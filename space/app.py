"""The demo page for sqlalchemy-upgrade-agent (Phase 6, Step 4).

A thin Gradio page over `rag.demo`. Everything that decides what the page says
-- the search, the prompt, the refusal check, the notice naming the generator,
the escaping of source text -- lives in `rag/demo.py`, which the test suite
covers. This file is layout only.

Dense search runs in memory, because a free host has no Qdrant container.
That path was scored on the golden set against the Qdrant baseline before it
was allowed here: broken 0, moved 0 (D102).

    # locally, with the measured generator (no key needed):
    DEMO_GENERATOR=ollama RAG_DENSE=memory PYTHONPATH=. uv run --with gradio==6.27.0 python space/app.py
"""

import os
import time
import uuid

os.environ.setdefault("RAG_DENSE", "memory")   # must be set before rag.index is used

import gradio as gr  # noqa: E402

from rag import demo  # noqa: E402

# "nvidia" for a hosted page (key from the environment); "ollama" to run the
# measured generator locally, which needs no key: DEMO_GENERATOR=ollama.
BACKEND = os.environ.get("DEMO_GENERATOR", "nvidia")
# The limits exist because a hosted page spends API credits. A local Ollama run
# spends nothing, so it is not limited: two example clicks in a row just work.
LIMITER = (demo.RateLimiter(per_hour=10**9, gap=0) if BACKEND == "ollama" else demo.RateLimiter())
GENERATOR = "qwen2.5-coder:7b (Ollama, the measured model)" if BACKEND == "ollama" else demo.MODEL

# Chosen from measurements, not taste (PHASE-6.md Step 4): the first four are
# golden-set questions the measured model ANSWERED, citing its source, on the Mac
# (framing-phase6.Darwin-arm64.json arm A). The last is one it DECLINES with the
# answer page in hand -- a measured over-refusal (D72) -- shown on purpose.
EXAMPLES = [
    ("query(User).get(1) moved", "query(User).get(1) warns LegacyAPIWarning, where did get move to"),
    ("backref= deprecated?", "backref= in relationship is deprecated what should I use instead"),
    ("Session(autocommit=True) gone", "Session(autocommit=True) is gone, what replaces autocommit mode"),
    ("insert(values=...) broke", "insert().values() keyword constructor style for update/delete broke"),
    ("engine.execute gone (declines)", "engine.execute select gone AttributeError use connection instead"),
]

HOW_IT_WORKS = f"""
**1. Search.** Your question is matched against 3284 passages from the SQLAlchemy 1.4 and 2.0
documentation: meaning-based search (BGE-M3) and keyword search (BM25) combined, with a
cross-encoder allowed to promote one page into fifth place. The five best pages go to step 2.

**2. Answer.** A language model reads only those five pages and must cite them as `[1]`–`[5]`.
If they do not answer the question it must say so, and the page marks that as *declined*.

**3. Measured, not claimed.** On a hand-verified set of 100 real questions, the right page reaches
the five for **64%** of the answerable ones. End to end, with `qwen2.5-coder:7b`, **42%** got an
answer with that page in hand (lab machine). This page is generating with **{GENERATOR}**.
"""

CSS = """
.app-header h1 { margin-bottom: 0.15em; }
.app-header p { opacity: 0.8; margin-top: 0; }
.example-row button { white-space: normal; text-align: left; }
.answer-box { min-height: 180px; }
footer { display: none !important; }
"""

# Clicking "[2]" in an answer opens source card 2 and scrolls to it. A plain
# #src-2 hash link was not enough, measured in the browser: the link rendered and
# the card existed, but the hash never changed, so nothing opened. A delegated
# click handler does not depend on hash navigation. The window flag stops a
# second copy of this script (Gradio injected the head twice) from double-binding.
HEAD = """<script>
if (!window.__srcLinks) {
  window.__srcLinks = true;
  document.addEventListener("click", (event) => {
    const link = event.target.closest && event.target.closest('a[href^="#src-"]');
    if (!link) return;
    const card = document.getElementById(link.getAttribute("href").slice(1));
    if (!card) return;
    event.preventDefault();
    card.open = true;
    card.scrollIntoView({behavior: "smooth", block: "center"});
  }, true);
}
</script>"""

WORKING = ("**Searching 3284 documentation passages, then asking the model…**\n\n"
           "<sub>The first question after start-up loads the models and can take about a minute.</sub>")
EMPTY_ANSWER = "Ask a question, or pick an example on the left."


def _key():
    """The environment first; when run from the repo, fall back to its .env."""
    if os.environ.get(demo.KEY_VAR):
        return os.environ[demo.KEY_VAR]
    try:
        from rag import faithful
        return faithful.env_key(demo.KEY_VAR)
    except Exception:
        return None


def ask(question: str, session: str):
    session = session or uuid.uuid4().hex
    started = time.perf_counter()
    result = demo.answer(question, key=_key(), session=session, limiter=LIMITER, backend=BACKEND)
    took = time.perf_counter() - started
    meta = f"<sub>{took:.1f} s · {len(result.get('sources') or [])} sources · {GENERATOR}</sub>"
    return demo.render_answer(result, BACKEND) + "\n\n" + meta, demo.render_sources(result), session


def working():
    return WORKING, demo.render_sources({})


def clear():
    return "", EMPTY_ANSWER, demo.render_sources({})


with gr.Blocks(title="SQLAlchemy 1.4 → 2.0 upgrade assistant") as app:
    session = gr.State("")
    with gr.Column(elem_classes="app-header"):
        gr.Markdown(
            "# SQLAlchemy 1.4 → 2.0 upgrade assistant\n"
            "Paste the error, or describe the 1.4 code that broke. The answer cites the documentation "
            "pages it was given; click a citation like **[1]** to open that page below."
        )
    with gr.Row(equal_height=False):
        with gr.Column(scale=4, min_width=320):
            question = gr.Textbox(
                label="Your question", lines=4, max_length=demo.MAX_QUESTION_CHARS,
                placeholder="e.g. session.query(User).get(5) warns LegacyAPIWarning, what replaces it?",
                submit_btn="Ask",
            )
            clear_btn = gr.Button("Clear", size="sm", variant="secondary")
            gr.Markdown("**Try a real question from the test set**")
            with gr.Column(elem_classes="example-row"):
                example_buttons = [(gr.Button(label, size="sm"), text) for label, text in EXAMPLES]
            with gr.Accordion("How this works, and what is measured", open=False):
                gr.Markdown(HOW_IT_WORKS)
        with gr.Column(scale=6, min_width=380):
            answer = gr.Markdown(EMPTY_ANSWER, container=True, padding=True, elem_classes="answer-box")
            gr.Markdown("### Sources the answer was given")
            sources = gr.HTML(demo.render_sources({}))

    outputs = [answer, sources, session]
    # show_progress="hidden" on every step: Gradio's own "processing | 0.0s" label
    # otherwise sits on top of the WORKING message (seen in the browser).
    question.submit(working, None, [answer, sources], queue=False, show_progress="hidden").then(
        ask, inputs=[question, session], outputs=outputs, show_progress="hidden")
    for button, text in example_buttons:
        button.click(lambda t=text: t, None, question, queue=False, show_progress="hidden").then(
            working, None, [answer, sources], queue=False, show_progress="hidden").then(
            ask, inputs=[question, session], outputs=outputs, show_progress="hidden")
    clear_btn.click(clear, None, [question, answer, sources], queue=False, show_progress="hidden")

if __name__ == "__main__":
    app.launch(theme=gr.themes.Soft(primary_hue="indigo", neutral_hue="slate"), css=CSS, head=HEAD)
