# §R10 — Phase 6: production — a gate, a priced router, and a demo

Plan and measurements: [`../phases/PHASE-6.md`](../phases/PHASE-6.md). Decisions: `D96` (framing,
rejected) through `D102` (the demo). **This file is the sitting; the plan is the record.** Every
block marked `# runnable` reproduces with no model and no Qdrant, and CI checks that it still does.

Three parts, in the order they were built:

1. **A quality gate** (R10.1–R10.8): a pull request that loses a golden answer cannot merge quietly.
2. **A router, priced and checked** (R10.9–R10.13): which questions go to a bigger model, what that
   costs, and whether the bigger model's answers are actually right.
3. **Shipping it** (R10.14–R10.17): the demo page, why it is not on a public link yet, and keys.

---

## R10.0 — Where to start

**Plain job.** Up to Phase 5 this repo measured a system. Phase 6 asks the questions a team running
it would ask: *can a bad change sneak in? would a bigger model help, and at what price? can a stranger
use it?*

**The whole phase on one page:**

| step | the question | the answer, measured | decision |
|---|---|---|---|
| 1 | does the *shape* of the prompt move the over-refusals? | a little, but it makes the model more willing to guess, not better at reading | `D96`: rejected |
| 2 | can a change that loses an answer merge quietly? | no: removing the reranker is blocked by name, `g017` | `D97` |
| 3a | which questions should go to a bigger model? | the ones the small model *refused*, not the ones whose search scored low | `D98` |
| 3b | does the bigger model answer them? | 16 of 20, but only 10 fully supported by the pages | `D99` |
| 3c | what does escalating every refusal cost, and does it add fabrications? | **$1.81 per 1000 queries** at list price; **0** new fabrications | `D100` |
| 3d | are those answers *correct*, not just supported? | 10 of 16 agree with the human-verified page: end to end **0.42 → at most 0.53** | `D101` |
| 4 | can a stranger use it? | the page works locally; Hugging Face now charges for it | `D102` |

**Who does what in this phase.** Several models appear, and mixing them up is the fastest way to say
something false:

| role | model | where it runs | why this one |
|---|---|---|---|
| writing this repo's code and docs | Claude | this conversation | the project itself never calls Claude |
| **the system's generator** (the 0.42) | `qwen2.5-coder:7b` | Ollama, local | free, fits the lab's GPU; every end-to-end number is this model |
| search | `BAAI/bge-m3` + BM25 + `BAAI/bge-reranker-base` | local | Phases 1–3 |
| the **bigger model** escalations go to | `nvidia/nemotron-3-ultra-550b-a55b` | NVIDIA API, free credits | the largest model the key could actually call (most returned 404) |
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

**Gating** means a check whose red cross **blocks the merge**. Technically, blocking is a
repository setting ("required status check") on top of a check that exits non-zero. The check is
in this repo; the setting is Viraj's to switch on.

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

The ROADMAP's picture of this phase is *"open a PR that removes your reranker, and film CI
rejecting it."* The rows for that PR were measured on the Mac (`rag.score --no-rerank`) and
committed, so the gate's verdict reproduces on any machine with no Qdrant:

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

**Read every number:**

- **`58/91` → `57/91`.** 91 is the answerable items (100 minus the 9 unanswerable). One item left
  the top 5. **`0.64` → `0.63` is inside the ±0.097 band**, so a gate that compared averages would
  call this noise and pass it.
- **`broken 1 g017`.** The item. This is `D68`'s only fix, so the gate blocks exactly the question
  the reranker was shipped to answer.
- **`moved 3`.** `g013`, `g037`, `g041` had their top 5 reshuffled, still found or still not found.
  Not a failure. It is the line to read first when a result surprises you.
- **`p = 1.000`.** One broken, zero fixed: no evidence of a *systematic* change. The gate ignores
  p on purpose. A statistically invisible loss of one answer is still a lost answer for whoever asks
  `g017`.
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

**Side by side, two hypothetical PRs** (made-up numbers, to show the shape, not a measurement):

```
PR A    fixed 5   broken 0    recall 0.64 -> 0.70    PASS
PR B    fixed 6   broken 1    recall 0.64 -> 0.70    BLOCKED
```

Same average. PR B took an answer away from someone. The gate does not say PR B is wrong. It says
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
| **embed 3284 chunks with bge-m3** | yes, **CPU only** | **the long pole** — 1106 s on the Mac's 10-core CPU (`D97`); a runner's time is unmeasured |
| Qdrant | yes, a **service container**, same `v1.19.0` pin as Compose (`D41`) | seconds |
| BM25, query embedding, reranker for 100 questions | yes, CPU | minutes |
| **generation (Ollama)** | **no** | not graded here |

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

**What it is not:** a measurement of the runner. The runner is a Linux x86 CPU with a different
math library from Apple's. If the first real run shows `moved` items on a PR that changed no
retrieval code, that is this question coming back, and `D97` names the fallback design.

---

---

**PART 2 — THE ROUTER, PRICED AND CHECKED**

## R10.9 — Routing: which questions are worth sending to a bigger model? (`D98`)

**Plain job.** A router keeps most questions on the free local model and sends some to a stronger,
paid one. The ROADMAP wants the sentence *"routing saves $X at a Y-point quality cost."* Before any
dollar figure there is a simpler question: **does the router send the right questions?**

**Start from the two ways a question fails here**, in the lab's run of the shipped prompt:

```
page ABSENT   33 answerable questions: retrieval never put the answer page in the prompt.
              Send one to a stronger model and it gets the same five wrong pages.
              It can only answer from memory -- the move that produced g065's invented
              op.create_view on 2026-08-21.

page PRESENT  g050, "engine.execute select gone AttributeError use connection instead":
              the answer page WAS in the prompt, and the local model replied
              "The sources do not answer this."  One of D72's over-refusals.
              A stronger model reading the same page plausibly answers it.
```

**Routing can only fix the second kind.** That sentence decides everything below.

**Two designs, rules written before the numbers** (`PHASE-6.md` Step 3a):

- **A, predictive:** before generating, score the five pages with the cross-encoder, and send the 30
  questions whose best page scores lowest.
- **B, cascade:** let the local model answer first; send only the questions it refused.

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
- **A catches 20 of 53; the bar was 27.** Random picking of 30 questions catches 16 on average, and
  catches 20 or more 5.7% of the time. So the score is a weak real signal, and it fails the bar.
- **A's `caught, page present 3 of 20`.** This is the damning line. Random picking would catch about
  6 of those 20. **A low retrieval score is exactly what a missing page looks like**, so the
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

**Plain job.** The cascade sends a bigger model the 20 questions our small model refused *with the
right page in hand*. Same question, same five pages, same prompt, word for word. Only the model
changes. Does it answer?

**What was held fixed, side by side:**

```
                 the small model (the 0.42)           the bigger model (escalation)
question         g050 "engine.execute select gone…"   the same
pages            the same five, retrieved once        the same five
prompt           ask.SYSTEM + ask.build_prompt        byte for byte the same (a test asserts it)
model            qwen2.5-coder:7b                     nvidia/nemotron-3-ultra-550b-a55b
```

**The first attempt, and why it was abandoned.** It used Google's `gemini-3.7-flash` on its free
tier. It answered 7 questions, then returned HTTP 429 (daily quota; the free tier is 20 calls a day
per model, `D80`). Its 7 answers were all judged supported, but the judge was `gemma4:e4b`, **also a
Google model**. You asked which models were in use, and that question exposed it: a Google model
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
figure, because a real deployment would pay. A **shadow cost** is what those exact calls *would* have
cost at a published price: counted tokens × price per token. Nothing was spent to get it.

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

**Plain job.** The judge is asked *"do these five pages say this?"* It is easy to read its `SUPPORTED`
as "right". Two page-absent answers, run against the real library, show why not.

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

| word | question it answers | who can answer it |
|---|---|---|
| **supported** | do the pages say this? | a judge model reading the pages |
| **correct** | is this true of SQLAlchemy 2.0.51? | running the code, or a person who knows the library |

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
- **The pre-registered quote: 38 + 10 = 48/91 = 0.53** end to end, against the lab's 38/91 = 0.42.
  An upper bound: it assumes each of the 10 is also correct on the real library, which is checked for
  none of them.
- **3c: 6 of 13 page-absent answers agree with the verified page.** That corrected `D98`'s claim that
  page-absent failures cannot be fixed. The 0.59 you get by counting them was **not** written down
  before the run, so it is labelled exploration and not quoted.

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

**Why that needed proof, not assumption.** Qdrant finds nearest neighbours with an **approximate** index
(HNSW), fast but allowed to miss. The in-memory version is **exact**: multiply every stored vector by
the question's vector and sort (`vectors @ query`). Exact and approximate can return different top
fives, and a different top five is a different system from the one that was graded.

**So the gate graded it.** The rule, written first: `broken 0` against the committed baseline.

```
Qdrant (approximate)      the baseline, 58/91 found in the top 5
in memory (exact)         58/91; broken 0, moved 0 (every top 5 identical)
top-20 lists identical    96 of 100 (the four that differ, differ only below rank 5)
```

Run it: `RAG_DENSE=memory uv run python -m rag.score --save /tmp/rows-memory.json`, then `rag.gate`
against `deliverables/gate-baseline.json` (block in `PHASE-6.md`; it needs the embedding model, so CI
classifies it ENV). **The switch is one environment variable**; the Qdrant path is unchanged.

**What is NOT claimed.** That exact and approximate search are the same in general. They agree on this
corpus's 100 golden questions at rank 5, and that is what the demo needed.

---

## R10.15 — The demo's page, and the sentence it must always show

`rag/demo.py` is the logic, and `space/app.py` is a thin Gradio page around it:

```
question -> index.retrieve (the graded search) -> ask.SYSTEM + ask.build_prompt (the shipped prompt)
         -> a generator -> the answer, then every page it was given, each expandable
```

**The generator depends on where it runs, and the page says which, on every answer:**

| where | generator | the notice under every answer |
|---|---|---|
| your Mac (`DEMO_GENERATOR=ollama`) | `qwen2.5-coder:7b`, the measured model | this is the model the 0.42 (lab) / 0.43 (Mac) was measured on |
| a hosted page (`nvidia`) | `nemotron-3-ultra-550b` | the 0.42 is for a different model and does not describe these answers |

**Why the notice is a test, not a nicety.** NVIDIA's API serves no qwen model at all (catalog checked
2026-09-12), so a hosted page *cannot* run the measured model. Printing "0.42" next to a model that did
not produce it is the exact mistake `D95` exists to stop. `test_the_page_always_says_the_measured_score_is_not_this_model`
fails if the sentence disappears.

**A real question through the local page.** `g050`'s wording, *"engine.execute select gone AttributeError
use connection instead"*: 28.7 seconds, and the answer was **"The sources do not answer this."**
That is one of `D72`'s over-refusals, the small model declining a page it has. **The local demo shows the
measured defect, exactly as measured**, which is what a demo of a measured system should do.

**The page, as it looks** (checked in a browser 2026-09-12): the question and four real golden-set
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
DEMO_GENERATOR=ollama RAG_DENSE=memory PYTHONPATH=. uv run --with gradio==6.27.0 python space/app.py
# then open http://127.0.0.1:7860
```

**Two bugs found building it, both real:** the first `requirements.txt` pinned `numpy==2.5.2` (grepped
from `uv.lock`), which needs Python 3.12 while the project runs 3.11; the pins now come from what is
actually installed. And `ask.generate` calls `sys.exit` when Ollama is down, which is right for a
command line and would kill a web server, because `SystemExit` is not an `Exception`. The page now
catches it and says Ollama is not running.

---

## R10.16 — Why there is no public link yet

**Hugging Face refused.** Creating the Space returned **HTTP 402 Payment Required**: *"Static Spaces are
free for everyone, but hosting Gradio and Docker Spaces on free cpu-basic requires a PRO
subscription."* Nothing was created.

**What the app needs from a host:** about **4 GB of memory**, for the embedding model and the reranker.
That single number decides every option:

| host | free allowance (checked 2026-09-12; confirm on the provider's page) | fits? |
|---|---|---|
| Hugging Face Gradio Space | paid plan required (the 402 above) | no |
| Render, Koyeb | 512 MB | no: an eighth of what is needed |
| Modal | $30 of credits a month, no card | yes; slow first question after idle |
| Oracle Cloud Always Free | 2 CPU / 12 GB since June 2026; card at signup | yes; always on |
| Google Cloud Run | a monthly free usage allowance; billing account | yes, for light use |

**Why the 512 MB hosts cannot be made to fit.** The obvious shrink is to embed questions through an API
instead of loading the model. NVIDIA hosts no `bge-m3`, and a different embedding model is a different
index: the questions would land in a different space from the stored vectors, and the gate would have
to pass again from scratch.

**What did NOT happen.** The lab PC was not used as a host: it is a shared machine and not yours to
expose. No paid plan was bought, because zero paid calls is a standing rule and breaking it is your
call. **Next:** a free host needs you to create the account; the bundle (`space/build.py`) is ready.

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
were chosen, not measured**, and the code says so.

---

## R10.18 — Say this out loud

**The gate.** “Every PR that touches retrieval rebuilds the index on a CI runner, scores the 100 golden
questions, and fails if any question whose answer was in the top five no longer is. Removing the
reranker costs one point of recall, inside the noise band, and the gate blocks it by naming the one
question, `g017`. It grades retrieval only, because retrieval reproduced exactly across my machines and
generation didn't.”

**The router.** “I don't predict which questions are hard; I tested that and it mostly picked
questions whose answer page was missing, which no bigger model can fix from the same pages. The router
is a cascade: the free local model answers first, and only a refusal is escalated.”

**The price and the gain.** “Escalating every refusal to a 550B model costs about $1.81 per 1000 queries
at one reseller's list price, adds no fabrications on the unanswerable questions, and lifts end to end
from 0.42 to at most 0.53. At most, because my judge checks faithfulness to pages, and when I ran two
answers against the real library it had called a wrong one supported and a right one unsupported.”

**The demo.** “The demo uses the graded search, proven identical without the database, and the shipped
prompt. Hosted, it would need a different generator, and the page says the measured score is not for
that model.”

**Do not say:**

- “CI blocks any quality regression.” It blocks *retrieval* regressions on the golden set.
- “A stronger model fixed ten answers.” Ten became *supported*; correctness is an upper bound.
- “Routing saves money.” It *costs* $1.81 per 1000 queries against a free local model; what it buys is
  up to 11 points of end to end.
- “The demo scores 0.42.” Only the local version runs the model that was measured.

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
0.42 was measured with `qwen2.5-coder:7b` generating. A hosted demo cannot run that model (NVIDIA
serves no qwen), so it would generate with Nemotron, a model never measured end to end on the golden
set. Showing 0.42 next to it would quote a number for a system that did not produce it. The local demo
runs qwen, so its notice says it is the measured model.

**Q11. Why is there no public link, and what would you do next?**
Hugging Face now requires a paid plan for this kind of page (HTTP 402), and the app needs about 4 GB of
memory, which rules out the 512 MB free hosts. Free hosts that fit exist (Modal, Oracle's always-free
server, Google Cloud Run), each needing an account in Viraj's name. The build script produces the
bundle for any of them; the in-memory search means no database has to be hosted.

**Q12. A pull request changes only a document, and the gate fails. What do you check first?**
First, whether the gate should have run at all: it only triggers on changes to retrieval code, the
corpus manifest, the golden set, the baseline, dependencies or its own workflow. If it ran on a
code-free change and shows `broken` or `moved` items, the code did not cause it. Read the baseline's
provenance line (which machine, which device, which model snapshots) and compare with the run:
the usual suspects are a model snapshot changing (why both models are pinned) or the runner's CPU
ranking a near-tie differently (R10.8).

---

## After this you can say

- what a required status check is, and which half of it lives in the repo
- why the gate compares question by question and ignores the p-value
- why generation is not in CI, with the decision that measured it
- why the embedding cache is saved before the gate runs, not after
- that the reranker was unpinned for three weeks, and how the gate would have turned that into a false failure
- why a cascade on refusal beats a predictor on search scores here, with the 3-of-20 number
- the difference between picking without replacement and independent coins, with a case you can check by hand
- how a shadow cost is computed, and what the $1.81 is and is not
- why "supported" is not "correct", with `g016` and `g007`
- why the demo can use in-memory search, and why its page must name its generator
- why there is no public link yet, and what 4 GB of memory rules out
