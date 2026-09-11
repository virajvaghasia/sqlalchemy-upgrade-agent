# Phase 5 — The agent, and the tools it is allowed to be wrong with

Part of [`sqlalchemy-upgrade-agent`](../README.md). Follows
[`PHASE-4.md`](PHASE-4.md), which closed with **end to end `0.43`** against a **`0.64`** retrieval
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

**Done when:** each tool has tests, runs standalone, and `check_api_signature` reproduces the
`g065` verdict — `create_view` absent, `create_table` present — as a `# runnable` block.

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

**Done when:** a deliberately injected tool failure is recovered visibly, and the injected-failure
drill is in the doc — the same shape as the `.dockerignore` break in `study/04-DOCKER.md` §3 and
the deliberately failing CI PR of Days 8–9.

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

**Done when:** the agent's single-answer numbers sit beside Phase 4's in one command, measured on
the lab or in one sitting, and any task-level claim names its n in the same sentence.

---

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
