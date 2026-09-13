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

LIMITER = demo.RateLimiter()
# "nvidia" for a hosted page (key from the environment); "ollama" to run the
# measured generator locally, which needs no key: DEMO_GENERATOR=ollama.
BACKEND = os.environ.get("DEMO_GENERATOR", "nvidia")
GENERATOR = "qwen2.5-coder:7b (Ollama, the measured model)" if BACKEND == "ollama" else demo.MODEL

EXAMPLES = [  # golden-set questions, as real developers phrased them (D65)
    "insert().values() keyword constructor style for update/delete broke",
    "joinedload with a string relationship name TypeError or removed in 2.0",
    "Column with `server_default` missing in __dict__ after flushing",
    "engine.execute select gone AttributeError use connection instead",
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
.app-header h1 { margin-bottom: 0.2em; }
.app-header p { opacity: 0.8; margin-top: 0; }
footer { display: none !important; }
"""


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


with gr.Blocks(title="SQLAlchemy 1.4 → 2.0 upgrade assistant", fill_width=False) as app:
    session = gr.State("")
    with gr.Column(elem_classes="app-header"):
        gr.Markdown(
            "# SQLAlchemy 1.4 → 2.0 upgrade assistant\n"
            "Paste the error or describe the 1.4 code that broke. Every answer cites the documentation "
            "pages it was given, and you can open each one below it."
        )
    with gr.Row(equal_height=False):
        with gr.Column(scale=4, min_width=320):
            question = gr.Textbox(
                label="Your question", lines=4, max_length=demo.MAX_QUESTION_CHARS,
                placeholder="e.g. session.query(User).get(5) is deprecated, what replaces it?",
                submit_btn="Ask",
            )
            gr.Examples(EXAMPLES, inputs=question, label="Real questions from the golden set")
            with gr.Accordion("How this works, and what is measured", open=False):
                gr.Markdown(HOW_IT_WORKS)
        with gr.Column(scale=6, min_width=380):
            answer = gr.Markdown("Ask a question to see an answer here.", label="Answer",
                                 container=True, padding=True, min_height=160)
            gr.Markdown("### Sources the answer was given")
            sources = gr.HTML(demo.render_sources({}))
    question.submit(ask, inputs=[question, session], outputs=[answer, sources, session],
                    show_progress="minimal")

if __name__ == "__main__":
    app.launch(theme=gr.themes.Soft(primary_hue="indigo", neutral_hue="slate"), css=CSS)
