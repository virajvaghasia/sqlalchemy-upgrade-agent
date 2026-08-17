# Generation — study notes

Part of [`sqlalchemy-upgrade-agent`](../README.md). **§R3 onwards**, continuing the `R` run that
[`10-RETRIEVAL.md`](10-RETRIEVAL.md) started at §R1. A reference to "§R2" resolves there and "§R3"
resolves here; the numbering does not restart, for the same reason `02` continues `01`.

**Why this is a separate file.** §R1 and §R2 are about *retrieval* — choosing a corpus, cutting it
up, turning it into vectors, and searching them. Everything in this file happens **after** search
has finished and the five chunks are already chosen. That is a different subject with different
failure modes, and [`README.md`](README.md) records the split rule this follows.

> **Sitting 3 is §R3.** It assumes §R1 and §R2 have landed — in particular that you can say what
> top-k is, and that the sources printed under an answer are the thing that makes it checkable.

---

## §R3 — The prompt is a component

### R3.1 Where generation sits

Retrieval ends with five chunks. Nothing about them is an answer yet — they are five passages of
documentation, one of which may not even be on topic. **Generation is the step that turns them
into a sentence**, and it is the last thing that happens before a human reads the output.

§R1.2 said RAG is *retrieve, augment, generate*, and then spent two sittings on the first two
words. This one is about the third.

The mechanism is not complicated: build a block of text containing the sources and the question,
hand it to a model, print what comes back. `rag/ask.py` does exactly that, and
`build_prompt()` is nine lines long.

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

**The interesting part is not that code. It is the paragraph of English sitting above it.**

### R3.2 The instruction that is also the bug

Alongside the sources goes a *system prompt* — standing instructions that do not change from
question to question. Ours is one paragraph:

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

Four instructions are in there. The third one — **the permission to refuse** — is the subject of
this section, because it turned out to be simultaneously **necessary and harmful**, and the
wording that threads that gap was found by experiment rather than by writing carefully.

**Why a refusal clause exists at all.** §R1.4 established that the corpus is a ceiling: some
questions have no answer anywhere in the 270 files. The honest output for those is *"I don't
know."* But §R1.1 established that a language model has **no mechanism for "I have nothing
here"** — it produces the most plausible continuation regardless. So if you want a refusal, you
have to ask for one explicitly.

### R3.3 Three prompts, two failure directions

Three wordings were tested against two questions: one the corpus can answer, and one it provably
cannot — the API-reference hole from `D07`.

```
# summary of: 09-DECISIONS.md D43 — the measured table

prompt                          answerable      unanswerable
A  canned refusal as the exit   REFUSED  x      refused  ok
B  refusal as last resort       answered ok     refused  ok     <- shipped
C  no refusal clause            answered ok     ANSWERED x
```

**Read the two failures, because they point in opposite directions.**

**C — no refusal clause — invented a complete method signature for `Session.execute` out of the
model's own weights.** Not a vague answer: a full argument list, fluent and wrong. This is exactly
the hallucination from §R1.1's failure mode one, and it is the reason the clause cannot simply be
deleted. **C proves the clause is necessary.**

**A — strict canned refusal — refused a question whose answer was in its own prompt.** The wording
was *"if the sources do not contain the answer, say exactly: 'The sources do not answer this.'"*
That reads as reasonable. It is not, because **"do not contain the answer" is a very high bar**: a
page that explains `engine.execute` at length, without quoting a FAQ that matches the question's
phrasing, still looks like a miss. **A proves the strict wording over-fires.**

**B threads it** by changing what the model is asked to prefer rather than by changing the bar:
*prefer answering from what the sources do say, even indirectly; refuse only if they are genuinely
silent.* The refusal is a last resort instead of a gate.

> **`n=1` per cell.** Two questions, three prompts. **This is a diagnosis, not a benchmark** — it
> identifies a mechanism, it does not measure how often it fires. Step 5 is where the shipped
> wording meets a list of twenty. Anyone quoting this table as evidence of a *rate* is
> overreading it, and saying so is part of reporting it.

### R3.4 How the cause was found, which matters as much as the answer

The symptom was a refusal on an answerable question. **Two hypotheses were tested and discarded
before the prompt was suspected at all**, and both were reasonable:

- **"The cross-version duplicates are eating top-k slots."** `D38` says 26.6% of the index is a
  1.4/2.0 twin, and §R1.5 shows twins scoring 0.9920 apart — so plausibly the real answer was
  pushed out of the five by a duplicate. **Tested: filtered the duplicates out and raised k to 10.
  It still refused.**
- **"Retrieval ranked the answer too low."** Also plausible, and it is R2.6's failure mode.
  **Tested: fed the model *only* the on-topic chunks — no ranking left to get wrong. It still
  refused.**

That second test is the one that settles it. **If the model refuses when handed nothing but the
answer, the problem cannot be in retrieval.** Everything upstream had been eliminated, and what
remained was the one component nobody had suspected — **because it was hand-written rather than
measured.**

**That is the lesson worth keeping, and it generalises past this bug.** Every other part of this
pipeline arrived with numbers attached: chunk sizes, vector dimensions, similarity scores,
recall@5. The prompt arrived as a paragraph somebody typed, and it was never treated as a
component that could be wrong. **Prose in a codebase does not look like a place bugs live.** It is.

### R3.5 Simple and broken are different things

There is an obvious objection: `D04` says build the naive version first, deliberately bad, so that
hybrid search and reranking are fixes for problems you have *watched happen*. Why fix the prompt?

**Because `D04` withholds architecture, not correctness.** It says: do not add hybrid search or
reranking before you have measured the retrieval failures that justify them. It does not say ship
a component that does not work.

**And the practical cost of getting this distinction wrong is large.** With prompt A in place,
*every* Step 5 question would have failed — and **every one of those failures would have been
unattributable.** `deliverables/FAILURES.md` exists to justify Phase 3 by showing where dense
retrieval breaks. With a broken prompt it would have recorded **one bug, forty times**, dressed as
forty pieces of evidence.

That is `D44`, and the interview question it answers is the sharp one:

> *"You said the system is bad on purpose. How do you tell that apart from actually broken?"*

The answer: a deliberate limitation is one you can name in advance and predict the shape of. A bug
is one you find by testing. The prompt was the second thing wearing the first thing's clothes.

---

## Vocabulary from this sitting

| term | one-line meaning |
|---|---|
| **generation** | the step after retrieval: the model reads the chosen chunks and writes the answer |
| **system prompt** | standing instructions sent with every question, separate from the question itself |
| **refusal clause** | the instruction permitting *"I don't know"* — necessary, because a model has no such mechanism of its own |
| **over-firing** | a rule that triggers when it should not; prompt A refusing an answerable question |
| **n=1** | one observation per cell — enough to identify a mechanism, never enough to state a rate |
| **unattributable failure** | a failure whose cause cannot be assigned, because a known-broken component sat upstream of it |

## Before Sitting 4

**Run this and read the paragraph above the sources, not just the answer:**

```bash
uv run python -m rag.ask "should I pass future=True to create_engine?" --show-prompt
```

**Answer these three:**

1. *The refusal clause is both necessary and harmful. What does each half mean, and which prompt
   proved which?* — R3.3
2. *A model refuses a question whose answer is in its prompt. How do you establish that the
   problem is the prompt rather than retrieval?* — R3.4
3. *Phase 1 is deliberately unsophisticated. Why was fixing this prompt not a violation of that?*
   — R3.5

**A warning about question 2.** "I read the prompt and it looked too strict" is not an answer —
that is how the bug survived being read several times. The answer is a test that eliminates
everything upstream.

## Where the rest of the repo lives

| | |
|---|---|
| [`10-RETRIEVAL.md`](10-RETRIEVAL.md) | §R1–§R2: why retrieval exists, and what an embedding is |
| [`09-DECISIONS.md`](09-DECISIONS.md) | **D43** and **D44** are this file in register form |
| [`../deliverables/FAILURES.md`](../deliverables/FAILURES.md) | the Phase 1 deliverable this prompt had to be correct before producing |
| [`../rag/ask.py`](../rag/ask.py) | this section in code — its header comment carries the same table |
