# Phase 1 — A deliberately dumb RAG (~2–3 weeks)

The current phase. [`ROADMAP.md`](ROADMAP.md) §3 defines it; this file plans it.
[`PHASE-0.md`](PHASE-0.md) is the phase before, complete except its Day 3 tunnel.

## What this phase is

Meaning-search only. **No hybrid search, no reranking, no agent.** Type a question in a
terminal, get an answer with sources. Ugly output is fine.

**Done when:** a question typed at a terminal returns an answer and the chunks it came from.

## Why it must be bad first

Hybrid search and reranking are **fixes for problems**. Build them now and they are best
practices copied from a blog post; build them in Phase 3, after watching dense retrieval
confidently return the wrong chunk, and each one is a number earned.

[`study/README.md`](../study/README.md)'s glossary already has the worked case — the query
*"what replaces `Query.get()`"* is one a keyword search nails and a meaning search fumbles.
**Phase 1 exists to make that failure real rather than illustrative.** Do not fix it here.

## The pipeline, and where each piece runs

```
corpus  ──chunk──►  chunks  ──embed──►  vectors  ──►  Qdrant
                                                        │
question ──embed──────────────────────────────────────► search
                                                        │
                                          top-k chunks ─┴─► Ollama ──► answer + sources
```

| step | machine | why |
|---|---|---|
| download, chunk | Mac | text processing, no GPU |
| embed the corpus | **lab PC** | thousands of passages; CPU is the bottleneck |
| Qdrant | lab PC | lives next to the vectors |
| embed one question | either | a single short string |
| Ollama | **lab PC** | the 3060, measured at 62.23 tok/s |

**The Day 3 tunnel matters here, not in Phase 0.** Every GPU step above means AnyDesk or
sitting at that desk until Tailscale is shared. Phase 0's checkbox did not care; this does.

**Start on the Mac anyway.** Steps 1–3 need no GPU, and a small corpus subset embeds on CPU
fine — enough to get end-to-end before the volume matters.

---

## Steps

### 1. Decide the corpus, and write down why

Not "download the docs". The corpus decides the ceiling on every later number, and the
question *"why this corpus?"* is the one an interviewer opens with.

#### What a corpus is, and why it is a decision

A language model does not know the answer to *"why can't I call `engine.execute` any more?"* —
it knows English and Python in general, and will produce something fluent that may be wrong.
Retrieval-augmented generation does not try to fix the model's memory. It **looks the answer up
first**, pastes the passages it found into the prompt, and reduces the model's job from *recall
the answer* to *summarise these five paragraphs*. The pile of text it looks up in is the corpus.

Two consequences, pulling in opposite directions:

- **A fact absent from the corpus can never be retrieved.** Hybrid search (Phase 3), reranking,
  the agent — all of them find the right chunk faster or more reliably. None of them can find a
  chunk that does not exist. The corpus is a hard ceiling on every number this project reports.
- **A corpus that is too large is also worse.** Every irrelevant page is one more thing search
  can confidently return *instead of* the answer. Bigger is not safer.

#### What is available, measured

Both versions this repo already pins publish their documentation as reStructuredText source
under `doc/build/`, tagged at exactly those versions — `pyproject.toml` pins 1.4.52 and
`verify_2_0.py` pins 2.0.51, so *"which release does this page describe?"* is answerable from
the directory a file came from rather than guessed.

```
# runnable: for t in rel_1_4_52 rel_2_0_51; do curl -sL \
#     "https://github.com/sqlalchemy/sqlalchemy/archive/refs/tags/$t.tar.gz" \
#     | tar xz "sqlalchemy-$t/doc/build"; done
#   for t in rel_1_4_52 rel_2_0_51; do D="sqlalchemy-$t/doc/build"; \
#     printf '%-11s %3d .rst  %7d bytes total  %7d changelog/  %2d files say future=True\n' \
#       "$t" \
#       "$(find $D -name '*.rst' | wc -l | tr -d ' ')" \
#       "$(find $D -name '*.rst' -exec cat {} + | wc -c | tr -d ' ')" \
#       "$(find $D/changelog -name '*.rst' -exec cat {} + | wc -c | tr -d ' ')" \
#       "$(grep -rl 'future=True' $D --include='*.rst' | wc -l | tr -d ' ')"; done
rel_1_4_52  170 .rst  4655735 bytes total  2712795 changelog/  15 files say future=True
rel_2_0_51  187 .rst  5319111 bytes total  3201073 changelog/   3 files say future=True
```

Three things that table decides:

- **`changelog/` is ~58% of 1.4's bytes and ~60% of 2.0's, and is mostly not prose.** Most of it
  is per-release one-line bug entries, plus migration guides for 1.0 through 1.4. High volume,
  low answer density, and a second source of version skew. The narrative directories
  (`orm/ core/ tutorial/ faq/`) are 1910065 bytes of 2.0's total; `changelog/migration_20.rst`
  — the 2.0 migration guide itself — is 93197 bytes.
- **The `.rst` source does not contain the API reference.** `.. autoclass::` / `.. automethod::`
  and friends appear 660 times in the 1.4 tree and 743 times in the 2.0 tree: instructions that
  say *at build time, read this class's Python docstring and paste it here*. The per-method
  reference pages a search engine lands you on exist only in the rendered HTML. "Docs source"
  and "the API reference" are two different corpora, not one.
- **Version skew is visible in the last column**, and it is the trap named below.

#### The version-skew trap, on one line of one file

The same tutorial page, at the two pinned tags:

```
# runnable: grep -n 'create_engine("sqlite' sqlalchemy-rel_*/doc/build/tutorial/engine.rst
sqlalchemy-rel_1_4_52/doc/build/tutorial/engine.rst:37:    >>> engine = create_engine("sqlite+pysqlite:///:memory:", echo=True, future=True)
sqlalchemy-rel_2_0_51/doc/build/tutorial/engine.rst:36:    >>> engine = create_engine("sqlite+pysqlite:///:memory:", echo=True)
```

1.4 teaches `future=True` as the forward-compatibility switch — `study/02-MIGRATION-2.0.md` §18
covers it as the migration bridge. By 2.0 it is gone from the tutorial entirely, surviving in
only three files (`errors.rst` and two changelog migration guides).

So: someone asks *"should I pass `future=True`?"*. Meaning-search returns the 1.4 tutorial — a
genuinely excellent, highly relevant passage about `create_engine`. The model reads it and
answers *yes*. **Confident, correctly sourced, and wrong for 2.0.** Nothing in the pipeline
noticed, because nothing in the pipeline knows which release that page describes.

That is not a bug to fix later. It is a property of what goes in the pile, which is why it is
settled here in Step 1 rather than in Step 4.

Candidates, in rough order of value:

- **the 2.0 migration guide** — enumerates exactly what broke, and is the direct answer to
  most real questions
- **SQLAlchemy 1.4 and 2.0 docs** — the ORM and Core pages people actually search
- **`deliverables/BREAKAGES.md`** — 23 verified breakages from this repo, already in
  question-and-answer shape
- **GitHub issues / Stack Overflow** — where the *messy* phrasing lives, and the reason
  Phase 2's golden set is harvested rather than invented

**Decision to record:** which of those are in, and what is deliberately out. Version skew is
the trap — 1.3 pages answering a 2.0 question is a wrong answer that looks right.

**Done when:** the corpus is on disk with a manifest saying where each file came from and
which version it documents.

### 2. Chunk it

A chunk is one retrievable idea (`ROADMAP.md` glossary). Too big and the embedding averages
several ideas into mush; too small and it loses the context that made it an answer.

Things that will bite, all worth writing down when they do:

- **code blocks must not be split.** Half a `before`/`after` pair is worse than neither.
- **headings are context.** A chunk saying *"this was removed in 2.0"* is useless without the
  heading naming what "this" is.
- **overlap** trades storage for not losing answers that straddle a boundary.

**Done when:** a chunking script produces chunks with their source file, heading path and
character range — and you can eyeball ten at random and find each one self-contained.

### 3. Embed and store

Model: **BGE-M3** (`ROADMAP.md` picks it). Store: **Qdrant**, which Compose already knows how
to run — the `db` service in `docker-compose.yml` is the pattern to copy.

**Measure, do not assume:** how long embedding takes, how much VRAM it wants alongside Ollama
(Phase 0 measured 7115 MiB free on the 3060 with qwen2.5-coder loaded), and how large the
collection is on disk.

**Done when:** a count of vectors in Qdrant matches the count of chunks, and a hand-written
query returns something plausible.

### 4. Retrieve and answer

Embed the question, take top-k, paste them into a prompt, send to Ollama, print the answer
**and the chunks it used**.

Sources are not decoration. Without them there is no way to tell a correct answer from a
lucky one, and no way to do Phase 2 at all.

**Done when:** `ask "why can't I call engine.execute any more?"` returns an answer and its
sources.

### 5. Break it on purpose, and write it down

The deliverable that makes Phase 3 mean anything. Run questions you know the answers to and
record where it fails:

- exact symbol names (`Query.get`) — where dense retrieval is weakest
- questions whose answer spans two chunks
- questions the corpus genuinely cannot answer, where the honest output is *"I don't know"*

**Done when:** a file of real failures with the retrieved-but-wrong chunk shown. That file is
the argument for everything in Phase 3.

---

## Decisions to make before writing code

| | |
|---|---|
| corpus scope | which sources, which versions, what is excluded |
| chunk size and overlap | and how you will know it was wrong |
| where Qdrant runs | lab PC alongside Ollama, or Mac for development |
| how the corpus gets to the PC | committed, or fetched by a script — it is large and regenerable |

`.gitignore` already excludes `corpus/raw/`, `models/` and `qdrant_storage/`, which answers
the last one: **fetch, do not commit.** A script that rebuilds the corpus is reproducible; a
200MB blob in git is not.

## What Phase 1 does not do

Hybrid search, reranking, an agent, evaluation, a golden dataset, and any tuning at all.
Every one of those is a later phase, and doing them here removes the before/after that makes
them defensible.

## Verification

Cold, no notes:

1. *"Why is your retrieval bad on purpose?"*
2. *"What is in your corpus and what did you leave out?"*
3. *"Your chunker split a code block. Why does that matter more than it sounds?"*
4. *"Dense retrieval missed a question containing an exact symbol name. Why?"*
5. *"How do you know the answer came from the sources and was not invented?"*

**Hard gate:** an answer with sources from a terminal, and a written list of failures with the
wrong chunks shown.
