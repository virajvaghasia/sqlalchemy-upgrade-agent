# Phase 3 — Make it good, and prove every improvement

Part of [`sqlalchemy-upgrade-agent`](../README.md). Continues from [`PHASE-2.md`](PHASE-2.md)
(complete: golden set of 100, signature closed, baseline artifact still the 50). The arc is in
[`ROADMAP.md`](ROADMAP.md) § Phase 3.

**Branch:** stay on `phase-2/measure` until you cut `phase-3/improve` (one long-lived branch
per phase). Lab Round 12 closed — Phase 2 confirmed on the 3060; continue here.

**Read first:** [`../study/15-IMPROVE.md`](../study/15-IMPROVE.md) §R7 — plain-language what
Phase 3 changed. This file is the measured plan/tables; that one is the sitting.

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
| **4. Chunking / text prep** | `D56` rates; also Sphinx strip | **both rejected — `D69`** (strip, measured) **and `D70`** (boundaries, surveyed) |

Do not start with a reranker before lever 2: it cannot invent a page that never entered the
candidate set. Lever 3 is a **seat-5 promotion**, not a full CE sort. Lever 4 is **two recorded
rejections**, and the second one never got built: the absents are phrasing failures, not `D56`
cuts, and `--absents` says so in one command.

**Phase 3 is closed.** Four levers, two shipped, two rejected with numbers. `0.51 → 0.64`,
**7↑ 0↓**, McNemar **p = 0.016**.

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
autobegin, …). Re-measure with **`--dense-only --no-rerank`** — both flags. `--dense-only` alone
leaves the seat-5 CE on and scores **0.53**, which is not this row and is not a system that has
ever shipped. This doc said `--dense-only` until 2026-08-22.

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

## Step 4 — Sphinx strip tried (`D69`) — rejected

**Tried overnight 2026-08-22.** Strip `:role:`…`` before embed + BM25 so developer vocabulary
matches docs vocabulary. Code path: `rag/textnorm.py`.

**Result.** Full re-embed: recall@5 **0.64 → 0.58**, **2 broken** vs baseline. Reverted;
vectors restored to raw-text embed. **Ship nothing that changes the index.**

**Implication for “chunking”.** The 17 absents’ answer chunks are **not** `D56` ends-open /
opens-ref failures. That observation lived here as prose with no command behind it until
2026-08-22; it is **Step 5** now, measured with a control (`D70`). Re-cutting prose boundaries
may still help citation quality — that is Phase 4's subject, not this scorecard's. Retrieval
here is finished: the remaining absents want a different hypothesis entirely (query rewrite,
corpus add) or the ceiling is accepted, and Phase 4 is where the larger loss actually is.

---

## Step 5 — boundary re-chunking (`D70`) — rejected without building it

**The last ROADMAP row, and the only one closed by a survey rather than a run.**

**Why it looked obvious.** `ROADMAP.md` listed “improve chunking” before Phase 1 ran, and `D56`
then attached a number to it: **10.7%** of chunks do not stand alone, **6.3%** lose content
outright. A defect that size in the thing search reads from is hard to walk past.

**Why it was the wrong population.** That 10.7% is a fact about the **corpus**. Phase 3 is
judged on the **17 answerable items absent from the top-20** — and an absent item is beyond the
reranker by construction (`D68` reorders what retrieval returned; it cannot reach a page that
never entered the list). Re-chunking is recall-side, so the absents are what it has to explain.

**Measured, and it costs no extra retrieval — it reads rows the scorer already has:**

```
# runnable: uv run python -m rag.score --absents
ABSENT FROM TOP-20 — are their answer chunks BROKEN, or just worded differently?  (D70)
  17 answerable items, 30 answer chunks between them
  g003, g005, g014, g022, g039, g040, g042, g058, g060, g071, g074, g085, g096, g112, g113, g114, g119

  shape of those 30 answer chunks                  count    corpus
    A  ends announcing what never follows            0     4.1%
    B  opens pointing at what is not here            0     6.9%
    C  boundary severed inside a code listing        1     0.2%  of cuts
    any of the three                                 1    10.7%

  control — the 74 items retrieval DOES find: 2 of 123 answer chunks flagged = 2%

  flagged, and each one wants reading before it is believed:
    g113  c02823  shape C
```

Every count sits beside the rate for the whole corpus, because **a count with no base rate is
not evidence**: 1 of 30 is alarming against a 0.2% corpus and unremarkable against a 10.7% one.

**The control is the finding, not the zeroes.** The **74** items retrieval *does* find carry
**2 of 123** flagged answer chunks — **2%**. Broken chunks sit behind successful retrievals at
the same rate as behind failures. **Chunk quality is not the variable separating them.**

**The one hit was read rather than counted.** `g113` → `c02823`: shape C fires because both
edges are indented code, but the chunk ends on a **complete** doctest (`{stop}<...>`) and
`c02824` opens a separate `>>> session.rollback()` teardown. Nothing is severed. A detector
that flags 1 in 30 needs its hit opened, or the survey is just a third regex firing.

**What this does not claim.** Not that the chunker is good — `D56` stands and `c00138`’s payload
is still gone. Not that boundary work is dead: a listing cut in half is a **citation-quality**
defect and belongs to Phase 4, which is about what the model does with the pages it is handed.
It claims one thing: **re-chunking is not the lever that reaches the 17.**

**Code.** `rag/score.py` `absent_shapes()` / `report_absents()`, calling `rag/chunk.py`’s own
`ends_open_shape` / `opens_backward_shape` / `severed_listing`. Shape C is new code for a defect
§R5.3 had only ever computed by hand. Tests: `tests/test_score.py`, `tests/test_chunk.py` —
including the indented-glossary control that separates “at least 11” from the loose 123, and a
mutation asserting the scorer holds no private copy of a detector.

---

## Gate

Phase 3 is not “done” when the ROADMAP table is full. It is done when each row has a measured
before/after and a decision id that says what was rejected.

**Closed 2026-08-22.** Every row now has both:

| row | number | decision |
|---|---|---|
| twin collapse | 0.51 → 0.52, dup seats 31 → 0 | `D66` |
| hybrid BM25 + RRF | 0.52 → **0.63**, absents 22 → 17 | `D67` |
| seat-5 CE rerank | 0.63 → **0.64**, 7↑ 0↓, p = 0.016 | `D68` |
| Sphinx strip | 0.64 → 0.58 — **rejected**, index reverted | `D69` |
| boundary re-chunking | 1 of 30 vs 2 of 123 control — **rejected unbuilt** | `D70` |

**Phase 3 ships `recall@5 = 0.64 ±0.097`**, against a Phase 1 baseline of `0.51`. Paired against
the saved 50-item ruler (`D61`/`D65`): **7 fixed, 0 broken, McNemar p = 0.016**.

**Two of the five rows are rejections, and that is the honest shape of the phase.** The gate was
written to make that sayable — a lever tried and dropped with a number beside it is evidence
about the system; a lever quietly skipped is a hole. The remaining **17 absents** are a phrasing
and corpus-ceiling problem, and no retrieval lever left on the list reaches them.

**What is not fixed, and is named rather than absorbed.** Re-measured after this phase shipped
(`D72`, 2026-08-22): end to end the system answers **0.43** against a retrieval ceiling of
**0.64** — generation loses **21 points** that no number in this table can see (`D62`).

**Phase 3's gain half-arrived.** Retrieval went up 15 points and the user got 8. Worse, **two of
the seven items this phase fixed — `g044` and `g050` — are now refused with the page in the
prompt.** Every row above scores them as wins, correctly, and the user got nothing from either.
That gap, the **19** over-refusals with the answer already in the prompt, and the two
fabrications (`g056`, `g065`) are **Phase 4**.
