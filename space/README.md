---
title: SQLAlchemy 1.4 to 2.0 upgrade assistant
emoji: 🔧
colorFrom: indigo
colorTo: gray
sdk: gradio
sdk_version: 6.27.0
python_version: "3.11"
app_file: app.py
pinned: false
---

# SQLAlchemy 1.4 → 2.0 upgrade assistant

Ask about 1.4 code that broke on SQLAlchemy 2.0. The answer cites numbered documentation pages, and
every page it was given is shown beneath it.

**How it works.** Hybrid search (dense BGE-M3 + BM25, cross-encoder at the fifth seat) over 3284
chunks of the SQLAlchemy 1.4 and 2.0 documentation finds five pages; a language model answers
from those pages only, citing them, and says so when they do not answer.

**What is measured, and what is not.** Retrieval puts the verified answer page in the top five for
64% of the 91 answerable questions in a hand-verified 100-question golden set. End to end, with
`qwen2.5-coder:7b`, 42% of those questions got an answer with the right page in hand (lab machine).
**This page uses a different generator** (`nvidia/nemotron-3-ultra-550b-a55b`), because this hosting
cannot run the local model, so the 42% does not describe these answers.

Source, measurements and every decision behind them: https://github.com/virajvaghasia/sqlalchemy-upgrade-agent
