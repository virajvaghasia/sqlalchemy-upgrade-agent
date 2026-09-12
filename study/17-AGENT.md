# §R9 — The agent, and what a 7B model will not do

Phase 5's sitting. The measured plan is [`../phases/PHASE-5.md`](../phases/PHASE-5.md); this file
is the read. Continues the `R` run after [`16-JUDGE.md`](16-JUDGE.md) (§R8) — one run across all
of it, `R` for RAG, not Retrieval (`D47`).

**Read this before the plan.** The plan says what was run. This says what any of it means.

---

## R9.0 — Where to start

If you have ten minutes before an interview, read **R9.2** (what an agent actually is here),
**R9.5** (the 0.02, and why the number is not the finding) and **R9.8** (the three things to say
out loud). Everything else is evidence for those.

---

## R9.1 — What changed, in one sentence with no jargon in it

Up to Phase 4 the system did one thing: you asked a question, it looked in the docs **once**, and
it wrote an answer.

Now it can **decide for itself** what to look up, look, read what came back, and decide again.

That is the whole difference, and it is worth being blunt about what did *not* change:

- **You did not train anything.** Same model file, same weights, same `qwen2.5-coder:7b`.
- **The corpus did not change.** Same 3284 chunks, same Qdrant collection.
- **Retrieval did not change.** The agent calls `index.retrieve` — the exact function Phase 2
  graded and Phase 3 improved. Not a copy of it.

**What changed is who decides.** Before, the code decided: *every* question got exactly one
lookup, always, whether it needed one or not. Now the model decides. That is the entire upgrade,
and R9.5 is about what it did with the freedom.

---

## R9.2 — A "tool" is a Python function and a paragraph describing it

There is no magic here and the word makes it sound like there is.

A tool is two things:

**One — a normal function.** `rag/tools.py` has three. `check_api("Query.from_self")` returns
`{"exists": False}`. That is it. You could call it from a shell.

**Two — a paragraph the model is shown**, telling it the function exists and when to use it:

```json
{"name": "check_api",
 "description": "Check whether a symbol still exists in SQLAlchemy 2.0 and what its
                 signature is. Use to confirm whether something was removed, renamed,
                 or is still available.",
 "parameters": {"symbol": "A dotted symbol, e.g. 'Query.from_self'"}}
```

The model reads that paragraph and writes back, in text:

```json
{"name": "check_api", "arguments": {"symbol": "Query.from_self"}}
```

**The model does not run anything.** It writes a string. Our loop reads the string, calls the real
function, and pastes the result back into the conversation as if a person had typed it. Then the
model writes again.

> **An LLM with tools is still only writing text. The text just sometimes looks like a function
> call, and something else does the calling.**

That is worth saying plainly because the failure in R9.5 is *exactly* a text-writing failure and
makes no sense if you think the model is executing anything.

---

## R9.3 — The three tools, and why one of them is the whole argument

| tool | what it does | where it came from |
|---|---|---|
| `search_docs` | the corpus, through `index.retrieve` | Phases 1–3, unchanged |
| `get_function_source` | real source out of real SQLAlchemy 2.0.51 | new |
| **`check_api`** | **does this symbol exist in 2.0, and what is its signature** | **`D77`, turned around** |

**`check_api` is the one that matters, and here is the argument for it in full.**

Back in Phase 4, prompt `D` answered an unanswerable question — `g065` — with an Alembic migration
script. The script called four things. Two are real:

```python
op.create_table(...)      # real
sa.Column(...)            # real
op.create_view(...)       # DOES NOT EXIST
op.drop_view(...)         # DOES NOT EXIST
```

We proved the last two were invented by running one line:

```python
hasattr(Operations, "create_view")   # False
hasattr(Operations, "create_table")  # True
```

**That was a post-mortem.** The bad answer already existed; a person went looking, afterwards, and
found it.

`check_api` is that same line, offered to the model **before it writes**. Reproduce it:

```
uv run python -m rag.tools --g065
  OK alembic.operations.Operations.create_table       exists=True  (expected True)
  OK alembic.operations.Operations.create_view        exists=False (expected False)
```

> **The measurement that caught the bug becomes the tool that prevents it.** That is the only way
> I know to be sure a guardrail guards something real, rather than something imagined.

**What it is NOT.** It is not a fact-checker for prose — it reads symbols, not claims. `g056`
fabricated in *sentences*, not code, and `check_api` is structurally blind to it, exactly as `D77`
said it would be.

---

## R9.4 — The version problem, which is the interesting engineering bit

**This project is pinned to SQLAlchemy 1.4.52 on purpose.** `experiments/` is an instrument
pointed at 1.4; that is the whole point of it (`D04`).

So: the process that needs to answer *"does this exist in 2.0?"* **cannot import 2.0 to find out.**
It is running on 1.4.

The answer is to ask a **different interpreter**:

```
uv run --no-project --with 'sqlalchemy==2.0.51' python -c "...one JSON in, one JSON out..."
```

That was already this repo's answer — `verify_2_0.py` has done it since Phase 0 — so `tools.py`
reuses it rather than inventing a second one.

**And there is a trap in reusing it that is worth knowing.** You cannot `from verify_2_0 import
PIN`, because that module calls `sys.exit()` at import time when it finds itself on 1.4 — which is
always, here. Worse:

> **`SystemExit` does not inherit from `Exception`.** A `try/except Exception` around the import
> would not catch it. Your process just ends.

So `PIN` is **read out of the file as text**. One source of truth, no import, and a test ties the
two together.

---

## R9.5 — The result: `0.02`, and why the number is not the finding

The lab ran all 100 golden questions through the agent.

```
end to end     2/91 = 0.02        (the shipped one-shot pipeline, same box: 38/91 = 0.42)
```

**Twenty times worse. And reporting it that way would be wrong.** Three separate things are going
on and they have to be separated before anything means anything.

### First — most of that gap is the metric's definition, not the answer's quality

`end_to_end` means *a verified answer page reached the model **and** the model answered*. For the
agent, "reached the model" requires a `search_docs` call.

```
no tool call   96      one tool 4      two or more 0
```

**The agent answered 96 of 100 questions without looking anything up.** Of those, 43 declined and
**53 answered from memory**.

> Those 53 answers are scored **zero by construction**. Not because they are wrong — because the
> metric cannot see an answer that had no lookup behind it.

So `0.02` against `0.42` is not "twenty times worse at answering". Comparing them as one quantity
is the mistake this project has a whole rule about.

### Second — the 53 answers are worse than the score suggests, not better

The obvious next thought is *"maybe those 53 memory answers were fine"*. They were not:

| of the 53 answers with no retrieval | |
|---|---|
| carrying an `[n]` citation | **31** |
| …of which pointed at a real source | **0** |
| containing code | 42 |
| …code with no source at all | 41 |

**`n_sources` is zero on all 53**, so every `[1]` in them refers to a passage that was never
fetched. `g003` cites `[1]` against nothing.

> **Phase 4's defect was answers that cite NOTHING. This is answers that cite something that does
> not exist.**

That is worse, and it is worse in precisely the dimension the whole citation effort was about. So
`0.02` was *generous*.

### Third — the cause was one word, and finding that took one A/B

The standalone probe had already got a tool call on **100 of 100 of these same questions**. Same
model, same machine, same temperature. The only difference was the instruction:

| | |
|---|---|
| probe → **100/100 called a tool** | *"Call **exactly one** of them. **Do not answer from memory.**"* |
| agent → **4/100 called a tool** | *"You **may** call tools."* |

**A permission against an obligation.** Changing that one thing, and nothing else:

| lab, paired, n=20 | delivered | bad citations |
|---|---|---|
| shipped prompt | — | **9 wrong** |
| must-call prompt | **6↑ 0↓**, p = 0.031 | **0 wrong** |

**Nine fabricated-citation items fixed, none broken.** Because an agent that actually retrieves has
real sources to point at.

---

## R9.6 — Tool calls do not reproduce across machines — until you look closer

While checking the prompt, the same 20 items were run with the **same shipped prompt** on both
boxes, at temperature 0:

| | no tool call |
|---|---|
| Mac | **9 / 20** |
| lab | **19 / 20** |

**Ten of the twenty flip.**

> **Whether the agent calls a tool at all disagrees between two machines on half the items.**

This is larger than anything earlier in the project. `D83` found generation wording drifting while
the answer/refuse decision held; `D84` found two items in seven flipping overnight on the Mac.
**Here the coarse decision itself — call a tool, or don't — is the thing that stopped
reproducing.**

**Why it matters more than it sounds.** It means `96/100` is *the lab's number*, not the system's.
And it put my own prompt fix in exactly the position prompt `H` was in: a strong result on one
machine, with the other one unmeasured. Which is why Round 18 existed at all.

### The rule that came out of it, once a second measurement existed

The nudge experiment in R9.7 agrees across machines on **10 of 10** questions. The same two boxes,
the same model, the same day. So *"tool calls don't reproduce"* is too blunt. Put the two side by
side:

| the decision | agreement across machines |
|---|---|
| *is this how-to question worth a lookup at all?* | **10 of 20** — a coin flip |
| *the symbol is gone; is the question also asking what replaces it?* | **10 of 10** |

> **Ambiguous decisions diverge across machines. Unambiguous ones do not.**

That single rule explains every reproducibility result in this project, in order: retrieval is
arithmetic and reproduces exactly; answer-or-refuse is mostly settled and drifts a little; *is this
worth a lookup* is a genuine judgement call and lands on a coin flip; *is half an answer the whole
answer* has one right answer and lands identically twice.

**And it tells you what to build.** Not a firmer instruction — **less ambiguity**. The nudge works
because it turns *"is there more to do?"* into a question with one answer. The must-call prompt
works for the same reason: *"you MUST call a tool"* contains no judgement, where *"you may"* is an
invitation to decide.

---

## R9.7 — What no prompt fixed, and what that probably means

One number has been the same everywhere: **two machines, two prompts, eighty runs, tools were
chained exactly once.**

The named example is the clearest way to see it. Asked *"Was `MetaData.bind` removed in 2.0, and
how do I replace it?"* — a two-part question — the agent:

1. called `check_api("MetaData.bind")`,
2. got back **NOT FOUND**, which is correct and is half the answer,
3. and then **declined**, instead of searching for the replacement.

It answered the first half and abandoned the second. Every failure path in the loop worked
correctly; the model simply stopped.

> **The measured answer so far is that this model does single-tool lookup, not multi-step agency.**

**What that is NOT.** It is not "agents don't work" and it is not "this model is bad". It is a
statement about **a 7B local model on this task with these tools**, and the honest form of it names
all three. A larger model may well chain; nothing here measures that.

### And then it turned out to be the other explanation

There were two stories that fit, and from outside they look the same:

- **It never planned a second step.** Then nothing you say will produce one, and you need a
  different model.
- **It does not know the first step was not the end.** Then telling it is enough.

To tell them apart you need questions that *require* two steps. The golden set will not do —
measured, `check_api` was called **zero** times in 60 runs over the first twenty golden items,
because those are how-to questions and route to the docs. So: ten questions built to be two-part, a
symbol that is gone plus what replaces it.

Then one sentence, added to the tool result **only** when `check_api` comes back NOT FOUND:

> *"That settles whether the symbol exists. If the question also asks what to use instead, search
> the docs before answering."*

```
            no tool   one  two+
plain             0    10     0
nudged            0     3     7
```

**Zero to seven out of ten. Paired, p = 0.0156.**

> **It stops. It cannot not-continue.** The ceiling that nothing had moved in eighty runs came
> down to one sentence, fired at the one moment the model has half an answer and does not know it.

**The lab then saw the same thing — and not merely the same summary.** Plain 0 of 10, nudged 7 of
10, `p = 0.0156`, on both boxes, **agreeing question by question, ten out of ten.** The same seven
chained and the same three did not.

**And the honest denominator is 7 of 9.** One question went to the docs first on both machines, so
the API check never returned NOT FOUND and the nudge could not fire at all. Counting it in the
denominator would inflate the result with an item the experiment never reached — which is exactly
how the first version of this experiment fooled me.

**What that is NOT.** Not "the agent chains now". It chains on questions *built* to need two steps,
when *told* the first was partial. It says nothing about three steps.

**The honest part I would say in an interview:** I wrote down which explanation I expected — the
planning one — before running it, and I was wrong.

---

## R9.8 — Say this out loud

**"My agent scored 0.02 and I did not report that as the finding."**
The metric requires a retrieval the agent never performed, so 53 answers were zero by construction.
Then I checked whether those answers were fine anyway, and they were worse than the score — a
majority cited passages that had never been fetched. Then I found the one-word prompt cause, fixed
it, and measured 9 fabricated-citation items fixed and none broken.

**"Whether it calls a tool at all disagrees across my two machines on half the items."**
Same prompt, same model, temperature 0, ten of twenty flip. So I stopped quoting `96/100` as a
property of the system, and I put my own prompt fix behind the same cross-machine rule that is
currently holding a *different* prompt I would rather have shipped.

**"It stopped after one tool, and I found out why rather than tuning around it."**
`MetaData.bind`: it checks the API, correctly learns the symbol is gone, and stops without looking
up the replacement — eighty runs, two machines, two prompts, one chained call. I wrote down the
explanation I expected, designed the test to *distinguish* it from the alternative rather than
confirm it, and was wrong: one sentence fired only after a NOT FOUND took chaining **0 → 7 of 10**,
p = 0.0156. It is a stopping failure, not a planning one.

### The follow-ups these attract, and what kills them

| they say | you say |
|---|---|
| *"So the agent is a failure."* | It fixed a real defect — fabricated citations to zero, both machines, zero regressions. It has not yet shown multi-step behaviour, which is a different claim and I have the number for it. |
| *"Why not just use a bigger model?"* | Nothing here measures a bigger model, so I would not claim it. The constraint is the project's: zero paid API calls, a 12 GiB card. |
| *"Isn't 0.02 vs 0.42 just bad?"* | They are not the same quantity. One requires a retrieval that the other performs unconditionally. Comparing them directly is the error I avoided, and the citation numbers are where the real comparison is. |
| *"You changed the prompt after seeing the result — isn't that tuning?"* | The threshold was written before the run, and **it was not met** — 7 of 20, not the ~2 I predicted. I recorded that it was not met rather than moving it, and the change went in on a different argument, which is in the register. |
