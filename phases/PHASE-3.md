# Phase 3 — Make it good, and prove every improvement

Part of [`sqlalchemy-upgrade-agent`](../README.md). Continues from [`PHASE-2.md`](PHASE-2.md)
(complete: golden set of 100, signature closed, baseline artifact still the 50). The arc is in
[`ROADMAP.md`](ROADMAP.md) § Phase 3.

**Branch:** stay on `phase-2/measure` until you cut `phase-3/improve` (one long-lived branch
per phase). Lab Round 12 closed — Phase 2 confirmed on the 3060; continue here.

**Rule:** one change at a time, measure after each (`D61` paired comparison against
`deliverables/baseline-phase1.json`).

---

## Levers, sized by Phase 2 — not by the ROADMAP draft order

`ROADMAP.md` listed hybrid → reranker → chunking before Phase 1 ran. Measurement reordered them:

| lever | what Phase 2 sized | status |
|---|---|---|
| **1. Twin collapse at retrieve** | **31** top-5 seats lost to cross-version duplicates on the 100 | **done 2026-08-21 — `D66`** |
| **2. Recall-side (BM25 + hybrid RRF)** | **22** answerable items absent from top-20 | **done 2026-08-21 — `D67`** |
| **3. Reranker** | helps ranks like 8–12, not pages still absent | **done 2026-08-21 — `D68`** |
| **4. Chunking / text prep** | `D56` rates; also Sphinx strip | **`D69` strip rejected**; boundary repair still open |

Do not start with a reranker before lever 2: it cannot invent a page that never entered the
candidate set. Lever 3 is a **seat-5 promotion**, not a full CE sort. Lever 4’s first attempt
(Sphinx strip) is a recorded rejection — absents are mostly phrasing, not `D56` cuts.

---

## Step 1 — Twin collapse (`D66`) — closed

**What.** `rag/index.retrieve` over-fetches, then keeps one chunk per `(heading_path, text)` —
the same key as embedding (`D58`). Prefer **2.0.51** when both halves appear.

**Why prefer 2.0.** This product answers 1.4 → 2.0 upgrades. The vectors are byte-identical, so
score cannot choose; the product can.

**Measured 2026-08-21 on the Mac (Qdrant up):**

| | no dedupe | with dedupe |
|---|---|---|
| recall@5 (100 / 91 answerable) | **0.495** | **0.516** (~0.52 ±0.101) |
| slots lost to duplicates in top-5 | **31** | **0** |
| not in top-20 | 22 | 22 (unchanged — as expected) |
| vs 50-item baseline (`--baseline`) | — | **2 fixed** (`g046`, `g047`), **0 broken**, McNemar p = 0.500 |

**Honest read.** The McNemar p against the 50 is not significant — two flips is inside noise at
that n. The **clear** win is the tax: 31 wasted seats → 0, with **zero regressions**. Strict and
permissive recall now match on the headline, because the twin no longer occupies a second seat.

**Code.** `rag/dedup.py`, wired through `rag/index.retrieve(..., dedupe=True)`. `dedupe=False`
keeps the Phase 2 measurement path. Tests: `tests/test_dedup.py`.

---

## Step 2 — BM25 + dense-heavy RRF (`D67`) — closed

**What.** Keyword search (Okapi BM25 over `chunks.jsonl`) runs beside dense Qdrant search. The
two ranked lists fuse with Reciprocal Rank Fusion. Dense gets a stronger vote (`kd=25`) than
BM25 (`kb=90`) — measured, not assumed.

**Why not equal-k RRF.** Equal `k=60` lifted recall@5 but **broke five** items that dense already
had. `D61` cares about flipped items; a higher average with regressions is a worse story than a
smaller gain with none.

**Sweep (100-item, after `D66`, Mac):**

| kd | kb | recall@5 | fixed vs dense | broken |
|---|---|---|---|---|
| 20 | 100 | 0.582 | 6 | **0** |
| **25** | **90** | **0.615** (probe) | **9** | **0** |
| 30 | 80 | 0.637 | 13 | 2 |

Shipped: **kd=25, kb=90**.

**Measured end-to-end (`uv run python -m rag.score`, hybrid on):**

| | dense+dedupe | + hybrid (`D67`) |
|---|---|---|
| recall@5 (100 / 91) | 0.52 ±0.101 | **0.63 ±0.097** |
| recall@20 | 0.76 | **0.81** |
| MRR | 0.376 | **0.436** |
| not in top-20 | 22 | **17** |
| stackoverflow recall@5 | 0.38 | **0.48** |
| vs 50-item baseline | 2↑ 0↓ (D66 alone) | **6↑ 0↓**, McNemar **p = 0.031** |

Fixed against the saved baseline: `g024`, `g038`, `g044`, `g046`, `g047`, `g050`. Zero broken.

**What it is not.** Hybrid does not fix `has_table` (zero chunks — corpus ceiling). It does not
make `table_names` a free win either: BM25 alone still ranks the answer past 20 on that
phrasing; the gain is on other symbol-shaped misses (`joinedload` string path, `Row` vs entity,
autobegin, …). Re-measure with `--dense-only` anytime.

**Code.** `rag/bm25.py`, `rag/hybrid.py`, wired as `retrieve(..., hybrid=True)`. Flags:
`rag.score --dense-only`, `rag.index --search … --dense-only`. Tests: `tests/test_hybrid.py`.

**Not done here.** Reranking, re-chunking, or raising `DEFAULT_K`.

---

## Step 3 — seat-5 CE promotion (`D68`) — closed

**What.** `BAAI/bge-reranker-base` scores the hybrid top-20. **Only seat 5** may change: if the
best CE score among ranks **6..10** beats seat 5 by ≥ **0.8** logits, that chunk takes seat 5.

**What was rejected (measured).** Full CE reorder: +3 at recall@5 and **10 broken**. Hybrid-heavy
RRF of the two lists: **0 fixed** once safe. Freeze-head fill: always broken until identity.

**Measured end-to-end:**

| | hybrid (`D67`) | + seat-5 CE (`D68`) |
|---|---|---|
| recall@5 (100 / 91) | 0.63 ±0.097 | **0.64 ±0.097** |
| not in top-20 | 17 | **17** |
| vs 50-item baseline | 6↑ 0↓ | **7↑ 0↓** (`g017` added), McNemar **p = 0.016** |

**Honest read.** One clean flip. Worth shipping because the unsafe alternative looked better on
the average and would have been the wrong interview story. Re-measure with `--no-rerank`.

**Code.** `rag/rerank.py`, wired as `retrieve(..., rerank=True)`. Tests: `tests/test_rerank.py`.

---

## Step 4 — Sphinx strip tried (`D69`) — rejected; chunk boundary repair still open

**Tried overnight 2026-08-22.** Strip `:role:`…`` before embed + BM25 so developer vocabulary
matches docs vocabulary. Code path: `rag/textnorm.py`.

**Result.** Full re-embed: recall@5 **0.64 → 0.58**, **2 broken** vs baseline. Reverted;
vectors restored to raw-text embed. **Ship nothing that changes the index.**

**Implication for “chunking”.** The 17 absents’ answer chunks are **not** `D56` ends-open /
opens-ref failures. Re-cutting prose boundaries may still help citation quality; it is not the
absent lever this scorecard is asking for. Next retrieval work needs a different hypothesis
(query rewrite, corpus add, or accept the ceiling and move to Phase 4 generation).

---

## Gate

Phase 3 is not “done” when the ROADMAP table is full. It is done when each row has a measured
before/after and a decision id that says what was rejected.
