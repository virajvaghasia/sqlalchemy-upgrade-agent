# Improve — study notes

Part of [`sqlalchemy-upgrade-agent`](../README.md). **§R7**, continuing the `R` run after
[`14-MEASURE.md`](14-MEASURE.md) §R6. Plan file (decisions + tables):
[`../phases/PHASE-3.md`](../phases/PHASE-3.md). Decisions: **`D66`–`D69`**.

> **Read this after Phase 2's scorecard.** §R6 told you the system found the right page about
> half the time, and that generation lost another ~15 points on top. This file is what we
> **changed on the search side**, one lever at a time, and what we refused to ship.

---

## If you are lost — one picture

```
  Phase 2 baseline (50-item artifact)     after Phase 3 retrieval work
  ─────────────────────────────────       ────────────────────────────
  recall@5 = 0.51                         recall@5 = 0.64   ← quote this
  duplicate seats in top-5: lots          duplicate seats: 0
  absents (not in top-20): many           absents: 17
  vs that baseline: —                     7 fixed, 0 broken (p = 0.016)
```

**Four levers. Three shipped. One measured and rejected.**

| lever | plain English | decision | headline |
|---|---|---|---|
| 1 Twin collapse | stop seating the same paragraph twice | **`D66`** | 31 wasted seats → **0** |
| 2 Hybrid BM25 | keyword search beside vector search | **`D67`** | **0.52 → 0.63** |
| 3 Seat-5 CE | one careful promotion, not a full re-sort | **`D68`** | **0.63 → 0.64** |
| 4 Sphinx strip | clean `:class:\`Session\`` before embed | **`D69` rejected** | **0.64 → 0.58** |

**What did *not* happen.** We did not “add a reranker and get smarter.” Full CE reorder of the
top-20 **broke ten** items. We did not fix the 17 absents by cleaning Sphinx markup. We did not
need the lab PC for any of these four — Mac + Qdrant was enough. Lab is for **generation** next.

**Flags that freeze the old world for a re-measure:**

```
uv run python -m rag.score --dense-only   # pre-hybrid (still has twin collapse)
uv run python -m rag.score --no-rerank    # hybrid without seat-5 CE
uv run python -m rag.score                # what ships: hybrid + seat-5 CE
uv run python -m rag.score --baseline deliverables/baseline-phase1.json
```

---

## §R7 — What Phase 3 actually changed

### R7.0 Why the ROADMAP order was wrong

`ROADMAP.md` drafted hybrid → reranker → chunking before Phase 1 ran. Phase 2's scorecard
**reordered** the work:

```
  Phase 2 finding                         What that sized
  ────────────────                        ────────────────
  31 top-5 seats lost to twins            Lever 1 first — free seats, no model
  22 answerable pages absent from top-20  Lever 2 — recall-side; reranker cannot invent them
  Median rank when found ≈ 2.5            Lever 3 — only helps ranks already nearby
  D56 chunk-cut rates                     Lever 4 — looked like chunking; absents were not cuts
```

**Show the hole a reranker cannot fill.** If the answer chunk is **not in the top 20 at all**,
the cross-encoder never sees it. Promoting seat 5 cannot create a page that never entered the
list. That is why lever 2 came before lever 3 — not because hybrid is fashionable.

---

### R7.1 Twin collapse (`D66`) — same text, two versions, one seat

The corpus holds **both** 1.4 and 2.0 docs. Many paragraphs are byte-identical across the two
releases. Dense search returns both; they eat two of five prompt seats for one idea.

**Named example of the tax.** On the 100-item set, Phase 2 counted **31** top-5 seats lost to
those twins. After collapse: **0**.

**What the code does.** Over-fetch from Qdrant, keep one chunk per `(heading_path, text)` —
the same key embedding already used (`D58`). When both halves appear, prefer **2.0.51** —
this product answers upgrades *to* 2.0; score cannot choose (vectors are identical).

```
  BEFORE                                      AFTER
  seat 1: 2.0 migration_20 paragraph          seat 1: 2.0 migration_20 paragraph
  seat 2: 1.4 twin of the same text           seat 2: something else useful
  seat 3: …                                   …
```

**Honest number.** Alone, twin collapse moved recall@5 about **0.495 → 0.516** and fixed
**2** baseline items with **0** broken. The McNemar p vs the 50 is not significant. The clear
win is the **tax**: wasted seats → 0. Absents stayed **22** — collapsing twins cannot surface a
page that was never retrieved.

**Code.** `rag/dedup.py`, on by default in `retrieve`. `dedupe=False` keeps the Phase 2 path.

**What it is not.** It is not “delete the 1.4 corpus.” Both versions stay indexed; only the
*prompt seats* stop double-booking.

---

### R7.2 Hybrid BM25 + dense-heavy RRF (`D67`) — the big lift

Dense search matches *meaning*. BM25 matches *words*. Stuck developers type error strings and
API names; docs sometimes bury those names in headings the dense model under-ranks.

**What ships.** Run BM25 over `chunks.jsonl` beside Qdrant. Fuse the two ranked lists with
**Reciprocal Rank Fusion** (RRF). Dense gets a stronger vote: **`kd=25`**, BM25 **`kb=90`**.

**Why not equal weights.** Equal `k=60` raised the average and **broke five** items dense
already had. `D61` reports flipped items; a prettier mean with regressions is the wrong story.

**Named example of the gain.** Stack Overflow provenance: **0.38 → 0.48** at recall@5. Real
developer phrasing is where keyword search pays.

| | dense + dedupe | + hybrid |
|---|---|---|
| recall@5 (91 answerable) | 0.52 ±0.101 | **0.63 ±0.097** |
| not in top-20 | 22 | **17** |
| vs 50-item baseline | 2↑ 0↓ | **6↑ 0↓**, p = 0.031 |

Fixed against the saved baseline: `g024`, `g038`, `g044`, `g046`, `g047`, `g050`.

**What it is not.** Hybrid does not invent `has_table` (zero chunks in the corpus — ceiling).
It does not make every symbol miss free: some phrasings still leave the answer past rank 20.
Re-measure anytime with `--dense-only`.

**Code.** `rag/bm25.py`, `rag/hybrid.py`. Default `retrieve(..., hybrid=True)`.

---

### R7.3 Seat-5 CE promotion (`D68`) — one seat, not a sort

A **cross-encoder** (CE) reads the question and one candidate together and scores that pair.
`BAAI/bge-reranker-base` scores the hybrid top-20.

**What was tried and rejected.** Full reorder by CE score: recall@5 went up a few points and
**broke ten** items. That is the interview trap — average improved, paired comparison failed.

**What ships instead.** Only **seat 5** may change. Look at ranks **6..10**. If the best CE
score there beats seat 5 by ≥ **0.8** logits, promote that chunk into seat 5. Everything else
stays.

```
  hybrid top-5          CE says rank-7 is much better than seat 5
  [A B C D E]     →     [A B C D G]     only E↔G, and only if margin ≥ 0.8
                 ranks 6–10 scanned; 1–4 frozen
```

| | hybrid | + seat-5 CE |
|---|---|---|
| recall@5 | 0.63 | **0.64** |
| absents | 17 | **17** (unchanged — as expected) |
| vs 50-item baseline | 6↑ 0↓ | **7↑ 0↓** (`g017` added), p = 0.016 |

**Honest read.** One clean flip. Worth shipping because the unsafe alternative looked better
on the average. Absents stay 17 — a reranker cannot reach them.

**Code.** `rag/rerank.py`. Default on. `--no-rerank` freezes the pre-`D68` path.

---

### R7.4 Sphinx strip (`D69`) — measured, rejected, kept on disk

Docs are written `:class:\`_orm.Session\``. Developers type `Session`. Phase 1 left markup
raw on purpose. Overnight we tried stripping roles before embed + BM25 so vocabularies match.

**BM25-only strip:** no headline gain; absents still 17.

**Full re-embed with strip:**

| | raw (ships) | stripped embed |
|---|---|---|
| recall@5 | **0.64** | **0.58** |
| vs baseline | **7↑ 0↓** | **5↑ 2↓** (`g008`, `g013` broken) |
| absents | 17 | 15 |

Two pages entered the top-20; the top-5 fell apart. Mean tokens dropped 363 → 314 — the model
was not starving for room. Best current read: BGE-M3 already embeds the inner identifiers;
stripping also deletes path cues (`_orm`, `_engine`) the dense space had been using.

**What remains on disk.** `rag/textnorm.py` + `tests/test_textnorm.py` — the rejected
experiment, so the next sitting does not re-derive a worse index. Production
`embedding_input` and BM25 stay on **raw** text (`D69`).

**Implication for “chunking.”** Survey of the 17 absents: answer chunks are **not** the
`D56` ends-open / opens-ref failures. Example: `g042` (*comment.issue = issue, never
INSERTed*) overlaps its cascade answer chunk **0/8** tokens — vocabulary mismatch, not a
severed listing. Boundary re-cuts may still help citation quality; they are not the absent
lever this scorecard is asking for.

---

### R7.5 What is left — and what needs the lab

**Retrieval ceiling for now.** Quote **0.64**. Seventeen absents are mostly phrasing or
corpus gaps. Further retrieval bets (query rewrite, add pages to the corpus) are optional
measured experiments — not required to close Phase 3's retrieval story.

**Phase 4 is generation.** §R6.2 already named it:

- **13** answerable items refused **with** the answer chunk already in the prompt
- Fabrications **`g056`**, **`g065`**
- Q18 / Q19 from Phase 1 (same class)

That work needs **Ollama + GPU** for a full `--refusals` re-baseline in one sitting (`D54`:
do not compare refusal cells across days). The lab PC is the right box. Start from
[`../logs/HANDOFF.md`](../logs/HANDOFF.md) **Round 13**.

**Mac vs lab for what you just read:**

| work | where |
|---|---|
| `D66`–`D69` (this file) | **Mac** — Qdrant + embed + score |
| Confirm retrieval after pull | either machine |
| `--refusals`, prompt changes, judge later | **lab PC** (3060) — Round 13 |

---

## After this you can say

- Phase 3 shipped **twin collapse, hybrid BM25, seat-5 CE**; **Sphinx strip was tried and
  rejected** with numbers.
- Full CE reorder looked better on the average and **broke ten** items — that is why seat-5
  only shipped.
- Absents are not a markup problem and mostly not a `D56` cut problem.
- Next sitting is Phase 4 on the lab, not another embed experiment on the Mac.

## Do not say

- “We added a reranker” (without saying seat-5 promotion and the rejected full sort).
- “Chunking is next” as if `D69` were unfinished homework — strip is closed; boundary repair
  is optional and unlikely to fix the 17.
- “0.64 on the lab, 0.64 on the Mac” as two systems — one scorecard; lab confirms.

---

## Where the rest lives

| | |
|---|---|
| [`../phases/PHASE-3.md`](../phases/PHASE-3.md) | step-by-step plan + measured tables |
| [`09-DECISIONS.md`](09-DECISIONS.md) | `D66`–`D69` full entries |
| [`14-MEASURE.md`](14-MEASURE.md) | §R6 — the scorecard Phase 3 improved from |
| [`../logs/HANDOFF.md`](../logs/HANDOFF.md) | Round 13 — lab start for Phase 4 |
| [`../phases/ROADMAP.md`](../phases/ROADMAP.md) | Phase 4 judge / faithfulness arc |
