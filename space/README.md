# SQLAlchemy 1.4 → 2.0 upgrade assistant

Ask about 1.4 code that broke on SQLAlchemy 2.0. The answer cites numbered documentation pages, and
every page it was given is shown beside it (below it on a phone).

**How it works.** Hybrid search (dense BGE-M3 + BM25, cross-encoder at the fifth seat) over 3284
chunks of the SQLAlchemy 1.4 and 2.0 documentation finds five pages; a language model answers
from those pages only, citing them, and says so when they do not answer.

**What is measured, and what is not.** Retrieval puts the verified answer page in the top five for
64% of the 91 answerable questions in a hand-verified 100-question golden set. End to end, with
`qwen2.5-coder:7b`, 42% of those questions got an answer with the right page in hand (lab machine).
**This page uses a different generator** (`nvidia/nemotron-3-ultra-550b-a55b`), because this hosting
cannot run the local model. Measured once on the same 100 questions, retrieval and prompt (2026-09-13):
**58%** end to end, no fabrications on the 9 unanswerable questions, and **77%** of its answers judged
fully supported by the pages it was given. Supported is not the same as correct.

Source, measurements and every decision behind them: https://github.com/virajvaghasia/sqlalchemy-upgrade-agent

**Run it.** `pip install -r requirements.txt && python web.py`, then open http://127.0.0.1:7860.
On a server set `HOST=0.0.0.0` and `PORT`, and the secret `NVIDIA_API_KEY`; without the key the
page says it is missing. `DEMO_GENERATOR=ollama` uses a local `qwen2.5-coder:7b` instead, the
measured generator, and then the page's notice says so.
