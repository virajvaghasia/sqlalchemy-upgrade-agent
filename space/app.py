"""The Hugging Face Space for sqlalchemy-upgrade-agent (Phase 6, Step 4).

A thin Gradio page over `rag.demo.answer()`. Everything that decides what the
page says lives in `rag/demo.py`, which the repo's test suite covers.

Dense search runs in memory here, because a Space has no Qdrant container.
That path was scored on the golden set against the Qdrant baseline before it
was allowed into this file: broken 0, moved 0 (D102).
"""

import os
import uuid

os.environ.setdefault("RAG_DENSE", "memory")   # must be set before rag.index is used

import gradio as gr  # noqa: E402

from rag import demo  # noqa: E402

LIMITER = demo.RateLimiter()
EXAMPLES = [  # three golden-set questions whose answers two independent judges supported (D101)
    "insert().values() keyword constructor style for update/delete broke",
    "joinedload with a string relationship name TypeError or removed in 2.0",
    "Column with `server_default` missing in __dict__ after flushing",
]


def ask(question: str, session: str) -> tuple[str, str]:
    session = session or uuid.uuid4().hex
    result = demo.answer(question, key=os.environ.get(demo.KEY_VAR), session=session,
                         limiter=LIMITER)
    return demo.render(result), session


with gr.Blocks(title="SQLAlchemy 1.4 → 2.0 upgrade assistant") as app:
    gr.Markdown(
        "# SQLAlchemy 1.4 → 2.0 upgrade assistant\n"
        "Paste the error or the 1.4 code that broke. The answer cites the SQLAlchemy documentation "
        "pages it was given, and every one of those pages is shown under it. If the pages do not "
        "answer the question, it says so instead of guessing."
    )
    session = gr.State("")
    question = gr.Textbox(label="Question", lines=3, max_length=demo.MAX_QUESTION_CHARS)
    button = gr.Button("Ask", variant="primary")
    output = gr.Markdown()
    gr.Examples(EXAMPLES, inputs=question)
    button.click(ask, inputs=[question, session], outputs=[output, session])
    question.submit(ask, inputs=[question, session], outputs=[output, session])

if __name__ == "__main__":
    app.launch()
