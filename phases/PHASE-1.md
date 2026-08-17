# Phase 1 — A deliberately dumb RAG (~2–3 weeks)

The current phase. [`ROADMAP.md`](ROADMAP.md) §3 defines it; this file plans it.
[`PHASE-0.md`](PHASE-0.md) is the phase before, complete except its Day 3 tunnel.

## Where this phase is

| step | state | machine | what exists |
|---|---|---|---|
| [1. decide the corpus](#1-decide-the-corpus-and-write-down-why) | **done** 2026-08-13 | Mac | `rag/corpus.py`, `corpus/MANIFEST.json`, 270 files fetched |
| [2. chunk it](#2-chunk-it) | **built** 2026-08-14 · char range added 08-15 | Mac | `rag/chunk.py`, 3284 chunks. **Gate open:** eyeball ten |
| [3. embed and store](#3-embed-and-store) | **done** 2026-08-14 | Mac (M4/Metal) | `rag/embed.py` + `rag/index.py`, 3284 × 1024 vectors in Qdrant |
| [4. retrieve and answer](#4-retrieve-and-answer) | **done** 2026-08-15 | Mac — 18.4 tok/s | `rag/ask.py` — **the hard gate is met** |
| [5. break it on purpose](#5-break-it-on-purpose-and-write-it-down) | **built** 2026-08-15 | Mac | `rag/probe.py` → `deliverables/FAILURES.md`. **Gate open:** 19 verdicts |

**Picking this up cold?** Read each step's write-up in order — they carry the measurements and
the corrections.

> ### Phase 1 is BUILT, not COMPLETE — and the difference is not a formality
>
> All five steps run and the pipeline gate is met. **Three of this file's own stated criteria
> are still open, and every one of them is a human's:**
>
> | open gate | where | who |
> |---|---|---|
> | eyeball ten chunks at random and find each self-contained | Step 2 *Done when* | **Viraj** |
> | 19 `UNVERIFIED` verdicts — is each answer right? | Step 5 *Done when* | **Viraj** |
> | the five cold verification questions | [Verification](#verification) | **Viraj** |
>
> **One criterion was silently unmet until 2026-08-15 and is now fixed.** Step 2 asks for chunks
> carrying *"source file, heading path and character range"*. They carried a length (`n_chars`)
> and no offsets — which names a file but not a place in it. `char_start` / `char_end` now ship,
> verified on 400 sampled chunks. Texts and ids were byte-identical afterwards, so the vectors
> did not need rebuilding.
>
> That miss is the argument for the gates: **the code passing is not the phase passing.**

### The machine question, reopened 2026-08-14

The table above used to say **lab PC** for Steps 3 and 4. Step 3 then ran on the Mac in ten
minutes, and Step 4's generator turned out to be installed here already. The reason the plan
changed is worth keeping.

**The lab PC is shared, and it went away for two days** — the other user needed the 3060. A
plan whose only answer to that is "wait" has a single point of failure that is somebody else's
calendar.

So the machine that had never been measured got measured:

```
# runnable: sysctl -n machdep.cpu.brand_string; sysctl -n hw.ncpu; sysctl -n hw.memsize
Apple M4    10 cores    16 GiB unified memory    arm64    Docker 29.2.0
```

| | lab PC (Dell XPS 8950) | this Mac |
|---|---|---|
| accelerator | RTX 3060, **12288 MiB** dedicated VRAM | Apple M4, Metal over **16 GiB unified** |
| memory model | VRAM is a separate, hard budget | unified — the GPU sees system memory |
| availability | **shared; unavailable ~2 days from 2026-08-14** | always |
| Docker | Engine 29.7.2 | Desktop 29.2.0 |
| measured throughput | `qwen2.5-coder:7b` at **62.23 tok/s** | embedding **5.2 chunks/s**, generation **18.4 tok/s** |
| `qwen2.5-coder:7b` present | yes | **yes — already pulled, 4.7 GB** |

**Answered, 2026-08-15: the Mac was fast enough for all of Phase 1.** The whole corpus embedded
in ten minutes and questions answer in about five seconds. The 3060 is **3.4× faster at
generation** (62.23 vs 18.4 tok/s), which is the largest gap measured and the first real reason
to prefer it — but not one that changes anything at a terminal prompt.

**The design target this changes:** Steps 3 and 4 take the device as a **flag**, not an
assumption — same code, `--device mps` or `--device cuda` or `--device cpu`. If the Mac is too
slow, that produces a number justifying the wait instead of an unexamined dependency. Recorded
as [`../study/09-DECISIONS.md`](../study/09-DECISIONS.md) **D27**.

**Steps 1–2 need no accelerator at all**, so none of this blocks what is next.

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

> **Measured 2026-08-14, and it did not fumble.** BGE-M3 ranked the right chunk **1 of 3284**.
> The illustration above is the one this project has cited since the roadmap was written, and it
> does not reproduce. Step 3's write-up has the measurement. The argument for Phase 3 still
> stands on other evidence — the `future=True` version skew, and 26.6% of the index being
> cross-version duplicates — but **Step 5 has to find a failure that is real, not assumed.**

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
| download, chunk | Mac | text processing, no accelerator |
| embed the corpus | **either** — done on the Mac | measured: M4/Metal at 5.2 chunks/s, 627s for all 3284 |
| Qdrant | either | lives next to the vectors; both machines run Docker |
| embed one question | either | a single short string |
| Ollama | either | 3060 **62.23 tok/s**, M4 **18.4 tok/s** — 3.4x, the biggest gap measured |

**This table used to say `lab PC` for embedding, and the Day 3 tunnel used to matter here.**
Neither survived contact: the whole corpus embedded on the Mac in **10 minutes**, so the
expensive step was never expensive enough to need the 3060. See *The machine question* above
and [`../study/09-DECISIONS.md`](../study/09-DECISIONS.md) **D27**.

Ollama is the remaining row with a real reason to prefer the 3060, and now it is measured rather
than assumed: 3.4× on generation, against 1× on everything else.

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
  and friends appear **660 times in the 1.4 tree and 743 times in the 2.0 tree** — that is
  **stub lines, not files**. One `.rst` we *do* keep can contain many of them. Each line is an
  instruction: *at build time, read this class's Python docstring and paste it here*. The
  per-method pages a search engine lands you on exist only in the rendered HTML. Inside our
  270-file subset the same count is **514 / 569** (R1.4). "Docs source" and "the API reference"
  are two different corpora, not one. `270` is the file count; `660` is not.
- **Version skew is visible in the last column**, and it is the trap named below.

#### The version-skew trap, on one line of one file

The same tutorial page, at the two pinned tags:

```
# runnable: grep -n 'create_engine("sqlite' corpus/raw/*/tutorial/engine.rst
corpus/raw/1.4.52/tutorial/engine.rst:37:    >>> engine = create_engine("sqlite+pysqlite:///:memory:", echo=True, future=True)
corpus/raw/2.0.51/tutorial/engine.rst:36:    >>> engine = create_engine("sqlite+pysqlite:///:memory:", echo=True)
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

#### The decision, made 2026-08-13

| | source | why |
|---|---|---|
| **in** | `changelog/migration_20.rst`, **2.0 only** | enumerates exactly what broke; the direct answer to most real questions |
| **in** | `orm/ core/ tutorial/ faq/`, **both versions** | the pages people actually search, and the 1.4 side is half of every migration answer |
| **in** | `errors.rst`, `glossary.rst`, **both versions** | `errors.rst` maps real exception text to an explanation, which is the shape of Step 4's own acceptance question; `glossary.rst` defines the terms the other pages assume |
| **out** | the rest of `changelog/` | ~60% of the bytes, almost all per-release one-line bug entries, plus migration guides for 1.0–1.4 — more skew, few answers |
| **out** | `dialects/` | Postgres/MySQL/SQLite specifics, not migration material |
| **out** | `index/ contents/ copyright/ intro` `.rst` | navigation and a licence notice; nothing retrievable |
| **out** | the API reference | not in the `.rst` source at all — see above |
| **out** | GitHub issues, Stack Overflow, `lib/sqlalchemy` | volume, and each is a clean Phase 3 before/after instead |
| **out** | `deliverables/BREAKAGES.md` | **it seeds the Phase 2 golden dataset.** A corpus containing the answer key makes Phase 2 measure whether retrieval can find its own answers |

**Version skew is recorded, not prevented.** Every file carries its release in the manifest and
every chunk will inherit it, but Step 4 retrieves across both versions with no filter. A filter
here would delete the failure before it could be measured, and that failure is the argument for
Phase 3. The honest version of this system, in Phase 1, gets `future=True` wrong — and the Step 5
file will show which 1.4 page it came from.

`migration_20.rst` sits inside `changelog/`, which is otherwise excluded. It is named
individually; its ~33 siblings are not. `corpus/MANIFEST.json` states this under `selection`
so it does not read as a bug.

**Done when:** the corpus is on disk with a manifest saying where each file came from and
which version it documents.

#### Done — `rag/corpus.py`

```
# runnable: uv run python -m rag.corpus --force 2>&1
fetching rel_1_4_52 ...
fetching rel_2_0_51 ...
corpus manifest: corpus/MANIFEST.json
  rel_1_4_52   126 files   1903934 bytes   https://github.com/sqlalchemy/sqlalchemy/archive/refs/tags/rel_1_4_52.tar.gz
  rel_2_0_51   144 files   2154490 bytes   https://github.com/sqlalchemy/sqlalchemy/archive/refs/tags/rel_2_0_51.tar.gz
  TOTAL        270 files   4058424 bytes
  by top-level directory:
    orm           157 files   2109455 bytes
    core           66 files    884110 bytes
    tutorial       24 files    446017 bytes
    (root)          4 files    282520 bytes
    faq            18 files    243125 bytes
    changelog       1 files     93197 bytes
```

Four properties worth knowing, each of them a decision rather than an accident:

- **Neither version number is typed in the script.** 1.4.52 is read from `pyproject.toml`'s own
  dependency pin; 2.0.51 is read out of `verify_2_0.PIN`, the constant that already governs what
  `BREAKAGES.md` was measured on. The corpus cannot document a release the rest of the repo is
  not on. (`verify_2_0` is read as text rather than imported, because it calls `sys.exit()` at
  import time under 1.4 — correct for that module, fatal for this one.)
- **`corpus/raw/` is fetched, never committed** — `.gitignore` already said so. 4.5 MB on disk.
  `corpus/MANIFEST.json` **is** committed, at 74983 bytes: it is the provenance record, and a
  diff on it means the corpus actually moved.
- **The manifest carries no timestamp**, so it is a pure function of the two tags and the
  selection rules. Verified rather than asserted: `--force` re-downloads both tarballs and
  reproduces the file byte-for-byte. A `generated_at` field would make every regeneration a diff
  and train you to stop reading them.
- **Re-running is safe.** Like `seed.py`, an intact corpus is left alone; `--check` re-hashes all
  270 files against the manifest, and `--force` rebuilds.

```
# runnable: uv run python -m rag.corpus --check
all 270 files match the manifest
corpus manifest: corpus/MANIFEST.json
  rel_1_4_52   126 files   1903934 bytes   https://github.com/sqlalchemy/sqlalchemy/archive/refs/tags/rel_1_4_52.tar.gz
  rel_2_0_51   144 files   2154490 bytes   https://github.com/sqlalchemy/sqlalchemy/archive/refs/tags/rel_2_0_51.tar.gz
  TOTAL        270 files   4058424 bytes
  by top-level directory:
    orm           157 files   2109455 bytes
    core           66 files    884110 bytes
    tutorial       24 files    446017 bytes
    (root)          4 files    282520 bytes
    faq            18 files    243125 bytes
    changelog       1 files     93197 bytes
```

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

> **The character range was missed on the first pass, and shipped 2026-08-15.** Chunks carried
> `n_chars` — a *length* — which is not a range. It names a file but not a place in it, so a
> reader who distrusts a retrieved passage cannot open the original at the right spot. They now
> carry `char_start` / `char_end`, checked against the source on 400 sampled chunks, all 400
> bracketed correctly. Chunk texts and ids came out byte-identical, so the embeddings did not
> need rebuilding.
>
> Worth noticing *how* it was missed: the step was marked done because the script ran and the
> output looked right. Nothing checked the sentence in this file word by word. That is what the
> gates are for.

#### Done — `rag/chunk.py`

```
# runnable: uv run python -m rag.chunk
chunks: corpus/chunks.jsonl
  target=1800  hard_max=2400  overlap_max=400
  3284 chunks   3946041 chars
    1.4.52    1541 chunks
    2.0.51    1743 chunks
  with a code block: 2461   over hard_max: 34
  size  min=120  median=1299  p75=1601  p90=1740  p99=2451  max=5346
```

**The size was derived, not chosen.** Measuring the corpus first:

| | n | median | p75 | p90 | p99 |
|---|---|---|---|---|---|
| RST sections | 2351 | **1274** | 2569 | 3816 | 7149 |
| literal (code) blocks | 3811 | 275 | 489 | 782 | **1723** |

Two numbers decide it and they agree. The **median section is 1274 characters** — a section is
already "one idea with a heading on it", the unit the author chose, so a target above 1274
leaves most of them whole. The **99th-percentile code block is 1723** — a budget below that
guarantees splitting examples. `TARGET = 1800` clears both.

**Why median and not mean, since they both claim to say "typical".** Add everything up and
divide and you get the **mean**; sort them and take the middle one and you get the **median**.
They disagree whenever a few values are enormous — and here they are: the median chunk is 1299
characters and the largest is **5346**, with a 69236-byte glossary before it was split per term.
A single monster drags a mean upward; it cannot drag a median anywhere, because it is still just
one item at the end of the queue. **Sizing the chunker on the mean would have picked a target too
big for most sections in order to accommodate a handful of giants.**

`p99` in the table is the same idea pushed to the end: sort every code block by size and look at
the one 99% of the way along. A budget that clears p99 splits at most 1 in 100.

#### What the "eyeball ten at random" gate actually caught

The gate is not ceremony. Four defects survived a passing script and were only visible in the
samples:

| what the sample showed | cause | fix |
|---|---|---|
| a chunk that was just `===============` | overlined titles (`===` / title / `===`) were not detected, so the overline became its own chunk | detect overlines |
| **10.8%** of chunks under 150 chars — `.. _anchor:`, `.. toctree::`, `.. autoclass::` | Sphinx *instructions* were being indexed as content | `is_content()` + a `MIN_CHARS` floor |
| a chunk opening `"sed on"` — a word cut in half | overlap carried a raw `tail[-200:]` slice | overlap carries **whole prose blocks** or nothing |
| `"...based on the"` ending one chunk, `"argument given::"` starting the next | in RST the line ending `::` is the last line of the introducing paragraph, and it was being severed from its own example | the paragraph is pulled into the code atom |

Junk rate went **10.8% → 0.6%**, minimum chunk **8 → 120** characters, and chunks with no
heading at all **239 → 1**.

**A fifth defect was found by a test rather than the eye**, and it is the subtlest: per the RST
spec, **overline+underline is a different heading level from underline-only with the same
character**. SQLAlchemy relies on this — page titles are overlined `===`, sections are underlined
`===`. Keying the level on the character alone collapsed them, and every section silently lost
its parent heading. Fixed, the ancestry is real:

```
# runnable: the deepest heading_path in corpus/chunks.jsonl
Working with Engines and Connections > Using Transactions >
  Nesting of Transaction Blocks > Arbitrary Transaction Nesting as an Antipattern
```

**Two things are deliberately left alone.** `glossary.rst` is one `.. glossary::` directive
holding every term — 69236 bytes at 2.0 — so it is split per term rather than chunked as prose.
And RST markup is kept **raw**: `:class:`_orm.Session`` is not rewritten to `Session`, because
that is a fix for a problem Step 5 has not yet demonstrated ([`../study/09-DECISIONS.md`](../study/09-DECISIONS.md) **D04**).

**Still open for a human:** run `uv run python -m rag.chunk --sample 10` and confirm each of the
ten reads as one self-contained idea. The seed is fixed at `20260814`, so the ten are the same
ten every time and a review of them can be cited.

### 3. Embed and store

Model: **BGE-M3** (`ROADMAP.md` picks it). Store: **Qdrant**, which Compose already knows how
to run — the `db` service in `docker-compose.yml` is the pattern to copy.

**Measure, do not assume:** how long embedding takes, how much VRAM it wants alongside Ollama
(Phase 0 measured 7115 MiB free on the 3060 with qwen2.5-coder loaded), and how large the
collection is on disk.

#### One run, one machine, to a file

**Do not split the corpus across the two machines.** The question came up when the lab PC went
away, and the answer is no — recorded as [`../study/09-DECISIONS.md`](../study/09-DECISIONS.md)
**D36**.

**The job is too small to be worth splitting.** 3284 chunks, 3946041 characters — roughly a
million tokens through a 568M-parameter model, which is minutes on either machine. *(Estimated
from character count. Timing it is part of this step.)*

**And splitting it fails in ways that are silent.** Two halves embedded by different model
revisions are not comparable *at all* — cosine similarity between them is noise, not
degradation. A normalization setting that differs between halves breaks similarity across the
boundary while the search keeps returning results. Meanwhile the thing people worry about,
float rounding between Metal and CUDA, lands around 1e-6 and does not matter.

**The real blocker is Qdrant, not the model.** The two machines cannot route to each other, so
half-and-half does not produce one index — it produces **two Qdrant instances with no path
between them**, and merging means a hand-copied snapshot or re-embedding a half anyway.

**So the pipeline writes a file, and loading is separate:**

```
chunks.jsonl  ──embed──►  embeddings.npy  ──load──►  Qdrant
   3284             the expensive step        seconds, wherever
                    (portable artifact)       Qdrant happens to live
```

Worth doing whether or not the split was ever considered. Direct ingestion makes the index a
*side effect of a process*; a file makes it an **input** — copyable by hand, loadable anywhere,
and resumable after a failure instead of restartable.

**Pin the model revision explicitly**, not just its name. "BGE-M3" is not reproducible; a
revision hash is.

#### Running it on both machines — the right comparison

`--device` is a flag (`mps` / `cuda` / `cpu`), so the same code runs on either machine, and the
run reports **throughput and peak memory**. Run it on the Mac now, and on the 3060 when it is
free.

**Compare speed and memory headroom. Do not compare answer quality — there is none to compare.**
With the revision, dtype and normalization pinned, both machines produce the same vectors;
differences land near 1e-6, which cosine ranking cannot see. **If the two machines disagree
meaningfully, that is a bug, not a result** — something is unpinned, and the discrepancy is what
to chase. Keep that as a diagnostic.

What actually differs is whether **both models fit at once**: 7115 MiB free on the 3060 with
`qwen2.5-coder:7b` resident, versus 16 GiB of unified memory on the Mac shared with macOS and
Qdrant. If a machine cannot hold the embedder and the generator together, every query has to
unload one to load the other — an architectural consequence, not a tuning detail.

The comparison that *does* move retrieval quality is between **models**, not machines — see
[`../study/09-DECISIONS.md`](../study/09-DECISIONS.md) **D32** and **D37**.

**Done when:** a count of vectors in Qdrant matches the count of chunks, and a hand-written
query returns something plausible.

#### Done (3a — embedding) — `rag/embed.py`

```
# runnable: uv run python -m rag.embed --batch-size 8   (progress bars stripped)
model    BAAI/bge-m3  revision=5617a9f61b028005a4858fdac845db406aefb181
device   mps   batch_size=8   max_seq_length=2048
chunks   3284   4229821 chars
loaded in 4.7s
tokens   max=1586  mean=363  truncated=0
vectors  3284 x 1024  float32  -> corpus/embeddings.npy
encode   627.1s   5.2 chunks/s
memory   torch_allocated_mib = 2165.9
memory   process_peak_rss_mib = 944.1
```

13 MB on disk. **Zero truncated** — `MAX_SEQ_LENGTH = 2048` was a guess with headroom, and the
measured maximum is 1586 tokens, so it holds. The vectors check out: all 3284 norms are exactly
1.0 (normalization is on), no NaN, no Inf, no zero rows.

##### Bigger batches are *slower* on Metal

Backwards from the CUDA habit, measured on 256 chunks:

| batch | chunks/s |
|---|---|
| 2 | 7.4 |
| 4 | 7.4 |
| 8 | 6.3 – 7.7 *(two runs, same setting)* |
| 32 | 5.9 |
| 64 | 3.6 |

**Read this carefully: 2, 4 and 8 are indistinguishable.** Batch 8 measured 7.7 once and 6.3
another time, so that spread is noise and "8 is optimal" is not a claim this data supports. What
it does support is that **32 and 64 are clearly worse**. Likely cause: batches are padded to
their longest sequence, so a wider batch drags more short chunks up to a long one.

**A methodological flaw worth admitting:** `--limit 256` takes the *first* 256 chunks, not a
random sample. Those came out at ~7.4 chunks/s while the full run managed 5.2 — so the sweep was
measured on an unrepresentative, shorter-than-average slice. The ranking between batch sizes is
still informative; the absolute numbers were not the corpus.

##### 26.6% of the index is a cross-version duplicate

Found by checking whether any two vectors were byte-identical, which 443 pairs were:

```
# runnable: group corpus/chunks.jsonl by (heading_path, text)
distinct texts: 2847   texts appearing more than once: 437
chunks involved in a duplicate: 874
  duplicated ACROSS versions (1.4 text == 2.0 text): 437
  duplicated WITHIN one version:                      0
```

**Every single duplicate is cross-version, and none is within a version.** Much of SQLAlchemy's
prose simply did not change between 1.4 and 2.0, so the same paragraph exists in both trees and
gets embedded twice.

**This costs top-k slots, and it showed up on the first query run.** Asking *"why can't I call
engine.execute any more?"* returns, at ranks 1 and 2, the *same text* from `errors.rst` — once
tagged 1.4.52 and once 2.0.51. Two of five slots spent on one passage.

**Not fixed here, on purpose.** Deduplication is a fix, and Step 5 is where the cost gets
measured across real questions rather than one. What the fix should key on is also not obvious:
identical text at two versions is not always redundant, since the *version* is sometimes the
answer.

##### The predicted `Query.get()` failure did not happen

This one contradicts the plan, so it is recorded rather than quietly dropped.

`ROADMAP.md`'s glossary, this file, and `09-DECISIONS.md` **D04** all use the same illustration:
*"what replaces `Query.get()`"* is supposed to be a query keyword search nails and **meaning
search fumbles**, because `Query.get` is a literal string. Phase 1 was meant to make that failure
real. Measured:

```
# runnable: embed the query, rank all 3284 vectors by cosine
chunks in the corpus literally containing 'Query.get': 4
how many of those are in the top 5: 1
rank of the FIRST chunk containing 'Query.get': 1 out of 3284
```

**Rank 1 of 3284.** BGE-M3 did not fumble it.

**What this does and does not mean.** It does *not* show hybrid search is unnecessary — that is
one query, one model, one corpus, and Step 5 is the real test with a list of questions. It does
show that **the specific worked example this project has been citing since the roadmap was
written does not reproduce**, and continuing to cite it as though it does would be exactly the
kind of unmeasured claim `CLAUDE.md` exists to prevent.

Two plausible reasons, neither verified: BGE-M3 is a stronger model than the prediction assumed,
and the corpus only contains **4** chunks with that string — so there is very little for search
to "drift toward". Step 5 needs to find a case that fails for real.

#### Done (3b — Qdrant) — `rag/index.py`

```
# runnable: docker compose up -d qdrant && uv run python -m rag.index
created collection sqlalchemy-upgrade-agent-bge-m3-5617a9f6  dim=1024  distance=COSINE
points in Qdrant: 3284   vectors on disk: 3284
counts match
```

##### Why a database at all, when a dot product already worked

Worth being honest about, because the obvious answer is wrong. `rag/embed.py` leaves 3284 unit
vectors in a NumPy array and searching them is one line — `vectors @ query` — which is fast at
this size. **Speed is not the reason.** Three things are:

- **Filtering.** Every chunk carries its version. "Only 2.0 pages" is a filtered search, which a
  flat array cannot express without rebuilding itself per query. Phase 3 needs it.
- **The payload travels with the vector.** Step 4 prints sources next to the answer, so the text
  must come back *from the search* rather than from a separate lookup that could drift.
- **It stops being a script.** An in-memory array is something one process can use. A database is
  something several processes and the Phase 5 agent can share.

Claiming a 3284-row array needed a vector database would not survive one follow-up question.

##### The collection name carries the model and the revision

`sqlalchemy-upgrade-agent-bge-m3-5617a9f6`, not `chunks`.

Vectors from two model revisions are not comparable — cosine between them is noise, not
degradation. Qdrant has no collection-level metadata field to record what produced a collection,
so the fact goes where it cannot be ignored: **the name**. Re-embed with a different revision and
you get a *different collection* rather than a silently mixed one. Same move as declaring
`image:` in Compose — make the wrong thing inexpressible rather than merely discouraged.

##### A published port, which this repo's own rule says not to do

`db` publishes nothing, because its only client is another container. The rule was never "ports
are bad" — it was *"publishing is for traffic arriving from outside, and `app` is not outside."*

Qdrant's client is `rag/index.py`, a script you run on the host. **The host genuinely is
outside**, so a published port is the right tool here rather than a shortcut. Bound explicitly:

```yaml
ports:
  - "127.0.0.1:6333:6333"
```

The short form `6333:6333` binds `0.0.0.0`, which puts an **unauthenticated vector database on
every network the laptop joins**. That is a coffee-shop problem, not a theoretical one.

##### The healthcheck that lied — worth reading, it is the best failure here

First version used `CMD-SHELL`. The container ran perfectly, served every request, and reported
`unhealthy` forever:

```
# runnable: docker inspect sqlalchemy-upgrade-agent-qdrant-1 --format '{{json .State.Health.Log}}'
exit: 2
out: '/bin/sh: 1: cannot create /dev/tcp/127.0.0.1/6333: Directory nonexistent'
```

The Qdrant image has no `curl`, `wget` or `nc` — only `bash`. So the check uses bash's `/dev/tcp`
to open a socket and speak enough HTTP to read the status line. **But `/dev/tcp` is a bash
builtin, not a real device**, and `CMD-SHELL` runs the string through `/bin/sh`, which is dash
here. Dash has no such feature and fails on every probe.

Fixed by using `CMD` with an explicit `bash -c`. Healthy in 4 seconds.

**Why this is the worst failure shape available:** nothing crashed, nothing logged an error, and
the service was ready the whole time. Anything later depending on `condition: service_healthy`
would have waited forever on a container that was fine — a hang with no error anywhere.

##### Filtering, demonstrated on the duplicate problem

The unfiltered search for *"why can't I call engine.execute any more?"* returns the same
`errors.rst` passage at ranks 1 and 2 — the cross-version duplicate from D38, eating a slot.
Adding the filter recovers it:

```
# runnable: uv run python -m rag.index --search "..." --version 2.0.51
1. 0.633  2.0.51  doc/build/errors.rst          (was rank 1)
2. 0.605  2.0.51  changelog/migration_20.rst    (was rank 3 — the 1.4 duplicate is gone)
```

**This is not turned on by default**, and that is deliberate: D10 keeps the skew and the
duplication visible so Step 5 can measure what they cost. The filter existing is what makes
Phase 3's fix a one-line change rather than a rebuild.

##### Persistence

The vectors live in a named volume and survive a restart — `points: 3284, status: green` after
`docker compose up -d`. **Losing that volume costs one `rag.index` run of about a second**,
because the vectors themselves are a file. That split is the point of D36: the database is never
the only copy of anything expensive.

### 4. Retrieve and answer

Embed the question, take top-k, paste them into a prompt, send to Ollama, print the answer
**and the chunks it used**.

Sources are not decoration. Without them there is no way to tell a correct answer from a
lucky one, and no way to do Phase 2 at all.

**Done when:** `ask "why can't I call engine.execute any more?"` returns an answer and its
sources.

#### Done — `rag/ask.py`. **The hard gate is met.**

```
# runnable: uv run python -m rag.ask "why can't I call engine.execute any more?"
Q: why can't I call engine.execute any more?

You can no longer call `engine.execute` directly because it relies on "bound metadata"
and "implicit, connectionless" execution patterns, which are removed in SQLAlchemy 2.0
[4]. Instead, you should use the `Connection.execute` method of a `Connection` object
obtained from an `Engine`, or use the ORM's `Session` to execute statements [1].

[qwen2.5-coder:7b  78 tokens  18.4 tok/s  4.9s wall  prompt 1913 tokens]
------------------------------------------------------------------------------
SOURCES
[1] 0.633  SQLAlchemy 2.0.51  doc/build/errors.rst …
```

Correct, cited, and the five sources print underneath every time — never behind a flag.

##### Generation speed on the Mac, which D27 had left unmeasured

| | tok/s |
|---|---|
| RTX 3060 (Phase 0) | **62.23** |
| Apple M4, same model and tag | **18.4** |

**The 3060 is roughly 3.4× faster at generation** — a much bigger gap than embedding showed, and
the first number that gives the lab PC a real reason to exist for Phase 1. It does not change
anything yet: 4.9 seconds a question is fine for a terminal tool.

##### The bug that ate an afternoon, and it was mine

The first run **refused a question whose answer was in the prompt**:

```
Q: why can't I call engine.execute any more?
The sources do not answer this.
```

…while sources 3, 4 and 5 were literally *"'Implicit' and 'Connectionless' execution, 'bound
metadata' removed"* and contained the string `engine.execute`.

**Three hypotheses, tested in order, and the first two were wrong:**

1. *The cross-version duplicate at ranks 1–2 (D38) is eating slots.* — **No.** It still refused
   with `--version 2.0.51` (duplicate gone) and at `--k 10`.
2. *Retrieval put the answer too low.* — **No.** Feeding it **only** the three on-topic chunks,
   with retrieval removed as a variable entirely, still produced a refusal.
3. *The system prompt.* — **Yes.**

Same sources, three prompts, plus a question the corpus provably cannot answer — the API
reference hole from **D07**, *"what is the exact signature of `Session.execute`?"*:

**A is not a slogan.** It is this instruction, given to the model as a system prompt:

> If the sources do not contain the answer, say exactly: "The sources do not answer this."

*"Say exactly"* is the part that bites. It hands the model a **canned sentence it is allowed
to emit instead of answering.** "Do not contain the answer" is a high bar: the `engine.execute`
pages explained the removal without being a one-line FAQ, so the model treated them as a miss
and printed the canned line. That is over-firing — refusing a question whose answer was in
the prompt.

**B** is what shipped: *prefer answering from what the sources do say, even indirectly; only
if they are genuinely silent, then refuse.* Same canned sentence, but as a last resort, not
the default exit.

**C** has no refusal instruction at all. The model must always write an answer.

| prompt | what the model is told | answerable (`engine.execute`) | unanswerable (`Session.execute` signature) |
|---|---|---|---|
| **A** | if sources do not contain the answer, emit that canned sentence | **REFUSED** ✗ | refused ✓ |
| **B** | prefer answering; refuse only if the sources are silent | answered ✓ | refused ✓ |
| **C** | no "you may say you don't know" | answered ✓ | **ANSWERED** ✗ |

**Both failure modes are real and they pull opposite ways.** C invented a complete method
signature for `Session.execute` out of the model's own weights — exactly the hallucination the
clause exists to stop, and exactly the hole D07 predicted. A refused a question it could answer.

So the refusal clause is **necessary** (C proves it) and the strict wording **over-fires** (A
proves it). B is what shipped. `n=1` per cell — two questions is a diagnosis, not a benchmark,
which is what Step 5 is for.

**Why this counts as a bug rather than baseline naivety.** D04 says build the simple
architecture first — no hybrid search, no reranking. It does not say ship a prompt that refuses
answerable questions. *Simple* and *broken* are different, and the distinction is worth holding:
a wrong prompt would have made every Step 5 failure unattributable, because everything would
have failed.

### 5. Break it on purpose, and write it down

The deliverable that makes Phase 3 mean anything. Run questions you know the answers to and
record where it fails:

- exact symbol names (`Query.get`) — where dense retrieval is weakest
- questions whose answer spans two chunks
- questions the corpus genuinely cannot answer, where the honest output is *"I don't know"*

**Done when:** a file of real failures with the retrieved-but-wrong chunk shown. That file is
the argument for everything in Phase 3.

#### Done — `rag/probe.py` → [`../deliverables/FAILURES.md`](../deliverables/FAILURES.md)

19 questions across 5 categories, drawn from `BREAKAGES.md` — answers already known, already
hand-verified, and deliberately **not in the corpus** (D09), so asking about them is a fair test
rather than a lookup of the answer key.

```
# runnable: uv run python -m rag.probe
{ "refused": 8, "uncited": 3, "version_mixed": 13, "symbol_missing": 5,
  "single_source": 6, "retrieval_failure": 4, "ceiling": 1,
  "any_duplicate_slot": 2, "total_duplicate_slots": 2, "questions": 19 }
```

##### The script does not grade answers, and that is deliberate

Every answer is written out marked **`UNVERIFIED`** with a blank verdict line. D06 says the
golden dataset is hand-verified, never auto-generated — and a script that decided which of its
own answers were correct would be scoring against a key written by the same model family that
produced them. That measures self-consistency, not truth.

What it computes instead are **mechanical signals**: true or false without opinion. `refused`,
`uncited`, `duplicate_slots`, `version_mixed`, `single_source`. **None of them is automatically
a failure** — `refused` is the *correct* output for a question the corpus cannot answer.

##### The finding: two failures that look identical and need opposite fixes

Five questions retrieved nothing containing the symbol they asked about. Left there, that reads
as one problem. The script also counts how many chunks in the **whole corpus** contain that
symbol, and the five split cleanly:

| symbol | chunks in corpus | retrieved | so the failure is |
|---|---|---|---|
| `table_names` | **6** | ✗ | **retrieval** — the answer was there and search missed it |
| `keys()` | **7** | ✗ | **retrieval** |
| `cascade_backrefs` | **12** | ✗ | **retrieval** |
| `backref` | present | ✗ | **retrieval** |
| `has_table` | **0** | ✗ | **the ceiling** — there is nothing to find |

```
retrieval_failure: 4      <- what hybrid search and reranking are aimed at
ceiling:           1      <- a corpus decision wearing a retrieval costume
```

**This is the number Phase 3 has to beat, and the one it cannot touch.** Without the split, four
fixable failures and one unfixable one would have been reported as "five retrieval problems",
and Phase 3 would have been measured against a target that includes something it can never move.

`has_table` is D07's API-reference hole showing up concretely: it is an API-reference item, and
the API reference is not in the `.rst` source. R1.4's ceiling argument, in one row of a table.

##### The prediction was wrong about *which* symbol, and right about the failure

`Query.get()` was cited from the roadmap onward as the case dense retrieval fumbles. It did not
(D39 — ranked 1 of 3284). But **the underlying claim holds**: the `symbol` category has the
worst results of any — **4 of 6 refused, 3 of 6 retrieval failures** — it just shows up on
`table_names`, `keys()` and `has_table` instead.

That is a better outcome than either being right or being wrong. The illustration was replaced
by evidence.

##### What is still a human's job

Every verdict. The file has 19 `UNVERIFIED` lines waiting for `CORRECT` / `WRONG` / `PARTIAL`
and one sentence each. **The signals say where to look; they do not say what is true.** In
particular the 13 `version_mixed` questions need reading — most are harmless, and the point of
D10 was to find the ones that are not.

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
