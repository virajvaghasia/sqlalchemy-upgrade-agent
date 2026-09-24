"""
The retrieval system — corpus in, answer with sources out. Phases 1 through 4.

Separate from `experiments/sqlalchemy_1_4_vs_2_0/` on purpose: that package is
an instrument pointed at SQLAlchemy, and it is pinned to 1.4.52 because the
thing it measures is a 1.4 app. This package is pointed at *text*, imports no
SQLAlchemy at all, and would work the same if the corpus were something else
entirely.

Run order, for someone opening this folder for the first time:

    corpus.py      Step 1 — fetch the documentation source for both pinned
                   releases; writes corpus/MANIFEST.json, which records where
                   every file came from and which version it documents
    chunk.py       Step 2 — cut 270 files into 3284 chunks. `--audit` counts
                   the ones that do not stand alone (10.7% / 6.3% lost)
                   and holds the three boundary-defect detectors
    embed.py       Step 3 — 3284 x 1024 float32 vectors, BGE-M3
    index.py       Step 3b — load Qdrant; `retrieve()` is the one entry point
                   every other module searches through
    ask.py         Step 4 — question in, answer plus the chunks it came from.
                   Holds the prompt, DEFAULT_K, and `refused()` — the single
                   refusal detector, beside the clause that mandates the string
    probe.py       Step 5 — break it on purpose; writes deliverables/FAILURES.md

Phase 2 — measure it:

    golden.py      the bench for building the golden set by hand. It cannot
                   mark anything verified, and a test asserts that
    score.py       the scorer. recall@k, MRR, duplicate slots, a paired
                   `--baseline` comparison with an exact McNemar p-value,
                   `--refusals` and `--absents`

Phase 3 — improve retrieval. Each of these is one measured lever:

    dedup.py       collapse cross-version twins at retrieve time
    bm25.py        keyword search, the channel dense retrieval lacks
    hybrid.py      dense-heavy RRF over the two channels
    rerank.py      seat-5 cross-encoder promotion. NOT a full re-sort:
                   re-sorting the top-20 broke ten items
    textnorm.py    REJECTED. Stripping Sphinx roles before embedding
                   cost six points of recall. Kept as the record so nobody
                   re-derives a worse index

Phase 4 — judge the answers rather than the search:

    judge.py       citation integrity, computed with no model and no API
                   key: citations pointing at sources that do not exist, code
                   blocks citing nothing, coverage of the prompt's pages.
                   Also ungrounded API calls in code, and `--report`, the
                   whole-system scorecard for Phase 4
    faithful.py    the half that needs a reader: is this answer's
                   PROSE supported by the pages it was given? Code is judge.py's
                   half and is deliberately stripped out. The judge is LOCAL
                   (`--local`, gemma4:e4b) because the hosted free tier allows
                   20 requests a day per model against a ~110-call run, and
                   the binding property is one judge across both arms in one
                   sitting. `--agreement` renders Step 5's ten for a human;
                   `--cross-check` asks a second model the same ten

This file only says what exists; each module's docstring holds its reasoning.
"""
