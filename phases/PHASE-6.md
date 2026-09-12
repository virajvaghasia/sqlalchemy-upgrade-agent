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
| **2** | **CI quality gate** — a PR that loses a golden answer fails a check | **built, demo reproduces locally** (`D97`); first run on a real runner not yet taken |
| **3** | routing with shadow cost — cheap questions local, hard ones to a strong model, priced | **3a closed** (`D98`): cascade on refusal; **3b measured** (`D99`): 16/20 answered, 10 supported, upper bound 0.42 → 0.53; price not sourced |
| 4 | deploy + package — a demo link and a README that opens with the product | not started |
| 5 | Langfuse — traces, tokens, latency, cost per query | last, on demand (standing decision) |

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
  not SUPPORTED  g013=PARTIAL g021=PARTIAL g044=PARTIAL g049=PARTIAL g099=PARTIAL g106=PARTIAL

  tokens, as returned by the API: prompt 45015, output 15624  (over 20 calls)
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

**Not done:** the `gemma4:e4b` agreement pass (`rag.escalate --judge`, ~15 min on the Mac), and a
human read of the six `PARTIAL`s.