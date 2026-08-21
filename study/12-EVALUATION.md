# Evaluation — study notes

Part of [`sqlalchemy-upgrade-agent`](../README.md). **§R4 onwards**, continuing the `R` run that
[`10-RETRIEVAL.md`](10-RETRIEVAL.md) starts at §R1 and [`11-GENERATION.md`](11-GENERATION.md)
carries at §R3. The `R` is for RAG, not Retrieval (`09-DECISIONS.md` **D47**).

**Why this is a third file.** §R1–§R2 are retrieval — choosing a corpus, cutting it up, searching
it. §R3 is generation — what the model does with what it was handed. **§R4 is neither: it is how
you find out whether any of it worked.** That is a different subject with a different failure
mode, and the failure mode is the interesting part.

> **Sitting 4 is §R4.** It assumes §R1–§R3 have landed. Everything here is measured off the 19
> answers in [`../deliverables/FAILURES.md`](../deliverables/FAILURES.md), whose verdicts were
> closed on 2026-08-17 — so this section describes a thing that exists rather than a plan.

---

## If you are lost — two report cards, not one grade

Forget the metric names for one page. You already know the library picture from §R1:

1. Search finds **five pages** (retrieval).
2. The chatbot reads those pages and **writes a paragraph** (generation).

**Those are two different jobs.** Scoring them with one number is what makes evaluation feel
muddy. Keep them apart:

```
  REPORT CARD A — did we find the right page?     REPORT CARD B — is the paragraph any good?
  ─────────────────────────────────────────       ──────────────────────────────────────────
  Question: "where is backref explained?"         Question: "is this answer correct?"
  Check: open the five pages. Is the answer       Check: a person who knows SQLAlchemy 2.0
         somewhere in them?  yes / no                    reads it and says CORRECT / PARTIAL / WRONG
  Who can grade it: a script (set membership)     Who can grade it: only a human (judgement)
  Phase that owns it: Phase 2 (golden set)        Phase that owns it: Phase 4 (answers), and the
                                                         19 hand verdicts already done for the probe
```

**What did *not* happen.** Nobody computed “the system is 74% good.” That sentence would mix
“page not found” with “page found, answer still wrong.” Those need different fixes — so they
must not share one score.

**The rest of §R4 in one breath:**

| section | plain job |
|---|---|
| **R4.1** | why those two report cards must stay separate |
| **R4.2** | three ways to score report card A, and what each is blind to |
| **R4.3** | the measurement that split “dense missed it” into four different fixes |
| **R4.4** | what the 19 human grades on report card B actually looked like |
| **R4.5** | why a human must fill the answer key (`D06`) |
| **R4.6** | a trap: the score moves when you swap the catalogue and change nothing else |

---

## §R4 — Measuring a thing that has no right answer

### R4.1 Why this is hard in a way search is not

Ordinary Google-style search is easy to check: you look at a link and say “yes, that page.”
RAG is harder because the thing you see is a **paragraph of English**, and paragraphs are not
equal or unequal to a single correct string.

So evaluation splits into the two report cards above. **One question of ours on each row, so
the split is concrete rather than tidy.**

**Report card A — a script can settle it.**

> *"`engine.has_table()` no longer exists, what replaces it?"*

Did any of the five pages contain the string `has_table`? `grep` answers that: **zero chunks in
the whole index contain it.** No reading, no opinion. The page was never shelved. Call that a
**ceiling** (`D45`) — no amount of “search harder” invents text that is not there.

**Report card B — no script can settle it.**

Question 1 asked what replaces `Query.from_self()`. The answer said use `aliased`, and cited
`[2][3]` — real pages, correct section. Right or wrong? **Partly right.** `aliased(Issue)`
renames a table; `aliased(Issue, subq)` wraps a subquery. The answer never mentions the second
argument. Run against the practice database: that query returns `['a','e']`; the correct version
returns `['a']`. **A human had to know that.** No string match separates that answer from a
complete one: both name `aliased`, both cite a real page, both read fluently.

**Almost everything measurable is on report card A.** That is not an apology — it is why Phase 2
scores retrieval and Phase 4 is a separate phase for answers. Mixing them produces a number that
looks like quality and measures plumbing.

### R4.2 The metrics — three rulers for report card A

You ask 19 questions. For each one, search returns an ordered list of pages (rank 1 = closest,
rank 2 = next, …). Somewhere in the 3284 pages there is usually a page that *contains* the
answer. Call that page the **hit**.

Three rulers. Same list of ranks. Different questions. **Show them on one failure first, then
name them.**

**Worked example — `backref`.** The first page that mentions `backref` sat at **rank 6**. We
only paste the top **5** into the prompt (`DEFAULT_K = 5`).

| ruler | what you ask | what you get for `backref` |
|---|---|---|
| **Did a hit land in the top 5?** | yes / no | **no** (hit is at 6) |
| **How good was the position?** | `1 ÷ rank` | `1 ÷ 6 ≈ 0.17` (rank 1 would be 1.0) |
| **How far off was the miss?** | the rank number itself | **6** — one place below the cut |

Now the names:

| name | what it averages across questions | what it cannot see |
|---|---|---|
| **recall@k** | fraction of questions where *some* hit landed in the top k | *where* in the top k — rank 1 and rank 5 both count as a win |
| **MRR** (mean reciprocal rank) | average of `1 ÷ rank_of_first_hit` | whether the chatbot’s paragraph was any good once the page arrived |
| **rank of first hit** | the raw position for one question (or a table of them) | nothing about the other four slots in the prompt |

**No single one is enough.** `recall@5` alone says *failed* for `backref`. The rank says
*failed by one place* — and that changed the fix from “rebuild search” to “maybe change one
integer.” That is why this project almost skipped the third ruler and why R4.3 exists.

§R2’s *Before Sitting 3* introduced these off real output. Restating them here as a set,
because the blindness of each is the point.

### R4.3 The measurement that changed the plan

Closing the 19 verdicts produced a number nobody had asked for: for each failing question, the
**rank of the first chunk that actually contains the answer**, out of 3284.

Think of it as: “search put the right page how far down the pile?” Not “is the chatbot’s
paragraph good?” — that is report card B.

```
# summary of: rank of the first containing chunk, measured 2026-08-17 against
#   corpus/embeddings.npy. `probe.py` records presence; this adds position.
symbol             in corpus   rank   what it actually is
backref                   80      6   missed the cut by ONE place
cascade_backrefs          12      8   just outside
keys()                     7     12   squarely a reranking case
table_names                6     23   and its top-5 scored +0.001 over noise
has_table                  0    none   the ceiling — no k, no reranker, ever
```

**Read the first row again. `DEFAULT_K = 5`, and the answer was at 6.**

Before this, all five of those were filed as one thing: *"dense retrieval missed it, Phase 3 will
fix it with hybrid search."* They are **four different problems**, and the first one is an integer.

The integer is **`DEFAULT_K` in `rag/ask.py`**. It is currently **5**. Search put the first
`backref` page at **rank 6 of 3284**. The chatbot only sees the top k pages, so rank 6 never
gets pasted in. Change the constant to **6** and that page is in the prompt — no hybrid
search, no reranker, no new model.

Raising k *gets the page in*. It does **not** automatically get an answer: Round 7 left
refusals at 8 at every k, and at k=10 the `backref` page was in the prompt and the model still
refused (`D51`). k=10 also bought over-fires. **D54 kept `DEFAULT_K = 5`.** So 6 is the
integer that fixes the *retrieval miss*. It is not the integer that ships.

| failure | rank | what you change |
|---|---|---|
| `backref` | **6** | one integer: `DEFAULT_K` 5 → 6 |
| `cascade_backrefs` | 8 | rerank a *wider* list (take 20, keep 5). Search unchanged |
| `keys()` | 12 | same reranker — 6 is not enough |
| `table_names` | 23 | keyword search; the top-5 scored ~noise |
| `has_table` | none | nothing. Zero chunks. Only the corpus decision (`D45`) |

**That is the shape of a real evaluation finding**: it did not say the system is 74% good, it said
the plan was aimed at the wrong thing for at least one of five failures.

#### Side note — rank tells *how far*; a live run tells *which component*

> Round 7 went further — see `09-DECISIONS.md` D51. Sweeping `k` over the probe set moved
> retrieval (`symbol_missing` 6→4, `retrieval_failure` 5→3) and **left refusals at 8,
> unchanged, at every value of k.** A `--retrieval-only` run confirmed the `backref` answer was
> in the prompt at k=10 and the model refused anyway.
>
> So: the rank table sorted the *retrieval* failures into four buckets. It still could not see
> refusals — those are report card B. Hybrid search would have surfaced pages that were already
> being surfaced for some of those. **Measure before you rebuild.** That is the strongest
> argument in the repo for this sitting, and a caution about R4.3 itself: position ≠ component.

### R4.4 The verdicts — and first: what “dense retrieval” means

**Dense retrieval = meaning search.** Same thing, two names.

From §R1: every page got a spot on a map (1024 numbers). A question gets a spot on the same
map. Search returns the pages whose spots are **nearest in meaning**. That is dense retrieval.
It does **not** look for the exact string `backref` the way `grep` would. That string channel is
what Phase 3’s keyword search (BM25) adds later.

```
  MEANING SEARCH (what Phase 1 does)          STRING SEARCH (what Phase 1 does NOT do)
  ──────────────────────────────────          ──────────────────────────────────────
  “close a session” ≈ “terminate a            look for the letters b-a-c-k-r-e-f
   connection” even if no shared words        on the page
  name: dense retrieval                       name: keyword / BM25 / hybrid (with dense)
```

So when this file says “dense missed it,” it means: **meaning search ranked the right page too
far down** (or found nothing useful), not “the chatbot wrote a bad paragraph.”

#### Now the grades — report card B

Nineteen answers. A human graded each one against real SQLAlchemy 2.0.51. Three buckets only:

```
# summary of: deliverables/verdicts.json, closed 2026-08-17
CORRECT 10   PARTIAL 3   WRONG 6
```

| grade | plain meaning |
|---|---|
| **CORRECT** | would paste it — or correctly refused when the library has nothing |
| **PARTIAL** | right idea, incomplete or wrong when run (Q1: `aliased` without the second argument) |
| **WRONG** | would not paste it |

#### The concrete case people trip on — “WRONG” is not one kind of bug

§R1 trained you to fear **hallucination** (the chatbot invents an API). That is *not* what most
of the six `WRONG` are. Walk the six. Ask for each: **did meaning search fail, or did something
else fail?**

| Q | what happened | meaning search (dense) failed? | what actually failed |
|---|---|---|---|
| **19** `backref` | refused | **yes** — right page at **rank 6**, cut is top **5** | retrieval miss by one place (`DEFAULT_K`) |
| **5** `keys()` | refused | **yes** — right page at **rank 12** | retrieval; reranker on a wider list |
| **18** `cascade_backrefs` | refused | **yes** — right page at **rank 8**; top-5 near noise | retrieval; wider list + rerank |
| **3** `table_names` | refused | **yes** — right page at **rank 23**; top-5 ≈ noise | meaning search found *nothing useful*; needs **string** search |
| **7** `future=True` | answered confidently, **wrong** | **no** — it got a real 2.0 page | generation / version-skew reading (§R1.7) |
| **16** absent Q | answered when it should have refused | **no** — corpus has no full answer | generation (should have declined) |

**Read that table twice.** Four of the six `WRONG` *start* as dense (meaning-search) misses —
the right page never reached the five slots, or the five slots were junk. Two of the six are
**not** dense problems at all: the pages arrived (or were not needed) and the **paragraph** was
still wrong.

**Refusals that are CORRECT** sit next door and confuse the picture if you skip them:

| Q | refused? | grade | why CORRECT |
|---|---|---|---|
| **4** `has_table` | yes | CORRECT | **0 chunks** — ceiling. Honest decline |
| **6** `orm.relation()` | yes | CORRECT | not in corpus as an API — ceiling |
| **15**, **17** | yes | CORRECT | question outside the library on purpose |

So: **“it refused” is not automatically WRONG.** Refuse when the shelf is empty → good.
Refuse when the answer is on the shelf but not in the top 5 → bad, and often a dense miss.
Refuse when the answer *is* already pasted into the prompt → bad, and that is **generation**,
not dense retrieval (Round 7 / Q18–Q19 at higher `k` — Phase 4 territory).

#### One story end to end — Question 19 (`backref`)

```
  You ask about backref.
        │
        ▼
  Meaning search ranks 3284 pages.  First page that actually contains
  “backref” lands at rank 6.
        │
        ▼
  Chatbot only gets ranks 1–5  (DEFAULT_K = 5).  Rank 6 never pasted.
        │
        ▼
  Prompt has five pages that are *related in meaning* but do not hold
  the answer.  Model declines → refused → human marks WRONG.
```

Is that a dense-retrieval issue? **Yes** — meaning search put the hit one place too low.
Would raising `k` to 6 fix the *retrieval* miss? **Yes.** Does that guarantee a good paragraph?
**No** — Round 7 put the page in at k=10 and the model sometimes still refused. That second
half is report card B.

#### What R4.4 is trying to teach

1. **Dense retrieval = meaning search.** Phase 1 only does that.
2. The **10 / 3 / 6** split is report card B (human grades of paragraphs).
3. Inside the six `WRONG`, **most are “would not answer,” not “invented an API.”**
4. Of those refusals, **some are dense misses** (page not in top 5) and **some later become
   generation defects** once the page *is* in the prompt.
5. That mix is why you cannot say “the issue is dense retrieval” for the whole sitting — and
   why R4.3’s rank table and R4.4’s verdicts answer different questions.

So the dominant failure mode of the *paragraphs* is **not answering**, and it took closing the
gate to see that. It was not predicted in Phase 1’s plan. Separately, several of those
non-answers still *began* as meaning-search misses — R4.3 is how you see that.

### R4.5 Why the golden set is hand-verified — and what that costs

A **golden set** is a list of questions where someone already knows the right answer — like an
exam key. Phase 2 will score retrieval against ~50 of those.

`D06`: a **human** fills that key. Never auto-generate it. Short reason: if the same family of
model writes the answers *and* grades them, you measure “does it agree with itself,” not “is it
true.” Longer cost: **that gate stayed open for two days.**

Two things make the cost survivable:

- **The answers were already known.** Questions come from `BREAKAGES.md` — 23 breakages measured
  against real 2.0.51 in Phase 0. **14 of the 19 probe items have a fix marked `fix OK`.** Most
  verdicts are “compare to the key,” not “remember SQLAlchemy from scratch.”
- **The key is not in the corpus** (`D09`, §R1.6). Leave `BREAKAGES.md` in the search shelf and
  the system retrieves the answer key, then gets marked against it. That is grading your own
  homework. Keeping it out cost some Phase 1 answer quality and is what makes the score honest.

**And it can be executed rather than read.** For any answer that proposes code: type what it
says *literally*, run it on the pin, compare to the verified fix.

| what happens | grade |
|---|---|
| runs and matches the fix | `CORRECT` |
| will not run | `WRONG` |
| runs but behaves differently | `PARTIAL` — the dangerous one |

### R4.6 The trap: the score moves when nothing improved

You change the catalogue (vector store). You change nothing else — same pages, same map, same
`k`. Phase 2’s number moves anyway. That is not improvement. That is noise dressed as a win.

`D31` compared pgvector against Qdrant on this repo’s own vectors. Speed was uninteresting
(0.45 ms vs 2.65 ms — both noise beside the ~40 ms embed). **The interesting result: they
disagree.**

```
# summary of: 09-DECISIONS.md D31, measured 2026-08-17 over the 19 probe questions
identical top-5 : 15 / 19
```

Both use the same approximate algorithm (HNSW). Neither is “wrong.” But on **4 of 19** questions
the chatbot would have been handed **different pages** depending on which store was running.
Any Phase 2 score computed across that swap would move without retrieval having gotten better.

**Plain rule:** a benchmark only measures the thing you meant to change if everything else is
**pinned** — model *and revision* (`D41`), normalisation (`D36`), chunk settings, `k`, and the
store. The repo already pinned the first four. The fifth was invisible until measured.

### R4.7 The baseline — and the number not to quote

The golden set was finished on 2026-08-20: **50 questions, all verified by hand.** One command
scored them, and this is the Phase 1 baseline every Phase 3 change gets compared against.

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

**Read that as a sentence.** For half the questions, the page holding the answer never reached
the prompt. `DEFAULT_K = 5`, so the model was handed five pages, and for 23 of 47 answerable
questions none of them was the right one. The model was not being stupid on those — it was
never shown the answer.

#### The number not to quote, and why

`0.51` is the average of two groups that behave nothing alike. Split by where the question came
from:

| provenance | n | median overlap with top-1 | recall@5 |
|---|---|---|---|
| `migration_guide` | 16 | 0.64 | **0.73** |
| `breakages` | 34 | 0.43 | **0.41** |

**That gap — 32 points — is bigger than anything Phase 3 is expected to buy.** So which half you
quote matters more than the improvement you are about to make.

The **overlap** column is what explains it, and it is worth spelling out because it is not a
technical term so much as a bookkeeping one. Take the question, take the top-ranked chunk it
retrieved, and ask: *what fraction of the question's real words already appear in that chunk?*
Drop `the`, `a`, `is`, `how` — count the rest.

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
  second slot that a different page could have used (`D58`). Deduplicating at retrieval time is
  the cheapest lever on this list and it touches no model.
- **Median rank when found is 2.5.** When search works, it works well. The failure is **binary,
  not gradual** — the answer is either near the top or nowhere. That is why `D61` reports flipped
  items rather than a moving average: there is no gentle slope here to nudge.

### R4.8 Refusals — and the 15 points that recall does not see

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

The **6** that answered *without* the verified page in the prompt are the least understood cell in
the table, and this file will not pretend otherwise. They may have answered correctly from an
adjacent page, or partially, or they may have invented. **Retrieval cannot tell you and neither
can a refusal count** — deciding it means reading six answers against real 2.0.51, which is
exactly the judgement `D06` reserves for a human and exactly what Phase 4 exists to grade. It is
recorded here as an open cell rather than quietly averaged into a pass.

### R4.9 The three questions with no answer — and what "unanswerable" does not mean

Three of the 50 golden items are marked `answerable: false`. The word invites a wrong reading, so
start with what it is **not**.

**It does not mean the question is unanswerable.** All three have real, known, verified answers.
They are in `deliverables/BREAKAGES.md`, they were measured against real SQLAlchemy 2.0.51 in
Phase 0, and any of them could be answered in one line by somebody who knows the library:

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
| **report card A / retrieval** | did a page that contains the answer reach the prompt? |
| **report card B / generation** | is the written paragraph any good? (human only) |
| **golden dataset** | exam key — questions with known-correct answers; hand-verified here (`D06`) |
| **hit** | a page that contains the answer (for one question) |
| **recall@k** | fraction of questions where some hit landed in the top k |
| **MRR** | average of `1 ÷ rank_of_first_hit` — cares about position, which recall@k does not |
| **rank of first hit** | how far down the pile the first good page sat (e.g. `backref` at 6) |
| **leakage** | answer key sitting on the search shelf — scores go up for the wrong reason (`D09`) |
| **ceiling** | answer is in no page at all — no ranking fix can reach it (`D45`) |
| **pinned** | everything except the one thing under test held fixed — including the store (`D31`) |
| **dense retrieval** | **meaning search** — nearest pages on the embedding map (Phase 1). Not string/`grep` search |
| **refusal** | model declines to answer; CORRECT if the shelf is empty, WRONG if the answer was findable |

## Before Sitting 5

**Read, do not run — these all need the corpus and one needs a GPU:**

```bash
uv run python -m tools.review_sheet --full   # every answer, source and verdict
uv run python -m tools.apply_verdicts --check
```

**Answer these three (plain language):**

1. *`recall@5` says a question failed. Why also measure the **rank** of the first containing
   page — and what four different problems did that separate here?* — R4.3 (`backref` at 6 is
   the one-integer case)
2. *The golden set is hand-verified. That cost two days. What makes the cost survivable, and
   what would you have measured if a script graded itself?* — R4.5
3. *Two catalogues returned the same top-5 on 15 of 19 questions. Why is that a problem for
   Phase 2, not just a curiosity?* — R4.6

**A warning about question 3.** “One of them is less accurate” is not the answer — both matched
a brute-force scan on the question that was checked. The problem is not accuracy. The problem
is the **score moving when you did not change retrieval quality**.

| | |
|---|---|
| [`10-RETRIEVAL.md`](10-RETRIEVAL.md) | §R1–§R2 — why retrieval exists, and what an embedding is |
| [`11-GENERATION.md`](11-GENERATION.md) | §R3 — the prompt as a component |
| [`09-DECISIONS.md`](09-DECISIONS.md) | **D06, D09, D31, D45, D46** are this file in register form |
| [`../deliverables/FAILURES.md`](../deliverables/FAILURES.md) | the 19 answers, sources and verdicts |
