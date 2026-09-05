# Phase 4 — Judge the answers, not the search

Part of [`sqlalchemy-upgrade-agent`](../README.md). Follows
[`PHASE-3.md`](PHASE-3.md), which closed retrieval at **`recall@5 = 0.64`**. Spec:
[`ROADMAP.md`](ROADMAP.md) Phase 4. Teaching file: [`../study/16-JUDGE.md`](../study/16-JUDGE.md) (§R8) — read that first;
this file is the measured plan, that one is the sitting.

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

#### Correction 2026-08-30 — the pinning argument above is too strong (`D78`)

**The `D65` analogy imported a conclusion without its cost structure**, and the difference is
what it costs to re-derive the thing when it moves under you:

| | if it changes | cost to restore |
|---|---|---|
| golden set (`D65`) | every row is unpaired | **~25 hours** of `D06` hand-verification |
| vector store (`D31`) | 4 of 19 probe questions moved | a re-index — minutes |
| **judge** | the absolute faithfulness number shifts | **~60 calls** — minutes |

Sized, not asserted: over the saved sweep the answered items are **D 48 / H 62 / I 63**, so one
call per answer is ~60 per variant and ~180 claim-by-claim. Reproduce with
`deliverables/prompt-sweep-phase4.json`. **Rate limits are not the constraint on any free tier**,
which removes the reason most people pick one.

**So the snapshot id is a convenience. Two other properties are the tight ones:**

- **Same judge, both arms, one sitting.** `D54` applied to the judge rather than the generator.
  Judge D on Monday and H on Friday and the comparison is worthless however carefully the model
  was pinned. Free to honour, and it is the actual correctness requirement.
- **Agreement with a human, measured** — Step 5's hand-check of ten. A pinned judge with
  unmeasured agreement is a precise instrument of unknown accuracy, and `g065` is this repo's
  proof that the label no audit can test is exactly where it has been wrong before.

**What that changes in practice:** `rag/faithful.py` records the model on **every row**
(`stamp()`) rather than defending one id forever, and `--models` asks the key what it can
actually reach so the pin is chosen from what exists rather than from memory. A local judge is
in fact *more* pinnable than any API — you hold the weights — and stays the fallback if the
agreement-of-ten comes back poor. `ROADMAP.md`'s "too weak to grade itself" objection is about
**self**-grading; a different, larger model is not that.

#### Correction 2026-09-03 — the pin went dark, and the free tier is 20 a day (`D80`)

Three days after the pin was chosen, two of the paragraph above's premises failed on the same
morning. Both by measurement.

**The pinned id stopped answering.** One call each, same key, same minute:

```
gemini-3.6-flash     FAIL HTTP 503 from gemini-3.6-flash
gemini-3.5-flash     OK   SUPPORTED
gemini-3.7-flash     OK   SUPPORTED
gemini-3.8-flash     OK   SUPPORTED
```

**And the free tier's real ceiling contradicts the sizing above in as many words.** `D78` says
*"rate limits are not the constraint on any free tier"*. The 429 body:

```
quotaId:    GenerateRequestsPerDayPerProjectPerModel-FreeTier
quotaValue: 20
```

**Twenty requests per day, per model. This comparison needs ~110.** So the API judge cannot
finish it today or in any single day — and the tight property `D78` itself names is *same judge,
both arms, **one sitting***. Spreading the run over six days to fit the quota does not honour
that property, it destroys it.

**So the judge is local: `gemma4:e4b` on Ollama, no quota.** `D78` already named this fallback
and gave the reason it is a good one — you hold the weights, so it is *more* pinnable than any
API. It is **not** self-grading: the generator is `qwen2.5-coder:7b`, a different family and a
different size, and `ROADMAP.md`'s objection is to a model marking its own homework. Whether it
is *good enough* is Step 5's number, not a matter of reputation.

### Step 3 — Citation integrity, then faithfulness — both built and measured

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

**Faithfulness has a deterministic half too, and it is built** (`D77`). `ungrounded_calls()`
takes the dotted API calls in an answer's **code** and asks whether each appears in **any of its
own sources**. No judge, no key.

| | answered | with an ungrounded call | rate |
|---|---|---|---|
| **D** shipped | 48 | **2** | 4% |
| **H** | **62** | **0** | **0%** |
| **I** | 63 | 3 | 5% |

**It measures groundedness, not existence.** `op.create_table` is real; if no retrieved source
mentions it, an answer calling it is still unsupported by the pages the system was given. Whether
a symbol exists at all is `tools/audit_golden_fullbar.py`'s job against the real library.
Neither subsumes the other — `g065` fails both.

**The severity collapse a count could not see.** `fabr` is 2 under every wording, so by that
metric nothing improved. On `g065` what actually changed is large:

- **D** — a confident Alembic recipe: `op.create_table`, `sa.Column` (and `op.create_view` on
  the 08-21 run, which does not exist on alembic 1.19.1). **A fabricated procedure.**
- **H** — *"[3] SQLAlchemy supports ALTER TABLE, CREATE VIEW, CREATE TRIGGER… schema migration
  tools like Alembic or SQLAlchemy-Migrate can be used."* **Zero code blocks, one citation, a
  paraphrase of the page it cites.**

Both score as "answered an unanswerable item". **They are not the same failure**, and a count of
fabrications is not a measure of harm.

**It independently confirms the golden note.** The 08-21 spot-check rewrote `g065`'s reason to
*"CREATE VIEW chunks exist but do not teach same-migration CREATE TABLE + VIEW"*. H found exactly
those chunks and repeated exactly that much.

**What it cannot see: `g056`**, which fabricates in prose rather than code. A code-grounding
detector is structurally blind to that. **Prose-level faithfulness needs a judge** — and as of
2026-09-03 it is built and running (`D80`).

#### The prose half, built 2026-09-03 — `rag.faithful --sweep`

**What is sent to the judge, and what deliberately is not.** The prose only: fenced code is
stripped before the claim is built. That is a division of labour rather than a shortcut —
`judge.ungrounded_calls` already grades code deterministically, exactly, with no key (`D77`), and
sending the code here would spend a call to re-answer worse a question a regex answers exactly.
What is left is precisely `D77`'s stated blind spot.

**Three properties, each pinned by a test rather than promised:**

- **It judges SAVED answers and re-retrieves the sources.** Regenerating would cost the evening
  and produce *different* answers (`D54`), turning a scorecard into a new experiment. Retrieval
  is deterministic and prompt-independent, so it runs **once per item** and both arms are judged
  against **identical passages** — two lookups of one query is how a difference between prompts
  becomes a difference between lookups.
- **Refusals, failures and unanswered items never reach the judge.** A decline has nothing to be
  faithful to, and scoring it UNSUPPORTED would make the system look worse the more honest it got
  — `D62`'s trap. A **cited** refusal is still a refusal here (`D76`).
- **`UNPARSED` and `NO_PROSE` are kept out of every rate rather than coerced.** A judge that
  stopped following the format is a fact about the run; a code-only answer is not a pass. Both
  would move the number in the flattering direction.

`--claims <id>` is the deep dive the aggregate points at: one item, one call per sentence, so the
answer is *which sentence* rather than *how many answers*.

#### Measured 2026-09-03 — and the rate and the pairing disagree (`D82`)

110 answers judged by `gemma4:e4b`, one sitting, both arms, identical passages:

```
variant   answers  judged   SUPP  PART  UNSUP  UNPARSED  NO_PROSE  supported
D              48      47     40     2      5         0         1       85%
H              62      61     56     3      2         0         1       92%
```

**Do not quote 85% → 92% as "H is more faithful."** The paired comparison `D61` requires says
otherwise:

```
judged by both arms: 46          (D only: 2; H only: 16)
H supported where D was not : 5   g024 g045 g078 g080 g083
D supported where H is not  : 1   g088
exact McNemar p = 0.2188
```

**5↑ 1↓, p = 0.22** — clears neither half of `D61`'s bar. The rate gap comes from the **16 items
only H answered**, **13 of which are `SUPPORTED`**.

**That is a confirmation of `D74`, and a more useful one than another citation count.** The
standing objection to shipping H is that a prompt making the model more willing buys its extra
answers by talking past the evidence. Measured, it does not: **willingness did not cost
grounding.** Say it that way.

**`g088`, the single regression, read rather than counted.** D `SUPPORTED` — *"Passage [4]
provides a complete code example … detailing all the steps."* H `UNSUPPORTED` — *"The passages do
not contain the specific code example or the full instructional setup provided in the claim."*
H did not contradict its sources; **it supplied more than they contain**, which is the failure a
forthcoming prompt should be expected to have. Once in 46, and it is on the agreement sheet.

**`g016`, where three instruments land on one item.** The `D79` re-score says its stored fields
called it cited `[0,1,2]` when today it cites `[2]` and **uncited code blocks goes 0 → 1**; the
citation check says the code block has no source; the judge says `UNSUPPORTED` — *"None of the
passages state that `row.keys()` is deprecated."* The subscript bug made that block *look* cited,
and the claim was not in the pages either.

**`g065` is `PARTIAL` on both arms and the reasons keep `D77`'s severity split** — D's *"do not
contain the specific code example or the detailed `upgrade`/`downgrade` functions"* against H's
*"outside SQLAlchemy's scope, but they recommend Alembic."* Same verdict, different harm. **A
count of PARTIAL is no more a measure of harm than a count of fabrications was.**

**Every figure here is provisional on section 5.** The judge's agreement with a human is **0 of
10 answered**.

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

**Built 2026-09-03: `uv run python -m rag.faithful --agreement`** renders
`deliverables/JUDGE-AGREEMENT.md` — ten verdicts with the claim the judge read, the five passages
it read them against, and a blank. **Claude renders the sheet and does not fill it in** (`D06`).

**The sample is risk-weighted, not random**, and both halves of that matter:

- every `UNSUPPORTED` and `PARTIAL` goes in first, because a uniform ten from a mostly-`SUPPORTED`
  set measures agreement where it is easiest and says nothing about the verdicts a decision would
  rest on;
- `SUPPORTED` rows fill the rest, because **without them the sheet can only catch the judge
  accusing wrongly, never the judge missing something** — and a miss is exactly the `g065` failure
  mode.

**The rate is read back out of the filled sheet**, not typed into a doc beside it, so the number
in the scorecard is the artifact a human actually wrote in. An unanswered row counts as
unanswered and never as agreement; the blanks are printed next to the rate, because *"9 of 10
agree"* over one filled row is the shape of every flattering statistic this repo has caught.

---

## Gate

**Done when one command scores the full golden set and emits retrieval metrics, faithfulness and
citation accuracy in one report** — and when the judge's own agreement with a human on ten
hand-checked items is a number in that report rather than an assumption.

**The same rule as Phase 3:** a lever tried and dropped with a number beside it counts. A lever
skipped does not.

### The command, built 2026-09-03 (`D81`)

```
uv run python -m rag.judge --report
```

Five sections, and **each states whether it was measured live or read from a file** — a report
that mixes the two and labels neither is how `0.64` came to be quoted as the system's score.
Retrieval is live (cheap: lookups, no generations). Everything about the answers is read from the
300 saved generations, because regenerating them costs the evening *and* returns different
answers (`D54`).

**Its generation figures were checked against the published ones rather than trusted**: D
**39/91 = 0.43**, 19 over-refusals, 2 fabrications; H **47/91 = 0.52**, 10, 2; I **46/91 = 0.51**,
11, 2 — every cell identical to `D72` and `D74`.

**Citations are re-scored with today's rules, not read**, because the saved fields predate `D79`
— and the report names each row where the two disagree. `g016` is one, and the old bug was worse
than a phantom citation: `row[keys[0]]` made an **uncited code block look cited**. `D` yields zero
such rows; only the complying variants do.

**What is still open at the gate:** section 5's agreement rate. The sheet exists, and a human has
not read it. The report prints that fact rather than a number.

---

## What this phase does NOT inherit

- **The 17 absents.** They are `D70`'s recorded ceiling, not Phase 4's backlog. An answer cannot
  be faithful to a page that never reached the prompt.
- **Re-chunking as a recall lever** (`D70`). But a **severed listing pasted into a prompt** is a
  citation-quality defect and does belong here — §R5.3's "at least 11 of 3077" is about what the
  model is handed, which is exactly this phase's subject.
- **`recall@5 = 0.64` as a headline for the system.** Quote **0.43** for what a user gets
  (`D72`), until this phase moves it.
