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

## §R4 — Measuring a thing that has no right answer

### R4.1 Why this is hard in a way search is not

Ordinary search has a comfortable property: you can usually tell whether a result is right by
looking at it. RAG does not. **The output is a paragraph of English, and paragraphs are not equal
or unequal to anything.**

So evaluation splits into two questions that get confused constantly:

| | question | can a script answer it? |
|---|---|---|
| **retrieval** | did the right chunk reach the prompt? | **yes** — it is a set membership test |
| **generation** | is the answer any good? | **no** — it is a judgement |

**Almost everything measurable is on the first row.** That is not a coincidence and it is not a
limitation to apologise for — it is why Phase 2 is scoped to retrieval and Phase 4 is a separate
phase for answers. Conflating them produces a number that looks like quality and measures
plumbing.

### R4.2 The metrics, and what each is blind to

§R2's *Before Sitting 3* introduced these off real output. Restating them as a set, because the
blindness of each is the point:

| metric | what it sees | what it cannot see |
|---|---|---|
| **recall@k** | did a containing chunk land in the top k | *where* in the top k — rank 1 and rank 5 score the same |
| **MRR** | position, via `1 ÷ rank` averaged | whether the answer was any good once retrieved |
| **rank of first hit** | exactly how far off a miss was | nothing about the other four slots |

**No single one of them is enough, and the third is the one this project nearly skipped.**
`recall@5` says *failed*. The rank says *failed by how much*, and that turned out to change what
the fix is.

### R4.3 The measurement that changed the plan

Closing the 19 verdicts produced a number nobody had asked for: for each failing question, the
rank of the first chunk that actually contains the answer, out of 3284.

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
fix it with hybrid search."* They are **four different problems**:

- **rank 6** — a constant is wrong. One integer fixes it.
- **rank 8, 12** — the ranking is roughly right and the cut is too tight. A reranker over a wider
  candidate set fixes these without changing search at all.
- **rank 23, with a top-5 scoring `+0.001` over noise** — search did not rank the answer low, it
  **found nothing** and filled five slots with near-random text. Reranking a list of noise cannot
  help; keyword search can.
- **not present** — the corpus ceiling (`D45`, §R1.4). No phase touches it.

**That is the shape of a real evaluation finding**: it did not say the system is 74% good, it said
the plan was aimed at the wrong thing for at least one of five failures.

### R4.4 The verdicts, and what the distribution says

```
# summary of: deliverables/verdicts.json, closed 2026-08-17
CORRECT 10   PARTIAL 3   WRONG 6
```

**The surprise is in the six.** §R1 spent a whole sitting on hallucination — the model inventing
things — because that is the failure everyone expects and the one `D43`'s refusal clause exists to
prevent.

**Five of the six `WRONG` are refusals.** The system declined questions whose answers were in the
corpus. Only two are the expected failure: one confidently wrong from a correctly-labelled 2.0
page (§R1.7), and one that answered a narrower question than the one asked.

So the dominant failure mode of this system is **not answering**, and it took closing the gate to
see that. It was not predicted anywhere in Phase 1's plan.

### R4.5 Why the golden set is hand-verified, stated as a cost

`D06`: the golden dataset is hand-verified, never auto-generated. The argument is short — a model
grading answers produced by the same family of model measures self-consistency, not truth — and
the cost is not short at all. **That gate stayed open for two days.**

Two things make it survivable, and both are worth copying:

- **The answers were already known.** The questions come from `BREAKAGES.md`, 23 breakages
  measured against real 2.0.51 in Phase 0. **14 of the 19 have a fix marked `fix OK`.** So most
  verdicts are a comparison against a key, not a recall test.
- **The key is not in the corpus** (`D09`, §R1.6). That decision cost real answer quality in Phase
  1 and is what makes this measurement legitimate rather than circular.

**And it can be executed rather than read.** For any answer proposing code: write what it says
*literally*, run it on the pin, compare against the verified fix. Runs and matches → `CORRECT`.
Won't run → `WRONG`. **Runs and behaves differently → `PARTIAL`**, which is the dangerous one and
is now a measured outcome rather than a hedge.

### R4.6 The trap: a benchmark that moves when nothing improved

`D31` compared pgvector against Qdrant on this repo's own vectors. The speed result was
uninteresting — 0.45 ms against 2.65 ms, both noise beside the ~40 ms embed. **The interesting
result was that they disagree.**

```
# summary of: 09-DECISIONS.md D31, measured 2026-08-17 over the 19 probe questions
identical top-5 : 15 / 19
```

Both are HNSW. Both are approximate. Neither is wrong. **But on 4 of 19 questions the model would
have been handed different sources depending on which store was running** — and any Phase 2 number
computed across that swap would move without retrieval having improved at all.

**This generalises past vector stores.** A benchmark is only a benchmark if everything except the
thing under test is pinned: model *and revision* (`D41`), normalisation (`D36`), chunk parameters,
`k`, and the store. The repo pins the first four already. The fifth was invisible until measured.

---

## Vocabulary from this sitting

| term | one-line meaning |
|---|---|
| **golden dataset** | questions with known-correct answers, used to score the system — hand-verified here (`D06`) |
| **recall@k** | of the questions, how many put a containing chunk in the top k |
| **MRR** | mean of `1 ÷ rank` — sees position, which recall cannot |
| **rank of first hit** | how far off a miss was; distinguishes "one place out" from "found nothing" |
| **leakage** | the answer key present in the corpus being searched, inflating every score (`D09`) |
| **ceiling** | the answer is in no chunk, so no ranking change can ever reach it (`D45`) |
| **pinned** | every variable except the one under test held fixed — including the vector store (`D31`) |

## Before Sitting 5

**Read, do not run — these all need the corpus and one needs a GPU:**

```bash
uv run python -m tools.review_sheet --full   # every answer, source and verdict
uv run python -m tools.apply_verdicts --check
```

**Answer these three:**

1. *`recall@5` says a question failed. Why is the **rank** of the first containing chunk worth
   measuring as well, and what four different problems did it separate here?* — R4.3
2. *The golden set is hand-verified, which kept a gate open for two days. What makes that cost
   survivable, and what would it have measured instead if the script had graded itself?* — R4.5
3. *Two vector stores returned identical top-5 on 15 of 19 questions. Why is that a problem for
   Phase 2 specifically, rather than a curiosity?* — R4.6

**A warning about question 3.** "One of them is less accurate" is not the answer — both matched a
brute-force scan on the question that was checked. The problem is not accuracy.

## Where the rest of the repo lives

| | |
|---|---|
| [`10-RETRIEVAL.md`](10-RETRIEVAL.md) | §R1–§R2 — why retrieval exists, and what an embedding is |
| [`11-GENERATION.md`](11-GENERATION.md) | §R3 — the prompt as a component |
| [`09-DECISIONS.md`](09-DECISIONS.md) | **D06, D09, D31, D45, D46** are this file in register form |
| [`../deliverables/FAILURES.md`](../deliverables/FAILURES.md) | the 19 answers, sources and verdicts |
