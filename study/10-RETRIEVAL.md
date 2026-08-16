# Retrieval — study notes

Part of [`sqlalchemy-upgrade-agent`](../README.md). **§R1 onwards** — the retrieval sequence,
which is a third numbering family alongside §0–§22 (SQLAlchemy) and §1–§6 (infrastructure). The
`R` prefix exists so `§R1` can never be misread as `§1`; see [`README.md`](README.md).

This file explains **what Phase 1 is actually doing and why**, from zero. It assumes you know
Python and databases and nothing at all about retrieval or language models.

[`../phases/PHASE-1.md`](../phases/PHASE-1.md) is the *plan* — what was decided and what is
next. This is the *teaching*: the concepts underneath those decisions, with the gaps filled in.

> **Sitting 1 is §R1; sitting 2 is §R2.** Read it, run the commands at the end, answer the four questions.
> Then stop. §R2 is the next sitting and is not written yet — it arrives when this one has
> landed.
>
> **R1.1–R1.6 are concepts; R1.7 is what happened when the concepts met the running system.**
> R1.7 exists because one of R1.5's predictions turned out to be half wrong, and the correction
> is worth more than the original claim. Read it last, not first — it only means something once
> you know what it is correcting.

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

That is **RAG** — **R**etrieval **A**ugmented **G**eneration. Three words, one per stage. The
middle one is the one worth seeing rather than defining.

**Without retrieval, the prompt is only your question:**

```
# illustration
what replaces Query.get()?
```

That is small. The model answers from memory.

**With retrieval, a search runs first and the passages it found are pasted in.** *Augmented*
means exactly this — the same question, in a bigger prompt:

```
# illustration
Here are excerpts from the SQLAlchemy documentation:

  [1] SQLAlchemy 2.0 — changelog/migration_20.rst
      Session.get() is the 2.0 replacement for Query.get()...

  [2] SQLAlchemy 1.4 — orm/queryguide/query.rst
      ...

what replaces Query.get()?

Answer using only the excerpts above, and cite the number.
```

**Same question. Bigger prompt. The extra bytes are the lookup results.**

Nothing magical happens here, and it is worth being clear about what did *not* happen:

- **You did not train the model.** Its weights are identical before and after. It learned nothing.
- **You did not enlarge its knowledge.** Nothing was added to the model at all.
- **You enlarged one request**, by stuffing the found pages into it.

Then *generation* is just the model writing an answer from that stuffed prompt — the ordinary
thing it always does, on text you chose.

`rag/ask.py` builds exactly that second prompt, and `--show-prompt` prints it if you want to see
the real one rather than this sketch.

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
   270 .rst            3284              3284 x 1024      searchable
   files               pieces            float32

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

  **Where those files came from, since it is not obvious.** SQLAlchemy's documentation is not a
  website we scraped. It is written as plain text files that live in SQLAlchemy's own git
  repository under `doc/build/` — the website is *built* from them. So we downloaded two
  snapshots and kept the files we chose:

  ```
  # illustration
  curl -sL https://github.com/sqlalchemy/sqlalchemy/archive/refs/tags/rel_2_0_51.tar.gz | tar xz
  ```

  `rel_2_0_51` is a **tag** — a permanent bookmark on the exact code that became version
  2.0.51. That is why the version is trustworthy. It is not "the docs as of today", which move;
  it is "the docs as they were at that release", which cannot. `rag/corpus.py` does this for
  both versions and records a SHA-256 per file so you can prove nothing changed underneath.
- **Chunk** — one retrievable piece of the corpus. You do not retrieve whole files, because a
  whole file is mostly irrelevant to any one question. Ours are 3284 pieces with a **median of
  1299 characters and a mean of 1202**. **This is Step 2, and it is done.**

  *Two numbers rather than one, on purpose.* An earlier draft of this file said "averaging about
  1300", which was the **median** wearing the word "average" — the mean is 1202, and 1300 appears
  nowhere in the stats file. The gap is small but it is not noise, and what causes it is worth
  seeing, because it is the chunker's design showing up in the arithmetic:

  ```
  # runnable: uv run python -c "import json,sys; n=sorted(json.loads(l)['n_chars'] for l in open('corpus/chunks.jsonl')); \
  #   [print(f'{lo:5d}-{hi:<5d} {sum(1 for x in n if lo<=x<hi):5d}  {100*sum(1 for x in n if lo<=x<hi)/len(n):5.1f}%') \
  #    for lo,hi in [(0,300),(300,600),(600,900),(900,1200),(1200,1500),(1500,1800),(1800,2400),(2400,6000)]]"
      0-300     170    5.2%
    300-600     357   10.9%
    600-900     453   13.8%
    900-1200    463   14.1%
   1200-1500    720   21.9%
   1500-1800   1015   30.9%
   1800-2400     72    2.2%
   2400-6000     34    1.0%
  ```

  Read the shape. **Nearly a third of all chunks land in 1500–1800** — they piled up against
  `TARGET = 1800`, because the packer keeps adding blocks until the next one would breach it. Only
  **3.2% get past 1800** at all. So the distribution has a **ceiling on the right and no floor
  pushing up the left**: the small chunks (a section that was simply short) have nothing to
  balance them, and they pull the mean *below* the middle value.

  That is the general lesson, and it costs nothing to learn now: **a mean and a median that
  disagree are telling you the distribution is lopsided, and which way.** Quoting one and calling
  it the other hides exactly that. Whenever you see a single "average" for a spread of values,
  ask which one it is.
- **Embed** — turn a piece of text into a list of numbers that represents its *meaning*. The
  list is called an **embedding** or a **vector**. Ours are **1024 numbers per chunk**, from a
  model called BGE-M3. **This is Step 3, and it is built** — 3284 vectors, in `embeddings.npy`.
- **Index / vector database** — a store built to answer one question very fast: *given this
  vector, which stored vectors are closest?* Ours is Qdrant. **This is Step 3b, and it is built.**
- **top-k** — the k best matches. Ours is **`DEFAULT_K = 5`** in
  [`../rag/ask.py`](../rag/ask.py). You take the top few, not everything above a threshold — so
  five slots is a hard budget, which is the mechanism R1.5 turns on.
- **Generation** — the model reads the top-k and writes the answer. Ours is `qwen2.5-coder:7b`
  through Ollama. **This is Step 4, and it is built** — [`../rag/ask.py`](../rag/ask.py).

**Status, as of the current commit: all five steps are BUILT. Phase 1 is not COMPLETE.** The
difference is deliberate and it is the honest bit: three of the phase's own gates are still open,
and every one of them requires a human — eyeball ten chunks, mark 19 answer verdicts, answer five
questions cold. A step is not done because the script ran and the output looked plausible.
[`../phases/PHASE-1.md`](../phases/PHASE-1.md) lists the open gates.

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

> ⚠️ **That second command is not read-only, and the trap is worth more than the number.**
> `rag/chunk.py` writes `corpus/chunks.jsonl` and `corpus/CHUNK_STATS.json` **every time it runs**
> — including with `--sample`, which writes *before* it prints the samples. It is safe here only
> because the chunker is deterministic, so re-running reproduces the file byte-for-byte.
>
> It is **not** safe while anything downstream is mid-run. `embeddings.npy` is row-aligned to
> `chunks.jsonl` by position: row *i* is chunk *i*. Rewrite the chunks under a running embed and
> you get an index whose vectors point at the wrong text — **and nothing errors.** Search keeps
> returning results; they are just attached to the wrong sources.
>
> To read the same numbers without writing anything:
>
> ```
> # runnable: uv run python -c "import json; s=json.load(open('corpus/CHUNK_STATS.json')); print(s['n_chunks'], s['n_chars'])"
> 3284 3946041
> ```
>
> The general habit: **before running a "verification" command, check whether it mutates the thing
> it verifies.** A surprising number of them do.

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

**How many promises?** The number that matters is the one inside the pile we actually indexed,
and it is reproducible from `corpus/raw/` with nothing downloaded:

```
# runnable: for v in 1.4.52 2.0.51; do printf '%-8s %4d\n' "$v" \
#   "$(grep -rhoE '\.\. auto(class|function|module|method|attribute)::' corpus/raw/$v --include='*.rst' | wc -l | tr -d ' ')"; done
1.4.52    514
2.0.51    569
```

**1083 directives in our corpus that resolve to nothing.** Each one is a place where a reader of
the rendered website would find a method signature and a parameter list, and where our retriever
finds two lines of Sphinx configuration.

The same count over the *full* documentation tree — every `.rst` in the tag, including everything
Step 1 excluded — is **660 and 743**. That is the figure quoted in
[`../phases/PHASE-1.md`](../phases/PHASE-1.md) Step 1, and it needs a download to reproduce:

```
# runnable: for t in rel_1_4_52 rel_2_0_51; do curl -sL \
#     "https://github.com/sqlalchemy/sqlalchemy/archive/refs/tags/$t.tar.gz" \
#     | tar xz "sqlalchemy-$t/doc/build"; done
#   for t in rel_1_4_52 rel_2_0_51; do printf '%-11s %4d\n' "$t" \
#     "$(grep -rhoE '\.\. auto(class|function|module|method|attribute)::' sqlalchemy-$t/doc/build --include='*.rst' | wc -l | tr -d ' ')"; done
rel_1_4_52   660
rel_2_0_51   743
```

**Two numbers, and the difference between them is the point of Step 1.** 660 is what SQLAlchemy
ships; 514 is what survived our selection. Neither is wrong — they answer different questions, and
a number is only meaningful once you say which pile it counted. Quote the corpus figure when
arguing about *this system's* ceiling; quote the tree figure when arguing about *reStructuredText
source in general*.

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
gone from the tutorial entirely:

```
# runnable: for v in 1.4.52 2.0.51; do printf '%-8s %2d files\n' "$v" \
#   "$(grep -rl 'future=True' corpus/raw/$v --include='*.rst' | wc -l | tr -d ' ')"; done
1.4.52   13 files
2.0.51    2 files
```

**13 files against 2.** In the *full* documentation tree it is **15 against 3**, and the three
files that account for the whole difference are worth naming, because each one is Step 1 doing
what it was told:

| version | file dropped | why |
|---|---|---|
| 1.4.52 | `changelog/migration_14.rst` | the rest of `changelog/` is excluded |
| 1.4.52 | `changelog/migration_20.rst` | kept from **2.0 only** — the 2.0 copy is the current one |
| 2.0.51 | `changelog/migration_14.rst` | the rest of `changelog/` is excluded |

Same discipline as R1.4: **say which pile you counted.** 15/3 is true of SQLAlchemy's docs; 13/2
is true of this system. Only the second one predicts what our retriever can return.

Now trace a question through the system. Someone asks *"should I pass `future=True`?"* The search
finds the 1.4 tutorial — a genuinely excellent, highly relevant, well-written passage about
`create_engine`. The model reads it and answers **yes**.

**Confident. Correctly sourced. Wrong.**

Nothing in the pipeline noticed, because nothing in the pipeline knows which release that page
describes. This is the failure that the whole of Phase 3 exists to fix, and
[`../phases/PHASE-1.md`](../phases/PHASE-1.md) Step 5 is where we go looking for it deliberately.

#### And now it can be measured, not just asserted

Everything above was written before Step 3 existed, so it was an argument. Step 3 is now built,
which means the claim *"nothing in the pipeline can tell the two versions apart"* stops being a
prediction and becomes a number.

**One idea you need first, and only one.** Step 3 turned every chunk into a list of numbers (§R2
explains how, and it is the next sitting). Once that exists you can ask how close any two chunks
are, and the answer comes out as a single score called **cosine similarity**:

- **1.0** means *pointing in exactly the same direction* — as far as the system is concerned, the
  same meaning.
- **0.0** means unrelated.
- Anything **above about 0.95** means the system cannot meaningfully tell them apart.

You do not need to know how the numbers are produced to read the result. Treat it for now as
*"how close does this system think these two passages are?"*, and ask §R2 for the mechanism.

**Start with the two pages from the grep above** — the 1.4 and 2.0 versions of the engine
tutorial. Chunk `c01464` is the 1.4 one. What are its nearest neighbours in the whole corpus?

```
# runnable: uv run python -c "
# import json,numpy as np
# r=[json.loads(l) for l in open('corpus/chunks.jsonl')]; V=np.load('corpus/embeddings.npy')
# q=next(i for i,c in enumerate(r) if c['id']=='c01464')
# s=V@V[q]
# for i in np.argsort(-s)[:4]:
#     print(f\"{s[i]:.4f}  {r[i]['sqlalchemy_version']}  {r[i]['id']}  {r[i]['source_path'].split('doc/build/')[-1]}\")
# "
1.0000  1.4.52  c01464  tutorial/engine.rst
0.9691  2.0.51  c03211  tutorial/engine.rst
0.8611  1.4.52  c01139  orm/quickstart.rst
0.8343  1.4.52  c01296  orm/tutorial.rst
```

Row one is the chunk matching itself, which is why it is exactly 1.0. **Row two is the 2.0 twin at
0.9691** — and the gap down to row three (0.8611) is enormous by comparison. The system is telling
you, correctly, that these two passages are about the same thing.

Now look at everything that differs between those two chunks:

```
# runnable: uv run python -c "
# import json,difflib
# r={json.loads(l)['id']: json.loads(l) for l in open('corpus/chunks.jsonl')}
# print('\n'.join(l for l in difflib.unified_diff(
#     r['c01464']['text'].splitlines(), r['c03211']['text'].splitlines(), lineterm='', n=0)
#     if l[:1] in '+-' and not l.startswith(('---','+++'))))
# "
-:class:`_future.Engine`.   This object acts as a central source of connections
+:class:`_engine.Engine`.   This object acts as a central source of connections
-set up.  The :class:`_future.Engine` is created by using :func:`_sa.create_engine`, specifying
-the :paramref:`_sa.create_engine.future` flag set to ``True`` so that we make full use
-of :term:`2.0 style` usage:
+set up.  The :class:`_engine.Engine` is created by using the
+:func:`_sa.create_engine` function:
-    >>> engine = create_engine("sqlite+pysqlite:///:memory:", echo=True, future=True)
+    >>> engine = create_engine("sqlite+pysqlite:///:memory:", echo=True)
-This string indicates to the :class:`_future.Engine` three important
+This string indicates to the :class:`_engine.Engine` three important
```

**Four edits — and one of them is the entire answer to the question.** 1.4 says *"specifying the
`future` flag set to `True`"*. 2.0 deleted that sentence. To a human those two passages give
opposite advice. To the retriever they are 0.9691 apart, which is to say: the same.

**How widespread is this?** Take every 1.4 chunk and find its closest 2.0 chunk:

```
# runnable: uv run python -c "
# import json,numpy as np
# r=[json.loads(l) for l in open('corpus/chunks.jsonl')]; V=np.load('corpus/embeddings.npy')
# a=[i for i,c in enumerate(r) if c['sqlalchemy_version']=='1.4.52']
# b=[i for i,c in enumerate(r) if c['sqlalchemy_version']=='2.0.51']
# best=(V[a]@V[b].T).max(axis=1)
# for t in (0.99,0.95,0.90):
#     print(f'>= {t:.2f}  {int((best>=t).sum()):5d} of {len(a)}  ({100*(best>=t).mean():.1f}%)')
# print(f'median {np.median(best):.4f}   min {best.min():.4f}')
# "
>= 0.99    792 of 1541  (51.4%)
>= 0.95   1065 of 1541  (69.1%)
>= 0.90   1182 of 1541  (76.7%)
median 0.9920   min 0.6204
```

**Read the median: 0.9920.** For a *typical* 1.4 chunk there exists a 2.0 chunk that the system
considers all but identical. **Over half the 1.4 corpus has a 2.0 twin at 0.99 or above.**

This is the sentence to take away, and it is stronger than anything the prose above claimed:

> **The vector space does not encode version.** Not "encodes it weakly" — the two releases of a
> page land essentially on top of each other. When a question lands near a twin pair, which twin
> wins a top-k slot is decided in the fourth decimal place, which is to say: by noise.

**And this tells you what the fix has to be.** A better *meaning* search cannot separate two
passages that mean the same thing — that is not a flaw in the search, it is the search working.
Reranking does not help either, because a reranker reads the same near-identical text. The only
things that can separate them are the things that are **not** in the text: the version label we
recorded on every file in Step 1, used as a **filter** or a routing rule. That is why **D10**
(record skew, do not prevent it) had to keep the label even though Phase 1 never uses it — Phase 3
cannot invent it later.

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

### R1.7 What happened when we actually ran it

Everything above R1.6 was written while Steps 3–5 were still plans. They are now built, and the
system has been asked the very question R1.5 walks through. **The prediction was half right, and
the half that was wrong is more interesting than the half that was right.**

[`../deliverables/FAILURES.md`](../deliverables/FAILURES.md) question **#7** is literally
*"should I pass future=True to create_engine?"*. What came back:

> *"Yes, you should pass `future=True` to `create_engine`. This is necessary for enabling the new
> 2.0 API in SQLAlchemy and ensuring compatibility with the upcoming version [1]."*

**Wrong, in the way R1.5 predicted — and sourced from a document R1.5 did not predict.** R1.5 says
the search will find *the 1.4 tutorial*. It did not. It found this:

```
# summary of: deliverables/FAILURES.md entry 7  (RST role markup stripped for reading;
#   the verbatim chunk, with :class:`_engine.Engine` etc. intact, is in that file)
[1]  0.659 · SQLAlchemy 2.0.51 · doc/build/changelog/migration_20.rst
     "Migration to 2.0 Step Four - Use the ``future`` flag on Engine"

     The Engine object features an updated transaction-level API in version 2.0.
     In 1.4, this new API is available by passing the flag future=True to the
     create_engine function.
```

Read that source carefully, because three separate things are going on and they are all worth
learning:

**One — the retrieved page is a 2.0 page.** So the obvious fix, *"just filter the corpus to 2.0
and the skew problem goes away"*, **would not have caught this.** If you take one thing from R1.7,
take that. A version filter is a real improvement and it is not sufficient.

**Two — the passage is version-*conditional*, and the condition is the whole answer.** It says
*"**In 1.4**, this new API is available by passing the flag `future=True`."* A human reads the
opening two words and knows this does not apply to them. The model dropped them and reported the
recommendation as current. The give-away is in its own wording: it wrote *"compatibility with the
**upcoming** version"* — but 2.0 is not upcoming, it is the version being asked about. That phrase
leaked out of 1.4-era framing inside a 2.0 file.

So version skew is not only *"a page from the wrong version"*. It is also **a page from the right
version that describes the wrong version**, and no metadata on the file can catch that, because
the file's metadata is correct.

**Three — the system retrieved its own correction and did not use it.** Result `[2]` was
`core/future.rst` at 2.0, which says the `future` parameter *"continues to remain available for
backwards-compatibility support, however if specified must be left at the value of `True`"* — in
other words, in 2.0 it does nothing. **The right nuance was in the top-k and the answer cited only
`[1]`.** That is the `single_source` signal recorded on the entry, and it is a *generation*
failure sitting on top of a retrieval failure. Note what made it visible: the sources were
printed. This is R1.2's *"it becomes checkable"* paying out, exactly once, in a real case.

**The verdict on #7 is `UNVERIFIED`, and that is not an oversight.** All 19 entries in
`FAILURES.md` are unverified, and marking them is a human gate — the golden dataset is
hand-verified, never auto-generated ([`09-DECISIONS.md`](09-DECISIONS.md) **D09**'s sibling
principle). A system that grades its own homework reports whatever number you wanted.

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
| **embedding / vector** | a list of numbers representing a text's meaning — ours are 1024 long |
| **cosine similarity** | one score for how close two texts are: 1.0 = the same direction, 0.0 = unrelated. Above ~0.95 the system cannot tell them apart. Qdrant is configured with `Distance.COSINE` |
| **vector database / index** | a store that answers *"which stored vectors are closest to this one?"* fast |
| **top-k** | the fixed number of chunks retrieval hands to the model — the slots everything competes for. Ours is `DEFAULT_K = 5` |
| **recall** | of the answers that exist, how many are found |
| **precision** | of what is returned, how much is relevant |
| **version skew** | **two shapes.** (a) a page from the *wrong* version answering confidently and wrongly; (b) a page from the *right* version whose prose is conditional on another version — *"in 1.4, do X"*. A version filter catches (a) and not (b); see R1.7 |
| **leakage** | evaluation answers present in the corpus, inflating the score |

---

## Before Sitting 2

**Run these, and look at the output rather than the exit code.** All three are read-only — none of
them writes anything, for the reason given in the warning box in R1.3:

```bash
uv run python -m rag.corpus --check
uv run python -c "import json; s=json.load(open('corpus/CHUNK_STATS.json')); print(s['n_chunks'], s['n_chars'])"
uv run pytest
```

**Answer these four. If any is shaky, that part of §R1 is where to reread.**

1. *Why does adding more documents to the corpus make the system worse, when it obviously also
   adds more answers?* — R1.5
2. *Our system cannot answer "what arguments does `Session.execute()` take". Why can no amount of
   Phase 3 work fix that?* — R1.4
3. *`BREAKAGES.md` would improve the answers. Why is it deliberately excluded?* — R1.6
4. *We already have a `--version` filter. Question #7 still got the wrong answer from a correctly
   labelled 2.0 page. Why didn't the filter save it?* — R1.7

**A warning about question 4.** The tempting answer is *"the filter wasn't switched on"*. That is
not it, and reaching for it means R1.7 has not landed. Reread the source passage and notice what
its first two words are.

**Next sitting, §R2:** what an embedding actually is — how a piece of text becomes a list of
numbers, why similar meanings end up close together, and what "close" means when the things
being compared have a thousand dimensions. That is Step 3, and it is the concept the whole
pipeline turns on.

---

---

## §R2 — What an embedding actually is

> **Sitting 2.** §R1 said an embedding is "a list of numbers representing meaning" and moved on.
> That sentence is true and useless. This section makes it concrete, using the 3284 vectors
> already sitting in `corpus/embeddings.npy`.

### R2.1 The problem it solves

A computer can compare two strings for equality. It cannot compare them for **meaning**.

`"close a session"` and `"terminate a connection"` share no words at all. A database `LIKE`, a
`grep`, a hash — every exact-matching tool says these are unrelated. To a person they are nearly
the same sentence.

That is the whole problem. **You need a way to turn text into something arithmetic can compare**,
where "arithmetic" gets the answer a person would.

### R2.2 A vector is a position

Take a much smaller idea first. Suppose you described every document with exactly two numbers:

```
                 formal
                    ▲
                    │   • the migration guide
                    │
                    │             • the FAQ
    about-code ─────┼────────────────────► about-prose
                    │
       • a code     │
         example    │
                    ▼
                 casual
```

Each document is now a **point**. Two points close together mean two documents that are alike on
those two axes. You can now *measure* similarity — with a ruler.

An embedding is that idea, with two changes:

- **The axes are not named.** Nobody decided "axis 1 = formality". The model learned 1024 axes
  during training, and no human knows what most of them mean. They are not interpretable, and
  that is fine — you never read them, you only compare them.
- **There are 1024 of them, not 2.** Meaning has more than two independent dimensions, and
  cramming it into two would put unrelated things on top of each other.

**What the model does** is take text in and produce a position out, having been trained so that
text people consider similar comes out at nearby positions. That is the entire trick.

### R2.3 What our vectors actually are

Not a metaphor — the file on disk:

```
# runnable: uv run python -c "
#   import numpy as np; V = np.load('corpus/embeddings.npy')
#   print(f'shape {V.shape}  dtype {V.dtype}  bytes {V.nbytes}')
#   print('first 6 numbers of the first vector:', np.round(V[0][:6], 4).tolist())
#   print('norm of every vector: min %.6f max %.6f' % (
#       np.linalg.norm(V, axis=1).min(), np.linalg.norm(V, axis=1).max()))"
shape (3284, 1024)  dtype float32  bytes 13451264
first 6 numbers of the first vector: [0.0213, 0.0288, -0.0193, 0.0272, -0.0565, -0.0498]
norm of every vector: min 1.000000 max 1.000000
```

**3284 rows, one per chunk. 1024 columns, one per learned axis. 13 MB.** That is the entire
"understanding" the retrieval half of this system has.

Every one of those numbers is worth being able to explain, so:

**`3284 × 1024` is a table.** Literally a spreadsheet — 3284 rows, one per chunk, and 1024
columns, one per number the model produces:

```
# illustration
            dim 1    dim 2    dim 3   ...   dim 1024
chunk 1     0.0213   0.0288  -0.0193  ...    -0.0498
chunk 2     ...
   ...
chunk 3284
```

A **dimension** is one slot in that list. Nothing more mysterious than a column.

**3284 is a consequence, not a decision.** Nobody chose it. Feed 3946041 characters to a
chunker aiming at 1800 and never splitting a code block, and 3284 pieces fall out —
3946041 ÷ 3284 = **1202 characters** each on average. Aim for 900 instead and you get roughly
twice as many. **The decision was 1800; the count is arithmetic.**

**`float32` splits into two words.** *float* — a number with a decimal point, `0.0213` rather
than `3`. *32* — how many bits each one takes, which is **4 bytes**. Which makes the file size
multiplication rather than mystery:

```
# runnable: python3 -c "print(3284*1024*4, 'bytes')"
13451264 bytes
```

**That is exactly the `bytes 13451264` printed above.** Nothing is hidden in the format.

**What the 32 bits actually buy.** They hold roughly **7 significant decimal digits**. Our
numbers look like `0.0213` and every one sits between -1 and 1, so float32 can tell apart values
about `0.0000001` apart.

**Why that is far more than enough here.** The only thing this system does with these numbers is
add up 1024 products and compare the totals — and it only needs the **ordering** to come out
right (§R2.5). The gaps that decide an ordering are large: the top hit for *"why can't I call
engine.execute any more?"* scored 0.633 against a 0.540 baseline, a gap of **0.09**. float32
resolves about 0.0000001. **That is a million times finer than the difference being judged.**
Precision is not the binding constraint, and it is worth knowing which constraint is.

Now the neighbours:

| | bytes each | our file would be | |
|---|---|---|---|
| `float16` | 2 | **6.7 MB** | half the size, ~3 decimal digits |
| **`float32`** | **4** | **13 MB** | what the model computes in |
| `float64` | 8 | 26 MB | double the disk for digits that were never computed |

**`float64` is the easy one to reject.** The model *produced* float32. Storing it wider cannot
add accuracy — there is no eighth digit to store, so you are padding real numbers with zeros.
Double the file for nothing. **A bigger number type is not a more accurate one; it is only a
bigger container.**

**`float16` is the interesting one, because it is genuinely tempting.** It halves the file and
~3 decimal digits still clears a 0.09 gap comfortably. So why not?

**Because at 13 MB there is nothing to buy.** Saving 6.7 MB solves no problem — the file loads
instantly, fits in memory ten times over, and copies in a second. You would take on a real risk
(precision that is fine *now*, and might not be after Phase 3 adds reranking, where scores get
compared much more finely) in exchange for a saving nobody can feel.

**That answer is scale-dependent, and saying so is the point.** At 10 million chunks the same
array would be 40 GB in float32 and 20 GB in float16, and then it is a genuine decision with
real money attached. **Here it is not a decision at all** — which is why the honest reason for
float32 is *"the model emits it and nothing forces us off it"*, not a performance argument we
never made.

Note the last line: **every vector has length exactly 1.0.** That is not a coincidence, it is
`normalize_embeddings=True` in `rag/embed.py` (D36). Every position has been pushed out onto the
surface of a sphere, all the same distance from the origin — so only the *direction* carries
meaning, never the magnitude. The next section is why that matters.

### R2.4 "Close" means the angle between them

With everything on a unit sphere, similarity is the **cosine of the angle** between two
directions:

| angle | cosine | means |
|---|---|---|
| 0° | **1.0** | same direction — as similar as the model can say |
| 90° | **0.0** | unrelated |
| 180° | **-1.0** | opposite |

And here is the payoff for normalising: **for unit vectors, the cosine is just the dot product**
— multiply the pairs and add. That is one instruction on a CPU, over 1024 numbers. It is why
searching 3284 chunks takes no perceptible time, and it is what `vectors @ query` does in
`rag/index.py`.

Measured against a real chunk — `c01464`, the 1.4 tutorial paragraph about `create_engine`:

```
# runnable: uv run python -c "
#   import json, numpy as np
#   r=[json.loads(l) for l in open('corpus/chunks.jsonl')]; V=np.load('corpus/embeddings.npy')
#   q=next(i for i,c in enumerate(r) if c['id']=='c01464')
#   s=V@V[q]; order=np.argsort(-s)
#   for i in list(order[1:4]) + list(order[-2:]):
#       print(f\"{s[i]:.4f}  {r[i]['sqlalchemy_version']}  {r[i]['source_path'].split('doc/build/')[-1]}\")"
0.9691  2.0.51  tutorial/engine.rst
0.8611  1.4.52  orm/quickstart.rst
0.8343  1.4.52  orm/tutorial.rst
0.3925  2.0.51  orm/queryguide/columns.rst
0.3820  2.0.51  orm/queryguide/columns.rst
```

**The nearest thing to the 1.4 `create_engine` paragraph is the 2.0 `create_engine` paragraph,
at 0.9691.** Nobody told the model those two pages correspond. It has never seen a version
number. It placed them next to each other because they say nearly the same thing — which is
exactly the behaviour §R1.5's version-skew problem depends on.

And the furthest things are query-guide pages about selecting columns. Different subject,
different neighbourhood.

### R2.5 The number is not a percentage — and this one catches everyone

`0.8343` looks like "83% similar". It is not. **You cannot read a cosine score without knowing
what the baseline is for your model**, and for BGE-M3 on this corpus the baseline is high:

```
# runnable: uv run python -c "
#   import numpy as np
#   V=np.load('corpus/embeddings.npy')
#   rng=np.random.default_rng(7); idx=rng.choice(len(V),4000)
#   s=(V[idx[:2000]]*V[idx[2000:]]).sum(1)
#   print('random pairs      mean %.3f  min %.3f  max %.3f' % (s.mean(), s.min(), s.max()))"
random pairs      mean 0.540  min 0.329  max 1.000
```

**Two chunks picked at random score 0.540 on average.** Nothing in this corpus scores near zero;
the floor is about 0.33. So the usable range is roughly **0.33 to 1.0**, not 0 to 1, and it is
squashed into the top half.

Consequences worth carrying:

- **A score of 0.63 — the top hit for *"why can't I call engine.execute any more?"* — is not
  "63% confident".** It is *0.09 above what two unrelated chunks score*. That is a much weaker
  signal than the number looks.
- **A fixed threshold like "only return hits above 0.7" is a guess** unless you have measured
  your own baseline. Copied from a tutorial written against a different model, it will either
  return everything or nothing.
- **Only the ordering is trustworthy**, which is why retrieval takes top-k rather than
  everything above a cutoff (§R1.3). Rank is robust; the absolute number is not.

### R2.6 What this cannot do, and Step 5 measured it

Meaning-space has a blind spot, and it is the mirror image of its strength.

`Query.from_self` and `Query.filter` are, to an embedding model, almost the same thing: both are
`Query` methods, in the same docs, in near-identical sentences. Their *meanings* genuinely are
close. But if you asked about one and got the other, the answer is simply wrong — **an exact
symbol name is not a fuzzy concept, and the model has no way to know that.**

That is not theory. Step 5 ran it:

```
symbol            in corpus   retrieved   so the failure is
table_names        6 chunks       ✗       retrieval — the answer was there
keys()             7 chunks       ✗       retrieval
cascade_backrefs  12 chunks       ✗       retrieval
has_table          0 chunks       ✗       the ceiling — nothing to find
```

**Three questions where the answer existed and meaning-search did not find it.** The `symbol`
category has the worst results of any in `deliverables/FAILURES.md`.

**This is the argument for hybrid search**, and it is now a measured argument rather than the
borrowed one. §R1 quoted the roadmap's example — *"what replaces `Query.get()`"* — which turned
out **not** to fail (D39: ranked 1 of 3284). The claim was right; the illustration was wrong.
Keyword search would nail `table_names` precisely because it is a literal string, and that is
Phase 3.

---

## Vocabulary from this sitting

| term | one-line meaning |
|---|---|
| **vector / embedding** | a position in a space with many axes, produced from text |
| **dimension** | one axis. Ours has 1024, none of them individually meaningful |
| **normalised / unit vector** | pushed to length exactly 1, so only direction carries meaning |
| **cosine similarity** | the angle between two directions; for unit vectors, a dot product |
| **baseline similarity** | what two *unrelated* items score. Ours is **0.540**, not 0 |
| **dense retrieval** | search by these positions — what Phase 1 does |
| **sparse retrieval / BM25** | search by literal words. Nails exact symbols; Phase 3 |

## Before Sitting 3

**Run these two and look at the numbers, not the exit code:**

```bash
uv run python -m rag.ask "how do I use joinedload?" --retrieval-only
uv run python -m rag.compare_embedders
```

**Answer these three:**

1. *Every vector in our file has length exactly 1.0. What does that buy, and what does it throw
   away?* — R2.3, R2.4
2. *A search returns a top hit at 0.61. Is that good? What do you need to know before you can
   say?* — R2.5
3. *`table_names` appears in 6 chunks and retrieval did not find any of them. Why is that a
   different problem from `has_table`, which appears in 0?* — R2.6

**Next sitting, §R3:** the prompt — why the model refuses answerable questions if you tell it
too firmly that it may refuse, and what that experiment looked like.

## Where the rest of the repo lives

| | |
|---|---|
| [`../phases/PHASE-1.md`](../phases/PHASE-1.md) | the plan: what was decided, what is next |
| [`09-DECISIONS.md`](09-DECISIONS.md) | every decision with what was rejected — **D09, D10, D05** are cited above |
| [`README.md`](README.md) | this folder's index and the three § numbering families |
| [`../rag/corpus.py`](../rag/corpus.py) | Step 1 in code — its docstring is the short form of R1.4–R1.6 |
| [`../rag/chunk.py`](../rag/chunk.py) | Step 2 in code |
