# Judge — study notes

Part of [`sqlalchemy-upgrade-agent`](../README.md). **§R8**, after
[`15-IMPROVE.md`](15-IMPROVE.md) §R7. Plan: [`../phases/PHASE-4.md`](../phases/PHASE-4.md).
Decisions: **`D71`–`D82`**.

> **§R7 was search** — which five pages land on the desk. **This file is the writing.** The
> model looks at those pages and either answers, refuses, cites, or invents. Search metrics
> stop at “page arrived.” Users care about what comes back.

---

## If you are lost — one picture

**“Desk” = the five pages the model is allowed to read for this one question.**

Search is a library. The model does not read all 3284 chunks. For each question it only gets
**five** short documentation excerpts pasted into the prompt (`DEFAULT_K = 5`). Those five are
the **desk**. A “desk page” is one of those excerpts — not a special file on disk.

```
  Library (corpus)     →  search picks 5  →  desk  →  model writes answer
  3284 chunks                ↑
                        "desk pages"
```

Same idea as §R7’s desk seats. Here we care what the model does *after* those five arrived.

```
  Search finds the right page     0.64     ← that page was among the five on the desk
  Model actually answers          0.43     ← Phase 4 headline. Quote THIS.
  ─────────────────────────────   ────
  Lost after search already won   0.21
```

Same **91** answerable questions. Most of the gap: the right page was already on the desk, and
the model still said *"The sources do not answer this."*

**Say `0.43`.** Say `0.64` only with the word **retrieval** in the same breath.

---

## Where to start — Phase 4 is five tracks, not one “judge”

**Do not treat this file as one chapter you must finish before anything else.** Phase 4 is five
separate report cards plus one ship decision. Each track has its own question, its own tool,
and its own “done.” Mixing them is how people invent a single “quality %” that hides a broken
product.

**Start reading order (first sitting):**

1. This section (the tracks table).
2. **Track A** → §R8.1 (end to end) — why Phase 4 exists at all.
3. **Track B** → §R8.2 (citations) — what “SOURCES ARE NOT DECORATION” actually failed.
4. **Track F** → §R8.3 / §R8.3a (prompt H) — the ship call.
5. Then **C → D → E** only when you need that column.

**What “the judge” usually means in chat:** Track **E** only — the prose LLM that grades
sentences. Tracks A–D need **no** second model. If someone says “start the judge,” ask which
track; most of the time they mean E, and E is the last human work, not the first.

### The five tracks (keep the columns separate)

| Track | Plain question | Section | Tool / file | Needs a second LLM? | Status |
|---|---|---|---|---|---|
| **A. End to end** | Right page on desk **and** model answered? | §R8.1 | `rag.score --refusals`, `rag.judge --report` | No | Measured — **0.43** under D (`D72`) |
| **B. Citations** | Can you open a `[n]` and check the claim? | §R8.2 | `rag.judge --citations` | No | Measured — **65%** of D answers cite nothing (`D73`) |
| **C. Groundedness (code)** | Do API names in **code** appear on the desk pages? | §R8.5 | `ungrounded_calls()` in `rag/judge.py` | No | Measured — D 2 ungrounded / H 0 (`D77`) |
| **D. Open cell** | Golden page **missed** the desk — is the answer still right on real 2.0.51? | §R8.5a | `deliverables/OPEN-CELL-REVIEW.md` | No (you read it) | **Done** — 35/35 marked |
| **E. Prose faithfulness** | Does this **sentence** match the passages? | §R8.6–§R8.7 | `rag.faithful --sweep --local`, `JUDGE-AGREEMENT.md` | Yes — local `gemma4:e4b` | Measured (`D82`), **provisional** until you mark the ten |

**Plus Track F — ship H or keep D** (not a metric). Recommendation is H; production prompt is
still D until you say so. Evidence: end to end **0.43 → 0.52**, uncited **67% → 10%**, open-cell
H-only extras **3 CORRECT / 4 PARTIAL / 0 WRONG**. See §R8.3a.

```
  Phase 3 closed here ─────────────────────────────┐
                                                     ▼
  A  end to end     "user got an answer?"
  B  citations      "I can verify which page?"
  C  code grounding "invented API in a code block?"
  D  open cell      "answered without the golden page — still correct?"
  E  prose judge    "does this sentence match the passages?"
  F  ship H?        your call — numbers ready
```

### Track A — End to end (detailed)

**Picture.** Search puts five pages on the desk. One of them is the golden answer. The model
still writes: *"The sources do not answer this."* Search scored a hit. The user got nothing.

```
  Right page on desk + model writes an answer  →  counts toward 0.43
  Right page on desk + model refuses           →  over-refusal (Phase 4's main defect)
  Right page never arrived                     →  retrieval miss (Phase 3; already closed)
```

**Named example.** Phase 3 fixed `g044` and `g050` into the top 5. Same sitting, both refused
with the page in hand. Retrieval’s win; generation’s loss.

**What it is not.** It is not “accuracy.” An answered item can still be wrong, uncited, or
ungrounded. End to end only asks: *did the user get text instead of a decline, with the right
page present?*

**Command.** `uv run python -m rag.judge --report` (generation section) or
`uv run python -m rag.score --refusals`.

### Track B — Citations (detailed)

**Picture.** A good RAG answer looks like: *“…was removed in 2.0 [3].”* You open source **[3]**
and check. Under shipped prompt D, about **two of three** answers have **no** `[n]` at all —
correct or not, you cannot tell from the product.

**Named example.** `g002` answered `from_self` with zero citations and leaked Sphinx markup
(`` :meth:`_orm.Query.from_self` ``) into user-facing text.

**What it is not.** Citation ≠ correctness. An answer can cite `[2]` and still be wrong about
what `[2]` says. That is Track E. Citation only asks: *did it point at a real desk page?*

**Command.** `uv run python -m rag.judge --citations`.

### Track C — Groundedness / code (detailed)

**Picture.** Look only at **code blocks** in the answer. Pull every dotted call
(`op.create_view`, `session.scalars`). Ask: does that string appear **anywhere** on the five
desk pages? If not → ungrounded. No second AI. Exact string match.

```
  Answer code:   op.create_view(...)
  Desk pages:    … no "create_view" …
  → ungrounded   (whether or not Alembic has that method in real life)
```

**Named example.** `g065` under D invents an Alembic recipe. Under H it paraphrases the real
CREATE VIEW FAQ page with **no code block**. Same “answered an unanswerable” count; different
harm.

**What it is not.** It is not “does this API exist in SQLAlchemy?” Existence is
`audit_golden_fullbar.py` on real 2.0.51. Grounding only asks: *was it in the pages we
retrieved?* And it is **blind to prose lies** — `g056` invents in sentences, not code. That
hole is why Track E exists.

### Track D — Open cell (detailed)

**Picture.** The golden set named chunk `c01588` as the answer. Search did **not** put
`c01588` on the desk. The model answered anyway. The scorer cannot say if that answer is good
— it only knows the golden page was missing. **You** read the answer against real 2.0.51.

```
  Golden chunk     = answer key for grading (model does NOT see it when absent)
  Five desk pages  = what the model actually read
  Open-cell review = human: is this answer still correct?
```

**Named example.** `g074` — golden chunks `c00711`/`c01010` absent; model still produced the
official `SomethingMixin` + `column_property` pattern. Marked **CORRECT**, still a **retrieval
miss**.

**Ship-gate slice.** The seven answers **only H** produced (D refused them) decide whether H’s
extra willingness is safe: `g016`, `g028`, `g036`, `g039`, `g040`, `g058`, `g085` →
**3 CORRECT / 4 PARTIAL / 0 WRONG**. Shared open cells (`g014`, `g060`, …) do not prefer one
prompt.

**File.** [`../deliverables/OPEN-CELL-REVIEW.md`](../deliverables/OPEN-CELL-REVIEW.md) — complete.

### Track E — Prose faithfulness / “the judge” (detailed)

**Picture.** Take one sentence from the answer. Take the five desk pages. Ask a **second**
model: do those pages say this?

```
  SUPPORTED     passages say it (or it follows from them)
  PARTIAL       some of it is there, some is not
  UNSUPPORTED   passages do not say it — even if it is true elsewhere
```

**Say what this is not.** `UNSUPPORTED` ≠ false. It means *not in the pages we gave it*. A
correct sentence from training memory with no support on the desk is `UNSUPPORTED` here — and
that is the point of RAG grading.

**Why local.** Hosted free tier is **20 calls/day/model**; a D+H sweep needs ~110. Judge is
`gemma4:e4b` on Ollama — different family from the generator (`qwen2.5-coder:7b`), so nothing
self-grades (`D80`).

**Your remaining job on this track.** Mark
[`../deliverables/JUDGE-AGREEMENT.md`](../deliverables/JUDGE-AGREEMENT.md) (ten items). Until
then every faithfulness % is provisional. Command to regenerate the sheet:
`uv run python -m rag.faithful --agreement`.

### Track F — Ship H or keep D (detailed)

Not a report card — a product decision. Prompt **H** moves the citation rule into the **user
turn** next to `ANSWER:` (same words as D; different place). Measured: end to end **0.52**,
uncited **10%**, McNemar **9↑ 0↓**, p = 0.0039. Production `ask.SYSTEM` is still **D** until
you change it. Full argument: §R8.3a.

---

## Easy picture — four different report cards (keep them separate)

Remember the desk from §R7: search puts **five documentation pages** in front of the model.
Then the model writes. Phase 4 is only about that writing. It asks **separate questions**.
Each gets its own score. Do **not** blend them into one “the system is X% good” number.

**1. Did search put the right page on the desk?**

```
  Question → search → five pages on the desk
                         ↑
                    was the verified answer among them?
```

That is **retrieval**. Phase 3 already measured it: **0.64**. This file does not re-fight that.
(Not one of the five Phase 4 tracks — it is the ceiling Tracks A–E sit under.)

**2. When the right page *was* on the desk, did the model still answer?** → **Track A**

```
  Right page on desk + model writes an answer  →  good for the user
  Right page on desk + model says "sources don't answer"  →  search won, user got nothing
```

That combo (page arrived **and** model answered) is **end to end**: **0.43**.
Quote **0.43** as what the system does. Quote **0.64** only as “search’s ceiling.”

**3. If it answered, can you open a page and check the claim?** → **Track B**

A good answer looks like: *“…was removed in 2.0 [3].”* — you open source **[3]** and verify.
A bad-for-RAG answer can be *correct* but have **no `[1]`/`[2]`/…** at all — you just have to trust it.

That is **citations**. Under the shipped prompt, about **two thirds** of answers cite nothing.

**4. If it pasted code, do those API names appear on the desk pages?** → **Track C**

```
  Answer shows:  op.create_view(...)
  Desk pages:    no "create_view" anywhere
  → the code is not backed by what we retrieved
```

That is **grounding**. A small script checks it — no second AI judge required.

Tracks **D** (open cell) and **E** (prose judge) are the two that need a human eye; they are
detailed in the tracks table above and in §R8.5a / §R8.6.

---

**Why you must not average these into one score**

Suppose the model always refuses. Then:
- citations look “perfect” (there is nothing to cite),
- but every user gets a useless decline.

One blended “quality” number would go **up** while the product got worse. So we keep separate
columns, the same way we never blend “did search find it?” with “did the model answer?”

---

**If someone asks in an interview — one sentence each**

| They ask | You say |
|---|---|
| What’s your score? | **0.43** end to end. **0.64** is only “did search find the page.” |
| Why did refusals go *up* after better search? | More questions now *have* the page in the prompt, so more can refuse *with it there*. Look at the **percentage**, not the raw count. |
| What fixed citations? | Same instruction, moved to sit **right before** the answer — not shouted louder at the top. |
| Did you fix hallucinations? | Still **2** fabrications on unanswerable items; under prompt H the dangerous *code recipes* got milder. |
| What is “the judge”? | Five tracks. The LLM judge is only **prose faithfulness** (Track E). Citations and code grounding are scripts with no model. |
| What’s left in Phase 4? | Ship H (your call), and mark the ten-item agreement sheet so faithfulness stops being provisional. |

---

## §R8 — what Phase 4 measured

Each subsection below is one track from **Where to start** above. Read the track table first
if you are lost; these sections are the measured story behind each column.

### R8.1 End to end (`D72`) — Track A: did the user get an answer?

**Plain job.** A “win” needs **both**:

1. the verified answer page was among the five on the desk, **and**
2. the model did **not** refuse.

Search alone can only guarantee (1). Users need (1) **and** (2).

```
  Desk has the right page?     Model answers?
       YES ──────────────────── YES  →  count as end-to-end win
       YES ──────────────────── NO   →  over-refusal (search won, user got nothing)
       NO  ──────────────────── *    →  search miss (Phase 3 / absents)
```

**The arithmetic (91 answerable):**

```
  58  page reached the prompt          ← search's ceiling → 58/91 ≈ 0.64
  19  of those, model still refused    ← thrown away
  ────
  39  answered with the page in hand   =  39/91 = 0.43
```

**Where the numbers come from — do not invent them.** Retrieval ceiling is “answer chunk in
the five pages” (same idea as `recall@5`, but scored at the generation k). End to end subtracts
only the refusals that happened **with that page present**. Refusals where the page never
arrived are honest retrieval misses — they do not belong in the “over-refusal” cell.

**Command — do not hand-subtract in a spreadsheet:**

```
uv run python -m rag.score --refusals
uv run python -m rag.judge --report   # generation section reprints the same cells
```

**Weird fact that is NOT a bug.** After Phase 3 improved search, “over-refusals with page in
hand” went **13 → 19**.

Read the cell name again: *refused **while the answer was already in the prompt***. Better
search puts the right page in front of the model **more often** → more questions become
*eligible* for that cell. A question whose page never arrived cannot “over-refuse”; it is just
a miss.

```
  before Phase 3   13 of 45 eligible  = 29%
  after  Phase 3   19 of 58 eligible  = 33%
```

So: **never compare the raw count across a retrieval change.** Compare the rate.

**Named example.** Phase 3’s paired baseline fixed seven items. Two of them — **`g044`** and
**`g050`** — sit on today’s over-refusal list. Search found the page (§R7 correctly calls that a
win). The model declined. The user got nothing from either.

**Side by side — what each metric sees on `g050`:**

| Metric | Sees |
|---|---|
| `recall@5` | Hit — golden chunk in top 5 |
| End to end | Miss — model refused |
| Citations | Nothing to score (no answer text) |

**What it is not.**

- Not “accuracy.” An answered item can still be wrong, uncited, or ungrounded.
- Not “generation got worse after Phase 3.” The ceiling moved; more of the old generation
  defect became visible.
- Not something a reranker can fix. The page is already on the desk.

**Say this:** “End to end is 0.43. Retrieval is 0.64. The 21-point gap is generation refusing
with the right page already in the prompt.”

**Do not say:** “My RAG is 64% accurate.”

---

### R8.2 Citations (`D73`) — Track B: can someone verify the answer?

**Plain job.** The product promise of RAG: *here are the pages, and here is which one I used.*
Without `[2]`-style markers, a correct answer and a lucky guess look the same to a reader.

`rag/ask.py` already *asks* for citations (`SOURCES ARE NOT DECORATION`). Measured on the **48**
questions that got an answer under the shipped prompt:

```
  cite nothing at all                 31   65%
  cite only one of the five pages     16   33%
  write code                          28
    …and that code has no citation    26   93% of those
  invent a fake source number [7]      0    0%
```

**Two answers in three cannot be checked.** Not always *wrong* — *unverifiable*.

**How the checker works (no model).** `rag/judge.py` looks for `[n]` markers that are real
citations — not Python subscripts like `row[0]`. It then asks:

- Is `n` between 1 and the number of desk pages? (out of range = invented source)
- Does a code fence have a citation nearby? (uncited code)
- How many of the five pages got cited at least once? (coverage)

**Side by side — `g002`:**

```
  WHAT SHIPPED (correct, blind)              WHAT WOULD BE CHECKABLE
  ─────────────────────────────              ───────────────────────
  The :meth:`_orm.Query.from_self`           Query.from_self was removed [3].
  method has been removed…                   Use aliased(…) instead [3].
  (zero [n]; Sphinx junk in the face)
```

With `[3]` you open source 3 and verify in seconds. That *is* the RAG pitch. It was not
happening.

**Omission ≠ invention.**

| defect | what happened | fix shape |
|---|---|---|
| **Omission** (the real one) | No `[n]` at all | Get the model to cite |
| **Invention** | Cite `[7]` when only `[1]`–`[5]` exist | We measured **0** of these |

**Why Phase 1’s `uncited: 3` did not settle this.** That was 3 of **11** answered probe
questions (~27%). Eleven questions cannot pin a rate; **48** can. Same trap as “3 unanswerable
items cannot measure fabrication.”

**What it is not.**

- A claim the answers are mostly false. Many are right *and* unchecked.
- The same as grounding (Track C). Citing `[2]` does not prove the claim matches `[2]`.
- Fixed by retrieval. The pages are already numbered `[1]`…`[5]` in the prompt.

**Command:** `uv run python -m rag.judge --citations`

**Say this:** “Under the shipped prompt, 65% of answers cite nothing. The model never invents
a fake source number — the defect is omission.”

**Do not say:** “Citations prove the answer is correct.”

---

### R8.3 Prompt lab (`D74`) — Track F setup: *where* the rule sits beats *how loud* it is

**Plain job.** Refusal and citation failures are the **model’s** habits, not search’s. Cheapest
lever: change the prompt. Free. No re-embed.

**How the lab ran (so the numbers are comparable).** One sitting (`D54`): same retrieval for
every variant (prompt cannot change search), one generation per (item, variant), score refusal
and citation off the **same** text. Answers saved (`D75`) so a detector bug can be fixed without
regenerating 300 calls.

**Trap: shout louder in SYSTEM (variant E).** Same cite rule, written as hard as English allows,
still in the system message. On `g002`: still **zero** citations. Whole table unchanged.

**Why shouting fails.** The rule is buried under five long doc pages before the model writes:

```
  ┌─ SYSTEM: "cite like [2]…" ─┐   ← rule lives way back here
  │  SOURCE 1  (~700 tokens)   │
  │  SOURCE 2                  │
  │  SOURCE 3                  │
  │  SOURCE 4                  │
  │  SOURCE 5                  │
  │  QUESTION                  │
  └─ ANSWER: ──────────────────┘   ← model starts writing; rule is forgotten
```

**What worked (variant H): same words, new seat.** Put the rule as the **last line before
ANSWER** — right next to where writing starts. No new wording. Only position.

```
  QUESTION
  Before answering: cite like [2] after each statement…
  ANSWER:                         ← rule is right here
```

| | end to end | over-refused | uncited |
|---|---|---|---|
| **D** (ships today) | 39/91 = **0.43** | 19 | **67%** |
| **E** louder in SYSTEM | same as D | | |
| **H** same words, user turn | **47/91 = 0.52** | **10** | **10%** |

**9↑ 0↓**, McNemar p = **0.0039**.

Moving one sentence bought **more** end-to-end lift than all of Phase 3 search (0.35 → 0.43).
H targeted citations; over-refusals also fell **19 → 10**. No invented mechanism — say “we don’t
know why willingness rose” rather than fake a story.

**What it is not.**

- Not shipped — `ask.SYSTEM` is still D; H lives in `rag/compare_prompts.py` until you decide.
- Not “we improved the prompt” in the vague sense — **position** is the lever; **volume** was
  measured and did nothing.
- Not a new model or a new retriever.

---

### R8.3a Which prompt should we pick? (Track F)

**Recommendation: pick H as the next production candidate.** It is the only variant with a
full 100-item result that improves the two problems this phase is trying to improve, while
introducing **zero paired regressions**:

```
  D = today's production prompt
  H = same system prompt as D
      + the same citation reminder in the user message,
        immediately before ANSWER:
```

H is not a new model and not a new retrieval method. It changes **where one instruction is
written**. The instruction is farther away in the system message; H repeats it beside the
place where the model is about to write.

**The choices, in plain language:**

| choice | what it changes | what we learned | pick? |
|---|---|---|---|
| **D** | current shipped prompt | baseline: end to end **0.43**, uncited **67%** | keep only as control |
| **E** | shouts “citations are mandatory” in SYSTEM | same result as D; louder was not better | **No** |
| **F** | tells the model search results are relevant | only screened on 20; not the clean full-run winner | not first |
| **H** | repeats D’s citation rule immediately before `ANSWER:` | **0.52**, uncited **10%**, **9↑ 0↓** | **Recommended** |
| **I** | H plus F’s extra relevance instruction | **0.51**, uncited **16%**; worse than H everywhere | **No** |

**Why H beats I.** I sounds like it gives the model more help: “these pages are relevant,
answer from them.” But adding that second instruction diluted the first. H is simpler and
measured better. More instructions are not automatically more control.

**What H fixes:**

- end to end: **0.43 → 0.52**
- over-refusals with the page already present: **19 → 10**
- answers with no citation: **67% → 10%**
- paired comparison: **9 fixed, 0 broken**, exact McNemar **p = 0.0039**
- open-cell H-only extras (answers D refused): **3 CORRECT / 4 PARTIAL / 0 WRONG** — did not
  invent harmful wrong answers when it was more willing (§R8.5a)

**What H does not fix:**

- fabrications remain **2 of 9** (`g056`, `g065`)
- **53%** of H's code-containing answers still have no source beside the code
- prose faithfulness on the **paired** set is not a win (5↑ 1↓, p = 0.22) — the claim is
  “extra answers hold up,” not “H is more faithful” (`D82`, §R8.6)
- the agreement sheet for the prose judge is still blank (§R8.7)

So the recommendation is not “H solves the system.” It is: **H is the best measured prompt
candidate, and its remaining failures are visible.**

**The exact decision to make.** If the goal is to improve what users receive now, choose H.
If the goal is to preserve the current production behaviour until a human reviews the raw
answers, keep D temporarily. Either is defensible; silently changing D is not.

**Say this:**

> “I recommend H. It keeps the shipped system prompt and moves the citation reminder into the
> user turn immediately before the answer. On the 100-item run it improved end to end from
> 0.43 to 0.52, reduced uncited answers from 67% to 10%, fixed nine paired items with no
> regressions, and still leaves fabrication and the human agreement sheet open.”

**Do not say this:**

- “H fixed hallucinations.” Fabrications stayed at **2**.
- “H is more faithful.” Unpaired rates look better; the paired test does not clear the bar.
- “H is proven correct forever.” The result is one measured sitting; `D54` says generation can
  drift between days.
- “E failed because the model ignores instructions.” The measured claim is narrower: E's
  stronger system wording produced no improvement; we do not know the model's internal reason.
- “I is safer because it has more instructions.” It measured worse than H.
- “H is shipped.” It remains in `compare_prompts.py`; `ask.SYSTEM` is still D until you decide.

---

### R8.4 Detector bug (`D76`) — a refusal wearing a `[2]` badge

**Plain job.** When you change the prompt, re-check that your *scorer* still means what you
think. H taught the model to put `[n]` everywhere — including in front of a refusal.

**What went wrong, step by step.**

1. First scoreboard for H: **12↑**, end to end **0.55** — looked even better than the true
   result.
2. Spot-check of raw `g006`:

```
[2] The sources do not answer this.
```

3. That is a **decline**, not an answer. The detector `ask.refused()` asked: does the text
   **start with** `"The sources do not answer"`?
4. `"[2] The sources…"` does **not** → counted as answered.
5. **The fix under test broke the meter** — H’s whole content is “cite before each statement,”
   so the model complied *in front of* its own refusal.

```
  first (wrong)   12 fixed,  end to end 0.55
  true            9 fixed,   end to end 0.52   ← still clears the bar; now honest
```

**Fix:** strip leading `[n]` markers, *then* test the start. Still a **prefix** test — not a
substring search.

**Why not “search for the phrase anywhere”?** Prompt D deliberately writes answers like *“here
is what the sources cover, and here is what they do not.”* That is an **answer**. A substring
match would score it as a refusal and inflate the flattering number.

**Why D’s published numbers did not need rewriting.** Shipped prompt D produced **zero** cited
refusals — the bug is invisible until the arm under test starts citing. Same class as `D79`
(subscripts looking like citations) and the `--report` re-score of `g016`.

Saved full answers (`D75`) made the correction seconds, not another 300 generations.

**What it is not.** “H was fake.” Corrected H still wins; the first table was just wrong.

**Say this:** “When I change the prompt, I re-check the detector on the new shape of answers —
H started citing refusals, and a prefix test missed them until we strip leading `[n]`.”

**Do not say:** “The first H score was fine.”

---

### R8.5 Groundedness (`D77`) — Track C: did the code invent APIs?

**Two different “is this lying?” questions:**

| | citations (`D73` / Track B) | grounding (`D77` / Track C) |
|---|---|---|
| Asks | Can I find which page you used? | Are the **API calls in your code** on those pages? |
| Needs | `[n]` markers | String match into the five desk pages |
| Needs a big judge model? | No | No |

**How it works, in order.**

1. Find fenced code blocks in the answer.
2. Pull dotted call names (`op.create_view`, `session.scalars`, …).
3. Drop local variables and names that only appear in the **question** (those are not claims
   about the docs).
4. For each remaining name: does it appear in **any** of the five desk pages?
5. If not → ungrounded.

```
  Answer code:   op.create_view(...)
  Desk pages:    … no "create_view" anywhere …
  → ungrounded   (unsupported by what we retrieved — whether or not Alembic has it)
```

| | answered | with an ungrounded call |
|---|---|---|
| **D** | 48 | **2** (4%) |
| **H** | **62** | **0** (0%) |

**Fabrication count stayed 2 of 9** under every prompt tried. Harm did not. Named example
**`g065`** (corpus cannot teach same-migration CREATE TABLE + VIEW):

| D (shipped) | H |
|---|---|
| Full recipe: `op.create_table`, invented view helpers — **none of that text on the desk** | Cites the real page, paraphrases, **no code block** |

Both score as “answered an unanswerable.” One is a procedure a developer might run. One stops.

> A fabrication **count** is not a measure of **harm**.

**Blind spots — say them out loud:**

- **`g056`** invents in **prose**, not code → this detector cannot see it. That hole is Track E.
- Grounding ≠ “does this symbol exist in Alembic?” That is `audit_golden_fullbar.py` against
  the real library. Grounding only asks: *was it in the pages we retrieved?*
- `op.create_table` can be **real** and still ungrounded if no desk page mentions it.

**What it is not.** “I fixed hallucination.” Count unchanged; severity under H dropped.

**Say this:** “Code grounding is a string match into the retrieved pages — no judge model. H
had zero ungrounded API calls in 62 answers; D had two in 48. Prose lies need a separate
reader.”

**Do not say:** “Grounding proved the answers are true.”

---

### R8.5a The open cell — Track D: the golden page is not on the desk

**Plain job.** Sometimes the model answers even though the golden answer chunk never reached
the five desk pages. Retrieval metrics call that a miss. The answer might still be correct on
real SQLAlchemy 2.0.51. **Only a human (or a careful live test) can say.** Claude may draft
a first pass; **you** stamp the verdict (`D06`).

This is the part that is easy to mix up:

| Thing | What it does | Does the model see it? |
|---|---|---|
| **Golden answer chunk** | Reference page used to judge whether the answer is right | **No**, when it is absent from the retrieved prompt |
| **Five retrieved chunks** | The pages actually handed to the model | **Yes** |
| **Open-cell review** | Human checks whether the answer is correct anyway | Happens **after** generation |

**How to review one item (the sitting we actually did):**

1. Read the question and the model answer.
2. Open the golden chunk ids — record source path and what they teach.
3. Confirm those ids were **not** in the prompt (that is why it is “open”).
4. Check official 2.0 docs and/or run a minimal `sqlalchemy==2.0.51` script.
5. Mark `CORRECT` / `PARTIAL` / `WRONG` in `OPEN-CELL-REVIEW.md`.

**Chunk record for every reviewed item:**

| Item | Golden chunks and corpus sources | What those chunks say |
|---|---|---|
| **`g014`** | `c01588`, `c01589` — both `doc/build/changelog/migration_20.rst` | `Result` returns tuples by default; call `.scalars()` to return ORM objects directly. The second chunk shows `session.execute(select(User))` followed by `.scalars()`. |
| **`g060`** | `c02378` — `doc/build/orm/declarative_tables.rst` | `mapped_column()` adds ORM-specific configuration and becomes a normal `Column` in the Declarative table. |
| **`g112`** | `c01585` — `doc/build/changelog/migration_20.rst` | Maps `session.query(User).count()` to `session.scalar(select(func.count()).select_from(User))` or `session.scalar(select(func.count(User.id)))`. |
| **`g117`** | `c02482`, `c02485` — both `doc/build/orm/extensions/asyncio.rst` | Lazy relationships need `AsyncAttrs.awaitable_attrs`, `selectinload`, or `refresh(..., attribute_names=[...])` — not plain sync-style attribute access. |
| **`g120`** | `c00890`, `c00897` — both `doc/build/orm/inheritance_loading.rst` | `with_polymorphic()` works with joined inheritance; emits LEFT OUTER JOINs to subclass tables. |
| **`g119`** | `c02996`, `c01181` — both `doc/build/orm/session_basics.rst` | General 2.0 querying via `select()` + `Session.execute()` / `Session.scalars()`; does not directly compare `scalar` vs `scalar_one_or_none`. |
| **`g016`** | `c01576` — `migration_20.rst` | Row is a named tuple; mapping access moves to `row._mapping` / `result.mappings()`. |
| **`g028`** | `c01562` — `migration_20.rst` | Library-level autocommit removed; driver-level remains via `isolation_level`. |
| **`g036`** | `c01567`, `c01568` — `migration_20.rst` | `MetaData(bind=…)` / bound metadata removed; pass `Engine` to `create_all` / `sessionmaker`. |
| **`g039`** | `c01588`, `c01589` — same as `g014` | Same scalars story under different wording. |
| **`g040`** | `c01603` — `migration_20.rst` | Joinedload of a collection needs `Result.unique()` in 2.0. |
| **`g058`** | `c01567`, `c01568`, `c01573` — `migration_20.rst` | Prefer `Connection.execute(text(…))`; connectionless `engine.execute` removed. |
| **`g085`** | `c01608`, `c03009` — `migration_20.rst` + `session_basics.rst` | Session autocommit removed; autobegin added (and can be disabled). |
| **`g020`** | `c02230` — `orm/cascades.rst` | `cascade_backrefs` removed; many-to-one assignment no longer enrolls the object. |
| **`g114`** | `c01181`, `c03126` — `session_basics.rst` + `tutorial/data_select.rst` | `execute(select(User))` returns `Row`; delete needs a mapped instance (or a Core `delete()`). |

Those chunks were absent from the five-page prompts. Answers were checked against the
official 2.0 documentation and live `sqlalchemy==2.0.51` tests. Full sheet verdicts live in
`deliverables/OPEN-CELL-REVIEW.md`.

Take **`g074`**. The golden set names `c00711` and `c01010` as answer pages, but neither
reached the five pages on the model’s desk. The model therefore could not “grab” the golden
answer from the prompt. It produced the mixin and `column_property()` example anyway.

The review then checked that answer against three things:

1. The official SQLAlchemy 2.0 documentation, which contains the same
   `SomethingMixin` / `x_plus_y` pattern.
2. The golden chunks, recorded precisely:

   | Chunk | Corpus source | What it contributes |
   |---|---|---|
   | `c00711` | `doc/build/orm/declarative_config.rst` | Shows `column_property(firstname + " " + lastname)` as a mapped SQL expression. |
   | `c01010` | `doc/build/orm/mapped_sql_expr.rst` | Describes a plain Python `@property` alternative and contrasts it with `column_property()` and `hybrid_property`. |

   Neither chunk contains the exact `SomethingMixin` example. They support the underlying
   `column_property()` claim; the exact reusable-mixin pattern was verified from the official
   2.0 documentation separately.
3. A live SQLAlchemy `2.0.51` run, which produced:

```text
SELECT something.x + something.y AS anon_1
FROM something
[5]
```

So `g074` is **CORRECT**, but it is still a **retrieval miss**. The model answered from
knowledge or from a pattern it reconstructed; it did not demonstrate that this RAG run
retrieved the right page. That is why the answer can be correct while the retrieval metric
still records an open cell.

**What it is not.** The golden set is not secretly added to the prompt, and a correct open-cell
answer does not prove retrieval succeeded. It proves only that the model answered correctly
without the designated reference page in front of it.

**`g112` shows why “partly correct” matters.** Its reference chunk `c01585` in
`doc/build/changelog/migration_20.rst` gives the requested 2.0 form:

```python
session.scalar(
    select(func.count()).select_from(User)
)
```

It also gives `session.scalar(select(func.count(User.id)))` as the simpler alternative.
The `D` answer only explains the legacy `Query.count()` method, so it never answers the
equivalent-API question. `H` and `I` add `func.count(User.name)` and explain the
`select()` direction, but their code still uses legacy `session.query()` and never gives
the modern count form. Their claim that the example counts “each distinct user name” is
also false: `func.count(User.name)` counts non-NULL values; it does not apply `DISTINCT`.

A live `2.0.51` test confirmed the difference: the legacy query emitted a subquery and
returned `2`, while the modern `select(func.count()).select_from(User)` form returned `3`
for the test data. The exact `LIKE` patterns also differ: `"%ed"` matches a suffix, while
`"%ed%"` matches the substring described in the answer.

**`g117` misses the async-specific answer.** Golden chunks `c02482` and `c02485` say: use
`AsyncAttrs.awaitable_attrs`, eager `selectinload`, or `refresh(..., attribute_names=[...])`.
The `D` answer only defines `relationship()` and then loops `for address in user.addresses`
inside `AsyncSession` — generic ORM, not the asyncio guidance. The `I` answer is worse: it
builds `sessionmaker(conn.sync_engine, class_=AsyncSession)`, which mixes a sync engine with
an async session class and is not the documented pattern.

**`g120` is a thin but correct yes.** Chunks `c00883`/`c00890` show `with_polymorphic(Employee,
[Engineer, Manager])` emitting LEFT OUTER JOINs under joined inheritance. `c00897` extends the
same hierarchy through `Manager` → `VicePresident`.

**`g119` gets the conclusion direction right but the mechanism wrong.** Live `2.0.51`:
`session.scalar(select(User.name))` with two rows returns the **first row** (`a`) and does
**not** raise. `session.execute(...).scalar_one_or_none()` raises `MultipleResultsFound`.
So they are **not equivalent** on multi-row results, but not because `scalar` raises — it
silently returns the first value. The `D` answer even contradicts itself: it says `scalar`
raises on multiple rows, then says it performs no row-count checks.

**Open-cell sheet — complete rollup** (`deliverables/OPEN-CELL-REVIEW.md`):

| Verdict | D (7) | H (13) | I (15) |
|---|---|---|---|
| `CORRECT` | 4 | 6 | 5 |
| `PARTIAL` | 3 | 7 | 9 |
| `WRONG` | 0 | 0 | 1 (`g117`) |

**The ship-gate seven** — answers **only H** produced (D refused them). Shared open cells do
not prefer one prompt:

| Item | Verdict | One-line reason |
|---|---|---|
| `g036` | **CORRECT** | MetaData `bind=` removed |
| `g039` | **CORRECT** | need `.scalars()` |
| `g058` | **CORRECT** | use `Connection.execute(text(...))` |
| `g016` | **PARTIAL** | `row.keys` gone; pointed at `Result.keys()` not `_mapping` |
| `g028` | **PARTIAL** | “driver-level remains”; missed library autocommit removed |
| `g040` | **PARTIAL** | suggested `selectinload`; missed `.unique()` |
| `g085` | **PARTIAL** | talked subtransactions; golden is autocommit → autobegin |

**3 CORRECT / 4 PARTIAL / 0 WRONG** — H’s extra willingness did not invent harmful wrong
answers. It also did not make those seven fully right.

Named H/I-only findings beyond the seven:

- **`g020` PARTIAL (I only)** — correctly says `cascade_backrefs` was removed, then wrongly
  tells you to set it `False` / use `Session(future=True)` as if the option still existed.
- **`g114` PARTIAL (I only)** — diagnosis is right (don’t `delete` a `Row`), but never names
  `.scalars()`, which is the usual cause the golden chunks document.

Shared wins that stayed correct across prompts: `g014`/`g039` (scalars), `g036` (no
`MetaData(bind=…)`), `g058` (`Connection.execute`), `g060`, `g074`, `g120`.

**Say this:** “Open cell means the golden page missed the desk. A correct open-cell answer is
still a retrieval miss. The seven H-only answers are the ship gate — 3 correct, 4 partial,
0 wrong.”

**Do not say:** “The model secretly got the golden chunk.” / “Correct open cell means search
worked.”

---

### R8.6 The prose judge — Track E: and the day the judge itself broke (`D80`)

**Plain job (Track E).** `R8.5` / Track C catches invented *code*: it lists dotted calls in a
code block and asks whether each appears on the five desk pages. No model needed, exact.

**Now the sentence that detector cannot see.** `g056`'s answer does not put its invention in a
code block. It says it in prose. There is nothing dotted to look up, so the code detector reads
that answer and finds nothing wrong — and `D77` says so in its own text: *"structurally blind"*.

So the missing half is one question, asked about a paragraph rather than about a symbol:

> Here is a sentence from the answer. Here are the five pages the model was handed. **Do those
> pages say this?**

That is reading, and reading needs a reader. This is what people mean by *LLM as judge*: a second
model, which never saw the question and has no stake in the answer, is given the claim and the
passages, and replies with one word.

```
SUPPORTED    the passages say this, or say something it follows from
PARTIAL      part of it is in the passages and part is not
UNSUPPORTED  the passages do not say this — even if it happens to be true elsewhere
```

**Say what this is not.** It is **not** a fact-checker. `UNSUPPORTED` does not mean *wrong*; it
means *not in the pages we gave it*. A perfectly correct sentence the model knew from training
and no retrieved page mentions is `UNSUPPORTED` here, and that is the intended reading — a RAG
system that answers from memory has not used its sources, and you cannot check it.

**And it is not a replacement for R8.5.** Code is stripped out of the claim before the judge sees
it, on purpose. The code half already has an exact answer; paying a judge to re-answer it worse,
with an opinion, would be a downgrade dressed as an upgrade.

#### The bit that went wrong, which is more interesting than the bit that worked

The plan (`D78`, 2026-08-30) was a strong hosted judge on a free tier, pinned to one model id.
On **2026-09-03**, one call each, same key, same minute:

```
gemini-3.6-flash     FAIL HTTP 503 from gemini-3.6-flash     <- the pinned one
gemini-3.5-flash     OK   SUPPORTED
gemini-3.7-flash     OK   SUPPORTED
gemini-3.8-flash     OK   SUPPORTED
```

The pinned model — chosen three days earlier and written into the code — was the only one not
answering. **Pinning a name does not pin a service.**

Switching to a sibling hit the second wall, and this one is the real finding, because `D78` had
written the opposite in a sentence:

> `D78`: *"Rate limits are not the constraint on any free tier."*

```
quotaId:    GenerateRequestsPerDayPerProjectPerModel-FreeTier
quotaValue: 20
```

**Twenty calls a day, per model.** Judging D and H over the saved answers is about **110 calls**.
Not 110 an hour — 110 total, and the ceiling is 20 a day. And the rule `D78` itself insists on is
that **both prompts must be judged by the same judge in one sitting**, because a judge read on
Monday and Friday is two judges wearing one name. Spreading 110 calls over six days to fit the
quota does not satisfy that rule. It breaks it.

#### So the judge is a model on this laptop, and that is not a consolation prize

`gemma4:e4b`, run by Ollama on the Mac. No quota, no key, no provider.

**The obvious objection, and why it does not apply.** *"Isn't asking the model to grade itself
worthless?"* — yes, and this is not that. The **generator** is `qwen2.5-coder:7b`. The **judge**
is a different family and a different size. Nothing marks its own homework.

**The honest objection, and what answers it.** *"Is a local model good enough to judge?"* Nobody
knows, and a model card would not settle it. **That is what §R8.7 is for**: ten of this judge's
verdicts go in front of a human, and the agreement rate is a measured number. A famous judge with
unmeasured agreement and an unknown judge with unmeasured agreement are the same object — a
precise instrument of unknown accuracy.

**One property survived all of this unchanged, and it is why the swap took an afternoon rather
than a rewrite:** every row carries the model that produced it (`D78`'s `stamp()`). Swapping
judges does not orphan old rows; it labels new ones.

#### Two silent bugs found on the way, both flattering

| what happened | why it mattered |
|---|---|
| The report header printed the model **constant**, so a run judged by `gemma4:e4b` announced itself as `gemini-3.7-flash`. | A report that misnames its own instrument. Now the header is built from the row stamps, and two ids in one run print `!! TWO JUDGES IN ONE RUN` — that is a void comparison, not a warning. |
| Ollama truncates the prompt at `num_ctx` **in silence** — default 4096 tokens. The judge prompt measures 7127–11149 characters, roughly 1800–2800 tokens. | It fits *today*. Which is exactly when to pin it: the first answer that overflows gets confident verdicts based on four passages out of five, with no error anywhere. Pinned at 8192, with a test. |

#### What it measured, and the trap in reading it (`D82`)

110 answers, one sitting, judge `gemma4:e4b`:

```
variant   answers  judged   SUPP  PART  UNSUP   supported
D              48      47     40     2      5        85%
H              62      61     56     3      2        92%
```

**The trap is reading that as "H is more faithful."** Those are two rates over **two different
sets of answers** — D answered 48 questions, H answered 62. Comparing them is comparing averages
of different populations, which is the mistake `D61` exists to stop.

**Line the same items up instead.** 46 questions got an answer from *both* prompts:

```
H supported where D was not : 5   g024 g045 g078 g080 g083
D supported where H is not  : 1   g088
p = 0.22
```

Five better, one worse, and a p-value that says a coin could do that. **On the answers both
prompts produced, H is not measurably more faithful.**

**So where did the 7 points go?** Into the **16 questions only H answered at all** — D refused
those. **13 of the 16 came back `SUPPORTED`.**

That is worth saying slowly, because it is the actual result and it is not what the headline
looks like:

> H does not write better-grounded answers to the same question. It **answers questions D walked
> away from**, and those extra answers are mostly grounded in the pages it was given.

**And it kills the strongest objection to shipping H.** The obvious worry about a prompt that
makes a model more willing to answer is that it buys the extra answers by making things up. That
worry is now measured, and the answer is no.

**One item went the other way — `g088`, and it is worth reading.**

| | verdict | the judge's reason |
|---|---|---|
| **D** | `SUPPORTED` | *"Passage [4] provides a complete code example and description detailing all the steps listed in the claim."* |
| **H** | `UNSUPPORTED` | *"The passages do not contain the specific code example or the full instructional setup provided in the claim."* |

H did not contradict its sources. **It said more than they contain.** That is exactly the failure
a chattier prompt should be expected to have — and it happened once in 46.

**A named item where three separate checks agree — `g016`.**

| check | what it found |
|---|---|
| `D79` re-score | stored fields said it cited `[0,1,2]`; today `[2]`, and **uncited code blocks 0 → 1** |
| citation integrity | a code block with no source |
| the prose judge | `UNSUPPORTED` — *"None of the passages state that `row.keys()` is deprecated"* |

The `row[keys[0]]` subscript had made that code block *look* cited. Underneath the fake citation,
the claim was not in the pages either.

#### And then a second model was asked the same ten, and agreed with four

This is the part to be uncomfortable about, and it is measured rather than suspected.
`gemini-3.5-flash` re-judged the ten verdicts on the review sheet:

```
  g045   D  UNSUPPORTED  -> UNSUPPORTED  agree
  g079   D  UNSUPPORTED  -> UNSUPPORTED  agree
  g080   D  UNSUPPORTED  -> PARTIAL      DIFFER
  g083   D  UNSUPPORTED  -> SUPPORTED    DIFFER
  g119   D  UNSUPPORTED  -> UNSUPPORTED  agree
  g016   H  UNSUPPORTED  -> UNSUPPORTED  agree
  g088   H  UNSUPPORTED  -> PARTIAL      DIFFER
  g056   D  SUPPORTED    -> PARTIAL      DIFFER
  g056   H  SUPPORTED    -> PARTIAL      DIFFER
  g014   D  SUPPORTED    -> PARTIAL      DIFFER

  4/10 = 40% model-to-model agreement
```

**Two runs exist and they have different denominators, so read the labels.** The ten above is the
complete first pass. A second pass was needed to *save* the verdicts into the review sheet, and it
got **7 of 10 before the daily cap** — the three `SUPPORTED` controls (`g056` twice, `g014`) came
back `(no answer: 429)`. The saved file therefore says **4/7 = 57%**, over what it answered, with
the three misses printed rather than quietly dropped. Same finding, smaller sample; the sheet fills
in on tomorrow's quota.

**Look at the right-hand column of every disagreement.** All six are `PARTIAL`. The second model
kept reaching for the middle box; the local judge almost never does — **2 `PARTIAL` in 47
answers** for D, **3 in 61** for H.

So the weakness has a name. It is not *"the local model is worse"*, which is unfalsifiable and
useless. It is:

> **The local judge has a coarser scale.** Given a three-way rubric it behaves closer to a
> two-way one, so answers that are *partly* in the sources get pushed to whichever end is nearer.

**`g056` is where that costs something real.** Three readings of the same item now exist:

| judge | verdict |
|---|---|
| `gemini-3.6-flash` (`D78`, 2026-08-31) | `PARTIAL` |
| `gemini-3.5-flash` (2026-09-03) | `PARTIAL` on both arms |
| **`gemma4:e4b` (the one that produced the table)** | **`SUPPORTED` on both arms** |

Two hosted models agree with each other and disagree with ours — on **the exact item `D77` named
as the reason a prose judge was needed at all**, because it fabricates in prose rather than in
code. If our judge is wrong there, it is wrong in the direction that matters: it waved through an
answer this repo already classifies as a fabrication.

**What that does to the numbers, precisely:** it does not overturn them, and it does not rescue
them either. The paired comparison was already not significant, so a noisier judge cannot make H
a winner. What it does change is how hard to lean on *13 of the 16 extra answers are grounded* —
those are `SUPPORTED` verdicts from a judge that over-uses `SUPPORTED`, so **read 13/16 as a
ceiling.**

**And why we do not simply use the better judge:** we cannot run it. Twenty calls a day per model
against a 110-call run (`D80`). Ten calls for a second opinion on the rows a decision rests on is
affordable; a hundred and ten is not. **A local judge with a named, measured weakness beats a
stronger judge that cannot finish.**

**Say what `UNSUPPORTED` is not.** It does **not** mean *false*. It means *not in the pages the
system retrieved*. A sentence that is perfectly true, that the model knew from training, and that
none of the five retrieved pages mentions, is `UNSUPPORTED` here — on purpose. A RAG system
answering from memory has not used its sources, and nobody can check it.

### R8.7 The judge's own ceiling — ten verdicts a human reads (`D80`)

**Plain job.** An automated judge produces a number per run. Nobody knows whether that number
is right until someone checks the judge the way the judge checks the model. This section is
**your** remaining Track E work.

`uv run python -m rag.faithful --agreement` writes `deliverables/JUDGE-AGREEMENT.md`: ten
verdicts, each with the claim the judge read, the five passages it read them against, and a
blank. **Claude renders it; Claude does not fill it in** (`D06`) — same rule as the golden set.

**How you fill one row.**

1. Read the claim the judge scored.
2. Skim the five passages printed under it (these are the desk pages for that item).
3. Decide: do those passages support the claim? Mark `AGREE` or `DISAGREE` with the judge’s
   `SUPPORTED` / `PARTIAL` / `UNSUPPORTED`.
4. If you disagree, write one line why (e.g. “passages only cover X; claim also asserts Y”).

**What agreement means.** You and the judge gave the **same** label. Disagreement is useful —
especially on `SUPPORTED` controls, where a miss means the judge waved something through.

**The ten are picked by risk, not at random, and both halves of that are deliberate:**

- **Every `UNSUPPORTED` and `PARTIAL` first.** Most answers will come back `SUPPORTED`. A random
  ten from that pile mostly asks *"do you agree the judge found nothing wrong?"*, which is the
  easy question, and none of the verdicts a decision would actually rest on.
- **`SUPPORTED` rows fill the rest, and they are not padding.** Without them the sheet can only
  catch the judge **accusing wrongly**. It could never catch the judge **missing something** —
  and a miss is precisely the `g065` failure: the item whose stated reason was wrong and whose
  label no audit could test.

**Three of the ten are `SUPPORTED` on purpose, and that had to be forced.** The finished run has
7 `UNSUPPORTED` and 5 `PARTIAL`, so ranking by risk alone filled all ten slots with accusations
and **not one control got in.** A sheet of only accusations can catch the judge condemning an
answer its sources do support — and is structurally incapable of catching the judge waving
through one they do not. The second error is the `g065` failure mode. So three slots are
reserved, capped at half the sheet so risk still leads.

**The rate is read back out of the sheet**, not typed into a doc beside it. An unanswered row
counts as unanswered — never as agreement — and the number of blanks prints next to the rate,
because *"9 of 10 agreed"* over one filled row is the shape of every flattering statistic this
repo has caught.

**Until the sheet is filled:** every faithfulness % in §R8.6 is **provisional**.
`rag.judge --report` prints that instead of inventing an agreement rate.

**Say this:** “I hand-check ten judge verdicts before I trust the faithfulness number. Until
then the figure is provisional.”

**Do not say:** “The judge agrees with humans 85–92%” (that is someone else’s judge).

### R8.8 One command for the whole thing (`D81`)

**Plain job.** Phase 4’s gate is a sentence: *one command scores the full golden set and emits
retrieval metrics, faithfulness and citation accuracy in one report.* You should not have to
remember five flags and stitch a spreadsheet.

```
uv run python -m rag.judge --report
```

**What each section is (maps to tracks):**

| Report section | Track | source | why |
|---|---|---|---|
| retrieval | (Phase 3 ceiling) | **live** | lookups only — cheap |
| generation / end to end | **A** | saved answers | 300 generations; re-run ≠ same answers (`D54`) |
| citations | **B** | saved answers, **re-scored** | stored fields predate `D79` |
| groundedness | **C** | derived from saved answers | no judge model |
| faithfulness | **E** | saved judge rows | ~110 judge calls |
| judge agreement | **E** human | the filled sheet | you write it (`D06`) |

**The design decision worth knowing is the labelling.** Every section says whether it was
**measured live** or **read from a file**. A report that mixes a live number with a stored one
and labels neither is how `0.64` came to be quoted as the system’s score.

**Two things it does that a printout would not:**

- **It re-derives the published figures instead of quoting them.** D **39/91 = 0.43**, 19
  over-refusals, 2 fabrications; H **47/91 = 0.52**, 10, 2; I **46/91 = 0.51**, 11, 2 — every cell
  identical to `D72`/`D74`. That agreement is the check that this is the same derivation and not a
  plausible second opinion.
- **It says `NOT MEASURED` out loud.** No judge rows yet → section prints the command that
  fixes it, not a zero. Sheet not filled → prints *"0 answered — a human has not read them
  yet"*, not an agreement rate over an empty file.

**A named example the re-scoring caught, and it is the third of its kind.** `g016` under prompt H
contains `print(f"x: {row[keys[0]]}  y: {row[keys[1]]}")`. Before `D79`:

| | stored 2026-08-27 | today |
|---|---|---|
| cited | `[0, 1, 2]` | `[2]` |
| out of range | `[0]` | none |
| **uncited code blocks** | **0** | **1** |

The subscripts did not just invent a citation of a source numbered zero. **They made an uncited
code block look cited.** And prompt `D` produces **zero** such rows — D barely cites and barely
writes code, so the bug cannot fire on it. Third time in this phase a broken detector was
invisible until the arm under test started complying (`D76`, `D79`, this). **Test your instruments
against the arm that changed, never only against the control.**

**Say this:** “One command prints every Phase 4 report card and labels live vs file for each.”

**Do not say:** “The report is the data.” Saved JSON is the data; the report is a view.

### R8.9 What is left — and what to do next

Tracks **A–D** are measured (open-cell sheet marked). What remains:

| Open | Track | What you actually do |
|---|---|---|
| **Ship H or keep D** | **F** | Read §R8.3a. If you ship: move H’s user-turn citation line into `ask.build_prompt` / production path; leave a note in `09-DECISIONS.md`. If you keep D: write *why* (e.g. wait for agreement sheet). Production `ask.SYSTEM` is still D either way until you change it. |
| **The judge's agreement** | **E** | Open `deliverables/JUDGE-AGREEMENT.md`. Fill all ten blanks (`AGREE`/`DISAGREE`). Regenerate with `uv run python -m rag.faithful --agreement` if the file is stale. Until then every faithfulness % is provisional. |
| **Lab Round 13 / 14** | optional | On the lab PC, branch `phase-2/measure`: confirm recall / re-run `--refusals` or D vs H on the 3060. Mac already has both measurements; lab is a second-machine check, not a blocker. |

**Suggested order for your next sitting:**

1. Read §R8.3a once cold — decide H or D (or “decide after agreement sheet”).
2. Fill `JUDGE-AGREEMENT.md` (Track E human gate).
3. Re-run `uv run python -m rag.judge --report` and confirm the agreement section is no longer
   blank.
4. Only then treat `D82` faithfulness figures as non-provisional.

Start map for the five tracks: top of this file, **Where to start**.

---

## After this you can say

- End to end **0.43**; **0.64** is retrieval’s ceiling only.
- Better search made over-refusal **count** rise — compare **rates** (29% → 33%).
- Two Phase 3 search wins (`g044`, `g050`) are still refused with the page in hand.
- **Moving** the cite rule beat **shouting** it: 0.43 → 0.52, uncited 67% → 10%.
- First H score was wrong (`[2] The sources…`); corrected, still significant (`D76`).
- Invented **code** can be caught with no judge model (`D77`); prose lies need a reader.
- The hosted judge was **503 on its pinned id and capped at 20 calls a day per model** — the
  run needs ~110 — so the judge is local. Not a downgrade: `stamp()` keeps every row traceable,
  and the generator is a different model, so nothing grades itself (`D80`).
- **`UNSUPPORTED` means "not in the pages we gave it"**, not "false".
- One command emits all of it, and each section says **live or read from a file** (`D81`).
- Prose faithfulness: D **85%** supported, H **92%** — but **on the 46 items both answered it is
  5↑ 1↓, p = 0.22.** The gap is the **16 questions only H answered**, 13 of them grounded. So:
  **H answers more, and the extra answers hold up** — not "H is more faithful" (`D82`).
- A second model agreed with our judge on **4 of 10**, and **all six disagreements were it
  choosing `PARTIAL`** — our judge has a **coarser scale** (2 PARTIAL in 47). On `g056` two hosted
  models say `PARTIAL` and ours says `SUPPORTED` (`D82`).
- Phase 4 is **five tracks + ship H** — not one “judge” chapter. Open cell done; agreement
  sheet and ship call remain.

## Do not say

- “My RAG is 64% accurate.”
- “I fixed hallucination” (count still 2; severity changed).
- “H is more faithful” — the rates say 85% → 92%, the **paired** test says p = 0.22 (`D82`).
  Two rates over two different sets of answers is not a comparison.
- “I improved the prompt” without saying **position** (E was louder and did nothing).
- “Chunking / reranker will fix the rest” (`D70` closed that for the 17 absents).
- “LLM-as-judge grades my answers” **without saying which judge and when** — same judge, both
  arms, one sitting, model stamped on every row, or it is not a comparison (`D78`, `D80`).
- “The judge agrees with humans 85–92%” — that is somebody else's judge on somebody else's task.
  Ours is unmeasured until the sheet of ten is read.
- “The open cell proves retrieval worked.” Correct without the golden page is still a miss.

---

## Where the rest lives

| | |
|---|---|
| [`../phases/PHASE-4.md`](../phases/PHASE-4.md) | plan + measured tables |
| [`09-DECISIONS.md`](09-DECISIONS.md) | `D71`–`D82` |
| [`15-IMPROVE.md`](15-IMPROVE.md) | §R7 — search / desk pages |
| [`14-MEASURE.md`](14-MEASURE.md) | §R6 — generation gap first seen |
| `rag/judge.py` | citations + grounding (no model, no key) |
| `rag/compare_prompts.py` | prompt lab (`--golden`) |
| `rag/faithful.py` | the prose judge (`--sweep`, `--claims`, `--agreement`) |
| `rag/judge.py --report` | the gate: everything in one command |
| [`../deliverables/OPEN-CELL-REVIEW.md`](../deliverables/OPEN-CELL-REVIEW.md) | Track D — human open-cell sheet |
| [`../deliverables/JUDGE-AGREEMENT.md`](../deliverables/JUDGE-AGREEMENT.md) | Track E — human agreement sheet |
| [`../logs/HANDOFF.md`](../logs/HANDOFF.md) | Round 13 |
