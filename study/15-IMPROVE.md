# Improve — study notes

Part of [`sqlalchemy-upgrade-agent`](../README.md). **§R7**, continuing the `R` run after
[`14-MEASURE.md`](14-MEASURE.md) §R6. Plan file (decisions + tables):
[`../phases/PHASE-3.md`](../phases/PHASE-3.md). Decisions: **`D66`–`D70`**.

> **Read this after Phase 2's scorecard.** §R6 told you the system found the right page about
> half the time, and that generation lost another ~15 points on top (re-measured after this
> phase: **21** points, `D72`). This file is what we
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

**Five levers. Three shipped. Two rejected — one after a full re-embed, one after a survey
that cost a single command.**

| lever | plain English | decision | headline |
|---|---|---|---|
| 1 Twin collapse | stop seating the same paragraph twice | **`D66`** | 31 wasted seats → **0** |
| 2 Hybrid BM25 | keyword search beside vector search | **`D67`** | **0.52 → 0.63** |
| 3 Seat-5 CE | one careful promotion, not a full re-sort | **`D68`** | **0.63 → 0.64** |
| 4 Sphinx strip | clean `:class:\`Session\`` before embed | **`D69` rejected** | **0.64 → 0.58** |
| 5 Re-chunk boundaries | re-cut the pages search reads | **`D70` rejected** | 1 of 30 vs **2 of 123** control |

### Easy picture — what each lever is doing

You only put **five pages** on the desk for the model (`DEFAULT_K = 5`). Everything below is
about *which five*, and *how they got onto the shortlist*.

**1. Twin collapse (`D66`) — stop photocopies eating seats**

The library has the same paragraph in the **1.4 book** and the **2.0 book**. Search finds both.
Without this lever, two of your five desk slots are the *same* text twice. Twin collapse keeps
**one** copy (prefers 2.0) and frees a seat for something else.

```
  Desk before:  [page A] [same A again] [B] [C] [D]     ← one idea, two seats
  Desk after:   [page A] [B] [C] [D] [E]                 ← E finally fits
```

It does **not** find new books. It only stops wasting seats on duplicates.

**2. Hybrid BM25 (`D67`) — two ways to pick books, then merge**

- **Dense (vectors):** “pages that *mean* something like this question.”
- **BM25 (keywords):** “pages that *contain these words*” (`table_names`, `RemovedIn20Warning`, …).

A stuck developer often types the **error string**. Dense can miss that; BM25 catches the
literal words. Hybrid runs **both**, then merges the two ranked lists (RRF). Dense gets a
stronger vote so keyword search cannot shove good semantic hits off the desk.

```
  Dense alone:   good for “vibes”, weak for exact API names
  BM25 alone:    good for exact names, weak for paraphrase
  Hybrid:        both lists → one shortlist of 20 → then take top 5 for the prompt
```

This **can** pull in pages that were absent before (absents 22 → 17). Biggest Phase 3 gain.

**3. Seat-5 CE (`D68`) — a second opinion on only the last seat**

After hybrid, you already have a top-20. A **cross-encoder** re-reads *question + one page*
together and scores that pair (more careful, slower).

We did **not** re-sort all twenty — that broke ten questions. We only allow a swap into
**seat 5**: if something in ranks 6–10 scores *clearly* better than whatever is in seat 5,
promote it. Seats 1–4 stay put.

```
  Hybrid desk:     [1] [2] [3] [4] [5]     and 6…10 waiting in the hall
  After seat-5:    [1] [2] [3] [4] [7?]    only if 7 beats 5 by a wide margin
```

Small gain (0.63 → 0.64). Cannot help pages still outside the top 20.

**4. Sphinx strip (`D69`) — clean the markup before searching — REJECTED**

Docs say `:class:\`_orm.Session\``. You type `Session`. Idea: strip the Sphinx wrapping so
search sees `Session`.

Tried it. **Made search worse** (0.64 → 0.58) and broke two baseline hits. So we **did not
ship it**. Raw text stays. The cleaning code is on disk only so nobody “cleverly” re-tries
it without reading the measurement.

**One line each, if someone asks in an interview:**

| lever | one sentence |
|---|---|
| Twin collapse | Don’t put the same paragraph on the desk twice. |
| Hybrid | Search by meaning **and** by exact words, then merge. |
| Seat-5 CE | Let a careful scorer swap only the 5th page, not reshuffle everything. |
| Sphinx strip | Cleaning docs markup before embed hurt; we left the text raw. |

**What did *not* happen.** We did not “add a reranker and get smarter.” Full CE reorder of the
top-20 **broke ten** items. We did not fix the 17 absents by cleaning Sphinx markup. We did not
need the lab PC for any of these four — Mac + Qdrant was enough. Lab is for **generation** next.

**Flags that freeze the old world for a re-measure:**

```
uv run python -m rag.score --dense-only --no-rerank   # the D66 row: dense + twin collapse
uv run python -m rag.score --no-rerank                # the D67 row: hybrid, no seat-5 CE
uv run python -m rag.score                            # what ships: hybrid + seat-5 CE
uv run python -m rag.score --baseline deliverables/baseline-phase1.json
uv run python -m rag.score --absents                  # D70: why the 17 misses are missed
```

**`--dense-only` on its own is not the `D66` row**, and this file said it was until 2026-08-22.
It turns off BM25 and leaves the cross-encoder on — a combination that has never shipped and is
not a row in the table. It scores **0.53**; the `D66` row is **0.52**. One flag, one point of
recall, and a number in a doc that no command produced. **Both flags, or neither.**

---

## §R7 — What Phase 3 actually changed

### R7.0 Why we did the levers in this order (not the ROADMAP order)

`ROADMAP.md` guessed: hybrid → reranker → chunking. Phase 2 then **measured** four separate
problems. Each problem pointed at a different fix. Left column = what we saw. Right column =
which lever we tried because of it.

```
  What Phase 2 measured                     Fix we tried because of it
  ─────────────────────                     ──────────────────────────
  31 top-5 seats were duplicate twins       Lever 1 — twin collapse (free a seat, no new model)
  22 answers never showed up in top-20      Lever 2 — hybrid search (find more pages first)
  When found, answer was usually rank ~2.5  Lever 3 — only nudge seat 5 (not reshuffle all 20)
  Some chunks look cut mid-sentence (D56)   Lever 4 — looked like “fix chunking”; mostly wrong bet
```

**Row 1 — 31 duplicate seats → twin collapse**

Across the top-5 lists, **31 seats** were the same paragraph twice (1.4 copy + 2.0 copy). Search
had the right idea; it just wasted a desk slot. Fix: keep one copy. Cheap. Do it first so the
next levers are not fighting doubles.

**Row 2 — 22 answers missing from the top 20 → hybrid**

For **22** questions, the right page was **not in the top 20 at all**. A reranker only reorders
pages already on the list — it cannot pull in a page that never arrived. So first: search better
(keyword + vectors). Then worry about order.

**Row 3 — usually already near the front → seat-5 only**

When the answer *was* found, it was usually already high (about rank **2.5**). So the common
failure was not “stuck at rank 12.” Full re-sorting the top-20 was the wrong fix. A small swap
into seat 5 (from ranks 6–10) matched what we saw.

**Row 4 — cut-looking chunks → not the absent fix**

Phase 1 saw that some chunks end or start mid-thought (`D56`) — **10.7%** of them. Easy to blame
the absents on that. We checked the missing answers instead of assuming: their pages are
**whole**, just hard to match by phrasing. Cleaning Sphinx markup was the cheap try and it made
scores worse (`D69`); re-cutting the boundaries was surveyed and never built (`D70`, R7.5),
because the questions search *does* find have broken answer chunks at the **same 2% rate**.

**The one picture that decides order:** if the page is outside the top 20, nothing that only
reorders seats 1–20 can help. Find more pages first (lever 2), then polish order (lever 3).

---

### R7.1 Twin collapse (`D66`) — don’t put the same page on the desk twice

**The problem in one picture.**

You ask a question. Search returns five pages for the model. Often two of those five were
**the same paragraph printed twice** — once from the 1.4 docs, once from the 2.0 docs — because
we index both releases and many lines are word-for-word identical.

```
  Desk before twin collapse
  ┌─────┬─────┬─────┬─────┬─────┐
  │  A  │  A  │  B  │  C  │  D  │   ← two seats say the same thing
  │ 2.0 │ 1.4 │     │     │     │
  └─────┴─────┴─────┴─────┴─────┘
         ↑ waste: seat 2 teaches nothing new
```

**What we do.** Keep **one** of those twins. Throw the other off the desk so a different page
(`E`) can sit there.

```
  Desk after
  ┌─────┬─────┬─────┬─────┬─────┐
  │  A  │  B  │  C  │  D  │  E  │   ← five different ideas
  │ 2.0 │     │     │     │     │
  └─────┴─────┴─────┴─────┴─────┘
```

**Why keep the 2.0 copy, not the 1.4 one?**

Search scores them **exactly the same** (same text → same vector). It cannot decide. We can:
this tool is for people upgrading **to 2.0**, so when we must pick one twin, we keep **2.0**.

Nothing magical. Same paragraph, we chose the edition that matches the product.

**Did this make recall jump?** Mostly no — and that is fine.

| | meaning |
|---|---|
| **31 → 0** | How many top-5 seats were wasted on twins. **This is the real win.** |
| recall 0.495 → 0.516 | Slightly more questions got a *useful* 5th page. Small. |
| absents still 22 | Pages that were never found are still never found. Twin collapse does not search harder; it only stops photocopies. |

So: you did **not** “find more books in the library.” You stopped putting two copies of the
same book on a five-book desk.

**Still on the shelf: both 1.4 and 2.0.** We did not delete 1.4 from the corpus. Search can
still return a 1.4-only page when that is the right hit. We only collapse when **both**
versions of the *same* paragraph show up together.

**Code.** Logic lives in `rag/dedup.py`. It runs automatically. Turn it off with
`dedupe=False` if you want to re-measure the old “double seats” behaviour.

---

### R7.2 Hybrid BM25 (`D67`) — search by meaning *and* by exact words

**Plain job.** Two librarians, then one merged shortlist.

| librarian | good at | weak at |
|---|---|---|
| **Dense** (vectors in Qdrant) | “pages that *mean* something like this” | exact API / error strings |
| **BM25** (keyword index on `chunks.jsonl`) | “pages that *contain these words*” | paraphrase / soft wording |

A stuck developer types `engine.table_names()` or a warning string. Dense may miss; BM25 often
hits. Hybrid runs **both**, merges the ranked lists, then you take the top pages for the desk.

**How the merge works — and what RRF is.**

You now have **two ranked lists** of the same library (dense’s top pages, BM25’s top pages).
You need **one** ordered shortlist. **RRF** = Reciprocal Rank Fusion = the recipe we use to
merge them.

Nothing neural. No second embedding. For each page that appears on either list, add up points
from its ranks, then sort by total:

```
  points from dense  =  1 / (kd + rank_in_dense_list)
  points from BM25   =  1 / (kb + rank_in_bm25_list)
  final score        =  those two added together
```

**Tiny worked example.** Page X is #1 for dense and #10 for BM25. Page Y is missing from dense
but #1 for BM25. With `kd=25`, `kb=90`:

```
  X:  1/(25+1) + 1/(90+10)  =  1/26 + 1/100  ≈ 0.038 + 0.010  = 0.048
  Y:  0        + 1/(90+1)   =  0     + 1/91  ≈ 0.011
  → X ranks above Y in the merged list
```

A page that both librarians like rises. A page only one likes can still enter — that is how
hybrid pulls in keyword hits dense missed.

**`kd` and `kb` are the numbers in that formula** — **not** “top-k” like `DEFAULT_K = 5`.

| name | who it belongs to | what ships |
|---|---|---|
| **`kd`** | dense (d = dense) | **25** |
| **`kb`** | BM25 (b = BM25 / “bag of words”) | **90** |

**Smaller number → louder vote.** Rank-1 dense with `kd=25` gets `1/26 ≈ 0.038`. Rank-1 BM25
with `kb=90` gets `1/91 ≈ 0.011`. Same first place, dense contributes ~3× more. That is what
“dense-heavy” means — not a separate model.

**Why not the same number for both?** Equal merge (`k=60` each) raised the average but
**broke five** questions dense already had right. Shipped pair (`25` / `90`) was the strongest
BM25 help we could take **with zero regressions**.

**What RRF is not.** Averaging the raw similarity scores from Qdrant and BM25 (those scores
live on different scales and do not mix cleanly). RRF only uses **rank position** — 1st, 2nd,
3rd — so the two lists stay comparable.

**What we measured** (after twin collapse):

| | dense only | + hybrid |
|---|---|---|
| recall@5 (on all **100**) | 0.52 | **0.63** |
| answers missing from top-20 | 22 | **17** |
| vs **50-item** baseline | 2↑ 0↓ | **6↑ 0↓** (p = 0.031) |

**Why “50” when the golden set is 100?** Two different jobs, two files:

| | what | count |
|---|---|---|
| **Golden set** (`golden.json`) | every question we score today | **100** |
| **Baseline artifact** (`baseline-phase1.json`) | the frozen Phase-1 *before* picture Phase 3 compares against | **50** |

We doubled the set to 100 later (`D65`). We **did not** replace the baseline file. Phase 3
judges each change with a **paired** test: for the same 50 questions, did this lever flip any
from miss → hit (`↑` fixed) or hit → miss (`↓` broken)? Swap the ruler mid-project and every
later row becomes two unpaired averages — you cannot say “we fixed six.” Proven: scoring
today’s system against that saved 50 still gives a clean paired table (`D61` / `D65`).

So the table above mixes both on purpose:

- **0.52 → 0.63** = how good search is on the full **100**
- **6↑ 0↓** = among the original **50**, hybrid fixed six and broke none

Named gain on the 100: Stack Overflow **0.38 → 0.48**. Fixed baseline ids (the six ↑):
`g024`, `g038`, `g044`, `g046`, `g047`, `g050`.

**What it is not.** A fix for pages that **do not exist** in the corpus (e.g. `has_table` —
zero chunks). Re-measure without it anytime: `--dense-only`.

**Code.** `rag/bm25.py`, `rag/hybrid.py`. Default on.

---

### R7.3 Seat-5 CE (`D68`) — a second opinion on *only* the last seat

**Plain job.** Hybrid already gave you a top-20. A **cross-encoder** (CE) re-reads
*question + one page* as a pair and scores that match more carefully (slower, pickier).

**Trap we measured and refused.** Re-sort all 20 by CE score: average recall went up a bit,
**ten** questions that used to hit in the top-5 **stopped hitting**. Pretty average, ugly paired
comparison. Do not ship that.

**What we ship instead.** Seats **1–4 stay frozen**. Look only at ranks **6–10**. If one of
those scores *clearly* better than seat 5 (margin ≥ **0.8**), swap it into seat 5. Nothing else
moves.

```
  Hybrid desk:   [1] [2] [3] [4] [5]     ranks 6–10 waiting outside
  After:         [1] [2] [3] [4] [7?]    only if 7 beats 5 by a wide margin
```

**What we measured:**

| | hybrid | + seat-5 CE |
|---|---|---|
| recall@5 | 0.63 | **0.64** |
| missing from top-20 | 17 | **17** (unchanged — expected) |
| vs **50-item** baseline | 6↑ 0↓ | **7↑ 0↓** (`g017` added) |

(Same 50-vs-100 split as R7.2 — recall row is on 100; ↑↓ is paired against the frozen 50.)

One clean flip. Small on purpose. Pages still outside the top 20 still cannot be helped.

**What it is not.** “We added a reranker” as if the whole list were re-sorted. Say **seat-5
promotion**, and say the full sort was rejected.

**Code.** `rag/rerank.py` (`BAAI/bge-reranker-base`). `--no-rerank` = hybrid only.

---

### R7.4 Sphinx strip (`D69`) — clean the markup? Tried. Made it worse. Reverted.

**Plain job we hoped for.** Docs are written `:class:\`_orm.Session\``. You type `Session`.
Strip the Sphinx wrapping before search so both sides say `Session`.

**What happened.**

| try | result |
|---|---|
| Strip for BM25 only | Almost no change; still **17** absents |
| Strip, re-embed everything, re-index | recall@5 **0.64 → 0.58**; **2** baseline hits broken (`g008`, `g013`) |

Two missing pages crept into the top-20; the top-5 got worse overall. Cleaning did **not**
help the model “see more” in a useful way — it also dropped path cues like `_orm` / `_engine`
that dense search had been using.

**So we did not ship it.** Embed + BM25 stay on **raw** docs text. `rag/textnorm.py` stays in
the repo with tests so the next sitting does not “cleverly” re-try a known bad idea.

**What about “fix chunking”?** The remaining **17** absents are mostly not mid-cut chunks
(`D56`). Named example: `g042` (*I assigned comment.issue = issue and Comment never
INSERTed*) shares **0 of 8** content words with its cascade answer page — wrong vocabulary,
not a severed listing. Re-cutting boundaries might still help citations someday; it is not
why those 17 are missing from search.

---

### R7.5 Boundary re-chunking (`D70`) — rejected by *asking the right 17 pages*

**The lever, in plain words.** The chunker cuts each documentation page into pieces. Sometimes
it cuts badly — a piece ends *"the steps are as follows:"* and the steps are in the next piece.
`D56` counted it: **10.7%** of the 3284 pieces do not stand on their own, and **6.3%** lose
their content outright. The ROADMAP said *fix the chunking* from the very beginning.

**Why we did not.** Look at *which* pages that 10.7% is costing us.

There are **17 questions** whose answer page never appears in the top 20 at all. Not ranked
low — **absent**. Those are the only questions re-chunking could possibly help, because the
reranker already handles "in the list but too far down," and nothing can rank a page that
was never in the list.

So: are the 17 absents' answer pages the broken ones?

```
their 30 answer chunks              broken?      whole corpus
  ends "…as follows:"                  0             4.1%
  opens "The above example…"           0             6.9%
  cut inside a code listing            1             0.2% of cuts
```

**Zero and zero and one.** But that alone proves nothing — three regexes that never fire would
print the same thing. **The control is the result:**

```
the 74 questions search DOES find:  2 of their 123 answer chunks are broken = 2%
the 17 it misses:                   1 of their  30 answer chunks = 3%
```

**Same rate.** Broken chunks sit behind the questions that work just as often as behind the
questions that fail. Whatever is separating found from missed, **it is not chunk quality.**

**The one hit, opened rather than counted.** `g113`'s chunk `c02823` was flagged for the
code-listing cut. Reading it: the chunk ends on a **finished** example (`{stop}<...>`), and the
next chunk starts a *separate* `>>> session.rollback()` snippet. Nothing was cut in half. The
detector fires on "indented code on both sides of the cut," and here the listing was already
over. **A detector that flags 1 in 30 has to have its hit read, or you are trusting a regex.**

**What this is NOT saying.** Not that the chunker is fine — `D56` still stands, and `c00138`'s
content is still gone from every chunk. Not that boundary work is dead forever: a code block cut
in half is bad for the **answer the model writes** from it, which is Phase 4's subject. It says
one thing: **re-chunking will not find those 17 pages.**

**The cheap part, and the lesson.** `D69` spent a full re-embed (and a 6-point recall drop) to
learn the same shape of answer. This one cost a single command over rows the scorer already
had. **Survey the failures before paying for the fix** — and had `--absents` existed a day
earlier, `D69` would have been rejected on paper first.

**Code.** `rag/score.py --absents`, calling `rag/chunk.py`'s **own** detectors, with a test that
fails if the scorer ever grows a private copy of one.

---

### R7.6 What is left — and what needs the lab

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

- Phase 3 shipped **twin collapse, hybrid BM25, seat-5 CE**; **Sphinx strip and boundary
  re-chunking were both rejected** with numbers (`D69`, `D70`).
- Full CE reorder looked better on the average and **broke ten** items — that is why seat-5
  only shipped.
- Absents are not a markup problem and not a chunk-boundary problem — measured, with the
  found items as the control: **2% of their answer chunks are broken too**.
- Next sitting is Phase 4 on the lab, not another embed experiment on the Mac.

## Do not say

- “We added a reranker” (without saying seat-5 promotion and the rejected full sort).
- “Chunking is next.” Both halves of that lever are closed: strip measured and reverted
  (`D69`), boundaries surveyed and rejected (`D70`). Phase 3's retrieval story is finished.
- “The chunker is fine.” It is not — `D56`'s 10.7% / 6.3% stands. It just isn't why the 17
  are missing.
- “0.64 on the lab, 0.64 on the Mac” as two systems — one scorecard; lab confirms.

---

## Where the rest lives

| | |
|---|---|
| [`../phases/PHASE-3.md`](../phases/PHASE-3.md) | step-by-step plan + measured tables |
| [`09-DECISIONS.md`](09-DECISIONS.md) | `D66`–`D70` full entries |
| [`14-MEASURE.md`](14-MEASURE.md) | §R6 — the scorecard Phase 3 improved from |
| [`../logs/HANDOFF.md`](../logs/HANDOFF.md) | Round 13 — lab start for Phase 4 |
| [`../phases/ROADMAP.md`](../phases/ROADMAP.md) | Phase 4 judge / faithfulness arc |
