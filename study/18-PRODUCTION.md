# §R10 — Phase 6: production — a gate, a priced router, and a demo

Plan and measurements: [`../phases/PHASE-6.md`](../phases/PHASE-6.md). Decisions: `D96` (framing,
rejected) through `D108` (Langfuse traces the live demo). **This file is the sitting; the plan is the
record.** Blocks marked `# runnable` are re-run by `tools.check_runnable`. The ones that need no model,
no network and no Qdrant are compared verbatim on every PR; the rest are listed as `ENV` with the
reason.

**Where Phase 6 ended (2026-09-14).** Both halves of the ROADMAP's finish line are met: the public demo
link answers with citations (R10.16), and on a real GitHub runner a pull request that removes the
reranker is blocked by name, with the check required on `main` (R10.7b).

**Study order:** finish [`17-AGENT.md`](17-AGENT.md) (§R9) first if you are reading the RAG sittings
in order — Phase 5 closes the agent story; this file is what you do once you have a system worth
shipping.

Three parts, in the order they were built:

1. **A quality gate** (R10.1–R10.8): a pull request that loses a golden answer cannot merge quietly.
2. **A router, priced and checked** (R10.9–R10.13): which questions go to a bigger model, what that
   costs, and whether the bigger model's answers are actually right.
3. **Shipping it** (R10.14–R10.17b): the demo page, the hosted model on all 100, the **live Modal
   link** (`D106`), keys, and Langfuse traces of real visitors (`D108`).

---

## Stop — how to read the ids and rates in this file

Same three systems as [`17-AGENT.md`](17-AGENT.md). Skim once.

### 1. Labels that are not scores

| You see | What it is | What it is **not** |
|---|---|---|
| **`R10.4`** | Section 4 of *this* sitting | A score out of 10 |
| **`D97`, `D106`…** | One design decision in [`09-DECISIONS.md`](09-DECISIONS.md) | A section number or a grade |
| **`g017`, `g050`…** | One question in the 100-item golden set | A metric family |

### 2. Rates — counts first, decimals later

Do **not** read a decimal until the section has shown what was counted. Short map:

| You will see | What was counted | Section that shows the arithmetic |
|---|---|---|
| **`58/91` → `0.64`** | Search only: answer page in the top 5 (retrieval ceiling). **Not** “the system scores 0.64.” | R10.3 |
| **`38/91` → `0.42`** | Lab one-shot: page in the five **and** local qwen answered | R10.9, R10.11 |
| **`48/91` → at most `0.53`** | Lab 38 + 10 escalated answers that agree with the verified page (upper bound) | R10.13 |
| **`53/91` → `0.58`** | Same 91, hosted nemotron answered with the page present | R10.15b |
| **`53/69` → `77%`** then **`91%`** | Judge said SUPPORTED (text-only fail → with headings pass) | R10.15b / `D107` |
| **`$1.81` / 1000** | Shadow cost of escalating every local refusal — **$0 spent**; free credits | R10.12 |

`g017` is the *question* that loses its answer page when you remove the reranker — not a rate.

### 3. Map of this file

| Section | One sentence | Read when |
|---|---|---|
| **R10.0** | Phase overview table | Starting cold |
| **R10.1–R10.8** | Quality gate: broken/fixed/moved; demo blocks `g017`; the real runner and the bug it found (R10.7b) | Before shipping code |
| **R10.9–R10.13** | Cascade router, escalation, shadow cost, supported ≠ correct | Before quoting dollars |
| **R10.14–R10.17b** | Demo page, nemotron on all 100, Modal live, keys, Langfuse | Before the live link |

**If you have ten minutes:** R10.3 → R10.7b → R10.9 → R10.13 → R10.15b.
### Golden questions this file names by id

When a later section says only `g017`, look it up here. Full text is in
`deliverables/golden.json`.

| id | answerable? | the developer's question (short) | why this file names it |
|---|---|---|---|
| **`g017`** | yes | joinedload returns duplicate parents — do I need `unique()`? | **CI gate demo:** removing the reranker drops this answer out of the top 5 |
| **`g050`** | yes | `engine.execute` gone — use connection instead | Over-refusal with the page in hand; demo "declines" example; escalation gain |
| **`g016`** | yes | `row.keys()` AttributeError — where did keys go? | Judge said SUPPORTED; **2.0.51 says the method is gone** (supported ≠ correct) |
| **`g007`** | yes | `MetaData(bind=engine)` TypeError — how do I `create_all`? | Judge said UNSUPPORTED/PARTIAL; **2.0.51 agrees it is removed** |
| **`g044`** | yes | `autoload=True` without `autoload_with` — 2.0 way? | Human review found the sheet hid a **heading** the model had seen |
| **`g053`** | yes | Flask-SQLAlchemy `User.query.get(1)` in 2.0? | The **one** question nemotron lost vs qwen (stricter decline) |
| **`g056`** | **no** | Query property for models in 1.4–2.0 | Fabrication in prose (not caught by `check_api`) |
| **`g065`** | **no** | Create table and view in the same migration | Fabrication: invented `op.create_view` (Phase 4 / agent `check_api`) |
| **`g087`** | yes | `server_default` missing in `__dict__` after flush | Escalation / nemotron checkable **fail** on 2.0.51 |
| **`g099`** | yes | `MappedAsDataclass` + callable `default=` | Same: checkable **fail** on 2.0.51 |

Other ids in tables below (`g013`, `g021`, …) are the same kind of thing: one golden question each.
If you need the wording, open `golden.json` — do not invent what `g021` "means" from the id alone.

### Words this file uses that are not Python

Same rule as [`17-AGENT.md`](17-AGENT.md): the table is the short meaning; the section is the story.
Do not treat these as synonyms for each other.

| Word | Plain meaning (show, then name) | Where the story is |
|---|---|---|
| **CI / check / gate** | GitHub can run a program on every pull request. If it exits non-zero, the check is red. A **gate** is a check that is allowed to **block merge** when answers get worse — not only when code crashes. | R10.1–R10.3 |
| **pull request (PR)** | “Please merge these commits into `main`.” | R10.1 |
| **baseline** | The saved scorecard of “how search ranked each golden question *before* this PR.” The gate compares the PR against that file, not against a moving average. | R10.3, R10.5 |
| **broken** | A question whose answer page **was** in the top 5 before, and **is not** after the change. Gate fails on any broken. | R10.2–R10.4 |
| **fixed** | The opposite: was missing from the top 5, now found. | R10.2 |
| **moved** | Still found (or still missing), but the five page ids reshuffled. Reported; does not fail the gate by itself. | R10.3 |
| **reranker** | A second model that reorders search hits. Here it only promotes one strong candidate into seat 5. Turning it off breaks `g017`. | R10.3, R10.7 |
| **router** | Policy for “which questions go to a bigger, costlier model?” | R10.9 |
| **predictive routing** | *Before* answering, guess which questions are hard (e.g. low search score) and send those. **Failed** here — it mostly picked missing pages. | R10.9 design A |
| **cascade** | Let the cheap local model answer first; send to the bigger model **only if it refused**. Catches every page-present over-refusal. | R10.9 design B |
| **escalate** | Actually call the bigger model on those routed questions. | R10.11 |
| **shadow cost** | Tokens × published $/token for calls that ran on **free** credits. What you *would* pay if billed — **$0 was spent**. | R10.12 |
| **SUPPORTED / PARTIAL / UNSUPPORTED** | Judge grades: answer fully on the given pages / partly / not. **Not** “correct when you run SQLAlchemy.” | R10.11, R10.13 |
| **faithfulness** | “Does the answer stick to the pages it was given?” — the judge’s job. | R10.15b |
| **correct / checkable** | “Does the answer’s central claim hold on real `sqlalchemy==2.0.51`?” — a small Python check, not the judge. | R10.13, R10.15b 4f |
| **page present / page absent** | Was the verified answer chunk among the five pages in the prompt, or not? | R10.9 |
| **over-refusal** | Page present, model still declined. | R10.9 (`g050`) |
| **fabrication** | Answered an unanswerable question (or invented an API). | R10.12 (`g056`/`g065`) |
| **in-memory search** | Dense search over `embeddings.npy` in the process — no Qdrant container. Required for the hosted demo. | R10.14 |
| **cold start** | First request after the container was asleep: load models, maybe download weights — can take minutes. | R10.16 |
| **required check** | Repo setting: a red gate **cannot** be merged. The code lives in the repo; the setting lives on GitHub. `quality gate` has been required on `main` since 2026-09-14. | R10.1, R10.7b |
| **cold / warm cache** | Cold: the runner has no saved embeddings and must compute all 3284 (about 1–2 hours). Warm: it restores them and only scores (about 2 minutes). | R10.6 |
| **trace** | One saved record of one visitor's question: what was asked, which five pages came back, what the model wrote, tokens, time. Not a grade. | R10.17b |

---

## R10.0 — Where to start

**Plain job.** Up to Phase 5 this repo measured a system. Phase 6 asks the questions a team running
it would ask: *can a bad change sneak in? would a bigger model help, and at what price? can a stranger
use it?*

**The whole phase on one page** (fractions first; decimals are the same count written short):

| step | the question | the answer, measured | decision |
|---|---|---|---|
| 1 | does the *shape* of the prompt move the over-refusals? | a little, but it makes the model more willing to guess, not better at reading | `D96`: rejected |
| 2 | can a change that loses an answer merge quietly? | no: removing the reranker is blocked by name on *"joinedload… do I need unique?"* (`g017`) | `D97` |
| 3a | which questions should go to a bigger model? | the ones the small model *refused*, not the ones whose search scored low | `D98` |
| 3b | does the bigger model answer them? | **16 of 20** answered; only **10 of 16** fully supported by the pages | `D99` |
| 3c | what does escalating every refusal cost, and does it add fabrications? | shadow cost **$1.81 per 1000 queries** if billed (**$0 spent**); **0** new fabrications | `D100` |
| 3d | are those answers *correct*, not just supported? | **10 of 16** agree with the human-verified page → at most **48 of 91** end to end (lab alone was **38 of 91**) | `D101` |
| 4 | can a stranger use it? | **yes — live on Modal** (HF Gradio returned HTTP 402 on free); in-memory search gated first | `D102`, `D106` |
| 4d | what does the hosted model score on all 100? | **53 of 91** vs qwen's **38 of 91** (16 gained, 1 lost); **0** fabrications; judge **53 of 69** supported under text-only (bar 80%) | `D104` |
| 4e | judged by the SAME judge, is the bigger model more faithful? | no: **level** (qwen **37 of 47**, nemotron **36 of 47**; paired 3 vs 6) | `D105` |
| 4f | are its 53 delivered answers right when run? | **47 of 51** checkable pass; the judge's grade does not predict which | `D105` |
| 4g | does the judge see what the model saw? | no, it never saw headings; given them, nemotron **53 of 69 → 63 of 69**; still level with qwen | `D107` |
| 4h | does Phase 4's judge change when given headings? | no: prompt D **36 → 38 of 47**, H **56 → 57 of 61**, under the "matter" bar; Phase 4's figures stand | Round 22 |
| 2, live | does the gate work on a real GitHub runner? | yes: a no-retrieval PR **moved 0**; the reranker PR **BLOCKED `g017`**, after fixing a scorer bug the first run exposed | `D97` |
| 5 | what do real visitors do? | every question on the live page is a Langfuse trace; not an evaluation | `D108` |

**Who does what in this phase.** Several models appear, and mixing them up is the fastest way to say
something false:

| role | model | where it runs | why this one |
|---|---|---|---|
| writing this repo's code and docs | Claude | this conversation | the project itself never calls Claude |
| **the system's generator** (lab **38 of 91**) | `qwen2.5-coder:7b` | Ollama, local | free, fits the lab's GPU; every local end-to-end number is this model |
| search | `BAAI/bge-m3` + BM25 + `BAAI/bge-reranker-base` | local | Phases 1–3 |
| the **bigger model** escalations go to, and the hosted demo's generator | `nvidia/nemotron-3-ultra-550b-a55b` | NVIDIA API, free credits | the largest model the key could actually call (most returned 404); measured on all 100 in R10.15b |
| the **judge** whose verdicts count | `openai/gpt-oss-20b` | NVIDIA API | a different lab from every model it grades |
| a second judge, for agreement only | `gemma4:e4b` | Ollama, local | Phase 4's judge |
| abandoned | `gemini-3.7-flash` | Google, free tier | 20 calls a day stopped the run at 7 of 20 (R10.11) |

**What did NOT change.** The golden set is the same 100 questions. The shipped prompt is the same.
Nothing here retrains a model or edits the corpus.

---

**PART 1 — THE QUALITY GATE**

## R10.1 — What "CI gating" means, starting from a pull request

A **pull request** (PR) is a proposal: *here are my commits, please merge them into `main`.* GitHub
can run programs against those commits before anyone merges, and show a green tick or a red cross
next to each one. Those programs are **checks**. The file that says what to run is a **workflow**,
in `.github/workflows/`.

This repo already had four checks in `ci.yml`: the tests, the `# runnable` blocks, the 2.0 evidence,
the Docker image. They answer *"is the code broken?"*. None of them answers *"did the answers get
worse?"*. A PR could delete the reranker and every one of the four would stay green.

**Gating** means a check whose red cross **blocks the merge**. Technically, blocking is two things,
and they live in two places:

```
the check      .github/workflows/gate.yml runs rag.gate, which exits 1 on any broken item   (in the repo)
the blocking   branch protection on main lists "quality gate" as a required status check  (a GitHub setting)
```

A check without the setting draws a red cross that anyone can merge past. The setting without the
check has nothing to wait for. Since 2026-09-14 `main` requires five checks: `tests`, `2.0 evidence`,
`image builds`, `docs reproduce`, and `quality gate`.

---

## R10.2 — The gate in Python and SQL terms

Two tables, one row per golden question:

```
baseline (the branch you merge INTO)        this run (your PR)
id     answerable  rank                     id     answerable  rank
g017   true        5                        g017   true        6
g013   true        3                        g013   true        3
g056   false       -                        g056   false       -
```

Join on `id`. For each answerable row, ask one yes/no question on both sides: **was the answer page
in the top 5?** Rank 5 is yes, rank 6 is no, because `DEFAULT_K = 5` is how many pages reach the
prompt.

```
was yes, now no    -> BROKEN   the check fails
was no,  now yes   -> FIXED    reported
same on both sides -> unchanged (or MOVED, if the top 5 ids reshuffled)
```

In SQL it is one query:

```sql
SELECT b.id
FROM baseline b JOIN this_run r USING (id)
WHERE b.answerable AND b.rank <= 5 AND (r.rank IS NULL OR r.rank > 5);
-- any row returned = the gate fails
```

That is the whole gate. `rag/gate.py`, `paired()` and `blocked()`.

---

## R10.3 — The demo: remove the reranker

**Plain job.** Show one change that should fail the gate — and that the average alone would miss it.

### What we ran (before any decimal)

| | |
|---|---|
| **Change** | Turn the reranker **off** (`rag.score --no-rerank`) — same search otherwise |
| **Compared to** | Committed baseline: search **with** the shipped reranker |
| **Questions** | Same 100 golden; only the **91** answerable count in the fraction |
| **Machine for the rows** | Mac; rows committed so any box can re-check the verdict with no Qdrant. Repeated later as a real PR on a GitHub runner, same verdict (R10.7b) |

### What we counted

For each answerable question: was the verified answer page in the **top 5** before? After?

```
  with reranker (baseline):     answer page in top 5 on  58 of 91
  without reranker (this run):  answer page in top 5 on  57 of 91

  newly FIXED (was out, now in):   0
  newly BROKEN (was in, now out):  1   ← g017
  MOVED (still in or still out, ids reshuffled):  3
```

**Now the decimals** (same fractions, short form — and why they are not the gate):

| | fraction | often written |
|---|---|---|
| baseline | **58 / 91** | **0.64** |
| no reranker | **57 / 91** | **0.63** |

**What `±0.097` is.** 91 questions is a small sample. If you wrote another 91 questions of the same
kind, the share found in the top 5 would not come out at exactly 58 of 91 again. The Wilson interval
is the usual way to say how far it could plausibly move at 95% confidence. For 58 of 91 it runs from
**0.535 to 0.729**, which is `0.64 ± 0.097` (`rag/score.py`, `wilson_half_width(58/91, 91)`).

`0.63` is well inside that range. A gate that compared averages would call this noise and **pass**.
The gate does not compare averages; it counts **broken**.

The ROADMAP's picture: *"open a PR that removes your reranker, and film CI rejecting it."* The
committed rows reproduce that verdict:

```
# runnable: uv run python -m rag.gate --baseline deliverables/gate-baseline.json --rows deliverables/gate-demo-no-rerank.json; echo "exit $?"
QUALITY GATE — retrieval, recall@5, paired by golden id

  baseline   58/91 = 0.64
  this run   57/91 = 0.63

  fixed        0  -
  broken       1  g017
  moved        3  (top-5 ids changed, found/not-found did not)
  unpaired     0  (new items, no baseline yet)
  exact McNemar p = 1.000  (context only; the gate reads `broken`)

BLOCKED — 1 golden answer(s) left the top 5: g017

baseline provenance: {"machine": "Darwin-arm64", "embed_model": "BAAI/bge-m3", "embed_revision": "5617a9f61b028005a4858fdac845db406aefb181", "embed_device": "mps", "rerank_model": "BAAI/bge-reranker-base", "rerank_revision": "2cfc18c9415c912f9d8155881c133215df768a70"}
exit 1
```

**Read every line of the report:**

- **`broken 1 g017`.** The item — *"joinedload collection query returns duplicate parents, do I
  need unique?"* This is `D68`'s only fix, so the gate blocks exactly the question the reranker
  was shipped to answer.
- **`moved 3`.** `g013`, `g037`, `g041` had their top 5 reshuffled, still found or still not found.
  Not a failure. It is the line to read first when a result surprises you.
- **`p = 1.000`.** One broken, zero fixed: no evidence of a *systematic* change. The gate ignores
  p on purpose. A statistically invisible loss of one answer is still a lost answer for whoever asks
  that joinedload/`unique()` question (`g017`).
- **`exit 1`.** What makes GitHub draw the red cross. A gate that prints BLOCKED and exits 0 is a
  comment. There is a test for exactly that (`test_main_exits_nonzero_and_writes_the_job_summary`).

**What the reranker actually does for `g017`**, the top 6 chunk ids from the two committed files:

```
with reranker      c02103 c02890 c01347 c00965 [c01603] c00970     answer at rank 5: reaches the prompt
without            c02103 c02890 c01347 c00965  c00970 [c01603]    answer at rank 6: does not
```

**One swap at the seat 5/6 boundary.** That is the entire lever (`D68`: promote into seat 5 from
ranks 6–10 when the cross-encoder margin is at least 0.8). Same shape as `backref` at rank 6 in
Phase 1 (§R4.3): the page was found, one seat short.

---

## R10.4 — Why one broken item fails, even when five others were fixed

**Side by side, two hypothetical PRs** (invented, to show the shape, not a measurement; the arithmetic
is real). Both start from the baseline's 58 of 91:

```
PR A    fixed 5   broken 0    58 + 5 - 0 = 63 of 91    0.64 -> 0.69    PASS
PR B    fixed 6   broken 1    58 + 6 - 1 = 63 of 91    0.64 -> 0.69    BLOCKED
```

Same average, because an average only sees the total. PR B took an answer away from someone. The gate does not say PR B is wrong. It says
**a human must look at `broken` and decide**, instead of the loss riding in unseen under a better
average.

**This is not new strictness invented for CI.** It is the rule this repo already applied by hand:
Round 14 wrote *one regression is a hold* before its data, and that rule is what still holds prompt
`H` back (`D83`); it is what rejected the source framing (`D96`: `g043`).

**What it is not:** a claim that recall must never drop. A PR that deliberately trades `g017` for
something bigger can still merge. It just cannot merge *silently*.

---

## R10.5 — The ruler cannot be moved by the thing being graded

The obvious way to pass a gate that joins on id: **delete the item you broke.** Nothing to join,
nothing broken. Or flip it to `answerable: false`, and it stops being graded.

```
baseline: g017 answerable rank 5      PR deletes g017 from golden.json     naive join: PASS
                                                                          this gate: BLOCKED, "ruler changed"
```

Both fail as `ruler changed` (`missing`, `relabelled`). New items pass as `unpaired`, because there
is no baseline for them yet. And **the baseline is read from the base branch**, never from the PR's
own copy of `gate-baseline.json`, or a PR could rewrite the baseline to match what it broke.

This is `D06` enforced in CI: who verifies the golden set is a human decision, and a PR that edits
it should be reviewed as that, on its own.

---

## R10.6 — What CI can and cannot run, and where the hours go

| step | on a CI runner | cost |
|---|---|---|
| fetch corpus, chunk | yes, same steps as `docs reproduce` | small; not separately timed |
| **embed 3284 chunks with bge-m3** | yes, **CPU only** | **the long pole**: 1106 s on the Mac's 10-core CPU (`D97`); **2,737 s and 6,560 s** on two GitHub runners |
| Qdrant | yes, a **service container**, same `v1.19.0` pin as Compose (`D41`) | seconds |
| BM25, query embedding, reranker for 100 questions | yes, CPU | 626 s and 1,467 s cold; **48 s** warm |
| **generation (Ollama)** | **no** | not graded here |

**The runner times, measured on 2026-09-14** (`PHASE-6.md`, "The gate on a real runner"):

```
                              embed      score     whole job
PR #29, cold cache           2,737 s     626 s     3,442 s  = 57 min
PR #30, cold cache           6,560 s   1,467 s     8,089 s  = 135 min
PR #30 re-run, warm cache    skipped      48 s       123 s  = 2 min
```

**Why two cold runs of the same work differ by more than 2×** (`6560 ÷ 2737 = 2.4`): GitHub hands
each job whichever machine is free, and they are not identical. So quote a range, not one figure.
**Why the warm run is 2 minutes:** it restores the saved vectors and skips the embedding entirely.
**What is not explained here:** why scoring itself took 626 s cold and 48 s warm. The record does not
break that time down, and a guess is not a measurement.

**Why it starts on every PR but only works on some.** The gate first used GitHub's `paths:` filter, so
a docs-only PR never started it. That breaks once the check is required: a required check that never
starts never reports, and GitHub waits for it forever, freezing every docs PR. So `gate.yml` now always
starts, a small first job (`did retrieval change?`) diffs the PR against its base, and the real job is
**skipped** when no retrieval file changed. GitHub counts a skipped required job as passed.

**The embeddings are cached**, keyed on exactly what they are a function of: the chunk file's bytes,
the model and revision, the window, normalisation, and the source of `embedding_input()`. A PR that
only changes retrieval code (the reranker demo) never re-embeds. A PR that changes `rag/chunk.py`
pays the full cost, and that is correct: it changed the thing the cache holds.

**The cache had a trap, found by reading the workflow (`D97`).** GitHub's usual cache step saves at
the *end* of the job, and only if the job succeeded. A gate exists to fail. So a PR that the gate
blocks would throw away the hours of embedding it just paid for, and the next push would pay them
again. The fix is two separate steps, restore at the start and **save straight after the embedding**,
before the gate has a chance to fail anything:

```
restore cache  ->  embed (only on a miss)  ->  SAVE cache  ->  score  ->  gate (may fail)
```

**What did NOT happen:** the vectors were not committed (`D11`, `D36`), and no GPU was rented.

**Why generation is not in the gate:** `D83`. Retrieval reproduced exactly across two machines;
generation reproduced nowhere. A check that flips depending on which runner GitHub assigns would be
switched off within a week, which is how measurement rules die.

---

## R10.7 — The bug the gate found before it ever ran

`rag/rerank.py`, since 2026-08-21:

```python
# Pinned like embed.MODEL_REVISION — changing it means re-measure, not retune.
MODEL_ID = "BAAI/bge-reranker-base"
...
_MODEL = CrossEncoder(MODEL_ID, device=embed.pick_device(None))     # no revision
```

The comment said pinned. **Nothing was pinned.** On one Mac with one cached snapshot, that never
mattered. On a CI runner, every cold cache downloads whatever the Hugging Face repo's `main` points
at *that day*. The reranker's only contribution is `g017`, decided by a margin of 0.8 at one seat
boundary, so a new upload could flip it with no code change, and **the gate would fail an innocent
PR.**

Now `MODEL_REVISION = "2cfc18c9…"`, passed to the load, and a test asserts the *load* receives it
(asserting the constant exists would have passed under the old bug). **Re-scored: 0.64, 7↑ 0↓,
p = 0.016, the same seven ids.** Pinning changed nothing, because it pinned what was already
there.

**The lesson, plainly:** a comment is a claim. `check_runnable` checks blocks and has no opinion
about comments. This one was wrong for three weeks and green the whole time.

---

## R10.7b — The bug the real runner found: the gate graded its own settings

**Plain job.** R10.3's demo was produced by *running the scorer with a flag* (`rag.score --no-rerank`).
A real pull request does not do that. It changes the code that users get. So the demo was repeated the
way a real change would arrive, as PR #30 on GitHub, and **the gate passed it.**

### What PR #30 changed

One default, in the function every user path calls:

```
rag/index.py, the PR's only file:
-    rerank: bool = True,
+    rerank: bool = False,   # DEMO PR: the reranker removed. The quality gate must block this.
```

`rag.ask` and the live page call `index.retrieve` without saying `rerank=`, so after this PR users get
no reranker. `g017` should lose its answer page. The gate should block.

### What the gate did: PASSED, `0.64`

The scorer did not call the function the way users call it. Before the fix, `rag/score.py`:

```python
def score_items(..., hybrid: bool = True, rerank: bool = True):
    ...
    index.retrieve(q, limit=DEPTH, hybrid=hybrid, rerank=rerank)    # always says rerank=True
```

Side by side, the two callers after PR #30:

```
rag.ask / the live page     index.retrieve(q)                  -> uses the new default: rerank=False
rag.score (the gate)        index.retrieve(q, rerank=True)     -> overrides it: reranker still on
```

**So the gate graded the scorer's own settings, not the shipped system.** A PR that turned the reranker
off for every user would have merged with a green tick.

### The fix (commit `b9ea135`, test first)

```python
def score_items(..., hybrid: bool | None = None, rerank: bool | None = None):
    ...
    overrides = {k: v for k, v in (("hybrid", hybrid), ("rerank", rerank)) if v is not None}
    index.retrieve(q, limit=DEPTH, **overrides)     # passes nothing unless a flag asked
```

`None` means "whatever `index.retrieve` ships". Only `--no-rerank` or `--dense-only` sets a value. The
test that pins it, `test_the_scorer_grades_the_shipped_defaults_unless_a_flag_asks_otherwise`, swaps in
a fake `retrieve` that records its keyword arguments, and asserts two things: with no flag the scorer
passes **nothing** (`{}`), and with flags it passes exactly `{"hybrid": False, "rerank": False}`.

**Why the baseline did not move.** The shipped defaults are hybrid on and reranker on, which is exactly
what the old code passed explicitly. The fix changes *which* settings get graded only when a PR changes
the defaults, and that is the case the gate exists for.

### PR #30, re-run on the fixed scorer

```
QUALITY GATE — retrieval, recall@5, paired by golden id

  baseline   58/91 = 0.64
  this run   57/91 = 0.63

  fixed        0  -
  broken       1  g017
  moved        3  (top-5 ids changed, found/not-found did not)
  unpaired     0  (new items, no baseline yet)
  exact McNemar p = 1.000  (context only; the gate reads `broken`)

BLOCKED — 1 golden answer(s) left the top 5: g017
```

(Pasted from the runner's log into `PHASE-6.md`; it needs a runner, so it is not a `# runnable` block.)
It is the same report, line for line, as R10.3's locally committed demo. **PR #30 stays open and
unmerged as the record.**

**What did NOT happen.** No test caught this, and no reading did. The scorer's tests either handed it a
fake `retrieve`, or (the two end-to-end tests that use Qdrant) passed `hybrid=False, rerank=False`
explicitly. Not one called the scorer with no flags and checked what reached `index.retrieve`, which is
the only call the gate makes. It surfaced only because the demo was run as a real PR instead of a flag. **A gate is checked by feeding it the
change it exists to stop, in the form that change would really take.**

---

## R10.8 — The machine question (`D97`)

The baseline rows were produced on the Mac: **MPS** for embeddings, queries and the reranker. The
runner will use a **CPU**. Two different pieces of hardware doing float arithmetic can disagree in
the last digits, and at a rank 5/6 boundary decided by a 0.8 margin, the last digits can matter.

**Why that would be fatal:** a phantom `broken` on every PR, from the hardware, not the code. `D83`
measured MPS and CUDA agreeing exactly; CPU had never been measured.

**So it was measured.** All 3284 chunks re-embedded on the Mac's CPU into a throwaway collection,
and the 100 questions scored with every model on CPU:

```
vectors bit-identical to MPS      0 of 3284      largest difference 0.000013
top-20 chunk lists identical      100 of 100
gate against the MPS baseline     fixed 0  broken 0  moved 0  -> PASSED
```

**Read the two lines together.** Not one vector is the same number. Not one ranking changed. The
hardware really does produce different floats, and the differences are far too small to swap two
chunks. Saying "CPU and GPU give the same vectors" would be false; "they give the same rankings
here" is what was measured.

**That was the Mac's CPU, not a runner's.** A GitHub runner is a Linux x86 CPU with a different maths
library from Apple's, so the question stayed open until a real run.

**Then the runner answered it (PR #29, 2026-09-14).** That PR changed the workflow and no retrieval
code, so any movement would have come from the hardware:

```
ubuntu-latest, CPU     58/91 = 0.64    fixed 0   broken 0   moved 0   -> PASSED
Mac baseline, MPS      58/91 = 0.64
```

`moved 0` means that for all 91 answerable questions the top-5 list came out identical, same ids in the
same order, to the Mac GPU's (`rag/gate.py` compares `hits[:5]` as lists; unanswerable items are skipped). **What it is not:** a
promise about every future runner image. If a PR that touches no retrieval code ever shows `moved`
items, this is the first suspect, and `D97` names the fallback design.

---

---

**PART 2 — THE ROUTER, PRICED AND CHECKED**

## R10.9 — Routing: which questions are worth sending to a bigger model? (`D98`)

**Plain job.** A router keeps most questions on the free local model and sends some to a stronger,
paid one. The ROADMAP wants the sentence *"routing saves $X at a Y-point quality cost."* Before any
dollar figure there is a simpler question: **does the router send the right questions?**

### What we ran (before any design name)

| | |
|---|---|
| **Machine** | Lab PC |
| **System** | One-shot pipeline, shipped prompt D (always searches; no tools) |
| **Questions** | Same 100 golden |
| **Generator** | Local `qwen2.5-coder:7b` |

### What we counted on that run

Of the **91** answerable questions:

```
  page in the five AND model answered     38 of 91     (often written 0.42)
  failed somehow                          53 of 91

  of those 53 failures:
      answer page was in the five         20           ← only these can a bigger model fix from the same pages
      answer page was NOT in the five     33           ← bigger model gets the same wrong five pages
```

**Two ways a question fails — named example for each:**

```
page ABSENT   33 answerable: search never put the answer page in the prompt.
              Send one to a stronger model and it gets the same five wrong pages.
              It can only answer from memory — the move that produced g065's invented
              op.create_view on 2026-08-21.

page PRESENT  g050, "engine.execute select gone AttributeError use connection instead":
              the answer page WAS in the prompt, and the local model replied
              "The sources do not answer this."  One of D72's over-refusals.
              A stronger model reading the same page plausibly answers it.
```

**Routing can only fix the second kind** (with a later correction in R10.13). That sentence decides
everything below.

### Two designs, rules written before the numbers (`PHASE-6.md` Step 3a)

Show what each does, then the name:

| Design | What it does in plain words | Name |
|---|---|---|
| **A** | *Before* answering, score the five pages; send the **30** questions whose best page looks weakest | **predictive** routing |
| **B** | Let the local model answer first; send only the questions it **refused** | **cascade** (escalate on refusal) |

```
# runnable: uv run python -m rag.route --report
local pipeline (lab, Round 16, prompt D): 38/91 delivered, 53 failures, 20 of them with the page PRESENT

A  predictive, route 30 lowest max-CE
   failures caught      20 of 53   bar 27  -> FAIL
   random routing       median 16, 95th percentile 20, P(>= 20) = 0.057  (exact hypergeometric)
   caught, page present 3 of 20
   routed but delivered locally 6, routed unanswerable 4

B  cascade, escalate on refusal
   escalated            53 of 100
   answerable, page present 20 of 20   page absent 26
   unanswerable escalated   7
   failures never escalated 7  (answered without the page)
```

**Read it line by line:**

- **`53 failures, 20 with the page PRESENT`.** Only those 20 are the kind a stronger model can fix.
- **A catches 20 of 53; the bar was 27.** Random picking of 30 questions out of 100 catches, on
  average, 30% of the 53 failures: `30 × 53 ÷ 100 = 15.9`, which is why the report's median is 16. It catches
  20 or more only 5.7% of the time. So the score is a weak real signal, and it still fails the bar.
- **A's `caught, page present 3 of 20`.** This is the damning line. Random picking would catch about
  `30% of 20 = 6` of those 20; the predictor caught half that. **A low retrieval score is exactly what a missing page looks like**, so the
  predictive router sends the questions no model can fix and keeps the ones one could.
- **B's `page present 20 of 20`.** Every fixable failure is a refusal, by definition, so the cascade
  catches all of them.
- **B's `escalated 53 of 100`.** The price: 26 are honest refusals with the page absent, and 7 are
  unanswerable questions the local model correctly declined. Escalating those invites a
  fabrication.
- **B's `failures never escalated 7`.** Questions answered without the page. A cascade on refusal
  cannot see a confident wrong answer.

**What did NOT happen.** No strong model answered anything and nothing was priced. This step decides
*which* questions a router should send. Whether sending them helps, and what it costs, is Step 3b.

**The random-routing baseline above had a bug in its first version.** R10.10 is that bug.

**Say this:** “I don't predict which questions are hard. I tested that: routing on retrieval scores
mostly picked questions whose answer page was missing, which a bigger model can't fix from the same
pages. So the router is a cascade. The free model answers first, and only a refusal gets escalated.
That catches every case where the page was there and the small model declined.”

**Do not say:** “Routing improves quality by X” from this section alone. This section decides
*which* questions to send. What sending them buys is R10.11–R10.13.

**A correction that came later (`D101`).** "Routing can only fix the second kind" turned out too
absolute: 6 of the 26 page-absent refusals got answers that agree with the verified page (R10.13).
The cascade decision stands, and is stronger for it.

---

---

## R10.10 — The statistics bug: "pick 30 of 100" is not "each one 30% of the time"

**Plain job.** To say the predictive router beat chance, you need to know what chance looks like: if
you picked 30 of the 100 questions *at random*, how many of the 53 failures would you catch? The first
version of that calculation was wrong, and the wrong version made a weak signal look like no signal.

**Start small enough to check by hand.** 10 questions, 4 of them failures, a router that picks 3:

```
# runnable: uv run python -c "
#   from math import comb
#   N, K, n = 10, 4, 3
#   right = [comb(K, k) * comb(N - K, n - k) / comb(N, n) for k in range(n + 1)]
#   wrong = [comb(K, k) * (n / N) ** k * (1 - n / N) ** (K - k) for k in range(K + 1)]
#   print('10 questions, 4 failures, a router picks 3 at random')
#   print('right  (pick 3 of 10)          caught 0..3:', ' '.join(f'{p:.4f}' for p in right))
#   print('wrong  (each failure 30% alone) caught 0..4:', ' '.join(f'{p:.4f}' for p in wrong))
#   print('wrong version: P(catch 4 while picking only 3) =', f'{wrong[4]:.4f}')
#   print('the real case, P(>= 20 of 53 caught, picking 30 of 100): right', round(sum(comb(53, k) * comb(47, 30 - k) / comb(100, 30) for k in range(20, 31)), 4), ' wrong', round(sum(comb(53, k) * 0.3 ** k * 0.7 ** (53 - k) for k in range(20, 54)), 4))
#   "
10 questions, 4 failures, a router picks 3 at random
right  (pick 3 of 10)          caught 0..3: 0.1667 0.5000 0.3000 0.0333
wrong  (each failure 30% alone) caught 0..4: 0.2401 0.4116 0.2646 0.0756 0.0081
wrong version: P(catch 4 while picking only 3) = 0.0081
the real case, P(>= 20 of 53 caught, picking 30 of 100): right 0.0571  wrong 0.1408
```

**Read the `wrong` line's last number.** It gives a **0.0081** chance of catching **4** failures while
picking only **3** questions. That is impossible, and it is the whole bug in one number. The wrong
version flips a separate 30% coin for every failure, as if each were picked independently. The real
router picks exactly 3 questions, so it can never catch more than 3.

**Check the right line by hand.** Catching all 3 means the 3 picks are all failures: there are
`comb(4, 3) = 4` ways to pick 3 of the 4 failures, out of `comb(10, 3) = 120` ways to pick any 3.
4 ÷ 120 = **0.0333**, the last number on the `right` line.

**Names, after the picture.** Picking without putting back is the **hypergeometric** distribution.
Independent coins are the **binomial**. At the real sizes the binomial has fatter tails, so it said a
chance router catches 20+ failures **14%** of the time; the truth is **5.7%**.

**How it was caught.** Not by review. The scratch script said 0.14, the committed instrument
(`rag/route.py`) said 0.06, and two numbers for one question meant one of them was wrong. The exact
formula settled it, and `test_the_random_baseline_is_hypergeometric_not_binomial` pins 0.0571.
**The lesson:** a number that comes out of a quick script and a number that comes out of the
committed tool should agree; when they do not, that disagreement is a finding.

---

## R10.11 — Does a bigger model answer the refusals it gets? (`D99`)

**Plain job.** The cascade sends a bigger model the **20** questions our small model refused *with
the right page in hand*. Same question, same five pages, same prompt, word for word. Only the model
changes. Does it answer?

### What we ran (before any rate)

| | |
|---|---|
| **Questions** | The **20** page-present refusals from the lab one-shot run (of 53 total failures) |
| **Pages + prompt** | Retrieved once; identical for both models (a test asserts the prompt is byte-identical) |
| **Small model** | Local `qwen2.5-coder:7b` — on the full 91 it delivered **38 of 91** |
| **Bigger model** | `nvidia/nemotron-3-ultra-550b-a55b` on free credits |
| **Judge** | `openai/gpt-oss-20b` (different lab from qwen and nemotron) |

**What was held fixed, side by side:**

```
                 local qwen (lab: 38 of 91)              bigger model (escalation)
question         g050 "engine.execute select gone…"      the same
pages            the same five, retrieved once           the same five
prompt           ask.SYSTEM + ask.build_prompt           byte for byte the same
model            qwen2.5-coder:7b                        nvidia/nemotron-3-ultra-550b-a55b
```

**The first attempt, and why it was abandoned.** It used Google's `gemini-3.7-flash` on its free
tier. It answered 7 questions, then returned HTTP 429 (daily quota; the free tier is 20 calls a day
per model, `D80`). Its 7 answers were all judged supported, but the judge was `gemma4:e4b`, **also a
Google model**. Viraj asked which models were in use, and that question exposed it: a Google model
grading a Google model is a weak form of grading your own homework. Both were replaced before any
answer from the new models existed, and the 7 rows are kept in a separate `…-abandoned.json` file,
never mixed in.

**Choosing the NVIDIA models honestly.** Most of NVIDIA's catalog returned **404** on this key,
including the first choices. Models were probed with *"Reply with the single word OK"* only, so
nothing about the questions was seen before choosing. The judge became `openai/gpt-oss-20b`, a
different lab from NVIDIA (the escalation model), Alibaba (qwen) and Google (gemma).

```
# runnable: uv run python -m rag.escalate --report
ESCALATION — nvidia/nemotron-3-ultra-550b-a55b on the cascade's page-present refusals (20 of 20)

  answered   16 of 20   rule >= 15  -> PASS
  refused     4   g064 g084 g103 g116
  SUPPORTED  10 of 16 judged = 62%   rule >= 80%  -> FAIL
  judge      openai/gpt-oss-20b
  judges agree on 11 of 14 (gemma4:e4b vs openai/gpt-oss-20b)
  not SUPPORTED  g013=PARTIAL g021=PARTIAL g044=PARTIAL g049=PARTIAL g099=PARTIAL g106=PARTIAL

  tokens, as returned by the API: prompt 45015, output 15624  (over 20 calls)
  shadow cost at the price snapshot: $0.0770 total, $0.00385 per escalation  (calls were free credits)
```

**Read it line by line:**

- **`answered 16 of 20 → PASS`.** The rule, written before any call, was 15. So most of these refusals
  were the small model being small, not the pages being unanswerable.
- **`refused 4`.** `g064 g084 g103 g116`: the bigger model declined too, which suggests those pages
  answer only obliquely.
- **`SUPPORTED 10 of 16 = 62% → FAIL`.** The rule was 80%. Every one of the other six is `PARTIAL`, none
  `UNSUPPORTED`: the model used the page **and added things the page does not say**. By the rule, only
  the 10 count.
- **`judges agree on 11 of 14`.** The second judge (gemma) finished 14 of 16 before timing out; the
  machine was at 10 GB of swap. The two judges give nearly the same *rate* on different *items*.
- **`tokens … prompt 45015, output 15624`.** Counted by the API, not estimated. Output includes the
  model's hidden reasoning, which is what a paid call would bill.
- **`shadow cost $0.0770`.** R10.12.

**My prediction, written first:** 14 answered and about 85% supported. Actual 16 and 62%. Both wrong,
and the second one by a lot; the prediction stays on the page for that reason.

**The six PARTIALs are for a human.** `deliverables/ESCALATE-PARTIAL-REVIEW.md` has each question,
the full answer, the judge's reason and all five pages, with the verdict line blank.

---

## R10.12 — What it costs: the shadow cost (`D100`)

**Plain job.** The calls ran on free credits and cost nothing. The ROADMAP still wants a dollar
figure, because a real deployment would pay.

### What “shadow cost” means (show, then name)

1. Count the tokens the API returned for the real calls.
2. Multiply by a **published** price per token (here: OpenRouter’s list for that model).
3. The dollar figure is what those calls *would* have cost if billed.

That product is the **shadow cost**. **$0 was spent** — free credits covered the run. The number
is a what-if, not a receipt.

**The price, and its limits.** `deliverables/prices-phase6.json` holds OpenRouter's published list
price for the model, fetched 2026-09-12 22:51 UTC: **$0.000000625 per prompt token** and
**$0.000003125 per output token** ($0.625 and $3.125 per million). It is **one reseller's price, not
NVIDIA's**, and prices change, which is why the file records where and when.


**A real cascade escalates every refusal, not only the 20.** It cannot tell which refusals had the page.
So Step 3c sent the other 33 too (26 page-absent, 7 unanswerable), and they carry their own risk: a
bigger, more willing model might *answer* an unanswerable question, which is a fabrication.

```
# runnable: uv run python -m rag.escalate --rest --report
ESCALATION REST — nvidia/nemotron-3-ultra-550b-a55b on the 33 escalations a cascade cannot tell apart

  unanswerable, answered   0 of 7   rule >= 2  -> refusals stay honest   
  page absent, answered    13 of 26   g007 g011 g016 g020 g022 g028 g036 g037 g039 g040 g058 g085 g094
  page absent, SUPPORTED   9 of 13 judged  (by those pages, NOT the verified one)
  not SUPPORTED            g007=UNSUPPORTED g011=PARTIAL g028=PARTIAL g085=PARTIAL

  tokens, as returned by the API: prompt 70210, output 19330  (over 33 calls)
  shadow cost at the price snapshot: $0.1043 total, $0.00316 per escalation
```

```
# runnable: uv run python -m rag.escalate --cascade
CASCADE — escalate every local refusal to nvidia/nemotron-3-ultra-550b-a55b

  queries 100, escalated 53 (53%)
  shadow cost $0.1812 for these 100 queries  ->  $1.81 per 1000 queries  (price snapshot; calls were free)
```

**The arithmetic, so you never have to trust the $1.81:**

```
# runnable: uv run python -c "
#   p, c = 0.000000625, 0.000003125
#   b = 45015 * p + 15624 * c
#   r = 70210 * p + 19330 * c
#   print(f'3b   45015 x {p} + 15624 x {c} = \${b:.5f}   (20 calls)')
#   print(f'3c   70210 x {p} + 19330 x {c} = \${r:.5f}   (33 calls)')
#   print(f'all 53 escalations                                  = \${b + r:.5f}')
#   print(f'the golden set is 100 queries, so per 1000 queries  = \${(b + r) / 100 * 1000:.2f}')
#   "
3b   45015 x 6.25e-07 + 15624 x 3.125e-06 = $0.07696   (20 calls)
3c   70210 x 6.25e-07 + 19330 x 3.125e-06 = $0.10429   (33 calls)
all 53 escalations                                  = $0.18125
the golden set is 100 queries, so per 1000 queries  = $1.81
```

**Read the rest of the report:**

- **`unanswerable, answered 0 of 7 → refusals stay honest`.** The rule was "2 or more means escalation
  buys fabrications". The bigger model refused all 7 unanswerable questions the small model had
  refused. (The other two unanswerable items, `g056` and `g065`, the small model *answers*, wrongly,
  so a cascade on refusal never sees them.)
- **`page absent, answered 13 of 26`**, **`SUPPORTED 9 of 13`** — by *those* pages, which did not include
  the verified answer page. R10.13 shows why that word is not "correct".

**Prediction, written first:** 3 of 7 unanswerable answered (actual **0**), 15 of 26 page-absent
(actual 13), about $2 per 1000 queries (actual $1.81).

---

## R10.13 — "Supported" is not "correct" (`D100`, `D101`)

**Plain job.** The judge is asked *"do these five pages say this?"* It is easy to read its grade
`SUPPORTED` as *"the answer is right."* Those are different questions. Show both failing in opposite
directions on real SQLAlchemy 2.0.51.

### Three words that must stay apart

| Word | Plain question | Who answers it |
|---|---|---|
| **SUPPORTED** | Do these *pages* back the answer? | The judge model |
| **correct** | Is this true of SQLAlchemy **2.0.51**? | Running the code, or a person who knows the library |
| **checkable** | Can we turn the answer’s central claim into a small Python check? | `tools/check_escalated.py` |

Two page-absent answers, run against the real library, show why “SUPPORTED” is not “right”:

```
# runnable: uv run --no-project --with 'sqlalchemy==2.0.51' python -c "
#   import sqlalchemy as sa
#   e = sa.create_engine('sqlite://')
#   with e.connect() as c:
#       row = c.execute(sa.text('select 1 as x')).first()
#       print('sqlalchemy', sa.__version__)
#       print('g016  hasattr(row, \"keys\") =', hasattr(row, 'keys'), '  row._mapping.keys() =', list(row._mapping.keys()))
#   try:
#       sa.MetaData(bind=e)
#       print('g007  MetaData(bind=engine) accepted')
#   except TypeError as ex:
#       print('g007  MetaData(bind=engine) -> TypeError:', ex)
#   " 2>/dev/null
sqlalchemy 2.0.51
g016  hasattr(row, "keys") = False   row._mapping.keys() = ['x']
g007  MetaData(bind=engine) -> TypeError: MetaData.__init__() got an unexpected keyword argument 'bind'
```

```
g016  "row.keys() AttributeError, where did keys go on result rows"
      the answer says:  row.keys() should exist in SQLAlchemy 2.0
      real 2.0.51:      hasattr(row, "keys") is False  -> the answer is WRONG
      the judge said:   SUPPORTED   (a page mentions row.keys() in another context)

g007  "MetaData(bind=engine) TypeError, how do I create_all now"
      the answer says:  2.0 removed MetaData's bind parameter; pass the engine to create_all()
      real 2.0.51:      MetaData(bind=engine) raises TypeError  -> the answer is RIGHT
      the judge said:   UNSUPPORTED   (none of the five pages say bind was removed)
```

**What did NOT happen.** The judge did not malfunction. It answered the question it was asked. The right
answer came from the model's own knowledge, which the pages do not contain; the wrong one came from
misreading a page.

**What was done about it: a reference judge, calibrated first.** The same judge read every escalated
answer against the page **a human verified** answers the question (`D06`), instead of the five
retrieved ones. Before trusting it, it had to pass on the two answers whose truth was *executed*:
`g016` (wrong) must not be `SUPPORTED`, `g007` (right) must be `SUPPORTED` or `PARTIAL`. If either
failed, the report prints no count at all (a test asserts that).

```
# runnable: uv run python -m rag.escalate --reference-report
REFERENCE JUDGE — escalated answers against the verified answer chunks (D06)

  calibration  g016 (wrong on 2.0.51) -> UNSUPPORTED   g007 (right on 2.0.51) -> PARTIAL
  calibration passed (a smoke test on two items, not a validation)
  3b page present judged 16   SUPPORTED 10   PARTIAL  6   UNSUPPORTED  0
      SUPPORTED  g006 g029 g044 g048 g049 g087 g090 g095 g099 g100
  3c page absent  judged 13   SUPPORTED  6   PARTIAL  6   UNSUPPORTED  1
      SUPPORTED  g020 g022 g036 g037 g039 g094
  3b: page judge and reference judge both SUPPORTED 7; page only g008 g050 g051; reference only g044 g049 g099

  pre-registered quote: 38 + 10 = 48/91 = 0.53 end to end (upper bound; lab delivered 38)
  NOT pre-registered, exploration: + 6 page-absent -> 54/91 = 0.59
```

**Read it:**

- **Calibration passed, weakly.** Two items is a smoke test, and the judge rejected `g016` because the
  verified page *does not mention* `row.keys()`, not because the page contradicts it.
- **3b: 10 of 16 again, but only 7 the same items.** Against retrieved pages and against verified pages,
  the *rate* is 10 both times; three answers swap in each direction. Quote the rate, not a list of
  "the ten".
- **The pre-registered quote: lab 38 + 10 reference-SUPPORTED = 48 of 91** (often written **0.53**)
  end to end, against the lab alone **38 of 91** (often **0.42**).
  An upper bound: it assumes each of the 10 is also correct on the real library, which is checked for
  none of them at this line.
- **3c: 6 of 13 page-absent answers agree with the verified page.** That corrected `D98`'s claim that
  page-absent failures cannot be fixed. Counting those six as well gives **54 of 91** (often **0.59**)
  — that figure was **not** written down before the run, so it is labelled exploration and not quoted.

**Then correctness was executed, not judged (`D103`).** Each escalated answer's central claim was
written as a check and run on 2.0.51 (`tools/check_escalated.py`, committed before its first run).
3b: **13 of 15 checkable pass (87%)**, so the 0.53 stands on executed evidence. The two failures are
answers the reference judge had called **SUPPORTED**:

```
g087  "server_default is not in __dict__ after flush by default"   2.0.51: it is (eager_defaults="auto" uses RETURNING)
g099  "a callable default= is not allowed under MappedAsDataclass"  2.0.51: accepted; the lambda becomes the value
```

And six answers it called only PARTIAL have correct central claims. **Same rate, wrong items, again.**

---

**PART 3 — SHIPPING IT**

## R10.14 — The demo searches without Qdrant, and the gate proved that is safe (`D102`)

**Plain job.** Every measurement in this repo used Qdrant, a database running in Docker. A free web
host cannot run that container. So the demo does the search itself, in memory.

### What we compared (before any claim of “safe”)

| | |
|---|---|
| **Baseline** | Qdrant search — answer page in top 5 on **58 of 91** |
| **Candidate** | In-memory exact search (`RAG_DENSE=memory`) — same 100 questions |
| **Gate rule (written first)** | `broken` must be **0** (no answerable question loses its top-5 page) |

**Why that needed proof, not assumption.** Qdrant finds nearest neighbours with an **approximate** index
(HNSW), fast but allowed to miss. The in-memory version is **exact**: multiply every stored vector by
the question's vector and sort (`vectors @ query`). Exact and approximate can return different top
fives, and a different top five is a different system from the one that was graded.

**What we counted:**

```
Qdrant (approximate)      58 of 91 found in the top 5
in memory (exact)         58 of 91; broken 0, moved 0 (every top 5 identical)
top-20 lists identical    96 of 100 (the four that differ, differ only below rank 5)
```

Run it: `RAG_DENSE=memory uv run python -m rag.score --save /tmp/rows-memory.json`, then `rag.gate`
against `deliverables/gate-baseline.json` (block in `PHASE-6.md`; it needs the embedding model, so CI
classifies it ENV). **The switch is one environment variable**; the Qdrant path is unchanged.

**What is NOT claimed.** That exact and approximate search are the same in general. They agree on this
corpus's 100 golden questions at rank 5, and that is what the demo needed.

---

## R10.15 — The demo's page, and the sentence it must always show

**Three files, and only one of them has logic.** `rag/demo.py` does everything that can be wrong, and
`tests/test_demo.py` covers it. The page is two thin files over it:

| file | what it does | what it does NOT do |
|---|---|---|
| `rag/demo.py` | search, prompt, generate, the refusal check, turning `[2]` into a link to card 2, marking cited cards, the notice | draw anything |
| `space/web.py` | serves one HTML file and one JSON endpoint, `POST /api/ask` → `demo.payload()` | decide anything about the answer |
| `space/static/index.html` | draws the JSON: status pill, answer, source cards, the notice | re-implement citation linking in JavaScript (one rule, one home: `link_citations`) |

```
question -> index.retrieve (the graded search) -> ask.SYSTEM + ask.build_prompt (the shipped prompt)
         -> a generator -> the answer, then every page it was given, each expandable
```

`space/app.py`, the older Gradio page, still runs over the same `rag/demo.py`. It is no longer what
`space/build.py` ships: Gradio was chosen for a Hugging Face Space, and Hugging Face refused that on
the free plan (R10.16), so the bundle now carries the page that was actually checked.

**The generator depends on where it runs, and the page says which, on every answer:**

| where | generator | the notice under every answer |
|---|---|---|
| your Mac (`DEMO_GENERATOR=ollama`) | `qwen2.5-coder:7b`, the measured model | this is the model the lab **38 of 91** / Mac **39 of 91** was measured on |
| a hosted page (`nvidia`) | `nemotron-3-ultra-550b` | the **38 of 91** is for a different model and does not describe these answers |

**Why the notice is a test, not a nicety.** NVIDIA's API serves no qwen model at all (catalog checked
2026-09-12), so a hosted page *cannot* run the measured model. Printing “0.42” (or **38 of 91**) next
to a model that did not produce it is the exact mistake `D95` exists to stop.
`test_the_page_always_says_the_measured_score_is_not_this_model` fails if the sentence disappears.

**A real question through the local page.** `g050`'s wording, *"engine.execute select gone AttributeError
use connection instead"*: 28.7 seconds, and the answer was **"The sources do not answer this."**
That is one of `D72`'s over-refusals, the small model declining a page it has. **The local demo shows the
measured defect, exactly as measured**, which is what a demo of a measured system should do.

**The four checks are now a script** (`tools/check_page.py`, `D105`). It uses Anthropic's
`webapp-testing` skill, installed in `.claude/skills/`: a helper starts the page, a headless Chromium
loads it at 1280 px and 400 px, and the page's own drawing functions get the inputs that can break them.
No model is involved, so it takes seconds:

```
uv run --with playwright==1.62.0 python .claude/skills/webapp-testing/scripts/with_server.py --timeout 90 \
  --server "PORT=7861 DEMO_GENERATOR=ollama RAG_DENSE=memory PYTHONPATH=. uv run --with fastapi --with uvicorn python space/web.py" \
  --port 7861 -- uv run --with playwright==1.62.0 python tools/check_page.py http://127.0.0.1:7861
```

17 of 17 pass. **It was then made to fail on purpose:** with the phone bug put back (`1fr`), the 400 px
page measured 853 px and 2 checks failed. A check nobody has seen fail is a check nobody knows works.

**The page, third version: hand-designed, four checks in Chrome (2026-09-13, `PHASE-6.md` Step 4c).**
The rules were written before the browser was opened. Two passed as written, and two found something:

| check | what was seen | verdict |
|---|---|---|
| the *engine.execute gone* example | **Declined**, 36.1 s, five cards, the refusal quoted and not rendered as an answer | pass, **and the note under it was false** (below) |
| a 400 px phone screen, one long code line in the answer | the page was **991 px wide**: the whole page scrolled sideways | **fail, fixed**, now 398 of 398 |
| Ollama unreachable | **Not answered**, "Ollama is not running", **all five cards still shown**, Ask usable again | pass |
| the notice after a reload | `qwen2.5-coder:7b` drawn as code, no stray backtick | pass |

**The phone bug, side by side.** On a narrow screen the two columns become one. The first version said
`grid-template-columns: 1fr`. That looks like "one column as wide as the screen". It is not.

```
1fr               the column may not get narrower than its widest content.
                  A code line 883 px long makes the column 883 px, the page 991 px,
                  and the visitor scrolls the whole page sideways to read anything.

minmax(0, 1fr)    the column may shrink to 0, so it is the screen's width (350 px).
                  The code block is now narrower than its line, and ITS OWN box scrolls:
                  883 px of code inside a 266 px box, measured.
```

The first check did not catch it because the real answer it got had **no code block**. The page was
398 px wide and my prediction ("fails somewhere") looked wrong. Only a synthetic answer with a long
line exposed it. **A pass on an input that could not fail is not a pass.**

**The declined note, corrected.** The note said *"The five pages it found don't answer this."* For this
exact example that is false: `g050` is one of the 19 over-refusals, so its answer page **was** among
the five. The page cannot know whether a decline is honest. Only the model made that judgment. The note
now says so, with the number that sizes it, derived from prompt `D`'s committed rows
(`deliverables/prompt-sweep-phase4.json`): **52 declines on the 100 questions (45 answerable + 7
unanswerable), and 19 of them had the right page in hand.** Those are the same 19 ids Step 4b measured.

**What did NOT happen in the error check.** Ollama was not quit: macOS refused the quit
(*"User canceled"*), and a second copy of the server would have pushed a Mac already at 14.5 of 15.4 GB
swap into a stall. So the same `web.py` was restarted with only `ask.OLLAMA_URL` pointed at a port
nothing listens on. That raises the same "connection refused" a stopped Ollama raises, through the same
`SystemExit` catch. It is a stand-in, and the check says so.

**The page, second version (Gradio), checked end to end in Chrome (2026-09-13).** Each change fixes
something seen, not imagined:

| seen | fixed |
|---|---|
| 3 of 4 example questions were measured over-refusals, so a visitor mostly saw declines | examples chosen from data: four the measured model **answered with a citation** on the Mac, one it **declines**, labelled so |
| `[1]` in an answer went nowhere | `[n]` links to source card n and **opens it** (a click handler; a plain `#src-1` link did not change the URL in Gradio, measured) |
| no way to tell which sources the answer used | cards the answer cited carry a **cited** badge |
| `:meth:`_orm.Query.get`` leaked into answers and cards | Sphinx roles shown as names (`Query.get`); the first version skipped roles because their backticks looked like inline code, **caught in the browser**, now a test |
| nothing happened for up to a minute after asking | an immediate "Searching…" message; Gradio's own "processing" label hidden |
| truncated example labels; no clear button | short full labels on buttons that ask in one click; **Clear** |
| the 20-second limit applied locally | limits apply only to the hosted backend, which spends credits |

**Known limit, measured:** a click in the first second or two after the page loads, before Gradio wires
its events, does nothing; after that the first click works (checked: question filled and "Searching…"
shown within 2.5 s).

**The page, first version** (checked in a browser 2026-09-12): the question and four real golden-set
examples on the left; on the right a coloured status (*answered* / *declined rather than guess* / *not
answered*), the answer, the generator notice, the time taken, and the five sources as numbered cards
with a version badge (2.0.51 or 1.4.52) that open to the full page text. Source text is HTML-escaped,
because the docs contain literal `<...>` that would otherwise be read as markup (a test checks it).

**A second real question through the browser:** the `g048` example (*"joinedload with a string
relationship name TypeError or removed in 2.0"*) came back **declined**, 74.4 s on a cold start, with
source [1] being exactly the answer page (*"Joining / loading on relationships uses attributes, not
strings"*). `g048` is one of the page-present refusals the router escalates (R10.11): the page shows
the same defect the measurements found.

**Is the local demo really the measured system? Measured overnight.** The whole refusal measurement
re-run through the demo's own in-memory search: **39/91 = 0.43 end to end, the same 19 over-refused
questions, the same two fabrications** as the Qdrant-based reference taken the same day. The notice is
true, not hoped.

**Run it yourself:**

```bash
DEMO_GENERATOR=ollama RAG_DENSE=memory PYTHONPATH=. uv run --with fastapi --with uvicorn python space/web.py
# then open http://127.0.0.1:7860; the first question after start-up takes about a minute
```

The built bundle runs the same way from its own folder, installed only from its own pins. Checked on
2026-09-13: `uv run python space/build.py`, then in `space/dist/`
`uv run --no-project --python 3.11 --with-requirements requirements.txt python web.py`. It answered
*query.get() moved* with `[1]`, and clicking `[1]` opened card 1.

**Two bugs found building it, both real:** the first `requirements.txt` pinned `numpy==2.5.2` (grepped
from `uv.lock`), which needs Python 3.12 while the project runs 3.11; the pins now come from what is
actually installed. And `ask.generate` calls `sys.exit` when Ollama is down, which is right for a
command line and would kill a web server, because `SystemExit` is not an `Exception`. The page now
catches it and says Ollama is not running.

---

## R10.15b — The hosted model, asked all 100 questions (`D104`)

**Start from what was missing.** The hosted demo answers with `nemotron-3-ultra-550b`. The page
could only say *"lab qwen’s end-to-end is not this model"* — honest, but no number for the model
visitors actually hit. We had asked nemotron **53** questions before, but only the ones qwen
declined (R10.11). A visitor asks anything, so the question was: **what does it score on all 100,
counted the same way qwen was scored?**

### What we ran (before any decimal)

| | |
|---|---|
| **Questions** | All **100** golden (score uses the **91** answerable) |
| **Pages + prompt** | Same five pages per question, same prompt — search identical (`D83`) |
| **Local comparison** | Lab qwen: **38 of 91** delivered |
| **Hosted model** | `nemotron-3-ultra-550b` via NVIDIA key (Mac sent the requests; generation is remote) |
| **What did NOT happen** | No retrain, no re-search, no prompt edit — only which model reads the five pages |

Rules and a prediction were committed before the first call (`51174aa`).

**Why the Mac sent the requests.** Generation is remote (NVIDIA). Search is identical on both boxes
(`D83`), so either machine would get the same answers. The Mac can run unattended; the lab does not
need to sit this one.

### How the test runs, one question walked through (`g050`)

Viraj asked how the Ollama process and the NVIDIA-key process can produce "the same kind of result".
The answer is that **they are the same process with one function swapped**. Here is `g050`, *"engine.execute
select gone AttributeError use connection instead"*, through every step.

**Step 1: search. Local, identical for both models.** `index.retrieve` finds five pages:

```
c00456 c01567 c02028 c01569 c01573        (the verified answer page is among them)
```

**Step 2: build the prompt. Identical for both.** Two messages: the rules (`ask.SYSTEM`) and the question
with the five pages pasted under it (`ask.build_prompt`). Temperature 0. About 2221 tokens.

**Step 3: send it to a model. THE ONLY STEP THAT DIFFERS.**

```
                 qwen (Ollama)                              nemotron (NVIDIA key)
function         ask.generate                               escalate.nvidia_chat
sends to         http://127.0.0.1:11434/api/chat            https://integrate.api.nvidia.com/v1/chat/completions
model            qwen2.5-coder:7b                           nvidia/nemotron-3-ultra-550b-a55b
runs on          your machine's GPU                         NVIDIA's servers (the key goes in the request header)
messages         [system: ask.SYSTEM, user: the prompt]     the same two messages, byte for byte (a test checks)
```

**Step 4: save the answer to a file.** One row per question: id, the five page ids, the answer text.

```
qwen      "The sources do not answer this. The specific thing looked for and did not find was how to
           replace engine.execute ..."
nemotron  "In SQLAlchemy 2.0, the engine.execute() method and the "connectionless" execution pattern ...
           have been removed. You must now obtain a Connection explicitly and call execute() on it. ... [2]"
```

**Step 5: score each saved answer. Same code for both, no model involved.**

```
did it decline?            ask.refused(answer)              qwen yes      nemotron no
was the page in the five?  score.rank_of_first_hit(...)     yes           yes
delivered?                 route.delivered: page AND answered   no        YES
```

**Step 6: add up the 91 answerable questions, then compare question by question.** qwen delivered 38,
nemotron 53. `g050` is one of the 16 that nemotron delivers and qwen does not.

**The commands, side by side.** Generation needs the model; everything after it reads files:

```
qwen, lab Round 16:   uv run python -m rag.compare_prompts --golden D H --save <file>   (Ollama running)
nemotron, Step 4d:    uv run python -m rag.escalate --all --generate                    (NVIDIA_API_KEY in .env)
the report, both:     uv run python -m rag.escalate --all                               (no model, no key)
```

**What did NOT happen.** The NVIDIA run did not re-run search differently, change the prompt, or score
answers with different rules. And nothing is "sent to NVIDIA to be graded against qwen": the comparison
is arithmetic on two saved files. **Nothing magical: same questions, same pages, same prompt, same
scoring, a different model writing the answer.**

**Layer 2 is the same idea one level up.** The judge takes a saved answer plus its five pages and returns
one word (`SUPPORTED`, `PARTIAL`, `UNSUPPORTED`). For nemotron that judge was `gpt-oss-20b`, also through
the NVIDIA key (`g050` came back `SUPPORTED`).

### The result, one question at a time

A question counts only if **its answer page was among the five AND the model answered** (`D72`).
Same **91** answerable questions, both models:

```
                           page among the five   answered it   fraction   often written   declined with page in hand
qwen2.5-coder:7b (lab)            58                 38        38/91         0.42                    20
nemotron-3-ultra-550b             58                 53        53/91         0.58                     5
```

**The 58 is identical, so search did not change.** The difference is the last column: qwen had the
right page in front of it **20** times and said *"The sources do not answer this."* anyway. Nemotron
did that **5** times. Retrieval got the page there both times; the bigger model reads it.

**Paired, question by question** (the same way every change in this project is judged, `D61`): **16
questions** nemotron delivers and qwen does not, **1** the other way, exact McNemar **p = 0.0003**. The
bar written first was *6 or more fixed, at most 1 broken, p < 0.05*, so the verdict is **AHEAD**.

**The one it lost, `g053`, is worth reading, because it is not what "worse" suggests.** The question:
*"SQLAlchemy 2.0 version of User.query.get(1) in Flask-SQLAlchemy?"* The right page is rank 1, and it
explains `session.query(User).get(5)` becoming `session.get(User, 5)`. It never mentions
Flask-SQLAlchemy.

```
qwen       "...is replaced with a direct call to session.get(User, 1) on the session object [1]."
nemotron   "The sources do not answer this. ... the provided sources only cover core SQLAlchemy ORM
            ... and do not mention Flask-SQLAlchemy or its model-level query property at all."
```

qwen's answer is the useful one. **Nemotron did not fail to read the page; it read the question more
strictly** than the small model did. One of the sixteen gains (`g050`, the demo's own "declines"
example) is the mirror image: qwen declined with the page in hand, nemotron answered.

### Three more numbers, each with what it is not

**Fabrications: 0 of 9.** On the 9 questions the docs cannot answer, it declined all 9. qwen answered 2
of them (`g056`, `g065`). This is not "it never makes things up"; it is 9 questions.

**Faithfulness: 53 of 69 answers SUPPORTED = 77%, which FAILS the 80% bar.** *(Restated below, "Follow-up 3": the judge had been shown page text without the headings the model saw; given them it is 91%, a PASS, `D107`.)* A second model
(`gpt-oss-20b`) read each answer against its five pages. The other 16 are all `PARTIAL` (part of the
answer goes beyond the pages); **none** `UNSUPPORTED`. Two things this is not:

- **Not "77% correct."** Supported means the pages back it up. Step 3e ran answers against the real
  library and found the judge had called two *wrong* answers supported (`D103`).
- **Not comparable with qwen's 77–92%.** Those came from a different judge. **Measured next, below:**
  the same judge on qwen's answers gives 79%, level.

**Asked twice: 19 of 20 decisions repeat, 0 of 20 texts do.** The first 20 questions were asked again
at temperature 0. The answer-or-decline decision held on 19. The wording was never identical, so a
hosted model at temperature 0 is **not** a lookup table. The one flip, `g007`, is the same fix both
times; run 1 *opened* with the decline sentence and then gave it, and the repeat opened with *"Based on
the provided sources"*. `ask.refused` reads the opening sentence, so one counts as a decline.

**A bug in my own instrument, found by the real run.** The judge's reply for `g025` was empty. It came
back `UNPARSED` and the report printed *"judged 69 of 69"*: an unreadable verdict counted as a verdict.
Fixed with a test, `g025` asked once more (`PARTIAL`). The FAIL did not depend on it: 53/68 is 77.9%,
and even a SUPPORTED retry would have been 54/69 = 78.3%.

### What it would cost on a paid plan, and what it does NOT change

**We paid nothing.** All 190 calls ran on NVIDIA's free credits. The dollar figure below is a **shadow
cost** (R10.12): what the same calls *would* cost if someone paid for them, at one reseller's list price.
It is there because free credits are a trial allowance, not a way to serve strangers: they run out, and a
public demo or a team using this for real would be billed per token.

```
215177 prompt tokens × $0.000000625  = $0.1345
 67260 output tokens × $0.000003125  = $0.2102
                                        $0.3447 for these 100 questions  ->  $3.45 per 1000
```

The cascade (R10.12) sends the bigger model only qwen's refusals, so on the same price it *would* cost
$1.81 per 1000. **Neither number was spent.**

**The demo's notice now carries this model's own numbers:** **53 of 91** end to end (often written
0.58) and **53 of 69** supported under the text-only judge (77%; later **63 of 69** with headings),
"measured
once", with the 0.42 still named as qwen's. A test recomputes both numbers from the saved rows.

**The system of record stays qwen**, and that is not an oversight: this project runs on zero paid calls,
and free credits run out. The bigger model is measured, quoted where it is used, and used only by design
choices that say so.

**Reproduce the report with no model and no network:** `uv run python -m rag.escalate --all` (reads
`deliverables/nemotron-all-phase6.json`; the full printout is in `PHASE-6.md` Step 4d).

### Two follow-ups: the same judge on both models, and running the answers (`D105`)

**Why they were needed.** Step 4d left two things open. The 77% could not be set beside qwen's number,
because a different judge graded qwen. And "supported" is only a judge's opinion that the pages back an
answer; it is not a check that the answer is right.

**Follow-up 1: the same judge reads qwen's answers.** `gpt-oss-20b` read qwen's 47 answers against the
same five pages. Nothing else changed.

```
                        answered   SUPPORTED   PARTIAL   UNSUPPORTED
qwen2.5-coder:7b (lab)     47       37 = 79%       7          3
nemotron                   69       53 = 77%      16          0
```

Question by question, over the 42 both answered: nemotron fully supported where qwen was not **3**
times, the reverse **6** times, p = 0.51. **Level.** So the bigger model does not stick to the pages
better; it answers more questions, and those answers hold up about as well. One difference is worth
naming: qwen's 3 UNSUPPORTED include `g065`, the invented Alembic recipe (`D77`). Nemotron has none at
that grade; its misses are all "goes beyond the pages", never "not in the pages at all".

**Follow-up 2: run each answer's main claim against SQLAlchemy 2.0.51.** Same method as R10.13: read
the answer, write down its main claim, turn it into code that checks the old way is gone **and** the new
way works. Take `g031`:

```
the answer says   mapper() is replaced by registry().map_imperatively()
the check does    call mapper(Old, table)            -> must raise InvalidRequestError
                  registry().map_imperatively(...)   -> must map the class
2.0.51 says       "The 'sqlalchemy.orm.mapper()' function is removed as of SQLAlchemy 2.0.
                   Use ... map_imperatively()"       -> PASS
```

**Result: 47 of the 51 checkable answers are right = 92%**, over the 80% bar written first. Two answers
could not be checked (a typing question, and one that only says the pages do not cover the question).

**The four wrong answers, each with what 2.0.51 actually does:**

```
g002  from_self replacement      the answer's own code raises NoSuchColumnError
g078  "leave SQLALCHEMY_WARN_20 unset and it runs silently"   it prints a RemovedIn20Warning anyway
g087  "server_default is not in __dict__ after flush"         on 2.0 with RETURNING, it is (eager_defaults="auto")
g099  "default= must not be a callable under MappedAsDataclass"   2.0.51 accepts one
```

`g087` and `g099` were also the two wrong answers in Step 3e, a day earlier, in different words. **A
bigger model repeats a wrong claim when the pages invite it.**

**What did NOT happen: my checks were not simply trusted.** The first run said 43 right, 7 wrong, 1
crashed. Every failure was run on its own before being counted. Three were my mistakes, not the
answers': `mapper` still *imports* on 2.0.51 (it refuses only when called), 1.4 prints a one-line summary
warning even without the variable (the specific warnings need it), and one check threw away a class it
still needed. Those were fixed, marked in the file, and listed in `PHASE-6.md`. Counting all of them as
failures anyway, it would be 43 of 51 = 84%: still over the bar.

**The finding that matters most (not planned in advance, so it is exploration):**

```
judge said SUPPORTED   ->  36 right, 3 wrong    (92%)
judge said PARTIAL     ->  11 right, 1 wrong    (92%)
```

**The judge's grade did not predict whether an answer was right.** Answers it marked "partly supported"
were right as often as the ones it marked "fully supported", and three of the four wrong answers were
marked "fully supported". So Step 4d's 77% FAIL is a grounding result, not a correctness result, and it
cannot be converted into one. Only running the code does that.

### Follow-up 3: the judge was never shown what the model was shown (`D107`)

**Start from the prompt.** For every page, the model receives three lines, not one:

```
[2] SQLAlchemy 2.0.51 — doc/build/changelog/migration_20.rst
     SQLAlchemy 2.0 - Major Migration Guide > 2.0 Migration - Core Connection / Transaction > "Implicit" and "Connectionless" execution, "bound metadata" removed

...the page text...
```

**The judge received only `...the page text...`.** The source line and the heading line were never
passed to it, in this phase or the ones before. Viraj found it by reading `g044`: his first reason said the
claim "bound metadata was removed" was not on the pages, and it is, in the heading above. The review
sheet had hidden headings from him too.

**What was measured, rules written first.** Same judge, same answers, same five pages, each page now
exactly as the model saw it (a test holds the two byte-equal). And a control, because this judge's own
repeatability had never been measured: 20 answers re-read text-only, with nothing changed.

```
noise control   20 answers read twice, text only           2 changed (both down)     limit was 2
nemotron        77% text-only  ->  91% with headings        11 up, 1 down, p = 0.0063  HEADINGS MATTER
qwen            79% text-only  ->  81% with headings         3 up, 2 down, p = 1.0
both, paired    nemotron-only supported 5, qwen-only 2      p = 0.45                   still LEVEL
```

**What it changes.** Nemotron's faithfulness is **91%, a PASS** against the 80% bar, measured on the input
it was actually given; the 77% FAIL is restated, not deleted, and the demo notice says 91%. The comparison
with qwen is still level. **What it does not say:** that headings explain each of the 11 changes. Most of
the judge's new reasons do not name a line; one names the version line (`g051`, *"confirms the same for
SQLAlchemy 2.0"*). The noise control was at its limit, so a few of the 12 changes may be noise; the evidence
is that 11 went one way.

**Then Phase 4's judge got the same treatment (Step 4h, lab Round 22, 2026-09-14).** Phase 4's
faithfulness figures came from a different judge, `gemma4:e4b`, which had also read text only. It was
re-run on the lab with each page exactly as the model saw it, same saved answers, same rule:

```
prompt D   SUPPORTED   text-only 36/47 (77%)   with headings 38/47 (81%)   up 3  down 1   p = 0.625
prompt H   SUPPORTED   text-only 56/61 (92%)   with headings 57/61 (93%)   up 2  down 1   p = 1.000
rule -> headings do NOT matter
```

The rule needed at least 3 up, more up than down, **and** p < 0.05. D has the 3 up but p = 0.625, so it
fails the rule. Phase 4's figures stand. **Why the lab, and why no noise control:** the lab's judge had
re-read the same 110 answers five days apart and returned byte-identical verdicts (`D84`), so anything
that moves there is the headings. **Why headings moved nemotron and not qwen's answers** is a
hypothesis, not a finding: nemotron's answers are long and name sections and versions, qwen's are
short. Two judges and two machines differ between the runs, so it is not a controlled comparison.

**`g044` itself stayed PARTIAL with the judge.** Given the heading, it accepted the Engine/Connection part and
asked for the removal of `autoload=True` to be stated, which the heading does not say. Viraj's SUPPORTED is his
verdict. **A judge and a human can disagree about which part of a claim needs a source; both must at least be
shown the same page.**

---

## R10.16 — The public link is on Modal (`D106`)

**Hugging Face refused.** Creating a Gradio Space returned **HTTP 402 Payment Required**: *"Static
Spaces are free for everyone, but hosting Gradio and Docker Spaces on free cpu-basic requires a PRO
subscription."* Nothing was created.

**What the app needs from a host:** about **4 GB of memory**, for the embedding model and the
reranker. That single number decided every option, then Modal was the one that got an account:

| host | free allowance (checked 2026-09-12; confirm on the provider's page) | fits? | used? |
|---|---|---|---|
| Hugging Face Gradio Space | paid plan required (the 402 above) | no | no |
| Render, Koyeb | 512 MB | no: an eighth of what is needed | no |
| **Modal** | $30 of credits a month, no card | yes; slow first question after idle | **yes — live** |
| Oracle Cloud Always Free | 2 CPU / 12 GB since June 2026; card at signup | yes; always on | not chosen |
| Google Cloud Run | a monthly free usage allowance; billing account | yes, for light use | not chosen |

**Public URL:** https://virajvaghasia--sqlalchemy-upgrade-agent.modal.run

Redeploy: `uv run python space/build.py && uv run --with modal modal deploy space/modal_app.py`.
Secret on Modal is named `nvidia` and must contain `NVIDIA_API_KEY`. First cold ask after a deploy
that still needs HF weights took **116 s** and answered; the page and `/api/config` were already
fast. Details and the two crash-loop footguns: `D106`.

**Why the 512 MB hosts cannot be made to fit.** The obvious shrink is to embed questions through an
API instead of loading the model. NVIDIA hosts no `bge-m3`, and a different embedding model is a
different index: the questions would land in a different space from the stored vectors, and the gate
would have to pass again from scratch.

**What did NOT happen.** The lab PC was not used as a host: it is a shared machine and not yours to
expose. No paid plan was bought.

---

## R10.17 — Keys, free tiers and secrets, in plain words

**An API key is a password for a paid (or free-credit) service.** Anyone holding it spends your quota.

| rule | why |
|---|---|
| keys live in `.env`, which `.gitignore` excludes | a key committed to GitHub is public forever, even after deletion |
| never paste a key into a chat | a chat is not a secret store; a pasted key should be treated as leaked |
| on a host, a key is a **secret** setting, not a file | the page's code reads it from the environment; visitors never see it |
| scripts read keys, they never print them | a key in a log is a key in whatever the log is copied into |

**Free tiers have limits that end experiments.** Gemini's is 20 calls a day per model, which stopped Step
3b at 7 of 20. NVIDIA's free credits covered the whole of 3b–3d, but most of its catalog returned 404 on
this key, so a model has to be probed before it is chosen.

**A public page spends your credits**, so the demo has rate limits: 60 questions an hour for everyone
together, 20 seconds between questions from one visitor, 500 characters per question. **These numbers
were chosen, not measured**, and the code says so (`GLOBAL_PER_HOUR`, `SESSION_MIN_SECONDS` and
`MAX_QUESTION_CHARS` in `rag/demo.py`).

---

## R10.17b — Langfuse: seeing what visitors actually ask (`D108`)

**Start from what the repo could not see.** Every measurement so far is on questions this project
chose: the 100 golden ones. Each run saves its rows to a committed file. A visitor on the live page
asks whatever they like, and until 2026-09-14 that question, the pages found and the answer
disappeared when the request ended.

**What one trace holds.** Each question on the live page becomes one record in Langfuse, a hosted
service for storing these. `rag/demo.py` opens it and puts two steps inside:

```
demo.answer    span        input: the question and which backend       the whole request, start to finish
  ├─ retrieve  retriever   input: the question                         output: the five page ids
  └─ generate  generation  input: the full prompt (question + pages)   output: the answer, model name,
                                                                        prompt and completion tokens
```

That is three observations per trace, the number Langfuse's API reported back when this was checked
live: one question answered in 46.0 s with 5 sources, and the trace read back with 3 observations and
a latency of 45.9 s.

**It is off unless the keys are there.** `demo.langfuse_client()` returns nothing when
`LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are missing (or the `langfuse` package is not
installed), and every tracing call then goes through `_observe`, which hands back a do-nothing stand-in.
So the tests, the lab and every local run behave exactly as before. On Modal the keys come from a
secret named `langfuse` (R10.17's rule: a key is a secret setting, never a file).

**What it is NOT.**

- **Not an evaluation.** Nothing in a trace says whether the answer was right. The golden set, the
  judge and the CI gate grade quality; a trace records what happened.
- **Not used on the golden-set runs.** Those already write every row to files the repo commits, so
  tracing them would store the same thing twice (`D108`, rejected option).
- **Not self-hosted.** Self-hosting Langfuse is about five containers (Postgres, ClickHouse, Redis,
  MinIO, the web app), on a 16 GB Mac that had just run out of memory running the local demo. The
  free Cloud plan was chosen instead.

**The cost, said plainly:** visitors' questions now leave for a third party. When tracing is on, the
page's footer adds: *"Questions and answers are logged (Langfuse) to measure this demo; do not paste
secrets."* (`space/static/index.html`, shown only when `/api/config` reports `traced`).

**How to actually look at it**, because a trace nobody opens is a checkbox:

| you want | where |
|---|---|
| what people asked the live page | `cloud.langfuse.com`, US region, this project → **Traces**. One row per question; open it for the five retrieved ids, the answer, latency and tokens |
| tokens the live page has spent | the same trace list — each `generate` observation carries `prompt_tokens` / `completion_tokens` |
| tokens spent by runs on YOUR machine | `uv run python -m rag.usage --report` — the local ledger (`rag/usage.py`), which Langfuse never sees |
| whether tracing is even on right now | `curl -s <demo-url>/api/config` → `"traced": true` |

**Why both exist.** The page runs in an ephemeral Modal container: a file written there dies with the
container, so the page's record has to be remote, and that is Langfuse. Everything run from a machine
you own writes to the local ledger instead. Neither is a bill — NVIDIA Build is free — and neither is
a quota meter, because NVIDIA publishes none: **measured 2026-09-16, its replies carry no rate-limit
headers at all**, so a `429` recorded in one of these two places is the only way you will ever learn
that a limit was reached.

**Say this:** “Every question on the live demo is a trace: what was asked, which five pages came back,
what the model wrote, tokens and time. It is for seeing real traffic, not for grading. Grading is the
golden set and the gate.”

---

## R10.18 — Say this out loud

**The gate.** “Every PR that touches retrieval rebuilds the index on a CI runner, scores the 100 golden
questions, and fails if any question whose answer was in the top five no longer is. Removing the
reranker costs one point of recall, inside the noise band, and the gate blocks it by naming the one
question, `g017`. It grades retrieval only, because retrieval reproduced exactly across my machines and
generation didn't. It's a required check on main, and it caught a bug in itself on its first real run:
the scorer passed its own reranker setting, so a PR that turned the reranker off for users passed. Now
it grades the shipped defaults, and that PR is blocked on a GitHub runner.”

**The router.** “I don't predict which questions are hard; I tested that and it mostly picked
questions whose answer page was missing, which no bigger model can fix from the same pages. The router
is a cascade: the free local model answers first, and only a refusal is escalated.”

**The price and the gain.** “Escalating every refusal to a 550B model would cost about $1.81 per 1000 queries on a paid plan
at one reseller's list price, adds no fabrications on the unanswerable questions, and lifts end to end
from **38 of 91** to at most **48 of 91**. At most, because my judge checks faithfulness to pages, and when I ran two
answers against the real library it had called a wrong one supported and a right one unsupported.”

**The demo.** “The demo uses the graded search, proven identical without the database, and the shipped
prompt. Hosted on Modal at a public URL, it needs a different generator, so I measured that one on the
same 100 questions: **53 of 91** against the local model's **38 of 91**, sixteen gained and one lost, no
fabrications, and 91% of its answers fully supported by the pages as the model saw them (77% when my judge
was shown text only). The page
quotes those numbers.”

**Do not say:**

- “CI blocks any quality regression.” It blocks *retrieval* regressions on the golden set.
- “A stronger model fixed ten answers.” Ten became *supported*; correctness is an upper bound.
- “Routing saves money.” On a paid plan it would *cost* $1.81 per 1000 queries against a free local model; what it buys is
  up to 11 points of end to end.
- “The demo scores 0.42.” Only the local version runs qwen; the hosted model is 0.58, measured once.
- “The bigger model is more faithful.” The same judge rates it level with qwen: 91% vs 81% with headings
  (paired p = 0.45), 77% vs 79% without.
- “77% supported means 23% are wrong.” 77% was a judge that missed the headings (91% with them), and run
  against the library 92% of its checkable answers are right.

---

## R10.19 — Questions to answer cold

**Q1. What does the CI gate check, and what does it not check?**
It re-runs the search for all 100 golden questions and compares, question by question, against the
baseline on the branch being merged into. If any question whose verified answer page was in the top 5
drops out, the check fails, and it names the question. It does **not** check the generated answer at
all: no model writes anything in CI, because generation did not reproduce across machines (`D83`). A
prompt change that makes every answer worse would pass it.

**Q2. Removing the reranker only drops recall from 0.64 to 0.63. Why block it?**
Because 0.64 → 0.63 is one question, and it is inside the ±0.097 uncertainty band, so any gate that
compares averages would wave it through. The paired gate asks per question, and one question, `g017`,
lost its page: the reranker's whole contribution was moving that page from rank 6 to rank 5. A lost
answer for the person who asks `g017` is real even when the average cannot see it. The gate does not
forbid the change; it makes a human sign off on the loss.

**Q3. The reranker had a comment saying it was pinned. Why did fixing that matter?**
The comment said pinned, and the code passed no version to the model loader. On a CI runner with an
empty cache, that downloads whatever version the model's owner has published *that day*. The
reranker's only effect is one swap at rank 5, decided by a 0.8 score margin, so a new upload could
undo it with no code change, and the gate would fail an innocent pull request. It is pinned now to the
exact snapshot every measurement used, re-scored to confirm nothing moved (0.64, same seven fixes),
and a test checks the loader actually receives the version.

**Q4. CPU and GPU produce different vectors. Why trust a gate that runs on a CPU?**
Because different vectors are not different rankings. All 3284 vectors were re-computed on a CPU:
none matched the GPU's to the last digit (largest difference 0.000013), and all 100 top-20 lists were
identical. The differences are real and too small to swap two pages. What is not measured is the
runner's own CPU, a Linux x86 chip with a different maths library; if a code-free PR ever shows
`moved` items, that is the first suspect.

**Q5. Why is the router a cascade and not a predictor?**
A predictor has to guess, before answering, which questions the small model will fail. The guess used
here, low search scores, did catch more failures than chance, but it mostly caught questions whose
answer page was **missing**, where a bigger model gets the same wrong pages. It caught only 3 of the 20
failures where the page was there and the small model refused. The cascade does not guess: every
refusal is escalated, which by definition catches all 20. Its costs: it escalates 53 of 100 questions,
and it never sees a confident wrong answer.

**Q6. What was the statistics bug, and how would you spot one like it?**
The chance baseline flipped an independent 30% coin for each failure, instead of picking exactly 30
questions. The tell is that the wrong version allows catching more failures than questions picked. At
the real sizes it said chance does as well as the router 14% of the time; the truth is 5.7%. It was
spotted because a quick script and the committed tool disagreed (0.14 against 0.06), and a
disagreement between two tools computing one number means one of them is wrong.

**Q7. Why did you stop using Gemini, and what was wrong with the first judge?**
Gemini's free tier is 20 calls a day per model; the run needed 20 answers plus judging and stopped at
7. And the judge for those 7 was `gemma4:e4b`, a Google model grading answers from Google's Gemini: not
the same model, but the same lab, which weakens the independence a judge exists to provide. Both roles
moved to NVIDIA's API: Nemotron answers and `gpt-oss-20b`, from a different lab, judges. The switch
happened before any answer from the new models existed, and Gemini's 7 rows are kept separately.

**Q8. What is a shadow cost, and where does $1.81 come from?**
It is what calls would have cost at a published price, when they were actually made for free. The API
reports exactly how many tokens each call used: 45015 + 70210 prompt tokens and 15624 + 19330 output
tokens over all 53 escalations. Multiply by the snapshot price ($0.000000625 prompt, $0.000003125
output) and you get $0.18125 for the golden set's 100 queries, so $1.81 per 1000. The price is one
reseller's list price on one date, saved in a file, not NVIDIA's own.

**Q9. What is the difference between "supported" and "correct"? Give an example.**
Supported means the pages given to the model say it; correct means it is true of SQLAlchemy 2.0.51.
`g016`'s answer said `row.keys()` still exists in 2.0: the judge called it supported, and running it
on 2.0.51 shows the method does not exist. `g007`'s answer said `MetaData(bind=)` was removed: the
judge called it unsupported because the pages do not say so, and 2.0.51 raises a TypeError, so the
answer was right. A faithfulness judge measures the first question, never the second.

**Q10. The project's number is 0.42. Why does the demo say that number does not describe it?**
0.42 is 38 of 91, measured with `qwen2.5-coder:7b` generating. A hosted demo cannot run that model
(NVIDIA serves no qwen), so it generates with Nemotron. Showing 0.42 next to Nemotron's answers would
quote a number for a system that did not produce them. When the hosted page was first built, Nemotron
had never been measured on all 100, so the notice could only say "not this model". Step 4d then
measured it (R10.15b), and the hosted notice (`NOT_THE_MEASURED_MODEL` in `rag/demo.py`) now reads:
*"…measured once on the project's 100-question set with the same retrieval and prompt (2026-09-13): 0.58
end to end, and 91% of its answers judged fully supported by the pages it was given (supported is not
the same as correct). The 0.42 quoted elsewhere is for `qwen2.5-coder:7b`, a different model."* 0.58 is
53 of 91 and 91% is 63 of 69; a test re-derives both from the saved rows. The local demo runs qwen, so
its notice says it is the measured model.

**Q11. Where is the public demo, and why that host?**
https://virajvaghasia--sqlalchemy-upgrade-agent.modal.run. Hugging Face Gradio Spaces returned HTTP
402 on the free plan, and the app needs about 4 GB of memory, which rules out the 512 MB free hosts.
Modal's Starter credits fit, need no card, and scale to zero when idle. The first cold answer after
deploy took about two minutes while it pulled the embedding models; the page itself was already up.

**Q12. A pull request changes only a document, and the gate fails. What do you check first?**
First, whether the real job ran at all. The workflow always starts, and its first job
(`did retrieval change?`) diffs the PR against its base. The scoring job runs only if a file under
`rag/`, the corpus manifest, the golden set, the baseline, `pyproject.toml`, `uv.lock` or `gate.yml`
changed; otherwise it is skipped, and a skipped required job counts as passed. So a docs-only PR should
show the gate skipped, not failed. If the scoring job did run on a change that cannot move retrieval
and shows `broken` or `moved` items, the code did not cause it. Read the baseline's
provenance line (which machine, which device, which model snapshots) and compare with the run:
the usual suspects are a model snapshot changing (why both models are pinned) or the runner's CPU
ranking a near-tie differently (R10.8). PR #29 measured the second one once, `moved 0`, which makes it
less likely, not impossible.

**Q14. The gate's demo passed as a real PR before it was blocked. What was wrong, and what does it
teach?**
PR #30 changed `index.retrieve`'s default to `rerank=False`, the path users get. The scorer called
`index.retrieve(q, rerank=True)` explicitly, so it kept grading a system with the reranker on, and the
gate read 0.64 and passed. The fix makes the scorer pass nothing unless a flag asks, so it grades
whatever `index.retrieve` ships; a test records the keyword arguments to prove it. Re-run, the same PR
was blocked on `g017`. The lesson: my earlier demo used a command-line flag, which is not how a real
change arrives. A gate has to be fed the change it exists to stop, in the shape that change would
really take.

**Q15. What is Langfuse doing in this project, and what is it not doing?**
It stores one trace per question asked on the live demo: the question, the five page ids retrieval
returned, the prompt, the answer, token counts and time. That is the only place real visitors' questions
are recorded; the golden-set runs already save their rows to committed files. It grades nothing: whether
an answer is right is still the golden set, the judge and the gate. It is switched off whenever the keys
are absent, so tests and local runs are unchanged, and the page tells visitors their questions are
logged.

**Q13. The bigger model scores 0.58 against the small model's 0.42. Why not just switch?**
Start with what the 0.58 is. On the same 100 questions and the same five pages, nemotron answered 53 of
the 91 answerable ones with the right page in hand, and qwen answered 38. The 58 questions where search
found the page are identical for both; nemotron simply declined far less often with the page in front
of it (5 times against qwen's 20). Question by question that is 16 gained and 1 lost, p = 0.0003, so
the gain is real, not noise. Now the reasons not to switch. First, grounding is level, not better:
given the pages as the model saw them, 91% of its answers are fully supported against qwen's 81%, and
question by question the difference is not significant (p = 0.45). (Run against the library, 47 of 51 of its checkable answers are
right, so this is about sticking to the pages, not about being wrong.) Second, it was measured once, on one day. Asked twice, the
decision held on 19 of 20 and the wording on none. Third, the project runs on zero paid calls; free
credits end. So it is quoted where it is used (the hosted page) and used where the design says so (the
cascade sends it only the refusals). And the one question it lost, `g053`, is a stricter reading of a
Flask-SQLAlchemy question, which is a reminder that "fewer declines" is not automatically "better".

---

## After this you can say

- what a required status check is, and which half of it lives in the repo
- what the runner measured: `moved 0` on Linux CPU, 57–135 minutes cold, about 2 minutes warm
- how the demo PR first passed (the scorer passed `rerank=True` itself) and why a flag is not a real PR
- why the gate compares question by question and ignores the p-value
- why generation is not in CI, with the decision that measured it
- why the embedding cache is saved before the gate runs, not after
- that the reranker was unpinned for three weeks, and how the gate would have turned that into a false failure
- why a cascade on refusal beats a predictor on search scores here, with the 3-of-20 number
- the difference between picking without replacement and independent coins, with a case you can check by hand
- how a shadow cost is computed, and what the $1.81 is and is not
- why "supported" is not "correct", with `g016` and `g007`
- why the demo can use in-memory search, and why its page must name its generator
- what the hosted model scores on all 100, why search is not the difference, and why 77% supported still fails
- that the same judge rates both models level, and that the judge's grade did not predict which answers were right
- that the judge had never been shown the headings the model saw, and what changed when it was (77% → 91%)
- that Phase 4's judge, given headings too, did not move enough to matter (D 77% → 81%, H 92% → 93%)
- where the public demo lives (Modal), why HF refused, and what 4 GB of memory rules out
- what a Langfuse trace holds, and why it is not an evaluation
