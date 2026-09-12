# Phase 5 — The agent, and the tools it is allowed to be wrong with

Part of [`sqlalchemy-upgrade-agent`](../README.md). **Teaching file:
[`../study/17-AGENT.md`](../study/17-AGENT.md) (§R9) — read that first;** this file is the measured
plan, that one is the sitting. Follows [`PHASE-4.md`](PHASE-4.md), which closed with **end to end `0.43`** against a **`0.64`** retrieval
ceiling, a judge measured at **70% human agreement** (`D86`), and prompt `H` **held** rather than
shipped (`D83`, `D84`). Spec: [`ROADMAP.md`](ROADMAP.md) Phase 5.

> **Up to now the system answers a question. Now it does a job.** That is a bigger change than it
> sounds, and the honest version of why is not "agents are the next step" — it is that **every
> number this repo trusts was measured on a single call**, and an agent is many calls whose
> failures compound.

---

## The number that decides whether this phase is possible at all

Phase 4 measured the generator answering **once**, with five passages already in the prompt:

| | |
|---|---|
| right page reached the prompt | **58 of 91** |
| …and the model actually answered | **39 of 91 = 0.43** |
| over-refusals with the page in hand | **19** |

**An agent multiplies that.** A two-tool task is at least three generations — choose a tool, read
its result, answer — and if each behaves like the one we measured, the compounded success rate is
not 0.43, it is closer to `0.43³`. **That arithmetic is the phase's central risk and it is why
Step 0 exists.** Nothing here is worth building if the local model cannot emit a valid tool call.

**The arithmetic is illustrative, not a prediction.** The three calls are not independent and the
third one is the only one graded the way `0.43` was. It is on the page because it sets the
question Step 0 has to answer with data: *does the loss per step look anything like this?*

---

## The constraint this phase inherits and must not forget

**`D84`: the Mac's generator drifts across days and the lab's does not.** Two lab runs five days
apart reproduced to the item; the Mac flipped two of seven overnight. **`D86` adds the judge to the
picture**: it drifts on the Mac (3 in 110) and is byte-identical on the lab, reason text included.

> **An agent is a generation-heavy system being built on the machine whose generations do not
> reproduce.** Every before/after in this phase is therefore either **run on the lab**, or **run in
> one sitting** on the Mac with the baseline re-taken beside it (`D54`). There is no third option
> and this is not negotiable for any number that reaches a doc.

**And a second inheritance, from `D61`:** report **flipped tasks**, not an average success rate.
Three separate routes in Phase 4 — drift (`D84`), the denominator (`D85`), the human's own
corrections (`D86`) — all moved individual grades and left the paired cells identical. That is now
the most reproducible finding in the project and it should shape how Phase 5 reports anything.

---

## Steps

### Step 0 — Can the local model call a tool at all? (half a sitting, and it may end the phase)

**Nothing is built until this is measured.** `qwen2.5-coder:7b` has never been asked to emit a
tool call in this repo. Its measured behaviour is all single-turn prose with citations.

Ask it, over the golden set's own questions, to choose between two obviously-distinct tools and
emit a structured call. Count three things and nothing else:

| | why this one |
|---|---|
| **syntactically valid** calls | a call that does not parse is not a retry problem, it is a dead end |
| **right tool chosen** | picking the wrong tool correctly is worse than failing loudly |
| **arguments that resolve** | `search_symbol("Query.from_self")` is only useful if the symbol exists |

**Decide from it, and write the decision down either way:**

- **If valid-call rate is high** — build the graph, Step 1.
- **If it is low** — that is a **result**, not a blocker. The phase becomes *"a tool-using agent on
  a 7B local model, and the measurement that says why it cannot be one"*, plus a fallback:
  constrained decoding, or a smaller hand-rolled loop with a single tool. **`D70` is the
  precedent** — a lever rejected without being built, on a number.

**CLOSED 2026-09-11 (`D87`). The gate opens, with a constraint.**

| | synthetic, labelled | the 100 golden questions |
|---|---|---|
| usable call | **20/20 = 100%** | **100/100 = 100%** |
| right tool | **20/20 = 100%** | not graded — unlabelled by design |
| on `message.tool_calls` | **0** | **0** |
| on `message.content` as JSON | **20** | **100** |

**The model chooses correctly and its arguments are well formed. It never uses the channel MCP
speaks.** All 120 calls arrived as JSON text in the content field. `gemma4:e4b` through the
identical code path uses `tool_calls` first attempt, so that is the model, not the harness.

**And the first run of this probe said `0 valid of 20`, which was my parser** — it read only
`message.tool_calls`. Printing one raw reply found a perfect call in the wrong field. *"The local
model cannot call tools"* would have ended this phase on thirty lines of my own code.

**Consequences for Step 1:** the agent parses content JSON; `qwen2.5-coder:7b` stays the model;
and **`gemma4:e4b` is not an option** however convenient its native channel, because it is the
**judge** (`D80`) and using it would have it grading its own tool use.

**Done when:** a rate exists with a decision id beside it, and the next step is chosen by it rather
than by the roadmap's ordering. — **met.**

---

### Step 1 — The MCP server, because it is the part that is nearly already built

**Build the tools before the agent.** They are independently testable, they are useful without an
agent, and this repo already contains most of them under different names.

| tool | what already does this | new work |
|---|---|---|
| `search_symbol` | `rag/bm25.py` + `rag/index.py` over `chunks.jsonl` | an MCP wrapper and a symbol-shaped query |
| `get_function_source` | — | real; reads the installed `sqlalchemy==2.0.51` |
| `check_api_signature` | **`tools/audit_golden_fullbar.py`** executes claims against real 2.0.51 | generalise from claims to signatures |

**`check_api_signature` is the differentiator and it is not hypothetical.** `D77` proved `g065`
fabricated by measuring `hasattr(Operations, "create_view") is False` on alembic 1.19.1 while
`create_table` in the same script was real. **That check, as a tool the model can call, is the
thing that would have caught the fabrication at generation time rather than in a post-mortem.**

**CLOSED 2026-09-11. `rag/tools.py`, 13 tests, all offline.**

```
# runnable: uv run python -m rag.tools --g065
g065 — the fabricated Alembic script, checked against real alembic (D77)
  OK alembic.operations.Operations.create_table       exists=True  (expected True)
  OK alembic.operations.Operations.create_view        exists=False (expected False)
  Two invented calls beside two working ones — and the tool separates them.
```

**That is the phase's argument in four lines.** `D77` could only prove `g065` fabricated *after*
the answer existed. The same check, callable before the model writes, is the difference between a
post-mortem and a guardrail.

**The version problem, and how it is solved rather than dodged.** This project is pinned to
**1.4.52** on purpose (`D04`), so the process asking *"does this exist in 2.0?"* cannot import 2.0
to find out. `check_api` runs the question in a throwaway interpreter —
`uv run --no-project --with 'sqlalchemy==2.0.51'` — which is `verify_2_0.py`'s answer, reused
rather than reinvented. **`PIN` is read out of that file, not copied**, and a test pins the two
together.

**And reading it is not squeamishness:** `verify_2_0` calls `sys.exit()` at module level when it
finds itself on 1.4, and `SystemExit` does not inherit from `Exception`, so importing it here would
kill the process past any guard. That trap is already in `CLAUDE.md`; this is the second module to
meet it.

**`exists: False` is an answer, not a failure** — the distinction the whole tool rests on. An agent
must treat *"this API was removed"* differently from *"the lookup broke"*.

**Done when:** each tool has tests, runs standalone, and `check_api_signature` reproduces the
`g065` verdict — `create_view` absent, `create_table` present — as a `# runnable` block. — **met.**

---

### Step 2 — The loop, and the failure path that justifies it

**An agent with no failure path is decoration**, so the failure path is built in the same step as
the loop rather than after it.

Four recovery behaviours, each with the defect it exists for:

- **Tool raised** → retry once, then fall back. `D75` is the precedent and it bit twice: a
  `socket.timeout` walked past a handler written for `URLError` and killed a sweep, and the same
  lesson **failed to travel between two modules** until a real timeout arrived at item 63 of 64.
- **Tool returned nothing** → reformulate, do not repeat. The 17 absents (`D70`) are the measured
  case where no reformulation helps; the agent must be able to stop.
- **Budget exhausted** → say so. An agent that loops is a worse failure than one that declines.
- **Nothing found** → **decline, and keep the refusal string `ask.refused()` already detects.**
  Phase 4's entire refusal instrumentation works only if the agent's decline looks like the
  generator's.

**BUILT 2026-09-11. `rag/agent.py`, 13 tests, all offline.** The loop reads `toolcall.classify`
and never either message field, so **`D87`'s open question cannot invalidate it**: whichever
channel Round 17 finds on the lab, this file is unchanged. Building it the other way would have
meant code whose correctness depended on a measurement still in flight.

**First real run found a classifier bug the Step 0 probe structurally could not.** Single-turn
probing got 120 replies that were pure JSON. Inside the loop the same model emits the call **and
then starts answering in the same field**:

```
{"name": "search_docs", "arguments": {"query": "from_self"}}

[1] SQLAlchemy 2.0 Migration Guide says...
```

`json.loads` on the whole string raises, so it scored as `prose` and **the loop treated it as an
answer and never ran the tool the model had just asked for.** Fixed with `raw_decode`; `D87`'s
numbers re-measured afterwards and unchanged at 20/20. **Fourth instrument in this repo to break
only once the thing under test started behaving differently** (`D76`, `D79`, `D87`).

**And the first honest look at multi-step behaviour, which is this phase's actual risk.** Three
questions, after the fix:

| question | tools used | outcome |
|---|---|---|
| rewrite a `from_self` query | `search_docs` | answered |
| was `MetaData.bind` removed, and what replaces it | `check_api` | **declined after one tool** |
| why is my `Comment` never INSERTed | **none** | **declined with no tool call** |

**One tool call, then stop.** `check_api` correctly returned NOT FOUND for `MetaData.bind` and the
model declined instead of searching for the replacement — a two-part question answered halfway and
then abandoned. **That is the compounding `PHASE-5.md` opened on, showing up on the third question
ever asked**, and it is Step 3's subject rather than a loop defect: every failure path here worked.

**Done when:** a deliberately injected tool failure is recovered visibly, and the injected-failure
drill is in the doc — the same shape as the `.dockerignore` break in `study/04-DOCKER.md` §3 and
the deliberately failing CI PR of Days 8–9. — **met in tests; the drill on a live model is Step 3.**

---

### Step 3 — Evaluate it, and admit the golden set does not fit

**The 100-item golden set grades single answers. It cannot grade a task.** Pretending otherwise is
the trap this step exists to name.

**The cheap, defensible instrument first:** the existing set, run through the agent, scored with
the existing `rag.judge --report`. That answers *"does the agent make single-answer quality worse?"*
— which is the question most likely to have an unwelcome answer, and it needs **no new labels**.

**Then, and only if Step 0 and 2 succeeded, a small task set.** Ten to twenty multi-step tasks,
**hand-verified** (`D06` — a test asserts Claude cannot stamp `verified_by`). Ten is not a
benchmark and must never be quoted as one; it is an existence proof with a denominator. `D65`
sized the golden set with Wilson intervals and that arithmetic applies here — at n=10 the band is
about ±0.30, so **report which tasks flipped, never a rate**.

**INSTRUMENT BUILT 2026-09-11; THE RUN IS ON THE LAB** (`logs/HANDOFF.md` ASK 17.4).
`uv run python -m rag.agent --golden` then `--report`. Rows are machine-suffixed and the sweep
**refuses to overwrite another machine's** — that guard exists because Round 15 silently destroyed
the Mac's faithfulness file and it came back out of git (`D83`).

**It reuses rather than reimplements, deliberately.** `answer_in_prompt` is
`score.rank_of_first_hit`, the same function `--refusals` and the prompt sweep use, so the column
is *comparable* with `D72`'s table rather than merely similar to it. The generation cells come from
`judge._sweep_generation`. **`D85` is what happens when one metric grows two implementations**, and
that mistake is not worth making twice in one project.

**For the agent, `answer_in_prompt` means: did a verified answer chunk come back from any
`search_docs` call this run made?** The agent chooses its own retrieval, so that is its equivalent
of "the page reached the prompt". An agent that never searched scores **zero sources** — which is a
measurement, not a gap: an answer with no lookup behind it is `D73`'s defect arriving by a
different route.

**The number to compare against is the LAB's, not the Mac's.** `D83`: the shipped pipeline is
**39/91 = 0.43** on Darwin-arm64 and **38/91 = 0.42** on the 3060. Putting an agent measured on one
box beside a baseline from the other is the error this whole phase inherited a rule about.

**Done when:** the agent's single-answer numbers sit beside Phase 4's in one command, measured on
the lab or in one sitting, and any task-level claim names its n in the same sentence.

---

### Step 3a — the experiment battery, written before any of it is run

**Round 17.4 came back at `2/91 = 0.02` against the lab's own `38/91 = 0.42` baseline.** The
pass/fail table written before that run says a number materially below baseline is *the phase's
finding, and it is a real one — report it, do not tune it away.* **That still stands. But the
headline number is not the finding, and saying it is would be wrong in a way this project has
been wrong four times already this session.**

#### What the run actually says

```
end to end     2/91 = 0.02        fabricated 5      over-refused 0
no tool call   96      one tool 4      two or more 0
```

| of the 96 that called no tool | |
|---|---|
| refused outright | **43** |
| **answered from memory** | **53** |
| retrieved anything | **0** |

**And when it did retrieve, it worked.** Of the three `search_docs` calls, two put a verified
answer chunk in front of the model and produced a correct, sourced answer (`g002`, `g024`).

> **`0.02` is measuring that the agent did not search. It is not measuring that the agent answered
> badly.**

**`end_to_end` requires `answer_in_prompt`, which for the agent requires a `search_docs` call.**
So **53 answers are scored zero by construction**, whether they are right or wrong. Comparing
`0.02` against `0.42` as though it were the same quantity is the apples-to-apples error this phase
inherited a whole rule about. **The honest one-line summary is: the agent answers from memory, and
the metric cannot see those answers at all.**

#### The suspect, named before it is tested

The standalone probe got a usable tool call on **100 of 100 of these same questions** (`D87`), on
this machine, at this temperature. The only difference is the system prompt:

| | |
|---|---|
| probe, **100/100 called a tool** | *"You have two tools. **Call exactly one of them** for the question you are given. **Do not answer from memory.**"* |
| agent, **4/100 called a tool** | *"**You may call tools.** … When you have enough to answer, answer in prose…"* |

That is the `D74` shape exactly — one permissive word against one imperative one, and a 96-point
swing. **Which is a hypothesis, not a conclusion**, and Round 16 is the precedent for what happens
to confident mechanisms here.

#### The battery

Each row states what it distinguishes and what result would mean what, **before it runs**.

| # | experiment | distinguishes | cost |
|---|---|---|---|
| **E1** | system prompt A/B: permissive vs *must call a tool* | prompt versus model capability | ~80 generations |
| **E2** | **structurally** force a tool call on step 1 — the loop rejects prose before any tool ran | what prompting can buy versus what only code can | ~200 |
| **E3** | grade the **53 memory answers** with `rag.judge` for citations and faithfulness | is the agent answering *badly*, or just *unmeasurably*? | 0 new generations |
| **E4** | the two-part failure: `check_api` says NOT FOUND, does a nudge produce the second call? | a **planning** failure versus a **stopping** failure | ~30 |
| **E5** | replicate 17.4 unchanged on the Mac | is `96/100` a property of the system or of one box (`D84`)? | ~200 |
| **E6** | re-run whichever variant wins on the **lab** | `D83` — nothing ships on one machine | lab sitting |

**E3 is the one to run first and it costs nothing new.** The answers are already saved. If the 53
memory answers are ungrounded and uncited, `0.02` is generous and the agent is genuinely worse. If
they are largely correct, then the defect is **retrieval discipline**, not answer quality, and E1/E2
are the fix rather than a rescue.

#### E3 — RUN 2026-09-11, and the answer is the unwelcome one

```
answers produced with NO retrieval        53
  carrying an [n] citation                31       <- every one OUT OF RANGE
  containing code                         42
  code with no source                     41/42
answered an UNANSWERABLE item from memory  5       (g010 g056 g065 g075 g097)
```

**`n_sources` is zero on all 53, so every `[n]` in them points at a passage that was never
fetched.** `g003` cites `[1]` against nothing at all, and so do thirty others.

> **Phase 4's `D73` defect was answers that cite NOTHING. This is answers that cite something that
> does not exist.**

That settles how the rest of the battery is read. **`0.02` was generous.** The agent is not merely
unmeasurable when it skips retrieval — **it is worse than the pipeline it replaces**, and worse in
the one dimension `H` was chosen to improve. `D79` measured a subscript making an uncited block
*look* cited and treated that as serious; this is the same failure without the excuse of a parser.

**So E1 and E2 are no longer about rescuing a number.** Even if a prompt restores tool calls to
100%, the thing that has to be re-measured is whether the citations then point at real retrieved
passages — because this run proves the model will happily write `[1]` with nothing behind it.

#### E1 and E5 — RUN 2026-09-11 on the Mac, one sitting (`D54`), n=20 answerable

```
              no tool   one  two+  in prompt  delivered  bad cites
A_shipped           9    11     0          9          7          3
B_mustcall          2    18     0         13          6          0
```

**The prompt hypothesis is supported, on this machine.** Making the permission an obligation takes
no-tool-call from **9 to 2** and **bad citations from 3 to 0** — because an agent that retrieves has
real sources to point at. That second column is the one E3 said would matter.

**Two things it did NOT move, and they are the more useful half.**

**`delivered` is 7 against 6.** Retrieval discipline did not buy end-to-end answers at n=20. So
*"the agent does not search"* and *"the agent does not answer"* are **two defects, not one**, and
only the first has a prompt-shaped fix.

**`two or more` is ZERO in both arms.** The model never chains tools whatever it is told. **That is
not a prompt effect**, it is the compounding `PHASE-5.md` opened on, and no wording tested reaches
it.

#### E5 fell out of E1, and it is the bigger finding

The same 20 items, the **same shipped prompt**, the same model at temperature 0:

| | no tool call |
|---|---|
| Mac | **9/20** |
| lab | **19/20** |

**Ten of the twenty flip.** `g004`, `g005`, `g007`, `g008`, `g009`, `g011`, `g014`, `g018`, `g019`,
`g021`.

> **The decision to call a tool does not reproduce across machines at all.** Fifty per cent
> disagreement on a binary decision — larger than anything `D83` or `D84` measured.

**One honest limitation of the Mac E1 above:** it ran arm A to completion and then arm B, not
interleaved. One sitting, but not the strongest design — on a box that drifts, a slow drift over
the hour lands unevenly on the two arms. `rag.agent --e1` now **alternates the arms within each
item**, so the lab's run is the better-designed one and the Mac's should be read as the weaker
of the two when they are compared.

**So `96/100` is not a property of the system.** It is the lab's number, and the Mac's is `9/20` on
the same items. And it puts **E1's result back in the same position prompt `H` was in**: a
candidate that looks strong on the Mac, on one machine, with the other machine unmeasured.
`D83`/`D84` already wrote the rule for that, and it applies here without amendment.

#### Round 18 — E1 on the lab, and the decision (`D90`)

| paired, item by item (`D61`) | delivered | bad citations | tool called |
|---|---|---|---|
| **lab** | **6↑ 0↓**, exact McNemar **p = 0.031** | **9 fixed, 0 broken** | 12 gained, 0 lost |
| **Mac** | **0↑ 1↓** (`g008`) | **3 fixed, 0 broken** | — |

**The designed effect reproduces; the side effect does not.** Under the shipped prompt the lab
produced **9 out-of-range citations in 20 items**. The candidate produces **zero on both machines,
with zero regressions on either**. Meanwhile `delivered` is `6↑ 0↓` on the lab and `0↑ 1↓` on the
Mac — and `g008`, the Mac's one regression, sits in the lab's fixed list.

**That is prompt `H`'s shape with the machines swapped**, and `D83`'s rule — believe the designed
effect over the bonus one — applies unchanged.

**Decided: `SYSTEM_MUSTCALL` is the agent's default.** Not the same call as shipping `H`: `H` was
the production answer path with users on the other side; this is unshipped Phase 5 code, and the
only question is which prompt to keep measuring with. Continuing on one that fabricates citations
on nearly half the lab's items would make every later number a measurement of a known defect.

**The pre-written threshold was NOT met and is recorded as not met.** Round 18's table said
*"~19/20 down to ~2/20 → ship"*; the lab gave **7/20**. The outcome fell between two rows of my own
table. Retrofitting the threshold would make every earlier pre-written rule here worthless.

**And the phase's real finding did not move.** Across **80 runs, two machines, two prompts, tools
were chained exactly once.** `PHASE-5.md` opened on the arithmetic of three-plus generations; the
measured answer so far is that **this model does single-tool lookup, not multi-step agency** — a
result about 7B local models, not about a prompt. `E2` (forcing structurally) is the only untried
lever, and it bounds rather than fixes.

#### E2 and E4 — RUN 2026-09-11 on the Mac. One of them changed the phase.

**E2, forcing the first tool call in code rather than asking for it (n=20):**

```
                  no tool   one  two+  forced  in prompt  delivered  bad cites
B_default (D90)         2    18     0       0         13          6          0
C_forced                1    19     0       2         14          7          0
```

**Marginal here, because `SYSTEM_MUSTCALL` had already taken no-tool-call to 2 of 20.** On the lab
the prompt only reached 7 of 20, so forcing has more room there — that is Round 19.2.

**E4 could not run at all the first time, and the null looked real.** Two arms came back
**byte-identical**. The reading is not *"the nudge did nothing"*: across 60 runs on the first 20
answerable golden items, `check_api` was called **zero** times — all 56 calls were `search_docs` —
and the nudge only fires after a `check_api` NOT FOUND. Step 0's probe explains it: only **9** of
the 100 golden questions route to `check_api`, and only `g018` is in the first 20. **The golden set
is how-to shaped because developers ask how-to questions.** Right ruler for Phase 2, wrong one
here.

> **A null from an experiment that did not run looks exactly like a null from one that did.** Two
> *identical* rows are what gave it away; "no significant difference" would not have.

**So E4 got ten questions built for it** — two-part by construction, a symbol that is gone plus
what replaces it, where answering fully requires both tools:

```
            no tool   one  two+   check_api first
plain             0    10     0                 9
nudged            0     3     7                 9
```

**7 chained, 0 un-chained, exact McNemar p = 0.0156** (`D91`).

> **The single-tool ceiling is a STOPPING failure, not a planning one. The model will take the
> second step; it does not know the first one was not the end.**

**And Round 19's own table says, in writing, that I expected the opposite.** The prediction stays
on the page. What moved it was one sentence appended to a tool result *only* after a NOT FOUND —
no system-prompt change, no new tool.

**It is a Mac result at n=10 and it is a screen, not a finding.** `D89` has tool decisions
disagreeing across machines on half the items and `D90` watched E1's direction invert. Round 19
now leads with this.

#### Round 19 — the lab agreed, and one rule got sharper (`D92`)

**E4 reproduced to the item.** Plain chains **0 of 10** on both machines, nudged chains **7 of 10**
on both, paired `7↑ 0↓, p = 0.0156` on both — **and it agrees question by question, 10 of 10.**
The honest denominator is **7 of 9 eligible**: one question went to `search_docs` first on both
boxes, so `check_api` never returned NOT FOUND and the nudge could not fire.

**So the stopping-failure finding holds on two machines.** It is the first thing in this phase to
move the number nothing had moved.

**`D89` needed a distinction, not a retraction:**

| decision | agreement across machines |
|---|---|
| *is this how-to question worth a lookup?* | **10 of 20** |
| *the symbol is gone — is the question also asking what replaces it?* | **10 of 10** |

> **Ambiguous decisions diverge across machines. Unambiguous ones do not.**

**The design consequence is the useful part: remove ambiguity rather than add instruction.** The
nudge works because it turns *"is there more to do?"* into a question with one answer, and
`SYSTEM_MUSTCALL` works because *"you MUST"* has no judgement in it where *"you may"* does.

**And the hundred-item score moved:**

| lab, 100 items | old prompt | `SYSTEM_MUSTCALL` |
|---|---|---|
| end to end | 2/91 = **0.02** | **17/91 = 0.19** |
| no tool call | 96 | **53** |
| two or more | 0 | **0** |
| fabricated | 5 | **3** |

**Nine times the score and still well under the one-shot `0.42`.** And **53 of 100 still call no
tool** under a prompt that orders them to — forcing in code reaches what asking does not (lab n=20:
**8 → 0**). **The full 100 under forcing is the next measurement and is not yet taken on either
machine.**

**Pass/fail, fixed now:**

- **E1 moves `no_tool_call` from ~96 to near zero** → the prompt was the cause; re-run 17.4 with it
  and report both numbers, with the first one kept on the record.
- **E1 barely moves it** → prompting is not the lever; E2 decides whether code can force it, and if
  E2 also fails, **`0.02` is the finding and it ships as one**.
- **E2 forces tool calls but end-to-end stays low** → the model retrieves and then ignores what it
  retrieved, which is a different and more interesting defect than either.
- **E5 disagrees with the lab by more than a few items** → `D84` again, and every number here needs
  its machine before it means anything.

**What will NOT be done: tuning until the number looks good.** The pre-written rule stands, `D69`
and `D70` are the precedent for rejecting a lever with a measurement, and a variant that only wins
on the Mac does not ship (`D83`, `D84`).

## Gate

**Done when the agent completes a task needing 2+ tool calls, and visibly recovers from a tool
failure that was deliberately injected** — the roadmap's bar, unchanged.

**Plus three this repo adds, because the roadmap's bar can be met by a demo:**

1. **The agent does not make single-answer quality worse**, measured against Phase 4's numbers on
   the same machine in the same sitting.
2. **Every number carries its machine** (`D83`), and any Mac number carries its same-sitting
   baseline (`D54`).
3. **Step 0's tool-call rate is written down whichever way it came out.** A phase that can only be
   closed by success is not a measurement.

---

## What this phase does NOT inherit

- **Shipping prompt `H`.** Held on weight of evidence (`D83`, `D84`), and an agent does not reopen
  it. If the citation-only variant ever gets built it is measured on **both** machines from the
  start.
- **The 17 absents** (`D70`) and the **retrieval ceiling**. An agent can call a tool the retriever
  cannot, which is interesting — but it is a new capability, not a fix to recall, and must not be
  reported as one.
- **`0.64`.** Still retrieval's ceiling. Quote **`0.43`** for what a user gets until this phase
  moves it (`D72`).
- **Langfuse.** Phase 6, on demand, and the reason is unchanged: there is nothing to observe yet.
  An agent makes that argument weaker and it is still not this phase.
