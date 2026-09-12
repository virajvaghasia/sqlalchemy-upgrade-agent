# §R9 — The agent, and what a 7B model will not do

Phase 5's sitting. The measured plan is [`../phases/PHASE-5.md`](../phases/PHASE-5.md); this file
is the read. Continues the `R` run after [`16-JUDGE.md`](16-JUDGE.md) (§R8) — one run across all
of it, `R` for RAG, not Retrieval (`D47`). Decisions: **`D87`–`D95`**.

**Read this before the plan.** The plan says what was run. This says what any of it means.

---

## Stop — three kinds of “number” in this file

This file mixes three naming systems. They are not the same thing. Read this once or every
heading will feel like a score.

### 1. Section labels like `R9.4` — chapter headings, not scores

| You see | What it is | What it is **not** |
|---|---|---|
| **`§R9`** | This whole file. `R` = RAG teaching series. `9` = ninth sitting after §R1…§R8. | A grade out of 9 |
| **`R9.0` … `R9.8`** | Subsections *inside* this file (like §R8.1 in `16-JUDGE.md`) | Metrics, versions, or priorities |
| **`R9.7b`, `R9.7c`** | Extra subsections that grew under R9.7 (bug story, then landing) | Separate phases |
| **`D87`, `D95`…** | Decision IDs in [`09-DECISIONS.md`](09-DECISIONS.md) | Section numbers |
| **File `17-…`** | Reading-order filename (`01`…`17`) | Related to §R9’s digit |

So **`R9.4` means “section 4 of the Phase 5 study notes.”** Not “score 9.4,” not “SQLAlchemy 9.4.”

### 2. Scores like `0.02` and `0.42` — measured rates

| Number | Plain meaning | Where it lives |
|---|---|---|
| **`0.42` / `0.43`** | One-shot RAG (Phase 4): right page in the prompt **and** the model answered | Lab / Mac |
| **`0.02`** | Same *definition* of end-to-end for the **agent** on the lab’s first full run — almost always zero because the agent skipped search | R9.5 |
| **`96/100`**, **`4/100`** | How often the agent called a tool (or didn’t) | R9.5 |
| **`0.25` → `0.43`** | Agent after the `[:600]` truncation bug was fixed (Mac) | R9.7b |
| **`0.47`** | Agent with force+nudge levers (Mac screen — lab did **not** match the level) | R9.7c |

When a title says *“the result: `0.02`”*, that **`0.02` is a score**. The **`R9.5`** in front is
only the heading.

### 3. Map of this file

| Section | One sentence | Read when |
|---|---|---|
| **R9.0** | Interview skim list | Starting cold |
| **R9.1** | Before: one lookup always. Now: the model chooses when to look up. | First |
| **R9.2** | A “tool” = Python function + description. Model writes JSON; our code runs it. | First |
| **R9.3** | Three tools; `check_api` is the `g065` / `op.create_view` check offered *before* writing. | First |
| **R9.4** | Why we cannot `import` 2.0 from this 1.4 env — reuses an *old spawn trick*, not the breakages runner. | Before tools code |
| **R9.5** | Lab score `0.02` — and why “20× worse than 0.42” is the wrong story. | Core result |
| **R9.6** | Same prompt, Mac vs lab: call-a-tool-or-not flipped on half the items. | Reproducibility |
| **R9.7** | Almost never chains two tools — until a NOT FOUND nudge; then 7/10 on two-part questions. | Agency limit |
| **R9.7b** | Our own `[:600]` truncation made the agent look worse than it was. | The bug story |
| **R9.7c** | Where Phase 5 landed; lab withdrew the Mac headline; drill. | Closing |
| **R9.8** | What to say out loud in an interview. | Before interviews |

**If you have ten minutes:** R9.2 → R9.5 → R9.7b → R9.8.

---

## R9.0 — Where to start

**Plain job.** Point you at the three sections that carry the interview, so you do not drown in
R9.7c’s tables on day one.

**Say this:** “Phase 5 measured a tool-using loop on the same 7B model. The headline is not a
score — it is what the model would and would not do with tools.”

**Do not say:** “We built an agent and it got 2%.” (That sentence is how R9.5 starts, and R9.5
exists to kill it.)

---

## R9.1 — What changed (and what did not)

**Plain job.** Name the upgrade in one breath, then name three things people will wrongly assume
moved.

**Picture — before (Phases 1–4):**

```
  Question  →  retrieve top-5 once (code always does this)  →  one LLM answer
```

**Picture — now (Phase 5 agent):**

```
  Question  →  LLM may write {"name":"search_docs",...}
            →  our code runs the tool, pastes the result back
            →  LLM may call another tool, or write the final answer
            →  …until it stops or hits a step budget
```

**What did NOT change:**

| Claim people make | Reality |
|---|---|
| “You fine-tuned the model for tools” | **No.** Same `qwen2.5-coder:7b` weights. |
| “You rebuilt search for the agent” | **No.** `search_docs` calls `index.retrieve` — the same function Phase 2 graded and Phase 3 improved. |
| “The corpus grew” | **No.** Same 3284 chunks, same Qdrant collection. |

**What DID change:** **who decides whether to look up.** Before, the code always retrieved once.
Now the model chooses. That freedom is the whole experiment — and R9.5 is what it did with it.

**Named example of “who decides.”** Under the first agent prompt (*“You may call tools”*), the
lab called a tool on **4 of 100** questions. Same model, forced probe (*“Call exactly one… Do not
answer from memory”*) got **100 of 100**. The lookup machinery was fine; the *decision* to use it
was not.

**Say this:** “We did not train anything. We changed who chooses the lookup — from hard-coded
once to the model.”

**Do not say:** “We added an agent layer so retrieval got smarter.” (Retrieval is identical.)

---

## R9.2 — What a “tool” actually is

**Plain job.** Kill the idea that the model “runs code.” A tool is boring on purpose.

**Picture:**

```
  ┌─────────────────────────────┐
  │  Model (only writes text)   │
  │  "... {"name":"check_api",  │
  │        "arguments":{...}} " │
  └──────────────┬──────────────┘
                 │  our loop parses that JSON
                 ▼
  ┌─────────────────────────────┐
  │  Python in rag/tools.py     │
  │  actually runs check_api()  │
  └──────────────┬──────────────┘
                 │  result pasted back as another message
                 ▼
  ┌─────────────────────────────┐
  │  Model writes again         │
  │  (answer, or another call)  │
  └─────────────────────────────┘
```

**A tool is two things glued together:**

**1. A normal function** you could call from a shell:

```
uv run python -m rag.tools --check Query.from_self
```

**2. A paragraph in the system prompt** that lists the name, when to use it, and the argument
shape:

```json
{"name": "check_api",
 "description": "Check whether a symbol still exists in SQLAlchemy 2.0 …",
 "parameters": {"symbol": "A dotted symbol, e.g. 'Query.from_self'"}}
```

The model’s “tool call” is **more text that looks like JSON**. If it writes garbage JSON, the loop
fails that step — the model did not “crash a function”; it failed to write a parseable request.

**Named example.** Model writes:

```json
{"name": "check_api", "arguments": {"symbol": "Query.from_self"}}
```

Our code runs `check_api`, gets `exists=False`, pastes that back. The model never imported
SQLAlchemy.

**What it is not.**

- Not fine-tuning.
- Not the model executing Python.
- Not MCP / plugins / a separate “agent runtime” product — it is a `for` loop in `rag/agent.py`.

**Why this section exists before the results.** R9.5’s failure (*answers from memory with fake
citations*) is a **text-writing** failure. It makes no sense if you think the model was already
“using tools” in some magical sense.

**Say this:** “The model only emits text. Sometimes the text is a JSON tool request. Our loop runs
the function and feeds the result back.”

**Do not say:** “The LLM calls APIs.” (Our process does. The LLM asks.)

**Code.** `rag/tools.py` (functions), `rag/agent.py` (`run()` loop).

---

## R9.3 — The three tools (and why one of them is the argument)

**Plain job.** Show the menu, then spend the time on `check_api` — the only tool that exists
because a Phase 4 bug was measured.

| tool | what it does | where it came from |
|---|---|---|
| `search_docs` | Corpus lookup via `index.retrieve` | Phases 1–3, **unchanged** |
| `get_function_source` | Real source from real SQLAlchemy **2.0.51** | New |
| **`check_api`** | Does this symbol exist in 2.0, and what is its signature? | **`D77`, turned around** |

### Picture for `check_api`

```
  Phase 4 (after the fact)          Phase 5 (before the answer)
  ─────────────────────             ──────────────────────────
  Bad answer already written   →    Model may call check_api first
  Human runs hasattr(...)      →    Same check, as a tool
  Post-mortem                  →    Guardrail
```

### Named example — `g065`

Prompt D answered an unanswerable “table + view in one migration” question with an Alembic script:

```python
op.create_table(...)      # real
sa.Column(...)            # real
op.create_view(...)       # DOES NOT EXIST
op.drop_view(...)         # DOES NOT EXIST
```

Proved, not guessed:

```
uv run python -m rag.tools --g065
  OK alembic.operations.Operations.create_table       exists=True  (expected True)
  OK alembic.operations.Operations.create_view        exists=False (expected False)
```

> **The measurement that caught the bug becomes the tool that prevents it.** That is how you know
> a guardrail guards something real, not something imagined.

**Alembic is official** — the SQLAlchemy project’s migration tool, separate package. The
fabrication is not “Alembic is fake”; it is “`create_view` is not on `Operations`.”

**What `check_api` is NOT.**

- Not a prose fact-checker. `g056` lied in *sentences*; this tool is blind to that (`D77`).
- Not “does this advice help the user?” — only “does this dotted name resolve in the pinned 2.0
  (or alembic) install?”
- Not `verify_2_0.py` (that script runs breakages patterns). See R9.4.

**Say this:** “`check_api` is the `g065` post-mortem offered to the model before it writes.”

**Do not say:** “The agent verifies every answer against SQLAlchemy.” (Only if it chooses this
tool, and only for symbols.)

---

## R9.4 — The version problem (and what `verify_2_0` is *not* doing)

**Plain job.** Explain why “just `import sqlalchemy` and check” is illegal in this repo, and how
that relates to Phase 0 without merging the two jobs.

**Picture:**

```
  This project's normal Python          A throwaway Python we spawn
  (SQLAlchemy 1.4.52 on purpose)        (--with sqlalchemy==2.0.51)

        rag/tools.py  ──asks──►   "does Operations.create_view exist?"
              ▲                              │
              │                              ▼
              └──────── JSON yes/no ◄────────┘
```

**Why two Pythons.** `experiments/` is an instrument pointed at **1.4.52** (`D04`). The process
asking “does this exist in **2.0**?” cannot import 2.0 in-process — it would be a different
library fighting the project pin. So:

```
uv run --no-project --with 'sqlalchemy==2.0.51' python -c "...one JSON in, one JSON out..."
```

### Wasn’t `verify_2_0` only for breakages?

**Yes — as a program, that is all it does.**

| | `verify_2_0.py` (Phase 0) | `rag/tools.py` `check_api` (Phase 5) |
|---|---|---|
| **Job** | Run 1.4 patterns on real 2.0; fill `BREAKAGES.md` | “Does this *symbol* exist in 2.0?” |
| **Does the LLM call it?** | Never | Only if the agent chooses `check_api` — and even then it calls `tools.py`, **not** `verify_2_0` |
| **Shared** | Pin `PIN = "2.0.51"` + “spawn a 2.0 interpreter from a 1.4 process” | Same pin + same spawn trick |

Same *how do I ask 2.0 from a 1.4 process?*, different *question*. **Breakages tool ≠ agent tool.**

### The import trap (why PIN is read as text)

You cannot `from verify_2_0 import PIN` here: that module calls `sys.exit()` at import time when it
finds itself on 1.4 — which is always. Worse:

> **`SystemExit` does not inherit from `Exception`.** `try/except Exception` does not catch it.
> Your process just ends.

So `PIN` is **read out of the file as text**. One source of truth, no import, test ties them.

**Say this:** “We reuse verify_2_0’s pin and subprocess pattern. We do not run the breakages suite
for the LLM.”

**Do not say:** “The agent uses verify_2_0.” / “We upgraded the project to 2.0 for tools.”

**Code.** `rag/tools.py` `_pin()`, `PIN`; `experiments/.../verify_2_0.py` owns the string.

---

## R9.5 — Score `0.02`: why that number is not the finding

*(Heading `R9.5` ≠ score. `0.02` below is the rate.)*

**Plain job.** Separate three stories that look like one bad score: metric definition, citation
harm, and a one-word prompt cause.

**Picture — what “end to end” requires:**

```
  One-shot (Phase 4):   code ALWAYS retrieves  →  page may be present  →  model answers
  Agent (first lab run): model MUST call search_docs or the page is absent by construction
```

Lab, 100 golden questions through the agent:

```
end to end     2/91 = 0.02        (one-shot on same box: 38/91 = 0.42)
no tool call   96      one tool 4      two or more 0
```

**“Twenty times worse” is the wrong sentence.** Three separate facts:

### First — definition, not quality

For the agent, “right page reached the model” requires a `search_docs` call. **96 of 100** got no
tool call. Of those, 43 declined and **53 answered from memory**. Those 53 are scored **zero by
construction** — not because they were graded wrong, because the metric cannot see an answer with
no lookup.

> Comparing `0.02` to `0.42` as one quantity is the blending mistake this project keeps killing.

### Second — those 53 were not secretly fine

| of the 53 answers with no retrieval | |
|---|---|
| carrying an `[n]` citation | **31** |
| …of which pointed at a real source | **0** |
| containing code | 42 |
| …code with no source at all | 41 |

**`n_sources` is zero on all 53**, so every `[1]` points at a passage that was never fetched.
Named example: **`g003` cites `[1]` against nothing.**

> Phase 4’s defect was answers that cite **nothing**. This is answers that cite **something that
> does not exist.** Worse on the axis the citation work was about. So `0.02` was *generous*.

### Third — cause was one word (permission vs obligation)

Standalone probe on the **same** questions: **100/100** tool calls. Agent: **4/100**. Difference:

| | instruction |
|---|---|
| probe → **100/100** | *“Call **exactly one**. **Do not answer from memory.**”* |
| agent → **4/100** | *“You **may** call tools.”* |

Must-call A/B on lab, n=20: **6↑ 0↓**, p = 0.031 on delivered; bad citations **9 → 0**.

**Say this:** “0.02 meant the agent skipped search, so end-to-end could not fire — and the memory
answers fabricated citations. The fix was obligation, not a new retriever.”

**Do not say:** “The agent is 20× worse than RAG.” / “Tools don’t work on 7B.”

---

## R9.6 — Tool calls across machines (the coin flip)

**Plain job.** Show that *whether to call a tool* is not a stable system property on ambiguous
questions — then show what *does* reproduce.

**Picture:**

```
  Same prompt, same model, temperature 0, same 20 items

       Mac:  no tool on  9/20
       Lab:  no tool on 19/20

       10 of 20 items FLIP which box skips the tool
```

> Whether the agent calls a tool at all disagrees between two machines on **half** the items.

**Compared to earlier drift:**

| Finding | What drifted |
|---|---|
| `D83` | Generation *wording*; answer/refuse mostly held |
| `D84` | 2 of 7 items overnight on Mac generator |
| **R9.6** | The **coarse** decision: call a tool or don’t |

**Why it matters.** `96/100` is *the lab’s* no-tool rate, not “the system.” And it put the
must-call prompt in the same hole as prompt H: strong on one box until the other is measured.

### The refinement (after R9.7’s nudge existed)

| the decision | agreement across machines |
|---|---|
| *is this how-to worth a lookup at all?* | **10 of 20** — coin flip |
| *symbol is gone; does the question also ask what replaces it?* | **10 of 10** |

> **Ambiguous decisions diverge across machines. Unambiguous ones do not.**

That rule orders the whole project: retrieval (arithmetic) reproduces exactly; answer/refuse drifts
a little; *worth a lookup?* is a judgement and flips; *half an answer ≠ whole answer* has one right
reading and matched twice.

**What to build from that.** Not a louder prompt — **less ambiguity**. “You MUST call a tool”
removes the judgement. The NOT FOUND nudge turns “is there more?” into a question with one answer.

**Say this:** “Call-or-not disagreed on half my items across Mac and lab. I stopped quoting a single
no-tool rate as a system property.”

**Do not say:** “Temperature 0 means identical across machines.” (`D84` already killed that.)

---

## R9.7 — Single-tool stop, then the nudge that moved it

**Plain job.** Separate “cannot plan two steps” from “does not know the first step was incomplete.”

**Picture — the failure mode:**

```
  Q: "Was MetaData.bind removed in 2.0, and how do I replace it?"

  [1] check_api("MetaData.bind")  →  NOT FOUND   ← correct, half the answer
  [2] model DECLINES                ← abandoned the "how do I replace it?" half
```

Across **two machines, two prompts, eighty runs**: tools were chained **exactly once** before the
nudge work. Measured read: this 7B setup does **single-tool lookup**, not multi-step agency — until
told otherwise at the right moment.

**What that is NOT.** Not “agents don’t work.” Not “this model is bad.” It names **7B + this task +
these tools**. A larger model is unmeasured here.

### Two explanations that look the same from outside

| Story | If true, what fixes it |
|---|---|
| Never plans a second step | Need a different model |
| Does not know step 1 wasn’t the end | **Tell it** when step 1 is partial |

Golden how-to items almost never call `check_api` (0 times in 60 runs on first 20) — they route to
docs. So: **ten two-part questions** built on purpose (gone symbol + replacement).

Nudge text, appended **only** when `check_api` returns NOT FOUND:

> *“That settles whether the symbol exists. If the question also asks what to use instead, search
> the docs before answering.”*

```
            no tool   one  two+
plain             0    10     0
nudged            0     3     7
```

**0 → 7 of 10**, paired p = 0.0156. Lab matched Mac **question by question** (same seven chained).

**Honest denominator: 7 of 9.** One item searched docs first on both boxes, so NOT FOUND never
happened and the nudge never fired. Counting it would inflate a result the experiment never
reached.

**What that is NOT.** Not “the agent chains now” in general. It chains on questions *built* for two
steps, when *told* the first was partial. Says nothing about three steps.

**Interview honesty.** Expected explanation written down first: planning failure. **Wrong.** It was
a stopping failure.

**Say this:** “It stopped after a correct NOT FOUND. One sentence at that moment took chaining
0 → 7/10 on both machines.”

**Do not say:** “We solved multi-hop agents.” / “Prompting fixed planning.”

---

## R9.7b — The `[:600]` bug (why the agent looked broken)

**Plain job.** Show a gap with no mechanism, then the four characters that created it — and the
conclusion that reversed.

**Picture:**

```
  One-shot pipeline:  full chunk text in the prompt
  Agent (buggy):      hit["text"][:600]   ← median chunk is 1299 chars
                                          ← 2755 of 3284 chunks exceed 600

  Answer sitting in characters 601…1299  →  model never saw it
                                         →  correctly "refuses" a page that looks empty
```

**The suspicious table** (same model, same machine, page *did* reach the agent):

| | refused anyway |
|---|---|
| agent | 22 of 45 = **49%** |
| one-shot | 19 of 58 = **33%** |

Sixteen points with **no mechanism** if you believe both saw the same page. A model does not get
more cowardly because a different function called it.

**After deleting the slice:**

```
                     ceiling      delivered     conversion
agent, half pages     45/91      23/91 = 0.25      51%
agent, whole pages    45/91      39/91 = 0.43      87%
one-shot pipeline     58/91      39/91 = 0.43      67%
```

**16↑ 0↓**, p = 0.00003. Ceiling unchanged (same 45 items retrieved). Generation conversion
exploded.

### Conclusion reversed

Before the fix: “agent refusal ≈ Phase 4 over-refusal.” **Backwards.** After full pages:
over-refusals agent **6** vs pipeline **19**.

> Agent *generation* (with full pages) refuses less than the one-shot. Agent *retrieval discipline*
> is worse (many questions never look up). On the Mac those cancelled to the same **0.43**.

**The habit worth keeping:** a gap you cannot explain is a bug until proven otherwise. “Agents are
lossy” would have fitted the data and been wrong.

**Say this:** “0.25 vs 0.43 was my truncation of every retrieved chunk to 600 characters.”

**Do not say:** “Agents naturally over-refuse more than RAG.”

**Code.** Comment in `rag/agent.py` next to the full-text path — the `[:600]` is gone on purpose.

---

## R9.7c — Where it landed (levers, lab, policy, drill)

**Plain job.** Show what shipped as levers, what the Mac headline claimed, what the lab withdrew,
and the failure-path drill.

### The two levers (kept because measured)

| Lever | What it does | Constraint |
|---|---|---|
| **force** | If the model writes prose before any tool ran, refuse **once** and say so | Cap, not a loop — unbounded refusal → infinite retry |
| **nudge** | After `check_api` → NOT FOUND, one sentence that half the question may remain | Fires *only* there |

### Mac screen (not the final claim)

```
              default  force+nudge   one-shot pipeline
ceiling            45           54                 58
delivered          39           43                 39
over-refused        6           11                 19
no tool call       23            1                  —
two or more         0            6                  —
end to end       0.43         0.47               0.43
```

Mac levers vs Mac default: **4↑ 0↓**, p = 0.125 (no regressions; not significant at this n).

### Lab — headline withdrawn (`D94`)

```
                ceiling  delivered    e2e   conv  over-ref  no-tool  two+
Mac default          45         39   0.43    87%         6       23     0
Mac levers           54         43   0.47    80%        11        1     6
lab default          25         25   0.27   100%         0       51     0
lab levers           45         33   0.36    73%        12        4     7
one-shot pipeline    58         39   0.43    67%        19        —     —
```

> **“The agent matches the one-shot pipeline” is a MAC claim. Withdrawn.** Lab default **0.27**.
> Pass/fail named that outcome before the run.

**What reproduced (behaviours), what did not (level):**

| | Mac | lab |
|---|---|---|
| levers, paired | 4↑ 0↓, p = 0.125 | **8↑ 0↓, p = 0.0078** |
| chaining after levers | 6 | 7 |
| force: no-tool-call | 23 → 1 | 51 → 4 |
| over-refusals vs pipeline’s 19 | **6** | **0** |

Lab no-tool **51/100** vs Mac **23/100** — R9.6’s coin flip with score consequences.

> **The score is machine-dependent. The findings (levers help, chaining appears, fewer over-refusals
> than one-shot) are not.**

**Best system that holds on both boxes:** one-shot pipeline (**0.43 / 0.42**). An agent whose score
halves by machine is not “better” on its best day.

### Policy (`D95`)

**Mac screens, lab rules, both stay.** Measuring only on the lab would delete the disagreement
class that produced several register entries. Quote the lab, or quote both. A Mac-only figure is
labelled a **screen when written**, not after the lab disagrees.

### Drill — break a tool on purpose

Fake models prove the loop’s code paths. Real model + forced timeout:

```
[1] check_api('MetaData.bind') FAILED: TimeoutError: timed out after 120s
[2] refused prose before any tool ran
[3] search_docs('MetaData.bind removed in SQLAlchemy 2.0')
stopped: answered
```

Three recoveries: error written **in words** into the conversation; force blocks memory answer;
model switches to the **other** tool and answers.

> An agent with no failure path is decoration — shown, not asserted.

**Say this:** “On the Mac the levered agent tied 0.43; on the lab default it was 0.27. Behaviours
reproduced; the level did not. One-shot still wins as the portable system.”

**Do not say:** “Our agent beats RAG at 0.47.” (Mac screen; withdrawn as a cross-machine claim.)

---

## R9.8 — Say this out loud

**Plain job.** Five spoken claims + the follow-ups that kill soft answers.

**"I was wrong three times in one night, and the register says so."**
Predicted single-tool ceiling = planning failure — it was stopping; nudge **0 → 7/10**. Predicted
levered ~50 delivered at ceiling 58 — got 54/43. Wanted “agent matches pipeline” — lab **0.27**,
withdrawn. **Predictions written before the runs.**

**"The agent looked 18 points worse than the pipeline, and it was four characters of my own code."**
**0.25** vs **0.43** until `[:600]` died. Then **16↑ 0↓**, and over-refusals **6 vs 19** — generation
better, retrieval discipline worse.

**"My agent scored 0.02 and I did not report that as the finding."**
Metric needed a retrieval the agent skipped; 53 zeros by construction; those answers also cited
missing passages; must-call fixed fabricated citations **9 → 0** on the A/B.

**"Whether it calls a tool at all disagrees across my two machines on half the items."**
Same prompt, temperature 0, **10/20** flip. Stopped quoting `96/100` as a system constant.

**"It stopped after one tool, and I found out why rather than tuning around it."**
`MetaData.bind`: correct NOT FOUND, then stop. Distinguishing experiment → stopping failure, not
planning; nudge **p = 0.0156**, both boxes item-identical.

### Follow-ups

| they say | you say |
|---|---|
| *“So the agent is a failure.”* | It zeroed fabricated citations when it retrieved; it has not shown general multi-step agency — different claims, both numbered. |
| *“Why not a bigger model?”* | Unmeasured. Constraint is zero paid APIs + 12 GiB card. |
| *“Isn’t 0.02 vs 0.42 just bad?”* | Different quantities: one assumes unconditional retrieval. Real comparison was citation harm, then the must-call A/B. |
| *“You changed the prompt after seeing results — tuning?”* | Thresholds written first; several were **missed** and recorded as misses; changes argued in the register (`D87`…). |
| *“Does the LLM use verify_2_0?”* | No. Breakages runner is Phase 0. Tools reuse its **pin + subprocess**; the model never imports it. |

---

## After this you can say

- A tool is a function + a paragraph; the model only writes text.
- `check_api` is the `g065` / `op.create_view` post-mortem as a guardrail.
- `0.02` was skipped search + fake citations — not “20× worse RAG.”
- Call-or-not flipped on half the items across Mac/lab (ambiguous decisions).
- Chaining moved with a NOT FOUND nudge on two-part questions (**7/10**, both boxes).
- `[:600]` made 0.25; full text made 0.43 on the Mac and reversed the refusal story.
- Lab withdrew “agent matches pipeline”; portable winner stays the one-shot (**~0.43**).

**Commands:**

```
uv run python -m rag.tools --g065
uv run python -m rag.tools --check Query.from_self
# agent sweeps: see phases/PHASE-5.md and rag/agent.py (e1/e2/e4)
```

**Plan / decisions:** [`../phases/PHASE-5.md`](../phases/PHASE-5.md), [`09-DECISIONS.md`](09-DECISIONS.md)
`D87`–`D95`.
