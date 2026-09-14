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
| **File `17-…`** | Reading-order filename (`01`…`18`) | Related to §R9’s digit |

So **`R9.4` means “section 4 of the Phase 5 study notes.”** Not “score 9.4,” not “SQLAlchemy 9.4.”

### 2. Rates like `2/91` — counts first, decimals later

Scores in this file are **fractions of golden questions**, not section numbers. **Do not read a
decimal until R9.5 has shown you what was counted.** The short map:

| You will see | What was counted | Section that shows the arithmetic |
|---|---|---|
| **`2/91` → written `0.02`** | Agent on the lab: only **2** of **91** answerable questions both looked up a page *and* answered | **R9.5** (start there) |
| **`38/91` → written `0.42`** | Same box, same fraction, but the **one-shot** system (always searches; no tools) | R9.5 side-by-side |
| **`96/100` skipped tools** | How often the agent never called `search_docs` — the reason `2/91` is tiny | R9.5 |
| later `0.43`, `0.47` | Agent after bugs/levers; Mac vs lab disagree on the level | R9.7b–R9.7c |

`R9.5` in a heading is still just “section 5.” The rate lives *inside* that section.

### 3. Map of this file

| Section | One sentence | Read when |
|---|---|---|
| **R9.0** | The one sentence to say about Phase 5, and the slogan not to say | Starting cold |
| **R9.1** | Before: one lookup always. Now: the model chooses when to look up. | First |
| **R9.2** | A “tool” = Python function + description. Model writes JSON; our code runs it. | First |
| **R9.3** | Three tools; `check_api` is the “does `op.create_view` exist?” check from the fake Alembic answer (`g065`), offered *before* writing. | First |
| **R9.4** | Why we cannot `import` 2.0 from this 1.4 env — reuses an *old spawn trick*, not the breakages runner. | Before tools code |
| **R9.5** | Lab agent almost never searched; `2/91` is not “20× worse than one-shot.” | Core result |
| **R9.6** | Same prompt, Mac vs lab: call-a-tool-or-not flipped on half the items. | Reproducibility |
| **R9.7** | Almost never chains two tools — until a NOT FOUND nudge; then 7/10 on two-part questions. | Agency limit |
| **R9.7b** | Our own `[:600]` truncation made the agent look worse than it was. | The bug story |
| **R9.7c** | Where Phase 5 landed; lab withdrew the Mac headline; drill. | Closing |
| **R9.7d** | Copy the agent's conversation *shape* into the one-shot pipeline, no tools: refusals fall, guesses rise just as much. | After R9.7c |
| **R9.8** | What to say out loud in an interview. | Before interviews |

**If you have ten minutes:** R9.2 → R9.5 → R9.7b → R9.8.

### Words this file uses that are not Python

Read this table once. Every later section assumes it. When a word appears again, the table is the
short meaning; the named section is the full story.

| Word | Plain meaning (show, then name) | Where the story is |
|---|---|---|
| **agent** | A loop: model writes text → if the text asks for a tool, *our* code runs a Python function → we paste the result back → model writes again. Not “the model browses the internet.” | R9.1–R9.2 |
| **one-shot / pipeline** | The Phase 1–4 system: search once, stuff five pages into one prompt, answer once. No tools, no loop. | R9.1 |
| **tool** | A normal Python function plus a short description the model can read. The model does not run it; it writes JSON asking for it. | R9.2 |
| **tool call** | That JSON request (“please run `check_api` with …”). | R9.2 |
| **`tool_calls` channel** | Ollama’s special field for tool requests. Our model put the JSON in ordinary chat text instead — still usable, but not the “official” channel. | R9.5 / `D87` |
| **fabrication** | Model answered a question it should have refused, and invented content. | R9.3 (`g065`, `g056`) |
| **post-mortem** | Looking at a failure *after* it already happened (autopsy / after-action). | R9.3 day one |
| **guardrail** | A check meant to stop the bad thing *before* it ships. | R9.3 day two |
| **over-refusal** | Right doc page was already in the five pages on the desk, and the model still said “sources do not answer.” | R9.7b; Phase 4 |
| **ceiling** | Count of questions where search found the answer page — upper bound on what answering can get right. | R9.7b |
| **delivered** | Ceiling items the model actually answered (did not decline). | R9.7c |
| **conversion** | Delivered ÷ ceiling — “of the ones search found, how many did generation finish?” | R9.7b |
| **end to end (e2e)** | Delivered ÷ all answerable questions (91). The number users feel. | R9.5, R9.7c |
| **nudge** | One extra sentence *we* append to a tool result to push a second step. The model did not invent it. | R9.7 |
| **chaining** | Calling two or more tools in one question (step 1, then step 2). | R9.7 |
| **agency / multi-step** | Planning several tool uses on its own. Measured here: almost never, until the nudge. | R9.7 |
| **truncation** | Cutting text short. Our bug: only the first 600 characters of each page reached the agent. | R9.7b |
| **lever** | A deliberate change we turn on to measure (force a tool call; add the nudge). Not shipped as default unless said so. | R9.7c |
| **force** | Code that makes the model call a tool even if it wanted to answer from memory. | R9.7c |
| **screen (Mac screen)** | A result measured only on this laptop — useful for hunting bugs, **not** the number to quote until the lab agrees. | R9.7c / `D95` |
| **framing** | Changing the *shape* of the prompt (system/user turns) without adding tools. | R9.7d |
| **willingness** | Answering more often — including when the pages do not support an answer (guessing). | R9.7d |
| **coin flip** | Across Mac and lab, half the items disagree on “call a tool or not.” | R9.6 |
| **temperature 0** | Sampling setting that makes the model pick the most likely next token. Does **not** guarantee the same answer on two machines. | R9.6 |
| **paired / ↑ ↓** | Same questions before and after a change: how many newly fixed vs newly broken. | R9.7, R9.7c |
| **p = 0.0156** | Exact McNemar p-value. If the change did nothing, each flipped item is a coin toss between “fixed” and “broken”; p is how often coin tosses would come out at least this lopsided. 7 fixed, 0 broken → 0.0156. Smaller = harder to explain as luck. **Not** “the chance the result is wrong.” | R9.7 (worked arithmetic) |
| **SUPPORTED / PARTIAL / UNSUPPORTED** | A *judge model’s* grades: claims fully on the pages / partly / not on the pages. Not the same as “correct on real SQLAlchemy.” | R9.7d; Phase 4 / 6 |
| **must-call prompt** | System text that orders the model to call a tool instead of answering from memory. | R9.6–R9.7c |

When in doubt: **open the section in the right column**, do not invent a meaning from the word alone.

### Golden questions this file names by id

Same rule as production: an id is one row in `deliverables/golden.json`, not a score.

| id | the developer's question (short) | why this file names it |
|---|---|---|
| **`g065`** | Create table and view in the same migration | Invented `op.create_view`; becomes the `check_api` tool |
| **`g056`** | Query property for models in 1.4–2.0 | Fabrication in *prose* — `check_api` cannot see it |
| **`g003`** | `engine.table_names()` attribute error | Agent cited `[1]` with **no** retrieved sources |
| **`g050`** | `engine.execute` gone — use connection | Page-present over-refusal; framing arm B “fixed” it |
| **`g043`** | `select()` keyword args no longer work | Framing arm B **broke** a good A answer on both machines |
| **`g114`** | `Row is not mapped` when deleting | Page **absent**; arm B answered anyway (guess) |

---

## R9.0 — Where to start

**Plain job.** Point you at the three sections that carry the interview, so you do not drown in
R9.7c’s tables on day one.

**Say this:** “Phase 5 measured a tool-using loop on the same 7B model. The headline is not a
score — it is what the model would and would not do with tools.”

**Do not say:** “We built an agent and it got 2%.” (R9.5 shows what was counted; that slogan
skips the count and invents a comparison.)

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

**1. A normal function** you could call from a shell. Here is the one the model can ask for, run
by hand, with its real output:

```
$ uv run python -m rag.tools --check Query.from_self
Query.from_self  (in sqlalchemy 2.0.51)
  exists     False
  signature  None
```

`exists False` is an **answer**, not an error: `Query.from_self` was removed in 2.0, and the
function says so.

**2. A description sent with every request.** Each request to Ollama carries a `tools` list next to
the messages (`TOOLS` in `rag/toolcall.py`, sent by `toolcall.ask_messages`). This is the real
entry for `check_api`, shortened only in its argument block:

```python
{"type": "function",
 "function": {
     "name": "check_api",
     "description": ("Check whether a symbol still exists in SQLAlchemy 2.0 and "
                     "what its signature is. Use to confirm whether something was "
                     "removed, renamed, or is still available."),
     "parameters": {... "symbol" ...}}}
```

It is **not** part of the system prompt. The system prompt is a separate, short text that says
*how* to use tools. This is the agent's default one, `SYSTEM_MUSTCALL` in `rag/agent.py`:

```
You help a developer upgrade code from SQLAlchemy 1.4 to 2.0.
You have two tools. You MUST call a tool before answering — do not answer from memory.
Call ONE tool at a time and wait for its result. Once you have tool results, answer in prose and cite sources as [1], [2].
If the tools cannot establish the answer, reply "The sources do not answer this."
```

The model’s “tool call” is **more text that looks like JSON**. If it writes garbage JSON, the loop
fails that step — the model did not “crash a function”; it failed to write a parseable request.

**Named example, the whole round trip.** The model writes:

```json
{"name": "check_api", "arguments": {"symbol": "Query.from_self"}}
```

Our code runs `check_api`, gets `exists: False`, and pastes this sentence back as the next message
(`_observation` in `rag/agent.py`, word for word):

```
check_api: NOT FOUND. This symbol does not exist in the pinned version. That is a definite answer, not an error.
```

The model never imported SQLAlchemy. It read one sentence that our code wrote.

**Where the JSON actually arrives.** Ollama has a dedicated `tool_calls` field for these
requests. `qwen2.5-coder:7b` never used it: **0 of 120** calls in Step 0 came through that field,
and every one arrived as JSON inside ordinary reply text (`D87`). The loop reads the text. That is a
fact about this model, not a failure of the loop: `gemma4:e4b` used the field through the same code.

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
because a Phase 4 bug was measured. The menu table is further down, after the story that explains
its last row.

### Two ordinary words, with the day they happened

This section used to say *"post-mortem → guardrail"* and assume you knew both. You do not need
to. Here is what actually happened, then the names.

**Day one — the failure already happened (Phase 4, Aug 21).**

A developer on Stack Overflow asked: *"Create table and view in the same migration in
SQLAlchemy"* (golden id `g065`). Our docs do **not** teach that recipe, so the honest system
answer is *"The sources do not answer this."*

Instead the model wrote a confident Alembic script:

```python
op.create_table(...)      # real — exists on Alembic
sa.Column(...)            # real
op.create_view(...)       # FAKE — this method does not exist
op.drop_view(...)         # FAKE — same
```

Nothing crashed when it wrote that. A user who trusted the answer would have pasted two
invented calls next to two real ones. **We only caught it afterwards.** The check, as it runs today:

```
# runnable: uv run python -m rag.tools --g065
g065 — the fabricated Alembic script, checked against real alembic (D77)
  OK alembic.operations.Operations.create_table       exists=True  (expected True)
  OK alembic.operations.Operations.create_view        exists=False (expected False)
  Two invented calls beside two working ones — and the tool separates them.
```

Two lines, one real call and one invented one, and the only difference between them is
`exists=True` against `exists=False`. That is the whole check: import the longest importable part of
the dotted name (`alembic.operations`), then `getattr` each remaining name in turn (`Operations`,
then `create_view`). The first `None` means the symbol does not exist. It runs inside a throwaway
Python that has the library installed (R9.4 says why it has to be a throwaway one). The code is the
`_PROBE` string in `rag/tools.py`.

That *afterwards* check is what people call a **post-mortem** (literally: looking at a failure
after it is already dead — like an autopsy, or an after-action review at work). The answer was
already produced. The check explained *why it was wrong*. It did not stop the wrong answer from
being written.

**Day two — stop it before it is written (Phase 5).**

We took **the same** existence check and exposed it as a tool named `check_api`. Now the
model, *while answering*, can ask: *"Does `Operations.create_view` exist?"* and get `False`
**before** it invents a script. That is what people call a **guardrail**: a barrier that is
supposed to keep you from falling off, not a report written after you fell.

```
  AFTER the bad answer (Phase 4)         BEFORE the answer (Phase 5)
  ─────────────────────────────         ────────────────────────────
  Model already wrote create_view  →    Model may call check_api first
  Human runs hasattr(Operations,   →    Same question, callable as a tool
             "create_view")
  You learn it was wrong           →    Model can see "does not exist" first
  = post-mortem                    →    = guardrail
```

> **Nothing magical.** We did not train the model to know Alembic. We did not enlarge the
> corpus. We offered it one Python function that returns yes/no for a dotted name — the same
> function we used by hand when we caught `g065`.

**Alembic** is the SQLAlchemy project's official migration tool (separate package). The bug is
not “Alembic is fake”; it is “`create_view` is not on `Operations`.”

### The menu: three tools built, two offered

| tool | what it does | where it came from | offered to the agent? |
|---|---|---|---|
| `search_docs` | Corpus lookup via `index.retrieve` | Phases 1–3, **unchanged** | **yes** |
| **`check_api`** | Does this symbol exist in 2.0 (or alembic), and what is its signature? | **`g065` post-mortem → guardrail** (`D77`, `D88`) | **yes** |
| `get_function_source` | Real source from real SQLAlchemy **2.0.51** | New in Phase 5 | **no** |

**Read the last column before you say "three tools" out loud.** All three are functions in
`rag/tools.py`, each testable from a shell (`--check`, `--source`, `--g065`). But the list the
model is sent with every request, `TOOLS` in `rag/toolcall.py`, has two entries: `search_docs` and
`check_api`. That is why the system prompt says *"You have two tools."* Every agent number in this
file was measured with those two. `get_function_source` is built and tested, and the model never
saw it.

**What `check_api` is NOT.**

- Not a prose fact-checker. *"Query property for models…"* (`g056`) lied in *sentences* with no
  fake API name — this tool never sees that, because there is no dotted symbol to look up.
- Not “does this advice help the user?” — only “does this dotted name resolve in the pinned 2.0
  (or alembic) install?”
- Not `verify_2_0.py` (that script runs breakages patterns). See R9.4.
- Not automatic. The model must **choose** to call it. If it never calls the tool, there is no
  guardrail that day — only the option of one.

**Say this:** “In Phase 4 we caught a fake `op.create_view` after the answer was written. In
Phase 5 that same check is a tool the model can call before it writes.”

**Do not say:** “The agent verifies every answer against SQLAlchemy.” (Only if it chooses this
tool, and only for symbols.)
**Do not say:** “post-mortem” or “guardrail” in an interview without the day-one / day-two story
above — the words alone sound like buzzwords; the timeline is the proof.

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

**Why two Pythons.** `experiments/` is an instrument pointed at **1.4.52** (`D17`: the app under test must stay broken). The process
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

## R9.5 — The agent almost never looked anything up

**Plain job.** Show what we ran and what we counted on the lab. Only then name the fraction
people shorten to `0.02` — and show why “twenty times worse than `0.42`” is the wrong sentence.

### What we ran (before any decimal)

| | |
|---|---|
| **Machine** | Lab PC (RTX 3060) |
| **System** | The Phase 5 **agent** — model may call tools; code does not force a search |
| **Questions** | All **100** golden items (same set Phase 4 used) |
| **Model** | Same 7B generator as the one-shot pipeline (`qwen2.5-coder:7b`) |

Of those 100, **91** are answerable (9 are deliberately unanswerable). The fraction below uses
91 as the denominator, not 100.

### What we counted first: did it call a tool at all?

```
  of 100 questions:

      never called any tool     96
      called exactly one tool    4
      called two or more         0
```

So on **96 of 100** questions the agent never ran `search_docs`. No lookup → no doc pages on
the desk → it either declined or answered from memory.

### Then: of the 91 answerable, how many “worked end to end”?

This project’s **end-to-end** count needs **both**:

1. the verified answer page somehow reached the model, **and**
2. the model answered (did not decline).

For the **one-shot** system, step 1 is automatic: our code always searches and pastes five pages
into the prompt. For the **agent**, step 1 only happens if the model chooses `search_docs`.

```
  Lab, agent, first full run:

      both (1) and (2) true     2 of 91

  Same lab, same 91, one-shot pipeline (always searches):

      both (1) and (2) true    38 of 91
```

**Now the decimals** (same fractions, written short):

| system | fraction | often written |
|---|---|---|
| agent, that run | **2 / 91** | **0.02** |
| one-shot, same box | **38 / 91** | **0.42** |

`0.02` is not a section number and not “2% quality.” It is **2 successes out of 91 answerable
questions** under that agent run.

### Why “20× worse” is the wrong sentence

Someone sees `0.42 / 0.02 ≈ 21` and says the agent is twenty times worse than RAG. That blends
two different setups:

```
  One-shot:   code ALWAYS retrieves  →  pages may be present  →  model answers
  Agent:      model MUST call search_docs or pages are absent by construction
```

Of the **96** no-tool questions, **53** still *answered* from memory. Those 53 count as **zero**
on end-to-end — not because a human graded them wrong, but because the metric requires a lookup
that never happened. Comparing `2/91` to `38/91` as one “quality” number is the blending mistake
this project keeps killing.

### Those 53 memory answers were not secretly fine

| of the 53 answers with no retrieval | |
|---|---|
| carrying an `[n]` citation | **31** |
| …of which pointed at a real source | **0** |
| containing code | 42 |
| …code with no source at all | 41 |

**Zero sources were fetched**, so every `[1]` points at a passage that was never on the desk.
Named example: **`g003` cites `[1]` against nothing.**

> Phase 4’s defect was answers that cite **nothing**. This is answers that cite **something that
> does not exist.** Worse on the citation axis. So treating `2/91` as the whole story was
> *generous* to the agent.

### Cause was one word: permission vs obligation

A standalone probe on the **same** questions got **100/100** tool calls. The agent got **4/100**.
Difference:

| | instruction |
|---|---|
| probe → **100/100** | *“Call **exactly one**. **Do not answer from memory.**”* |
| agent → **4/100** | *“You **may** call tools.”* |

**The same swap, measured inside the agent** (Round 18, `D90`). Both prompts on the same **20**
answerable questions, lab PC, item by item:

```
                                   "You may call tools"   "You MUST call a tool"
out-of-range citations ([n] with          9                        0
  no source behind it), of 20
delivered: newly fixed / newly broken     —                  6 fixed, 0 broken   (p = 0.031)
```

The citation fix is the one the prompt was **designed** for, and it reproduced on the Mac too (3 → 0).
The `delivered` gain did **not** reproduce: on the Mac it was 0 fixed, 1 broken. So the must-call
prompt became the agent's default for fixing citations, not for its score. The p-value arithmetic is
in R9.7.

**Say this:** “On the lab the agent skipped search on 96 of 100 questions, so end-to-end was
only 2 of 91. That is not ‘20× worse RAG’ — the one-shot number assumes a lookup that the agent
never made. The memory answers also invented citations. The fix was obligation, not a new
retriever.”

**Do not say:** “The agent is 20× worse than RAG.” / “Tools don’t work on 7B.” / “We scored 0.02”
without saying **2 of 91** and **skipped search**.

---

## R9.6 — Tool calls across machines (the coin flip)

**Plain job.** Show that *whether to call a tool* is not a stable system property on ambiguous
questions — then show what *does* reproduce.

### What we ran (before any claim about “the system”)

| | |
|---|---|
| **Machines** | This Mac **and** the lab PC |
| **System** | Same agent prompt, same model (`qwen2.5-coder:7b`), temperature **0** |
| **Questions** | Same **20** golden items on both boxes |

### What we counted

```
  of those 20 questions, how many got NO tool call at all?

       Mac:   9 of 20
       Lab:  19 of 20

  how many items DISAGREED (one box called a tool, the other did not)?

       10 of 20   ← half the set
```

That half-disagreement is what this section means by **coin flip**: not random noise in wording —
the coarse yes/no *“should I look something up?”* flips by machine.

> Whether the agent calls a tool at all disagrees between two machines on **half** the items.

**Compared to earlier drift:**

| Finding | What drifted |
|---|---|
| `D83` | Generation *wording*; answer/refuse mostly held |
| `D84` | 2 of 7 items overnight on Mac generator |
| **R9.6** | The **coarse** decision: call a tool or don’t |

**Why it matters.** The lab’s full-run **96 of 100** never called a tool (R9.5). That is *the lab’s*
no-tool rate, not “the system.”

It also put the must-call prompt in the same hole as **prompt `H`**. `H` is Phase 4's candidate
answer prompt (§R8, `D74`): it moved the "cite your sources" sentence into the question turn, and on
the Mac it fixed 9 answers and broke 0. On the lab it fixed 6 and broke 2, so it was never shipped
(`D83`). The lesson carried over: a prompt that looks strong on one machine is a candidate until the
other machine has measured it.

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

### What “nudge” means here (before the numbers)

After a tool returns, *our code* can append one extra sentence the model did not write. That
sentence is the **nudge**. It is not a second prompt rewrite and not a new model.

### The failure mode (named example)

```
  Q: "Was MetaData.bind removed in 2.0, and how do I replace it?"

  [1] check_api("MetaData.bind")  →  NOT FOUND   ← correct, half the answer
  [2] model DECLINES                ← abandoned the "how do I replace it?" half
```

The first half is real and you can run it: `uv run python -m rag.tools --check MetaData.bind` prints
`exists False`, because 2.0 removed bound metadata. What the model read back was the sentence from
R9.2: *"check_api: NOT FOUND. This symbol does not exist in the pinned version. That is a definite
answer, not an error."* Nothing in that sentence says the question has a second half.

### What we counted before the nudge

Across **two machines, two prompts, eighty runs**: tools were chained (two or more in one
question) **exactly once**. Measured read: this 7B setup does **single-tool lookup**, not
multi-step agency — until told otherwise at the right moment.

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

### What we counted with the nudge

```
            no tool   one tool   two or more tools
plain             0         10                  0
nudged            0          3                  7
```

**Chaining went from 0 of 10 → 7 of 10.** Paired exact McNemar p = 0.0156. Lab matched Mac
**question by question** (same seven chained).

### Where `p = 0.0156` comes from, and every other p in this file

A p-value sounds like a statistics black box. Here it is a coin, and you can do it by hand.

Only the questions that **changed** count. A question that chained under both prompts, or under
neither, says nothing about the nudge. Seven questions changed, and all seven changed the same way
(plain: one tool → nudged: two).

Now suppose the nudge did nothing. Then each of those seven changes is a coin toss: as likely to go
"fixed" as "broken". Seven heads in a row is `0.5 ** 7 = 1/128 = 0.0078`. Seven tails in a row would
be just as surprising, so both count: `2 × 0.0078 = 0.0156`. That is the whole calculation.

When some flips go each way, you add up every outcome at least as lopsided. The same function, over
every paired result this file quotes:

```
# runnable: uv run python -c "
#   from math import comb
#   def p(fixed, broken):
#       n, k = fixed + broken, min(fixed, broken)
#       return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)
#   print('if nothing changed, each flipped item is a coin toss: fixed or broken')
#   for fixed, broken, where in [(7, 0, 'R9.7   nudge, chained'), (6, 0, 'R9.5   must-call, lab delivered'), (16, 0, 'R9.7b  whole pages vs half'), (8, 0, 'R9.7c  lab levers'), (4, 0, 'R9.7c  Mac levers'), (6, 1, 'R9.7d  arm B, Mac')]:
#       print(f'{where:33} {fixed:2} fixed {broken} broken   p = {p(fixed, broken):.5f}')
#   print('the smallest p that 4 flips can ever give:', 2 * 0.5 ** 4)
#   "
if nothing changed, each flipped item is a coin toss: fixed or broken
R9.7   nudge, chained              7 fixed 0 broken   p = 0.01562
R9.5   must-call, lab delivered    6 fixed 0 broken   p = 0.03125
R9.7b  whole pages vs half        16 fixed 0 broken   p = 0.00003
R9.7c  lab levers                  8 fixed 0 broken   p = 0.00781
R9.7c  Mac levers                  4 fixed 0 broken   p = 0.12500
R9.7d  arm B, Mac                  6 fixed 1 broken   p = 0.12500
the smallest p that 4 flips can ever give: 0.125
```

**Read the last line with the Mac levers row.** Four fixes and zero breaks is the best result four
flips can produce, and its p is still 0.125. So *"not significant"* there says the sample of changed
questions was small. It does **not** say the levers did nothing. The lab's eight clean fixes clear
the same bar easily (0.0078).

**And read the last two rows together.** "4 fixed 0 broken" and "6 fixed 1 broken" give the same p.
One break costs about as much evidence as two extra fixes buy.

**What a p-value is not.** It is not "the chance the finding is wrong", and it is not a size. `D61`
is why this project reports the fixed and broken **ids** beside it: a p says whether the flips could
be luck, and only the ids say *which* questions a user gains or loses.

**Honest denominator: 7 of 9.** One item searched docs first on both boxes, so NOT FOUND never
happened and the nudge never fired. Counting it would inflate a result the experiment never
reached.

**What that is NOT.** Not “the agent chains now” in general. It chains on questions *built* for two
steps, when *told* the first was partial. Says nothing about three steps.

**Interview honesty.** Expected explanation written down first: planning failure. **Wrong.** It was
a stopping failure.

**Say this:** “It stopped after a correct NOT FOUND. One sentence at that moment took chaining
from 0 of 10 to 7 of 10 on both machines.”

**Do not say:** “We solved multi-hop agents.” / “Prompting fixed planning.”

---

## R9.7b — The `[:600]` bug (why the agent looked broken)

**Plain job.** Show a gap with no mechanism, then the four characters that created it — and the
conclusion that reversed.

### What was wrong in the code (show, then name)

Each time the agent retrieved a doc page, our code passed the model only the **first 600
characters**:

```
  hit["text"][:600]
```

That cut is **truncation**. The median chunk in the corpus is **1299** characters; **2755 of
3284** chunks are longer than 600. So for most pages the model saw about **half** of what the
one-shot pipeline puts in the prompt.

```
  One-shot pipeline:  full chunk text in the prompt
  Agent (buggy):      first 600 characters only

  Answer sitting in characters 601…1299  →  model never saw it
                                         →  correctly "refuses" a page that looks empty
```

### The suspicious count (same model, same machine, page *did* reach the agent)

| | refused even though search found the page |
|---|---|
| agent (half pages) | **22 of 45** |
| one-shot (full pages) | **19 of 58** |

As rates: `22 ÷ 45 = 49%` for the agent, `19 ÷ 58 = 33%` for the one-shot. **Sixteen points** with
**no mechanism** if you believe both saw the same page. A model does not get more cowardly because a
different function called it.

The two denominators differ (45 against 58) because the agent searched on fewer questions. That is
why the comparison is a rate and not a raw count: 22 and 19 look close and are not.

### After deleting the slice — what we counted

Three words used below (same as the glossary at the top of this file):

- **ceiling** — how many of the 91 answerable had the answer page retrieved at all
- **delivered** — of those, how many the model actually answered
- **conversion** — delivered ÷ ceiling

```
                     ceiling      delivered              conversion
agent, half pages     45 of 91    23 of 91               23/45 = 51%
agent, whole pages    45 of 91    39 of 91               39/45 = 87%
one-shot pipeline     58 of 91    39 of 91               39/58 = 67%
```

**Now the short forms** people write for delivered ÷ 91:

| | fraction | often written |
|---|---|---|
| agent, half pages | **23 / 91** | **0.25** |
| agent, whole pages | **39 / 91** | **0.43** |
| one-shot | **39 / 91** | **0.43** |

Paired: **16** newly delivered, **0** newly broken after the fix (p = 0.00003). Ceiling unchanged
(same 45 items retrieved). Generation conversion exploded.

### Conclusion reversed

Before the fix: “agent refusal ≈ Phase 4 over-refusal.” **Backwards.** After full pages:
over-refusals agent **6** vs pipeline **19**.

> Agent *generation* (with full pages) refuses less than the one-shot. Agent *retrieval discipline*
> is worse (many questions never look up). On the Mac those cancelled to the same **39 of 91**.

**The habit worth keeping:** a gap you cannot explain is a bug until proven otherwise. “Agents are
lossy” would have fitted the data and been wrong.

**Say this:** “23 of 91 vs 39 of 91 was my truncation of every retrieved chunk to 600 characters —
not ‘agents refuse more.’”

**Do not say:** “Agents naturally over-refuse more than RAG.” / lead with `0.25` without **23 of 91**.

**Code.** Comment in `rag/agent.py` next to the full-text path — the `[:600]` is gone on purpose.

---

## R9.7c — Where it landed (levers, lab, policy, drill)

**Plain job.** Show what shipped as levers, what the Mac headline claimed, what the lab withdrew,
and the failure-path drill.

### The two levers (kept because measured)

| Lever | What it does in plain words | Constraint |
|---|---|---|
| **force** | If the model writes an answer before any tool ran, refuse **once** and say so | Cap, not a loop — unbounded refusal → infinite retry |
| **nudge** | After `check_api` → NOT FOUND, one sentence that half the question may remain | Fires *only* there |

### Mac screen — counts first (not the final claim)

A **screen** means: measured on this laptop only. Useful for hunting; **not** the number to quote
until the lab agrees (`D95`).

```
                         default     force+nudge     one-shot pipeline
ceiling (of 91)               45              54                    58
delivered (of 91)             39              43                    39
over-refused                   6              11                    19
no tool call (of 100)         23               1                     —
two or more tools              0               6                     —
```

**Same counts as short end-to-end rates** (delivered ÷ 91):

| | fraction | often written |
|---|---|---|
| Mac default | **39 / 91** | **0.43** |
| Mac levers | **43 / 91** | **0.47** |
| one-shot | **39 / 91** | **0.43** |

Mac levers vs Mac default: **4** newly delivered, **0** newly broken, p = 0.125 (no regressions;
not significant at this n).

### Lab — headline withdrawn (`D94`)

Same columns, both machines:

```
                         ceiling  delivered   of 91    conv   over-ref  no-tool  two+
Mac default                   45         39   39/91    87%          6       23     0
Mac levers                    54         43   43/91    80%         11        1     6
lab default                   25         25   25/91    100%         0       51     0
lab levers                    45         33   33/91    73%         12        4     7
one-shot pipeline             58         39   39/91    67%         19        —     —
```

Short forms for delivered ÷ 91: Mac default **0.43**, Mac levers **0.47**, lab default **0.27**,
lab levers **0.36**, one-shot **0.43**.

**Every column is arithmetic on the first two**, so you can check any row: `conv` = delivered ÷
ceiling (lab levers: `33 ÷ 45 = 73%`), `over-ref` = ceiling − delivered (lab levers: `45 − 33 = 12`).

**The lab default's `100%` is not a good sign.** Its ceiling is only **25**, and the biggest reason
is that **51 of 100** questions never called a tool, so no page could arrive for them. On the 25 where a page did arrive, the model
answered every one. A perfect conversion on a small ceiling still delivers the fewest answers in the
table.

> **“The agent matches the one-shot pipeline” is a MAC claim. Withdrawn.** Lab default is
> **25 of 91**. Pass/fail named that outcome before the run.

**What reproduced (behaviours), what did not (level):**

| | Mac | lab |
|---|---|---|
| levers, paired | 4↑ 0↓, p = 0.125 | **8↑ 0↓, p = 0.0078** |
| chaining after levers | 6 | 7 |
| force: no-tool-call | 23 → 1 | 51 → 4 |
| over-refusals, default prompt, vs pipeline’s 19 | **6** | **0** |

Lab no-tool **51 of 100** vs Mac **23 of 100** — R9.6’s coin flip with score consequences.

> **The score is machine-dependent. The findings (levers help, chaining appears, fewer over-refusals
> than one-shot) are not.**

**Best system that holds on both boxes:** one-shot pipeline (Mac **39 of 91** / lab **38 of 91**, one
apart). The agent's default goes from **39 of 91** on the Mac to **25 of 91** on the lab, fourteen
apart on the same questions. An agent that loses fourteen answers when you change the machine is not
“better” because of its best machine.

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

**Say this:** “On the Mac the levered agent delivered 43 of 91; on the lab default it was 25 of 91.
Behaviours reproduced; the level did not. One-shot still wins as the portable system.”

**Do not say:** “Our agent beats RAG at 0.47.” (Mac screen; withdrawn as a cross-machine claim.)

---

## R9.7d — Was it just the shape of the conversation? (`D96`)

**Plain job.** The agent refused far less than the pipeline when the right page was in front of it
(**6** on the Mac, **0** on the lab, against the pipeline's **19–20**). Before crediting the tools,
check the cheaper explanation: maybe it is only *how the pages arrive*.

### What we ran

| | |
|---|---|
| **Arms** | **A** = shipped one-shot shape; **B** = agent conversation shape with **no tools** and one call |
| **Held fixed** | Same model, same system prompt, same five pages, same `[1]`…`[5]` numbering |
| **Machines** | Mac and lab both |

### The two prompts, side by side

Same model, same system prompt, same five pages, same `[1]`…`[5]` numbering. One call each.

```
arm A — what ships                      arm B — the agent's shape, no tools
--------------------------------        --------------------------------------------------
system: SYSTEM                          system: SYSTEM
user:   SOURCES [1]..[5]                user:   QUESTION: row.keys() AttributeError ...
        ---                             assistant: Let me look that up in the SQLAlchemy
        QUESTION: ...                              documentation.        <- we wrote this line
        ANSWER:                         user:   SOURCES [1]..[5] --- QUESTION --- ANSWER:
```

**What did NOT happen in arm B.** No tool was called. The model did not choose a query, did not
decide to look anything up, and did not generate that assistant line. We typed it. It is the agent's
conversation with every agent-like part removed. `rag/framing.py`, `as_conversation`.

### The count that looked like a win

```
                 page present   over-refused
arm A                      58             19      <- D72's number, to the item: the control works
arm B                      58             14      Mac: 6 fixed, 1 broken, p = 0.125
```

Five fewer refusals with the page in hand. That is the number Phase 4 could not move with five
wordings (`D74`).

### The row nobody had printed

"Over-refused" only looks at items **where the answer page was in the prompt**. When the page was
**not** there, refusing is the honest outcome, so a prompt that answers *more* there is not
improving. It is guessing more.

Each count below is a number of questions where **arm A declined and arm B answered**. It is not a
net figure: the few that went the other way are in the next table.

```
                         page present: A declined,     page ABSENT: A declined,
                         B answered                    B answered
Mac, B vs A              6   (g008 g021 g049 g050 ...)   6   (g005 g016 g028 g085 g113 g114)
lab, B vs A              5   (g021 g029 g049 g050 g100)  4   (g005 g016 g113 g114)
```

**Same shift on both sides of the line.** That is what "more willing to answer" looks like. A
prompt that helped the model *read* would move the left column and leave the right one alone.

Take `g114`: *"Why am I getting 'Class sqlalchemy.engine.row.Row is not mapped'…"*. The page that
answers it was not retrieved. Arm A said *"The sources do not answer this."*, which is correct.
Arm B answered anyway on **both** machines. On the Mac the answer had two code blocks and no
citation, and the judge found it `UNSUPPORTED`. On the lab it had one code block citing `[3]`,
which is a page that does not hold the answer (the lab's answer was not judged).

### Read the ids, not the counts

Each id below is one golden question (see the **Golden questions this file names by id** table
near the top of this file).

```
                       both machines              Mac only     lab only
page present  fixed    g021 g049 g050 g100        g008 g116    g029
page present  broken   g043                       --           g019
page absent   extra    g005 g016 g113 g114        g028 g085    --
```

Named so the table is readable without opening `golden.json`:

| id | short question | role in this experiment |
|---|---|---|
| `g050` | `engine.execute` gone | page present; B answered where A refused |
| `g043` | `select()` keyword args gone | page present; **B broke** a good A answer on both boxes |
| `g114` | `Row is not mapped` | page **absent**; B guessed on both boxes |
| `g056` / `g065` | query property / table+view migration | fabrications — **unchanged** under both arms |

- **What reproduces is four fixes and one break**, not six and one. `g008` and `g116` were Mac
  extras. On the lab, B still refused them.
- **`g043` is a real loss.** Arm A answered it (*"select() no longer accepts keyword arguments…"*),
  and the judge read that answer as `SUPPORTED`. Arm B refused it on both machines.
- **Of the four shared fixes, two are `SUPPORTED`** (`g021 g049`) **and two `PARTIAL`** (`g050
  g100`). Three of the four shared page-absent extras are `UNSUPPORTED`. (Mac judge, a screen.)
- **Fabrications did not move:** `g056` and `g065`, both arms, both machines.
- **Citations did not improve:** uncited 67% → 68% on the Mac, 33% → 44% on the lab.

### What it is, and what it is not

- It **is** a measured rejection. The shipped prompt stays; `D72`'s 19–20 stand.
- It is **not** "framing does nothing". Framing moved refusals in both directions, and the part
  that moved is mostly willingness.
- It is **not** an explanation of the agent's low refusals. With the tools removed, the shape
  alone gave a small, noisy move that came with unsupported answers. What the agent does
  differently (its own query, its own decision to look) is still the suspect, and it is untested.

**Say this:** “I copied the agent's conversation shape into the pipeline with no tools. Refusals
with the page present fell on both machines, but the items answered *without* the page rose just as
much. Read by id, what reproduced was four fixes against one lost good answer and four new unsupported
guesses, so I didn't ship it.”

**Do not say:** “Conversation framing cuts over-refusals by a quarter.” That is one machine's count
of one row. The second machine and the second row both disagree.

---

## R9.8 — Say this out loud

**Plain job.** Five spoken claims + the follow-ups that kill soft answers.

**"I was wrong three times in one night, and the register says so."**
Predicted single-tool ceiling = planning failure — it was stopping; nudge **0 of 10 → 7 of 10**.
Predicted levered ~50 delivered at ceiling 58 — got ceiling 54 / delivered 43. Wanted “agent matches
pipeline” — lab **25 of 91**, withdrawn. **Predictions written before the runs.**

**"The agent looked 18 points worse than the pipeline, and it was four characters of my own code."**
**23 of 91** vs **39 of 91** until `[:600]` died. Then **16↑ 0↓**, and over-refusals **6 vs 19** —
generation better, retrieval discipline worse.

**"On the lab the agent searched on 4 of 100; end-to-end was 2 of 91 — and that was not the finding."**
Metric needed a lookup the agent skipped; 53 memory answers scored zero by construction; those
answers also cited passages that were never fetched; must-call fixed fabricated citations **9 → 0**
on the A/B. Do not report “0.02 vs 0.42” as one quality ratio.

**"Whether it calls a tool at all disagrees across my two machines on half the items."**
Same prompt, temperature 0, **10/20** flip. Stopped quoting `96/100` as a system constant.

**"It stopped after one tool, and I found out why rather than tuning around it."**
`MetaData.bind`: correct NOT FOUND, then stop. Distinguishing experiment → stopping failure, not
planning; nudge **p = 0.0156**, both boxes item-identical.

### Follow-ups

| they say | you say |
|---|---|
| *“So the agent is a failure.”* | Once it was made to search, its out-of-range citations went to zero (lab 9 → 0, Mac 3 → 0, `D90`); it has not shown general multi-step agency — different claims, both numbered. |
| *“Why not a bigger model?”* | **As the agent: unmeasured.** Phase 6 did run a 550B hosted model, `nemotron-3-ultra-550b`, but as the **one-shot** generator on free credits (§R10.15b), never inside this loop. The local constraint is zero paid APIs and a 12 GiB card. |
| *“Isn’t 0.02 vs 0.42 just bad?”* | Show **2/91** vs **38/91** first. Different setups: one-shot always searches; agent skipped search on 96/100. Real comparison was citation harm, then the must-call A/B. |
| *“You changed the prompt after seeing results — tuning?”* | Thresholds written first; several were **missed** and recorded as misses; changes argued in the register (`D87`…). |
| *“Does the LLM use verify_2_0?”* | No. Breakages runner is Phase 0. Tools reuse its **pin + subprocess**; the model never imports it. |

---

## After this you can say

- A tool is a function + a description sent in the request's `tools` list; the model only writes text.
- Three tools are built; the agent was offered two (`search_docs`, `check_api`).
- `check_api` is the `g065` / `op.create_view` post-mortem as a guardrail.
- First lab agent run: **2 of 91** end-to-end because it skipped search — not “20× worse RAG.”
- Call-or-not flipped on half the items across Mac/lab (ambiguous decisions).
- Chaining moved with a NOT FOUND nudge on two-part questions (**7/10**, both boxes).
- `[:600]` made **23 of 91**; full text made **39 of 91** on the Mac and reversed the refusal story.
- Lab withdrew “agent matches pipeline”; portable winner stays the one-shot (**~39 of 91** / lab **38 of 91**).

**Commands:**

```
uv run python -m rag.tools --g065
uv run python -m rag.tools --check Query.from_self
# agent sweeps: see phases/PHASE-5.md and rag/agent.py (e1/e2/e4)
```

**Plan / decisions:** [`../phases/PHASE-5.md`](../phases/PHASE-5.md), [`09-DECISIONS.md`](09-DECISIONS.md)
`D87`–`D95`.
