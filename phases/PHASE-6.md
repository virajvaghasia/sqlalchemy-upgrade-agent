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
| **3** | routing with shadow cost — cheap questions local, hard ones to a strong model, priced | **3a closed** (`D98`): cascade on refusal; **3b** (`D99`): 16/20 answered, 10 page-supported; **3c** (`D100`): full cascade **$1.81 / 1000 queries**, 0 new fabrications; **3d** (`D101`): 10/16 hold against verified pages → **0.42 → 0.53** upper bound |
| **4** | deploy + package — a demo link and a README that opens with the product | **built** (`D102`): in-memory search gated (broken 0, moved 0), Space bundle builds; **push is Viraj's** |
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
| `space/requirements.txt` | pinned to the versions **installed** where the baseline was gated |
| `space/README.md` | the Space card: what it does, what is measured, and that 0.42 is not this model |
| `space/build.py` | assembles `space/dist/` (gitignored): app, `rag/`, the corpus files, LFS attributes |

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

---

## Night of 2026-09-12 — two checks, pre-registered at 23:55 before either ran

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