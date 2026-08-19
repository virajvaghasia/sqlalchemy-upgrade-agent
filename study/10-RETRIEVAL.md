# Retrieval — study notes

Part of [`sqlalchemy-upgrade-agent`](../README.md).

**What you already know:** Python, SQL, and SQLAlchemy 1.4 vs 2.0 from `01` / `02`. That is
enough.

**What this file does not assume:** ChatGPT internals, "embeddings", "vectors", cosine,
Qdrant, or anything else from an AI blog. If a sentence uses a bold word, that word was shown
with an example earlier in this file. If it was not, that is a bug in the file.

[`../phases/PHASE-1.md`](../phases/PHASE-1.md) is the *plan* (what we decided to build). This
file is the *why*. Decision IDs like **D05** are rows in [`09-DECISIONS.md`](09-DECISIONS.md) —
a register of "we picked X, not Y, because Z." You can ignore the ID on a first read and still
follow the argument.

**The letter `R`.** Docker notes already used `§1`. SQLAlchemy notes already used `§0`–`§22`.
This topic needed a third numbering so `§1` cannot mean two things. `R` names this whole
system (the three-letter recipe on the next page), not "retrieval" as a topic. Search is
§R1–§R2 in *this* file. Writing the answer is §R3 in
[`11-GENERATION.md`](11-GENERATION.md).

**Two sittings. Stop after the first.**

| sitting | after it you can explain, in your own words |
|---|---|
| **1 — §R1** | why we look the answer up in our own files instead of asking a chatbot from memory; why some questions can never be answered from these files; why adding more files can make answers *worse* |
| **2 — §R2** | what the spreadsheet of numbers on disk is doing; why a score of `0.61` is not "61% similar"; why missing `table_names` and missing `has_table` are two different bugs |

R1.1–R1.6 are the ideas. **R1.7 is a real run that proved R1.5 half-wrong.** Read it last.

---

## If you have never built one of these — five facts, then a picture

Forget the jargon for one page. Here is the whole system as a library.

You walk into a library with a question: *"Why can't I call `engine.execute()` any more?"*

**A chatbot with no library** writes an answer from memory. It sounds sure. You cannot walk
over to a shelf and check.

**This project is a library plus a clerk.**

1. We bought **270 specific books** — SQLAlchemy's own documentation files, frozen at versions
   1.4.52 and 2.0.51. Not the live website. Not Stack Overflow. Not this repo's answer key.
   That set of books is the **corpus** (the only text search is allowed to look in).
2. We tore each book into **pages** of about 1800 characters, never cutting a code example in
   half. 3284 pages. Each page is a **chunk**. Search returns pages, not whole books, because
   a whole book is mostly off-topic for one question.
3. We cannot `grep` for meaning. `"close a session"` and `"terminate a connection"` share no
   words. So we gave every page a **location on a map** — 1024 numbers that place similar
   meanings near each other. That list of numbers is an **embedding** (also called a
   **vector**). The map-maker is a small program called BGE-M3. This is *not* the chatbot.
   Different job.
4. We put all 3284 locations in a **catalogue** that, given one location, returns the nearest
   neighbours fast. That catalogue is **Qdrant**. People call it a vector database. You can
   think "index": like a book index, but for positions instead of words.
5. When you ask a question, we put *the question* on the same map, take the **five nearest
   pages**, paste those five pages plus your question into one message, and send that message
   to a chatbot. The chatbot is `qwen2.5-coder:7b`, served by a program called **Ollama**
   (runs the model on this machine; no paid API). Five is **top-k** with k = 5: a hard budget,
   not "everything that looks related."

The chatbot still only does one thing: **write the next word**. We changed what it is looking
at. We did not teach it SQLAlchemy. We did not update its memory. We stuffed five pages into
one request.

That stuffing has a name. **RAG** = Retrieve (find pages) + Augment (paste them into the
message) + Generate (write the answer). Three steps. The middle one is a bigger message, not
a smarter chatbot.

The entire message you send the chatbot is the **prompt**. The question is only one part of
it. Instructions ("cite your sources") and the five pasted pages are also the prompt.

**Two clocks, because the slow work is done once:**

| when | what | how long, measured here |
|---|---|---|
| **once, before anyone asks** | tear the books into pages; put every page on the map; load the catalogue | ~10.5 minutes to map all 3284 pages |
| **every question** | put the question on the map (~40 ms); find the five nearest pages (~1 ms); send the stuffed message to the chatbot | seconds, plus however long the chatbot takes to type |

Without the "once" half, every question would mean mapping all 3284 pages first — **627
seconds instead of 0.04**. The catalogue is not a clever algorithm. It is a cache of work we
refuse to redo.

That is the whole machine. §R1 is *why* we built it this way, and what it still cannot do.
§R2 is *what those 1024 numbers actually are*. You can now read the diagram in R1.3 without
it being a wall of undefined words.

---

## §R1 — Why this system exists at all

A developer upgrading SQLAlchemy 1.4 → 2.0 types a question. We do **not** send that question
to a chatbot and hope. We search our 270 files first, paste the hits into the prompt, then
ask the chatbot to read. This sitting is why that is necessary, and what it still cannot do.

### R1.1 What happens when you just ask the chatbot

A real question:

> *"Why can't I call `engine.execute()` any more?"*

Type that into a chatbot with nothing else in the prompt — no docs pasted, no "only use these
pages." You get a fluent, confident paragraph. It may even be right. **You have no way to
tell.** There is no page to point at.

**What the chatbot is actually doing.** It writes the next piece of text, over and over. It
does not open SQLAlchemy's website. It does not open this repo. It does not have a table of
facts it looks up. Months or years ago, people trained it on a huge pile of internet text.
The result of that training is a giant file of numbers called **weights**. After training,
those numbers do not change when you ask a question. Asking is not learning. Completing a
paragraph is not searching.

Two ways that goes wrong. They need different names because they need different fixes.

**1. It never saw this.** A fact was missing from the training pile, or too rare to leave a
trace. The chatbot still answers. It has no "I don't know" button. It writes the most
plausible next sentence. That sentence can be invented. People call this a
**hallucination**. The useful picture is: *fluent, no basis*.

**2. It saw both versions and blended them.** This is why *this* project exists. SQLAlchemy
1.4 docs and 2.0 docs are both on the public internet. Both were almost certainly in the
training pile. The chatbot has completed a lot of text where `engine.execute()` is normal
(it *was*, in 1.4) and a lot of text where it raises (2.0). **It has no reliable way to tell
you which era it is drawing on.**

A migration assistant lives in the gap between two versions of the same library. That is
exactly the gap a chatbot's memory blurs.

**3. Even a right answer is uncheckable.** A confident paragraph with no source looks the same
as a confident paragraph with no basis. There is nothing to look at.

### R1.2 What looking it up first changes

Do not ask the chatbot to remember. **Look the answer up in our 270 files first, put those
pages in front of it, ask it to read.**

When a question arrives:

1. **Search** the 3284 pages for the five nearest to the question (the catalogue in the
   picture above).
2. **Paste** those five pages into the prompt, numbered `[1]` … `[5]`.
3. **The chatbot reads those pages** and writes a sentence. It is not recalling the internet.

**Without the lookup, the prompt is only the question:**

```
# illustration
what replaces Query.get()?
```

Small. The chatbot answers from the training pile.

**With the lookup, search runs first and the hits are pasted in:**

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

**Same question. Bigger prompt. The extra bytes are the five pages.**

That is what **augmented** means. Not a smarter model. A longer message.

What did **not** happen:

- You did **not** train the chatbot. The weights file is identical before and after.
- You did **not** add SQLAlchemy into its memory. Nothing was added to the model at all.
- You enlarged **one request**, by stuffing found pages into it.

Then it writes the next sentence — the ordinary thing it always does — on text *you* chose.
The script `rag/ask.py` builds that second prompt. `--show-prompt` prints the real one
instead of this sketch.

**Why this is better than asking from memory:**

| | |
|---|---|
| **Easier job** | "Read these five paragraphs" is easier than "recall the right SQLAlchemy page from a training pile years ago." A small local model can do it. That is why we run on this machine with no paid API (**D05**). |
| **You pick the books** | 270 files, two frozen versions. Not a blur of the whole internet. |
| **You can check** | Five specific pages sit next to the answer. If the answer says something they do not, you can see it. |

That last row is why the running system prints sources under every answer. Without them you
are back to trusting a fluent paragraph.

**What the lookup does not fix.** The chatbot can still ignore the five pages and answer from
the training pile anyway. It can still misread them. Looking it up makes the answer
*checkable*. It does not make it *guaranteed*. Later we score answers against a human-checked
list instead of hoping.

### R1.3 The same picture, with the names the rest of this file uses

The library story is the system. Here it is as a diagram. Every label was named in the
"five facts" page. **Build time** = the once column. **Query time** = every question.

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

**What each number in that picture is:**

| in the diagram | what it is |
|---|---|
| `270 .rst` | 270 files we kept. `.rst` is the plain-text format SQLAlchemy writes docs in (see Corpus below) |
| `3284 pieces` | those files, cut up. **Not a target** — it is what falls out of aiming at ~1800 characters. 3946041 characters ÷ 3284 = 1202 each on average |
| `3284 x 1024` | a table: **3284 rows** (one per chunk), **1024 columns** (one number each). Each row is one chunk's position in meaning-space |
| `1024` | how many numbers describe one chunk. Each is a **dimension** — a column, nothing more |
| `float32` | type of each number. *float* = has a decimal (`0.0213`, not `3`); *32* = 32 bits = **4 bytes** |

File size is multiplication, not a mystery:

```
3284 chunks  ×  1024 numbers each   =  3362816 numbers in total
3362816 numbers  ×  4 bytes each    =  13451264 bytes    (about 13 MB)
```

**That 13 MB is the entire "understanding" the search half has.** It is not a smarter model. Swap
in a 384-dimension embedder and the file is 3284 × 384 × 4 = **5 MB** — smaller, and (measured,
**D32**) it retrieves just as well. Size is fixed the moment you pick *how many chunks* and *how
many dimensions*. Quality is not in the byte count.

#### Why the chunks are not all exactly 1800

The chunker never cuts a paragraph or a code block in half. It adds whole blocks until the next
one will not fit, then stops.

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

- **The next block did not fit** — the bulge at 1500–1799, the fullest boxes.
- **The section simply ended.** A 400-character section *is* a 400-character chunk. Packing
  resumes under the next heading.

**1800 is a ceiling, not a quota.** Forcing every chunk to 1800 would mean cutting mid-sentence
and mid-code-block — the one thing Step 2 exists to prevent. The handful *above* 1800 are single
code blocks larger than the budget, emitted whole. An honest oversized chunk beats a silently
truncated example.

§R2 unpacks dimension, 1024 vs 2, and float32 vs float16. The table above is enough to read the
diagram.

#### The names again, with the details this project actually uses

You already have the library picture. This is the same list with the files and numbers
attached, so later sections can say "corpus" without repeating the story.

- **Corpus** — the only text search is allowed to look in. Ours: 270 reStructuredText files from
  SQLAlchemy **1.4.52** and **2.0.51**. Step 1, done.

  SQLAlchemy's docs are not a website we scraped. They are plain files in SQLAlchemy's git repo
  under `doc/build/`. The website is *built* from them. We downloaded two **tags** (permanent
  bookmarks on a release) and kept the files we chose:

  ```
  # illustration
  curl -sL https://github.com/sqlalchemy/sqlalchemy/archive/refs/tags/rel_2_0_51.tar.gz | tar xz
  ```

  `rel_2_0_51` is "the docs as they were at 2.0.51", which cannot move. "The docs as of today"
  can. `rag/corpus.py` records a SHA-256 per file so you can prove nothing changed underneath.

- **Chunk** — one searchable piece. You do not retrieve whole files: a file is mostly irrelevant
  to any one question. 3284 pieces. **Median 1299 characters, mean 1202.** Step 2, done.

  Two numbers on purpose. An earlier draft said "averaging about 1300", which was the **median**
  wearing the word "average". The mean is 1202. The gap is the chunker's design showing up:

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

  **Nearly a third land in 1500–1800** — piled up against `TARGET = 1800`. Only **3.2% get past
  1800**. Ceiling on the right, no floor on the left: short sections pull the mean *below* the
  middle value. A mean and a median that disagree mean the distribution is lopsided. Quoting one
  and calling it the other hides that.

- **Embed** — turn text into a list of numbers that represents *meaning*. That list is an
  **embedding** / **vector**. Ours: **1024 numbers per chunk**, model BGE-M3. Step 3, built —
  `embeddings.npy`.

- **Index / vector database** — answers one question fast: *given this vector, which stored
  vectors are closest?* Ours is Qdrant. Step 3b, built.

- **top-k** — the k best matches. Ours is **`DEFAULT_K = 5`** in `rag/ask.py`. Five slots, not
  "everything above a score". That hard budget is the mechanism R1.5 turns on.

- **Generation** — the model reads the five and writes a sentence. Ours: `qwen2.5-coder:7b`
  through Ollama. Step 4, built — `rag/ask.py`. Covered in §R3.

**Status:** all five steps are **BUILT**. Phase 1 is not **COMPLETE**. Three gates still need a
human: eyeball ten chunks, mark 19 answer verdicts, five questions cold. A script finishing is
not a gate. [`../phases/PHASE-1.md`](../phases/PHASE-1.md) lists them.

#### Why build time and query time are split

**Embedding is slow. Comparing numbers is fast.** So every slow thing was pushed into the once
half:

| when | what | measured here |
|---|---|---|
| **once, ahead of time** | embed all 3284 chunks | **627000 ms** (10.5 minutes) |
| **every question** | embed just the question | **~40 ms** |
| **every question** | compare it against all 3284 | **~1 ms** |

Without the cache, answering one question would mean embedding the whole corpus first. Every
question would cost **627 seconds instead of 0.04** — roughly 15000× worse, forever.

> **That 627 s is this Mac.** The same corpus embeds in about **165 s** on the lab PC's RTX 3060
> — 19.9 chunks/s against 7.2 (`09-DECISIONS.md` **D48**). The ratio the argument rests on does
> not change, because both halves move together: faster hardware shortens the one-off build and
> the per-question embed alike. **A build-time cost you pay once is worth optimising for
> convenience; it is not what makes the design right.**

A vector index is not a clever algorithm. **It is a cache of work you refuse to redo.** Pay ten
minutes once; each question afterwards is "embed one short string + 3284 multiply-and-adds."

Change the embedding model and all 3284 vectors become worthless — they live in a different
space (**D36**). The ten minutes comes back.

You can see Steps 1 and 2 without rewriting them:

```
# runnable: uv run python -m rag.corpus --check | head -1
all 270 files match the manifest
```

```
# runnable: uv run python -c "import json; s=json.load(open('corpus/CHUNK_STATS.json')); print(s['n_chunks'], s['n_chars'])"
3284 3946041
```

> **Why that reads the stats file instead of running the chunker.**
> `uv run python -m rag.chunk` prints the same numbers **and rewrites** `corpus/chunks.jsonl`
> and `corpus/CHUNK_STATS.json`. It is a build command, not a check.
>
> It looks harmless: the chunker is deterministic and the rewrite matches byte-for-byte. It is
> not harmless while anything downstream is running. `embeddings.npy` is row-aligned to
> `chunks.jsonl` **by position** — row *i* is chunk *i*. Rewrite the chunks under a running
> embed and you get an index whose vectors point at the wrong text. **Nothing errors.** Search
> keeps returning results attached to the wrong sources.
>
> Reading `CHUNK_STATS.json` opens a file and writes nothing.
>
> **`--sample` used to rewrite both files too.** It now builds in memory and touches nothing.
> A flag whose job is "show me examples" should not have side effects. Pinned by a test.
>
> **The habit:** before running a command to *verify* something, check whether it *mutates* the
> thing it verifies. A surprising number do.

### R1.4 The 270 files are a ceiling

**If a fact is not in those 270 files, search cannot find it.**

Later we will add extra search tricks (search by exact words as well as by meaning; a second
pass that reorders the hits). Those tricks reorder pages that *exist*. None of them can invent
a page. That cap is the **ceiling**: not "hard to find", **not present**.

**Read this table first.** Every number in R1.4 is here. **None of 514 / 569 / 660 / 743 is a
file count.** Those four count **stub lines** — one line of config inside a file we already
kept, looking like `.. autoclass:: Session`. One file can contribute many stubs. `270` is the
only file count in this section.

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

`# runnable` under a command means: paste it, the lines below are the printout.

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

Not “514 unused files.” Walk `corpus/raw/` and count every
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
measurement.

#### Measurement 3 — a question the ceiling actually blocks

Step 5 ran nineteen questions. One of them is a true ceiling: `engine.has_table()`. Count how
many of the 3284 searchable pieces even mention the name:

```
# runnable: grep -c has_table corpus/chunks.jsonl
0
```

**`0`** means the string is in **no chunk**. Ranking cannot rank an empty list. Phase 3 cannot
fix it. Phase 5 cannot fix it. The only fix is changing the corpus — a Step 1 decision.

Interviewer: *"Can't you just add reranking?"* Answer: *"Not for `has_table`. Zero chunks."*

> #### A correction worth keeping, because it nearly went in as the example
>
> This section first used *"what arguments does `Session.execute()` take?"* as the ceiling case,
> and claimed `execution_options` and `bind_arguments` were absent. **Checked, and they are not.**
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

### R1.5 Why a bigger corpus is also worse

The instinct: more docs = safer. Wrong for this system.

**Search returns a fixed number of chunks.** Ours is k = 5 — the constant `DEFAULT_K` in
`rag/ask.py`. Those five slots are all the model will ever see. New text can add answers. It also
adds **rivals** for the same five slots, on *every* question — including questions the new text
has nothing to do with.

**This is not a thought experiment. It already happened here, before anyone added anything.**
SQLAlchemy barely changed much of its prose between 1.4 and 2.0, so the same paragraph is in the
index twice — once per version. **874 of the 3284 chunks are one half of a cross-version
duplicate pair** (`D38`). `errors.rst` alone contains **27** such pairs. Here is one, byte-for-byte
the same text under two ids and two version tags:

```
# runnable: uv run python -c "
#   import json, collections
#   rows=[json.loads(l) for l in open('corpus/chunks.jsonl')]
#   g=collections.defaultdict(list)
#   [g[r['text']].append(r) for r in rows if r['source_path'].endswith('errors.rst')]
#   d=[v for v in g.values() if len(v)>1]
#   print('duplicate pairs in errors.rst:', len(d))
#   p=max(d, key=lambda v: len(v[0]['text']))
#   print(' ', [(x['id'], x['sqlalchemy_version']) for x in p])
#   print(' ', ' > '.join(p[0]['heading_path'])[:78])"
duplicate pairs in errors.rst: 27
  [('c00403', '1.4.52'), ('c01965', '2.0.51')]
  Error Messages > Connections and Transactions > QueuePool limit of size <x> ov
```

When a question lands near that paragraph, **both** copies score almost identically, because they
are the same words. Two of the five slots go to one paragraph. That is not a prediction: the very
first real question asked of this system — *"why can't I call `engine.execute` any more?"* —
came back with the same `errors.rst` passage at rank 1 and rank 2, one tagged 1.4.52 and one
tagged 2.0.51 (`D38`).

**Note what that example does not show.** Neither copy contains the string `engine.execute` —
**no chunk of `errors.rst` does.** They were retrieved on meaning, not words, which is §R2's
whole subject and the reason you cannot debug retrieval by grepping for the question.

Nothing was added to cause any of this; it is what a corpus holding two versions of the same book
does on its own. Now add SQLAlchemy's `changelog/` — roughly 60% of the doc tree by bytes, almost
all of it one-line release notes — and ask what those five slots look like on *every* question
afterwards.

#### "Irrelevant" is your word. The machine never uses it

There is no relevance test in this pipeline. No classifier, no cutoff, no "good chunk" flag.
The entire selection policy is this:

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

Qdrant returns the five stored vectors whose **direction** is closest to the question's
(cosine similarity). That is everything. **"Relevant" is a word you apply afterwards**, looking
at what came back. The machine has one quantity: *how close is this direction to that one*.

Those two things agree often enough to be useful, and disagree often enough to need Phase 2.
**Every entry in `FAILURES.md` lives in the gap.**

Three consequences:

- **Nothing is ever ruled out.** Every chunk is scored against every question. A chunk cannot
  sit a round out; it can only lose.
- **The band is narrow.** Two chunks picked at random score **0.540** (R2.5). The top hit for
  *"why can't I call `engine.execute()` any more?"* scored **0.633**. Best-of-3284 vs two
  unrelated paragraphs is **0.09**. Winning a slot is not a landslide.
- **Closeness is not usefulness.** A 1.4 page and its 2.0 twin sit at a median **0.9920**. They
  give opposite advice. If the score knew what "relevant" meant, that could not happen.

An *irrelevant* chunk is not one the system sets aside. It is one **you** would call useless,
still scored on every question, still able to outrank the page you needed.

Two real cases from our corpus decision:

**Case one — `changelog/`, which we excluded.** About 60% of SQLAlchemy's documentation by
bytes. Almost all of it is per-release one-liners like *"Fixed issue in ORM where…"*. Enormous
volume, almost no answers to the questions this system exists for. Including it would roughly
triple the index and fill those five slots with changelog fragments.

**Case two — version skew.** We kept *both* 1.4 and 2.0, because half of every migration
question is "what did 1.4 do?". Same page, two versions:

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

### R1.6 Why we left out the best document we have

Size is not the only reason to exclude something.

`deliverables/BREAKAGES.md` is this repo's own record of 23 verified 1.4→2.0 breakages, each
with the real error. It is already in question-and-answer shape. Adding it would **measurably
improve** answers — right content, dense, no noise.

We left it out anyway.

**It is the answer key.** It seeds the Phase 2 golden dataset: questions with known-correct
answers that retrieval gets *scored* against. A corpus that contains the answer key makes Phase 2
measure whether the system can find its own homework. The score goes up and means less.

That is **leakage** — eval answers sitting in the corpus. Real quality now, traded for an honest
number later. **D09.**

### R1.7 What happened when we actually ran it

R1.5 **predicted**: ask *"should I pass `future=True`?"* → meaning-search grabs the **1.4
tutorial** → answer yes.

This section is the **run**. Question **#7** in
[`../deliverables/FAILURES.md`](../deliverables/FAILURES.md) is that question. The answer was
still **wrong** — but **not the way R1.5 guessed.** Same poison, different bottle.

**What came back:**

> *"Yes, you should pass `future=True` to `create_engine`. This is necessary for enabling the new
> 2.0 API in SQLAlchemy and ensuring compatibility with the upcoming version [1]."*

Wrong for someone on 2.0. "Upcoming version" is a tell: 2.0 is the version being asked about,
not a future release.

**What R1.5 expected as `[1]`:** 1.4 `tutorial/engine.rst`.  
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

Three facts:

**1. A version filter would not have saved you.**  
This page's label is `2.0.51`. Drop every 1.4 chunk and it **stays**. "Just search 2.0" helps
the *twin tutorial* case (R1.5). It does **not** fix this case. Phase 3's version filter is
necessary and **not enough**.

**2. The page is 2.0 talking about 1.4.**  
The prose says *"**In 1.4**, this new API is available by passing `future=True`."* A human
treats those two words as history. The model dropped them and reported the advice as current.

Skew is two shapes:

| | example | does a version **filter** catch it? |
|---|---|---|
| **Wrong file version** | 1.4 tutorial wins a 2.0 question (R1.5 twins) | yes — drop 1.4 |
| **Right file, wrong era in the prose** | 2.0 migration guide describing 1.4 (this run) | **no** — metadata is already 2.0 |

**3. The right chunk was in the prompt and unused.**  
`[2]` was 2.0 `core/future.rst`: in 2.0 the flag does nothing useful. Retrieval got a correction
into the top-5. The answer cited only `[1]`. That is **generation** ignoring what it was given.
Visible only because sources are printed (R1.2).

**`UNVERIFIED` on #7 is not an oversight.** All 19 `FAILURES.md` rows stay unmarked until a
human writes CORRECT / WRONG / PARTIAL. A script grading its own answers reports whatever
number you wanted.

**One line.** R1.5 said the *1.4 tutorial* would poison the answer. The poison was a *2.0
migration page that still describes 1.4.*

---

## Vocabulary from this sitting

Same words as the library page, in one line each. If a row is opaque, reread the five-facts
page — not a glossary site.

| word | in this project |
|---|---|
| **chatbot / language model** | writes the next word. Does not open files. Ours is `qwen2.5-coder:7b` via Ollama |
| **weights** | the giant numbers file from training. Asking a question does not change them |
| **prompt** | the *entire* message we send: rules + five pages + the question |
| **hallucination** | fluent sentence, no basis — there is no "I don't know" unless we ask for one |
| **corpus** | the 270 books. Search may not look anywhere else |
| **chunk** | one page, ~1800 characters. Search returns pages, not whole files |
| **embedding / vector** | 1024 numbers = that page's position on the map |
| **Qdrant / index** | the catalogue: given a position, return the nearest pages |
| **top-k** | we only hand the chatbot **five** pages. New books compete for those five slots |
| **RAG** | find pages, paste them into the prompt, write the answer. We did not train anything |
| **cosine similarity** | how close two arrows point. 1.0 = same direction. Random pages here already score ~0.54 |
| **recall** | of the answers that exist in the 270 files, how many did search find? More files help |
| **precision** | of the five pages it returned, how many were actually useful? More files hurt |
| **version skew** | two shapes: (a) a 1.4 page answering a 2.0 question; (b) a 2.0 page whose prose is *"in 1.4, do X"*. A version filter catches (a), not (b) |
| **leakage** | putting the test answers in the library — why `BREAKAGES.md` is not one of the 270 |

---

## Before Sitting 2

Three read-only commands (none writes — see the warning in R1.3). Look at the output, not the
exit code:

```bash
uv run python -m rag.corpus --check
uv run python -c "import json; s=json.load(open('corpus/CHUNK_STATS.json')); print(s['n_chunks'], s['n_chars'])"
uv run pytest
```

### The four questions, in plain language

**Q1.** Search returns exactly five chunks. Adding more docs also adds more answers. Why can
that still make the system *worse*?  
*(R1.5)*

**Q2.** We cannot answer *"what is `engine.has_table()`"*. Why can no later search trick — extra
keyword search, a second-pass reorder, a bigger chatbot — ever fix that?  
*(R1.4)*

**Q3.** `BREAKAGES.md` would improve answers. Why did we keep it out of the 270 files?  
*(R1.6)*

**Q4.** We already have a `--version` filter. Question #7 still got the wrong answer from a
correctly labelled 2.0 page. Why didn't the filter save it?  
*(R1.7)*

Do not answer Q4 with *"the filter wasn't switched on."* Read source `[1]`'s first two words.

### Answers

**Q1 — why more docs can make it worse**

There are five slots. New text cannot add a sixth. It can only steal a slot from whatever was
winning.

Every chunk is scored on every question. Added text competes on queries it has nothing to do
with. Recall goes up, precision goes down, and precision is what fills the five slots.

*Not:* "it costs more tokens" or "search gets slower." The prompt always carries five chunks,
whether the index holds 3284 or three million. Comparing all 3284 takes **~1 ms** against **~40
ms** to embed the question. `D40` refuses speed as a reason for Qdrant.

*Example:* `changelog/` is ~60% of SQLAlchemy's docs by bytes, almost all one-line release
notes. Including it would roughly triple the index and spend slots on *"Fixed issue in ORM
where…"* on every question.

**Q2 — why Phase 3 cannot answer `has_table`**

The name is in **zero** chunks. Ranking cannot rank an empty list.

The corpus is documentation *source*. Method signatures live in HTML that Sphinx generates
later from `.. autoclass::` stubs. In our 270 files those stubs number 514 (1.4) and 569 (2.0).
Search indexes the empty instruction.

```
grep -c has_table corpus/chunks.jsonl  →  0
```

*Different problem:* `table_names` is in **6** chunks and still was not retrieved. That is a
*ranking* miss — Phase 3 hybrid search is the fix. `has_table` at 0 is the *ceiling* — only
Step 1 (change the corpus) can touch it. Same-looking wrong answer; different owner. **D45.**

**Q3 — why `BREAKAGES.md` is out**

It is the answer key for Phase 2.

If the corpus contains the eval answers, the score measures "can we find our own homework."
The number goes up and means less. That is leakage. **D09.** Real quality now, traded for an
honest number later.

**Q4 — why `--version` did not save question #7**

`[1]` was already a 2.0 page, so the filter was never positioned to catch it.

Skew has two shapes. A filter only catches one:

| shape | this run |
|---|---|
| wrong *file* version | not this — `[1]` is labelled `2.0.51` |
| right file, prose about another version | **this** — the page says *"**In 1.4**, pass `future=True`"* |

The model dropped those two words and reported the advice as current. It wrote *"upcoming
version"* — 2.0 is not upcoming.

*Underneath:* `[2]` was 2.0 `core/future.rst`, which says the flag now does nothing. The
correction was already in the top-5. The answer cited only `[1]`. Generation, on top of
retrieval. Visible only because sources are printed.

**Next sitting, §R2:** what an embedding actually is — how text becomes 1024 numbers, why
similar meanings sit close, and what "close" means. That is Step 3.

---


## §R2 — What the 1024 numbers actually are

**Sitting 2.** Stop after the questions at the end. Do not start [`11-GENERATION.md`](11-GENERATION.md) in the same sitting.

§R1 said: we put every page on a map of 1024 numbers so similar meanings sit near each other.
True. You cannot defend that sentence in an interview until you have *seen the file*.

You do not need linear algebra. You need three pictures:

1. A computer can check `==`. It cannot check "these two sentences mean the same thing."
2. If you give every page a position, "similar" becomes "close on the map."
3. The map is a spreadsheet on disk: `corpus/embeddings.npy`. 3284 rows, 1024 columns, 13 MB.

| subsection | after it you can say |
|---|---|
| R2.1–R2.2 | why `grep` cannot find a synonym; a vector is just a position |
| R2.3 | that spreadsheet is real; every row was stretched to length 1.0 on purpose |
| R2.4 | "close" means a small *angle* between two arrows, not a percentage |
| R2.5 | two random pages here already score **0.540**. So 0.61 is barely above noise |
| R2.6 | meaning-search cannot see a rare function name. That is a different bug from "the name is not in the files at all" |

### R2.1 The problem a map is solving

`grep "close a session"` will not find `"terminate a connection"`. They share no words. A
SQL `LIKE`, a hash, an exact filename — every exact-matching tool says unrelated. To a
person they are nearly the same sentence.

**You need a way to turn text into numbers arithmetic can compare**, where the arithmetic
gives the answer a person would. That is all an embedding is for. It is not a SQLAlchemy
encyclopedia. It does not store facts. It stores *where a page sits relative to other pages*.

### R2.2 A vector is a position — start with two numbers, not 1024

Suppose you described every page with exactly two numbers, like a map with two axes:

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

Each document is now a **point**. Two points close together mean two documents alike on those
two axes. You can measure similarity with a ruler.

An embedding is that idea, with two changes:

- **The axes are not named.** Nobody decided "axis 1 = formality". The model learned 1024 axes
  during training. No human knows what most of them mean. You never read them. You only compare
  them.
- **There are 1024 of them, not 2.** Meaning has more than two independent directions. Cram it
  into two and unrelated things land on top of each other.

**What the model does:** text in, position out. Trained so that text people consider similar
comes out nearby. That is the entire trick.

Nothing here is a lookup table of SQLAlchemy facts. It is a **map** of where passages sit
relative to each other. Search is "put the question on the same map, pick the nearest
neighbours."

### R2.3 What our vectors actually are

Three facts, then the file, then why length is 1.0. Do not skip the file — the rest is just
reading it.

| fact | in this repo |
|---|---|
| **A table, not a brain** | 3284 rows × 1024 columns in `embeddings.npy`. 13 MB. That is all search "knows" |
| **3284 was not chosen** | 3946041 characters packed toward 1800, never splitting a code block. The count fell out |
| **Every row has length 1.0** | so "close" is an *angle*, and a cheap multiply-and-add is exactly cosine |

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

**3284 rows, one per page. 1024 columns, one per unnamed axis. 13 MB.** That spreadsheet is
the entire "understanding" the search half has. It is not the chatbot. It does not contain
SQLAlchemy facts. It contains *where each page sits*.

The last printed line says every row has length **1.000000**. **Length** here is the same
Pythagoras you already know: square each of the 1024 numbers, add them, take the square
root — a 1024-sided hypotenuse. We forced every row to that length on purpose. The rest of
R2.3 is why. You can skip the float32 / float16 detour on a first pass and still follow
R2.4.

**`3284 × 1024` is a table.** Literally a spreadsheet — 3284 rows, one per chunk, and 1024
columns, one per number the map-maker produces:

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
# import random, math
# rng = random.Random(0)
# rows = [[rng.gauss(0, 1) for _ in range(1024)] for _ in range(3284)]
# norms = [math.sqrt(sum(x*x for x in r)) for r in rows]
# print('un-normalised   min %.4f  max %.4f  spread %.4f' % (min(norms), max(norms), max(norms)-min(norms)))
# after = [math.sqrt(sum((x/n)**2 for x in r)) for r, n in zip(rows, norms)]
# print('after dividing  min %.6f  max %.6f' % (min(after), max(after)))"
un-normalised   min 29.3964  max 34.4316  spread 5.0352
after dividing  min 1.000000  max 1.000000
```

A spread of **5.0352** collapsing to nothing. That is what the flag did to our file.

> **Why this block uses no NumPy, when every other vector block here does.** The others read
> `corpus/embeddings.npy`, which cannot exist without the embedding model, so they are marked
> `ENV` and never run in CI. This one demonstrates *arithmetic* and should run anywhere — but
> NumPy arrives in this project through the `embed` extra, which pulls ~2GB of torch and which CI
> deliberately does not install (`pyproject.toml` says why). Written with NumPy it passed locally
> and **failed in CI**, which is the check earning its keep: the machine that runs the docs is not
> the machine that wrote them. Standard library only, so the claim is checkable by anyone with
> Python.

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

**You have written this query hundreds of times.** In SQL, ranking is:

```sql
SELECT id, <some number> AS score FROM pages ORDER BY score DESC LIMIT 5;
```

The database computes one number per row, sorts by it, returns five. **Search here is that
statement.** The `LIMIT 5` is `DEFAULT_K` in `rag/ask.py`. The only part that is new is how
`<some number>` gets computed — and this section is only about that number.

Everything sits on a unit sphere (length 1) — meaning every chunk's 1024 numbers are scaled so
the arrow they describe has length exactly 1. Two arrows of length 1 can differ in one way
only: **direction**. So the score is the **cosine of the angle** between them:

| angle | cosine | means |
|---|---|---|
| 0° | **1.0** | same direction — as similar as the model can say |
| 90° | **0.0** | unrelated |
| 180° | **-1.0** | opposite |

Because every vector has length 1, cosine **is** the dot product — multiply matching pairs,
add. One CPU instruction over 1024 numbers. That is why searching 3284 chunks takes no
perceptible time, and it is what `vectors @ query` does in `rag/index.py`.

**What the number is not.** It is not a percentage and not a probability. `0.83` does not mean
*83% relevant* — there is nothing it is 83% of. It is a comparison between two arrows and it is
only meaningful **against the other scores in the same query**. The floor is not 0 either: two
unrelated pages in this corpus already score around **0.54**, because they are both technical
English about databases. So a chunk scoring `0.61` is not "somewhat relevant" — it is noise
that happens to be written in the same dialect. That is exactly the `table_names` failure in
§R4.3, where the five returned chunks beat the rest of the index by `+0.001`.

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

### R2.5 The number is not a percentage

`0.8343` looks like "83% similar". It is not.

**You cannot read a cosine score without knowing what unrelated text scores for this model on
this corpus.** For BGE-M3 here, that baseline is high:

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

### R2.6 What this cannot do — and Step 5 measured it

Meaning-search has a blind spot that is the mirror of its strength.

`Query.from_self` and `Query.filter` are, to an embedding model, almost the same thing: both
`Query` methods, same docs, near-identical sentences. Their *meanings* really are close. If you
asked about one and got the other, the answer is simply wrong. **An exact symbol name is not a
fuzzy concept.** The model has no way to know that.

Not theory. Step 5 ran it:

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

---

## Vocabulary from this sitting

| term | in this project |
|---|---|
| **vector / embedding** | a position: 1024 numbers produced from one chunk |
| **dimension** | one column in that list. None of them has a name you can read |
| **normalised / unit vector** | length exactly 1, so only *direction* carries meaning |
| **cosine similarity** | the angle between two directions; for unit vectors, just a dot product |
| **baseline similarity** | what two *unrelated* chunks score. Ours is **0.540**, not 0 |
| **dense retrieval** | search by these positions — Phase 1 |
| **sparse retrieval / BM25** | search by literal words. Nails exact symbols — Phase 3 |

## Before Sitting 3

Two commands. Look at the numbers, not the exit code.

```bash
uv run python -m rag.ask "how do I use joinedload?" --retrieval-only
uv run python -m rag.compare_embedders
```

The first needs Qdrant up (`docker compose ps` should show it `healthy`) and returns in a
second or two. The second takes **upwards of ten minutes** — it loads BGE-M3 *and* MiniLM and
re-embeds with both — and prints nothing until it is finished (Python buffers when it is not
writing to a terminal). Run it in your own shell. Its conclusion is `D32` and is already
recorded.

### What the first command returns — three things in one result

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

- **The whole top-5 spans 0.015** (0.715 → 0.700). When a question lands near a cluster, which
  chunk takes a slot is decided in the fourth decimal — noise. And 0.715 is not "72%
  confident": against a random-pair baseline of **0.540**, it is **0.175 above noise**.
- **`[2]` and `[4]` are the same passage at two releases**, **0.008 apart**. Two of five slots
  saying the same thing twice. `D38`: the duplicated index costing 20% of the budget on an
  ordinary question.
- **Four of five hits are 1.4** on a question that named no version. A 2.0 user gets a prompt
  that is 80% old-release text. Nothing noticed. That is R1.5 arriving without being provoked.

### What the second command returns — read the columns as sentences

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

**Rank** is the position of the first chunk that contains the answer, out of 3284. Rank 1 =
search put it first. Every other column is made from 15 of those ranks (one question dropped
because the corpus has no chunk — D45, so we do not score the *model* for a *corpus* hole).

| column | means | here |
|---|---|---|
| **R@5** | fraction of questions whose answer landed in the top five | `0.733 × 15 = 11`. Those 11 reached the model. Four did not |
| **R@10** | same at ten | `0.867 × 15 = 13`. So **2** answers sat at rank 6–10 — retrieved, missed the budget. Reranking exists to rescue those |
| **MRR** | average of `1 ÷ rank` | Rank 1 and rank 5 both count as a hit for R@5. MRR still splits them. The two models tie on R@5 and still differ on MRR (0.675 vs 0.668) |
| **median / worst** | raw ranks, not fractions | typical question: rank 1. Worst: 23 (BGE-M3) vs 79 (MiniLM) |

Read BGE-M3's row: *"11 of 15 answers reached the prompt, 13 reached the top ten, the typical
one was first, the worst was buried at 23."*

**What it settles (D32):** `568 ÷ 23 = 24.7×` the parameters and `259.7 ÷ 7.2 = 36×` the speed,
identical R@5. Ten-minute wait: `3284 ÷ 7.2 = 456` seconds for BGE-M3 vs `3284 ÷ 259.7 = 12.6`
for MiniLM.

**What it does not settle:** fifteen questions is a small sample. Identical R@5 is not
"equivalent models." When MiniLM misses, it misses far worse (79 vs 23), and nothing downstream
recovers a chunk buried that deep.

### The three questions, in plain language

**Q1.** Every vector in our file has length exactly 1.0. What does that buy? What does it throw
away?  
*(R2.3, R2.4)*

**Q2.** A search returns a top hit at 0.61. Is that good? What do you need before you can say?  
*(R2.5)*

**Q3.** `table_names` is in 6 chunks and search still missed it. `has_table` is in 0. Why are
those different problems?  
*(R2.6)*

### Answers

**Q1 — length 1.0: what it buys, what it throws away**

**Buys:** the cheap formula is the *correct* formula. Cosine is `(a · b) / (|a| × |b|)`. When
both lengths are 1, the denominator is 1, dividing by 1 changes nothing, so cosine **is** the
dot product. `vectors @ query` in `rag/index.py` is exactly right, not approximately right.

*Not a speed argument.* Skipping the division saves **0.92 ms** against **~40 ms** to embed the
question — about 2% of query time. Answer "speed" and *"how much faster?"* retracts it.

**Throws away:** magnitude. Overwritten, not de-weighted. Before normalising, lengths ran
`29.5299` to `35.0566`; after, min and max are both `1.000000`. That spread was "how much text
is in this chunk." Nothing downstream can recover it. Re-embedding all 3284 is the only undo.

*Why we do it anyway:* scale an unrelated chunk's vector by 3 and raw dot product ranks it
**1.1461** against the correct twin's **0.9691** — it wins for being long. Cosine scores it
**0.3820** and puts it last.

**Q2 — is a top hit of 0.61 good?**

**Unanswerable until you know what unrelated text scores here.**

Ours: 2000 random pairs average **0.540**, floor around **0.329**. So 0.61 is **0.070 above
noise**. Not "61% confident." The usable range is roughly 0.33 → 1.0, not 0 → 1.

Also ask the gap to the next hit. The `joinedload` query is 0.715, 0.714, 0.712, 0.706, 0.700 —
strong against random, **0.001** from its neighbour. Those are different questions.

*Consequence:* only the **ordering** is trustworthy. That is why we take top-k, not "everything
above 0.7." A threshold copied from another model's tutorial will return everything or nothing.

**Q3 — why `table_names` ≠ `has_table`**

**Different owners.**

| | in corpus | failure | who fixes it |
|---|---|---|---|
| `table_names` | 6 chunks | ranking too low | Phase 3 keyword search |
| `has_table` | **0** chunks | ceiling — nothing to rank | only Step 1 (change the corpus) |

*Not a "better embedder" problem.* BGE-M3 (568M) and MiniLM (23M) both score **R@5 = 0.733**.
A 25× larger model does not find `table_names` either.

*Why dense search cannot see it:* `table_names` is **66 of 4792 characters — 1.38%** of the
text it lives in. One vector describes the whole chunk → *"a passage about introspection"*.
Correct, and useless when the literal string *is* the question. The rarity that erases it from
the vector (6 chunks, 0.18%) is the same rarity that makes BM25 lock onto it. Opposite
failures — that is the argument for combining them.

From outside, both look the same: a wrong answer. Only counting chunks separates them. That is
**D45**, and why `compare_embedders` drops the zero-chunk question instead of scoring it as a
model miss.

**Next sitting is a different file:** [`11-GENERATION.md`](11-GENERATION.md) (§R3). Everything
above happens *before* the five chunks are chosen. Everything there happens *after*.

## Where the rest of the repo lives

| | |
|---|---|
| [`../phases/PHASE-1.md`](../phases/PHASE-1.md) | the plan: what was decided, what is next |
| [`09-DECISIONS.md`](09-DECISIONS.md) | every decision with what was rejected — **D09, D10, D05** are cited above |
| [`README.md`](README.md) | this folder's index and the three § numbering families |
| [`../rag/corpus.py`](../rag/corpus.py) | Step 1 in code — its docstring is the short form of R1.4–R1.6 |
| [`../rag/chunk.py`](../rag/chunk.py) | Step 2 in code |
