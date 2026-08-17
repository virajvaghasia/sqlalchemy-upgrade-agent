# Retrieval — study notes

Part of [`sqlalchemy-upgrade-agent`](../README.md). **§R1 onwards** — a third numbering family
alongside §0–§22 (SQLAlchemy) and §1–§6 (infrastructure). **The `R` is for RAG, not for
retrieval**, which matters once the run continues past this file: §R1–§R2 here are retrieval,
§R3 onwards in [`11-GENERATION.md`](11-GENERATION.md) is generation, and both are RAG. The prefix
exists so `§R1` can never be misread as `§1`; see [`README.md`](README.md).

This file explains **what Phase 1 is actually doing and why**, from zero. It assumes you know
Python and databases and nothing at all about retrieval or language models.

[`../phases/PHASE-1.md`](../phases/PHASE-1.md) is the *plan* — what was decided and what is
next. This is the *teaching*: the concepts underneath those decisions, with the gaps filled in.

> **Sitting 1 is §R1; sitting 2 is §R2.** Read §R1, run the three commands at the end, and answer
> the four questions. Worked answers follow them — cover those on a first pass, because a question
> you have already read the answer to tests nothing. Then stop.
>
> **§R2 is written** and starts at *"What an embedding actually is"*. It is a separate sitting, so
> do not roll straight on. **§R3 is written too, and lives in
> [`11-GENERATION.md`](11-GENERATION.md)** — the numbering continues across the pair, so this file
> is retrieval (§R1–§R2) and that one is generation (§R3–).
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

**Every number in that diagram, before anything else.** They are shown above and it is fair to
ask what they mean:

| in the diagram | what it is |
|---|---|
| `270 .rst` | 270 files. `.rst` is the plain-text format SQLAlchemy writes its docs in — see the Corpus bullet below for where they came from |
| `3284 pieces` | how many chunks the corpus was cut into. **Not a target** — it is what falls out of aiming at ~1800 characters. 3946041 characters ÷ 3284 = 1202 each on average |
| `3284 x 1024` | a table: **3284 rows**, one per chunk, and **1024 columns**, one number each. Every row is one chunk's position in meaning-space |
| `1024` | how many numbers describe one chunk. Each is called a **dimension** — nothing more mysterious than a column |
| `float32` | the type of each of those numbers. *float* = has a decimal point (`0.0213`, not `3`); *32* = 32 bits = **4 bytes** each |

**And the size of the whole thing is just counting boxes.** Two steps, nothing hidden:

```
3284 chunks  ×  1024 numbers each   =  3362816 numbers in total
3362816 numbers  ×  4 bytes each    =  13451264 bytes    (about 13 MB)
```

How many numbers there are, times how big one number is. **That is the entire "understanding"
the retrieval half of this system has.**

**Why bother computing it.** 13 MB sounds like it might *mean* something — like a bigger file
held more meaning, or came from a smarter model. It does not. The size is fixed the moment you
pick **how many chunks** and **how many dimensions**, and nothing about the quality of the
retrieval is in it. Swap in a 384-dimension model and the file is 3284 × 384 × 4 = **5 MB** —
smaller, and (measured, `09-DECISIONS.md` **D32**) it retrieves just as well.

#### Why the chunks are not all exactly 1800

Because **the chunker never cuts a paragraph or a code block in half.** It adds whole blocks
until the next one will not fit, then stops — wherever that lands.

Packing a box that holds 1800 grams, with books. At 1500g the next book weighs 500g. Adding it
overflows, so you close the box at **1500**. You cannot tear the book in half.

```
# runnable: uv run python -c "
# import json, collections
# n=[json.loads(l)['n_chars'] for l in open('corpus/chunks.jsonl')]
# b=collections.Counter(min(x//300*300, 2400) for x in n)
# for k in sorted(b): print(f'{k:>5}-{k+299:<5} {b[k]:>5}  {chr(35)*(b[k]//25)}')
# print('exactly 1800:', sum(1 for x in n if x==1800))"
    0-299     170  ######
  300-599     357  ##############
  600-899     453  ##################
  900-1199    463  ##################
 1200-1499    720  ############################
 1500-1799   1015  ########################################
 1800-2099     48  #
 2100-2399     24
 2400-2699     34  #
exactly 1800: 1
```

**One chunk out of 3284 is exactly 1800.** Two things pull the rest below it:

- **The next block did not fit** — that is the bulge at 1500–1799, the fullest boxes.
- **The section simply ended.** A section only 400 characters long *is* a 400-character chunk.
  There is nothing left to add; packing resumes in the next section, under a different heading.

**1800 is a ceiling, not a quota** — and that is the right shape. Forcing every chunk to exactly
1800 would mean cutting mid-sentence and mid-code-block, which is the one thing Step 2 exists to
prevent. The handful *above* 1800 are single code blocks larger than the entire budget, emitted
whole rather than cut: an honest oversized chunk beats a silently truncated example.

**§R2 takes all of this apart properly** — what a dimension really is, why 1024 rather than 2,
and why `float32` rather than the half-size `float16` that is genuinely tempting. For now the
table above is enough to read the diagram without anything dangling.

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

#### Why it is split into two halves at all

**Embedding is slow. Comparing numbers is fast.** So every slow thing was pushed into the
build-time half, which runs once, before any question exists. Measured on this machine:

| | | |
|---|---|---|
| **once, ahead of time** | embed all 3284 chunks | **627000 ms** (10.5 minutes) |
| **every question** | embed just the question | **~40 ms** |
| **every question** | compare it against all 3284 | **~1 ms** |

**The alternative is what makes it obvious.** Without doing the work up front, answering one
question would mean embedding the entire corpus *first* — you cannot compare against numbers
you have not produced yet. Every question would cost **627 seconds instead of 0.04**. That is
roughly 15000× worse, per question, forever.

So a vector index is not a clever search algorithm. **It is a cache of work you refuse to
redo.** You pay ten minutes once, and each question afterwards costs the price of embedding one
short string plus 3284 multiply-and-adds.

It is also why re-embedding is an event rather than a tweak: change the model and all 3284
vectors become worthless, because they describe positions in a different space
(`09-DECISIONS.md` **D36**). The ten minutes comes back.

Steps 1 and 2 have already happened, and you can see both:

```
# runnable: uv run python -m rag.corpus --check | head -1
all 270 files match the manifest
```

```
# runnable: uv run python -c "import json; s=json.load(open('corpus/CHUNK_STATS.json')); print(s['n_chunks'], s['n_chars'])"
3284 3946041
```

> **Why that reads the stats file instead of just running the chunker.**
> The obvious command is `uv run python -m rag.chunk`, and it would print the same numbers — but
> **a full run rewrites `corpus/chunks.jsonl` and `corpus/CHUNK_STATS.json`.** It is a build
> command, not a check.
>
> It looks harmless, because the chunker is deterministic and the rewrite reproduces both files
> byte-for-byte. It is not harmless while anything downstream is running: `embeddings.npy` is
> row-aligned to `chunks.jsonl` **by position** — row *i* is chunk *i*. Rewrite the chunks under
> a running embed and you get an index whose vectors point at the wrong text. **Nothing errors.**
> Search keeps returning results; they are simply attached to the wrong sources.
>
> Reading `CHUNK_STATS.json` opens a file and writes nothing, which is what a check should do.
>
> **`--sample` used to have the same problem and no longer does** — it printed ten chunks *and*
> rewrote both files. It now builds in memory and touches nothing, because a flag whose purpose
> is "show me some examples" should not have side effects. Pinned by a test.
>
> **The habit, which outlives this example:** before running a command to *verify* something,
> check whether it *mutates* the thing it verifies. A surprising number do.

### R1.4 The corpus is a ceiling

Here is the idea that makes Step 1 a *step* rather than a download, and it is the single most
important thing in this file.

> **If a fact is not in the corpus, no amount of engineering will ever retrieve it.**

Hybrid search, reranking, the agent — those find a chunk **faster or higher**. None of them can
find a chunk that **does not exist**. Whatever you left out of the 270 files is a permanent hole.
Every later score is capped by it. That cap is the **ceiling**: not "hard to find", **not present**.

**Read this table first.** Every number in R1.4 is here. **None of 514 / 569 / 660 / 743 is a
file count.** Those four are counts of **stub lines** — one `.. autoclass::` (or similar) per
count — sitting *inside* files we already kept. One file can contribute many stubs. `270` is
the only file count in this section.

| number | unit | where | signifies |
|---|---|---|---|
| **270** | **files** | `corpus/raw/` | the docs we **do** use |
| **3284** | chunks | `corpus/chunks.jsonl` | those files, cut into searchable pieces |
| **514** | stub **lines** | inside the 1.4 half of those 270 | empty API placeholders in files we kept |
| **569** | stub **lines** | inside the 2.0 half of those 270 | same, 2.0 |
| **1083** | stub **lines** | 514 + 569 | HTML would show a signature here; we stored config instead |
| **660** | stub **lines** | *all* 1.4.52 docs on GitHub, not only our 270 | same kind of line, bigger pile |
| **743** | stub **lines** | *all* 2.0.51 docs on GitHub | same |
| **0** | chunks | grep `has_table` in `chunks.jsonl` | that name is in **no** piece — a real ceiling |
| **103** / **5** | chunks | grep `execution_options` / `bind_arguments` | those names **are** present — not a ceiling |

`# runnable` under a command means: paste it, the lines below are the printout. You do not
need to re-run them to read the table.

This is not hypothetical. We have a hole, and we put it there by choosing `.rst` source instead
of the rendered website.

#### The hole in one file

SQLAlchemy's git repo holds documentation *source*, not the website. Per-method pages you hit
from Google are **generated later** from Python docstrings. In the `.rst` the generator is a
directive that looks like this:

```
.. autoclass:: Session
    :members:
```

That is not a method signature. It is an instruction: *"when Sphinx builds HTML, go read
`Session`'s docstring and paste it here."* On disk, in `corpus/raw/`, it is two lines of config.
Search indexes those two lines. It never sees the signature.

#### Measurement 1 — stub *lines* inside *our* 270 files

Not “514 unused files.” Walk `corpus/raw/` (already on disk) and count every
`.. autoclass::` / `.. autofunction::` / `.. automodule::` / `.. automethod::` /
`.. autoattribute::` **line**. Each hit is one placeholder, not one file:

```
# runnable: for v in 1.4.52 2.0.51; do printf '%-8s %4d\n' "$v" \
#   "$(grep -rhoE '\.\. auto(class|function|module|method|attribute)::' corpus/raw/$v --include='*.rst' | wc -l | tr -d ' ')"; done
1.4.52    514
2.0.51    569
```

| printed | unit | what it signifies |
|---|---|---|
| `1.4.52    514` | **lines**, not files | 514 `.. auto*::` placeholders in the 1.4 files we **use** |
| `2.0.51    569` | **lines**, not files | same for 2.0 files we use |
| **1083** | lines | 514 + 569. Website would fill these in; search sees the empty instruction |

Quote **this** pair when arguing about *this system's* ceiling.

#### Measurement 2 — same stubs in SQLAlchemy's *whole* docs tree

Same `grep`, but on every `.rst` in the git tag — including files Step 1 **did not** keep.
Needs a download of the two tags:

```
# runnable: for t in rel_1_4_52 rel_2_0_51; do curl -sL \
#     "https://github.com/sqlalchemy/sqlalchemy/archive/refs/tags/$t.tar.gz" \
#     | tar xz "sqlalchemy-$t/doc/build"; done
#   for t in rel_1_4_52 rel_2_0_51; do printf '%-11s %4d\n' "$t" \
#     "$(grep -rhoE '\.\. auto(class|function|module|method|attribute)::' sqlalchemy-$t/doc/build --include='*.rst' | wc -l | tr -d ' ')"; done
rel_1_4_52   660
rel_2_0_51   743
```

| printed | unit | what it signifies |
|---|---|---|
| `rel_1_4_52   660` | **lines**, not files | same stub kind, counted on SQLAlchemy’s **entire** 1.4 tree (including files we dropped) |
| `rel_2_0_51   743` | **lines**, not files | same for the entire 2.0 tree |

**660 − 514 = 146** stub lines that live only in files Step 1 excluded. That difference is
about **which files we kept**, still not a file count.

That pair is what [`../phases/PHASE-1.md`](../phases/PHASE-1.md) Step 1 quotes. Quote **this**
pair when arguing about reStructuredText source *in general*.

**514 vs 660 is the point of Step 1**, not a typo. 660 is what the library ships. 514 is what
survived our file list. A number is only meaningful once you say which pile it counted.

You do not need to re-run the `curl` to understand the section. The two result lines are the
measurement. Re-run it only if you are checking they still hold.

#### Measurement 3 — a question the ceiling actually blocks

Step 5 ran nineteen questions. One of them is a true ceiling: `engine.has_table()`. Count how
many of the 3284 searchable pieces even mention the name:

```
# runnable: grep -c has_table corpus/chunks.jsonl
0
```

**`0`** means the string is in **no chunk**. Ranking cannot rank an empty list. Phase 3 cannot
fix it. Phase 5 cannot fix it. The only fix is changing the corpus — a Step 1 decision.

That is why this section exists: so *"why this corpus?"* has a measured hole, not a vibe.
Interviewer: *"Can't you just add reranking?"* Answer: *"Not for `has_table`. Zero chunks."*

> #### A correction worth keeping, because it nearly went in as the example
>
> This section first used *"what arguments does `Session.execute()` take?"* as the ceiling case,
> and claimed `execution_options` and `bind_arguments` were absent. **Checked, and they are not.**
> Same `# runnable` contract: the command counts matching lines in `chunks.jsonl`.
>
> ```
> # runnable: for t in execution_options bind_arguments; do printf '%-20s %3d chunks\n' "$t" "$(grep -c "$t" corpus/chunks.jsonl)"; done
> execution_options    103 chunks
> bind_arguments         5 chunks
> ```
>
> **103** and **5** mean those strings *are* in the index. They were also **retrieved**: chunk
> `c01169` was source `[3]` and contains both; `[4]` and `[5]` contain `execution_options`. The
> model was handed the parameters in three of five sources **and named neither**.
>
> That is not a ceiling. It is a third failure: **generation ignored what it was given.** The
> sources print is already on screen; the check that would catch it is reading them. Wrong
> example for this section; kept as its own finding rather than deleted.

That is why *"why this corpus?"* is the question an interviewer opens with.

### R1.5 Why a bigger corpus is also worse

The instinct is that more data is safer — if in doubt, throw it all in. That instinct is wrong,
and understanding why is what separates someone who has built one of these from someone who has
read about one.

**The mechanism.** Retrieval returns a **fixed number** of chunks. Say k = 5. Those five slots
are all the model will ever see. Every irrelevant chunk in the index is a competitor for those
five slots. It does not sit harmlessly in the corner; it is in the race, every time, for every
question.

#### But who decides "irrelevant"? Nothing does

That sentence needs pinning down, because it implies a judgement the system never makes. **There
is no relevance test anywhere in this pipeline** — no classifier, no threshold, no list of good
chunks, no flag on a chunk saying it is worth returning. The entire selection policy is this:

```
from rag/index.py — retrieve()

return client().query_points(
    collection_name=collection_name(stats),
    query=query_vector(query),   # the question, turned into 1024 numbers
    limit=limit,                 # 5 — and that is the whole policy
    query_filter=flt,
    with_payload=True,
).points
```

Qdrant returns the five stored vectors whose direction is closest to the question's, ordered by
cosine similarity. That is everything that happens. **"Relevant" is a word *you* apply from the
outside, looking at what came back.** The machine has exactly one quantity: *how close is this
direction to that one*.

Those two things agree often enough for the system to be useful, and disagree often enough to
need Phase 2. **Every entry in `FAILURES.md` lives in the gap between them.**

Three consequences follow, and they are worth carrying separately:

- **Nothing is ever ruled out.** Every chunk in the index is scored against every question. A
  chunk cannot sit a round out; it can only *lose* one. So "it competes for a slot" is literal,
  not a figure of speech — there is no state in which a chunk is not competing.
- **The band the decision happens in is narrow.** Two chunks picked at random score **0.540**
  (R2.5). The top hit for *"why can't I call `engine.execute()` any more?"* scored **0.633**. So
  the entire distance between *the best of 3284 chunks* and *two unrelated paragraphs* is
  **0.09**. Winning a slot is not a landslide.
- **Closeness is not usefulness, and the gap is measured, not feared.** A 1.4 page and its 2.0
  twin sit at a median **0.9920** — as near identical as this system can report. They give
  opposite advice. **If the score knew what "relevant" meant, that could not happen.**

So read the paragraph above strictly. An *irrelevant* chunk is not one the system sets aside. It
is one **you** would call useless, which is still being scored on every question you ask, and
which can still outrank the page you actually needed.

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

**Now vs later — do not mix these up.**

| | |
|---|---|
| **Now (Phase 1)** | Search **is** meaning-search. Both twins can sit in the top 5. We **do not** filter on version. That is deliberate (D10): the failure has to show up so Phase 3 has a before number. |
| **Later (Phase 3)** | We still do **not** “wait for embeddings to notice `future=True`.” A better meaning model sees the same near-identical paragraph. The split uses the **version label** already on each chunk (`1.4.52` / `2.0.51`) as a **filter or route** — metadata, not smarter vectors. Hybrid search is for a *different* hole (exact symbols like `table_names`). |
| **Still not a full fix** | A **2.0 file** can still say *“in 1.4, pass `future=True`.”* Filtering to 2.0 keeps that page. R1.7 measured that. |

**And this tells you what the fix has to be.** A better *meaning* search cannot separate two
passages that mean the same thing — that is not a flaw in the search, it is the search working.
Reranking the same near-identical text does not split them either. The only things that can
separate **twin pages** are the things that are **not** in the text: the version label from
Step 1. That is why **D10** (record skew, do not prevent it) kept the label even though Phase 1
never uses it — Phase 3 cannot invent it later.

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

R1.5 was a **prediction**: ask *"should I pass `future=True`?"* and meaning-search will grab the
**1.4 tutorial** and answer yes.

This section is the **run**. Steps 3–5 exist now. Question **#7** in
[`../deliverables/FAILURES.md`](../deliverables/FAILURES.md) is that exact question. The answer
was still **wrong** — but **not in the way R1.5 guessed.** Same poison, different bottle. That
mismatch is the whole of R1.7.

**What came back:**

> *"Yes, you should pass `future=True` to `create_engine`. This is necessary for enabling the new
> 2.0 API in SQLAlchemy and ensuring compatibility with the upcoming version [1]."*

Wrong for someone on 2.0. "Upcoming version" is already a tell: 2.0 is the version being asked
about, not a future release.

**What R1.5 expected as `[1]`:** 1.4 `tutorial/engine.rst` (the twin in the diff above).  
**What actually ranked `[1]`:** a **2.0** file.

```
# summary of: deliverables/FAILURES.md entry 7  (RST role markup stripped for reading;
#   the verbatim chunk, with :class:`_engine.Engine` etc. intact, is in that file)
[1]  0.659 · SQLAlchemy 2.0.51 · doc/build/changelog/migration_20.rst
     "Migration to 2.0 Step Four - Use the ``future`` flag on Engine"

     The Engine object features an updated transaction-level API in version 2.0.
     In 1.4, this new API is available by passing the flag future=True to the
     create_engine function.
```

Three facts, and they are not the same fact:

**1. A version filter would not have saved you.**  
This page's label is `2.0.51`. Drop every 1.4 chunk and it **stays**. "Just search 2.0" helps the
*twin tutorial* case (R1.5). It does **not** fix this case. If you take one sentence from R1.7,
take that: Phase 3's version filter is necessary and **not enough**.

**2. The page is 2.0 talking about 1.4.**  
The prose says *"**In 1.4**, this new API is available by passing `future=True`."* A human reads
those two words and treats it as history. The model dropped them and reported the advice as
current. "Upcoming version" in the answer leaked out of that 1.4-era framing inside a 2.0 file.

So skew is two shapes:

| | example | does a version **filter** catch it? |
|---|---|---|
| **Wrong file version** | 1.4 tutorial wins a 2.0 question (R1.5 twins) | yes — drop 1.4 |
| **Right file, wrong era in the prose** | 2.0 migration guide describing 1.4 (this run) | **no** — metadata is already 2.0 |

**3. The right chunk was in the prompt and unused.**  
`[2]` was 2.0 `core/future.rst`: in 2.0 the flag does nothing useful if you pass it. Retrieval
got a correction into the top-k. The answer cited only `[1]`. That is **generation** ignoring
what it was given, on top of a retrieval miss. Visible only because sources are printed (R1.2).
The `single_source` signal on the entry is that fact as a flag, not a verdict.

**`UNVERIFIED` on #7 is not an oversight.** All 19 `FAILURES.md` rows are unmarked until a human
writes CORRECT / WRONG / PARTIAL. The golden set is hand-verified (D09's sibling). A script
grading its own answers reports whatever number you wanted.

**One line.** R1.5 said the *1.4 tutorial* would poison the answer. The poison was a *2.0
migration page that still describes 1.4.*

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
2. *Our system cannot answer "what is `engine.has_table()`". Why can no amount of
   Phase 3 work fix that?* — R1.4
3. *`BREAKAGES.md` would improve the answers. Why is it deliberately excluded?* — R1.6
4. *We already have a `--version` filter. Question #7 still got the wrong answer from a correctly
   labelled 2.0 page. Why didn't the filter save it?* — R1.7

**A warning about question 4.** The tempting answer is *"the filter wasn't switched on"*. That is
not it, and reaching for it means R1.7 has not landed. Reread the source passage and notice what
its first two words are.

#### Answers

**Cover these on a first pass** — the questions are only worth anything attempted cold. They are
written down so a reread months later does not have to reconstruct them. Each is shaped *short
answer → why → what it is NOT → evidence*.

**1. Why does adding documents make it worse?**

**Because top-k is fixed, so new text cannot add capacity — it can only take slots from whatever
was winning before.** `DEFAULT_K = 5` in `rag/ask.py` is a hard budget of five.

*Why:* nothing is ever ruled out of the race (R1.5, *"But who decides irrelevant"*). Every chunk
is scored against every question, so added text competes on queries it has nothing to do with.
Recall goes up, precision goes down, and precision is what fills the five slots.

*What it is NOT:* it does not cost more tokens, and compute is not the argument. The prompt
carries five chunks whether the index holds 3284 or three million. Comparing against all 3284
takes **~1 ms** against the **~40 ms** of embedding the question — search is 2.4% of query time,
and `D40` declines to claim speed as a reason for Qdrant at all. Reaching for a cost argument is
the common wrong answer and does not survive *"top-k is fixed — why would the prompt grow?"*

*Evidence:* `changelog/` is ~60% of SQLAlchemy's docs by bytes and almost entirely one-line
release entries. Including it would roughly triple the index and spend slots on *"Fixed issue in
ORM where…"* fragments, on every question.

**2. Why can no amount of Phase 3 work answer `engine.has_table()`?**

**Because the text is not in the corpus at all.** Phase 3 changes how chunks are *ranked*;
ranking cannot surface a chunk that does not exist.

*Why:* the corpus is documentation *source*, and the API reference is not in the source — it is
generated at build time from docstrings by `.. autoclass::`-family directives. In our 270 files
those directives number 514 (1.4) and 569 (2.0), and every one resolves to nothing here.

*Evidence:* `grep -c has_table corpus/chunks.jsonl` → **0**.

*The distinction that matters (`D45`):* `table_names` appears in **6** chunks and still was not
retrieved. That is a *retrieval* failure and Phase 3's hybrid search is exactly the fix.
`has_table` at **0** chunks is the *ceiling*, and the only fix is a Step 1 decision. "Hard to
find" and "not present" are different problems with different owners.

**3. Why is `BREAKAGES.md` excluded when it would improve answers?**

**Because it is the answer key.** It seeds the Phase 2 golden dataset.

*Why:* a corpus containing the evaluation answers makes Phase 2 measure whether the system can
retrieve its own answer key. The score goes up and means less — the classic leakage between
corpus and evaluation set.

*The honest cost:* this gives up real quality now to keep a number honest later. It is `D09`, and
it is the decision most worth being able to explain, because most people have never considered
corpus/eval leakage until asked.

**4. Why didn't the `--version` filter save question #7?**

**Because the page it retrieved was already a 2.0 page.** The filter was never positioned to
catch it.

*Why:* version skew has **two shapes**, and a filter only catches one. (a) A page from the
*wrong* version — a filter catches this. (b) A page from the *right* version whose prose is
*conditional on another version* — no metadata can catch this, because the file's metadata is
correct.

*Evidence:* #7's source `[1]` was `changelog/migration_20.rst` at **2.0.51**, reading *"**In
1.4**, this new API is available by passing the flag `future=True`."* Those first two words are
the whole answer, and the model dropped them. Its own wording gave it away — it wrote
*"compatibility with the **upcoming** version"*, but 2.0 is not upcoming.

*And a second failure underneath:* result `[2]` was `core/future.rst` at 2.0, which says the flag
now does nothing. **The correction was already in the top-k and the answer cited only `[1]`.**
That is a generation failure sitting on a retrieval failure — visible only because the sources
were printed.

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

**"On average" is doing work in that sentence, so pin it down.** There are two ways to say
"typical" and they disagree:

- **Mean** — add every value, divide by how many. *The average.* One enormous value drags it up.
- **Median** — sort them all, take the middle one. *The one in the middle.* An enormous value
  cannot drag it anywhere; it is still just one item at the end of the queue.

Ours differ, and the difference decided a parameter:

```
# runnable: uv run python -c "
# import json, statistics
# n=[json.loads(l)['n_chars'] for l in open('corpus/chunks.jsonl')]
# print(f'mean {statistics.mean(n):.0f}  median {statistics.median(n):.0f}  max {max(n)}')"
mean 1202  median 1299  max 5346
```

The largest chunk is **5346** — four times the middle one — and before `glossary.rst` was split
per term there was a single 69236-byte block in there. **The chunker was sized on the median,
not the mean**, because a handful of giants distort an average and would have pushed the target
above what most sections need. That is `TARGET = 1800` in `rag/chunk.py`, and it is why the same
table in `phases/PHASE-1.md` Step 2 quotes a median.

#### If the target is 1800, how is anything 5346?

Because **1800 is a packing limit, not a truncation limit.** It decides when to stop *adding*
blocks. It never cuts one. There are two limits and neither can split a block:

```
TARGET   = 1800   before adding the next block: if it would breach 1800, close this chunk first
HARD_MAX = 2400   after adding: if the chunk is past 2400, close it immediately
```

The whole behaviour comes down to one guard in `pack()`:

```
from rag/chunk.py — pack()

if current and size + n + 2 > target:   # "if current" — only fires if something is already in
    emit()
    ...
current.append(block)                   # unconditional: the block always goes in whole
size += n + 2
if size >= hard_max:
    emit()
```

**When the chunk is empty, no emit can fire, however large the incoming block is.** So an
oversized block lands whole in an empty chunk, and the `hard_max` check immediately kicks it out
alone. Both numbers only ever choose *where a boundary between blocks falls* — never where a
boundary falls *inside* one.

**And the 5346 is a single indivisible thing:**

```
# runnable: uv run python -c "
# import json
# r=[json.loads(l) for l in open('corpus/chunks.jsonl')]
# b=max(r, key=lambda c: c['n_chars'])
# print(b['id'], b['n_chars'], 'chars')
# print(b['source_path'].split('doc/build/')[-1])
# print(' -> '.join(b['heading_path']))"
c00519 5346 chars
faq/performance.rst
Performance -> I'm inserting 400,000 rows with the ORM and it's really slow!
```

One Python benchmark script, printed whole in that FAQ answer. There is no legal cut point
inside it.

**How many get past each limit, and what it costs:**

```
# runnable: uv run python -c "
# import json
# n=[json.loads(l)['n_chars'] for l in open('corpus/chunks.jsonl')]
# for lo in (1800, 2400):
#     print(f'over {lo}: {sum(1 for x in n if x>lo):4d}  ({100*sum(1 for x in n if x>lo)/len(n):.1f}%)')
# print('stats oversized:', json.load(open('corpus/CHUNK_STATS.json'))['oversized'])"
over 1800:  105  (3.2%)
over 2400:   34  (1.0%)
stats oversized: 34
```

The `oversized` figure in `CHUNK_STATS.json` counts exactly the chunks that beat `HARD_MAX`, so
the number of times the rule bent is recorded rather than hidden.

**Why this is right rather than a leak.** Cut that script at 1800 and you get three fragments,
each of which *looks* like a complete example and none of which runs. A retrieval hit on fragment
two hands the model the middle of a benchmark with no imports and no `Base` — and the model will
summarise it confidently, because nothing in the text says it is a fragment. **An honest
oversized chunk beats a silently truncated example**, and the cost is bounded at 34 chunks, 1%
of the index.

**`float32` is a name with two facts packed into it.** Nothing is split at runtime — it is the
*identifier* that comes apart, and each half tells you something different:

```
# illustration
float32
│    └── 32   how many bits each number occupies:  32 ÷ 8 = 4 bytes
└─────── float  it has a decimal point — 0.0213, not 3
```

Read together: *"decimal numbers, four bytes each."* Which makes the file size a multiplication
rather than a mystery:

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

#### Why min and max are the same number

**A norm is the length of the arrow** from the origin out to that point: square every component,
add them up, take the square root. Nothing more exotic than Pythagoras with 1024 sides.

**And printing `min` and `max` is a check, not a statistic.** A *mean* of 1.0 would prove nothing
— vectors of length 0.5 and 1.5 average to 1.0 as well. `min == max == 1.000000` is the only
output shape that says **every single one, no exceptions, across all 3284.** Two identical
numbers are the finding, not a redundancy.

**What that line looks like when nothing has normalised it** — the same shape and dtype, filled
with random values instead of meanings:

```
# runnable: uv run python -c "
# import numpy as np
# rng=np.random.default_rng(0); R=rng.normal(size=(3284,1024)).astype(np.float32)
# n=np.linalg.norm(R,axis=1)
# print('un-normalised   min %.4f  max %.4f  spread %.4f' % (n.min(), n.max(), n.max()-n.min()))
# m=np.linalg.norm(R/n[:,None],axis=1)
# print('after dividing  min %.6f  max %.6f' % (m.min(), m.max()))"
un-normalised   min 29.5299  max 35.0566  spread 5.5267
after dividing  min 1.000000  max 1.000000
```

A spread of **5.5267** collapsing to nothing. That is what the flag did to our file.

**"Exactly 1.0" is exact only to float32's limit**, and the arithmetic shows where it stops:

```
# runnable: uv run python -c "
# import numpy as np; v=np.load('corpus/embeddings.npy')[0].astype(np.float64)
# print('sum of squares', (v**2).sum()); print('square root   ', np.sqrt((v**2).sum()))"
sum of squares 1.0000000980377284
square root    1.000000049018863
```

It misses 1 in the **eighth** significant digit — precisely where this section already said
float32 runs out, at about seven. `%.6f` rounds that away. The same precision fact from two
paragraphs above, wearing a different disguise.

**Why do it at all.** The short answer is that it buys the right to use the *cheap* operation.
That takes two steps to see.

**Step one — magnitude can beat relevance.** Use the 1.4 engine tutorial as the query. Its
correct match is the 2.0 twin at 0.9691, and the least related chunk in all 3284 is a query-guide
page at 0.3820. Now suppose that unrelated chunk were three times longer, so its vector were three
times as long:

```
# runnable: uv run python -c "
# import json, numpy as np
# r=[json.loads(l) for l in open('corpus/chunks.jsonl')]; V=np.load('corpus/embeddings.npy')
# q=next(i for i,c in enumerate(r) if c['id']=='c01464')
# s=V@V[q]; o=np.argsort(-s); good, bad = o[1], o[-1]
# fake=V[bad]*3
# cos=lambda a,b: float(a@b/(np.linalg.norm(a)*np.linalg.norm(b)))
# print('                       raw dot   cosine')
# print('correct  (c03211)      %.4f    %.4f' % (float(V[q]@V[good]), cos(V[q],V[good])))
# print('unrelated x3 (c02771)  %.4f    %.4f' % (float(V[q]@fake),    cos(V[q],fake)))"
                       raw dot   cosine
correct  (c03211)      0.9691    0.9691
unrelated x3 (c02771)  1.1461    0.3820
```

**Under raw dot product the unrelated chunk wins — 1.1461 against 0.9691.** It did not become
more relevant. It became bigger. A retrieval system built on raw dot products returns long
documents.

**Step two — cosine already fixes that, by dividing the length back out:**

```
cosine(a, b) = (a · b) / (|a| × |b|)
             = 1.1461 / (1 × 3)
             = 0.3820        ← back to last place, where it belongs
```

Look at the `cosine` column above: the fake chunk scores 0.3820 no matter how much it is scaled.
**So cosine is not what normalising buys — cosine was always available.** What it costs is that
division: two vector lengths computed on every comparison, 3284 times per question.

**What normalising buys is this identity:**

```
# runnable: uv run python -c "
# import json, numpy as np
# r=[json.loads(l) for l in open('corpus/chunks.jsonl')]; V=np.load('corpus/embeddings.npy')
# q=next(i for i,c in enumerate(r) if c['id']=='c01464')
# cos=lambda a,b: float(a@b/(np.linalg.norm(a)*np.linalg.norm(b)))
# print('unit vectors: dot == cosine ?', np.allclose(V@V[q], [cos(V[i],V[q]) for i in range(len(V))]))"
unit vectors: dot == cosine ? True
```

**Here is that in full, because "the denominator is 1" is doing all the work and is easy to
skim past.** There are two different formulas, and ordinarily they disagree:

```
# illustration
correct :  cosine(a, b) = (a · b) / (|a| × |b|)    a dot product, two lengths, one division
cheap   :                  a · b                    a dot product, and nothing else
```

They disagreed in the table above — `1.1461` against `0.3820` — because one of those vectors had
length 3. But **when every vector has length 1**, substitute and the division disappears:

```
# illustration
cosine(a, b) = (a · b) / (|a| × |b|)
             = (a · b) / (  1 ×  1 )      ← both are unit vectors
             = (a · b) /      1
             = (a · b)                    ← the cheap formula, unchanged
```

**That is what "exactly" means here.** The cheap formula is not an approximation of the correct
one that happens to be close enough. It **is** the correct one, on this data, because the step
that was skipped was a division by 1 — and dividing by 1 changes nothing. There is no tolerance
to check and no error to bound.

So you get cosine's immunity to length at the dot product's price: one multiply-and-add across
1024 numbers, no division anywhere. That is what earns `rag/index.py` the right to write
`vectors @ query` — and it is only true because of the flag. Turn normalisation off and that same
line silently starts returning long documents.

**Said plainly: normalising does not make the search smarter. It makes the cheap operation and
the correct operation the same operation.** The division is paid once, at build time, instead of
3284 times per question forever — which is §R1.3's build-time/query-time trade applied one level
further down.

**And what it costs is in the same two lines.** Before normalising, the lengths ranged from
`29.5299` to `35.0566`; afterwards `min` and `max` are both `1.000000`. **That spread was
information — roughly how much text a chunk held — and it has been overwritten, not
de-weighted.** Nothing downstream can recover it: not Qdrant, not Phase 3's reranker, not the
Phase 5 agent. Recovering it means re-embedding all 3284. Mostly that is exactly what you want,
since the demonstration above shows length winning fights it should lose — but it is a trade, and
the cost half is the half worth being able to state.

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

#### Why the embedding is structurally unable to see a symbol

The failure above is not the model being weak. It is a consequence of how a chunk becomes one
vector, and the arithmetic says so:

```
# runnable: uv run python -c "
# import json
# r=[json.loads(l) for l in open('corpus/chunks.jsonl')]
# h=[x for x in r if 'table_names' in x['text']]
# for x in h: print(f\"  {x['id']}  {x['sqlalchemy_version']}  {x['n_chars']:5d} chars  x{x['text'].count('table_names')}\")
# tot=sum(x['n_chars'] for x in h); occ=sum(x['text'].count('table_names') for x in h)
# print(f'  {occ*11} of {tot} characters = {100*occ*11/tot:.2f}% of the text')"
  c00290  1.4.52    382 chars  x1
  c00449  1.4.52   1022 chars  x1
  c00807  1.4.52    992 chars  x1
  c01934  2.0.51    382 chars  x1
  c02021  2.0.51   1022 chars  x1
  c02502  2.0.51    992 chars  x1
  66 of 4792 characters = 1.38% of the text
```

**`table_names` is 1.38% of the text it lives in.** It appears once per chunk; the other 98.6% is
prose about reflection, errors and asyncio. One vector has to describe all of it, so the vector
describes *"a passage about database introspection"* — which is correct, and useless when the
literal string **is** the question. Nothing is malfunctioning. A summary of a paragraph is not a
record of which identifiers the paragraph contained.

**Then look at the rarity, which is where the fix comes from:**

```
# runnable: uv run python -c "
# import json
# r=[json.loads(l) for l in open('corpus/chunks.jsonl')]; n=len(r)
# for t in ('table_names','has_table','cascade_backrefs','keys()','session','select'):
#     c=sum(1 for x in r if t in x['text'])
#     print(f'{t:20s} {c:5d} chunks  ({100*c/n:5.2f}% of corpus)')"
table_names              6 chunks  ( 0.18% of corpus)
has_table                0 chunks  ( 0.00% of corpus)
cascade_backrefs        12 chunks  ( 0.37% of corpus)
keys()                   7 chunks  ( 0.21% of corpus)
session                781 chunks  (23.78% of corpus)
select                 819 chunks  (24.94% of corpus)
```

**To a dense embedder rarity is invisible** — one token among a few hundred is averaged away.
**To keyword search rarity is the strongest signal available**: that is exactly what BM25's IDF
term computes, and a word appearing in 6 of 3284 documents is enormously discriminative where one
in 819 is nearly worthless. *The very property that erases `table_names` from the vector is the
property that makes BM25 lock onto it.* The two methods fail in opposite directions, which is
what makes combining them worth doing rather than merely more work.

**One detail the "6 chunks" figure hides.** Read the version column: the six are **three pages,
each present twice** — `core/reflection.rst`, `errors.rst` and `orm/extensions/asyncio.rst`, at
1.4 and again at 2.0, byte-identical in length. So the real coverage is **three distinct
passages**, and each has a twin competing for the same top-k slot. §R1.5's version skew and
`D38`'s duplicated index are not separate topics from this one; they are the same corpus seen
from a different angle.

**So: does Phase 3 fix it?** For three of the four, yes — and for the fourth, never:

| symbol | in corpus | can Phase 3 fix it? |
|---|---|---|
| `table_names` | 6 chunks (3 pages × 2 versions) | **yes** — the text is there, the ranking is wrong |
| `keys()` | 7 chunks | **yes** |
| `cascade_backrefs` | 12 chunks | **yes** |
| `has_table` | **0 chunks** | **no, and no later phase can** |

`has_table` is not a ranking problem. Hybrid search, reranking, a larger model and the Phase 5
agent all reorder what exists; none can return text that was never indexed. The only fix is
changing the corpus, which is a Step 1 decision. **This is `D45`, and it is worth being able to
state cold, because the two failures look identical from outside — both simply return a wrong
answer.** Only counting chunks separates them, which is why `D45` requires the split be computed
mechanically rather than judged by eye.

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

**The first needs Qdrant up** (`docker compose ps` should show it `healthy`) and returns in a
second or two. **The second takes upwards of ten minutes** — it loads BGE-M3 *and* MiniLM and
re-embeds with both — and it prints nothing at all until it is finished, because Python buffers
its output when it is not writing to a terminal. Run it in your own shell, where you will at
least see it stream. Its conclusion is `D32` and is already recorded.

#### What the first command returns, and the three things to notice

```
# summary of: uv run python -m rag.ask "how do I use joinedload?" --retrieval-only
#   (score, version, file and heading are verbatim; the text preview under each
#    hit is trimmed to its first line so the five fit side by side)
[1] 0.715  1.4.52  orm/loading_relationships.rst    Zen of Joined Eager Loading
[2] 0.714  1.4.52  orm/loading_relationships.rst    Zen of Joined Eager Loading
[3] 0.712  1.4.52  orm/tutorial.rst                 Eager Loading > Joined Load
[4] 0.706  2.0.51  orm/queryguide/relationships.rst Zen of Joined Eager Loading
[5] 0.700  1.4.52  orm/loading_relationships.rst    Zen of Joined Eager Loading
```

This one result demonstrates three separate things §R1 and §R2 argued for, so it is worth
reading slowly:

- **The entire top-5 spans 0.015** — from 0.715 to 0.700. §R1.5 predicted that when a question
  lands near a cluster, which chunk takes a slot is "decided in the fourth decimal place, which
  is to say: by noise." This is that sentence as output. And per R2.5 the numbers are not
  percentages: against a random-pair baseline of **0.540**, a 0.715 top hit is **0.175 above
  noise**, not "72% confident".
- **`[2]` and `[4]` are the same passage at two releases.** Both open *"Above, we can see that
  the two JOINs have very different roles"* — one from 1.4, one from 2.0, **0.008 apart**. Two of
  five slots spent saying the same thing twice. That is `D38`'s duplicated index costing 20% of
  the budget on a single ordinary question.
- **Four of the five hits are 1.4** on a question that named no version at all. A 2.0 user asking
  this gets a prompt that is 80% old-release text, and nothing in the pipeline noticed — which is
  §R1.5's version skew, arriving without anyone provoking it.

#### What the second command returns, and what its columns mean

```
# summary of: uv run python -m rag.compare_embedders   (~10 minutes)
#   HuggingFace progress bars and a rate-limit warning are stripped; the two
#   result rows and the exclusion line are verbatim.
3284 chunks, 16 questions with a known symbol

scoring BAAI/bge-m3 ...
scoring sentence-transformers/all-MiniLM-L6-v2 ...

model                                     dim  params  chunks/s    R@5   R@10    MRR  median  worst
BAAI/bge-m3                              1024    568M       7.2  0.733  0.867  0.675       1     23
sentence-transformers/all-MiniLM-L6-v2    384     23M     259.7  0.733  0.867  0.668       1     79

1 question(s) excluded: no chunk in the corpus contains the symbol at all —
the ceiling (D45), which no model can move.
```

**Start with `rank`, because every other column is made from it.** For one question, the rank is
the position of the first chunk that contains the answer, within the ordering of all 3284. Rank 1
means the search put it first. The script computes it at `compare_embedders.py:98` and then
summarises 15 of them.

**`R@5` — recall at 5. Of the questions, what fraction put a containing chunk in the top five?**

```
0.733 × 15 = 11 questions
```

**11 of 15.** This is the column that matters most, because `DEFAULT_K = 5` is exactly what
reaches the model. For the other four the answer was in the corpus and never entered the prompt.

**`R@10` — the same thing at ten.**

```
0.867 × 15 = 13 questions
```

**13 of 15 — and the gap is the useful part.** `13 − 11 = 2` questions had their answer at rank
**6–10**: retrieved, ordered, and missed the budget by a few places. **Those two are what
reranking in Phase 3 exists to rescue** — no corpus change required, only reordering.

**`MRR` — mean reciprocal rank.** For each question take `1 ÷ rank`, then average:

```
rank  1  ->  1.000
rank  2  ->  0.500
rank  4  ->  0.250
rank 10  ->  0.100
```

**It exists because `R@5` is blind to position.** Rank 1 and rank 5 both score as "in the top
five" and are indistinguishable to recall. MRR separates them. That is exactly what happens here:
the two models are **identical** on R@5 and R@10, and MRR still splits them, 0.675 against 0.668.
A tie at the head hiding a small ordering difference.

**`median` and `worst` are raw ranks**, not fractions: the middle question came back at rank 1 for
both models, and the single worst-placed answer sat at 23 for BGE-M3 and 79 for MiniLM.

**Read the row as a sentence:** *"11 of 15 answers reached the prompt, 13 reached the top ten, the
typical one was ranked first, and the worst was buried at 23."*

**Why 15 and not 16.** Line 101 keeps only ranks that exist — `scored = [r for r in ranks if r is
not None]`. A question whose symbol appears in no chunk is dropped rather than counted as a
failure, because scoring a model on a question the corpus cannot answer measures the corpus, not
the model. That is `D45` built into the measurement instead of applied afterwards, and it is why
every column divides by 15.

**What it settles.** `568 ÷ 23 = 24.7×` the parameters and `259.7 ÷ 7.2 = 36×` the speed, for an
identical R@5. That is `D32`. It also explains the ten-minute wait: `3284 ÷ 7.2 = 456 seconds`
for the BGE-M3 pass against `3284 ÷ 259.7 = 12.6 seconds` for MiniLM.

**What it does not settle.** Fifteen questions is a small sample, and *"identical to three
decimals"* across fifteen items is not *"these models are equivalent."* The `worst` column is the
one hint that they are not: both find the answer at median rank 1, but when MiniLM misses it
misses far worse — rank 79 against 23 — and nothing downstream recovers a chunk buried that deep.

**Answer these three:**

1. *Every vector in our file has length exactly 1.0. What does that buy, and what does it throw
   away?* — R2.3, R2.4
2. *A search returns a top hit at 0.61. Is that good? What do you need to know before you can
   say?* — R2.5
3. *`table_names` appears in 6 chunks and retrieval did not find any of them. Why is that a
   different problem from `has_table`, which appears in 0?* — R2.6

#### Answers

**Cover these on a first pass**, as in §R1. Each is shaped *short answer → why → what it is NOT →
evidence*. All three were attempted cold first, and the corrections that came out of that are
kept, because the wrong answers are the more instructive half.

**1. Length exactly 1.0 — what does it buy, and what does it throw away?**

**It buys the right to use the cheap formula.** Cosine is `(a · b) / (|a| × |b|)`. When both
lengths are 1 the denominator is 1, and dividing by 1 changes nothing — so cosine *is* the dot
product. `vectors @ query` in `rag/index.py` is exactly correct rather than approximately
correct, with no tolerance to check.

*What it is NOT: a speed argument.* Measured on this file, skipping the division saves **0.92 ms**
against the **~40 ms** spent embedding the question — about 2% of query time. Answer "speed" and
the follow-up *"how much faster?"* retracts the claim. The defensible version is a correctness
claim, and correctness gets no "how much?".

*What it throws away: magnitude — overwritten, not de-weighted.* Before normalising, vector
lengths ran `29.5299` to `35.0566`; after, `min` and `max` are both `1.000000`. That spread was
information about how much text a chunk held, and nothing downstream can recover it — not Qdrant,
not Phase 3's reranker, not the Phase 5 agent. Recovering it means re-embedding all 3284.

*Evidence:* scale an unrelated chunk's vector by 3 and raw dot product ranks it **1.1461** against
the correct answer's **0.9691** — it wins for being long. Cosine scores the same chunk **0.3820**
and puts it back last.

**2. A top hit at 0.61 — is that good?**

**Unanswerable until you know what unrelated text scores for this model on this corpus.**

*For ours:* 2000 random pairs average **0.540**, with a floor around **0.329**. So 0.61 is
**0.070 above noise**, and the usable range is roughly 0.33 → 1.0 rather than 0 → 1. It is not
"61% confident"; the number is not a percentage and there is no percentage hiding in it.

*A second thing to ask, which the single number cannot tell you: the gap to the next hit.* The
`joinedload` query above returns 0.715, 0.714, 0.712, 0.706, 0.700 — a top hit 0.175 clear of
noise whose runner-up is **0.001** behind. Strong against random, indistinguishable from its
neighbours. Those are different questions.

*The consequence:* **only the ordering is trustworthy**, which is why retrieval takes top-k rather
than everything above a cutoff. A threshold like "return hits above 0.7" copied from a tutorial
written against another model will return everything or nothing.

**3. Why is `table_names` a different problem from `has_table`?**

**Because they have different owners.** `table_names` is a *ranking* failure — the text is in the
corpus and search put it too low, so Phase 3's keyword half fixes it. `has_table` is the
*ceiling* — no chunk contains it, so there is nothing to rank and no later phase can touch it.
Only Step 1, the corpus decision, can.

*What it is NOT: a model-quality problem.* `compare_embedders` scores BGE-M3 (568M parameters) and
MiniLM (23M) at an identical **R@5 of 0.733**. A 25× larger model does not find it either, so
"use a better embedder" is the wrong conclusion.

*Why dense retrieval cannot see it:* `table_names` is **66 of 4792 characters — 1.38%** of the
text it lives in. One vector describes the whole chunk, so it encodes *"a passage about
introspection"*. That is correct and useless when the literal string is the question. The rarity
that erases it from the vector (6 chunks, 0.18% of the corpus) is the same rarity that makes
BM25's IDF term lock onto it — the two methods fail in opposite directions, which is the argument
for combining them.

*Why this needs its own decision entry:* **from outside, the two failures are identical** — both
simply return a wrong answer. Nothing in the output distinguishes them; only counting chunks
does. That is `D45`, and it is why `compare_embedders` excludes the zero-chunk question instead
of scoring it as a miss.

**Next sitting, §R3 — and it is in a different file:**
[`11-GENERATION.md`](11-GENERATION.md). The prompt: why the model refuses answerable questions
when told too firmly that it may refuse, how the cause was found after two wrong hypotheses, and
why fixing it did not violate the build-the-naive-version-first rule.

**Why the file changes here.** Everything in §R1 and §R2 happens *before* the five chunks are
chosen. Everything in §R3 happens *after*. That is a different subject, so it gets its own file —
with the `R` numbering carried across, so a reference to §R3 still means exactly one thing.

## Where the rest of the repo lives

| | |
|---|---|
| [`../phases/PHASE-1.md`](../phases/PHASE-1.md) | the plan: what was decided, what is next |
| [`09-DECISIONS.md`](09-DECISIONS.md) | every decision with what was rejected — **D09, D10, D05** are cited above |
| [`README.md`](README.md) | this folder's index and the three § numbering families |
| [`../rag/corpus.py`](../rag/corpus.py) | Step 1 in code — its docstring is the short form of R1.4–R1.6 |
| [`../rag/chunk.py`](../rag/chunk.py) | Step 2 in code |
