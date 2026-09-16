# Phase 6 — Production: a change that makes it worse cannot merge quietly

Part of [`sqlalchemy-upgrade-agent`](../README.md). **Teaching file:
[`../study/18-PRODUCTION.md`](../study/18-PRODUCTION.md) (§R10) — read that first;** this file is
the measured plan, that one is the sitting. Follows [`PHASE-5.md`](PHASE-5.md), closed on
measurement (`D94`): the agent's levels are machine-dependent and its effects reproduce.
Spec: [`ROADMAP.md`](ROADMAP.md) Phase 6.

**Done when (ROADMAP):** a stranger can click a demo link and get a cited answer, **and a
quality-degrading PR gets auto-blocked.**

---

## The order, and why it is this order

| step | what | state |
|---|---|---|
| **1** | source framing — does the prompt's shape move `D72`'s over-refusals? | **closed, rejected** (`D96`) |
| **2** | **CI quality gate** — a PR that loses a golden answer fails a check | **done** (`D97`): Linux runner PASSED with `moved 0` (PR #29); removing the reranker **BLOCKED `g017`** on the runner (PR #30); required on `main`. Found: the scorer had graded its own settings, not the shipped defaults — fixed |
| **3** | routing with shadow cost — cheap questions local, hard ones to a strong model, priced | **3a closed** (`D98`): cascade on refusal; **3b** (`D99`): 16/20 answered, 10 page-supported; **3c** (`D100`): full cascade **$1.81 / 1000 queries**, 0 new fabrications; **3d** (`D101`): 10/16 hold against verified pages → **0.42 → 0.53** upper bound |
| **4** | deploy + package — a demo link and a README that opens with the product | **live on Modal** (`D106`): https://virajvaghasia--sqlalchemy-upgrade-agent.modal.run — HF Gradio refused (402); in-memory path still `D102` |
| 5 | Langfuse — traces, tokens, latency, cost per query | **live on the demo** (`D108`, 2026-09-14): one trace per question — retrieve, generate (tokens) |

**The gate comes before routing and deploy** because both of those change the system, and every
change after this point should arrive with the gate already watching. Built last, it would grade
nothing that mattered.

---

## Step 1 — source framing (CLOSED, `D96`)

Arm B replayed the agent's conversation shape with no tools. Page-present over-refusals fell on
both machines (Mac 19 → 14, lab 20 → 17), but read by id the part that reproduces is **4 fixes, 1
break (`g043`) and 4 page-absent answers** where declining was the honest outcome, three of them
unsupported. **A willingness shift, not better reading.** Shipped prompt unchanged. Full write-up
`study/17-AGENT.md` §R9.7d; Round 21 in `logs/HANDOFF.md`.

---

## Step 2 — the CI quality gate (`D97`)

### What it grades

Retrieval only, recall@5, **paired by golden id**. Any answerable item whose answer page was in the
top 5 on the base branch and is not in this PR's run **fails the check**, whatever else improved.
Generation is not graded in CI: no Ollama on a runner, and `D83` measured generation not
reproducing across machines at all, while retrieval reproduced exactly.

### The pieces

| file | job |
|---|---|
| `rag/gate.py` | the join, the buckets (`fixed` / `broken` / `moved` / `unpaired`), the exit code |
| `deliverables/gate-baseline.json` | the rows the gate compares against, with provenance |
| `deliverables/gate-demo-no-rerank.json` | the ROADMAP's demo, measured: the reranker removed |
| `.github/workflows/gate.yml` | builds corpus → embeds (cached) → Qdrant service → scores → gates |
| `tests/test_gate.py` | 12 tests, seven mutations checked, all caught |

### The ROADMAP's demo, measured

*"Open a PR that removes your reranker, and film CI auto-rejecting it."* Run locally against the
committed rows, no Qdrant needed:

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

**`g017` is `D68`'s only fix**, so the gate blocks exactly the item the reranker was shipped for. A
one-point drop in recall (0.64 → 0.63) is inside the ±0.097 band and would pass an average-based
gate; the paired gate does not let it through.

### Found while building it: the reranker was never pinned

`rag/rerank.py` said *"Pinned like embed.MODEL_REVISION"* from 2026-08-21, and `CrossEncoder` was
given no revision. Harmless on one Mac with one cached snapshot; **fatal for a CI gate**, where a
fresh runner downloads whatever `main` points at and a new upload could flip `g017` with no code
change. Pinned to `2cfc18c9…`, the only snapshot in the Mac's cache and the one `refs/main` named.
**Verified to change nothing:** the re-score gives recall@5 **0.64** and **7↑ 0↓, p = 0.016**
against the Phase 1 baseline, the same seven ids as `D66`–`D68`.

### Still open — and it is the one that decides whether the gate is trustworthy

**The baseline was taken on MPS; a GitHub runner has only a CPU.** If CPU floats reorder a near-tie
at the rank 5/6 boundary, every PR would show a phantom `broken` item. `D83` measured MPS and CUDA
reproducing exactly; CPU is a third backend. **Measured on the Mac CPU (`D97`): 0 of 3284 vectors
bit-identical to MPS (max difference 1.3e-5), and 100 of 100 top-20 lists identical — gate `moved
0`, PASSED.** Linux x86 CPU, which is what a runner is, stays unmeasured until the workflow runs.

**Not done, and not Claude's to do:** open a PR so the workflow runs on a real runner, and mark the
check *required* in branch protection. Both are actions on the GitHub repository.

### The gate on a real runner — 2026-09-14 (PRs #29 and #30)

**Linux x86 CPU ranks like the Mac's GPU.** PR #29 (the workflow change, no retrieval change) on
`ubuntu-latest`: **58/91 = 0.64, fixed 0, broken 0, moved 0 → PASSED.** The question above is answered.
Timings, first run, cold cache: **embed 2,737 s**, **score 626 s**, job **3,442 s**. PR #30's runner was
slower: embed 6,560 s, score 1,467 s, job 8,089 s. Runners differ by more than 2x; quote a range.

**The demo PR PASSED, and that exposed a real hole in what the gate grades.** PR #30 set
`index.retrieve(rerank=False)`, the path `rag.ask` and the live page call. The gate still read 0.64,
because `rag.score.score_items` **always passed `rerank=True` explicitly**: the gate graded its own
settings, not the shipped defaults. A PR that quietly turned the reranker off for users would have passed.
**Fixed** (test first, `test_the_scorer_grades_the_shipped_defaults_unless_a_flag_asks_otherwise`):
`score_items` passes `hybrid`/`rerank` only when a flag sets them. The baseline cannot move: the shipped
defaults are hybrid on, reranker on, which is what was passed before. PR #30 is re-run on the fixed code.

**Also changed:** the `paths:` filter became a `changes` job, so `quality gate` is skipped (counted as
passed) when retrieval cannot have moved; a required check that never reports freezes a PR. **`quality gate`
is now a required check on `main`** (with `tests`, `2.0 evidence`, `image builds`, `docs reproduce`), set by
Claude at Viraj's request after a first attempt was refused by the permission layer.

**The demo, re-run on the fixed scorer (PR #30, commit `b71bb6f`): BLOCKED on a GitHub runner.**

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

**It matches the locally committed demo exactly** (0.63, `broken 1 g017`, `moved 3`), now on a Linux runner.
With the vectors cached from the earlier run, embedding was skipped: **score 48 s, job 123 s**. A warm gate
takes about two minutes; only a cold cache costs the hour.

**Phase 6's finish line, both halves, met on 2026-09-14:** the demo link answers with citations (`D106`), and
a pull request that removes the reranker is rejected by CI by name, with `quality gate` required on `main`.
PR #30 stays open, unmerged, as the record.

---

## Step 3a — can routing know which questions to send? (pre-registered 2026-09-12, 14:30)

**The ROADMAP's sentence** is *"routing saves $X per 1000 queries at a Y-point quality cost."* Before
any price, a router needs a reason to send one question and not another. This step measures only
that, with **no generation and no API call**: lab outcomes already on disk (Round 16, prompt `D`,
the shipped path, `38/91` delivered) and retrieval signals recomputed on the Mac. Mixing the two is
legitimate for one reason: `D83` measured retrieval **identical** across the two machines.

**The distinction that decides what routing can buy:**

| local failure | what a stronger generator gets | can routing fix it? |
|---|---|---|
| page **absent** from the prompt | the same five wrong pages | only from memory, which is `g065`'s failure mode |
| page **present**, model refused or missed it | the right page | **plausibly** — unmeasured until a strong model answers |

**Two designs, both measured the same way:**

- **A — predictive.** Before generating, score the five shipped pages with the cross-encoder the
  reranker already loads, and route the **30%** of questions (30 of 100) whose **best page scores
  lowest**. One signal chosen in advance: `max CE over the five pages`. Other signals may be printed
  as exploration and decide nothing.
- **B — cascade.** Generate locally; escalate only if the answer is a refusal (`ask.refused`). No
  predictor.

**Rules, written before the numbers:**

| check | pass | meaning of a fail |
|---|---|---|
| A captures local failures at a 30% budget | **≥ 27 of the 53** answerable items not delivered (random routing expects ~16) | the signal cannot see failure; a predictive router is a coin toss with a bill |
| A's routed failures with the page **present** | reported, no threshold | this is the share routing could actually fix |
| B's escalations with the page **present** | reported, no threshold | same, for the cascade |

**My prediction, recorded so it can be wrong:** A passes the capture bar, but mostly by finding
**page-absent** failures, which a stronger generator cannot fix; B escalates fewer questions and a
larger share of them have the page present. So the cascade is the better design here, and the
predictive router looks good on capture and bad on what it can actually fix.

### Result (`D98`)

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

**Against the rules:**

| check | result |
|---|---|
| A captures ≥ 27 of 53 | **FAIL — 20.** Better than random picking (median 16, P = 0.057), not by enough to route on |
| A's catches with the page present | **3 of 20.** Random picking would expect ~6. The signal finds the failures a stronger model cannot fix |
| B's escalations with the page present | **20 of 46 answerable escalations**, and all 20 of the page-present failures |

**My prediction, scored:** *"A passes the capture bar"* — **wrong**. *"Mostly page-absent"* — right
(17 of 20). *"B escalates fewer questions"* — **wrong**: 53 against A's 30. *"A larger share of B's
have the page"* — right (43% against 15%). Two of four, recorded as written.

**Found while measuring it: my first random baseline was wrong.** The scratch version re-drew the
random sample once per failure, which is a binomial (P(≥ 20) = 0.14), not "pick 30 of 100"
(hypergeometric, P = 0.057). It made a marginal signal look like pure chance, and I had already
said so in chat before the committed instrument disagreed. The instrument now computes the exact
distribution instead of simulating it, and a test pins 0.0571.

**What this does NOT measure:** whether a stronger model would answer the 20 page-present
escalations, and what it would cost. Both are Step 3b, and neither is a number yet.

**Exploration, decides nothing:** within B's 46 answerable escalations, max CE separates
page-present from page-absent at AUC **0.71** (median 0.92 against 0.67). That is the hypothesis
Step 3b can pre-register: *escalate a refusal only when its best page looks relevant.* **It cannot
be tested on these 100 items**: the AUC came from them, so any threshold chosen here would be graded
by the data that picked it. It waits for new questions.

---

## Step 3b — do the escalations get fixed? (pre-registered 2026-09-12, 14:45)

**The question 3a left open.** The cascade sends the 20 page-present refusals upward. Does a stronger
model, given **the identical prompt and the identical five pages**, actually answer them, and are the
answers faithful to those pages?

**Setup, fixed before any call:**

| | |
|---|---|
| items | exactly the 20 ids `rag.route` lists as B's page-present escalations (lab, Round 16 `D`) |
| strong model | `gemini-3.7-flash`, hosted, **free tier** — the pinned id `D80` measured answering; 20 calls is one day's per-model quota, so **no `--check` call is spent** |
| prompt | `ask.SYSTEM` as the system instruction, `ask.build_prompt(question, hits)` as the user turn, temperature 0 — the shipped prompt, unchanged |
| pages | `index.retrieve(question, limit=5)` on the Mac; 3a's join check proved these match the lab's flags |
| judge | local `gemma4:e4b` via `faithful.judge_answer`. **A Mac screen** (`D95`; `D86`: too extreme both ways on hard rows). *Corrected 15:10, after the calls, on Viraj's question:* this row first said "a different family from the generator, so nothing grades itself". True against qwen, **not clean here** — Gemma and Gemini are both Google models, so this is a Google model grading a Google model. Not the same weights, and a weaker form of the self-grading problem `D78` avoided; any `SUPPORTED` count from this step carries it |
| tokens | the API's own `usageMetadata`, recorded per call — counted, not estimated |

**Rules:**

| strong model answers (not refused), of 20 | meaning |
|---|---|
| **≥ 15** | the page-present refusals are a model-size problem; the cascade's escalations are worth sending |
| **11–14** | mixed; routing helps some, and the rest are something a bigger model does not fix either |
| **≤ 10** | the refusals are not about model size (the page or the prompt); routing buys little and Step 3 should say so |

| of its answers, judged `SUPPORTED` | meaning |
|---|---|
| **≥ 80%** | the extra answers hold up (`D82`'s bar for `H`'s extra answers was met at 13 of 16) |
| **< 80%** | the stronger model answers by talking past the pages; count only the supported ones as fixes |

**If the quota runs out mid-run**, the rows so far are saved and the result is reported as
`INCOMPLETE — n of 20`, never scaled up.

**My prediction:** it answers **14 of 20** and about **85%** of those are `SUPPORTED`. The local model
refuses these with the page in hand; a larger model should read past a Sphinx-heavy passage more
often, but not always, because some of `D72`'s pages answer the question only obliquely.

### History — the Gemini run, 15:05, INCOMPLETE 7 of 20 (abandoned, rows in `escalate-phase6.gemini-3.7-flash-abandoned.json`)

```
ESCALATION — gemini-3.7-flash on the cascade's page-present refusals (INCOMPLETE — 7 of 20)

  answered    7 of 7   rule >= 15  -> no verdict on an incomplete run
  refused     0   -
  SUPPORTED   7 of 7 judged = 100%   rule >= 80%  -> no verdict on an incomplete run   (local judge, Mac screen)
  not SUPPORTED  -

  tokens, as returned by the API: prompt 17270, output 1820  (over 7 calls)
```

**What happened.** Call 2 hit HTTP 503 and the first version of the instrument stopped on it (fixed:
`faithful.retrying`, plus resume). The resumed run got 503s again, retried through them, and stopped
on **HTTP 429 at item 8**, most likely today's per-model daily quota, since the 503 attempts may
have counted against it. Not re-checked, because checking costs a call.

**What is and is not said.** Per the rule written before the calls: **no verdict and no scaling.**
"7 of 7" is not "20 of 20", and the seven are the first seven ids alphabetically, not a sample.
Recorded as observations only:

- all 7 answered, all 7 judged `SUPPORTED` by the local judge. Two caveats travel with that: it is
  a Mac screen with a judge `D86` measured as too extreme both ways, and **the judge is a Google
  model grading a Google model** (see the judge row above). So a clean 7 was read, not believed:
  `g044` and `g029` were opened and are correct, specific, cited migrations
- every one of the 7 cites at least one source (`judge.citations`), against the shipped local
  path's 67% citing nothing — but **9 of their 14 code blocks carry no citation**
- tokens as returned by the API: **17270 prompt + 1820 output over 7 calls**

**SWITCH, 15:12, before any answer from the new model — Viraj: do not use Gemini at all.** Its free
tier is 20 calls a day per model and it stopped this run at 7. Both roles move to Viraj's NVIDIA key
(free credits, `integrate.api.nvidia.com`):

| role | before | now |
|---|---|---|
| escalation model | `gemini-3.7-flash` | **`nvidia/llama-3.1-nemotron-70b-instruct`** — large, instruction-tuned, not a reasoning model |
| judge scored against the 80% rule | `gemma4:e4b` | **`mistralai/mistral-large-2-instruct`** — independent of Nemotron/Llama, of qwen and of Google |
| second judge, agreement only | — | `gemma4:e4b`, local |

**Second switch, 15:15, still before any golden-set answer:** the first NVIDIA call returned **HTTP
404** — Nemotron-70B is listed in the catalog and not invocable on this key, and neither are
`mistral-large-2-instruct`, `mistral-large`, `nemotron-4-340b`, `llama-3.1-nemotron-51b/ultra`,
`mixtral-8x22b`, `phi-3.5-moe`, `kimi-k2.6`. Probed with *"Reply with the single word OK"* only, so
nothing about the questions was seen. What answered, and the final assignment:

| role | model | why |
|---|---|---|
| **escalation model** | **`nvidia/nemotron-3-ultra-550b-a55b`** | the largest that responds; its reasoning comes back in a separate field, so the answer text is clean |
| **scored judge** | **`openai/gpt-oss-20b`** | OpenAI shares a lab with none of NVIDIA, Alibaba (qwen) or Google (gemma). `mistral-nemotron` formats as cleanly but is co-built with NVIDIA |
| agreement judge | `gemma4:e4b`, local | unchanged |

**Token counts for reasoning models include the reasoning** (`completion_tokens`), which is what
would be billed, so they are recorded as returned.

**Rules and prediction unchanged.** The 7 Gemini rows are kept as
`deliverables/escalate-phase6.gemini-3.7-flash-abandoned.json` and are **not** part of this result:
one set of 20 answered by two models would be two experiments averaged. Everything below this box
about the Gemini run is history.

**The judge question, settled 15:15 before the new judge read anything:** Viraj has an NVIDIA API
key (free credits). **`mistralai/mistral-large-2-instruct`** via `integrate.api.nvidia.com` becomes
the judge whose `SUPPORTED` count is scored against the 80% rule: not Google (the escalation model),
not Alibaba (the shipped qwen), not gemma; instruction-tuned rather than a reasoning model, so it
follows the one-word verdict format. **gemma's verdicts stay in the rows for agreement only.** Run
with `rag.escalate --judge-nvidia`; the key lives in `.env` as `NVIDIA_API_KEY`, never in a file
that is committed.

**Not done:** a price. The shadow cost needs a published per-token rate for this exact model, with
a date and a source. The token counts are measured and waiting for it.

**To finish:** `uv run python -m rag.escalate --generate` on a later day resumes at item 8 without
re-asking the 7, then judge, then `--report`. The block above will stop reproducing when it
completes, which is how this section gets updated.


### Result (`D99`) — 15:33, NVIDIA, complete

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

**Against the rules written before the first call:**

| rule | result |
|---|---|
| answered ≥ 15 of 20 | **PASS — 16.** The local model's page-present refusals are mostly a model-size problem |
| `SUPPORTED` ≥ 80% of answers | **FAIL — 10 of 16 = 62%.** Per the rule: only the 10 supported count as fixes |

**All six misses are `PARTIAL`, none `UNSUPPORTED`** (`g013 g021 g044 g049 g099 g106`): the bigger
model answers from the page *and* adds what the page does not say. That is the same direction `D86`
found in human disagreements with a judge. **Prediction scored:** 14 answered (actual 16) and ~85%
supported (actual 62%) — both wrong, the second by a lot.

**What routing buys, in the repo's own unit** (lab, 91 answerable, shipped end to end `38/91 =
0.42`): the cascade plus this model turns **10** page-present refusals into supported answers, so an
upper bound of **48/91 = 0.53** if every one of the 10 is also correct. Not measured: correctness
against real 2.0.51, and whether escalating the other 33 refusals (page absent or unanswerable)
creates fabrications.

**Tokens** (as returned; reasoning included): **45015 prompt + 15624 output over 20 calls.** A price
per token for this model, with a source and date, is the one input the shadow cost still needs.

**Second judge, 16:10 — incomplete, 14 of 16.** `gemma4:e4b` agrees with `gpt-oss-20b` on **11 of
14**. On those 14 it counts 10 `SUPPORTED` against gpt-oss's 9: nearly the same rate, **different
items** (`g006`: gemma UNSUPPORTED, gpt-oss SUPPORTED; `g021`, `g099`: gemma SUPPORTED, gpt-oss
PARTIAL). The last two (`g100`, `g106`) timed out: the Mac was at 10 GB of swap with ~7 GB wired
(Docker's VM and the GPU), and the run was stopped rather than left to crawl. **The first timeout
killed the run** — the gap the 2026-09-10 notes named and left open; both judge loops now skip a
timed-out item and leave it unjudged for a resume.

**Shadow cost, computed from the committed snapshot** (`deliverables/prices-phase6.json`, OpenRouter
list price fetched 2026-09-12 22:51 UTC; one reseller's price, not NVIDIA's; the calls were free):
**$0.0770 for the 20 calls, $0.00385 per escalation.** By hand: 45015 × $0.000000625 + 15624 ×
$0.000003125 = $0.0281 + $0.0488.

**Human read:** `deliverables/ESCALATE-PARTIAL-REVIEW.md` — the six `PARTIAL`s with question, full
answer, judge's reason and all five pages; verdict column blank for Viraj (`D06`).
---

## Step 3c — the escalations a real cascade cannot tell apart (pre-registered 2026-09-12, 15:55)

**Why 3b is not the whole router.** `D99` sent only the 20 page-present refusals, because they are the
ones a stronger model can fix. **A running cascade does not know which refusals those are.** It
escalates every refusal: `D98` counted **53 of 100** — the 20, plus **26 page-absent** answerable
refusals, plus **7 unanswerable** items the local model correctly declined. The 33 are where
escalation can *cost* quality, and nothing has measured them.

**Setup:** identical to 3b — same model (`nvidia/nemotron-3-ultra-550b-a55b`), same prompt, same pages,
same scored judge (`openai/gpt-oss-20b`). Ids derived by `rag.route`, never typed. Rows go to their
own file, `deliverables/escalate-rest-phase6.json`, so 3b's result cannot be overwritten.

**Rules:**

| row | result | meaning |
|---|---|---|
| **unanswerable**, answered | **≥ 2 of 7** | escalating blindly **buys fabrications** — the cascade needs a gate before escalation, not after |
| unanswerable, answered | 0–1 of 7 | escalation keeps the local model's honest refusals honest |
| **page absent**, answered | reported | answered without the verified page: a guess or a lucky neighbour page |
| page absent, `SUPPORTED` | reported | supported by *those* pages, which is not "correct" — the verified answer page was not among them |

**The shadow cost is computed, not typed**, from the API's token counts over **all 53** escalations and
the committed price snapshot `deliverables/prices-phase6.json` (OpenRouter list price, fetched
2026-09-12 22:51 UTC — one reseller's price, not NVIDIA's; the calls themselves were free credits).

**My prediction:** the stronger model answers **3 of the 7** unanswerable items (it answered 16 of 20
refusals, so it is willing) — so the first rule fires — and **15 of the 26** page-absent ones. Cost
about **$2 per 1000 queries** at a 53% escalation rate.


### Result (`D100`) — 16:53, complete

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

**Against the rules:**

| rule | result |
|---|---|
| unanswerable answered ≥ 2 of 7 → escalation buys fabrications | **0 of 7.** The stronger model keeps every honest refusal honest |
| page absent, answered | **13 of 26**, reported |
| page absent, `SUPPORTED` | **9 of 13**, reported — and see below for what that word does *not* mean |

**Prediction scored:** 3 of 7 unanswerable answered — **wrong (0)**; 15 of 26 page-absent answered —
close (13); about $2 per 1000 queries — close ($1.81).

**"Supported by the pages" is not "correct" — checked on real 2.0.51, and it fails in both
directions.** Two page-absent answers, read and then executed:

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

| item | what the answer claims | real 2.0.51 | judge |
|---|---|---|---|
| `g016` | "`row.keys()` **should exist** in SQLAlchemy 2.0" | `hasattr(row, "keys")` is **False** | **SUPPORTED** — a wrong answer, faithful to a page it misread |
| `g007` | "2.0 **removed** the `bind` parameter from `MetaData`" | **TypeError** | **UNSUPPORTED** — a right answer, from memory, that the pages do not state |

So the judge measures **faithfulness to the five pages**, which is what it was built for (`D82`), and
nothing in Phase 6 has measured **correctness** of escalated answers. The 9 page-absent `SUPPORTED`
answers are not fixes, and 3b's 10 are not verified fixes either.

**The ROADMAP's sentence, as far as it can honestly be written today:** *escalating every local
refusal to a 550B model would cost **$1.81 per 1000 queries** at one reseller's list price, escalates
**53%** of queries, adds **0** fabrications on the **7** unanswerable items it escalates (the other two,
`g056` and `g065`, the local model answers and fabricates, so a cascade on refusal never sees them),
and turns **10** of the 20
fixable refusals into page-supported answers — an upper bound of **0.42 → 0.53** end to end whose
correctness is not yet verified.*
---

## Step 3d — are the escalated answers correct? A reference judge, calibrated first (pre-registered 2026-09-12, 17:05)

**The gap `D100` left.** The judge read each answer against the five pages the model was given, which
measures faithfulness. `g016` and `g007` showed that is not correctness, in both directions.

**What changes, and only this:** the same judge (`openai/gpt-oss-20b`, same prompt) reads each
escalated answer against the golden set's **verified answer chunks** — the pages a human signed as
answering the question (`D06`) — instead of the retrieved five. Verdicts go in a separate field
(`verdict_ref`); nothing already recorded is overwritten.

**Calibration, run first, on the only two answers whose truth was executed on 2.0.51:**

| item | truth on 2.0.51 | the reference judge must say |
|---|---|---|
| `g016` | answer is **wrong** (`row.keys()` does not exist) | **not** `SUPPORTED` |
| `g007` | answer is **right** (`MetaData(bind=)` raises) | `SUPPORTED` or `PARTIAL` |

**If either calibration item fails, stop:** the reference judge is not trusted and no correctness
count is printed. Two items is a smoke test, not a validation — passing it means "not obviously
broken", nothing more.

**If both pass**, judge all 29 escalated answers (3b's 16, 3c's 13) and report per set:
`SUPPORTED` against the verified page, `PARTIAL`, and the rest. **The number quoted for the cascade's
quality gain becomes 38 + (3b answers `SUPPORTED` by the reference judge)**, replacing `D99`'s 10.
No threshold: this is a measurement, not a ship decision.

**My prediction:** calibration passes; 3b **11 of 16** reference-`SUPPORTED`; 3c page-absent **5 of
13**.


### Result (`D101`) — 17:07

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

**Against the rules:** calibration **passed** (`g016` → UNSUPPORTED, `g007` → PARTIAL), so the counts
print. Two caveats on that pass, both visible in the rows: it is two items, and the judge rejected
`g016` because the verified page *does not mention* `row.keys()`, not because it contradicts it.

**Scored:** 3b **10 of 16** reference-`SUPPORTED` (prediction 11); 3c page-absent **6 of 13**
(prediction 5). **The pre-registered quote: 48/91 = 0.53 end to end, upper bound.**

**Two judges, same count, different items.** Against the retrieved pages and against the verified
pages, 3b is 10 both times — but only **7** items are the same (`g008 g050 g051` only the first;
`g044 g049 g099` only the second). The rate reproduces and the membership does not: the pattern
`D89`, `D96` and `D83` each found in a different place.

**A correction to `D98`, from data it did not have.** `D98` said page-absent failures are the kind a
stronger generator cannot fix. **6 of the 26 page-absent refusals got answers that agree with the
verified page** — from neighbour pages or the model's own knowledge (`g036`, for example, is the
`MetaData(bind=)` removal, which 2.0.51 confirms). The cascade decision stands, and is stronger for it;
the premise was too absolute. **54/91 = 0.59 is not pre-registered** and is exploration only.
---

## Step 4 — deploy + package (opened 2026-09-12, 17:15)

**Viraj decided** (17:13): a **Hugging Face Space**, generating through the **NVIDIA API** with the key
stored as a Space secret.

**Constraints that shape it, each checked rather than assumed:**

| constraint | consequence |
|---|---|
| a free Space has no Docker-in-Docker, so no Qdrant container | dense search runs **in memory** over `embeddings.npy` (`RAG_DENSE=memory`, `rag/index.py`) |
| Qdrant's index is approximate; an exact search can rank differently | **the in-memory path must pass the CI gate against the committed baseline before it ships** (below) |
| `qwen2.5-coder:7b`, the measured generator, is **not on NVIDIA's API** (catalog checked 17:14: no `qwen` model at all) | the demo generates with `nvidia/nemotron-3-ultra-550b-a55b`, the one model measured with this prompt (`D99`–`D101`); **the page says the 0.42 does not describe it** |
| a public page spends Viraj's free credits | a per-session and global rate limit |

**Rule for the in-memory search, written before scoring it:** `rag.gate` against
`deliverables/gate-baseline.json` must show **`broken 0`**, and no ruler change. `moved` items are
reported; the demo depends only on found / not-found matching.


### Built (`D102`) — 17:30, not yet pushed

**The in-memory search passed its rule.** Golden set through `RAG_DENSE=memory`, gated against the
Qdrant baseline:

```
# runnable: RAG_DENSE=memory uv run python -m rag.score --save /tmp/rows-memory.json && uv run python -m rag.gate --baseline deliverables/gate-baseline.json --rows /tmp/rows-memory.json
QUALITY GATE — retrieval, recall@5, paired by golden id

  baseline   58/91 = 0.64
  this run   58/91 = 0.64

  fixed        0  -
  broken       0  -
  moved        0  (top-5 ids changed, found/not-found did not)
  unpaired     0  (new items, no baseline yet)
  exact McNemar p = 1.000  (context only; the gate reads `broken`)

PASSED — no golden answer lost
```

**Stronger than the rule asked:** every top-5 is identical, and **96 of 100 top-20 lists** are — the
four that differ do so below rank 5, which is Qdrant's approximate index showing.

**What exists:**

| file | job |
|---|---|
| `rag/demo.py` | question → the graded retrieval → the shipped prompt → NVIDIA → answer + every source; rate limits; the "not the measured model" notice. 7 tests |
| `space/app.py` | the Gradio page, a thin wrapper; three example questions both judges supported (`D101`) |
| `space/web.py` + `space/static/index.html` | **added 2026-09-13, now what `build.py` ships** (Step 4c): the hand-designed page over the same `rag/demo.py` |
| `space/requirements.txt` | pinned to the versions **installed** where the baseline was gated |
| `space/README.md` | the Space card: what it does, what is measured, and that 0.42 is not this model |
| `space/build.py` | assembles `space/dist/` (gitignored): the page (`app.py` until 2026-09-13, `web.py` + `static/` since), `rag/`, the corpus files, LFS attributes |

**Checked, not assumed:** one real question end to end in 30 s (`g048`'s wording: cited the migration
guide, correct on the string-name removal); the built bundle imports with the exact pins on Python
3.11 and builds the page; and **the bundle ranks identically to the repo** on the same query
(`c00456 c01567 c02028 c01569 c01573`, both).

**Found:** the first `requirements.txt` pinned `numpy==2.5.2`, grepped from `uv.lock`, which needs
Python 3.12; the gated environment runs 2.4.6 on 3.11. The resolver refused it before anything
shipped, and the pins are now read from the installed environment.

### To publish — Viraj's steps (Claude has no Hugging Face token and does not push)

```bash
uv run python space/build.py                       # rebuild space/dist/
hf auth login                                      # once, with a write token
hf repo create sqlalchemy-upgrade-agent --type space --space-sdk gradio
cd space/dist && git init && git lfs install && git lfs track "*.npy" "*.jsonl"
git remote add origin https://huggingface.co/spaces/<your-username>/sqlalchemy-upgrade-agent
git add . && git commit -m "Space: first publish" && git push -u origin main
```

Then in the Space's **Settings → Variables and secrets**, add the secret **`NVIDIA_API_KEY`**. The
page works without it (it says the key is missing) and never shows the key.

**Still open for the ROADMAP's gate** (*"a stranger can click your demo link and get a cited answer"*):
the push above, and a first answer from the live link. The CI gate's first real run (a PR) is the
other half.
### Deploy attempt, 17:40 — refused: Gradio Spaces now need a paid plan

`HfApi.create_repo(..., repo_type="space", space_sdk="gradio")` returned **HTTP 402 Payment
Required**: *"Static Spaces are free for everyone, but hosting Gradio and Docker Spaces on free
cpu-basic requires a PRO subscription."* (request `Root=1-6aa62173-5c25ac7412bfa8ce06c4bf6a`).
**Nothing was created** — the account lists no Spaces afterwards.

**Why the obvious workarounds do not work here, checked:**

| workaround | why not |
|---|---|
| a static Space | no server: cannot run the Python search, and an NVIDIA key in browser code is public |
| embed queries through NVIDIA's API so the server needs no torch | NVIDIA hosts no `bge-m3` (catalog checked 17:41); a different embedding model is a different index, and the gate would have to pass again from scratch |
| PRO subscription | breaks the standing zero-paid-calls rule; Viraj's call |

**The bundle in `space/dist/` is unchanged and still correct for any Python host with ~4 GB RAM.**

### The local demo, 17:50 — works, and uses the measured generator

Hosting was refused, so the demo runs locally in one command and **generates with `qwen2.5-coder:7b`
on Ollama, the model the 0.42 was measured on** (`DEMO_GENERATOR=ollama`); the page's notice says so.
No key needed.

```bash
DEMO_GENERATOR=ollama RAG_DENSE=memory PYTHONPATH=. uv run --with gradio==6.27.0 python space/app.py
```

**Superseded 2026-09-13 as the page to run** (Step 4c): `uv run --with fastapi --with uvicorn python space/web.py`,
same environment variables. The Gradio command above still works.

**Checked with a real question** (`g050`'s wording): the page built, the answer came back in 28.7 s,
and it was **"The sources do not answer this."** — `g050` is one of `D72`'s over-refusals with the
page in hand, on both machines. **The local demo reproduces the measured defect**, which is the honest
behaviour for a demo of a measured system.

### Free hosting that fits, checked 2026-09-12 (secondary sources; confirm on the provider's page)

The app needs **~4 GB RAM** (BGE-M3 + the reranker + torch). The no-torch shortcut is closed: NVIDIA
hosts no `bge-m3`.

| host | free allowance found | fits? |
|---|---|---|
| Hugging Face Gradio Space | **needs PRO** (HTTP 402, measured above) | no |
| Render, Koyeb | 512 MB RAM free instance | no — an eighth of what the models need |
| **Modal** (Starter) | $30/month credits, no payment method required | **yes**, scale-to-zero with a cold start |
| **Oracle Cloud Always Free** | Ampere A1 **halved June 2026 to 2 OCPU / 12 GB**; card at signup; regional capacity shortages | **yes**, always on; could even run qwen on CPU |
| Google Cloud Run | 360,000 GiB-seconds/month; billing account required | yes for a lightly used page; cold starts |

Sources: [InfoQ on Oracle's A1 cut](https://www.infoq.com/news/2026/07/oracle-cloud-free-tier-limits/),
[Cloud Run pricing](https://cloud.google.com/run/pricing),
[Modal free tier summary](https://aicreditmart.com/ai-credits-providers/modal-free-tier-how-to-get-30-month-in-compute-credits-2026/),
[Koyeb instances](https://www.koyeb.com/docs/reference/instances),
[Render free tier summary](https://www.srvrlss.io/provider/render/).

### Deployed on Modal (`D106`) — 2026-09-13

Viraj created a Modal token + the `nvidia` secret (`NVIDIA_API_KEY`). Claude wrote
`space/modal_app.py` and deployed.

**Public URL:** https://virajvaghasia--sqlalchemy-upgrade-agent.modal.run

```bash
uv run python space/build.py
uv run --with modal modal deploy space/modal_app.py
# stop warm containers after a code-only mount change: modal app stop sqlalchemy-upgrade-agent -y
```

**Checked live:** `GET /` and `/api/config` → 200; example *query.get() moved* → **200**, answered,
five sources, `Session.get` in the text, **116 s** on a cold start that still downloaded BGE-M3 and
the reranker into the HF volume. Later asks on a warm container are much faster.

**Found while deploying:** `index.retrieve` imported `qdrant_client` even when `version is None`, so
the memory demo crashed `/api/ask` without Qdrant installed. Gated behind `if version:`; pinned by
`test_retrieve_imports_qdrant_only_when_version_filtered`. Two other Modal footguns in the same
sitting: `include_source=False` and reading `requirements.txt` at import both crash-loop the
container — both recorded in `D106`.

---

## Night of 2026-09-12 — two checks, pre-registered at 23:55 before either ran

**Redeployed 2026-09-13 ~16:10 after `D107`** (`space/build.py`, `modal app stop`, `modal deploy`). Checked live: `GET /` 200; one question (*query.get() moved*) answered in **50.3 s** from a cold container with 5 sources, and the notice now reads *"0.58 end to end, and 91% of its answers judged fully supported"*. Billing: Viraj set the workspace usage limit to $30, equal to the Starter plan's monthly credits; the HF weights volume is 5.31 GiB, inside Modal's 1 TiB/month free storage (pricing page, fetched 2026-09-13).

### Step 4b — is the local demo the measured system?

**The claim on the page:** the local demo's notice says qwen is *"the generator the project measured:
… 0.43 on the Mac"*. That 0.43 went through **Qdrant**; the demo searches **in memory**. The gate showed
identical top-5s, so the pages reaching the model should be identical, and the answers should match
the measured ones up to the Mac's own day-to-day drift (`D84`).

**Run:** `RAG_DENSE=memory uv run python -m rag.score --refusals` on the Mac, all 100.
**Reference:** today's Mac arm A in `deliverables/framing-phase6.Darwin-arm64.json` (same machine,
same day, and it reproduced `D72`'s 19 over-refusal ids exactly).

| result | meaning |
|---|---|
| end to end **39/91 ± 2**, and the over-refused-with-page ids overlap arm A's 19 by **≥ 16** | the demo's path is the measured system; the notice stands |
| end to end off by **3 or more**, or overlap **< 16** | the notice overstates; it gets reworded to name the difference |

### Step 3e — are the escalated answers correct, executed on 2.0.51?

**The open question from `D101`:** 10 of 16 escalated answers agree with the verified page, but
correctness was *executed* for two answers only (`g016`, `g007`).

**Method, fixed before any check runs:** for each escalated answer (3b's 16, 3c's 13 page-absent),
Claude reads the answer and writes down **its central checkable claim about SQLAlchemy 2.0** — an API
that exists or does not, a call that raises or succeeds, a value returned — as a small Python check,
**before running it**. The checks run on real `sqlalchemy==2.0.51` with SQLite, in one script,
`tools/check_escalated.py`, whose output is a `# runnable` block.

- An answer whose central claim **cannot be made executable** (pure advice, a design opinion, a
  behaviour that needs a server) is counted **not checkable**, never correct.
- **Claude writes the checks, so this is not a human verdict (`D06`).** The checks are in the file,
  one per item, so anyone can read what was tested and dispute it.

**Rules:**

| result | meaning |
|---|---|
| of the 3b answers checked, **≥ 80%** pass | the reference judge's 10 is a fair estimate; the 0.53 upper bound stands as stated |
| **< 80%** pass | the escalation gain is overstated; the quoted upper bound is recomputed from the executed passes |

**Prediction:** about 70% of checkable 3b answers pass, and about 8 of the 29 are not checkable.


### Result — Step 3e (`D103`), 2026-09-12 23:57

```
# runnable: uv run --no-project --with 'sqlalchemy==2.0.51' --with aiosqlite --with greenlet python tools/check_escalated.py 2>/dev/null
ESCALATED ANSWERS, CENTRAL CLAIMS EXECUTED — sqlalchemy 2.0.51

3b page present
  g006  PASS           Connection.execute() rejects a plain SQL string; text() and exec_driver_sql() work
  g008  PASS           select([cols]) is rejected in 2.0; select(col, col) positionally works
  g013  PASS           a string attribute name in subqueryload is rejected; subqueryload(User.addresses) works
  g021  PASS           relationship(backref=...) is legacy but still works in 2.0; back_populates works
  g029  PASS           insert(t, values=...) and t.delete(whereclause) are rejected; insert(t).values().inline(), delete().where(), update().ordered_values() work
  g044  PASS           Table(autoload=True) without an engine is gone; Table(..., autoload_with=engine) reflects
  g048  PASS           joinedload('addresses') with a string is removed; joinedload(User.addresses) works
  g049  PASS           case([ (cond, val) ]) with a list is rejected in 2.0; case((cond, val), ...) positionally works
  g050  PASS           Engine has no execute(); with engine.connect() as conn: conn.execute(stmt) works
  g051  PASS           execute(select(User)).scalars().all() gives User objects; .all() gives Row tuples; session.scalars(...).first() gives a User
  g087  FAIL           a server_default column is NOT in __dict__ right after flush by default (expired); eager_defaults=True makes it present after flush
  g090  NOT_CHECKABLE  the answer's point is that the sources do not cover load_only's typing: a typing question is not executable here
  g095  PASS           populate_existing=True refreshes loaded objects, erasing pending unflushed changes
  g099  FAIL           under MappedAsDataclass: default= must be a constant (a callable is not allowed); default_factory= supplies callables; default= and insert_default= are mutually exclusive
  g100  PASS           AsyncSession.run_sync lets synchronous bulk_save_objects run inside async code
  g106  PASS           joinedload on a relationship to a polymorphic base does not load subclass-table columns unless with_polymorphic is used
  -> PASS 13  FAIL 2  NOT_CHECKABLE 1  ERROR 0   pass rate 87% of checkable

3c page absent
  g007  PASS           MetaData(bind=engine) raises TypeError in 2.0; MetaData() then create_all(engine) works
  g011  PASS           Query.join(..., aliased=True) is gone; join(User.addresses.of_type(a1)) and join(a1, User.addresses) work
  g016  FAIL           row.keys() exists on Row in SQLAlchemy 2.0
  g020  PASS           the cascade_backrefs behaviour is gone: assigning address.user = user (user in the session) does not add the address, so it is not INSERTed unless added explicitly
  g022  PASS           Engine.scalar() no longer exists in 2.0
  g028  PASS           driver-level autocommit works via execution_options(isolation_level='AUTOCOMMIT'), and Connection.execution_options() modifies the connection in place, returning it
  g036  PASS           MetaData(bind=...) raises TypeError in 2.0; sessionmaker(engine) is where the engine goes
  g037  PASS           a plain string passed to conn.execute fails; wrapping it in text() works
  g039  PASS           session.execute(select(User)).all() returns Row tuples; .scalars().all() returns User objects
  g040  PASS           legacy Query de-duplicates parents automatically when joinedload-ing a collection
  g058  PASS           on 1.4 with 2.0 warnings on, conn.execute('insert ...') on engine.connect() emits RemovedIn20Warning for implicit autocommit and for passing a string
  g085  PASS           calling session.begin() while a transaction is already in progress raises in 2.0
  g094  PASS           objects added without an explicit begin() are not discarded: commit() persists them
  -> PASS 12  FAIL 1  NOT_CHECKABLE 0  ERROR 0   pass rate 92% of checkable

rule (3b, >= 80% of checkable pass): 87% -> the 0.53 upper bound stands as stated
```

**Against the rule:** 3b **13 of 15 checkable = 87% ≥ 80%**, so **the 0.53 upper bound stands**, now on
executed evidence rather than a judge's opinion alone. **Prediction wrong twice:** ~70% passing
(actual 87%) and ~8 not checkable (actual 1).

**The three genuine failures, each diagnosed rather than counted:**

| item | what the answer claimed | real 2.0.51 |
|---|---|---|
| `g087` | a `server_default` column is **not** in `__dict__` after flush by default | it **is**: `eager_defaults` now defaults to `"auto"`, fetching it with `RETURNING` where the backend supports it (SQLite does). The answer describes older, backend-dependent behaviour as the default |
| `g099` | under `MappedAsDataclass`, a callable `default=` is not allowed; `default=` and `insert_default=` are mutually exclusive | **both accepted**; the lambda is stored as the value itself (`D().v` is the function object) |
| `g016` | `row.keys()` exists on `Row` in 2.0 | `hasattr(row, "keys")` is **False** (`D100`) |

**Disclosed correction, made after the first run.** `g028` first came back FAIL. The answer was right;
the check was wrong: it read `Connection.get_isolation_level()`, which on SQLite reports
`SERIALIZABLE` even in autocommit mode. At the driver, `sqlite3`'s `isolation_level` goes from `''` to
`None` (autocommit) once the option is set. The check now reads the driver, with the reason in a
comment, and `g028` passes. **Changing a check after seeing its result is a deviation from the
pre-registration**, allowed here only because the original demonstrably tested the wrong thing; it is
recorded so the reader can reject it.

**Executed vs judged, item by item.** Of the reference judge's 10 `SUPPORTED` 3b answers, **7** pass
execution, **2 fail** (`g087`, `g099`) and 1 is not checkable (`g090`). Six answers it called only
`PARTIAL` have correct central claims (`g008 g013 g021 g050 g051 g106`). The judge's *rate* was close;
its *items* were wrong in both directions: the third time this phase (`D96`, `D101`).

**What it is not:** a human verification (`D06`). Claude wrote the checks and chose each answer's
"central claim"; a correct central claim does not make every sentence of an answer correct.

### Result — Step 4b, night of 2026-09-12: the local demo IS the measured system

`RAG_DENSE=memory uv run python -m rag.score --refusals` (Mac, all 100; ENV — needs Ollama):

```
refused — over-refusal          45/91  (49%)
  with the answer IN the prompt  19   g006, g008, g013, g021, g044, g048, g049, g050, g051, g064,
                                      g084, g087, g090, g095, g099, g100, g103, g106, g116
answered — FABRICATED           2/9   g056, g065
answer reached the prompt       58/91
...and was answered, not refused 39/91  = 0.43   END TO END
```

**Against the rule:** end to end **39/91**, exactly the reference; the 19 over-refused ids overlap
today's Mac arm A (`framing-phase6.Darwin-arm64.json`) **19 of 19**, none only on one side; the two
fabrications are the same two. **Pass: the demo's notice ("the generator the project measured … 0.43
on the Mac") stands.** Same machine and same day as the reference, so this says nothing new about
cross-day drift (`D84`); it says the in-memory search changed nothing that reaches the model.
---

## Step 4c — the hand-designed page, four browser checks (pre-registered 2026-09-13, before opening the browser)

Commit `7cf1637` replaced the Gradio look with `space/static/index.html` served by `space/web.py`. Only
the answered state and one citation click were checked in Chrome. Four checks remain, each with its
rule written here first:

| # | check | PASS if | prediction |
|---|---|---|---|
| 1 | the **declined** chip, *engine.execute gone* (`g050`'s wording) | the pill reads **Declined**, the "it declined rather than guess" note shows, the refusal is quoted rather than rendered as an answer, five source cards render | declines — `g050` is on `D72`'s over-refusal list on both machines and on Step 4b's 19 |
| 2 | **phone width**, a real 400 px viewport (an iframe, since a desktop Chrome window will not narrow that far) | the page never scrolls sideways (`scrollWidth ≤ clientWidth`) with an answer and sources on screen; answer and sources stack; code scrolls inside its own box | **fails somewhere**: source cards print long unbroken paths and code with `pre-wrap` but nothing breaks a long token |
| 3 | the **error** state, Ollama quit for real (not a mocked URL) | the pill reads **Not answered**, the message names Ollama, **the five sources still render** (`demo.answer` returns them), the server stays up and the next question works once Ollama is back | passes — `SystemExit` is caught in `demo.answer` and tested |
| 4 | the **notice** after a hard reload | the notice shows `qwen2.5-coder:7b` as a code element and its text contains **no literal backtick** | passes |

### Result — Step 4c, 2026-09-13 (Mac, Chrome)

| # | seen | against the rule |
|---|---|---|
| 1 | **Declined**, 36.1 s, the note shown, the refusal quoted (`“The sources do not answer this.”`), 5 cards, 0 citation links | **pass.** Prediction right. **But the note was false for this example** (below) |
| 2 | a real answered question at 398 px: `scrollWidth 398`, one column, **no code block in the answer**. A synthetic answer through the page's own `renderAnswer` with one long code line: **`scrollWidth 991`** | **fail.** Prediction right, cause wrong: not the source cards but `grid-template-columns: 1fr`, which cannot shrink below its widest content. **Fixed** with `minmax(0, 1fr)` plus `overflow-wrap: anywhere` on prose, paths and card text: `scrollWidth 398`, code `883` px scrolling inside a `266` px box, long names wrapped (screenshot checked) |
| 3 | **Not answered**, *"The local answer model (Ollama) is not running…"*, **5 cards**, Ask enabled again; the next question after restart answered normally | **pass, with a deviation from the rule:** Ollama was **not** quit for real. `osascript quit` returned *"User canceled"* and I did not force it; swap was 14.5 of 15.4 GB, so no second server either. The same `web.py` ran with only `ask.OLLAMA_URL` pointed at a closed port, the connection-refused error a stopped Ollama gives, through the same `SystemExit` catch |
| 4 | after a reload, the notice's `qwen2.5-coder:7b` is a `<code>` element, `textContent` contains no backtick | **pass** |

**The note, corrected.** It said *"The five pages it found don't answer this."* `g050` is a measured
over-refusal: its answer page is in the five. The page cannot know whether a decline is honest, so the
note now says the model judged it, and that on the 100 questions **19 of its 52 declines had the right
page in hand**. Derived from prompt `D`'s rows in `deliverables/prompt-sweep-phase4.json` with
`ask.refused`: 52 declines = 45 answerable + 7 unanswerable; page present on 19, the same 19 ids as
Step 4b. The error message's *"The sources below"* became *"its sources are listed with this message"*:
on a desktop they are beside it.

**The bundle now ships this page** (`space/build.py`: `web.py` + `static/`, not `app.py`; pins gain
`fastapi==0.141.1` and `uvicorn==0.52.4`, read from the environment the checks ran in, and lose
`gradio`). Why: the Gradio page existed for a Hugging Face Gradio Space, which was refused, and the
remaining hosts (Modal, Oracle) run any Python process. **Checked:** built (36 files, 18.2 MiB), started
from `space/dist/` with `uv run --no-project --python 3.11 --with-requirements requirements.txt python web.py`,
asked *query.get() moved*: answered with `[1]` in 64.1 s (cold), and the click opened card 1.

---

## Step 4d — the demo's hosted generator on all 100 (pre-registered 2026-09-13, before any call)

**The question.** The hosted demo would generate with `nvidia/nemotron-3-ultra-550b-a55b`, and its
notice says the 0.42 "does not describe these answers" because nothing does yet. The 53 escalation
rows (`D99`, `D100`) are only the questions qwen declined. **This run asks all 100**, shipped prompt,
same retrieval, one sitting, on the Mac. Viraj approved ~200 NVIDIA free-credit calls (2026-09-13).

**Why the Mac, not the lab.** Generation happens on NVIDIA's servers, and retrieval reproduces exactly
across the two machines (`D83`; `route.join_check` found no page-present flag that differs). `D95`'s
"the lab rules" was about the local qwen drifting on the Mac; it does not reach a hosted model.

**Held fixed:** `ask.SYSTEM` + `ask.build_prompt`, temperature 0, `index.retrieve` at `DEFAULT_K = 5`
(Qdrant), the 100 verified golden items. **Scored with the repo's own definitions:** `ask.refused`,
`score.rank_of_first_hit` for "answer in the prompt", `route.delivered` for end to end (`D72`).

**Layer 1 — generation, 100 calls.** Command: `rag.escalate --all --generate`, rows
`deliverables/nemotron-all-phase6.json`.

| measure | rule, written before the run |
|---|---|
| completeness | `EMPTY` (no answer text) or unasked rows **> 5 → the run is not quoted**; fewer are listed and dropped from both sides of every pairing |
| end to end | `delivered / 91`, printed by the same `score.report_refusals` as qwen's |
| vs qwen, paired | against the **lab's** qwen rows (`prompt-sweep-round16.Linux-x86_64.json`, `D`, 38/91), by id on `delivered`. **Ahead** if fixed ≥ 6, broken ≤ 1 and exact McNemar p < 0.05 (`D61`'s bar). **Behind** if broken > fixed with p < 0.05. Otherwise **level**. The Mac's `prompt-sweep-phase4.json` `D` (39/91) prints as context only |
| fabrications | unanswerable items answered; **no worse** if ≤ 2 (qwen's count, `g056` `g065`) |

**Layer 2 — faithfulness, one call per answered item.** Judge `openai/gpt-oss-20b` on NVIDIA
(`faithful.NVIDIA_JUDGE`, the scored judge since Step 3b), reading each answer against **the five
pages it was given**. Bar: **SUPPORTED ≥ 80%** of judged answers. **Not comparable with qwen's
92% / 77–85%**, which came from a different judge (`gemma4:e4b`); judging qwen's answers with this
judge would be ~48 more calls and is not in this run. And `SUPPORTED` is not "correct" (`D100`).

**Repeat — 20 calls.** The first 20 golden ids in sorted order (chosen by position, not by result),
asked again after the 100, into `nemotron-all-repeat-phase6.json`. **Decision stable** if
answered/declined agrees on **≥ 19 of 20**. Identical answer text is counted, with no bar.

**Prediction (Claude, before the run).** End to end **≈ 52/91 = 0.57**: qwen's 39 answered items stay
answered, plus ~16 of the 20 page-present refusals (`D99` answered 16 of 20), minus ~2 new declines.
Against the lab's 38: **fixed ~17, broken ~3 → ahead**. Fabrications **1**. SUPPORTED **~75%, below
the bar** (`D99` was 62% on the hardest 20; easier items should do better but not reach 80%).
Repeat: decisions **19–20 of 20**; identical text **fewer than half** (a reasoning model).

### Result — Step 4d, 2026-09-13 11:32–12:39 (Mac; calls on NVIDIA free credits)

190 calls: 100 generations, 20 repeats, 69 judgments, and 1 re-judgment (below). No `EMPTY` answers,
no skipped questions.

```
# runnable: uv run python -m rag.escalate --all
ALL 100 — nvidia/nemotron-3-ultra-550b-a55b, shipped prompt, k=5  (asked 100, EMPTY 0)

REFUSALS  —  generation, at k=5 (D62; not averaged into recall)
  unanswerable items                9
    refused — correct               9/9  (100%)
    answered — FABRICATED           0/9  (0%)
  answerable items                  91
    refused — over-refusal          22/91  (24%)
      with the answer IN the prompt   5   generation defect (the Q18/Q19 class)   g053, g064, g084, g103, g116
      with the answer absent         17   honest — retrieval never supplied it

  answer reached the prompt          58/91   <- retrieval's ceiling, at k=5
  ...and was answered, not refused   53/91   = 0.58   END TO END
  generation loses                    5/91   = 0.05 of the ceiling, invisible to every recall figure

  vs lab qwen2.5-coder:7b, Round 16 (the rule)
    delivered 53 vs 38 over 91 paired   fixed 16  broken 1  exact McNemar p = 0.0003  -> AHEAD
    fixed   g006 g008 g013 g021 g029 g044 g048 g049 g050 g051 g087 g090 g095 g099 g100 g106
    broken  g053
  vs Mac qwen2.5-coder:7b, 2026-08-23 (context)
    delivered 53 vs 39 over 91 paired   fixed 15  broken 1  exact McNemar p = 0.0005
    fixed   g006 g008 g013 g021 g044 g048 g049 g050 g051 g087 g090 g095 g099 g100 g106
    broken  g053

  fabrications  0   rule <= 2  -> no worse   -

  FAITHFULNESS (openai/gpt-oss-20b, against the five pages given; SUPPORTED is not 'correct')
    judged 69 of 69 answered   SUPPORTED 53 = 77%   rule >= 80% -> FAIL
    not SUPPORTED  g013=PARTIAL g025=PARTIAL g028=PARTIAL g044=PARTIAL g048=PARTIAL g051=PARTIAL g055=PARTIAL g058=PARTIAL g060=PARTIAL g062=PARTIAL g078=PARTIAL g080=PARTIAL g085=PARTIAL g106=PARTIAL g109=PARTIAL g121=PARTIAL

  REPEAT  20 asked twice   same decision 19   rule >= 19 -> stable   identical text 0   flipped g007

  tokens, as returned by the API: prompt 259231, output 80270  (over 120 generation calls)
  shadow cost of the 100: $0.3447, $3.45 per 1000 queries  (price snapshot; calls were free credits)
```

**Against the rules written first:**

| measure | result | rule | prediction |
|---|---|---|---|
| completeness | 100 asked, 0 `EMPTY` | quoted | — |
| end to end | **53/91 = 0.58** | — | ≈ 52/91 (right) |
| vs lab qwen, paired | **16 fixed, 1 broken, p = 0.0003** | **AHEAD** | fixed ~17, broken ~3, ahead (right) |
| fabrications | **0 of 9** | no worse (≤ 2) | 1 (one too many) |
| faithfulness | **53 of 69 SUPPORTED = 77%**, 16 PARTIAL, **0 UNSUPPORTED** | **FAIL** (≥ 80%) | ~75%, below the bar (right) |
| repeat | decision **19 of 20**, identical text **0 of 20** | **stable** | 19–20; text under half (right, and more extreme) |

**Retrieval is not what changed.** The ceiling is 58/91 on both runs and no question's page-present flag
differs from the lab's, so the pairing compares the same five pages question by question. The whole
gain is generation: qwen lost 20 of the 58 where it had the page, nemotron loses 5.

**The one "broken" item, read.** `g053` asks for the SQLAlchemy 2.0 version of **Flask-SQLAlchemy's**
`User.query.get(1)`. Its page is rank 1 and covers `session.query(User).get` → `session.get`; it never
mentions Flask-SQLAlchemy. Nemotron declined *on exactly that ground*; qwen answered with the right
fix. The stricter reader lost this item, not the weaker one.

**The repeat's flip, read.** `g007` gave the same content twice. Run 1 opens *"The sources do not answer
this specific question…"* and then gives the correct `metadata_obj.create_all(engine)` fix with code;
the repeat opens *"Based on the provided sources…"* with the same fix. `ask.refused` reads the opening,
so one is a decline and one an answer. The page was absent both times, so end to end does not move.

**Found in my instrument during the run, and fixed test-first:** the judge's reply for `g025` was
**empty** and came back `UNPARSED`, and the report counted it as judged (*"judged 69 of 69"*). The judge
loop also skipped any row with a verdict field, so a resume would never have asked it again. Now
`UNPARSED` is not a verdict and a resume asks it; `g025` was asked once more and came back `PARTIAL`
(the row carries a `judge_note`). **The FAIL did not depend on it:** 53/68 = 77.9%, and 54/69 = 78.3%
even if it had come back SUPPORTED.

**Exploration, NOT pre-registered.**
- **Nemotron's declines explain themselves; qwen's do not.** Its 31 declines run 258–869 characters and
  say what the pages cover. qwen's 53 have a median of **31 characters**, the bare refusal sentence. Only
  one nemotron decline (`g007`) carries code after the refusal opening, so the prefix detector is not
  hiding answers: the 0.58 is not deflated in any way that matters.
- **Of the 16 fixed items, 11 are SUPPORTED and 5 PARTIAL** (`g013 g044 g048 g051 g106`), none
  UNSUPPORTED. The extra answers mostly hold up against their pages.
- **Faithfulness is not comparable with qwen's 77–92%**: a different judge (`gemma4:e4b`) produced those.
  Judging qwen's 48 answers with `gpt-oss-20b` is the measurement that would compare them.

**Cost.** 215177 prompt + 67260 output tokens for the 100; shadow cost **$0.34, i.e. $3.45 per 1000
queries** at the snapshot price, against the cascade's $1.81 (`D100`), which sends only refusals. The
calls were free credits.

---

## Step 4e — the same judge on both models (pre-registered 2026-09-13, before any call)

**The question.** Step 4d's 77% cannot be set beside qwen's 77–92%, because a different judge produced
those (`gemma4:e4b`). Here `openai/gpt-oss-20b`, the judge that read nemotron's answers, reads **the lab
qwen's 47 answers** (`prompt-sweep-round16.Linux-x86_64.json`, prompt `D`). Viraj approved it
(2026-09-13). ~47 NVIDIA free-credit calls.

**Held fixed.** The same judge prompt (`faithful.judge_answer`), the same model id, the same day. **The
pages:** qwen's rows do not store their five page ids, so each answer is judged against the five pages in
nemotron's Step 4d rows for the same question. That is legitimate only because retrieval reproduces
across the machines (`D83`); the report re-checks it by comparing, for every question, whether the answer
page was among the five in both runs, and **any mismatch drops that question from the pairing**.

| measure | rule, written first |
|---|---|
| paired, the **42** questions both models answered | SUPPORTED yes/no by id. **nemotron MORE faithful** if it is SUPPORTED where qwen is not on ≥ 6, the reverse on ≤ 1, and exact McNemar p < 0.05. **LESS** if the reverse outnumbers it with p < 0.05. Otherwise **LEVEL** |
| rates | qwen `SUPPORTED / judged` and nemotron's 53/69 printed side by side, **no verdict** (the two sets of answered questions differ) |
| completeness | an `UNPARSED` verdict is asked again once; still unparsed → dropped from both sides and listed |

**Prediction (Claude).** **LEVEL.** qwen ~70% SUPPORTED: its answers are shorter and cite less (`D73`),
which hurts "fully supported" more than it hurts "not contradicted".

## Step 4f — are nemotron's 53 delivered answers correct? Executed on 2.0.51 (pre-registered 2026-09-13)

**The question.** `SUPPORTED` means the pages back an answer, not that it is right (`D100`, `D103`). Step 3e
executed 29 escalated answers; today's answers are new text (0 of 53 identical to the saved escalations),
so those checks do not carry over. **These are the 53 that count toward the 0.58**: answerable, page in
the prompt, answered.

**Method, Step 3e's rules unchanged.** Claude reads each answer and writes its central checkable claim
as a string beside a check in `tools/check_nemotron_all.py`, **committed before its first run**. A check
tests the old behaviour the answer says is gone **and** the new behaviour it recommends, with narrow
exceptions. `NOT_CHECKABLE` (typing, advice, a claim that is only "the sources do not cover X") is never
counted as correct. A crash in a check is `ERROR`, reported apart. **Any check changed after the first
run is marked in a comment and listed here.** Claude wrote the checks; this is not a human verdict (`D06`).

| measure | rule |
|---|---|
| correctness | **≥ 80% of checkable answers PASS** → the 0.58 stands as "delivered and, where checkable, correct". Below → the 0.58 is overstated, and the executed-correct count is quoted beside it |

**Prediction (Claude).** ~88% of checkable pass (Step 3e: 13 of 15 = 87%); 5–10 `NOT_CHECKABLE`.

### Result — Step 4e, 2026-09-13 14:53–15:02 (Mac; 47 NVIDIA free-credit calls)

The same judge on the lab qwen's 47 answers, each against nemotron's five pages for that question. No
`UNPARSED` verdict (the second pass asked nothing), no question dropped for a page-flag mismatch.

```
# runnable: uv run python -m rag.escalate --all
ALL 100 — nvidia/nemotron-3-ultra-550b-a55b, shipped prompt, k=5  (asked 100, EMPTY 0)

REFUSALS  —  generation, at k=5 (D62; not averaged into recall)
  unanswerable items                9
    refused — correct               9/9  (100%)
    answered — FABRICATED           0/9  (0%)
  answerable items                  91
    refused — over-refusal          22/91  (24%)
      with the answer IN the prompt   5   generation defect (the Q18/Q19 class)   g053, g064, g084, g103, g116
      with the answer absent         17   honest — retrieval never supplied it

  answer reached the prompt          58/91   <- retrieval's ceiling, at k=5
  ...and was answered, not refused   53/91   = 0.58   END TO END
  generation loses                    5/91   = 0.05 of the ceiling, invisible to every recall figure

  vs lab qwen2.5-coder:7b, Round 16 (the rule)
    delivered 53 vs 38 over 91 paired   fixed 16  broken 1  exact McNemar p = 0.0003  -> AHEAD
    fixed   g006 g008 g013 g021 g029 g044 g048 g049 g050 g051 g087 g090 g095 g099 g100 g106
    broken  g053
  vs Mac qwen2.5-coder:7b, 2026-08-23 (context)
    delivered 53 vs 39 over 91 paired   fixed 15  broken 1  exact McNemar p = 0.0005
    fixed   g006 g008 g013 g021 g044 g048 g049 g050 g051 g087 g090 g095 g099 g100 g106
    broken  g053

  fabrications  0   rule <= 2  -> no worse   -

  FAITHFULNESS (openai/gpt-oss-20b, against the five pages given; SUPPORTED is not 'correct')
    judged 69 of 69 answered   SUPPORTED 53 = 77%   rule >= 80% -> FAIL
    not SUPPORTED  g013=PARTIAL g025=PARTIAL g028=PARTIAL g044=PARTIAL g048=PARTIAL g051=PARTIAL g055=PARTIAL g058=PARTIAL g060=PARTIAL g062=PARTIAL g078=PARTIAL g080=PARTIAL g085=PARTIAL g106=PARTIAL g109=PARTIAL g121=PARTIAL

  SAME JUDGE, BOTH MODELS (openai/gpt-oss-20b, each answer against its five pages)
    qwen2.5-coder:7b (lab)   judged 47 of 47 answered   SUPPORTED 37 = 79%   PARTIAL 7   UNSUPPORTED 3
    nemotron                 judged 69 of 69 answered   SUPPORTED 53 = 77%   PARTIAL 16   UNSUPPORTED 0
    paired over 42 answered by both   nemotron-only SUPPORTED 3  qwen-only SUPPORTED 6  exact McNemar p = 0.5078   -> LEVEL
      nemotron-only  g015 g030 g115
      qwen-only      g055 g060 g062 g080 g109 g121

  REPEAT  20 asked twice   same decision 19   rule >= 19 -> stable   identical text 0   flipped g007

  tokens, as returned by the API: prompt 259231, output 80270  (over 120 generation calls)
  shadow cost of the 100: $0.3447, $3.45 per 1000 queries  (price snapshot; calls were free credits)
```

| measure | result | rule | prediction |
|---|---|---|---|
| paired, answered by both | **42**: nemotron-only SUPPORTED **3**, qwen-only **6**, p = 0.51 | **LEVEL** | LEVEL (right) |
| rates, no verdict | qwen **37/47 = 79%** (7 PARTIAL, **3 UNSUPPORTED**); nemotron **53/69 = 77%** (16 PARTIAL, **0 UNSUPPORTED**) | — | qwen ~70% (too low) |

**Read, not just counted.** qwen's 3 UNSUPPORTED are `g065` (the invented Alembic recipe, `D77`), `g117`,
`g119`. Nemotron has none at that grade: its misses are all "goes beyond the pages", never "not in the
pages". **The same judge rates the two models level on faithfulness**, so Step 4d's gain is in answering,
not in grounding.

### Result — Step 4f, 2026-09-13 (Mac; no calls)

```
# runnable: uv run --no-project --with 'sqlalchemy==2.0.51' --with aiosqlite --with greenlet python tools/check_nemotron_all.py 2>/dev/null
NEMOTRON'S 53 DELIVERED ANSWERS, CENTRAL CLAIMS EXECUTED — sqlalchemy 2.0.51

  g002  FAIL           Query.from_self() is gone in 2.0; select(...).subquery() + aliased(User, subq) / aliased(Address, subq) selects both entities from the subquery
  g004  PASS           Engine has no execute(); Connection.execute runs statements; a plain string is rejected, text() and exec_driver_sql() work; **kwargs parameters are rejected, a dict works
  g006  PASS           Session.execute also rejects a raw SQL string in 2.0; text() works
  g008  PASS           select([cols]) is rejected in 2.0; select(col, col) positionally works
  g013  PASS           subqueryload('addresses') with a string is rejected; subqueryload(User.addresses) works
  g015  PASS           row['id'] fails in 2.0; row._mapping['id'], result.mappings() and row.id work
  g017  PASS           in 2.0, select(User).options(joinedload(User.addresses)) through session.execute raises unless .unique() is called; with .unique() the parents are not duplicated
  g018  PASS           Session(autocommit=True) is rejected in 2.0; Session + begin() + commit() persists
  g019  PASS           session.begin(subtransactions=True) is rejected in 2.0; the in_transaction() context-manager recipe nests without error and the outer block commits once
  g021  PASS           relationship(backref=...) still works in 2.0 (legacy); back_populates works
  g024  PASS           session.get(User, 5) is the replacement; Query.get() still exists as legacy (LegacyAPIWarning)
  g025  PASS           in 2.0 future= on create_engine is optional: future=True is accepted, future=False is rejected, and omitting it gives the same Engine
  g026  PASS           on 1.4, Session(future=True) removes subtransactions (begin(subtransactions=True) raises); in 2.0 future=True is accepted and future=False rejected   [1.4.52 said: NotImplementedError]
  g027  PASS           on 1.4, SQLALCHEMY_WARN_20=1 turns on RemovedIn20Warning (engine.execute warns only with it set)   [counts: with 1, without 0]
  g029  PASS           insert(t, values=...) and t.delete(whereclause) are rejected; insert().values().inline(), .returning(), delete().where(), update().ordered_values() work
  g030  PASS           from sqlalchemy.orm import declarative_base works; the sqlalchemy.ext.declarative import still works but warns it moved; DeclarativeBase works
  g031  PASS           sqlalchemy.orm.mapper() is gone in 2.0; registry().map_imperatively() maps a class
  g032  PASS           query(User).join('orders', 'items') chained strings are rejected; individual join() calls work
  g033  PASS           select(User, Address.email).join().distinct().order_by(Address.email) then session.execute(stmt).columns(User).all() returns only User per row
  g034  PASS           select_entity_from is gone; aliased(User, select(User).where(...).subquery()) selects from it
  g035  PASS           statement caching is built in and automatic in 2.0: the second run of the same select is a cache hit
  g038  PASS           session.execute(select(User)).scalars().all() and session.scalars(select(User)).all() both give User objects
  g041  PASS           backref still works in 2.0; back_populates on both sides of a many-to-many works
  g043  PASS           select(..., select_from=, order_by=) keyword arguments are rejected; .select_from().order_by() works
  g044  PASS           Table(autoload=True) without an engine is gone; autoload_with=engine / connection and reflect(engine) work
  g045  PASS           t.select().execute() is gone (a Select has no execute); connection.execute(t.select()) runs it
  g046  PASS           Session(autocommit=True) is rejected; a Session autobegins on first database access; with session.begin(): commits
  g047  PASS           subtransactions are gone; the in_transaction() recipe nests; begin_nested() is a SAVEPOINT: rolling it back discards u3 and keeps u1, u2, which commit at the end of sessionmaker.begin()
  g048  PASS           joinedload('addresses') with a string is removed; joinedload(User.addresses) works
  g049  PASS           case() no longer accepts a list of WHENs in 2.0; case((cond, val), ...) positionally works. SECONDARY SLIP, not the verdict: the answer says the list form 'emits a deprecation warning', which is 1.4's behaviour; on 2.0 it is rejected
  g050  PASS           Engine has no execute(), a Select has no execute(); with engine.connect() as conn: conn.execute(stmt) works
  g051  PASS           execute(select(User)).scalars().all() gives User objects; execute(select(User.name, User.id)).all() gives Row tuples; session.scalars() returns a ScalarResult
  g055  PASS           on 1.4, SQLALCHEMY_WARN_20=1 enables RemovedIn20Warning   [counts: with 1, without 0]
  g062  PASS           Mapped[Literal[...]] with type_annotation_map {Literal: Enum(enum.Enum)} gives an Enum column with the literal's values; mapped_column(Enum(..., name='status_enum')) works explicitly. SECONDARY SLIP, not the verdict: approach 1's code uses enum.Enum without importing enum
  g078  FAIL           on 1.4, RemovedIn20Warning is emitted only when SQLALCHEMY_WARN_20 is set, so leaving it unset suppresses them   [counts: with 1, without 1]
  g079  NOT_CHECKABLE  the answer's point is that the sources do not cover options with Session.get; a claim that is only 'the sources do not cover X' is not executable
  g080  PASS           select(Book).options(load_only(Book.title, Book.summary)) selects id, title, summary only; one load_only per entity; selectinload(User.books).load_only(Book.title) and defaultload(...) compile
  g081  PASS           Session(autobegin=False) refuses database work until begin() is called; with begin() it works
  g083  PASS           there is no engine.execute() in 2.0; engine.begin() commits on exit, and engine.connect() + conn.commit() commits
  g087  FAIL           a server_default column is NOT in __dict__ right after flush by default (expired, loaded on access); eager_defaults=True makes it present after flush
  g088  PASS           Session(bind=connection, join_transaction_mode='create_savepoint') inside connection.begin(): session.commit() and session.rollback() touch only savepoints, and the outer rollback removes everything
  g090  NOT_CHECKABLE  a typing question (load_only attrs typing on 2.0.0b4): not executable here
  g095  PASS           populate_existing fully refreshes loaded instances, erasing pending changes; with selectinload it replaces the loaded collection
  g098  PASS           in 2.0 the backref cascade is gone: with u1 persistent, a1.user = u1 does not put a1 in the session, so it must be added explicitly; relationship(cascade_backrefs=False) is still accepted. NOTE: one bullet reads the direction backwards ('assigning a parent to a child in a session -> parent not added'); the forward many-to-one cascade does add it. Not the central claim
  g099  FAIL           under MappedAsDataclass: default= must be a constant (a callable is rejected); default_factory= supplies callables; default= and insert_default= are mutually exclusive
  g100  PASS           AsyncSession.run_sync can run synchronous bulk_save_objects inside async code
  g106  PASS           joinedload on a relationship to a polymorphic base does not load subclass-table columns; joinedload(Owner.pets.of_type(with_polymorphic(Pet, [Dog], flat=True))) does
  g109  PASS           yield_per together with unique() raises when ORM rows are fetched
  g110  PASS           in 2.0 create_engine's future= must be True if given (False is rejected); the Connection has commit()/rollback(); strings need text(); the Engine has no execute()
  g111  PASS           with engine.connect() does not commit by itself (work is rolled back at close); engine.begin(), conn.begin() and conn.commit() all commit
  g115  PASS           2.0 connections: a plain string is rejected and text() works; engine.begin() commits; engine.connect() needs an explicit commit(); parameters go as a dict, not **kwargs
  g118  PASS           two aliased(Address) with User.addresses.of_type(alias) join the same table twice under two aliases
  g121  PASS           2.0 rows: execute(select(User)).scalars().all() gives objects; Row supports row[0], row.name and row._mapping['name']; result.mappings() keys ORM entities by class name. SECONDARY SLIP, not the verdict: it calls row['name'] 'deprecated'; on 2.0 it fails

  PASS 47  FAIL 4  NOT_CHECKABLE 2  ERROR 0   pass rate 92% of checkable
  FAIL           g002 g078 g087 g099
  NOT_CHECKABLE  g079 g090

rule (>= 80% of checkable pass): 92% -> the 0.58 stands as 'delivered and, where checkable, correct'
```

**Against the rule: 47 of 51 checkable = 92% → PASS.** The 0.58 stands as "delivered and, where
checkable, correct". Prediction ~88%, NOT_CHECKABLE 5–10: close on the rate, too many on the
not-checkable (2).

**First run, and what changed after it, disclosed.** The first run read **43 PASS, 7 FAIL, 2
NOT_CHECKABLE, 1 ERROR**. Every FAIL and the ERROR was investigated in isolation before counting:

| id | first run | cause | now |
|---|---|---|---|
| `g031` | FAIL | **the check was wrong.** `from sqlalchemy.orm import mapper` still imports on 2.0.51, as a stub that raises when called: *"The 'sqlalchemy.orm.mapper()' function is removed as of SQLAlchemy 2.0. Use ... map_imperatively()"*. The check now calls it | PASS |
| `g027`, `g055` | FAIL (`with 1, without 1`) | **the check was wrong.** Without `SQLALCHEMY_WARN_20`, 1.4.52 emits one summary warning (*"Deprecated API features detected! ... set SQLALCHEMY_WARN_20=1 to show all"*); with it, the specific *"The Engine.execute() method is considered legacy"*. The claim is about the specific ones | PASS (`with 1, without 0`) |
| `g100` | ERROR | **the check was wrong.** It discarded its `Address` class; alone it passed, in the full run *"expression 'Address' failed to locate a name"* | PASS |
| `g078` | FAIL | **the answer is wrong, check unchanged.** *"Leaving SQLALCHEMY_WARN_20 unset suppresses them … the program runs silently"*: run as a script with default filters, 1.4.52 prints a `RemovedIn20Warning` before `[(1,)]` | FAIL |
| `g002` | FAIL | **the answer is wrong.** Its own code, `aliased(Address, subq)` over a subquery that selected only `Address.email`, raises `NoSuchColumnError: ... 'addresses.id'` | FAIL |
| `g087` | FAIL | **the answer is wrong, and it is Step 3e's failure again.** 2.0's `eager_defaults` is `"auto"`: on a backend with RETURNING (SQLite here) the server default **is** in `__dict__` after flush | FAIL |
| `g099` | FAIL | **the answer is wrong, Step 3e's other failure again.** A callable `default=` and `default=` + `insert_default=` are both accepted under `MappedAsDataclass` on 2.0.51 | FAIL |

**The verdict does not depend on the corrections:** with all four corrected checks counted as failures,
it is 43 of 51 = 84%, still above the bar. One check was also changed **before** its first run and is
not a post-hoc correction: `g002` first tested a gentler query than the answer's own code; it was
rewritten to run the answer as written.

**Exploration, NOT pre-registered: the judge's grade does not predict correctness.** Crossing today's
judge verdicts with the executed results:

```
judge SUPPORTED   executed PASS 36   FAIL 3 (g002 g087 g099)   NOT_CHECKABLE 2
judge PARTIAL     executed PASS 11   FAIL 1 (g078)
```

92% of SUPPORTED and 92% of PARTIAL answers are correct when run. **So Step 4d's faithfulness FAIL (77%)
is not a correctness problem**: the answers the judge marked PARTIAL are right as often as the ones it
marked SUPPORTED, and three of the four wrong answers were marked SUPPORTED. The same shape as `D103`.

**Two answers repeat a wrong claim across days.** `g087` and `g099` failed in Step 3e (2026-09-12) and
fail again with different wording today. A stronger model is not a correction for a claim the pages
themselves invite.

### Step 4c, scripted — `tools/check_page.py` with the `webapp-testing` skill (2026-09-13)

Viraj decided to install the skill. It is Anthropic's `webapp-testing` (`anthropics/skills@34040c9`,
Apache-2.0), copied unmodified into `.claude/skills/webapp-testing/` so the lab gets it by `git pull`,
provenance in its `SOURCE.md`. Its helper starts the page, runs a Playwright script, and stops the page.

`tools/check_page.py` turns Step 4c's hand checks into 17 assertions in headless Chromium at 1280 px and
400 px, feeding the page's own `renderAnswer` the inputs that can fail (a long code line, declined, error),
with no model. **17 of 17 pass. With the Step 4c bug put back (`minmax(0, 1fr)` → `1fr`) it fails 2, the
page measuring 853 px on a 400 px screen**, which is the property the hand check lacked. ENV: it needs a
browser (`playwright install chromium --only-shell`, 199 MB), so it is not a `# runnable` block.

---

## The six PARTIAL answers, checked (2026-09-13) — and the judge never saw page headings

**What was found in the sheet.** `deliverables/ESCALATE-PARTIAL-REVIEW.md`'s six *Human verdict* lines are
filled (5 PARTIAL, 1 SUPPORTED). **They were written into the working tree between about 14:00 and 14:53
by someone other than this session, and Claude's commit `1b9bbb3` swept them in with `git add -A` under a
message that does not mention them.** Whether they are Viraj's is his to confirm (`D06`): a verdict is
human only if a human wrote it.

**Each verdict, checked against the five pages and against 2.0.51.** Claude did not change any verdict.

| id | verdict | its reason, checked against the pages | Step 3e, run on 2.0.51 |
|---|---|---|---|
| `g013` | PARTIAL | holds: [3] says *"the string forms will all be removed"* for options like `joinedload`; naming `subqueryload` is inference | PASS |
| `g021` | SUPPORTED | holds: [2] (`2.0.51`, `orm/backref.rst`) shows a working `backref=`; [5] says it *"will always remain available"* | PASS |
| `g044` | PARTIAL | **does not hold.** The reason says the section title *"bound metadata removed"* is not in the given excerpts. **Source [2]'s heading line is exactly that section**, and `ask.build_prompt` gives the model every heading. By the sheet's own rule this is **SUPPORTED** | PASS |
| `g049` | PARTIAL | holds: [1]/[2] show the positional form and the list's deprecation warning; neither says "removed in 2.0" | PASS (it is rejected on 2.0) |
| `g099` | PARTIAL | holds for faithfulness: [5] says `default` *"refers to a constant value"*, is *"mutually exclusive"* with `insert_default`, callables go to `default_factory`. **But run on 2.0.51 both "rules" are not enforced**: a callable `default=` and `default=` + `insert_default=` are accepted | **FAIL** (and again in 4f) |
| `g106` | PARTIAL | holds: [2]/[4] support `with_polymorphic` + `of_type`; "joinedload alone only loads base-class columns" is not stated | PASS (true on 2.0) |

**Why `g044` was misread: the sheet hid the headings.** Each page appeared as `[2] c01568` with only its
text. Fixed in `escalate.write_sheet` (test first): each page now shows its heading, and the function
**refuses to regenerate a sheet that holds human verdicts**. The existing sheet had its 30 page lines
given headings by a one-off substitution; `git diff` showed no other line changed.

**The larger finding: the judge has never been given page headings either.** `faithful.judge_answer` and
every caller pass chunk **text only** (`rag/faithful.py` contains no `heading`), while the model reads
heading + text. So every faithfulness figure (`D82`, `D83`, `D86`, `D99`, `D101`, `D104`, `D105`) was judged
against **less than the model saw**. The bias has one direction, harsher: a claim that rests on a heading
reads as unsupported. **Its size is not measured.** Paired comparisons (4e) are less exposed, since both
arms lost the same headings, but the absolute rates (77%, 79%) may be understated. **Not fixed here:**
adding headings changes the judge's input, so it is a re-measurement with its own rules and calls.

**Viraj's decisions, 2026-09-13:** the six verdicts are his; **`g044` changed to SUPPORTED** (the sheet keeps
the previous verdict and reason beneath it); and re-judge with headings, below.

---

## Step 4g — the judge given what the model was given (pre-registered 2026-09-13, before any call)

**The question.** The judge has read page **text** only; the model reads each page as `ask.build_prompt`
prints it: a source line, the heading line, then the text. Does giving the judge the heading line change
its verdicts, and does it change any conclusion?

**Held fixed.** Judge `openai/gpt-oss-20b`, the same judge prompt, the same saved answers, the same five
pages per question. **One change:** each passage is exactly the block `ask.build_prompt` shows the model
(source line + heading + text), without its `[n]`, which the judge prompt adds. A test pins that equality.
New fields `verdict_nvidia_h` / `reason_nvidia_h`; the text-only verdicts stay in the rows untouched.

**Calls: 136.** 69 nemotron answers + 47 lab qwen answers with headings, plus a **noise control**: the
first 20 nemotron answers by id, judged again **text-only**. `gpt-oss-20b`'s repeatability was never
measured, so without the control a verdict that moves could be the judge, not the heading.

| question | rule, written first |
|---|---|
| noise | flips of SUPPORTED yes/no between the two text-only readings of the same 20 answers. **> 2 of 20 → "judge too noisy to attribute"**, and Q1 gives no verdict |
| **Q1** do headings change verdicts? (each model, paired by id, text-only → headings) | **"headings matter"** if, in either model, the not-SUPPORTED → SUPPORTED flips are ≥ 3, outnumber the reverse, and exact McNemar p < 0.05, with noise ≤ 2 of 20. **Consequence if they matter:** the with-headings rate becomes the primary Phase 6 faithfulness figure, text-only quoted beside it. **If not:** the text-only figures stand, and this run is the evidence that they were not materially understated |
| **Q2** 4e again, with headings | the 42 paired questions, the same LEVEL / MORE / LESS rule as Step 4e |
| **Q3** nemotron's 80% bar, with headings | reported. `D104`'s FAIL is **restated** only if Q1 says headings matter **and** the with-headings rate is ≥ 80%; otherwise it stands |
| named check | nemotron's `g044` (text-only PARTIAL) — its heading carries the claim; reported, not a gate |

**Prediction (Claude).** Headings help a little and not significantly: nemotron 4 up / 1 down, qwen 2 up /
1 down, both p > 0.05 → **"headings do not matter"**; noise 1 of 20; nemotron with headings ~80%; Q2 still
LEVEL; `g044` flips to SUPPORTED.

### Result — Step 4g, 2026-09-13 15:26–15:38 (Mac; 136 NVIDIA free-credit calls)

20 noise-control + 69 + 47 verdicts, none `UNPARSED`, none skipped (the second pass asked nothing).

```
# runnable: uv run python -m rag.escalate --all
ALL 100 — nvidia/nemotron-3-ultra-550b-a55b, shipped prompt, k=5  (asked 100, EMPTY 0)

REFUSALS  —  generation, at k=5 (D62; not averaged into recall)
  unanswerable items                9
    refused — correct               9/9  (100%)
    answered — FABRICATED           0/9  (0%)
  answerable items                  91
    refused — over-refusal          22/91  (24%)
      with the answer IN the prompt   5   generation defect (the Q18/Q19 class)   g053, g064, g084, g103, g116
      with the answer absent         17   honest — retrieval never supplied it

  answer reached the prompt          58/91   <- retrieval's ceiling, at k=5
  ...and was answered, not refused   53/91   = 0.58   END TO END
  generation loses                    5/91   = 0.05 of the ceiling, invisible to every recall figure

  vs lab qwen2.5-coder:7b, Round 16 (the rule)
    delivered 53 vs 38 over 91 paired   fixed 16  broken 1  exact McNemar p = 0.0003  -> AHEAD
    fixed   g006 g008 g013 g021 g029 g044 g048 g049 g050 g051 g087 g090 g095 g099 g100 g106
    broken  g053
  vs Mac qwen2.5-coder:7b, 2026-08-23 (context)
    delivered 53 vs 39 over 91 paired   fixed 15  broken 1  exact McNemar p = 0.0005
    fixed   g006 g008 g013 g021 g044 g048 g049 g050 g051 g087 g090 g095 g099 g100 g106
    broken  g053

  fabrications  0   rule <= 2  -> no worse   -

  FAITHFULNESS (openai/gpt-oss-20b, against the five pages given; SUPPORTED is not 'correct')
    judged 69 of 69 answered   SUPPORTED 53 = 77%   rule >= 80% -> FAIL
    not SUPPORTED  g013=PARTIAL g025=PARTIAL g028=PARTIAL g044=PARTIAL g048=PARTIAL g051=PARTIAL g055=PARTIAL g058=PARTIAL g060=PARTIAL g062=PARTIAL g078=PARTIAL g080=PARTIAL g085=PARTIAL g106=PARTIAL g109=PARTIAL g121=PARTIAL

  SAME JUDGE, BOTH MODELS (openai/gpt-oss-20b, each answer against its five pages)
    qwen2.5-coder:7b (lab)   judged 47 of 47 answered   SUPPORTED 37 = 79%   PARTIAL 7   UNSUPPORTED 3
    nemotron                 judged 69 of 69 answered   SUPPORTED 53 = 77%   PARTIAL 16   UNSUPPORTED 0
    paired over 42 answered by both   nemotron-only SUPPORTED 3  qwen-only SUPPORTED 6  exact McNemar p = 0.5078   -> LEVEL
      nemotron-only  g015 g030 g115
      qwen-only      g055 g060 g062 g080 g109 g121

  STEP 4g — THE JUDGE GIVEN THE HEADINGS THE MODEL SAW
    noise control  20 nemotron answers judged text-only twice: flips 2  (up -; down g004 g020)   rule <= 2
    nemotron                 with headings judged 69 of 69   SUPPORTED 63 = 91%   text-only -> headings: up 11  down 1  p = 0.0063
      up    g028 g048 g051 g055 g058 g062 g078 g080 g085 g109 g121
      down  g099
    qwen2.5-coder:7b (lab)   with headings judged 47 of 47   SUPPORTED 38 = 81%   text-only -> headings: up 3  down 2  p = 1.0000
      up    g025 g030 g053
      down  g024 g080
    Q1  -> headings MATTER
    Q2  paired over 42: nemotron-only SUPPORTED 5  qwen-only 2  p = 0.4531   -> LEVEL
    g044 (nemotron)  text-only PARTIAL  ->  with headings PARTIAL

  REPEAT  20 asked twice   same decision 19   rule >= 19 -> stable   identical text 0   flipped g007

  tokens, as returned by the API: prompt 259231, output 80270  (over 120 generation calls)
  shadow cost of the 100: $0.3447, $3.45 per 1000 queries  (price snapshot; calls were free credits)
```

| question | result | rule | prediction |
|---|---|---|---|
| noise | **2 of 20** flips, both down (`g004`, `g020`) | ≤ 2 → attributable, **at the limit** | 1 (one short) |
| **Q1** nemotron | **63/69 = 91%**; not→SUPPORTED **11**, SUPPORTED→not **1** (`g099`), p = **0.0063** | **headings MATTER** | 4 up / 1 down, not significant (**wrong**) |
| **Q1** qwen | **38/47 = 81%**; 3 up / 2 down, p = 1.0 | no effect | 2 up / 1 down (right) |
| **Q2** paired, 42 | nemotron-only SUPPORTED **5**, qwen-only **2**, p = 0.45 | **LEVEL** | LEVEL (right) |
| **Q3** nemotron's 80% bar | **91%** | Q1 says matter **and** ≥ 80% → **`D104`'s FAIL is restated** | ~80% (low) |
| `g044` (nemotron) | PARTIAL → **PARTIAL** | named check, not a gate | flips (**wrong**) |

**The consequences written before the run, applied:**
- **The with-headings rate is now Phase 6's primary faithfulness figure**, text-only quoted beside it:
  nemotron **91%** (77% text-only), qwen **81%** (79%).
- **`D104`'s faithfulness FAIL is restated:** it failed on text-only input (77%) and **passes on the input the
  model actually saw (91%)**. The demo notice and the Space card now quote 91%.
- **`D105`'s LEVEL stands** (5 vs 2, p = 0.45). The direction changed sides, which is itself a reason not to
  read a direction into either.

**What the numbers do NOT say.**
- **The noise control sat at its limit.** A judge that changes 2 answers in 20 on a re-read could account for
  a handful of nemotron's 12 changes. What noise does not explain is the **11 to 1 asymmetry**: the control's
  own two changes went the other way.
- **"Headings" is shorthand for the whole source block.** The change also added each page's version and
  path line, and one upward reason uses it: `g051`, *"passage [5] confirms the same for SQLAlchemy 2.0"*.
  Most upward reasons do not say which line decided them (`g080`: *"Passages [1], [2], [3], and [5] provide
  the information"*), so the effect is measured in aggregate, not attributed item by item.
- **Why nemotron gains and qwen does not is not measured.** Nemotron's answers are longer and name sections
  and versions; qwen's are short. That is a hypothesis.
- **`g044` stayed PARTIAL for a different reason than the human sheet's.** With the heading the judge accepts
  the Engine/Connection claim and now wants the removal of `autoload=True` itself stated, which the heading
  ("bound metadata" removed) does not do. Viraj's SUPPORTED is his verdict and stands; the judge reads a
  different sub-claim more strictly.
- **Phase 4's faithfulness figures (`D82`: D 77–85%, H 92%, judge `gemma4:e4b`) were also judged text-only and
  are NOT re-measured here.** They may be understated the same way; that re-run is Ollama-local and ~110
  generations.

---

## Step 4h — Phase 4's judge given the pages as the model saw them, on the lab (pre-registered 2026-09-14, before any run)

**The question.** `D82`/`D83`'s faithfulness rates (lab: D 77%, H 92%, judge `gemma4:e4b`) came from a judge
given page text only, like every judge before Step 4g. Does giving it the source and heading lines change
them? **Run on the lab, not the Mac** (Viraj's question, answered from data): the lab's judge re-read the same
110 answers five days apart and came back **byte-identical, reasons included** (`D84`), so a verdict that
moves there is the headings, with no noise control needed. The Mac's judge drifts 3 in 110.

**Held fixed:** the same saved answers (`prompt-sweep-phase4.json`, arms D and H), the same judge
(`gemma4:e4b`, local), the same five re-retrieved pages. **One change:** each passage is
`faithful.passage_as_shown`, byte-equal to `ask.build_prompt`'s block (test). Rows go to
`faithfulness-phase4-headings.Linux-x86_64.json`; the committed text-only lab rows are never touched.

| question | rule, written first |
|---|---|
| does either arm move? | **headings MATTER** if, in D or H, ≥ 3 answers become SUPPORTED, more than move the other way, exact McNemar p < 0.05 (`faithful.headings_verdict`, the 4g rule) |
| consequence if they matter | the with-headings lab rates become Phase 4's primary faithfulness figures; `D82`/`D83` are restated, not deleted |
| D vs H, with headings | paired over items both arms answered and the judge read; reported, and `D82`'s "not significant" is re-checked on it |
| not in scope | the ship decision on prompt `H` (it rests on refusals, `D83`/`D84`, not on faithfulness) |

**Prediction (Claude).** **"Headings do NOT matter"** for both arms, because qwen's answers are short and
Step 4g moved qwen by 3 up / 2 down. D ~79%, H ~92%; D vs H still not significant.

### Result — Step 4h, 2026-09-14 (lab PC, RTX 3060, `gemma4:e4b`; no API calls)

The lab's run, re-derived on the Mac from the committed rows with the same command:

```
PHASE 4 JUDGE, TEXT ONLY vs PAGES AS THE MODEL SAW THEM — gemma4:e4b on Linux-x86_64
  text-only rows  faithfulness-phase4.Linux-x86_64.json  (Linux-x86_64)
  headings rows   faithfulness-phase4-headings.Linux-x86_64.json
  D  SUPPORTED text-only 36/47  with headings 38/47   up 3  down 1  p = 0.6250
     up    g014 g019 g120
     down  g098
  H  SUPPORTED text-only 56/61  with headings 57/61   up 2  down 1  p = 1.0000
     up    g031 g062
     down  g036
  D vs H with headings, paired over 45: H-only SUPPORTED 6  D-only 0  p = 0.0312
  rule -> headings do NOT matter
```

**Against the rule: headings do NOT matter** for Phase 4's judge on qwen's answers. D 77% → 81%, H 92% → 93%.
**Consequence as written:** `D82`/`D83`'s text-only figures stand, and this run is the evidence they were not
materially understated. **Prediction right** (D ~79%, H ~92%, no effect). The lab's run died once at 41/64 and
was resumed; the text-only rows were not touched.

**Why nemotron moved and qwen did not (4g vs 4h), stated as a hypothesis, not a finding:** nemotron's answers
are long and name sections and versions; qwen's are short. Two judges and two machines differ between the two
runs, so the contrast is not a controlled comparison.

**Reported, not pre-registered as a decision: prompt H is now significantly more faithful than D.** Paired over
the 45 items both arms answered, with headings: **H-only SUPPORTED 6, D-only 0, p = 0.031**. The same lab's
text-only rows on the same comparison read 8 vs 2, p = 0.11, and `D82` (Mac) read 5↑ 1↓, p = 0.22. It clears
`D61`'s bar (about six clean fixes, no regressions). One machine, one run. **It does not reopen the hold on H**,
which rests on refusals (`D83`, `D84`), not faithfulness.

## Step 5 — Langfuse on the live demo (2026-09-14, `D108`)

Viraj created a Langfuse Cloud project (free Hobby plan: 50k units a month, 30 days of data, no card; US
region) and put its keys in `.env`. **Self-hosting was rejected:** a ~5-container stack on a Mac that had just
killed the local demo for memory.

**What was built.** `demo.answer` opens one trace per question with two observations inside: `retrieve` (the
five page ids) and `generate` (the model's answer and its token counts). **It is off unless the keys are
present** (`demo.langfuse_client`), so tests, the lab and local runs are unchanged. On Modal the keys come from
the secret `langfuse`; the page's footer says questions are logged when tracing is on. 3 tests with a fake tracer.

**Checked live, not assumed:** `/api/config` reports `traced: True`; one question answered in 46.0 s with 5
sources; Langfuse's API then returned a `demo.answer` trace with 3 observations and latency 45.9 s.

**What it is not:** an evaluation. The golden set, the judge and the CI gate grade quality; Langfuse records
what visitors actually do.


---

## Phase 6 closed — the gate, item by item (2026-09-16)

The ROADMAP's bar for this phase is two sentences: *"a stranger can click your demo link and get a
cited answer, and a quality-degrading PR gets auto-blocked."* Both are met, and each half has a
command or a PR number behind it rather than a claim.

| the gate | evidence | id |
|---|---|---|
| a stranger clicks the link and gets a **cited** answer | https://virajvaghasia--sqlalchemy-upgrade-agent.modal.run — live on Modal; a cold ask answered `Session.get` in 116 s with 5 source cards; the README quotes a real answer with its `[1]` | `D106` |
| a quality-degrading PR is **auto-blocked** | PR #30 removed the reranker on a real GitHub runner and the `quality gate` job failed, naming `g017`; PR #29 (no retrieval change) passed with `moved 0`. The check is required on `main` | `D97` |

**The phase's other three bullets, with what each actually produced:**

| bullet | what shipped | what it cost or could not do |
|---|---|---|
| **Routing** | a **cascade**: escalate only when the local model refuses. Catches 20 of the 20 fixable items, priced at **$1.81 per 1000 queries** from a committed snapshot of list prices | **predictive** routing was measured and **failed its pre-written bar** — it caught 3 of the 20 fixable, fewer than random, because a low score marks a *missing page*, not a hard question (`D98`). And a judge's `SUPPORTED` is not `correct`: `g016` was supported by its page and wrong on 2.0.51 (`D100`) |
| **Observability** | Langfuse Cloud traces every demo question: one trace, with `retrieve` and `generate` inside. Off unless the keys are present | it records what visitors do. It does **not** grade anything (`D108`) |
| **Deploy + package** | the Modal app, a hand-built page checked in Chrome, and a README that opens with the product, a diagram and the measured table | Hugging Face refused the Space (402, PRO required); the page's own numbers are the hosted model's, and say so (`D104`, `D107`) |

**What Phase 6 rejected, which is the half worth saying out loud:** source framing (`D96` — the
agent's conversation shape does not fix over-refusal; it makes the model *more willing*, including
on pages that do not answer), and predictive routing (`D98`).

**Where the numbers stand at close:** 534 tests, 95 of 95 `# runnable` blocks reproducing, 108
decisions with §H empty, a 100-question hand-verified golden set. Retrieval `recall@5 = 0.64`
(58 of 91); end to end **0.43** on the Mac, **0.42** on the lab; the hosted model reaches **0.58**
under the same pages and prompt (`D104`).

### What is still open, and none of it is Phase 6's gate

- **The refusal clause is the remaining defect, and it is a trade, not a bug.** Rounds 23 and 24
  (2026-09-15/16) put it on the table plainly: with the answer page in the prompt, the shipped
  wording refuses, and on `g050` and `g044` **so does every wording that has a refusal sentence at
  all**. Only the variant with the sentence deleted answers — and that variant also answers the
  questions the corpus cannot answer, 13 of 13 (`D43`). Both effects are measured; nothing resolves
  them. `11-GENERATION.md` §R3.6.
- **Prompt H stays held** (`D83`, `D84`): the citation effect reproduced on both machines, the
  end-to-end gain did not.
- **The Day 3 Tailscale tunnel** — blocked on Shaili sharing the node since August, and nothing
  needs it; AnyDesk has carried every lab round.
- **Not started: Phase 7 (security / prompt injection)**, which the ROADMAP marks optional.


---

## ⚠️ The live demo stopped answering (found 2026-09-16, while setting up Phase 7 Step 2)

**Symptom, from the public page itself:**

```
POST /api/ask  {"question": "query(User).get(1) warns LegacyAPIWarning, where did get move to"}

{"status": "error",
 "status_label": "Not answered",
 "error": "The answer model did not respond (HTTPError). The search still ran, and its sources are listed.",
 "sources": [ ... five real pages, correctly retrieved ... ]}
```

**Cause, measured directly against NVIDIA rather than guessed:**

```
POST https://integrate.api.nvidia.com/v1/chat/completions   model = nvidia/nemotron-3-ultra-550b-a55b
-> HTTP 404  {"detail": "Function id '948fe171-...' version 'null': Specified function in account '...' not found"}

GET  /v1/models  -> 82 models, and nvidia/nemotron-3-ultra-550b-a55b IS still listed
```

**So the catalog advertises a model the account cannot call.** That is `D80`'s sentence arriving on
a different provider: *a pinned id is a promise about a name, not a service* — there, a pinned
Gemini id answered 503 all morning while three siblings answered; here, a listed NVIDIA model 404s
on the key that used it for 190 calls on 2026-09-13 (`D104`). Most likely the free credits are spent
or the entitlement changed; the API does not say which, and neither does this note.

**What still works, and it is the part that was designed for this:** search ran, the five sources
rendered, the page stayed up, and the error names the model rather than showing a stack trace. That
is Step 4c's error-state rule passing on a real outage instead of the stand-in it was tested with
(the stand-in was `ask.OLLAMA_URL` pointed at a closed port, disclosed at the time).

**What it costs:** the ROADMAP's Phase 6 gate — *"a stranger can click your demo link and get a
cited answer"* — **is not satisfiable today**. The gate was met on 2026-09-13 and the evidence for
that stands; what changed is a third party's entitlement, not this repo.

**The options, none of them started, because which one is right is Viraj's call:**

| option | cost | what it costs in honesty |
|---|---|---|
| repoint the demo at a model the key can call (`openai/gpt-oss-20b` answers today; it is also Phase 6's judge) | one constant, one redeploy | the page's measured numbers (`D104`: 0.58 end to end, 91% supported) describe nemotron, not the new model. The notice would have to say so, or be re-measured |
| run the demo on Ollama | free, but needs a machine that is up | the lab is the only box with the GPU, and it is not Viraj's to host on |
| leave it down and say so | nothing | the README's "Try it" link leads to an error page until someone changes it |

**Do not quote the demo as live without checking it first.** One command:
`curl -s --max-time 60 <url>/api/config` is a health check that costs nothing; the `/api/ask` above
costs one question against the page's own hourly limiter.
