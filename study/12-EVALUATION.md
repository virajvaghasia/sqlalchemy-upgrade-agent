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
