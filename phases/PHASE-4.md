# Phase 4 — Judge the answers, not the search

Part of [`sqlalchemy-upgrade-agent`](../README.md). Follows
[`PHASE-3.md`](PHASE-3.md), which closed retrieval at **`recall@5 = 0.64`**. Spec:
[`ROADMAP.md`](ROADMAP.md) Phase 4. Teaching file when this ships: `study/16-JUDGE.md` (§R8).

> **Phase 3 ended because retrieval ran out of levers, not because it got good.** Four levers,
> two shipped, two rejected with numbers (`D66`–`D70`). The **17 absents** are a phrasing and
> corpus-ceiling problem and nothing left on the retrieval list reaches them.
>
> **This phase is where the bigger loss already is.** It was measured in Phase 2 and has been
> sitting in the scorecard unaddressed ever since.

---

## The number that justifies the whole phase

Retrieval's score is a **ceiling**, and generation gives part of it back:

| | measured | what it means |
|---|---|---|
| `recall@5` after Phase 3 | **0.64** | the right page reached the prompt this often |
| end to end, right page **and** an answer | **0.43** (39 of 91) | what a user actually gets |
| **the gap** | **21 points** | lost *after* retrieval succeeded |

Measured 2026-08-22 (`D72`). Before Phase 3 the same three rows read **0.49 / 0.35 / ~15**.

**No retrieval metric can see that gap** — every number in `PHASE-3.md` is computed above it.
`D62` is the decision that refused to average the two together, and this is the phase where
that separation pays off: the 15 points have a name, a list of item ids, and an owner.

**Three defects make it up**, and they are not the same problem:

| defect | size | named ids |
|---|---|---|
| **Over-refusal with the answer in the prompt** | **19 of 91** | `g006`, `g008`, `g013`, `g021`, `g044`, `g048`, `g049`, `g050`, `g051`, `g064`, `g084`, `g087`, `g090`, `g095`, `g099`, `g100`, `g103`, `g106`, `g116` |
| **Fabrication on an unanswerable item** | **2 of 9** | `g056`, `g065` |
| **Answered without the verified page in the prompt** | **11** | the open cell — unread, and `D06` says a human reads it |

Phase 1 knew the first row as **two** questions (Q18/Q19). It is nineteen.

---

## The measurement problem that has to be solved first

**`D54`'s determinism claim was narrowed on 2026-08-21 and it constrains every experiment here.**

Same prompt, `TEMPERATURE = 0.0`, `rag/ask.py` unchanged since `b6320c4`, index unchanged — and
**two of seven items flipped between 08-20 and 08-21**: `g029` refused then and answers now,
`g015` the reverse. Within one sitting, five runs were unanimous on every cell.

**Consequence, and it is a hard rule for this phase:** a before/after must re-run its baseline
**in the same sitting as the change**. A two-item drift is most of the effect any prompt fix
would be judged by, so a baseline from yesterday is not a baseline.

**First task of the phase is therefore not a fix.** It is a `--refusals` re-baseline on the lab
PC in one sitting, which is what `logs/HANDOFF.md` **Round 13** already asks for.

---

## Steps

### Step 1 — Re-baseline refusals in one sitting (lab PC) — Round 13

**Why the lab.** ~100 generations. The 3060 runs `qwen2.5-coder:7b` at **62.23 tok/s** against
the M4's **18.4**. On the Mac the first attempt died at session teardown with nothing written,
because the report only prints after all 100 finish.

**Deliverable.** The three-row table above, re-derived, with every cell from one sitting. Any
item that disagrees with 08-21 is `D54` drift and gets named rather than averaged.

#### CLOSED 2026-08-22 — run on the Mac, one sitting, and the result reframes the phase (`D72`)

The lab was not reachable, so this ran here: ~100 generations at the M4's 18.4 tok/s. Slower,
same numbers — `D54`'s constraint is about *one sitting*, not about which box.

| | 2026-08-21 (pre-Phase 3) | 2026-08-22 (post) |
|---|---|---|
| retrieval ceiling, `recall@5` | 0.49 | **0.64** |
| answer reached the prompt | 45/91 | **58/91** |
| **end to end** | **32/91 = 0.35** | **39/91 = 0.43** |
| over-refused **with the page in hand** | **13** | **19** |
| generation's loss | ~15 points | **21 points** |

**Retrieval gained 15 points and the user got 8.** That is the phase justified in one line.

**The over-refusal count went UP while the system got better, and that is arithmetic rather
than a regression.** The cell counts items where the answer **is in the prompt** and the model
refused anyway; improving retrieval makes more items eligible for it. So **the raw count is not
comparable across retrieval changes** — as a rate against the ceiling it is 13/45 = 29% then,
19/58 = 33% now (`D72`).

**The named example.** Phase 3 fixed seven items against the saved baseline. **Two of them,
`g044` and `g050`, are on today's over-refusal list** — retrieval found the page, put it in
front of the model, and the model declined. `PHASE-3.md` scores both as wins, correctly, and
the user got nothing from either.

**Drift, separated from signal.** The list is not 13 plus six: **`g015` left**, **seven
joined**, twelve are common. A one-item exit is the `D54` noise floor. Seven joining — two of
them Phase 3's own fixes — is not.

**Unanswerable is unchanged: 7/9 refused, 2 FABRICATED** (`g056`, `g065`), identical to 08-21.
Retrieval work moved nothing there, exactly as `D70` implies — an item with no answer in the
corpus has no page for retrieval to find.

**And the headline number now prints.** `0.36` and `0.35` were hand-derived in earlier docs by
subtracting one printed figure from another — right both times, reproducible by no command.
`rag.score --refusals` computes end to end, the ceiling, and the gap between them (`D72`).

### Step 2 — The judge, pinned

`ROADMAP.md` says a **strong** judge (Gemini free tier), because the local model is too weak to
grade itself. Two decisions to record before any number is printed:

- **Pin the model and version.** Swapping judges mid-project invalidates every historical row,
  the same way swapping the golden set would (`D65`/`D61`) and the same way swapping the vector
  store would (`D31` — 4 of 19 probe questions returned different top-5).
- **Zero paid API calls** stands. Free tier or it does not ship.

### Step 3 — Citation integrity (built), then faithfulness (needs the judge)

**`D71`: the deterministic half first, and completely.** `rag/judge.py --citations` needs no
model, no key and no free tier. It answers what a script can settle exactly:

- **Out-of-range citations** — `[7]` when five sources were supplied. A source that does not
  exist. `probe.py` structurally cannot see these: its citation set is built as
  `{n for n in range(1, len(hits) + 1) …}`, so it only ever looks for numbers that exist, and an
  answer citing only `[7]` reads there as `uncited` instead.
- **Uncited code blocks** — the machine-visible shadow of `g065`. Nothing here can know
  `op.create_view` is invented; it can see executable-looking code pointing at no source.
- **Coverage** — what fraction of the `k` pages we paid to retrieve the answer actually used.
- **`uncited` / `single_source`** — same definitions as `probe.py`, pinned by a test so the
  Phase 1 deliverable and the Phase 4 report cannot disagree about the same answer.

**Refusals are excluded from every rate.** A declined answer has nothing to cite, and counting
it as `uncited` would make the system look worse the more honest it got — `D62`'s trap again.

**Faithfulness is the half that needs a judge**: is each claim supported by a chunk that was in
the prompt? That is a reading task, so it waits on Step 2's pinned model.

#### Measured 2026-08-22, first full run — and it is worse than Phase 1 recorded (`D73`)

```
# runnable: uv run python -m rag.judge --citations
CITATION INTEGRITY  —  deterministic, no judge model (Phase 4)
  items asked                     100
    refused, nothing to cite       52
    answered                       48   <- every rate below is over these

  cites a source that does not exist     0    0.0%
  no citation at all                    31   64.6%
  cites only one of the sources         16   33.3%
  answers containing code               28   58.3%
    of those, code with no citation     26   92.9%

  mean source coverage                0.07   (fraction of the 5 prompt sources an answer cites)
```

**`rag/ask.py` opens with the words "SOURCES ARE NOT DECORATION". Measured, they mostly are.**
Two answers in three cite nothing, and **93% of the answers containing code** put executable
code on screen with no source attached — which is the machine-visible shape of `g065`.

**Checked four ways before being believed**, because 65% is what a broken detector prints:
`build_prompt` numbers sources `[1]`…`[5]`; SYSTEM says *"cite the source number in brackets,
like [2]"*; `generate()` sends SYSTEM, by the identical path `--refusals` uses; and `g002`'s raw
answer was printed and read — zero `[n]`, plus `` :meth:`_orm.Query.from_self` `` leaked into
user-facing text.

**Zero out-of-range citations.** When it cites, it never invents a source number. The defect is
**omission**, not fabricated provenance, and those want different fixes.

**Phase 1 said `uncited: 3` and was underpowered, not wrong.** That was 3 of 11 *answered* probe
questions = 27%, Wilson **[0.04, 0.51]**, against this run's **[0.52, 0.78]**. Bands miss by a
hair. **Second time here:** three unanswerable items could not measure a fabrication rate on
08-21; eleven answered questions could not measure a citation rate.

**Mechanism open, and instrumented rather than guessed.** Phrasing was the suspect (`D63`), but
the uncited-code split runs **breakages 21% / github 20% / migration_guide 31% / stackoverflow
36%** — the repo's own docs-vocabulary set *above* real GitHub questions. `--citations` now
prints a full per-provenance split and `--save` keeps the rows, so the next ~100-generation run
answers it instead of re-asking it.

**Not a claim that 31 answers are wrong.** An uncited answer can be correct — `g002`'s is. It is
**uncheckable**, which is the property the retrieval apparatus exists to provide.

**`g065` is the worked example and it is already measured.** The answer called
**`op.create_view`** and **`op.drop_view`**; `hasattr(Operations, "create_view")` is **False** on
alembic 1.19.1, while `create_table` in the same script is real. **Two invented calls beside two
working ones, and no citation on the code block.** A faithfulness metric that does not catch
that one is not measuring anything.

### Step 4 — Fix the two defects with the prompt (`D74`) — screened, full run pending

**Both defects are generation's, so the prompt is the first lever, and it is free to try.**
`rag/compare_prompts.py --golden` runs the whole golden set through several wordings **in one
sitting** (`D54`) and scores *both* defects off the same answers — one generation per
(item, variant), because refusal and citation are properties of the same text.

**Screened on 20 items first**, deliberately, so a night of generation was not spent confirming
a no-op:

| | end/end | over-refused | uncited | code with no source |
|---|---|---|---|---|
| **D** shipped | 6/18 | 3 | **5/7** | 4/4 |
| **E** system msg: citation *mandatory* | 6/18 | 3 | **5/7** | 3/4 |
| **F** system msg: "sources are search results" | 7/18 | 2 | 6/8 | 5/5 |
| **H** *D's wording*, moved to the **user turn** | **8/18** | **1** | **1/13** | 2/6 |
| **I** F + H | 8/18 | 1 | 3/12 | 4/6 |

**`E` is a null result and it is the informative one.** It says *"an answer with no bracketed
number in it is not acceptable"* and returns cells identical to D's — on `g002`, an answer
near word-for-word D's with zero citations. **The model is not defying the instruction; it is
not attending to it.** By the time generation starts, the system message is thousands of tokens
back, behind five documentation chunks.

**`H` changes no wording whatsoever** — D's system prompt untouched, the citation rule on the
last line of the *user* message, immediately before the `ANSWER:` cue. Uncited: **5 of 7 → 1 of
13**.

**The denominators are the finding.** D answered 7 of 18; H answered **13**. Asking for
citations made the model *more willing to answer* — over-refusals 3 → 1. H was aimed at `D73`
and moved `D72` too. That was not the hypothesis.

**Same shape as `D54`:** prompt D beat B by changing the mechanism, not the volume. E is the
"say it louder" branch and it does nothing. **Position is a lever; emphasis is not.**

**The full 100-item run, 2026-08-23** (corrected for `D76` — see below):

| | end to end | over-refused | uncited | code with no source | fabricated |
|---|---|---|---|---|---|
| **D** shipped | 39/91 = **0.43** | 19 | 31/46 = **67%** | 25/26 = 96% | 2 |
| **H** | **47/91 = 0.52** | **10** | **6/60 = 10%** | 19/36 = 53% | 2 |
| **I** | 46/91 = 0.51 | 11 | 10/61 = 16% | 23/35 = 66% | 2 |

**H: 9 fixed, 0 broken, exact McNemar p = 0.0039** — `g008`, `g021`, `g049`, `g050`, `g064`,
`g095`, `g099`, `g103`, `g106`. `D61`'s bar for a Phase 3 move was ~6 clean fixes with no
regressions; one relocated sentence clears it.

**End to end 0.43 → 0.52 is bigger than everything Phase 3's retrieval work bought** (0.35 →
0.43).

**What it does not fix, stated rather than buried.** Fabrications stay at **2** under every
wording — `g056` and `g065` are untouched by position, emphasis or premise, so the prompt is not
the lever there. And **53% of H's code blocks still cite nothing**: much better, not solved.

**`I` is `H` plus F's premise and is worse on every column** — a second instruction dilutes the
first.

#### The result was wrong the first time, and the mechanism is worth knowing (`D76`)

The first read said **12 fixed, p = 0.000, end to end 0.55**. Spot-checking one raw answer —
which the measurement rule requires — gave this for `g006`:

```
[2] The sources do not answer this.
```

**A refusal wearing a citation.** `ask.refused()` is a **prefix** test, so `"[2] The sources…"`
does not match and was scored as an *answer*. H's whole content is *"cite before each
statement"* — the model complied, including in front of its own refusal. **The variant under
test reshaped the output in exactly the way that defeated the detector reading it**, and `D`
shows zero such cases because `D` barely cites: the bug is invisible until the thing being
measured starts working.

Six of H's answers were cited refusals; three sat in the "fixed" column. Fixed in `ask.refused`
(leading `[n]` stripped, anchor still at the start, so it does not become a substring search).
**No recorded number moves** — `D` produced zero cited refusals, so `D72`/`D73` stand as
published. Re-scoring cost nothing because `D75` had saved the answers.

**Nothing ships on this. Which prompt ships is Viraj's call** — the last time that was assumed
rather than asked it was the wrong call (2026-08-17). `ask.SYSTEM` and `build_prompt` are
unchanged; `H` lives in `compare_prompts.py` as a measured candidate.

### Step 5 — Know the judge's ceiling

LLM judges agree with humans ~85–92% of the time. **Hand-check ten judgments and report the
agreement rate.** Precedent exists: the golden-set signature closed on a risk-weighted
spot-check of ten (§H CLOSED, 2026-08-21), and `g065` is why that sample was worth taking — its
`answerable: false` reason was measurably wrong and no audit could see it.

---

## Gate

**Done when one command scores the full golden set and emits retrieval metrics, faithfulness and
citation accuracy in one report** — and when the judge's own agreement with a human on ten
hand-checked items is a number in that report rather than an assumption.

**The same rule as Phase 3:** a lever tried and dropped with a number beside it counts. A lever
skipped does not.

---

## What this phase does NOT inherit

- **The 17 absents.** They are `D70`'s recorded ceiling, not Phase 4's backlog. An answer cannot
  be faithful to a page that never reached the prompt.
- **Re-chunking as a recall lever** (`D70`). But a **severed listing pasted into a prompt** is a
  citation-quality defect and does belong here — §R5.3's "at least 11 of 3077" is about what the
  model is handed, which is exactly this phase's subject.
- **`recall@5 = 0.64` as a headline for the system.** Quote **0.43** for what a user gets
  (`D72`), until this phase moves it.
