# Measure — study notes

Part of [`sqlalchemy-upgrade-agent`](../README.md). **§R6**, continuing the `R` run that
[`10-RETRIEVAL.md`](10-RETRIEVAL.md) starts at §R1 and [`13-VERIFICATION.md`](13-VERIFICATION.md)
closed Phase 1 at §R5. The `R` is for RAG, not Retrieval (`09-DECISIONS.md` **D47**).

**Why this is a fifth file.** §R4 in [`12-EVALUATION.md`](12-EVALUATION.md) teaches *how* to
measure — two report cards, recall vs rank, why a human fills the answer key, the pin trap.
**§R6 is the Phase 2 result of that measurement:** the 50-item golden baseline, the 100-item
run (and the provenance split), the refusal runs, and the nine questions marked
`answerable: false`. That is a different subject from
Sitting 4 (still on the 19 probe answers) and a different skill from Sitting 5 (defending out
loud). Stuffing it into `12` made Phase 1 look unfinished; stuffing it into `13` would mix
interview rehearsal with a scorecard. The split rule's condition is met (`D64`).

> **This is not Sitting 6 of Phase 1.** Phase 1 ended at §R5. Read this after
> [`../phases/PHASE-2.md`](../phases/PHASE-2.md) has a finished `golden.json`, or after you have
> run `uv run python -m rag.score` yourself. Every number below was measured 2026-08-20 against
> the hand-verified set.

---

## If you are lost — three numbers, not one grade

Forget the section titles for half a page. Phase 2 produced three facts that must stay apart:

```
                                       50-item set (the baseline)   100-item set (2026-08-21)
  1. Did the right page reach          recall@5 = 0.51              recall@5 = 0.49
     the prompt?                       0.73 migration_guide         0.73 migration_guide
                                       0.41 breakages               0.38 stackoverflow ← quote this
  2. Did the model refuse when         3/3 unanswerable declined    7/9 declined, 2 FABRICATED
     it should?                        7 refused WITH the page      13 refused WITH the page
  3. Is the answer even on             has_table / orm.relation /   9 items; g065 reason was
     the shelf?                        with_labels = 0 of 3284      wrong, ceiling kept (spot-check)
```

**What did *not* happen.** Nobody said “the system is 51% good.” That figure averages
provenance groups that behave nothing alike (`D63`), and it ignores the generation defects that
look like retrieval successes on report card A. **And do not quote the 50-item refusal row as a
clean pass** — it read `0/3 fabricated` because three unanswerable items cannot measure a
fabrication rate; nine of them found two.

**The rest of §R6 in one breath:**

| section | plain job |
|---|---|
| **R6.0** | two jobs people mix up — verifying the key vs scoring search |
| **R6.1** | the baseline — and why not to quote `0.51` alone |
| **R6.2** | refusals — the 15 points recall cannot see, two fabrications, and a determinism claim that did not hold |
| **R6.3** | the 9 `answerable: false` items — what that word does not mean, and the one that looks mislabelled |

---

## §R6 — The Phase 2 scorecard

### R6.0 Verifying the key vs scoring search — not the same job

People ask two related things that get mashed together:

1. *“Doesn’t the system just check whether the right words are in the chunk?”*
2. *“I didn’t deep-read all 50 the first time — so verification is basically the same shortcut,
   right?”*

**Honest answer to (2): the first 50 were mostly a light check, and that was only safe because
the answers were already measured elsewhere.** Of the 50 human notes, almost all say
*approved*; only a couple say *opened* the `.rst`. **34 of 50** are `breakages` items whose
fix was already proven on real 2.0.51 in Phase 0 (`BREAKAGES.md`, many marked `FIX OK`).
Verification there was closer to: *does this chunk point at the section we already know is the
fix?* — not a fresh SQLAlchemy deep-dive per question. The 16 `migration_guide` items were
the same shape: the question was harvested from a heading you could match to a chunk.

That is **not** the same as what `rag.score` does. And it is **not** enough, alone, for the
SO/GitHub drafts — those have **no** Phase 0 measurement behind them.

```
  WHAT YOU DID ON THE FIRST 50 (practical)              WHAT rag.score DOES (always)
  ──────────────────────────────────────────            ────────────────────────────
  Often: confirm the chunk is about the same            Look up the chunk ids you stored
         API / section you already knew from            (e.g. c01598). Are they in top-k?
         BREAKAGES or the migration heading.            Yes/no. No reading. No keywords.
  Sometimes: open the .rst briefly.
  Rarely: re-derive the fix from scratch.

  WHAT THE NEW SO/GITHUB DRAFTS NEED (minimum)
  ────────────────────────────────────────────
  Open `uv run python -m rag.golden --show <chunk>`.
  Ask only: “is this page about THIS stuck-developer
  question?” Keep / replace / set answerable:false.
  You still do not memorise 100 answers.
```

**So: scoring never “checks the right words.”** It checks **ids you already recorded**. If you
recorded the wrong chunk, recall can look great or terrible for the wrong reason — the script
will not save you.

**And: “right words exist” is a weak verify.** It is how you get fooled (`relation` inside
`relationship`, a BM25 hit that says `execute` but never shows `text()`). For breakages-backed
items the risk was low because Phase 0 already knew the fix. For SO/GitHub drafts the risk is
the whole point of `D06` — BM25 proposed the chunks; **keyword search is exactly what proposed
them**, so “I see the word” is circular. The minimum bar is: open `--show`, decide if the
*page* answers the *question*, then mark human. Drop the item if you cannot tell in a minute.

**You do not need to memorise all 100 for interviews.** You need a once-per-draft pass at that
minimum bar (or delete the draft). Defend the *rule* later, not every `g0xx`.

**And this is what closed on 2026-08-21.** Every item in `golden.json` carries
`verified_by: "human"`. The notes on `g051`–`g121` had recorded Claude batch stamps; Viraj
closed §H by **spot-checking ten, then verified** (sheet in `PHASE-2.md` / §H CLOSED). The mechanical
half was already checked hard —
`tools/audit_golden_fullbar.py` resolves every chunk, fetches every source page live, and runs
the executable claims on real 2.0.51, 100 PASS. **The half in the picture above — "is this page
about THIS question?" — is what the spot-check sampled.** It does not claim he read all 50 of
the second tranche; it claims ten held (one note fixed) and he verified.

**Named example.** For `g002` (*from_self blew up*), the key was already BREAKAGES #12. Checking
meant confirming `c01598`/`c01599` are the migration section for `from_self` — light, because
the fix was already known. Scoring later only asks whether those ids landed in top-k.

### R6.1 The baseline — and the number not to quote

The first tranche was finished on 2026-08-20: **50 questions, all verified by hand.** One command
scored them, and that run — saved as `deliverables/baseline-phase1.json` — is **the** Phase 1
baseline every Phase 3 change gets compared against. It is still the baseline today.

**A second tranche has since landed and is measured further down** (*"The 100-item run"*, end of
this section). It is kept separate here on purpose: the baseline is an artifact you compare
against later, and swapping the ruler halfway through is how a paired comparison stops meaning
anything.

```
# summary of: uv run python -m rag.score. The command is ENV in
#   tools/check_runnable.py because corpus/chunks.jsonl is generated and
#   gitignored (D11) and the live path needs Qdrant.
ALL ITEMS  —  50 items, 47 answerable
  recall@k   @1=0.34  @3=0.43  @5=0.51  @10=0.68  @20=0.81
  MRR        0.434
  recall@5    0.51  ±0.137  (95%, Wilson)
  median rank when found  2.5   not in top-20: 9
  slots lost to duplicates in top-5: 20
```

#### What each line is saying (read this before the floats)

This block is **report card A only** — did a page that holds the answer show up in the ranked
pile? It is not grading the chatbot’s paragraph. The three unanswerable items are out of the
47: there is no answer page to hit, so they cannot score a recall win by construction.

Picture for one question:

```
Question  →  search returns a ranked pile of chunks
                #1  #2  #3  #4  #5  …  #20

Hit = “one of the answer_chunks we verified is somewhere in that pile”
```

`DEFAULT_K = 5` is what the chatbot actually gets pasted into the prompt. The scorer still
looks down to 20 so you can see *how far* the answer sat when it missed the cut.

| line | plain English |
|---|---|
| **`50 items, 47 answerable`** | 50 golden questions; 3 are ceiling (`has_table`, `orm.relation`, `with_labels`). Recall uses the **47**. |
| **`recall@1 = 0.34`** | ~1 in 3: the **first** page already holds the answer. |
| **`recall@5 = 0.51`** | ~half: the answer is somewhere in the **five pages the model sees**. This is “does shipping retrieval work?” |
| **`recall@20 = 0.81`** | ~4 in 5: the answer is somewhere in the **top 20**, even if not in the prompt yet. This is “could a deeper look / rerank still help?” |
| **`MRR 0.434`** | Cares about **how high** the first hit sat. Rank 1 → 1.0, rank 2 → 0.5, rank 4 → 0.25, never found → 0; then average. Recall only asks yes/no in top-k; MRR punishes “found but buried.” (Same idea as §R4.2’s `backref` at 6 → `1÷6`.) |
| **`±0.137 (95%, Wilson)`** | With only 47 questions, the true rate can sit in a wide band. That is why Phase 3 reports **which items flipped**, not “we gained 0.02.” |
| **`median rank when found 2.5`** | When search *does* find the answer, it is usually near the top (around 2nd–3rd). Failures are often **missing**, not “rank 18.” |
| **`not in top-20: 9`** | 9 of 47 never appear even in 20 results. A **reranker cannot fix those** — it only reorders what was already retrieved. Needs recall-side work (hybrid / keyword). |
| **`slots lost to duplicates in top-5: 20`** | Across the set, 20 of the top-5 seats are wasted on a **twin** of a page already in the list (same text from 1.4 and from 2.0). See “free win” below. |

**Memorize the jobs, not every float:** **@5 = what ships**, **@20 = ceiling for reorder**,
**9 absent = hybrid’s job**, **20 duplicate slots = free win**.

#### What “20 duplicate slots = free win” means

The chatbot only gets **five** pages (`DEFAULT_K = 5`). Each of those five seats is a chance to
show a *different* useful page. Sometimes search fills two seats with the **same words twice** —
once from the 1.4 docs and once from the 2.0 docs (`D38`, `D58`). Vectors for those twins are
byte-identical, so no ranker can prefer one; both look equally “close.”

```
WITHOUT dedupe (Phase 1–2)                 WITH dedupe (`D66`, ships now)
  seat 1: page A (2.0 copy)                  seat 1: page A (prefer 2.0.51)
  seat 2: page A again (1.4 twin)  ← waste   seat 2: page B   ← was crowded out before
  seat 3: page B                             seat 3: page C
  seat 4: page C                             seat 4: page D
  seat 5: page D                             seat 5: page E
```

**“20”** (50-item) / **“31”** (100-item) counted those wasted seats. **`D66` collected the free
win on 2026-08-21:** seats **31 → 0**, recall@5 **0.495 → 0.516**, **2 fixed / 0 broken** vs the
50-item baseline. Absents from top-20 stayed **22** — dedupe cannot invent a page.

**“Free win”** meant: cheap relative to hybrid/reranker — a bookkeeping filter, not a new model.
It is no longer a future lever; it is the first Phase 3 row in `ROADMAP.md` / `PHASE-3.md`.

**Hybrid (`D67`) is the second row.** Dense + BM25 fused with dense-heavy RRF (`kd=25`, `kb=90`):
recall@5 **0.52 → 0.63**, absents **22 → 17**, stackoverflow **0.38 → 0.48**, and the first
paired result that clears `D61` — **6 fixed / 0 broken**, McNemar p = 0.031 against the saved
50. Equal-k fusion was measured and rejected (broke five). Details in `PHASE-3.md` Step 2.

**Read the headline as a sentence.** For half the questions, the page holding the answer never
reached the prompt. `DEFAULT_K = 5`, so the model was handed five pages, and for 23 of 47
answerable questions none of them was the right one. The model was not being stupid on those —
it was never shown the answer.

#### The number not to quote, and why

`0.51` is the average of two groups that behave nothing alike. Split by where the question came
from:

| provenance | n | median overlap with top-1 | recall@5 |
|---|---|---|---|
| `migration_guide` | 16 | 0.64 | **0.73** |
| `breakages` | 34 | 0.43 | **0.41** |

**That gap — 32 points — is bigger than anything Phase 3 is expected to buy.** So which half you
quote matters more than the improvement you are about to make.

#### What “median overlap with top-1” means

Break the column name into three pieces. Nothing here is a model score — it is a word-counting
check that asks: *did the asker already use the documentation’s vocabulary?*

| piece | meaning |
|---|---|
| **top-1** | the **first** chunk search returned for that question (rank 1) — not the verified answer chunk, not the top-5. Just “what came back first.” |
| **overlap** | of the question’s **content words** (drop `the`, `a`, `is`, `how`, …), what **fraction** already appear in that top-1 chunk? |
| **median** | do that for every question in the group, then take the middle value — so one weird question does not drag the number |

Worked arithmetic on the two extremes of the set (`g034` and `g042` below):

```
overlap = (how many content words from the question also sit in top-1)
          ÷ (how many content words the question had)

g034: 6 of 6 content words already in top-1  →  overlap = 1.00
g042: 0 of 7 content words already in top-1  →  overlap = 0.00
```

**0.64 vs 0.43 in the table** means: for a typical `migration_guide` question, about **two
thirds** of its real words were already on the first page search returned; for a typical
`breakages` question, under **half**. High overlap = the question was already speaking the
docs’ language (leakier, easier for meaning-search). Low overlap = symptom wording
(`comment.issue = … never INSERTed`) against cause wording (`cascade_backrefs`) — harder.

**What it is not.** It is not recall. It is not “how good is the answer.” It does not care
whether top-1 is the *correct* page — only how much the question’s wording already matches
whatever came back first. The recall@5 column next to it is the separate yes/no: did a
verified answer chunk land in the top 5?

Side by side, the two real extremes of the set — `g034` and `g042`:

```
g034   provenance: migration_guide          overlap 6/6 = 1.00     rank 1
  "Query.select_entity_from removed how do I select an entity from a subquery"
   content words:  entity  query  removed  select  select_entity_from  subquery
   in chunk c01601: entity  query  removed  select  select_entity_from  subquery
                    ^ every single one. The question is nearly the heading.

g042   provenance: breakages                overlap 0/7 = 0.00     NOT IN TOP 20
  "I assigned comment.issue = issue and the Comment never got INSERTed silent bug"
   content words:  assigned  bug  comment  inserted  issue  never  silent
   in top-1 chunk: (none)
   the answer is c02230, in orm/cascades.rst, and it was never retrieved.
```

**Look at what `g042` does not contain: the word `cascade_backrefs`.** That is the name of the
thing that broke — and the developer hitting it does not know that name, because **nothing was
raised.** They know `comment.issue = issue`, they know the row is missing, and those are the
words they type. The chunk that answers them is written in the vocabulary of the *cause*; the
question is written in the vocabulary of the *symptom*. Meaning-search is supposed to bridge
exactly that gap, and here it does not: zero shared words, and the answer never appears in
twenty results.

`g034` is the opposite in every respect. `select_entity_from` is a name you can only be holding
if you have already read the API that removed it, so the question arrives pre-loaded with the
documentation's own vocabulary — and the right chunk comes back first.

**Same corpus. Same retriever. Same `k`. Rank 1 versus not-found.** The only variable is whether
the asker already knew the words.

#### What this corrects

`D60` predicted this problem and **attached it to the wrong group.** It quarantined the
`breakages` items as the leaky ones, because the 19 probe questions had been written from
`BREAKAGES.md`'s keys and carried the corpus's vocabulary. Measured on the finished set, the
`breakages` items are the **hardest** group and `migration_guide` is the leaky one — at **0.64**,
leakier than the 0.57 `D60` measured on the probe questions it was worried about.

**The thing that leaks is phrasing, not provenance.** `D60`'s own best evidence already said so
and it was not read that way at the time: chunk `c01542` comes back at **rank 1** for the tidy
phrasing and is **not in the top 20 at all** for the developer phrasing. Same question, same
answer chunk, and the only thing that changed was the words.

`D63` records the correction. `D60` is not reversed — the mechanism it chose, *report every
number with and without a provenance group*, is exactly what made this visible. Only the label
was wrong.

**So: `0.41` is the number that describes the shipped system** for a developer pasting an error
message. `0.51` is the honest average, and it needs the split said out loud beside it.

#### Three levers this run names for Phase 3

Not "improve retrieval." Three separate things, with the number that sizes each:

- **9 of 47 answerable items are not in the top 20 at all.** Not ranked low — **absent**. A
  reranker reorders a list it is handed; it can do nothing for these. Only recall-side work
  (keyword search, chunking) can reach them. This is the ceiling on reranking.
- **20 top-5 slots across the 50 items are lost to duplicates** — a cross-version twin taking a
  second seat that a different page could have used (`D58`). That is the “free win” above:
  dedupe at retrieval, no new model.
- **Median rank when found is 2.5.** When search works, it works well. The failure is **binary,
  not gradual** — the answer is either near the top or nowhere. That is why `D61` reports flipped
  items rather than a moving average: there is no gentle slope here to nudge.

#### The 100-item run — and the group that scores worst is the real one

Fifty more questions were added on 2026-08-21, and unlike the first fifty **they were not written
here**: 25 Stack Overflow titles and 25 `sqlalchemy/sqlalchemy` GitHub discussion titles, kept
verbatim, typos included. Scored on 2026-08-21:

```
# summary of: uv run python -m rag.score, 2026-08-21, 100-item set. ENV in
#   check_runnable: needs corpus/chunks.jsonl (gitignored, D11) and Qdrant.
ALL ITEMS  —  100 items, 91 answerable
  recall@k   @1=0.26  @3=0.38  @5=0.49  @10=0.65  @20=0.76
  MRR        0.373
  recall@5    0.49  ±0.101  (95%, Wilson)
  median rank when found  3   not in top-20: 22
  slots lost to duplicates in top-5: 31
```

**The headline hardly moved. The band is what doubling bought:** ±0.137 on 47 answerable items
became **±0.101** on 91. In plain terms — before, a Phase 3 change had to move recall by roughly
27 points before you could tell it apart from luck; now it is about 20. That is the whole return
on the hours, and it was predicted before the work started, not discovered after.

The interesting part is underneath the average:

| provenance | who phrased the question | n answerable | recall@5 | never in top-20 |
|---|---|---|---|---|
| `migration_guide` | this repo, in the docs' own words | 15 | **0.73** | 0 |
| `github` | real developers, in an issue thread | 23 | 0.57 | 4 |
| `breakages` | this repo, *imitating* a stuck developer | 32 | 0.41 | 9 |
| **`stackoverflow`** | **real developers, stuck** | **21** | **0.38** | **9** |

**Read the two middle rows against each other.** `breakages` was the repo's attempt to write like
a developer in trouble, and `D63` already showed it is harder than the guide-shaped questions.
Now there are real questions to compare it against, and **the imitation scored higher than the
real thing** — 0.41 against 0.38. Not by much, and n is small on both, but it points the same way
`D63` did: the closer a question gets to how someone actually types, the worse dense retrieval
does on it.

**Nine of the 21 answerable Stack Overflow items never appear in the top 20 at all** — the same
absent-not-buried failure `g042` shows. A reranker cannot reach those, whatever it costs.

**What this is not.** It is not "the system got worse" — `0.51` → `0.49` is inside the band, and
the paired check proves nothing regressed:

```
# summary of: uv run python -m rag.score --baseline deliverables/baseline-phase1.json
PAIRED against baseline  (recall@5)
  fixed    0  —
  broken   0  —
  exact McNemar p = 1.000  — NOT distinguishable from noise
```

Zero items flipped in either direction against the saved 50-item run. The retriever is unchanged
and deterministic; the average dropped because **harder questions were added**, not because
anything got worse. That is the difference between a score falling and a ruler getting honest.

**And one correction, because it is the exact error this file exists to catch.** `ROADMAP.md` and
`CLAUDE.md` quoted **`0.51 ±0.131`** for weeks. The scorer prints **±0.137**, and recomputing
Wilson from the saved baseline rows gives ±0.137. The `±0.131` is the band for **n = 50** — but
recall is computed over the **47 answerable** items, because the three unanswerable ones have no
answer page to hit. A hand-typed number, off by a group of three, repeated in two files, with a
green CI the whole time.

### R6.2 Refusals — and the 15 points that recall does not see

`--refusals` is the half of the score that needs the model to actually answer. Run against the
same 50 items:

```
# summary of: uv run python -m rag.score --refusals, 2026-08-20. ENV in
#   check_runnable: needs Ollama, corpus/chunks.jsonl and Qdrant.
REFUSALS  —  generation, at k=5 (D62; not averaged into recall)
  unanswerable items                3
    refused — correct               3/3  (100%)
    answered — FABRICATED           0/3  (0%)
  answerable items                  47
    refused — over-refusal          24/47  (51%)
      with the answer IN the prompt   7   generation defect (the Q18/Q19 class)
      with the answer absent         17   honest — retrieval never supplied it
```

**The unanswerable items are a clean pass.** All three were declined, none was answered, and that
includes `has_table` — the question §R2 proved can never be answered because the string is in
**zero** of the 3284 chunks. The system says so instead of inventing a signature. That is `D62`
earning its place: at the retrieval level those three items score `recall = 0` by construction and
measure nothing at all.

#### The number that is not in the recall table

Put the two halves together for the 47 answerable questions and a third figure falls out that
neither half reports on its own:

```
47 answerable questions
│
├── 24  the answer WAS retrieved into the prompt      (recall@5 = 0.51)
│   ├── 17  answered            ✓  the system worked, end to end
│   └──  7  REFUSED anyway      ✗  generation defect — it had the page and declined
│
└── 23  the answer was NOT retrieved
    ├── 17  refused             ✓  honest — nothing relevant was there to use
    └──  6  answered anyway     ?  answered without the verified page in the prompt
```

**17 of 47 is 0.36.** Recall says `0.51`; end to end the system produced an answer with the right
page in front of it on **36%** of the questions. **Retrieval's 0.51 is a ceiling that generation
then loses another 15 points of** — and no retrieval metric can see that, because from retrieval's
side those 7 items are successes. They are the reason `D62` refused to let refusal accuracy be
folded into recall.

#### Why the split matters more than the total

`24 of 47 refused` on its own is a useless number — it is two unrelated bugs added together:

| | what happened | whose problem | which phase |
|---|---|---|---|
| **7 items** | the answer chunk was in the prompt and it declined anyway | **generation** | Phase 4 |
| **17 items** | nothing relevant was retrieved, so it declined | **retrieval** | Phase 3 |

Hybrid search and a reranker — the whole of Phase 3 — can only move the second row. **If Phase 3
worked perfectly and fixed all 17, the 7 would still be there**, because those questions already
had their answer and the model still would not use it. Reporting one "51% refusal rate" would hide
that completely, and the obvious next move would be to weaken the refusal clause — which `D43`
already measured as the thing that makes the model invent API signatures.

#### This is bigger than Phase 1 thought

Phase 1 left this open as **two questions**, Q18 and Q19, and called them stubborn: both refuse at
`k=10` with their chunks in the prompt — Q19 has three of them, at positions 6, 7 and 8 — across
all four prompt wordings. On the golden set it is **seven**: `g006`, `g008`, `g013`, `g021`,
`g029`, `g048`, `g049`. All seven were confirmed against the separate retrieval run to have had
their answer chunk at rank ≤ 5.

**Seven named items is a different kind of evidence from two.** Two questions is an anecdote that
invites "your prompt is slightly off." Seven, on questions harvested independently of the prompt
work, is a **measured property of the generation step** — and it is Phase 4's, not Phase 3's.

#### The one cell to keep watching

The **6** that answered *without* the verified page in the prompt (**11** on the 100-item run
below) are the least understood cell in the table, and this file will not pretend otherwise. They may have answered correctly from an
adjacent page, or partially, or they may have invented. **Retrieval cannot tell you and neither
can a refusal count** — deciding it means reading six answers against real 2.0.51, which is
exactly the judgement `D06` reserves for a human and exactly what Phase 4 exists to grade. It is
recorded here as an open cell rather than quietly averaged into a pass.

#### The same run on 100 items — and the clean pass stopped being clean

`--refusals` was re-run against the finished 100 on 2026-08-21. **Two things changed, and the
first one is the serious one.**

```
# summary of: uv run python -m rag.score --refusals, 2026-08-21, 100-item set.
#   ENV in check_runnable: needs Ollama, corpus/chunks.jsonl and Qdrant.
REFUSALS  —  generation, at k=5 (D62; not averaged into recall)
  unanswerable items                9
    refused — correct               7/9  (78%)
    answered — FABRICATED           2/9  (22%)   g056, g065
  answerable items                  91
    refused — over-refusal          48/91  (53%)
      with the answer IN the prompt  13   generation defect (the Q18/Q19 class)
      with the answer absent         35   honest — retrieval never supplied it
```

**On 50 items this cell read `0/3 fabricated` and was quoted as a clean pass. It is now `2/9`.**
Nothing about the model or the prompt changed; the questions got harder. **Three unanswerable
items were never enough to measure a fabrication rate** — `D62` asked for at least three, and
nine is not many either.

**Look at what it invented, because "fabrication" is a word that needs an artifact.** `g065`
asked how to create a table and a view in one migration. The system answered with a confident
Alembic script:

```python
def upgrade():
    op.create_table('new_table', sa.Column('id', sa.Integer, primary_key=True), …)
    op.create_view('new_view', 'SELECT id, name FROM new_table')   # <- does not exist

def downgrade():
    op.drop_view('new_view')                                        # <- does not exist
    op.drop_table('new_table')
```

Checked rather than assumed, against real Alembic:

```
# summary of: uv run --no-project --with alembic python -c "…hasattr(Operations, …)"
alembic 1.19.1
create_view exists: False
drop_view exists: False
create_table exists: True
```

**Two of the four operations in that answer are invented, and they sit next to two real ones.**
That is the shape fabrication actually takes here — not gibberish, a plausible script where the
made-up lines are indistinguishable from the working ones unless you already know the API. It
cited no source for the code block, which is the tell a reader could have caught.

`g056` is the milder kind. The developer asked about the **`Query` property** — Flask-SQLAlchemy's
`Model.query`, from `scoped_session.query_property()`. The system answered with an unrelated
Python `@property` that runs a query inside it, and hedged at the end: *"The sources do not cover
how to migrate this property to SQLAlchemy 2.0."* **That hedge is why the detector is a prefix
test and not a substring search** — the sentence contains the refusal string, the answer is not a
refusal, and a substring test would have scored this fabrication as a correct decline.

**And `g065` is the item §R6.3 says may be mislabelled — both things are true at once.** Its
stated reason ("0 narrative chunks") is measurably wrong; its verdict (the system should have
refused) is vindicated by the invented `op.create_view`. **The label decides whether an answer
counts as a fabrication**, which is the sharpest argument for `D06` in the file: get the label
wrong and this number moves without the system changing at all.

#### The end-to-end figure, recomputed on 91 answerable items

```
91 answerable questions
│
├── 45  the answer WAS retrieved into the prompt      (recall@5 = 0.49)
│   ├── 32  answered            ✓  the system worked, end to end
│   └── 13  REFUSED anyway      ✗  generation defect — it had the page and declined
│
└── 46  the answer was NOT retrieved
    ├── 35  refused             ✓  honest
    └── 11  answered anyway     ?  answered without the verified page in the prompt
```

**32 of 91 is 0.35**, against a recall of `0.49`. The same ~15-point gap the 50-item run found,
holding at twice the size: **retrieval's number is a ceiling and generation loses a chunk of it**,
invisible to every retrieval metric. The open cell grew from 6 items to **11** — still unread,
still a human's call (`D06`), still Phase 4's.

#### `D54` said refusal behaviour is deterministic. Across days, it is not

The 08-20 run named seven items that refused with the answer in the prompt: `g006`, `g008`,
`g013`, `g021`, **`g029`**, `g048`, `g049`. The 08-21 run names, from the same fifty: `g006`,
`g008`, `g013`, **`g015`**, `g021`, `g048`, `g049`. **Two flipped, in opposite directions.**

Re-asked directly, today, both reproduce today's answer:

```
# summary of: uv run python -m rag.ask "<the g029 question>", then the g015 question, 2026-08-21
g029  "insert().values() keyword constructor style for update/delete broke"
      -> "The keyword constructor style for `insert().values()` was broken in the migration…"  ANSWERED
g015  "row['id'] TypeError on result rows after upgrade, how do I get mapping access"
      -> "The sources do not answer this."                                                     REFUSED
```

**What was ruled out.** `TEMPERATURE = 0.0` in `rag/ask.py`, and `git log` says that file has not
changed since `b6320c4` — the commit that introduced `--refusals` and produced the 08-20 run. The
index did not move either: the paired recall comparison is `0 fixed, 0 broken`. Same prompt, same
sources, same greedy decoding.

**What was not ruled out:** the model server. Greedy decoding is reproducible *within* a process,
and today's two runs agree with each other — it is across days and across processes that two of
seven moved. **So `D54`'s claim needs its scope stated: five runs in one sitting were unanimous,
which is a weaker statement than "deterministic."** It matters because a Phase 4 fix will be
judged by whether these items stop refusing, and a two-item drift is most of the effect anyone
would be looking for.

### R6.3 The questions with no answer — and what "unanswerable" does not mean

**Three of the first 50 golden items are marked `answerable: false`; the finished 100 carries 9.**
The first three are below and the six that arrived with the harvest have their own subsection. The word invites a wrong reading, so
start with what it is **not**.

**It does not mean the question has no answer in the world.** For two of the three, this repo
already measured the fix against real 2.0.51. For the third, an answer exists in SQLAlchemy but
**this project has never recorded it** — so we do not invent one here (`D03`). They are *not*
all in `BREAKAGES.md`, and they were *not* all measured in Phase 0:

| item | the question | the answer, and where this repo verified it |
|---|---|---|
| `g001` | `engine.has_table()` no longer exists, what replaces it? | `inspect(engine).has_table("issues")` — `BREAKAGES.md` #6, marked `fix OK` on 2.0.51 |
| `g010` | `from sqlalchemy.orm import relation` fails — what replaces `orm.relation`? | `relationship()` — `BREAKAGES.md` #10, "old nickname deleted" |
| `g023` | `Query.with_labels()` disappeared, what replaces it? | **not recorded here.** `with_labels` is not one of `BREAKAGES.md`'s 23 entries, so this repo has never run it against 2.0.51 |

**The third row is deliberately blank, and the blank is the point.** `g001` and `g010` have
answers this project *measured*; `g023` has an answer that exists in SQLAlchemy and that nothing
in this repo has verified. Writing one in from memory would be the exact move `D03` exists to
forbid — ground truth here is measured, not recalled. It changes nothing about the item's status:
`with_labels` is in **0 of 3284 chunks** either way, so the system must refuse either way.

**It does not mean something broke, either.** Nothing failed here. No bug, no bad chunk, no
retrieval mistake.

`answerable: false` means exactly one thing: **the text that would answer it is not in this
corpus**, so no amount of search can produce it. The answer exists in the world; it does not exist
on the shelf the system is allowed to read.

#### Six more arrived with the second fifty — and one of them may be wrong

The harvested questions brought the count from 3 to **9**. The new six are a different species
from the first three: those were **API-reference ceilings** (`D07`/`D50` — the API reference is
generated from docstrings and was never in the `.rst` tree we fetched). These are **topic**
ceilings — questions about tooling next to SQLAlchemy rather than SQLAlchemy itself.

| item | asked on | why it was marked unanswerable | corpus hits, measured |
|---|---|---|---|
| `g056` | Stack Overflow | `query_property` is API-reference material | `query_property` → **0** of 3284 |
| `g067` | Stack Overflow | `SQLALCHEMY_SILENCE_UBER_WARNING` lives in `changelog_14`, excluded by `D07` | **0** of 3284 |
| `g075` | Stack Overflow | *"relation does not exist"* after `flask migrate` — a Postgres error and an Alembic workflow | `flask_migrate` → **0**; `relation ... does not exist` → **0** |
| `g093` | GitHub | *"How long will 1.4 be supported?"* — a support policy, not documentation | — |
| `g097` | GitHub | `AttributeError: no attribute _active_history` | `_active_history` → **0** |
| **`g065`** | Stack Overflow | *"Alembic"* — creating a table and a view in one migration | **see below** |

**`g065` did not hold up as written — and the spot-check fixed the note, not the ceiling.**
Its note said *"Unanswerable from THIS corpus (0 narrative chunks)"*. Grep the corpus for
`CREATE VIEW` and you get **2** — a duplicate pair, `c00484` (1.4) and `c02056` (2.0), and their
heading is not incidental:

```
doc/build/faq/metadata_schema.rst
  MetaData / Schema
    > Does SQLAlchemy support ALTER TABLE, CREATE VIEW, CREATE TRIGGER,
    > Schema Upgrade Functionality?

  "General ALTER support isn't present in SQLAlchemy directly. For special DDL
   on an ad-hoc basis, the :class:`.DDL` and related constructs can be used.
   See :ref:`metadata_ddl_toplevel` …"
```

**That is an FAQ entry whose title is the question.** Whether it *answers* the developer — who
wanted a table and a view in one Alembic migration — is a judgement: it says SQLAlchemy does not
do this directly, names `DDL` as the tool, and points at Alembic. On 2026-08-21 Viraj's
spot-check **kept `answerable: false`** (those chunks do not teach same-migration steps) and
**rewrote the reason** so it no longer claims zero chunks. §H CLOSED records the sheet.

**Why this mattered more than one item.** `g065` is marked `answerable: false`, so
`tools/audit_golden_fullbar.py` reports it `N/A` on both the docs and SQL checks and it lands in
the 100 PASS rollup **without anything being checked**. An unanswerable label is the one label an
audit cannot test — which is why `D06` put a human on the signature, and why this item was
spot-check #1.

**The cost of getting this wrong runs both ways.** Mark an answerable item unanswerable and you
have removed a question retrieval was supposed to pass; mark an unanswerable one answerable and
you punish the system for not finding a page that does not exist. Both quietly move the baseline.

#### The check is a `grep`, and it is decisive

This is the rare claim that needs no ranking, no embedding and no model. Either the string is in
the 3284 chunks or it is not:

```
# summary of: counted over corpus/chunks.jsonl with rag/probe.py's whole-symbol
#   matcher. ENV in check_runnable — chunks.jsonl is generated and gitignored (D11).
has_table        0 of 3284 chunks
with_labels      0 of 3284 chunks
orm.relation     0 of 3284 chunks

  control, to prove the counter works:
from_self        4 of 3284
backref         80 of 3284
```

**Zero is a different kind of fact from "ranked low".** `backref` sits at rank 6 — that is a
retrieval failure, and `DEFAULT_K = 5` is the lever (§R4.3). `has_table` is at no rank at all,
because there is no chunk to rank. **Phase 3 can move the first and cannot touch the second.**
That distinction is `D45`, and it is the reason the count is computed rather than eyeballed.

#### So what went wrong? Nothing — and this was chosen on purpose

The absence traces to one decision, `D07`: the corpus is the **narrative** documentation from
SQLAlchemy's own git tags — `orm/`, `core/`, the tutorial, the FAQ, the error index, the glossary,
and the 2.0 migration guide. 270 files.

**The API reference is not in it, and it was never excluded — it does not exist as a file.**
SQLAlchemy generates the API reference from Python **docstrings** when Sphinx builds the site. It
has no `.rst` source to fetch. So `inspect(engine).has_table()` was never a candidate to retrieve;
it was never on the shelf to begin with.

That is worth saying carefully, because "we left out the API docs" and "the API docs are not
files" sound alike and are not:

```
DELIBERATE EXCLUSION            e.g. BREAKAGES.md (D09)
  the file exists
  we chose not to index it
  reversible: index it tomorrow and the answer appears

STRUCTURAL ABSENCE              the API reference (D07, D50)
  there is no file
  Sphinx builds it from docstrings at site-build time
  NOT reversible by re-indexing — you would have to add a
  different KIND of source
```

`g010` and `g023` are the same shape arriving from a different direction. The narrative docs are
written in the *current* vocabulary: 1.4 and 2.0 prose both say `relationship()`, and neither
stops to mention that it used to be spelled `relation`. The rename is old enough that the
narrative simply moved on. Nothing documents the thing the stuck developer typed.

#### `g010` is the one that nearly lied, and it is worth watching

Grep naively for `relation` and the corpus looks full of it:

```
relation, naive substring                     794 chunks   "answerable!"
relation, not followed by 'ship'                6 chunks
orm.relation / relation(                        0 chunks   the truth
```

**794 of those hits are the word `relationship`.** The remaining six are the English word — *"in
relation to your particular usage"*, *"the concept of a relation in relational algebra"* — and
they come in three cross-version pairs (`c00074`/`c01704`, `c00220`/`c01856`, `c00566`/`c02140`),
which is the duplicate structure `D58` describes.

**This exact bug already cost this repo a verdict.** In Phase 1, `rag/probe.py` matched symbols by
substring, so `relation` counted inside every `relationship`: **798 recorded, 21 true, 0
documenting `orm.relation()`**. It flipped Q6's verdict, and it silenced `symbol_missing` on
precisely the question that signal existed for — a signal can never fire for a symbol that is a
prefix of a common word. The fix is `probe.py`'s `_contains()`: a symbol ending in an identifier
character must not be followed by another one.

**So "is it in the corpus?" is not a `grep` for a substring.** It is a grep for a *whole symbol*,
and the difference between those two is 794 and 0.

#### Why keep questions the system cannot answer

Because they are the only items that measure whether it **says so**.

At the retrieval level an unanswerable item scores `recall = 0` by construction — the chunk does
not exist, so the zero is arithmetic, not evidence. It tells you nothing about the system. The
only thing these three can test is generation: does it decline, or does it invent a plausible API
signature? That is `D62`, and it is why refusal accuracy is printed apart from recall.

**The measured result: 3 of 3 refused, 0 fabricated.** Asked about `has_table`, the system says
the sources do not answer it and names what it looked for — rather than confidently emitting
`engine.has_table()`'s replacement from memory, which is the failure a RAG system is supposed to
prevent and the one `D43` measured the prompt into preventing.

**This is the honest ceiling of the project, stated as a number.** Not "our system sometimes does
not know things" — *three named questions, each provably absent from all 3284 chunks, each
correctly declined.* Knowing which questions you cannot answer, and proving your system knows it
too, is a stronger result than a higher recall figure.

---

## Vocabulary from this sitting

| term | plain meaning |
|---|---|
| **baseline** | the Phase 1 retrieval score every Phase 3 change is compared against |
| **recall@k** | fraction of answerable questions with a verified answer chunk in the top k — **@5 = what ships** |
| **MRR** | average of `1 ÷ rank_of_first_hit` — cares about position, which recall@k does not |
| **not in top-20** | answer never retrieved even deep — reranker cannot help |
| **duplicate slots** | top-k seats wasted on twin chunks (`D58`) |
| **provenance split** | report recall with and without each harvest group (`D60` / `D63`) |
| **overlap** | fraction of the question's content words already in the **top-1** (first returned) chunk — not the same as recall |
| **median overlap with top-1** | middle overlap in a provenance group; high ≈ question already uses docs vocabulary (`D63`) |
| **over-refusal** | declined an answerable question — either honest (no page) or a generation defect (page was there) |
| **ceiling** | answer string in zero chunks — Phase 3 cannot fix it (`D45`) |
| **structural absence** | no `.rst` file exists (API reference from docstrings) — not a deliberate exclusion |

## Where the numbers live as data

| | |
|---|---|
| [`../deliverables/golden.json`](../deliverables/golden.json) | the golden items — **100**, 91 answerable |
| [`../deliverables/GOLDEN-FULLBAR-AUDIT.md`](../deliverables/GOLDEN-FULLBAR-AUDIT.md) | all 100 re-checked against `chunks.jsonl`, live docs, and real 2.0.51 |
| [`../deliverables/baseline-phase1.json`](../deliverables/baseline-phase1.json) | the saved recall curve — **the 50-item run, and it stays that way** (`D65`) |
| [`../phases/PHASE-2.md`](../phases/PHASE-2.md) | the phase plan; this file is the teaching write-up of its score |
| [`12-EVALUATION.md`](12-EVALUATION.md) | §R4 — *how* to measure (Sitting 4, still the 19 probe answers) |
| [`13-VERIFICATION.md`](13-VERIFICATION.md) | §R5 — defend Phase 1 cold; Phase 1's last gate |
| [`09-DECISIONS.md`](09-DECISIONS.md) | **D06, D45, D58–D65**, plus §H CLOSED (spot-check of ten, then verified, 2026-08-21) |

