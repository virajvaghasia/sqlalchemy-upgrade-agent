# Judge — study notes

Part of [`sqlalchemy-upgrade-agent`](../README.md). **§R8**, continuing the `R` run after
[`15-IMPROVE.md`](15-IMPROVE.md) §R7. Plan file (decisions + tables):
[`../phases/PHASE-4.md`](../phases/PHASE-4.md). Decisions: **`D71`–`D77`**.

> **Read this after §R7.** §R7 was about *search* — finding the right page. This one is about
> what happens **after** the right page is already sitting in the prompt. That turns out to be
> where most of the loss is, and none of §R7's numbers could see it.

---

## If you are lost — one picture

You have been quoting **0.64**. That number is real, and it is **not what your system does**.

```
  0.64   the right page reached the prompt        ← what §R7 measured
  0.43   ...and the model actually answered       ← what a user gets
  ────
  0.21   lost AFTER search had already won
```

**Both numbers are about the same 91 questions.** The gap is 19 questions where search did its
job, put the correct documentation page in front of the model, and the model said *"The sources
do not answer this."*

**Say `0.43`.** Say `0.64` only with the word **retrieval** attached to it.

---

## §R8 — what Phase 4 measured

### R8.0 Three report cards, not two

§R4 taught you there were two: **retrieval** (did the right page arrive) and **generation** (was
the answer any good). Phase 4 splits the second one, because "any good" was hiding three
different failures that want three different fixes.

```
  Did the right page reach the prompt?          RETRIEVAL   — §R7 closed this at 0.64
  Did the model answer, or decline anyway?      REFUSAL     — 19 of 58 declined. D72
  If it answered, can you CHECK the answer?     CITATION    — 65% cite nothing. D73
  If it wrote code, is that code in the pages?  GROUNDING   — D77
```

**Why they must stay apart.** Suppose you averaged them into one "quality" score. A system that
refuses everything gets a *perfect* citation score, because a refusal has nothing to cite. The
number would go **up** as the system became more useless. `D62` refused that averaging for
recall and this file keeps refusing it.

---

### R8.1 End to end (`D72`) — the number that was being computed by hand

**Plain job.** Count the questions where **both** things went right: the answer chunk was in the
prompt, **and** the model did not decline.

```
  91 answerable questions
  58  the answer chunk reached the prompt          ← retrieval's ceiling
  19  ...of those, the model refused anyway        ← thrown away
  ────
  39  answered with the right page in hand   =  0.43
```

**Where it had been living.** Nowhere reproducible. Earlier docs said `0.36`, then `0.35`, both
arrived at by a person subtracting one printed number from another. Both were *right*. Neither
could be re-derived by running anything — which is precisely what this repo's measurement rule
exists to stop. It prints now:

```
uv run python -m rag.score --refusals
```

**The counter-intuitive bit, and it will be asked.** Phase 3 improved retrieval, and the
over-refusal count went **up**: 13 → 19.

That is not a regression. Read the definition again: *refused **with the answer in the
prompt***. Improve retrieval and more questions become **eligible** for that cell — a question
whose page never arrived cannot be over-refused, it is just a miss.

```
  before Phase 3   13 of 45 eligible   = 29%
  after  Phase 3   19 of 58 eligible   = 33%
```

**So never compare the raw count across a retrieval change.** Compare the rate.

**And the sharpest version of it:** Phase 3 fixed seven questions. **Two of them — `g044` and
`g050` — are now refused with the page in the prompt.** Search went and found the page, and the
model declined it. Every table in §R7 scores those two as wins. They are, and the user got
nothing from either.

---

### R8.2 Citations (`D73`) — `ask.py` fails its own opening sentence

`rag/ask.py` opens with these words:

> **SOURCES ARE NOT DECORATION**

and argues that without the chunks there is no way to tell a correct answer from a lucky one.

Measured over the 48 questions that got an answer at all:

```
  cite nothing at all              31   65%
  cite only one of the five        16   33%
  contain code                     28   58%
    ...of those, code uncited      26   93%
  cite a source that doesn't exist  0    0%
  mean coverage                  0.07   five pages in, a third of one cited
```

**Two answers in three are unverifiable.** Not *wrong* — unverifiable. Here is the whole
difference, on `g002`:

```
The :meth:`_orm.Query.from_self` method has been removed from :class:`_orm.Query`
in SQLAlchemy 2.0. Instead, you should use the :func:`_orm.aliased` construct...
```

That answer is **correct**. It is also a paragraph you have to take on faith, and it leaks raw
documentation markup into a user's face. If it had said `...has been removed [3].` you could
open source 3 and check it in four seconds. That is the entire product argument for RAG, and it
was not happening.

**Why I checked it four ways before believing it.** A 65% defect rate is exactly what a broken
detector prints. So:

1. `build_prompt` numbers the sources `[1]`…`[5]` — the format exists.
2. `SYSTEM` says *"cite the source number in brackets, like [2]"* — it is demanded.
3. `generate()` sends `SYSTEM` — the model was told.
4. `g002`'s raw answer, printed and read — **zero** `[n]` anywhere.

**Zero out-of-range citations is a real result too.** When the model does cite, it never invents
a source number like `[7]` when five were given. **The defect is omission, not invention** — and
those want different fixes.

**What it is NOT: a claim that Phase 1 was wrong.** Phase 1 measured this and reported
`uncited: 3`. That was 3 of the **11** probe questions that got an answer = 27%.

```
  Phase 1   3/11 = 27%   Wilson 95%  [0.04, 0.51]
  Phase 4  31/48 = 65%   Wilson 95%  [0.52, 0.78]
```

The bands miss each other **by a hair**. Phase 1 was not wrong; **eleven questions could never
have settled it either way**. This is the second time the repo has been bitten by exactly that —
three unanswerable items could not measure a fabrication rate on 08-21, and eleven answered
questions could not measure a citation rate.

---

### R8.3 The prompt lab (`D74`) — position beats emphasis

Both defects above are the *model's*, not search's. So the first lever is the prompt, and it is
free to try.

**The obvious idea, and it does nothing.** Variant **E** says it as hard as English allows, in
the system message:

> *"Every factual sentence must end with the bracketed number of the source it came from…
> **An answer with no bracketed number in it is not acceptable.**"*

Result on `g002`: an answer near word-for-word identical to the shipped prompt's, with **zero**
citations. Every cell in the table unmoved.

**The model is not defying you. It is not attending.** By the time it starts writing, that
instruction is thousands of tokens back, behind five full documentation chunks:

```
  [ SYSTEM: ...cite the source number...  ]   ← the rule, way back here
  [ SOURCE 1  ~700 tokens of docs         ]
  [ SOURCE 2  ~700 tokens                 ]
  [ SOURCE 3  ~700 tokens                 ]
  [ SOURCE 4  ~700 tokens                 ]
  [ SOURCE 5  ~700 tokens                 ]
  [ QUESTION: ...                         ]
  [ ANSWER:                               ]   ← it starts writing here
```

**Variant H changes no wording at all.** Same sentence, moved to the last line before `ANSWER:`:

```
  [ QUESTION: ...                                     ]
  [ Before answering: cite the source number in       ]  ← the rule, here instead
  [ brackets, like [2], after each statement...       ]
  [ ANSWER:                                           ]
```

Measured over all 100:

| | end to end | over-refused | uncited | code w/o source |
|---|---|---|---|---|
| **D** shipped | 39/91 = **0.43** | 19 | 31/46 = **67%** | 25/26 = 96% |
| **E** louder, system message | — same as D — | | | |
| **H** *same words*, user turn | **47/91 = 0.52** | **10** | **6/60 = 10%** | 19/36 = 53% |

**9 fixed, 0 broken, exact McNemar p = 0.0039.**

**End to end 0.43 → 0.52 is a bigger gain than everything §R7's retrieval work bought**
(0.35 → 0.43). From moving one sentence.

**The part that was not the hypothesis.** H was aimed at citations. It also cut over-refusals
**19 → 10**, and the count of questions answered at all went **46 → 60**. *Asking the model to
cite made it more willing to answer.* I do not have a mechanism for that, and saying so is
better than inventing one.

**This is the same shape as `D54`.** Prompt D beat prompt B not by being firmer but by changing
the **mechanism**. E is the "say it louder" branch, and it is a null result.
**Position is a lever. Volume is not.**

**What it is NOT: shipped.** `ask.SYSTEM` is untouched. H lives in `rag/compare_prompts.py` with
its numbers beside it, because which prompt ships is a decision, and the last time that was
assumed rather than asked (2026-08-17) it was the wrong call.

---

### R8.4 The result was wrong the first time (`D76`) — read this one twice

The first reading of that table said **12 fixed, p = 0.000, end to end 0.55**.

The measurement rule says spot-check a raw answer. Here is `g006` under H:

```
[2] The sources do not answer this.
```

**That is a refusal wearing a citation.**

`ask.refused()` is a **prefix** test — it asks whether the answer *starts with* `"The sources do
not answer"`. `"[2] The sources…"` does not. **It was scored as an answer.**

And look at *why*: H's entire content is *"cite the source number before each statement."* The
model complied. Including in front of its own refusal.

> **The variant under test reshaped the output in exactly the way that defeated the detector
> reading it.**

**And the shipped prompt shows zero such cases**, because the shipped prompt barely cites at all.
**The bug was invisible until the thing being measured started working.**

Corrected: 6 of H's answers were cited refusals, **3 of them sat in the "fixed" column**.

```
  first read    12 fixed, p = 0.000, 0.55
  true result    9 fixed, p = 0.0039, 0.52
```

Still significant. Still clears `D61`'s bar of ~6 clean fixes with no regressions. **And now
true.**

**Why the prefix test is not simply a bug to widen.** A substring search would be worse: prompt D
deliberately produces *"here is the part the sources cover, and here is the part they do not"* —
which is an **answer**. Matching the phrase anywhere would score that as a refusal and inflate
the number in the flattering direction. The fix strips leading `[n]` markers and keeps the anchor
at the **start**.

**Two things made the correction cheap, and both were decisions:**

- **The answers were saved** (`D75`). Re-scoring cost seconds. Had only the summary table been
  kept, correcting it would have meant regenerating 300 answers — and `D54` drift would have
  made the corrected run not comparable with the run it was correcting.
- **No recorded number moved.** The shipped prompt produced zero cited refusals, so `D72` and
  `D73` stand exactly as published. **Verified, not assumed.**

---

### R8.5 Groundedness (`D77`) — catching invented code with no judge model

Everything above is about citing. This is about **lying**.

**The one defect the prompt could not move.** Fabrications — answering a question the corpus
genuinely cannot answer — sat at **2 of 9** under *every* wording tried. Position, emphasis,
premise: all failed.

**The idea, and it needs no AI at all.** Take the API calls in the answer's **code**, and ask
whether each one appears in **any of the pages that were in the prompt**.

```
  answer says:   op.create_view("v", "SELECT ...")
  sources say:   ...nothing containing create_view...
  verdict:       ungrounded
```

| | answered | with an ungrounded call | rate |
|---|---|---|---|
| **D** shipped | 48 | **2** | 4% |
| **H** | **62** | **0** | **0%** |

**H answers 14 more questions and grounds every line of code in all of them.**

**Now the finding that a count could not show you.** The fabrication count is **2 for both**. By
that metric, nothing improved. Here is what actually changed, on `g065` — *"can I create a table
and a view in the same migration?"*, which the corpus cannot answer:

```
  ---- D (shipped) ----
  ...you can use the `DDL` construct along with Alembic...

  ```python
  from alembic import op
  import sqlalchemy as sa

  def upgrade():
      op.create_table('my_table', sa.Column('id', sa.Integer, ...))
      ...
  ```
  ← a recipe. None of these calls appear in any retrieved page.
    On the 08-21 run it also called op.create_view(), which does not
    exist on alembic 1.19.1 at all.

  ---- H ----
  [3] SQLAlchemy supports ALTER TABLE, CREATE VIEW, CREATE TRIGGER,
      Schema Upgrade Functionality. For a more comprehensive option,
      schema migration tools like Alembic or SQLAlchemy-Migrate can be used.
  ← zero code blocks. one citation. a paraphrase of the page it cites.
```

**Both are scored "answered an unanswerable item."** One hands a developer a procedure they will
run and that partly does not exist. The other repeats what the page says and stops.

> **A count of fabrications is not a measure of harm.**

**It confirms the golden set from the opposite direction.** On 2026-08-21 the spot-check of ten
rewrote `g065`'s reason to *"CREATE VIEW chunks exist (`c00484`/`c02056`) but do not teach
same-migration CREATE TABLE + VIEW."* H found exactly those chunks and repeated exactly that
much. The hand-written label and the machine's behaviour agree, arrived at independently.

**What it is NOT: a claim about whether an API exists.** `op.create_table` is a real Alembic
function, and it is still reported ungrounded when no source mentions it — which is **correct**
for a RAG metric: the answer is unsupported by the pages the system was given. *Does this symbol
exist at all* is a different question, answered against the real library by
`tools/audit_golden_fullbar.py`. **Neither replaces the other.** `g065` fails both.

**What it cannot see: `g056`.** Never flagged, under any wording, because it fabricates in
**prose** rather than code. A code-grounding detector is structurally blind to that, and saying
so is better than implying coverage it does not have.

---

### R8.6 What is left

**One thing, and it needs a key.** Prose-level faithfulness — *is this sentence supported by that
passage* — is a reading task, so it needs the strong judge `ROADMAP.md` specifies (Gemini free
tier). There is no key on this machine. Everything buildable without one is built.

When it exists, two rules from the plan file carry over:

- **Pin the judge model and version.** Swapping judges mid-project invalidates every historical
  row — the same trap as swapping the golden set (`D65`) or the vector store (`D31`, where 4 of
  19 probe questions returned different top-5).
- **Report the judge's agreement with a human on ten hand-checked items.** LLM judges agree with
  people ~85–92% of the time. The precedent is `§H CLOSED` — the golden signature closed on a
  risk-weighted spot-check of ten, and `g065` is why that sample was worth taking.

**And one decision is waiting on a person:** whether H ships.

---

## After this you can say

- **"My system scores 0.43, and 0.64 is retrieval's ceiling."** The 21 points between them are
  generation's, and no retrieval metric can see them.
- **"Improving retrieval made one defect's count go up, and that's arithmetic."** The cell counts
  refusals *with the page in the prompt*; better search makes more questions eligible. Compare
  the rate, not the count.
- **"Two of the seven questions Phase 3 fixed are now refused with the right page in hand."**
- **"Moving one sentence beat rewriting it."** Same words in the user turn instead of the system
  message: end to end 0.43 → 0.52, 9↑ 0↓, p = 0.0039, uncited 67% → 10%.
- **"My first version of that number was wrong and I found it."** The model cited its own
  refusal; a prefix detector scored six declines as answers. `D76`.
- **"I detect invented code without a second model"** — API calls checked against the pages that
  were actually retrieved.

## Do not say

- **"My RAG system is 64% accurate."** That is the ceiling, and it is the single most misleading
  sentence available about this project.
- **"I fixed hallucination."** Fabrication count is unchanged at 2. What changed is its
  *severity*, and that is a different and more honest claim.
- **"I improved the prompt."** Say **what** changed — its position — because *"I made the
  instruction stronger"* is the branch that was measured and did **nothing** (variant E).
- **"The reranker/chunking could fix the remaining misses."** `D70` closed that: the 17 absent
  answers are not broken chunks, and the questions retrieval *does* find have broken chunks at
  the same 2% rate.
- **"LLM-as-judge grades my answers."** Not yet. Everything in this file is deterministic —
  brackets and symbol matching. That is a strength worth stating plainly, not a gap to hide.

---

## Where the rest lives

| | |
|---|---|
| [`../phases/PHASE-4.md`](../phases/PHASE-4.md) | the plan, with every measured table |
| [`09-DECISIONS.md`](09-DECISIONS.md) | `D71`–`D77` in full, each with its interview question |
| [`15-IMPROVE.md`](15-IMPROVE.md) | §R7 — the retrieval work this phase sits on top of |
| [`14-MEASURE.md`](14-MEASURE.md) | §R6 — Phase 2's scorecard, where the 15-point gap was first seen |
| `rag/judge.py` | citations and groundedness — no model, no key |
| `rag/compare_prompts.py` | the prompt lab, `--golden` |
