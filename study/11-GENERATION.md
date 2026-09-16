# Generation — study notes

Part of [`sqlalchemy-upgrade-agent`](../README.md).

**Read [`10-RETRIEVAL.md`](10-RETRIEVAL.md) first** — at least the "five facts" page and §R1.
This file starts *after* search has already picked five pages. You need to know: the chatbot
only writes the next word; the **prompt** is the whole message we send it; those five pages
get pasted into that message.

**What this file is about.** Search returns pages. Pages are not an answer. Someone still has
to write a sentence a developer can read. That writing step is **generation**. The script is
`rag/ask.py`. The chatbot is still `qwen2.5-coder:7b` via Ollama. Nothing new is being trained.

**The numbering.** This is §R3, continuing the `R` run from the other file. `§R2` still means
"the 1024 numbers." `§R3` means this file. Same reason `02` continues `01`.

---

## Stop — how to read this file

| You see | What it is | What it is **not** |
|---|---|---|
| **`§R3`** | This sitting — generation (writing the answer) | A score |
| **prompt A / B / C / D** | Wordings of the standing instructions — **D ships** | Decision ids |
| **over-refusal** | Right pages were already on the desk; model still said “sources do not answer” | A search miss |
| **fabrication** | Model invented an API / answer the pages do not support | A wrong search rank |

### What “generation” means here

Search already picked five pages. **Generation** is the step that turns those pages + instructions
into a paragraph. Nothing is trained. The script is `rag/ask.py`; the model is still
`qwen2.5-coder:7b` via Ollama.

Named example for over-refusal: *“why can't I call `engine.execute` any more?”* — pages had the
answer; the model still refused (§R3.4).

---

## If search already picked five pages, what is left to get wrong?

Plenty. A wrong *instruction* at the top of the message can:

- refuse a question whose answer is sitting in those five pages, or
- invent a function signature that is in none of them.

Search did not do that. The English we send with every question did.

**The named case, because "a wrong instruction" is a type of thing and this was a real one.**
The question was *"why can't I call `engine.execute` any more?"* The five pages handed to the
model **already contained the answer** — the 2.0 migration pages saying exactly that. The reply
was:

```
The sources do not answer this.
```

Search worked. The library found the right pages. Then one sentence of standing instruction —
*refuse if the sources do not contain the answer* — fired anyway, and the pages were thrown
away unread. Two other explanations were tested first and both were wrong (§R3.4). The bug was
in the English.

| subsection | after it you can say |
|---|---|
| R3.1 | the message has two parts: standing rules (same every time) and this question's five pages |
| R3.2 | one sentence in the standing rules is "you may say you don't know." We need that sentence. The *strict* wording of it can fire when it should not |
| R3.3 | we tried three wordings on two questions. No "you may refuse" → invents APIs every time. Strict refuse → gave up once in three. The middle wording is what ships |
| R3.4 | we proved it was the instruction, not search, by handing the chatbot *only* the right pages. It still refused |
| R3.5 | "keep the first version simple" does not mean "ship a broken instruction" |
| R3.6 | over 19 questions A and B were the same, and D replaced both; over 100, D still refuses 19 of the 58 questions where the right page was in the prompt |

---

## §R3 — The instructions are a component, like the search

### R3.1 The message has two parts

Open `rag/ask.py` in your head as a letter:

```
Dear chatbot,

STANDING RULES (same for every question):
  You answer SQLAlchemy 1.4 → 2.0 questions.
  Use only the pages below. Cite them as [2].
  You may say "The sources do not answer this" if the pages are silent.
  If 1.4 and 2.0 disagree, say so.

THIS QUESTION'S PAGES:
  [1] ... five pages search just found ...
  [2] ...
  ...

QUESTION: should I pass future=True to create_engine?

ANSWER:
```

Two piles of text, concatenated:

| pile | changes when the question changes? | in the code |
|---|---|---|
| standing rules | **no** | a string named `SYSTEM` |
| this question's pages + the question | **yes** | built by `build_prompt()` |

People call the standing rules the **system prompt** and the rest the **user prompt**. Those
are just names for "the paragraph that does not change" and "the paragraph that does." The
bug in this sitting lives in the paragraph that does not change.

The real `build_prompt()` output looks like this:

```
# illustration — the shape build_prompt() produces
SOURCES

[1] SQLAlchemy 2.0.51 — doc/build/changelog/migration_20.rst
     Migration to 2.0 > Step Four - Use the future flag on Engine

     <the chunk text>

---

[2] SQLAlchemy 1.4.52 — doc/build/core/future.rst
     ...

---

QUESTION: should I pass future=True to create_engine?

ANSWER:
```

`--show-prompt` on `rag/ask.py` prints both piles for a real question.

### R3.2 The standing rule that is also the bug

Here is `SYSTEM` as it ships — read live out of the file. **This is wording D, shipped
2026-08-17 (`09-DECISIONS.md` D54); it replaced B, which the rest of this section is about:**

```
# runnable: uv run python -c "
# import ast, pathlib, textwrap
# tree = ast.parse(pathlib.Path('rag/ask.py').read_text())
# s = next(ast.literal_eval(n.value) for n in tree.body
#          if isinstance(n, ast.Assign) and getattr(n.targets[0],'id','')=='SYSTEM')
# print(textwrap.fill(s, 76))"
You answer questions about migrating Python code from SQLAlchemy 1.4 to 2.0.
You are given numbered sources from the SQLAlchemy documentation. Base your
answer on those sources and cite the source number in brackets, like [2].
Answer with whatever the sources do support, even partially: if they cover
part of the question, give that part and state plainly which part they do
not cover. Reply "The sources do not answer this." only when none of the
sources is about the subject of the question at all, and when you do, name
the specific thing you looked for and did not find. Each source is labelled
with the SQLAlchemy version it documents — if versions disagree, say so
rather than picking one silently.
```

Four jobs in that paragraph:

| # | instruction | why it is there |
|---|---|---|
| 1 | Use only these sources | otherwise the model answers from SQLAlchemy-in-its-weights, which blurs 1.4 and 2.0 (§R1.1) |
| 2 | Cite `[2]` | a claim you can check against source 2 in seconds |
| 3 | **You may refuse** — but only if no source is about the subject, and you must name what you looked for | §R1.4: some questions have **zero** chunks (`has_table`). A model has **no** built-in "I don't know" (§R1.1). If you want a refusal, you must ask for one |
| 4 | If versions disagree, say so | the version label is in the prompt; nothing that has shipped *filters* on it, Phase 3 included (§R1.5) |

**Job 3 is this section**, and job 3 is the only one that has ever changed. It is **necessary**
(without it the model invents APIs) and its wording can **over-fire** (refuse even when the docs
are in the prompt).

> **What R3.3–R3.5 describe is B, the wording that shipped until 2026-08-17.**
> Read it as the history, because the reasoning is the point and the replacement came out of it.
> D's own measurements are in R3.6. The short version: over all 19 probe questions, A and B
> refused the **same 8**, so `D43` had chosen between two options that behave identically. D
> refused those 8 **plus Q16**, a question the corpus cannot answer that B had answered anyway.
> At `DEFAULT_K = 5` every one of D's 9 refusals was correct.

The
shipped sentence was found by trying three wordings, not by writing carefully once.

**Refuse** here means the model prints exactly: `The sources do not answer this.`  
**Answer** means it writes a normal explanation (and should cite `[n]`).

### R3.3 Three prompts, two questions, two ways to be wrong

Only **one sentence** of `SYSTEM` changed. Same model (`qwen2.5-coder:7b`), temperature 0,
same retrieved chunks. That is a controlled test, not three anecdotes.

**The two questions — name them, or the table is noise.**

| column | the question | is the fact in our RST chunks? | what we **want** |
|---|---|---|---|
| **answerable** | *why can't I call `engine.execute` any more?* | **yes** — the migration pages say so | a real answer, with citations |
| **unanswerable** | *what is the exact signature of `Session.execute`?* | **no** — API reference is not in `.rst` (D07 / §R1.4) | a **refusal** |

**The three wordings of that one sentence:**

| | the model is told | default behaviour |
|---|---|---|
| **A** | *If the sources do not contain the answer, say exactly: "The sources do not answer this."* | refusing is the **easy exit**. "Contain the answer" is a high bar — a page that *explains* `engine.execute` without looking like a FAQ still looks like a miss |
| **B** (shipped until 2026-08-17) | *Prefer answering from what the sources do say, even indirectly. Only if they are genuinely silent, then refuse.* | answering is the default; refuse is last resort. Same canned sentence as A, harder to reach |
| **C** | *(that sentence deleted)* | always write an answer. When the sources are empty, the text comes from **weights**, not from `[1]`–`[5]` |

In the tables below, **CAPS + x** = that column's **failure**. Lowercase + ok = that column's
**success**. `REFUSED` on the answerable question is bad. `ANSWERED` on the unanswerable
question is bad. Same English words, opposite columns.

#### What `D43` recorded on 2026-08-15

```
# summary of: 09-DECISIONS.md D43 — the original table
prompt                          answerable      unanswerable
A  canned refusal as the exit   REFUSED  x      refused  ok
B  refusal as last resort       answered ok     refused  ok     <- shipped at the time
C  no refusal clause            answered ok     ANSWERED x
```

A failed left (gave up though the docs were in the prompt). C failed right (invented a
signature). B passed both.

#### What thirteen runs produced — not the same table

`D43` was `n=1` per cell. It has been run **twelve more times**: twice on the Mac on 2026-08-16,
then ten times on the lab PC's RTX 3060 on 2026-08-17, where 62.23 tok/s makes ten runs a
sitting rather than an evening.

```
# summary of: rag/compare_prompts.py, 13 runs across two machines.
#   The "answerable" column is the cell D43 recorded as REFUSED.
prompt                          answerable        unanswerable
A  canned refusal as the exit   refused  1 / 13   refused  13 / 13
B  refusal as last resort       answered 13 / 13  refused  13 / 13    <- shipped at the time
C  no refusal clause            answered 13 / 13  ANSWERED 13 / 13  x
```

**A's over-fire happened once and never again.** `D43`'s original run is the only observation of
it in thirteen.

**C's fabrication is 13 for 13, and it is stable rather than random.** The two Mac runs were not
byte-identical — 1905 characters against 1997 — but every substantive element recurred: the same
four arguments in the same order, down to the same illustrative `sqlite:///example.db`. A model
that invents something different each time looks unreliable; this one repeats itself, which is
what a retrieved fact looks like. **Stability is the property people mistake for correctness.**

**A caveat from `D43` retires here.** It warned the rebuilt index might have changed what was
retrieved. It had not: both Mac runs returned top-5 scores `0.646, 0.642, 0.639, 0.616, 0.615`
in that order. **Retrieval is deterministic** — every difference between runs was generation.

**Honest position, asymmetric:**

| claim | evidence |
|---|---|
| the refusal clause is **necessary** | C fabricates **13 for 13**, the same fabrication each time |
| the strict wording **over-fires** | **1 of 13** — the original observation, never reproduced |
| **B is the one to ship** | **26 of 26 cells** — every run, both machines |

B is the only variant that has **never** been wrong in these runs. That sentence only became
sayable by re-running a decision that was already "done."

What changed on 2026-08-16 was **confidence in half the justification**, not the choice: keep B.
**The next day the choice changed too**, for a reason these two questions could never show. Run
over all 19 probe questions, B turned out to behave exactly like A, and a fourth wording, D, beat
both. R3.6 has that.

> **`D43`'s table is `n=1` per cell, and this is what that costs.** Two questions × three prompts.
> It names a **mechanism**. It cannot name a **rate**. Anyone quoting it as "A fails 100% of the
> time" is overreading. The 13-run table narrows that for these two questions only. Step 5 is
> where the wording met 19 questions (R3.6), and Phase 4 is where it met 100.

### R3.4 How we knew it was the instruction, not search

The symptom (on the original A run): the chatbot printed `The sources do not answer this` for
*"why can't I call `engine.execute` any more?"* while pages 3–5 in the same message *were*
the migration pages that explain that removal.

Two other guesses, both fair. Both killed.

**Guess 1: the 1.4 copy of the page stole a slot.** We keep both versions of many pages, and
they sit almost on top of each other on the map (R1.5). Maybe the useful 2.0 page was crowded
out of the five. **Test:** drop every 1.4 page, and take ten pages instead of five. **Still
refused.**

**Guess 2: search ranked the useful page too low.** That is a real failure mode (R2.6: the
answer is in the files, just not in the top five). **Test:** skip search. Send *only* the
three pages that contain the answer. **Still refused.**

That second test settles it. If it refuses when handed nothing but the answer, search is not
the suspect. The standing rules are.

Reading the paragraph and saying "looks strict" is how the bug survived several reads. It is
not a test.

**The lesson that outlives this bug:** page sizes, 1024 columns, similarity scores all arrived
with numbers attached. The standing rules arrived as English someone typed. **English in a
repo can be wrong.** Treat it like code: change one sentence, hold the rest still, look at
two kinds of question.

### R3.5 "Keep it simple" is not "leave it broken"

The project rule (written down as **D04**): build the dumb version first — search by meaning
only, no extra keyword search, no second-pass reorder. Watch it fail. Then add the extra
machinery as a *fix*, so you can defend why it exists.

Someone can ask: then why rewrite the standing rules? Isn't that cheating?

**D04 says do not add extra search machinery yet. It does not say ship instructions that do
not work.**

The argument, as `D44` made it on 2026-08-15: the file of failures (`deliverables/FAILURES.md`)
exists to show where *search* breaks, so the next phase has a before-number. A broken instruction
sitting in front of search puts its own failure on every row, and then no row tells you anything
about search. **That principle stands.**

**The example it was made with did not survive measurement.** `D44` said that with wording A,
*every* Step 5 question would have failed. Two days later A ran over all 19 questions (`D52`) and
refused **8** — the same 8 as B, question by question. So keeping A would have produced the same
file B did. The instruction that really would have poisoned every row is **C**, which refuses
nothing and so answers the questions the corpus cannot answer, with no sign that it is guessing.
**Deleting the refusal sentence is the bug `D44` protects against; A versus B was never it.**

Say in an interview:

> *"You said the system is bad on purpose. How is that different from actually broken?"*

A **limit we chose** is one we can name before we run: we do not search by exact words yet;
method signatures are not in the `.rst` files. A **bug** is one we found by testing: no
"you may refuse" sentence → invents APIs every time (C, 13 of 13); B answered Q16, a question
the corpus cannot answer, where D refuses it (R3.6). The standing rules were a bug wearing a
limit's clothes.

### R3.6 D replaced B — and what 100 questions later said about D

**Two questions could not tell A from B. Nineteen could.** On 2026-08-17 the lab PC ran every
wording over all 19 probe questions from Step 5 (`D52`, `D53`), at `DEFAULT_K = 5`:

```
# summary of: 09-DECISIONS.md D53 — Round 9, lab PC, 19 probe questions, k=5
prompt    refused  answered   of 19
A               8        11
B               8        11    <- shipped at the time
C               0        19
D               9        10    <- answer partially, refuse only on subject
```

Read it as sentences:

- **A and B refused the same 8, question by question.** The one difference `D43` had seen did not
  exist over 19 questions. `D43` had picked between two options that behave identically.
- **C refused nothing**, so it answered the three questions whose answers are in no chunk at all.
  That is the fabrication from R3.3, now on 19 questions instead of one.
- **D refused the same 8 plus Q16.** Q16 is a question the corpus cannot answer, and B had answered
  it confidently. D's sentence says *name the specific thing you looked for and did not find*.
  Having to name the missing thing is what stopped the model inventing one.

**Were D's other 8 refusals mistakes?** Four of them (Q4, Q6, Q15, Q17) have nothing in the
corpus, so refusing is right. The other four (Q3 `table_names`, Q5 `keys()`, Q18, Q19) *do* have
answers in the corpus, at ranks **23, 12, 8 and 6**. All four are outside the top 5, so the answer
was **not in the prompt**. Refusing a question whose pages you were not given is honest, not an
over-refusal. So at k = 5, **D made no prompt errors on these 19** (`D54`).

**And k stayed 5 because 10 was measured and was worse** (`D54`): at k = 10, Q18 and Q19 had their
answer pages in the prompt and every wording refused anyway, and Q5 got five more near-miss pages
and the model talked itself into a fabricated answer. **More pages did not produce more answers.
They produced two over-refusals and one invention.**

Five repeat runs on the same day came back identical in every cell (`D54`, Round 11), so this
table is not luck at `n=1`. (Across days on the Mac, two items later flipped; `D54`'s scope notes
and `D84` say why that is the Mac's generator.)

#### Then 100 questions, and "no prompt errors" stopped being true

"No errors on 19 probe questions" is a claim about 19 questions. Phase 2 built a 100-question
golden set and Phase 4 ran D over it. The answers are saved, so the counts are derived here from
the files, not typed:

```
# runnable: uv run python -c "
# import json
# from rag import compare_prompts as cp
# for machine, f in (('Mac', 'prompt-sweep-phase4.json'), ('lab', 'prompt-sweep-round16.Linux-x86_64.json')):
#     c = cp.cells(json.load(open('deliverables/' + f))['D'])
#     print(f\"{machine}: page in prompt {c['ceiling']}/{c['n_ans']}   answered with it {c['end_to_end']}   \"
#           f\"refused with it {c['over_with']}   fabricated {c['fabricated']}/{c['n_una']}\")"
Mac: page in prompt 58/91   answered with it 39   refused with it 19   fabricated 2/9
lab: page in prompt 58/91   answered with it 38   refused with it 20   fabricated 2/9
```

- **`page in prompt 58/91`** — of the 91 questions the corpus can answer, search put an answer page
  in the five for 58. Same on both machines, because search is the same computation (`D83`).
- **`refused with it 19` / `20`** — the page was in front of the model and D still said *"The
  sources do not answer this."* That is the over-refusal this file was about, back at scale: **about
  one in three of the questions where search did its job** (19 of 58). Two probe questions (Q18,
  Q19 at k=10) had become 19 golden ones at k=5.
- **`answered with it 39` / `38`** — the number the system actually delivers: 39 of 91 = **0.43**
  on the Mac, 38 of 91 = **0.42** on the lab.
- **`fabricated 2/9`** — of the 9 questions marked unanswerable, D answered 2 (`g056`, `g065`)
  instead of refusing.

**D still ships.** A candidate called H, which moves the citation instruction next to `ANSWER:`,
answered more on the Mac and did not reproduce on the lab (6 fixed, 2 broken), so it was held
(`D83`, `D84`). That story, and how answers get graded rather than counted, is
[`14-MEASURE.md`](14-MEASURE.md) §R6.2 and [`16-JUDGE.md`](16-JUDGE.md) §R8.

**What this is not.** The 19-question result was not wrong. It was true of 19 questions at k = 5.
The golden set asked harder, more varied questions, and the same wording over-refused on a third
of the ones search got right. A prompt that is correct on your test questions is correct on your
test questions.

#### And on this file's own example, D refuses (lab, 2026-09-15)

The question at the top of this file — *"why can't I call `engine.execute` any more?"* — is the one
Phase 1's prompt A refused, and B fixed. **Prompt D had never been run on it.** The 13-run table
is A, B and C; `D52`–`D54` used the 19 probe questions, and this is not one of them. Round 23 ran
all four wordings on it, twice, on the lab PC:

```
# summary of: logs/HANDOFF.md REPLY 23.1 — lab PC, two runs, SUMMARY byte-identical
prompt   answerable                       unanswerable
A        answered  ok                     refused  ok
B        answered  ok                     refused  ok
C        answered  ok                     answered  X   ← fabricates, as always
D        refused   X   ← the shipped one  refused  ok
```

**The answer was in the prompt.** The five pages retrieved for that question today include
`c01569`, the migration guide's section on connectionless execution being removed — which names
`engine.execute` — and `c01573`, one of golden question `g050`'s verified answer chunks.

**And A, B and C were given those same five pages and answered.** That is R3.4's test without
having to run it: retrieval is held still, the wording is the only thing that changes, and the
wording that ships is the one that declines.

| | prompt A, 2026-08-15 | prompt D, 2026-09-15 |
|---|---|---|
| this question | refused (1 of 13 runs) | **refused, 2 of 2 runs** |
| what was wrong | the strict refuse sentence | not diagnosed — D's sentence is the *permissive* one |

**Do not over-read it.** One question, one machine, two runs. `D54` stands: on the 19 probe
questions at k = 5, D made no prompt errors. `D72`'s 19-of-58 still stands as the rate. What this
adds is that the defect reaches **the example this file teaches from**, under the prompt that
ships — and that the prediction written into Round 23 before the run ("expected answered") was
wrong, which is why it was written down first.

#### Two different over-refusals, and the second one no wording fixes (Mac screen, 2026-09-16)

Round 24 asked whether that refusal is one stubborn question or a shape. It took the two golden
questions Phase 3's hybrid search *fixed* into the top five and that are on record as refused with
the page in hand — `g050` (*engine.execute select gone*) and `g044` (*autoload=True without
autoload_with*) — checked the answer page really was in the five, then ran all four wordings on
**those same saved pages**, twice:

```
# summary of: logs/HANDOFF.md MAC SCREEN — Round 24, two runs, identical
          A         B         C          D (ships)
g050      REFUSED   REFUSED   answered   REFUSED
g044      REFUSED   REFUSED   answered   REFUSED
```

**That is not the Round 23 pattern.** There, A and B answered and only D refused. Here **every
wording that contains a refusal sentence refuses**, and the only one that answers is C — the
variant with that sentence deleted.

| | Round 23 (`engine.execute`) | Round 24 (`g050`, `g044`) |
|---|---|---|
| what changes the outcome | **which wording** | **whether the clause exists at all** |
| A, B | answered | refused |
| D (ships) | refused | refused |
| name for it | wording-sensitive over-refusal | the `D54` Q18/Q19 class, on golden items |

**And the model was not stuck.** C's answers are right — `connection.execute` for `g050`,
`autoload_with=engine` for `g044`, matching the verified fixes — and **grounded**: every API name
in that code appears on the five pages it was given (`judge.ungrounded_calls` returns nothing).
So the pages contain a correct answer, the model can write it from them, and three different
refusal sentences stop it.

> **The lever here is not the wording. It is the clause.**

**Which is exactly the trade `D43` measured, so do not reach for the obvious fix.** Delete the
clause and you get C, which also answers the questions the corpus cannot answer — 13 of 13 in the
prompt lab, and again in Round 23. **Both of these are real, and they point in opposite
directions:** the clause prevents invention and causes these refusals. Phase 4 named that tension;
nothing has resolved it.

**Status: measured on both machines, and they agree cell for cell.** The lab ran the same two
steps the same day: identical five pages per item, identical 8 decisions, two runs each. So this
is not a Mac screen any more (`D95` satisfied). Two items, not a rate.

**One difference between the boxes, and it is the familiar one.** On `g050` the lab's D refused
with *"…the specific thing looked for and did not find was how to…"*; the Mac's D refused with the
bare sentence. **Same decision, different prose** — `D84` found exactly that across days on one
machine, and here it shows across two machines. It also means the refusal is the *instructed* one:
D's clause asks the model to name what it looked for, and on the lab it did.

---

## Vocabulary from this sitting

| word | in this project |
|---|---|
| **generation** | after the five pages are chosen: the chatbot reads them and writes a sentence |
| **system prompt** | the standing rules (`SYSTEM`). Same for every question |
| **user prompt** | this question's five pages + the question itself |
| **refusal** | it prints exactly `The sources do not answer this.` instead of explaining |
| **refusal clause** | the sentence that *allows* that. Delete it (prompt C) and it invents APIs |
| **over-firing** | that sentence fires when it should not — A refused `engine.execute` even though those pages were in the message (1 of 13 runs). On the 100 golden questions, D does it on 19 of the 58 where the page was in the prompt (R3.6) |
| **prompt D** | the wording that ships since 2026-08-17 (`D54`): answer what the sources support, refuse only when no source is about the subject, and name what you looked for |
| **n=1** | one try per table cell. Enough to see a mechanism. Not enough to say "A always fails" |
| **unattributable failure** | you cannot tell *why* a later test failed, because a broken instruction sat in front of search |

## Before Sitting 4

Two commands. First: look at the **system paragraph** above the sources, not only the model's
answer. Second: the R3.3 experiment on its two questions, now with all four wordings A, B, C and
D (eight generations; it may not match D43's table).

> **The second command crashed until 2026-09-14.** Its default path used a variable `k` that was
> never defined, so it died with `NameError` before generating anything, from `eeedbc4`
> (2026-08-17) onward. Every other mode of the script passed `k` in, and no test ran the default
> path. Fixed, with two tests in `tests/test_compare_prompts.py` that run it with the model
> stubbed out.

```bash
uv run python -m rag.ask "should I pass future=True to create_engine?" --show-prompt
uv run python -m rag.compare_prompts
```

Ollama must be up (`ollama list` shows `qwen2.5-coder:7b`). The second command needs Qdrant too.

Run `compare_prompts` twice if you can. If a cell **flips**, that is generation being
non-deterministic — a mechanism vs a coin-flip. That is what `n=1` is warning about.

### The three questions, in plain language

**Q1.** We kept a "you may say you don't know" sentence (B). We are **more sure** we need *some*
such sentence than we are that A's strict wording is always harmful. Why? What do you say in an
interview so you don't claim "A always fails" and don't sound like the test was a wash?  
*(R3.3)*

**Q2.** The model said "The sources do not answer this" even though the `engine.execute` pages
were in the prompt. How do you prove that was the **prompt**, not search picking bad chunks?  
*(R3.4)*

**Q3.** Phase 1 is supposed to stay simple (no hybrid search, no reranker). Why was rewriting
the prompt allowed?  
*(R3.5)*

Do not answer Q2 with *"the wording looked strict."* That is how the bug survived several
reads. The answer is a **test that removes search**.

Q1 used to be *"necessary and harmful — which letter proved which?"* That assumed both legs
were equally proven. After 2026-08-16 they are not, so the question was rewritten. A drill
question is a claim; when the evidence moves, the question moves.

### Answers

**Q1 — why "necessary" is the stronger claim, and how to say it**

C failed every time we ran it. A failed once in thirteen. Same number of tries; not the same
strength.

| prompt | what we saw, 13 runs of the two R3.3 questions |
|---|---|
| **C** (no "you may refuse") | invented a `Session.execute(...)` signature **13/13**, the same invention each time |
| **A** (refuse if sources "do not contain the answer") | refused `engine.execute` **1/13** — `D43`'s original run, never again |
| **B** (prefer answering; refuse only if silent) | **26/26** cells correct |

*(An earlier version of this answer said 3/3, 1/3 and 6/6. Those were the counts after the two
Mac re-runs; the ten lab runs on 2026-08-17 had not been added.)*

*Why that is not nitpicking:* "C is why the clause stays" is a **mechanism you can replay**.
"A always over-fires" was written like a mechanism, but 1 in 13 might be luck. Thirteen runs
still cannot tell those apart for A.

*Say in an interview:*

> "If I delete the refuse sentence, the model fabricates an API — that repeated thirteen times,
> so the sentence stays. The stricter wording refused a question it could answer once; I
> could not make that happen again. Over 19 questions the strict and soft wordings behaved
> identically, so I ship a third wording, D, that also refuses the one unanswerable question
> the soft one answered. I am not claiming A fails 100% of the time."

*Not:* "I tried three prompts and picked the nicest." *Also not:* "the experiment failed, so
none of this counts." Weak A evidence does not make C a good idea.

**Q2 — how you know it was the prompt, not search**

Give the model **only** the right pages. If it still refuses, search is not the suspect.

The original A bug: *why can't I call `engine.execute` any more?* → canned refusal, while
those migration pages were already in the prompt.

Two other guesses, both fair, both killed:

1. 1.4/2.0 **twins** stole the five slots (D38 / §R1.5). Test: drop 1.4, raise k to 10. Still
   refused.
2. Search **ranked** the answer too low (R2.6). Test: skip ranking; send only the three
   on-topic chunks. Still refused.

Nothing is left upstream of `SYSTEM`. That is the proof. Reading the paragraph and saying
"looks strict" is not a test.

**Q3 — why fixing the prompt is not cheating D04**

D04 says do not add hybrid search or reranking yet. It does not say leave a **broken**
`SYSTEM` in place.

`FAILURES.md` is supposed to show **retrieval** failures so Phase 3 has a before number. An
instruction bug in front of search puts its own failure on the rows, and those rows stop saying
anything about search.

*Do not use the old example.* This answer used to say that with A, almost every Step 5 row would
have been "refused". Measured over all 19 (`D52`), A refused 8, the same 8 as B. The instruction
that would have spoiled the file is C: no refusal sentence, so it answers the questions the
corpus cannot answer.

*Deliberate limit:* we can name it before we run (no BM25; no API HTML).  
*Bug:* we found it by testing (C fabricates 13 of 13; B answered unanswerable Q16, D refuses it).

---

## Where the rest of the repo lives

| | |
|---|---|
| [`10-RETRIEVAL.md`](10-RETRIEVAL.md) | §R1–§R2: why retrieval exists, and what an embedding is |
| [`09-DECISIONS.md`](09-DECISIONS.md) | **D43** and **D44** are this file in register form |
| [`../deliverables/FAILURES.md`](../deliverables/FAILURES.md) | the Phase 1 deliverable this prompt had to be correct before producing |
| [`../rag/ask.py`](../rag/ask.py) | this section in code — its header comment carries the same table |
