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
                   the ones that do not stand alone (D56: 10.7% / 6.3% lost)
                   and holds the three boundary-defect detectors (D70)
    embed.py       Step 3 — 3284 x 1024 float32 vectors, BGE-M3
    index.py       Step 3b — load Qdrant; `retrieve()` is the one entry point
                   every other module searches through
    ask.py         Step 4 — question in, answer plus the chunks it came from.
                   Holds the prompt, DEFAULT_K, and `refused()` — the single
                   refusal detector, beside the clause that mandates the string
    probe.py       Step 5 — break it on purpose; writes deliverables/FAILURES.md

Phase 2 — measure it:

    golden.py      the bench for building the golden set by hand. It cannot
                   mark anything verified, and a test asserts that (D06)
    score.py       the scorer. recall@k, MRR, duplicate slots, a paired
                   `--baseline` comparison with an exact McNemar p-value,
                   `--refusals` (D62) and `--absents` (D70)

Phase 3 — improve retrieval. Each of these is one measured lever:

    dedup.py       D66 — collapse cross-version twins at retrieve time
    bm25.py        D67 — keyword search, the channel dense retrieval lacks
    hybrid.py      D67 — dense-heavy RRF over the two channels
    rerank.py      D68 — seat-5 cross-encoder promotion. NOT a full re-sort:
                   re-sorting the top-20 broke ten items
    textnorm.py    D69 — REJECTED. Stripping Sphinx roles before embedding
                   cost six points of recall. Kept as the record so the next
                   sitting does not re-derive a worse index

Phase 4 — judge the answers rather than the search:

    judge.py       D71 — citation integrity, computed with no model and no API
                   key: citations pointing at sources that do not exist, code
                   blocks citing nothing, coverage of the prompt's pages

`phases/PHASE-1.md` through `PHASE-4.md` hold the reasoning; this file only
says what exists. Decisions are cited by id and live in study/09-DECISIONS.md.
"""
