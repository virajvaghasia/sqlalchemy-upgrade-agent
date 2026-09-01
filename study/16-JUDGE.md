# Judge — study notes

Part of [`sqlalchemy-upgrade-agent`](../README.md). **§R8**, after
[`15-IMPROVE.md`](15-IMPROVE.md) §R7. Plan: [`../phases/PHASE-4.md`](../phases/PHASE-4.md).
Decisions: **`D71`–`D77`**.

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

## Easy picture — four different report cards (keep them separate)

Remember the desk from §R7: search puts **five documentation pages** in front of the model.
Then the model writes. Phase 4 is only about that writing. It asks **four separate questions**.
Each gets its own score. Do **not** blend them into one “the system is X% good” number.

**1. Did search put the right page on the desk?**

```
  Question → search → five pages on the desk
                         ↑
                    was the verified answer among them?
```

That is **retrieval**. Phase 3 already measured it: **0.64**. This file does not re-fight that.

**2. When the right page *was* on the desk, did the model still answer?**

```
  Right page on desk + model writes an answer  →  good for the user
  Right page on desk + model says "sources don't answer"  →  search won, user got nothing
```

That combo (page arrived **and** model answered) is **end to end**: **0.43**.
Quote **0.43** as what the system does. Quote **0.64** only as “search’s ceiling.”

**3. If it answered, can you open a page and check the claim?**

A good answer looks like: *“…was removed in 2.0 [3].”* — you open source **[3]** and verify.
A bad-for-RAG answer can be *correct* but have **no `[1]`/`[2]`/…** at all — you just have to trust it.

That is **citations**. Under the shipped prompt, about **two thirds** of answers cite nothing.

**4. If it pasted code, do those API names appear on the desk pages?**

```
  Answer shows:  op.create_view(...)
  Desk pages:    no "create_view" anywhere
  → the code is not backed by what we retrieved
```

That is **grounding**. A small script checks it — no second AI judge required.

---

**Why you must not average these into one score**

Suppose the model always refuses. Then:
- citations look “perfect” (there is nothing to cite),
- but every user gets a useless decline.

One blended “quality” number would go **up** while the product got worse. So we keep four
columns, the same way we never blend “did search find it?” with “did the model answer?”

---

**If someone asks in an interview — one sentence each**

| They ask | You say |
|---|---|
| What’s your score? | **0.43** end to end. **0.64** is only “did search find the page.” |
| Why did refusals go *up* after better search? | More questions now *have* the page in the prompt, so more can refuse *with it there*. Look at the **percentage**, not the raw count. |
| What fixed citations? | Same instruction, moved to sit **right before** the answer — not shouted louder at the top. |
| Did you fix hallucinations? | Still **2** fabrications on unanswerable items; under prompt H the dangerous *code recipes* got milder. |

---

## §R8 — what Phase 4 measured

### R8.1 End to end (`D72`) — did the user get an answer?

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

**Command — do not hand-subtract in a spreadsheet:**

```
uv run python -m rag.score --refusals
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

**What it is not.** “Generation got worse after Phase 3.” The ceiling moved; more of the old
generation defect became visible.

---

### R8.2 Citations (`D73`) — can someone verify the answer?

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

**What it is not.** A claim the answers are mostly false. Many are right *and* unchecked.

---

### R8.3 Prompt lab (`D74`) — *where* the rule sits beats *how loud* it is

**Plain job.** Refusal and citation failures are the **model’s** habits, not search’s. Cheapest
lever: change the prompt. Free. No re-embed.

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

---

### R8.3a Which prompt should we pick?

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

**What H does not fix:**

- fabrications remain **2 of 9** (`g056`, `g065`)
- **53%** of H's code-containing answers still have no source beside the code
- prose-level faithfulness is not measured yet; that needs the pinned strong judge

So the recommendation is not “H solves the system.” It is: **H is the best measured prompt
candidate, and its remaining failures are visible.**

**The exact decision to make.** If the goal is to improve what users receive now, choose H.
If the goal is to preserve the current production behaviour until a human reviews the raw
answers, keep D temporarily. Either is defensible; silently changing D is not.

**Say this:**

> “I recommend H. It keeps the shipped system prompt and moves the citation reminder into the
> user turn immediately before the answer. On the 100-item run it improved end to end from
> 0.43 to 0.52, reduced uncited answers from 67% to 10%, fixed nine paired items with no
> regressions, and still leaves fabrication and prose-faithfulness work open.”

**Do not say this:**

- “H fixed hallucinations.” Fabrications stayed at **2**.
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

First scoreboard for H: **12↑**, end to end **0.55**. Spot-check of raw `g006`:

```
[2] The sources do not answer this.
```

That is a **decline**, not an answer. The detector `ask.refused()` asked: does the text
**start with** `"The sources do not answer"`?  
`"[2] The sources…"` does **not** → counted as answered. **The fix under test broke the meter.**

```
  first (wrong)   12 fixed,  end to end 0.55
  true            9 fixed,   end to end 0.52   ← still clears the bar; now honest
```

**Fix:** strip leading `[n]` markers, *then* test the start.

**Why not “search for the phrase anywhere”?** Prompt D deliberately writes answers like *“here
is what the sources cover, and here is what they do not.”* That is an **answer**. A substring
match would score it as a refusal and inflate the flattering number.

Saved full answers (`D75`) made the correction seconds, not another 300 generations. Shipped
prompt D produced **zero** cited refusals, so published D72/D73 numbers did not need rewriting.

**What it is not.** “H was fake.” Corrected H still wins; the first table was just wrong.

---

### R8.5 Groundedness (`D77`) — did the code invent APIs?

**Two different “is this lying?” questions:**

| | citations (`D73`) | grounding (`D77`) |
|---|---|---|
| Asks | Can I find which page you used? | Are the **API calls in your code** on those pages? |
| Needs | `[n]` markers | String match into the five desk pages |
| Needs a big judge model? | No | No |

**Idea in one picture:**

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

- **`g056`** invents in **prose**, not code → this detector cannot see it.
- Grounding ≠ “does this symbol exist in Alembic?” That is `audit_golden_fullbar.py` against
  the real library. Grounding only asks: *was it in the pages we retrieved?*

**What it is not.** “I fixed hallucination.” Count unchanged; severity under H dropped.

---

### R8.5a The open cell — the golden page is not on the desk

This is the part that is easy to mix up:

| Thing | What it does | Does the model see it? |
|---|---|---|
| **Golden answer chunk** | Reference page used to judge whether the answer is right | **No**, when it is absent from the retrieved prompt |
| **Five retrieved chunks** | The pages actually handed to the model | **Yes** |
| **Open-cell review** | Human checks whether the answer is correct anyway | Happens **after** generation |

The same record applies to the earlier reviewed items:

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

Named H/I-only findings:

- **`g016` PARTIAL** — live: `hasattr(row, "keys")` is **False**; `result.keys()` and
  `row._mapping.keys()` both work. Answer pointed only at `Result.keys()`, while golden
  `c01576` teaches `_mapping` / `mappings()`.
- **`g028` PARTIAL** — only said “driver-level remains”; golden `c01562`’s load-bearing half
  is that **library-level autocommit was removed**.
- **`g040` PARTIAL** — suggested `selectinload` (valid alternative) but missed the golden
  2.0 fix: `result.unique()`. Live: without `unique()` → `InvalidRequestError`.
- **`g085` PARTIAL** — talked about subtransactions; golden is autocommit removed /
  autobegin (`c01608`, `c03009`).
- **`g020` PARTIAL (I only)** — correctly says `cascade_backrefs` was removed, then wrongly
  tells you to set it `False` / use `Session(future=True)` as if the option still existed.
- **`g114` PARTIAL (I only)** — diagnosis is right (don’t `delete` a `Row`), but never names
  `.scalars()`, which is the usual cause the golden chunks document.

Shared wins that stayed correct across prompts: `g014`/`g039` (scalars), `g036` (no
`MetaData(bind=…)`), `g058` (`Connection.execute`), `g060`, `g074`, `g120`.

---

### R8.6 What is left

| Open | Plain meaning |
|---|---|
| **Ship H or keep D** | Recommendation is H; your call. Numbers ready; production prompt still D. |
| **Prose faithfulness** | “Does this *sentence* match that passage?” Needs a pinned strong judge (e.g. Gemini free tier). No key on this machine yet. |
| **Lab Round 13** | GPU sittings for `--refusals`; Mac already ran one D72 baseline. |

When a judge exists: pin model + version; hand-check ~10 items and report agreement rate.

---

## After this you can say

- End to end **0.43**; **0.64** is retrieval’s ceiling only.
- Better search made over-refusal **count** rise — compare **rates** (29% → 33%).
- Two Phase 3 search wins (`g044`, `g050`) are still refused with the page in hand.
- **Moving** the cite rule beat **shouting** it: 0.43 → 0.52, uncited 67% → 10%.
- First H score was wrong (`[2] The sources…`); corrected, still significant (`D76`).
- Invented **code** can be caught with no judge model (`D77`); prose lies need more.

## Do not say

- “My RAG is 64% accurate.”
- “I fixed hallucination” (count still 2; severity changed).
- “I improved the prompt” without saying **position** (E was louder and did nothing).
- “Chunking / reranker will fix the rest” (`D70` closed that for the 17 absents).
- “LLM-as-judge grades my answers” — not yet; this file is brackets + symbol checks.

---

## Where the rest lives

| | |
|---|---|
| [`../phases/PHASE-4.md`](../phases/PHASE-4.md) | plan + measured tables |
| [`09-DECISIONS.md`](09-DECISIONS.md) | `D71`–`D77` |
| [`15-IMPROVE.md`](15-IMPROVE.md) | §R7 — search / desk pages |
| [`14-MEASURE.md`](14-MEASURE.md) | §R6 — generation gap first seen |
| `rag/judge.py` | citations + grounding (no model, no key) |
| `rag/compare_prompts.py` | prompt lab (`--golden`) |
| [`../logs/HANDOFF.md`](../logs/HANDOFF.md) | Round 13 |
