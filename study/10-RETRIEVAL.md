# Retrieval — study notes

Part of [`sqlalchemy-upgrade-agent`](../README.md). **§R1 onwards** — the retrieval sequence,
which is a third numbering family alongside §0–§22 (SQLAlchemy) and §1–§6 (infrastructure). The
`R` prefix exists so `§R1` can never be misread as `§1`; see [`README.md`](README.md).

This file explains **what Phase 1 is actually doing and why**, from zero. It assumes you know
Python and databases and nothing at all about retrieval or language models.

[`../phases/PHASE-1.md`](../phases/PHASE-1.md) is the *plan* — what was decided and what is
next. This is the *teaching*: the concepts underneath those decisions, with the gaps filled in.

> **Sitting 1 is §R1.** Read it, run the two commands at the end, answer the three questions.
> Then stop. §R2 is the next sitting and is not written yet — it arrives when this one has
> landed.

---

## §R1 — Why this system exists at all

### R1.1 What happens when you just ask the model

Start with the thing we are trying to beat. Here is a real question a developer has:

> *"Why can't I call `engine.execute()` any more?"*

Ask a language model directly and you will get a fluent, confident, well-organised answer. It
may even be right. The problem is that **you have no way to tell**, and the reason is worth
understanding precisely rather than as a slogan.

**What a language model actually does.** It predicts the next piece of text, over and over,
based on everything it has read. It is not looking anything up. There is no index inside it, no
table of facts, no page it consults. Its "knowledge" is a very large number of statistical
patterns baked into fixed weights during training, and by the time you talk to it, those weights
do not change.

That produces two distinct failure modes, and they need separate names because they need
different fixes.

**Failure mode one: it never saw this.** If a fact was not in the training data, or was rare
enough not to leave a trace, the model still answers. It does not have a mechanism for "I have
nothing here." It produces the most plausible-looking continuation, which is a fluent sentence
that happens to be invented. This is the one people mean by "hallucination."

**Failure mode two, and it is the one that matters here: it saw both versions and blended
them.** SQLAlchemy 1.4's documentation and 2.0's documentation are both on the public internet.
Both were almost certainly in the training data. The model read a great deal of text where
`engine.execute()` is completely normal — because in 1.4 it *was* — and a great deal of text
where it raises. **It has no reliable way to tell you which one it is drawing on.**

That second failure mode is why this specific project exists. A migration assistant lives
entirely in the gap between two versions of the same library, which is exactly the gap a
language model's memory blurs.

**And there is a third problem underneath both:** even when the answer is right, you cannot
check it. There is nothing to look at. A confident paragraph with no source is indistinguishable
from a confident paragraph with no basis.

### R1.2 What retrieval changes

The move is simple to state and it is the whole idea:

> **Do not ask the model to remember. Look the answer up first, put it in front of the model,
> and ask it to read.**

Concretely, when a question arrives:

1. **Search** a body of text *you* control for passages relevant to the question.
2. **Paste** the best few passages into the prompt: *"Here are five passages from the SQLAlchemy
   documentation. Answer the question using only these."*
3. **The model reads and summarises**, instead of recalling.

That is **RAG** — **R**etrieval **A**ugmented **G**eneration. Three words, one per stage:
*retrieval* is the lookup, *augmented* means the prompt has been enlarged with what was found,
*generation* is the model writing the answer.

**Why this is a genuine improvement and not a trick**, three reasons:

- **The job gets easier.** "Recall the correct answer about a library you read about years ago"
  is hard. "Read these five paragraphs and answer from them" is much easier — easy enough that a
  small model running on a desktop GPU can do it acceptably, which is what makes
  [`09-DECISIONS.md`](09-DECISIONS.md) **D05** (zero paid API calls) survivable.
- **You control the source.** The model is no longer answering from a blur of everything on the
  internet. It is answering from 270 files you chose deliberately, at two pinned versions.
- **It becomes checkable.** This is the big one. You retrieved five specific passages, so you can
  **print them next to the answer**. If the answer says something those passages do not, you can
  see it.

That last point is why [`../phases/PHASE-1.md`](../phases/PHASE-1.md) Step 4 insists on printing
sources, and says *"sources are not decoration."* Without them there is no way to distinguish a
correct answer from a lucky one — you are back to trusting a fluent paragraph.

**What retrieval does not fix.** The model can still ignore the passages and answer from memory
anyway. It can still misread them. RAG makes the answer *checkable* and *sourced*; it does not
make it *guaranteed*. Phase 2 is where that gets measured rather than hoped for.

### R1.3 The pipeline, named end to end

Every piece has a name, and the names are worth learning now because everything later uses them.

```
BUILD TIME — done once, ahead of any question

  corpus  ──chunk──►  chunks  ──embed──►  vectors  ──►  index (Qdrant)
   270 .rst            3284              one per chunk    searchable
   files               pieces

QUERY TIME — done for every question

  question ──embed──► vector ──search the index──► top-k chunks
                                                        │
                                          prompt ◄──────┘
                                             │
                                             ▼
                                          model (Ollama) ──► answer + sources
```

Read in words:

- **Corpus** — the body of text the system is allowed to look things up in. Ours is 270
  reStructuredText files from SQLAlchemy 1.4.52 and 2.0.51. **This is Step 1, and it is done.**
- **Chunk** — one retrievable piece of the corpus. You do not retrieve whole files, because a
  whole file is mostly irrelevant to any one question. Ours are 3284 pieces averaging about
  1300 characters. **This is Step 2, and it is done.**
- **Embed** — turn a piece of text into a list of numbers that represents its *meaning*. The
  list is called an **embedding** or a **vector**. **This is Step 3, and it is next.**
- **Index / vector database** — a store built to answer one question very fast: *given this
  vector, which stored vectors are closest?* Ours will be Qdrant.
- **top-k** — the k best matches, where k is a small number like 5. You take the top few, not
  everything above a threshold.
- **Generation** — the model reads the top-k and writes the answer. Ours is `qwen2.5-coder:7b`
  through Ollama.

**Notice the shape.** The build-time half runs once and is slow. The query-time half runs on
every question and must be fast. Everything expensive was moved to the left-hand side on
purpose — that is the entire architectural idea of a vector index.

Steps 1 and 2 have already happened, and you can see both:

```
# runnable: uv run python -m rag.corpus --check | head -1
all 270 files match the manifest
```

```
# runnable: uv run python -m rag.chunk | sed -n '3p'
  3284 chunks   3946041 chars
```

### R1.4 The corpus is a ceiling

Here is the idea that makes Step 1 a *step* rather than a download, and it is the single most
important thing in this file.

> **If a fact is not in the corpus, no amount of engineering will ever retrieve it.**

Everything that comes later — hybrid search in Phase 3, reranking, the agent in Phase 5 — is
about **finding the right chunk faster, or more reliably, or ranking it higher**. Not one of
them can find a chunk that does not exist. So whatever you leave out of the corpus is a
permanent hole in what the system can ever do, and every number this project reports for the
next three months is capped by it.

**This is not hypothetical here. We have a hole, and we put it there knowingly.**

The corpus is built from SQLAlchemy's documentation *source* — the `.rst` files in the git
repository. Those files do not contain the API reference. The per-method pages you land on from
a search engine are **generated at build time** from Python docstrings, by directives that look
like this:

```
.. autoclass:: Session
    :members:
```

That is not documentation. It is an *instruction* that says *"when Sphinx builds the HTML, go
read the `Session` class's docstring and paste it here."* In the source, it is an empty promise.
There are 660 such directives in the 1.4 tree and 743 in 2.0.

**The consequence, stated plainly:** ask this system *"what arguments does `Session.execute()`
take?"* and it will fail. Not because retrieval is weak — because the answer is **not in the
pile**. Phase 3 cannot fix it. Phase 5 cannot fix it. The only fix is changing the corpus, which
is a Step 1 decision.

That is what "ceiling" means, and it is why the question *"why this corpus?"* is the one an
interviewer opens with.

### R1.5 Why a bigger corpus is also worse

The instinct is that more data is safer — if in doubt, throw it all in. That instinct is wrong,
and understanding why is what separates someone who has built one of these from someone who has
read about one.

**The mechanism.** Retrieval returns a **fixed number** of chunks. Say k = 5. Those five slots
are all the model will ever see. Every irrelevant chunk in the index is a competitor for those
five slots. It does not sit harmlessly in the corner; it is in the race, every time, for every
question.

So adding text has two effects at once:

- **It can add answers** — good, this is why you add anything.
- **It adds competitors** — bad, and this cost is paid on *every* query, including all the
  queries the new text has nothing to do with.

Text with a poor ratio of answers to volume makes the system worse. Two real cases from our own
corpus decision:

**Case one — `changelog/`, which we excluded.** It is about 60% of SQLAlchemy's documentation
by bytes. Almost all of it is per-release one-line entries like *"Fixed issue in ORM where…"*.
Enormous volume, almost no answers to the questions this system exists for. Including it would
roughly triple the index and fill those five slots with changelog fragments.

**Case two — version skew, and this is the sharp one.** Our corpus deliberately contains *both*
1.4 and 2.0, because half of every migration question is "what did 1.4 do?". But look what that
means. Same page, same tutorial, at the two versions:

```
# runnable: grep -n 'create_engine("sqlite' corpus/raw/*/tutorial/engine.rst
corpus/raw/1.4.52/tutorial/engine.rst:37:    >>> engine = create_engine("sqlite+pysqlite:///:memory:", echo=True, future=True)
corpus/raw/2.0.51/tutorial/engine.rst:36:    >>> engine = create_engine("sqlite+pysqlite:///:memory:", echo=True)
```

1.4 *teaches* you to pass `future=True` — it was the forward-compatibility switch. By 2.0 it is
gone from the tutorial entirely: it appears in 15 files of the 1.4 docs and 3 of the 2.0 docs.

Now trace a question through the system. Someone asks *"should I pass `future=True`?"* The search
finds the 1.4 tutorial — a genuinely excellent, highly relevant, well-written passage about
`create_engine`. The model reads it and answers **yes**.

**Confident. Correctly sourced. Wrong.**

Nothing in the pipeline noticed, because nothing in the pipeline knows which release that page
describes. This is the failure that the whole of Phase 3 exists to fix, and
[`../phases/PHASE-1.md`](../phases/PHASE-1.md) Step 5 is where we go looking for it deliberately.

**We chose not to prevent it.** We could filter to 2.0 only. We did not, because the failure is
the *evidence* Phase 3 is built on, and a filter deletes it before it can be measured. What we
did instead is record the version on every file, so when it happens we can point at the page.
That is **D10** in [`09-DECISIONS.md`](09-DECISIONS.md).

**The general shape**, which shows up everywhere in retrieval:

| | |
|---|---|
| **recall** | of the answers that exist, how many does search find? — bigger corpus helps |
| **precision** | of what search returns, how much is actually relevant? — bigger corpus hurts |

You are always trading one against the other. "Add everything" optimises recall and quietly
destroys precision, and precision is what fills those five slots.

### R1.6 One more, because it is the subtlest

There is a third reason to leave something out, and it has nothing to do with size.

`deliverables/BREAKAGES.md` is this repo's own record of 23 verified 1.4→2.0 breakages, each
with the real error. It is already in question-and-answer shape. Adding it to the corpus would
**measurably improve** the answers — it is exactly the right content, densely relevant, no noise.

We left it out anyway.

**Because it is the answer key.** `BREAKAGES.md` seeds the Phase 2 golden dataset — the set of
questions with known-correct answers that retrieval gets *scored* against. A corpus that contains
the answer key makes Phase 2 measure whether the system can find its own answers. The score goes
up and means less.

This costs real quality now to keep a number honest later. It is **D09**, and it is the decision
most worth being able to explain, because most people have never thought about leakage between
corpus and evaluation set until someone asks.

---

## Vocabulary from this sitting

Say each of these out loud in one sentence before moving on.

| term | one-line meaning |
|---|---|
| **language model** | predicts the next piece of text from fixed weights; does not look anything up |
| **hallucination** | a fluent answer with no basis, produced because the model has no "I don't know" mechanism |
| **RAG** | retrieve passages, add them to the prompt, let the model read rather than recall |
| **corpus** | the body of text the system may look things up in — a hard ceiling on what it can answer |
| **chunk** | one retrievable piece of the corpus; the unit search returns |
| **embedding / vector** | a list of numbers representing a text's meaning |
| **vector database / index** | a store that answers *"which stored vectors are closest to this one?"* fast |
| **top-k** | the fixed number of chunks retrieval hands to the model — the slots everything competes for |
| **recall** | of the answers that exist, how many are found |
| **precision** | of what is returned, how much is relevant |
| **version skew** | a page from the wrong version answering confidently and wrongly |
| **leakage** | evaluation answers present in the corpus, inflating the score |

---

## Before Sitting 2

**Run both, and look at the output rather than the exit code:**

```bash
uv run python -m rag.corpus --check
uv run python -m rag.chunk
```

**Answer these three. If any is shaky, that part of §R1 is where to reread.**

1. *Why does adding more documents to the corpus make the system worse, when it obviously also
   adds more answers?* — R1.5
2. *Our system cannot answer "what arguments does `Session.execute()` take". Why can no amount of
   Phase 3 work fix that?* — R1.4
3. *`BREAKAGES.md` would improve the answers. Why is it deliberately excluded?* — R1.6

**Next sitting, §R2:** what an embedding actually is — how a piece of text becomes a list of
numbers, why similar meanings end up close together, and what "close" means when the things
being compared have a thousand dimensions. That is Step 3, and it is the concept the whole
pipeline turns on.

---

## Where the rest of the repo lives

| | |
|---|---|
| [`../phases/PHASE-1.md`](../phases/PHASE-1.md) | the plan: what was decided, what is next |
| [`09-DECISIONS.md`](09-DECISIONS.md) | every decision with what was rejected — **D09, D10, D05** are cited above |
| [`README.md`](README.md) | this folder's index and the three § numbering families |
| [`../rag/corpus.py`](../rag/corpus.py) | Step 1 in code — its docstring is the short form of R1.4–R1.6 |
| [`../rag/chunk.py`](../rag/chunk.py) | Step 2 in code |
