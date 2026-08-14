"""
The Phase 1 retrieval system — corpus in, answer with sources out.

Separate from `experiments/sqlalchemy_1_4_vs_2_0/` on purpose: that package is
an instrument pointed at SQLAlchemy, and it is pinned to 1.4.52 because the
thing it measures is a 1.4 app. This package is pointed at *text*, imports no
SQLAlchemy at all, and would work the same if the corpus were something else
entirely.

Run order, for someone opening this folder for the first time:

    corpus.py      Step 1 — fetch the documentation source for both pinned
                   versions and write corpus/MANIFEST.json, which records
                   where every file came from and which release it documents

Steps 2-5 (chunk, embed, retrieve, break-it-on-purpose) land here as they are
built. `phases/PHASE-1.md` is the plan and holds the reasoning; this file only
says what exists.
"""
