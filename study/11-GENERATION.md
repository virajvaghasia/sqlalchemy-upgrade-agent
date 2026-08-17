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

## If search already picked five pages, what is left to get wrong?

Plenty. A wrong *instruction* at the top of the message can:

- refuse a question whose answer is sitting in those five pages, or
- invent a function signature that is in none of them.

Search did not do that. The English we send with every question did.

| subsection | after it you can say |
|---|---|
| R3.1 | the message has two parts: standing rules (same every time) and this question's five pages |
| R3.2 | one sentence in the standing rules is "you may say you don't know." We need that sentence. The *strict* wording of it can fire when it should not |
| R3.3 | we tried three wordings on two questions. No "you may refuse" → invents APIs every time. Strict refuse → gave up once in three. The middle wording is what ships |
| R3.4 | we proved it was the instruction, not search, by handing the chatbot *only* the right pages. It still refused |
| R3.5 | "keep the first version simple" does not mean "ship a broken instruction" |

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

Here is `SYSTEM` as it ships — read live out of the file (this wording is **B**, not A):

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
Prefer answering from what the sources do say, even if they address the
question indirectly. Only if the sources are genuinely silent on the topic,
reply: "The sources do not answer this." Each source is labelled with the
SQLAlchemy version it documents — if versions disagree, say so rather than
picking one silently.
```

Four jobs in that paragraph:

| # | instruction | why it is there |
|---|---|---|
| 1 | Use only these sources | otherwise the model answers from SQLAlchemy-in-its-weights, which blurs 1.4 and 2.0 (§R1.1) |
| 2 | Cite `[2]` | a claim you can check against source 2 in seconds |
| 3 | **You may refuse** — but only if the sources are genuinely silent | §R1.4: some questions have **zero** chunks (`has_table`). A model has **no** built-in "I don't know" (§R1.1). If you want a refusal, you must ask for one |
| 4 | If versions disagree, say so | the version label is in the prompt; Phase 1 still does not *filter* on it |

**Job 3 is this section.** It is **necessary** (without it the model invents APIs) and the
*strict* wording of it can **over-fire** (refuse even when the docs are in the prompt). The
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
| **B** (ships) | *Prefer answering from what the sources do say, even indirectly. Only if they are genuinely silent, then refuse.* | answering is the default; refuse is last resort. Same canned sentence as A, harder to reach |
| **C** | *(that sentence deleted)* | always write an answer. When the sources are empty, the text comes from **weights**, not from `[1]`–`[5]` |

In the tables below, **CAPS + x** = that column's **failure**. Lowercase + ok = that column's
**success**. `REFUSED` on the answerable question is bad. `ANSWERED` on the unanswerable
question is bad. Same English words, opposite columns.

#### What `D43` recorded on 2026-08-15

```
# summary of: 09-DECISIONS.md D43 — the original table
prompt                          answerable      unanswerable
A  canned refusal as the exit   REFUSED  x      refused  ok
B  refusal as last resort       answered ok     refused  ok     <- shipped
C  no refusal clause            answered ok     ANSWERED x
```

A failed left (gave up though the docs were in the prompt). C failed right (invented a
signature). B passed both.

#### What two re-runs produced on 2026-08-16 — not the same table

**One cell did not reproduce — twice.** Recording that is the point of this subsection.

```
# summary of: three system prompts x two questions, run twice on 2026-08-16
#   against qwen2.5-coder:7b through Ollama, via `uv run python -m rag.compare_prompts`.
#   Both runs produced this table.
prompt                          answerable      unanswerable
A  canned refusal as the exit   answered ok     refused  ok     <- D43 recorded REFUSED
B  refusal as last resort       answered ok     refused  ok
C  no refusal clause            answered ok     ANSWERED x
```

**A / answerable is now 1 refusal in 3 attempts** — D43's original, then two runs that
answered.

**A caveat from D43 can be dropped.** It warned the index might have changed, so the chunks
might differ. They did not: both runs' top-5 scores were `0.646, 0.642, 0.639, 0.616, 0.615`
in that order. **Retrieval is deterministic** here. Every difference between runs is
**generation**. A caveat you can retire is worth more than one you keep repeating.

**C's failure reproduced exactly.** Worth seeing, because it does not look like nonsense:

```
# summary of: prompt C's answer to "what is the exact signature and full argument
#   list of Session.execute?" — the invented signature, argument prose trimmed
def execute(
    statement,
    parameters=None,
    bind_arguments=None,
    execution_options=None,
):
```

Five sources, **none** of which is the API reference. It still emitted a full signature, four
arguments, usage examples.

**The sharp part: that signature is largely correct.** `bind_arguments` and
`execution_options` are real — 5 and 103 chunks mention those *names*, which is not the same
as containing this method's signature (§R1.4's withdrawn example). C is not emitting garbage
you can spot. It is answering from **weights**, and the output does not say "I made this up."
That is §R1.1 inside a system built to stop it. **C proves the refusal clause is necessary,
three times.**

**The fabrication is stable, which is worse than random.** Two runs: 1905 vs 1997 characters,
but the same four arguments, same order, even the same `sqlite:///example.db`. A model that
invented something *different* each time would look unreliable. This one returns the same
confident answer every time — which is what a retrieved fact looks like. **Stability is what
people mistake for correctness.**

**A's over-fire did not reproduce** in either 08-16 run. D43's story (*"do not contain the
answer" is too high a bar*) still *can* happen — it happened once — but it is not a switch
that always flips.

**Honest position, asymmetric:**

| claim | evidence |
|---|---|
| the refusal clause is **necessary** | C fails **3 for 3**, same kind of fabrication |
| the strict wording **over-fires** | **1 of 3** — original observation, not reproduced twice |
| **B is the one to ship** | **6 for 6** — every cell, every run |

B is the only variant that has **never** been wrong in these runs. That sentence only became
sayable by re-running a decision that was already "done."

What changed is **confidence in half the justification**, not the choice. Keep B.

> **`n=1` per cell, and this is what that costs.** Two questions × three prompts. It names a
> **mechanism**. It cannot name a **rate**. Anyone quoting either table as "A fails 100% of
> the time" is overreading. Step 5 is where the shipped wording meets ~20 questions.

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

If we had kept wording A as the default, the file of failures (`deliverables/FAILURES.md`)
would mostly say *"the chatbot refused."* That file exists to show where *search* breaks, so
the next phase has a before-number. One instruction bug copied onto every row is not forty
findings. It is one bug forty times. That is **D44**.

Say in an interview:

> *"You said the system is bad on purpose. How is that different from actually broken?"*

A **limit we chose** is one we can name before we run: we do not search by exact words yet;
method signatures are not in the `.rst` files. A **bug** is one we found by testing: no
"you may refuse" sentence → invents APIs every time; the strict sentence refused a question
it could answer once. The standing rules were a bug wearing a limit's clothes.

---

## Vocabulary from this sitting

| word | in this project |
|---|---|
| **generation** | after the five pages are chosen: the chatbot reads them and writes a sentence |
| **system prompt** | the standing rules (`SYSTEM`). Same for every question |
| **user prompt** | this question's five pages + the question itself |
| **refusal** | it prints exactly `The sources do not answer this.` instead of explaining |
| **refusal clause** | the sentence that *allows* that. Delete it (prompt C) and it invents APIs |
| **over-firing** | that sentence fires when it should not — A refused `engine.execute` even though those pages were in the message (1 of 3 runs) |
| **n=1** | one try per table cell. Enough to see a mechanism. Not enough to say "A always fails" |
| **unattributable failure** | you cannot tell *why* a later test failed, because a broken instruction sat in front of search |

## Before Sitting 4

Two commands. First: look at the **system paragraph** above the sources, not only the model's
answer. Second: the A/B/C experiment from R3.3 (a few minutes; it may not match D43's table).

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

**Short:** C failed every time we ran it. A failed once in three. Same number of tries; not
the same strength.

| prompt | what we saw |
|---|---|
| **C** (no "you may refuse") | invented a `Session.execute(...)` signature **3/3** |
| **A** (refuse if sources "do not contain the answer") | refused `engine.execute` **1/3** — D43 yes, two later runs no |
| **B** (prefer answering; refuse only if silent) | **6/6** cells correct |

*Why that is not nitpicking:* "C is why the clause stays" is a **mechanism you can replay**.
"A always over-fires" was written like a mechanism, but 1-in-3 might be luck. Three runs
cannot tell those apart for A.

*Say in an interview:*

> "If I delete the refuse sentence, the model fabricates an API — that repeated three times,
> so the sentence stays. The stricter wording refused a question it could answer once; I
> could not make that happen again. I still ship the softer wording (B) because it was never
> wrong in any cell. I am not claiming A fails 100% of the time."

*Not:* "I tried three prompts and picked the nicest." *Also not:* "the experiment failed, so
none of this counts." B is still **6/6**. Weak A evidence does not make C a good idea.

**Q2 — how you know it was the prompt, not search**

**Short:** give the model **only** the right pages. If it still refuses, search is not the
suspect.

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

**Short:** D04 says do not add hybrid search / reranking yet. It does not say leave a
**broken** `SYSTEM` in place.

If we had kept A as the default, almost every Step 5 row in `FAILURES.md` would have been
"refused." That file is supposed to show **retrieval** failures so Phase 3 has a before
number. One prompt bug copied onto every row is not forty findings.

*Deliberate limit:* we can name it before we run (no BM25; no API HTML).  
*Bug:* we found it by testing (C fabricates; A over-refused once).

---

## Where the rest of the repo lives

| | |
|---|---|
| [`10-RETRIEVAL.md`](10-RETRIEVAL.md) | §R1–§R2: why retrieval exists, and what an embedding is |
| [`09-DECISIONS.md`](09-DECISIONS.md) | **D43** and **D44** are this file in register form |
| [`../deliverables/FAILURES.md`](../deliverables/FAILURES.md) | the Phase 1 deliverable this prompt had to be correct before producing |
| [`../rag/ask.py`](../rag/ask.py) | this section in code — its header comment carries the same table |
