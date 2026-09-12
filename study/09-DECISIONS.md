# Design decisions — the register

Every decision this project has made, what was rejected, and **why**. Written for revision:
read the bold line, and if the reasoning is already in your head, move on.

**Why this file exists.** The rest of the repo explains *how* things work. Almost nothing in it
answers *"why not the other thing?"* — and that is the entire content of a design interview.
A decision whose alternatives were never written down is a decision you will re-derive badly,
under pressure, in front of someone who has heard the confident version before.

**How to read an entry.** Each has a stable ID (`D01`…`D98`), so other docs can cite `D14` and mean
it. The shape is always the same:

> **Decided** — what was actually done
> **Instead of** — the alternatives, named
> **Because** — the reason, and where the evidence lives
> **Asked as** — the interview question it answers

**Two honest flags appear throughout:**

- 🔒 **Locked** — reopening it costs more than it saves. `CLAUDE.md` lists these as
  "don't silently reverse".
- ⚠️ **Not yet justified** — chosen, but the reasoning was never recorded. These are the
  dangerous ones, and §H collects them. **Do not invent a rationale for these in an
  interview.** "We picked it and haven't yet earned the choice" is a defensible answer;
  a fabricated benchmark is not.

---

## §A — What the project is

### D01 — A codebase migration assistant, not a chatbot 🔒

> **Decided** — a retrieval system that answers questions about upgrading Python code from
> SQLAlchemy 1.4 to 2.0.
> **Instead of** — a general "chat with your docs" demo; a customer-support bot; a
> summarizer.
> **Because** — migration questions have *checkable* answers. "Does this code break on 2.0?"
> is true or false, and `deliverables/BREAKAGES.md` proves which. A support bot's output can
> only be graded on vibes, so the evaluation phase would have nothing to measure.
> **Asked as** — *"Why this project?"* / *"How do you know your answers are right?"*

### D02 — SQLAlchemy 1.4 → 2.0 as the subject 🔒

> **Decided** — this specific migration.
> **Instead of** — Python 2→3, Django versions, React class→hooks, Java 8→17.
> **Because** three properties had to hold at once, and this is where they did:
> - **It is finished.** 2.0 shipped; the answer set does not move under you mid-project. A
>   framework mid-migration would invalidate the corpus every few weeks.
> - **It mixes code, prose and error messages.** Chunking prose is easy, chunking code is
>   hard, and a corpus of only one teaches half a lesson.
> - **The failures are subtle rather than loud.** See D03.
> **Asked as** — *"Why SQLAlchemy? Isn't that a narrow choice?"* — the answer is that depth in
> one migration beats vague familiarity with a library, and by the end you know this break
> better than most people who use SQLAlchemy daily.

### D03 — The corpus is measured, not scraped 🔒

> **Decided** — a deliberately 1.4-style app in `experiments/` is run against real 2.0, and
> every failure is recorded as it actually happened. That record is
> `deliverables/BREAKAGES.md`, 23 entries.
> **Instead of** — writing the breakage list from the migration guide, or from memory.
> **Because** the documentation is not a reliable inventory of what breaks, and this was
> measured rather than assumed:
>
> ```
> # runnable: uv run --no-project --with 'sqlalchemy==2.0.51' \
> #             python -m experiments.sqlalchemy_1_4_vs_2_0.verify_2_0
>   22 of 24 patterns FAIL on 2.0.51
> ```
>
> One pattern (`row["col"]`) is reported **safe** by both 1.4-side migration tools and fails
> anyway. A hand-written list from the guide would have missed it.
> **Asked as** — *"Where did your ground truth come from?"* This is the strongest answer in
> the project. Lead with it.

### D04 — Build the naive version first, on purpose 🔒

> **Decided** — Phase 1 is dense-retrieval-only. No hybrid search, no reranking, no agent.
> **Instead of** — building hybrid + rerank immediately, which is what every tutorial does.
> **Because** hybrid search and reranking are **fixes for problems**. Built now, they are
> best practices copied from a blog post and you cannot say what they bought. Built in Phase 3,
> after watching dense retrieval confidently return the wrong chunk, each is a number you
> earned.
> **The worked case that was assumed, and then measured — read both halves.** The query *"what
> replaces `Query.get()`"* was cited from the roadmap onward as one keyword search nails and
> meaning search fumbles, because `Query.get` is a literal string. **On 2026-08-14 it was
> measured and BGE-M3 ranked the right chunk 1 of 3284.** The illustration does not reproduce.
> Phase 1 still exists to make failure real rather than illustrative — that is exactly why the
> assumed example got checked, and Step 5 now has to find one that fails for real. Evidence that
> does hold: the `future=True` version skew, and 26.6% of the index being cross-version
> duplicates that eat top-k slots (D38).
> **Asked as** — *"Why is your retrieval bad?"* — and the answer *"deliberately, and here is
> the file of failures it produced"* is far stronger than a system that was always fine.

### D05 — Zero paid API calls 🔒

> **Decided** — local models on the RTX 3060, plus free tiers only.
> **Instead of** — OpenAI embeddings and GPT-4 for generation, which is faster to build.
> **Because** two reasons, and the second is the real one:
> - Cost control on a portfolio project with no budget.
> - **A paid API hides the parts worth learning.** If embeddings are an HTTP call you never
>   see VRAM budgeting, batch sizes, or why model choice is a trade rather than a preference.
> **Cost of this decision:** local models are weaker, so answer quality will be worse than a
> GPT-4 version. That is an accepted trade, not an oversight — say so plainly.
> **Asked as** — *"Why not just use OpenAI?"*

### D06 — The golden dataset is hand-verified, never auto-generated 🔒

> **Decided** — AI may draft and reformat; only a human verifies what enters the golden set.
> **Instead of** — generating question/answer pairs with an LLM, which is standard and fast.
> **Because** an auto-generated golden set grades your own homework with your own answer key.
> If the same model family writes the questions, writes the answers, and is then scored
> against them, the score measures self-consistency and not correctness.
> **Asked as** — *"How did you build your eval set?"* — a question that separates people who
> have run an evaluation from people who have read about one.

---

## §B — The corpus (Phase 1, Step 1)

Full reasoning in [`../phases/PHASE-1.md`](../phases/PHASE-1.md) Step 1; this is the compressed
form.

### D07 — Documentation source from pinned git tags, not the rendered site

> **Decided** — fetch `rel_1_4_52` and `rel_2_0_51` tarballs and take `doc/build/**/*.rst`.
> **Instead of** — scraping `docs.sqlalchemy.org`; or downloading a prebuilt docs zip.
> **Because** three things follow from the tag:
> - **The version is a directory name, not an inference.** See D10 for why that matters.
> - **Headings and code blocks are explicit markup.** HTML-to-text conversion is lossy on
>   exactly the code blocks the chunker must not split.
> - **It is reproducible.** One script rebuilds it identically; a scraped site changes under
>   you.
> **What this costs, and it is real:** the API reference is **not** in the `.rst` source. Those
> pages are generated at Sphinx build time from Python docstrings — **660 / 743
> `.. autoclass::`-family *lines*** in the full 1.4 / 2.0 trees (not 660 unused files; one
> kept file can hold many stubs). Inside the 270 files we actually index the same count is
> **514 / 569** ([`10-RETRIEVAL.md`](10-RETRIEVAL.md) R1.4). So per-method reference pages are
> absent, and a question like *"what is `engine.has_table()`?"* has nothing to retrieve
> (`grep -c has_table corpus/chunks.jsonl` is `0`). *"`Session.execute` arguments"* was the
> first example and was wrong: those names are in the chunks.
> **Asked as** — *"What is in your corpus?"* and, if they are good, *"what is missing from
> it?"* Volunteer the API reference gap; being the one to name your own blind spot is worth
> more than being caught not knowing it.

### D08 — Narrative prose only; `changelog/` excluded except one file

> **Decided** — `orm/ core/ tutorial/ faq/` plus `errors.rst` and `glossary.rst` from both
> versions, plus `changelog/migration_20.rst` from 2.0 only. 270 files, 4058424 bytes.
> **Instead of** — taking `doc/build` entirely, which is a simpler rule to state.
> **Because** `changelog/` is roughly 60% of the bytes and is mostly per-release one-line bug
> entries — high volume, almost no answers, and it carries migration guides for 1.0–1.4 that
> are pure version skew. **A bigger corpus is not a safer corpus:** every irrelevant page is
> one more thing retrieval can confidently return instead of the answer.
> **`errors.rst` was added deliberately** (81992 bytes at 2.0): it maps real exception text to
> an explanation, which is the exact shape of Step 4's own acceptance question, *"why can't I
> call `engine.execute` any more?"*
> **Asked as** — *"How did you decide what to leave out?"*

### D09 — `BREAKAGES.md` is kept **out** of the corpus

> **Decided** — the repo's own 23 verified breakages are not retrievable.
> **Instead of** — including them, which would measurably improve Phase 1 answers, since they
> are already in question-and-answer shape and highly relevant.
> **Because** `BREAKAGES.md` seeds the **Phase 2 golden dataset**. A corpus containing the
> answer key makes Phase 2 measure whether retrieval can find its own answers. The score goes
> up and means less.
> **This is the subtlest decision in the project.** It costs real quality now to keep a number
> honest later.
> **Asked as** — *"Is there any leakage between your corpus and your eval set?"* Most people
> have not thought about it. Having thought about it before being asked is the signal.

### D10 — Version skew is **recorded**, not filtered

> **Decided** — every file carries its release in the manifest; Step 4 retrieves across both
> 1.4 and 2.0 with no filter.
> **Instead of** — filtering to 2.0 at query time; or excluding 1.4 docs entirely.
> **Because** the skew failure is the *evidence* Phase 3 is built on, and a filter deletes it
> before it can be measured. The failure is concrete and already located:
>
> ```
> # runnable: grep -n 'create_engine("sqlite' sqlalchemy-rel_*/doc/build/tutorial/engine.rst
> sqlalchemy-rel_1_4_52/doc/build/tutorial/engine.rst:37:    >>> engine = create_engine("sqlite+pysqlite:///:memory:", echo=True, future=True)
> sqlalchemy-rel_2_0_51/doc/build/tutorial/engine.rst:36:    >>> engine = create_engine("sqlite+pysqlite:///:memory:", echo=True)
> ```
>
> 1.4's tutorial teaches `future=True`; 2.0's has dropped it. Ask *"should I pass
> `future=True`?"* and dense retrieval returns a genuinely excellent, correctly-sourced 1.4
> passage — and the answer is wrong. Excluding 1.4 would also break the system's ability to
> say what 1.4 *did*, which is half of every migration answer.
> **Asked as** — *"What happens when your corpus contains two versions of the same page?"*

### D11 — Fetch, do not commit

> **Decided** — `corpus/raw/` is gitignored and rebuilt by `rag/corpus.py`.
> `corpus/MANIFEST.json` **is** committed, at 74983 bytes.
> **Instead of** — committing the 4.5 MB corpus for convenience.
> **Because** a script that rebuilds the corpus is reproducible; a blob in git is a snapshot
> nobody can regenerate or verify. The manifest is the part worth versioning — it records
> where every file came from, which release it documents, and its SHA-256. **A diff on the
> manifest means the corpus actually moved.**
> **Asked as** — *"How do you handle large data in git?"*

### D12 — The manifest carries no timestamp

> **Decided** — no `generated_at` field.
> **Instead of** — stamping every regeneration, which is what most generators do.
> **Because** a timestamp makes every rebuild produce a diff even when nothing changed, and a
> diff that is always present is a diff nobody reads. Without it the manifest is a pure
> function of the two tags and the selection rules.
> **Verified rather than claimed:** `--force` re-downloads both tarballs and reproduces the
> file byte-for-byte.
> **Asked as** — *"How would you know if your data pipeline's output changed?"*

### D13 — Neither version number is typed into the fetcher

> **Decided** — 1.4.52 is read from `pyproject.toml`'s dependency pin; 2.0.51 from
> `verify_2_0.PIN`, the constant that already governs what `BREAKAGES.md` was measured
> against.
> **Instead of** — two string literals at the top of `rag/corpus.py`, which is obviously
> simpler.
> **Because** literals drift. The corpus would silently document a release the rest of the
> repo is not on, and nothing would fail. Reading the pins means moving a pin without moving
> the corpus is a **test failure**, not a surprise three weeks later.
> **One wrinkle worth being able to explain:** `verify_2_0` is read as *source text* rather
> than imported, because that module calls `sys.exit()` at import time when SQLAlchemy is
> older than 2.0. Correct for that module, fatal for this one.
> **Asked as** — *"How do you keep configuration from drifting?"*

---

## §C — Provenance and reproducibility

### D14 — The measurement rule 🔒

> **Decided** — never assert a number, count, or output that was not derived. Every
> `# runnable` block must reproduce verbatim; folding and annotation are the script's job,
> never hand-editing in the markdown.
> **Instead of** — normal technical writing, where you run something once and type the result.
> **Because** every time this was violated in this repo, the underlying claim turned out to be
> wrong or unreproducible: a state trace with no file behind it, a hardcoded `issue_id in
> (1, 3)` dressed up as an observation, a wrong flush/commit answer, a fabricated table.
> **This is the most transferable thing in the project.** It is a working habit, not a repo
> convention.
> **Asked as** — *"How do you make sure your documentation stays true?"*

### D15 — The example rule

> **Decided** — every concept a doc introduces carries real code, real named-command output,
> or a worked before/after. Prose alone is a claim; a block underneath it is evidence.
> **Because** prose hides errors that examples expose. `03-PRACTICE-APP.md` described a schema
> for 292 lines with no code block and asserted *"Six tables."* There are **six mapped classes
> and eight tables** — visible the instant anything real was printed.

### D16 — The 2.0 version is pinned, not floating

> **Decided** — `PIN = "2.0.51"` in `verify_2_0.py`, interpolated into every printed command.
> **Instead of** — `>=2.0`, which is what it used to be.
> **Because** `>=2.0` drifted to 2.0.52 mid-project, and `BREAKAGES.md` quotes **exact error
> strings**. A patch release rewording one exception silently invalidates the deliverable.
> Running off-pin now warns loudly.
> **Asked as** — *"Why pin a patch version?"*

### D17 — Test real 2.0 without upgrading the project

> **Decided** — `uv run --no-project --with 'sqlalchemy==2.0.51'` builds a throwaway
> environment while `pyproject.toml` stays pinned to 1.4.
> **Instead of** — upgrading and downgrading; or maintaining two virtualenvs; or trusting the
> 1.4-side warning tools.
> **Because** the app under test **must stay broken** — it is the specimen. And the warning
> tools are not an inventory: the sweep misses patterns that raise without warning,
> `future=True` misses construction-time removals it never evaluates, and one pattern is
> called safe by both and fails anyway.
> **Asked as** — *"How do you test against a version you're not on?"*

---

## §D — Containers

### D18 — `python:3.11-slim`, not Alpine

> **Decided** — Debian-based slim, **214 MB**.
> **Instead of** — `python:3.11-alpine` at roughly **50 MB**, which is smaller and is the
> reflexive choice.
> **Because** Alpine uses **musl** libc, not glibc, so it needs `musllinux` wheels — and
> SQLAlchemy 1.4.52 publishes **zero** musllinux wheels, for any Python version or CPU. The
> Alpine build therefore compiles from source: a toolchain in the image, minutes of build
> time, and a build that breaks when a dependency changes. Its own dependency `greenlet` *does*
> publish musllinux wheels, so the failure is per-package and not predictable by inspection.
> **The lesson generalises:** "smallest base image" is a bad default. The right question is
> *which libc do my wheels target?*
> **Asked as** — *"Why not Alpine?"* — a very common interview question with a bad standard
> answer ("it's smaller").

### D19 — The image holds code; the container holds data 🔒

> **Decided** — `issues.db` is created at container start by `entrypoint.sh`. Never `COPY`ed,
> and never seeded at build time with `RUN`.
> **Instead of** — seeding during the build, which *looks* like it works.
> **Because** a build-time seed produces a **fixture, not a database**: it lands in a read-only
> image layer, so every write goes to the container's writable layer and disappears when the
> container does. The failure is silent — the app starts, queries succeed, and data quietly
> never persists.
> **Why this survives Day 6:** once Postgres has its own container, "ship the database inside
> the app image" is not a worse option, it stops being *expressible*.
> **Measured in** `04-DOCKER.md` §3.4 — and the instructive part is that nothing was
> deliberately broken to produce it. The container had been recorded as working on the
> strength of a green build and an `ls`, with the app never re-run. It was emitting
> `no such table: issues` the whole time.
> **Asked as** — *"Where does state live in your containers?"*

### D20 — `image:` is declared explicitly in Compose

> **Decided** — `image: sqlalchemy-upgrade-agent:latest` alongside `build:`.
> **Instead of** — `build:` alone, which works fine and is what most compose files do.
> **Because** with `build:` and no `image:`, Compose **invents** a name from project and
> service. That is a *different* image from anything you tagged by hand — both current, both
> built from the same Dockerfile, drifting apart in silence. It cost an hour once; a stale
> image 13 hours older than the code silently invalidated a networking measurement mid-session.
> **Asked as** — *"How do you make sure you're running the code you just built?"*

### D21 — Service-name DNS, no published ports

> **Decided** — the app reaches Postgres at hostname `db`; nothing is published to the host.
> **Instead of** — publishing 5432 and connecting via `localhost`.
> **Because** `localhost` inside a container means *that container*. An app connecting to
> `localhost:5432` is looking for Postgres inside its own network namespace. Publishing a port
> is for **host** access, and the app is not on the host.
> **A second measured finding:** `--network` does two jobs and only one is usually noticed. It
> provides DNS, and it provides **isolation** — a container on the default bridge cannot reach
> a user-defined network *even by IP*. It times out.
> **Asked as** — *"Walk me through how two containers talk to each other."*

### D22 — Healthcheck plus `condition: service_healthy`

> **Decided** — `pg_isready` on the `db` service; the app waits on it declaratively.
> **Instead of** — a retry loop in application code, or a `sleep` in the entrypoint.
> **Because** `depends_on` alone waits for the container to *start*, not for Postgres to
> accept connections — the gap is where the flaky-on-CI-only bug lives. A sleep is a guess
> that is simultaneously too long and occasionally too short.

### D23 — The Postgres role is `app`, not the project name

> **Decided** — role `app`, database `issues`, while everything else is
> `sqlalchemy-upgrade-agent`.
> **Instead of** — one name absolutely everywhere.
> **Because** a Postgres identifier containing a hyphen must be **quoted in every statement**
> that names it. The role lives in a different namespace, so matching the Compose service it
> belongs to is the useful consistency.
> **A related measured surprise:** `POSTGRES_USER` does **not** create a limited account. It
> renames the superuser — `rolsuper = t`.

---

## §E — Testing and CI

### D24 — Tests pin what the *docs* claim, not what SQLAlchemy does

> **Decided** — 42 tests asserting the repo's own documented claims: the row counts, the
> six-classes/eight-tables split, seed determinism, the `is_seeded` guard, and now the corpus
> selection rules.
> **Instead of** — testing that SQLAlchemy works, which is SQLAlchemy's job.
> **Because** the failure mode this project actually has is **documentation drifting from
> reality**, and prose has no test. `test_corpus.py` extends this to the corpus decision: it
> fails if a `changelog/` sibling is smuggled in, if `BREAKAGES.md` appears, or if the totals
> quoted in `PHASE-1.md` stop matching what the fetcher measured.
> **Asked as** — *"What do your tests actually protect?"*

### D25 — Every test is mutation-checked

> **Decided** — break the thing a test describes and confirm it fails, before believing it.
> **Instead of** — trusting a green suite.
> **Because** a test that cannot fail is decoration. Two of the new corpus tests were checked
> this way: a stale total in `PHASE-1.md`, and a `changelog/` sibling added to the manifest.
> Both correctly failed. **A `sed` that silently did not match** during one of those checks is
> exactly why the check is run rather than assumed.

### D26 — The CI gate was proved with a deliberately failing PR

> **Decided** — required checks on `main`, branch protection with `enforce_admins` on,
> demonstrated by opening a PR that fails and confirming GitHub refuses to merge it.
> **Instead of** — configuring branch protection and assuming it works.
> **Because** "I set up CI" and "I proved CI blocks a bad merge" are different claims, and only
> the second survives *"how do you know?"*
>
> ⚠️ **Corrected 2026-08-16: it was three checks, not four, and the missing one was the
> important one.** This entry said *tests / 2.0 evidence / image builds*. `docs reproduce` — the
> job that runs `tools/check_runnable` and enforces the measurement rule — **existed in
> `ci.yml` but was never added to the required contexts**, so a red run could not block a merge.
> The rule this repo cares most about was enforced by a job nobody was required to pass.
> Added to the required list on 2026-08-16; there are now four.
> **It caught something on its first enforced run.** PR #18 went red with
> `ModuleNotFoundError: No module named 'numpy'` while passing locally at 52/52 — a doc block
> using NumPy, which reaches this project only through the `embed` extra that the docs job
> deliberately does not install. **The machine that runs the docs is not the machine that wrote
> them**, and nothing but a required check surfaces that.
> **Asked as** — *"How do you know your CI actually gates anything?"* — and the honest answer
> now includes that one job was configured but not required for two days, which is a more
> useful story than a clean one.

---

## §F — Where the work runs

### D27 — The lab PC is the build machine; the Mac is the desk ⚠️ **weakened 2026-08-14**

> **Decided** — chunking and text processing on the Mac; embedding, Qdrant and Ollama on the
> Ubuntu lab PC (Dell XPS 8950, RTX 3060).
> **Instead of** — doing everything on the Mac, or everything on the PC.
> **Because** the split follows the GPU, and the vectors must live where Qdrant lives.
> Measured on that box:
>
> | resource | measured | note |
> |---|---|---|
> | VRAM | **12288 MiB** | the tight budget |
> | system RAM | **31 GiB** | not the constraint |
> | Ollama `qwen2.5-coder:7b` | **62.23 tok/s** warm | on GPU, ~4650 MiB resident |
> | VRAM left with the model loaded | **7115 MiB** | what the embedder must fit inside |
>
> **The 31 GiB figure corrected a guess.** The plan had assumed 12 GB of system RAM, which was
> wrong and had been used to justify deferring things. VRAM is the real budget.
> **Asked as** — *"How did you decide what runs where?"*
>
> ---
>
> **⚠️ Weakened 2026-08-14, and the reason is instructive.** The lab PC became unavailable for
> two days — it is a **shared** machine, and the other user needed the GPU. The plan's response
> to that was "wait", which is what a plan says when it has an unexamined dependency.
>
> Measuring the machine that was *not* examined:
>
> ```
> # runnable: sysctl -n machdep.cpu.brand_string; sysctl -n hw.ncpu; sysctl -n hw.memsize
> Apple M4    10 cores    16 GiB unified memory    arm64    Docker 29.2.0
> ```
>
> **The Mac is not a thin client, and "the lab PC is the build machine" was decided when it
> was an unknown.** Apple Silicon has Metal, unified memory means the GPU sees all 16 GiB, and
> BGE-M3 at roughly 568M parameters is about 1.1 GB in fp16. Docker is already running, so
> Qdrant has a home here too.
>
> **What is NOT claimed:** that the Mac is fast enough. Throughput has not been measured, and
> 16 GiB shared between macOS, Qdrant, an embedder and a 4.7 GB generator is tight. The point
> is narrower and more useful: **the question is now answerable today rather than in two days**,
> and if the Mac turns out to be too slow, that is a *number* justifying the wait rather than an
> assumption.
>
> **The real lesson, and the one worth saying in an interview:** a pipeline that only runs on
> one shared machine has a single point of failure that is a *person's calendar*. Steps 2–4
> should be machine-agnostic — same code, different device — and the device should be a flag,
> not an assumption baked into the plan. That is now the design target, and it came from an
> outage rather than from foresight.

### D48 — The 3060 embeds 2.8x faster, and bigger batches are slower on CUDA too

> **Measured 2026-08-17 on the lab PC** (RTX 3060, 12288 MiB), closing the half of `D27` that
> had never been tested. `D27` called this box the build machine on the strength of a
> *generation* benchmark alone — 62.23 tok/s against the Mac's 18.4. Embedding had no
> counterpart until now.
>
> | | chunks/s | full corpus, 3284 chunks |
> |---|---|---|
> | Mac (M4, Metal) | **7.2** | 456 s by that rate; the production run took **627 s** |
> | RTX 3060 (CUDA, batch 8) | **19.9** | ~165 s |
>
> **2.8x on the rate**, which is real and smaller than the 3.4x generation gap. Worth stating
> plainly: this machine is the build machine, and the margin is a factor of three, not an order
> of magnitude.
>
> **The batch sweep is the surprising half, and it contradicts what was predicted.**
> `logs/HANDOFF.md` Round 5 said the Mac's result — bigger batches *slower* on Metal — was "a
> Metal result and there is no reason to expect it on CUDA, where larger batches usually win."
> CUDA behaves the same way:
>
> ```
> batch    8   19.4 chunks/s   torch peak 2571 MiB
> batch   32   15.8            3754
> batch   64   12.4            5337
> batch  128    7.3            8496
> ```
>
> **Slower and eight times the VRAM.** Batch 8 is both the fastest and the cheapest, and the
> sweep went to 128 specifically because the prediction said it should win there.
> **Why, and it is the transferable part:** these chunks vary in length — median 1299
> characters, max 5346 — and a batch pads every sequence to the longest one in it. A bigger
> batch catches more outliers, so a larger share of the compute is spent on padding. The usual
> "larger batches win" intuition assumes uniform inputs. Documentation chunks are not uniform.
> **Rejected as a result:** copying a batch size across hardware, and the belief that a CUDA
> answer can be reasoned to from a Metal one. The sweep is cheap (`--limit 256`) and the
> prediction was wrong on both counts.
> **Asked as** — *"How did you pick your batch size?"* — where the answer is that it was
> measured on each machine, and the number that looked obviously right was 2.7x slower.

### D49 — Retrieval and generation fit on one 12 GiB card, together

> **Measured 2026-08-17.** Whether this box can serve both halves at once decides whether Phase
> 5's agent needs two machines.
>
> ```
> cold                                    597 MiB used
> qwen2.5-coder:7b resident              5246 MiB used   (100% GPU, 4.7 GB model)
> + embedder at batch 32, torch peak     3754 MiB
> ```
>
> **~9 GiB of 12 GiB, no OOM.** They coexist. And after the embed process exits, `nvidia-smi`
> returns to generator-only — the two do not stay stacked unless both processes are alive.
> **The margin is thinner than it looks**, because batch 32 was used for the coexistence test
> and `D48` says batch 8 is faster anyway at 2571 MiB. At batch 128 the embedder alone peaks at
> 8496 MiB and the pair would not fit.
> **So the operational rule is:** batch 8 is the right default for two reasons, speed and
> headroom, and only one of them was the reason anyone expected.

>
> ⚠️ **The embedding half was closed on 2026-08-17 — see `D48`.** This entry rested on a
> generation benchmark alone (62.23 tok/s against 18.4). Embedding is **19.9 chunks/s against
> 7.2**, a factor of 2.8 rather than the 3.4 generation shows. The claim survives; the margin is
> a factor of three, not an order of magnitude, and `D48` also records that the batch size which
> "should" have won was 2.7x slower.

### D28 — Langfuse stays in Phase 6

> **Decided** — no observability stack until Phase 6.
> **Instead of** — instrumenting from the start, which is what production instinct says.
> **Because** there is nothing to observe yet, and a second Postgres + ClickHouse + Redis +
> MinIO + web pile is ops noise during Phases 0–5.
> **Worth stating precisely:** this is *not* a RAM constraint. 31 GiB would fit that stack
> comfortably. The RAM justification died when the hardware was measured, and the decision
> stands on product grounds instead. **Do not offer the RAM reason — it is not true.**

### D29 — Handoff to the lab PC goes through git, not chat

> **Decided** — `logs/HANDOFF.md` on branch `lab/handoff`, with ASK and REPLY blocks; raw
> pasted output is the measurement.
> **Instead of** — running commands conversationally.
> **Because** the Mac (10.23.x) and the lab PC (10.25.x/16) cannot route to each other — `ssh`
> reports *"Operation timed out"*, not *"refused"*, which is the signature of no route rather
> than a closed port. Commands typed into chat bounce back unrun. A git branch is an
> asynchronous wire that works with no network path at all.
> **Still blocked on a person, not on work:** that PC's Tailscale identity belongs to another
> user, who must share the node.

---

## §G — Naming

### D30 — One name, everywhere it can be one 🔒

> **Decided** — repo, folder, GitHub, Compose project and built image are all
> `sqlalchemy-upgrade-agent`. Containers, network and volume derive from it.
> **Instead of** — short convenient names per context (the image was once `sqlagent`).
> **Because** nothing is inferred, so nothing drifts. **It is long to type, and that is the
> accepted cost** of never again wondering which of two images you just ran.
> **Where a different name is required, it says what it is** — see D23.

---

## §H — Not yet justified ⚠️

**Chosen but unearned.** They appear in `ROADMAP.md`'s tools table and glossary and are named as
"yours", but no comparison, benchmark or trade-off was ever recorded. Treat this section as the
honest edge of the project.

**D32 left this section on 2026-08-15**, measured against a model 25× smaller. It is kept below
in its settled form so the shape of the answer is visible: what it was compared against, what
the numbers were, and — the part people skip — what fifteen data points do **not** license.
**D31 left this section on 2026-08-17**, measured against pgvector — which won on every number, and the entry says so rather than reporting a tie. **It was empty from 2026-08-17 to 2026-08-21, and that emptiness was always a claim to be suspicious of**: it meant every choice had a recorded comparison, not that every choice was right. **One item re-entered on 2026-08-21** (Claude-written `verified_by` stamps on `g051`+) **and left the same day** — closed below. **§H is empty again as of 2026-08-21 evening.**

### CLOSED 2026-08-21 — `verified_by` on the second 50, closed by spot-check of ten, then verified

> **Decided** — Viraj closed the signature by **spot-checking ten, then verified**. The ten were
> risk-weighted (start at `g065`; prefer notes that still said *"Awaiting human stamp"*; mix
> unanswerable ceilings and answerable keeps): `g065`, `g097`, `g093`, `g075`, `g099`, `g095`,
> `g088`, `g087`, `g079`, `g074`. Sheet verdicts: **KEEP** nine; **FIX note** on `g065` (keep
> `answerable: false`); optional chunk twin swap on `g079` (`c01189` → `c03004`). He approved
> that sheet.
> **What was wrong before.** `--status` already printed *"100 verified by a human"* because
> `verified_by` was `"human"`, but the notes on `g051`–`g121` recorded Claude batch stamps
> (`CLAUDE_REVIEW`, `STAMPED human (batch N)`), and ten still contained *"Awaiting human stamp
> … (D06)"* with the field already set. `rag/golden.py` cannot write that field; the file was
> edited directly. **Enforcement was on the tool, not on the file.**
> **What the spot-check changed on `g065`.** The old reason *"0 narrative chunks"* was false —
> `c00484` / `c02056` exist (FAQ: CREATE VIEW / schema upgrade → use Alembic). **The ceiling
> still holds**: those chunks redirect to Alembic; they do not teach putting CREATE TABLE and
> CREATE VIEW in the same migration. Note rewritten; still no `answer_chunks`.
> **What this does NOT claim.** It does not claim Viraj `--show`'d all 50 of the second tranche.
> It claims a sampled defence under `D06`: ten held (one note fixed), so the batch stamps stand.
> The full-bar audit (chunks / live docs / 2.0.51 SQL, 100 PASS) remains the mechanical half.
> **Baseline.** `deliverables/baseline-phase1.json` stays the 50-item Phase 1 ruler (`D65` /
> `D61`). The 100-item scorecard is now **measured and verified** for Phase 3 paired work on
> those 100 ids — not a replacement of the saved 50-row artifact.
> **Asked as** — *"Your benchmark says a human verified it. How would anyone know that is
> true?"* → *"I spot-checked ten, including the one whose reason was already wrong; here is the
> sheet; I verified."*

### D31 — Qdrant, measured against pgvector 2026-08-17 — and pgvector won on every number

> **Decided** — Qdrant stays for Phase 1, and **not because it is better**. This entry sat in §H
> for weeks saying "chosen, never benchmarked". It has now been benchmarked, and the honest
> result is uncomfortable enough to be worth stating first: **pgvector beat it on speed, on
> service count, and on setup, and the reason to stay is switching cost rather than merit.**
> **Compared against** — `pgvector/pgvector:pg16` (extension 0.8.6), HNSW with
> `vector_cosine_ops`, loaded with this repo's own 3284 × 1024 vectors.
>
> | | pgvector | Qdrant |
> |---|---|---|
> | search, median of 5 queries × 10 runs | **0.45 ms** | 2.65 ms |
> | load 3284 vectors | 4.1 s | — (already indexed) |
> | HNSW build | 0.7 s | — |
> | table + index on disk | 40 MB | — |
> | extra containers | **0** — Postgres is already in Compose | 1 |
>
> **The speed column is real and does not matter**, which is the same shape as `D40`. Both are
> noise against the ~40 ms it takes to embed the question (`10-RETRIEVAL.md` R1.3): 0.45 ms and
> 2.65 ms are 1% and 6% of a query. **A 5.9× win on 2 ms is not a reason to migrate anything.**
>
> **The finding that does matter is that they disagree.** Over the 19 probe questions, the two
> returned **identical top-5 for 15 of 19** — so on **4 questions the model would have been
> handed different sources** depending on which store was running. Neither is wrong: both are
> HNSW, both approximate, and on the one question checked against a brute-force NumPy scan both
> matched exactly. **But it means the vector store is not a neutral component.** Swap it and
> Phase 2's numbers move without retrieval having improved, which is a trap worth knowing about
> before there are numbers to protect.
>
> **What the original justification claimed, and how it holds up.** `D40` chose Qdrant for
> metadata filtering, payload travelling with the vector, and "it stops being a script".
> pgvector does all three — filtering is a `WHERE`, payload is a column, and Postgres is not a
> script by anyone's definition. **None of those three distinguishes them.** What does
> distinguish them is that pgvector needs **no second service**, and this project already runs
> Postgres.
>
> **So why keep Qdrant.** Phase 1 is built on it, `D41` bakes the model and revision into the
> collection name, `rag/index.py` speaks its client, and Step 3b is done. Migrating costs a
> re-index and a rewrite to save 2 ms and one container. **That is a legitimate reason and it is
> not the reason originally given** — the entry now says which is which.
> **What this does not license:** claiming Qdrant was chosen on the merits, or that it is the
> right default for a project that does not already have it. At this scale, with Postgres
> already present, pgvector is the choice this repo would make starting over.
> **Asked as** — *"Why a dedicated vector database?"* — where the answer is now *"at 3284
> vectors, you don't need one; I measured it, pgvector is faster and one fewer service, and I
> kept Qdrant because migrating a working Step 3b buys 2 ms."* That survives the follow-up in a
> way a feature list does not.

### D32 — BGE-M3, measured 2026-08-15 — and the 25× smaller model matched it

> **Decided** — BGE-M3 stays for Phase 1. **No longer unjustified, and the justification is not
> the one expected.**
> **Compared against** — `all-MiniLM-L6-v2`, chosen as a deliberately distant point on the
> size curve rather than a near-neighbour: 23M parameters against 568M, 384 dimensions
> against 1024.
> **The metric needs no human verdicts.** Answer quality is reserved for a person (D06), but
> retrieval is mechanical: *for each probe question with a known symbol, at what rank does the
> first chunk containing that symbol appear?* `rag/probe.py` already pairs each question with
> the exact string, and the corpus says which chunks hold it.
>
> ```
> # runnable: uv run python -m rag.compare_embedders
> model                                        dim  params  chunks/s    R@5   R@10    MRR  median  worst
> BAAI/bge-m3                                 1024    568M       7.7  0.733  0.867  0.675       1     23
> sentence-transformers/all-MiniLM-L6-v2       384     23M     222.9  0.733  0.867  0.668       1     79
> ```
>
> **Identical recall@5 and recall@10. MRR within 0.007.** The 25× smaller model retrieves the
> right chunk exactly as often, 29× faster.
>
> **What this does not license.** `n = 15` questions. That is a diagnosis, not a benchmark, and
> switching a load-bearing component on fifteen data points would be the same unmeasured
> confidence D32 was flagged for in the first place. It also measures *retrieval*, not answers —
> Phase 2 tests whether better chunks become better answers.
>
> **The one real difference, which the headline numbers hide.** BGE-M3's worst rank is **23**;
> MiniLM's is **79**. They agree on the easy questions and diverge on the hard tail. That is
> exactly where a reranker operates, so the two models may not stay tied once Phase 3 exists.
>
> **What it changes now:** nothing, and that is deliberate. What it changes about the *answer*:
> "BGE-M3, because the roadmap said so" becomes "BGE-M3, and I measured it against a model 25×
> smaller which matched it on recall — it holds a real edge only on the worst cases, and I would
> revisit it after Phase 3."
>
> **It also answers D32's other open question.** MiniLM at 23M parameters would leave far more
> of the 3060's 7115 free MiB for the generator. If the VRAM measurement (HANDOFF ASK 5.3) shows
> BGE-M3 and `qwen2.5-coder:7b` cannot coexist, there is now a measured alternative rather than
> a guess.
> **Asked as** — *"Why that embedding model?"* — and the strong answer names the cheaper thing
> you tested it against, not the leaderboard you read.

### D33 — Chunk size 1800 characters, overlap by whole block — **settled 2026-08-14**

> **Decided** — `TARGET = 1800` characters, `HARD_MAX = 2400`, and overlap carried as **whole
> prose blocks** up to 400 characters rather than as a character slice. 3284 chunks.
> **Instead of** — the common default of ~512 tokens with 10–20% character overlap, copied from
> a tutorial.
> **Because the corpus was measured first**, and two numbers agree:
>
> | | n | median | p99 |
> |---|---|---|---|
> | RST sections | 2351 | **1274** | 7149 |
> | literal (code) blocks | 3811 | 275 | **1723** |
>
> A section is already "one idea with a heading on it" — the unit the author chose — so a target
> above the 1274 median leaves most of them whole. And the 99th-percentile code block is 1723,
> so a budget below that *guarantees* splitting examples. 1800 clears both.
> **Asked as** — *"How did you pick your chunk size?"* Almost everyone answers "512 tokens, it's
> the standard." Answering with the distribution of the corpus is the differentiator.

### D34 — Overlap is whole blocks, not characters — **a correction, kept on purpose**

> **Decided** — carry the previous chunk's last complete **prose** block if it is under 400
> characters. Never a partial slice, never a code block.
> **Instead of** — `tail[-200:]`, which is what the first version did and what most examples do.
> **Because the ten-sample review showed what a character slice produces:** one chunk opened with
> `"sed on"` — a word cut in half — and another opened with an orphaned fragment of the previous
> glossary term, which read as the definition of the term that followed it.
> **The deeper reason, which is the transferable one:** overlap exists so an answer straddling a
> boundary is not lost, and that matters when the boundary is **arbitrary**. This chunker only
> splits between paragraphs and code blocks — boundaries the author chose. Character overlap was
> solving a problem the design had already removed, while adding a new one.
> **Asked as** — *"Why do you use overlap?"* — the good follow-up is *"does your splitter even
> need it?"*, and most people have never asked themselves that.

### D35 — The "eyeball ten at random" gate is not ceremony

> **Decided** — a human reads ten fixed-seed random chunks before Step 2 is called done.
> **Because it caught four defects a passing script did not**, none of which any test would have
> been written for in advance: a chunk that was just `===============`, 10.8% of chunks being
> Sphinx *instructions* (`.. toctree::`, `.. autoclass::`) rather than content, the truncated
> `"sed on"`, and a sentence severed from the example it introduced. Junk rate went **10.8% →
> 0.6%**; minimum chunk **8 → 120** characters; chunks with no heading **239 → 1**.
> **And one defect the eye missed that a test caught** — RST treats overlined `===` and
> underlined `===` as *different* heading levels; conflating them silently stripped every section
> of its parent heading. **The two methods are not substitutes.**
> **Asked as** — *"How do you know your chunking is any good?"* — "I looked at the output" is a
> better answer than a metric, at this stage, because there is no ground truth yet to compute a
> metric against.

### D36 — Embed in one run, on one machine, to a portable file

> **Decided** — the embedding pass runs once, on whichever machine is free, and writes vectors
> to a **file**. Loading that file into Qdrant is a separate, cheap step.
> **Instead of** — splitting the corpus across the Mac and the lab PC to work around the GPU
> being unavailable, or writing vectors straight into Qdrant as they are produced.
> **Because** — the job does not need splitting, and splitting it introduces failure modes that
> are silent.
>
> **The job is small.** 3284 chunks, 3946041 characters — roughly a million tokens through a
> 568M-parameter model. That is minutes on either machine, not hours. *(Order of magnitude,
> estimated from character count; not yet timed. Step 3 measures it.)* Splitting a
> three-minute job across two computers is work created rather than saved.
>
> **What would actually break if it were split.** Three fatal, one famously overrated:
>
> | | fatal? | why |
> |---|---|---|
> | model revision drift | **yes** | two halves embedded by different model weights are not comparable at all — cosine similarity between them is noise, not degradation |
> | normalization mismatch | **yes** | one half unit-normalized and the other not silently breaks cosine across the boundary; the search still returns results |
> | dtype (fp16 CUDA vs fp32 MPS) | mostly | half the index systematically offset from the other half, invisible to a smoke test |
> | float rounding, Metal vs CUDA | **no** | ~1e-6; cosine ranking does not care. The one people worry about and the one that does not matter |
>
> **The blocker is Qdrant, not the model.** The two machines cannot route to each other (D29).
> So "half here, half there" does not produce one index — it produces **two Qdrant instances
> with no path between them**, and merging means a hand-copied snapshot or re-embedding a half
> anyway. The work gets done twice.
>
> **Why a file rather than direct ingestion**, and this is the part worth keeping even though
> the split was rejected: writing to `embeddings.npy` decouples the expensive step from the
> machine that ran it. The vectors become an artifact that can be copied by hand, loaded
> wherever Qdrant lives, and resumed after a failure instead of restarted. Direct ingestion
> makes the index a side effect of a process; a file makes it an input.
>
> **Asked as** — *"Your GPU box was unavailable. What did you do?"* The good answer is not "I
> waited" or "I split the job" — it is *"I checked how big the job actually was, and made the
> output portable so the machine stopped mattering."*

### D37 — Benchmark both machines on speed and headroom, never on answer quality

> **Decided** — Step 3 takes `--device` as a flag and reports throughput and peak memory. Run
> it on both machines, and choose on **speed and memory headroom**.
> **Instead of** — embedding on both and picking whichever gives "better" retrieval.
> **Because there is no quality difference to find.** With the model revision, dtype and
> normalization pinned (D36), both machines produce the same vectors — differences land around
> 1e-6, which cosine ranking cannot see. A bake-off assumes the runs can differ in quality; if
> they are pinned correctly, they cannot.
>
> **And if they DO differ meaningfully, that is a bug rather than a result.** It means something
> is unpinned: a different revision pulled, a different dtype, one half normalized and the other
> not. Keep this as a diagnostic — *"if the two boxes disagree, something is unpinned"* — and
> chase the discrepancy rather than crowning a winner.
>
> **What genuinely differs, and is worth measuring:**
>
> | | RTX 3060 | Apple M4 |
> |---|---|---|
> | memory model | **12288 MiB dedicated**, 7115 free with `qwen2.5-coder:7b` resident | 16 GiB unified, shared with macOS and Qdrant |
> | availability | shared machine | always |
> | throughput | unmeasured — the actual question | unmeasured |
>
> The memory row is the one with architectural consequences. **If a machine cannot hold the
> embedder and the generator at once, every query must unload one to load the other** — that is
> a design constraint, not a tuning detail, and it is what running on both actually reveals.
>
> **The comparison worth running is between MODELS, not machines.** "Which is better" is the
> right question aimed at the wrong thing: BGE-M3 versus `all-MiniLM-L6-v2`, `e5-large` or
> `nomic-embed-text` changes retrieval quality (D32, still unjustified). Two machines running
> the same pinned model do not.
>
> **Asked as** — *"How did you choose your hardware?"* The trap is answering with a quality
> comparison that cannot exist. The answer that shows understanding is *"the vectors are
> identical by construction, so the only real questions were throughput and whether both models
> fit in memory at once."*

### D38 — 26.6% of the index is a cross-version duplicate, and it is not fixed yet

> **Found** — 437 texts appear twice in the index, involving 874 of 3284 chunks. **Every single
> duplicate is across versions** (1.4 text identical to 2.0 text) and **none is within a
> version**: much of SQLAlchemy's prose did not change between releases, so the same paragraph
> is embedded twice.
> **Discovered by** checking whether any two vectors were byte-identical — 443 pairs were — then
> grouping the chunks by `(heading_path, text)` to find out why.
> **It costs top-k slots, observed rather than predicted.** The first real query run,
> *"why can't I call `engine.execute` any more?"*, returned the **same** `errors.rst` passage at
> ranks 1 and 2 — one tagged 1.4.52, one 2.0.51. Two of five slots on one passage.
> **Deliberately not fixed.** Deduplication is a fix, and Step 5 measures the cost across real
> questions rather than one. The fix is also not obvious: identical text at two versions is not
> always redundant, because sometimes the *version* is the answer.
> **Asked as** — *"What surprised you when you first built the index?"*

### D39 — The `Query.get()` failure was assumed for three months and did not reproduce

> **Claimed, from `ROADMAP.md` onward** — the query *"what replaces `Query.get()`"* is one
> keyword search nails and dense retrieval fumbles, because `Query.get` is a literal string.
> Cited in the roadmap glossary, `PHASE-1.md`, and this file's own **D04**.
> **Measured 2026-08-14** — BGE-M3 ranked the right chunk **1 of 3284**.
>
> ```
> chunks in the corpus literally containing 'Query.get': 4
> rank of the FIRST chunk containing 'Query.get': 1 out of 3284
> ```
>
> **What this does not mean.** It is one query, one model, one corpus. It does **not** show
> hybrid search is unnecessary — Step 5 is the real test, with a list of questions.
> **What it does mean.** The worked example this project has been citing since before any code
> existed does not reproduce, and repeating it would be exactly the unmeasured claim
> `CLAUDE.md` exists to prevent. All three places now carry the correction rather than the
> original.
> **Two plausible causes, neither verified:** BGE-M3 is stronger than the prediction assumed,
> and the corpus contains only **4** chunks with that string — so there is little for search to
> drift toward.
> **Asked as** — *"Did anything in your plan turn out to be wrong?"* This is the answer. A
> project where nothing was ever disproved is a project where nothing was ever checked.

### D40 — Qdrant over a NumPy dot product — and **not** for speed

> **Decided** — load the vectors into Qdrant (`v1.19.0`, pinned) rather than searching the array
> in memory.
> **Instead of** — `vectors @ query`, which is one line, needs no container, and is genuinely
> fast over 3284 rows.
> **Because — and the honest part is what is *not* claimed:** speed is not the reason at this
> scale. Three things are:
> - **Filtering.** Every chunk carries its version; "only 2.0 pages" is a filtered search, which
>   a flat array cannot express without rebuilding itself per query. Phase 3 needs it.
> - **The payload travels with the vector**, so Step 4 can print sources *from the search result*
>   rather than from a separate lookup that could drift out of step.
> - **It stops being a script.** An in-memory array is something one process can use; a database
>   is something several processes and the Phase 5 agent can share.
> **Asked as** — *"Why a vector database for 3000 documents?"* This is a trap question, and
> *"honestly, not for speed — for filtering and because the payload has to come back with the
> hit"* is the answer that survives the follow-up. Claiming performance would not.

### D41 — The collection name carries the model and the revision

> **Decided** — `sqlalchemy-upgrade-agent-bge-m3-5617a9f6`.
> **Instead of** — `chunks`, or the project name alone.
> **Because** vectors from two model revisions are not comparable (D36), and **Qdrant has no
> collection-level metadata field** in which to record what produced a collection. So the fact
> goes where it cannot be ignored: the name. Re-embed at a different revision and you get a
> *different collection* rather than a silently mixed one.
> **Same move as D20** — declaring `image:` so Compose cannot invent a second image. Make the
> wrong thing **inexpressible** rather than merely discouraged.
> **Asked as** — *"How do you handle re-embedding when the model changes?"*

### D42 — One published port, bound to 127.0.0.1, against this repo's own rule

> **Decided** — `ports: ["127.0.0.1:6333:6333"]` on the `qdrant` service, while `db` still
> publishes nothing.
> **Instead of** — no ports (consistent, but then the loader cannot reach it), or `6333:6333`
> (the form every tutorial shows).
> **Because the rule was never "ports are bad".** It was *"publishing is for traffic arriving
> from outside, and `app` is not outside."* Qdrant's client is `rag/index.py`, a script run on
> the host — **the host genuinely is outside**, so the exception is the rule being applied
> correctly rather than bent.
> **And the bind address is the part that matters.** `6333:6333` binds `0.0.0.0`, putting an
> **unauthenticated vector database on every network the laptop joins**. That is a coffee-shop
> problem, not a theoretical one.
> **Asked as** — *"Walk me through your compose file"* — being able to say why one service
> publishes and another does not, in one sentence, is the whole answer.

### D43 — The refusal clause is necessary AND over-fires, so it is worded as a last resort

> **Decided** — the system prompt says *"prefer answering from what the sources do say… only if
> the sources are genuinely silent, reply 'The sources do not answer this.'"*
> **Instead of** — prompt **A**: *"If the sources do not contain the answer, say exactly:
> 'The sources do not answer this.'"* — a canned sentence the model may emit *instead of*
> answering — or prompt **C**: no refusal instruction at all.
> **Because both alternatives fail, in opposite directions.** Measured against one answerable
> question and one the corpus provably cannot answer — the API-reference hole from D07:
>
> | prompt | what it tells the model | answerable | unanswerable |
> |---|---|---|---|
> | **A** strict canned refusal | emit that sentence if sources "do not contain the answer" | **REFUSED** ✗ | refused ✓ |
> | **B** last resort | prefer answering; refuse only if sources are silent | answered ✓ | refused ✓ |
> | **C** none | always write an answer | answered ✓ | **ANSWERED** ✗ |
>
> Without the clause the model **invented a complete method signature** for `Session.execute`
> from its own weights. With it phrased strictly, it refused a question whose answer was sitting
> in the prompt — confirmed by feeding it *only* the on-topic chunks, which it also refused.
> **How the cause was found matters as much as the answer.** Two wrong hypotheses were tested
> and discarded first: that the cross-version duplicates (D38) were eating top-k slots — no, it
> still refused with them filtered out and at k=10 — and that retrieval had ranked the answer too
> low, which the only-on-topic-chunks test ruled out. The bug was in the prompt, which was the
> one component nobody suspected because it was hand-written rather than measured.
> **n=1 per cell.** Two questions is a diagnosis, not a benchmark.
> **Asked as** — *"How did you tune your prompt?"* — the answer is that one instruction was
> found to be simultaneously load-bearing and harmful, and the wording that threads it was
> chosen by testing both failure directions rather than by taste.
>
> ⚠️ **Settled 2026-08-17 on the lab PC: the A/answerable cell was one observation in
> thirteen, and it never reproduced.** `rag/compare_prompts.py` was run ten times on the RTX
> 3060 (62.23 tok/s makes ten runs a sitting rather than an evening), after two Mac re-runs on
> 2026-08-16.
>
> | prompt | answerable | unanswerable | across all 13 runs |
> |---|---|---|---|
> | **A** strict canned refusal | refused **1 / 13** | refused 13 / 13 | the over-fire is not reproducible |
> | **B** last resort — **shipped** | answered 13 / 13 | refused 13 / 13 | **correct in 26 of 26 cells** |
> | **C** no refusal clause | answered 13 / 13 | **answered 13 / 13** ✗ | fabricates every single time |
>
> **What this settles, and what it does not.** *"The clause is necessary"* is now as solid as
> thirteen observations get: without it the model invented a `Session.execute` signature every
> time, and the fabrication is stable rather than random — same four arguments, same example
> database path. *"The strict wording over-fires"* is **1 in 13**, which is a coin-flip's
> distance from noise. It is no longer a mechanism this entry may assert.
> **B is unaffected and is the only variant never once wrong.** The decision stands; what
> changed is that half its stated justification does not survive measurement, and the entry says
> so rather than keeping the tidy version.
> **One caveat retired.** The index rebuild did not change what was retrieved — both Mac runs
> returned top-5 scores `0.646, 0.642, 0.639, 0.616, 0.615` in that order. Retrieval is
> deterministic; all variation was generation.
> **The lesson is about the register, not the prompt.** This entry shipped a decision off `n=1`
> per cell and read as settled for two days. Nothing was wrong with the decision. What was wrong
> was the confidence, and only re-running it found that — `rag/compare_prompts.py` exists so the
> next person does not have to take either table on trust.
> **Asked as** — *"Has anything in your decision log turned out to be wrong?"* — and this is the
> entry to answer it with.
>
> ⚠️ **Superseded in part by `D52`, 2026-08-17.** Round 8 ran all three wordings over all 19
> probe questions. **A and B refused the same 8 questions, identically.** This entry chose B over
> A on a single differing outcome that never reproduced — so it chose between two options that
> behave the same. *"The clause is necessary"* holds and is now confirmed across 19 questions
> (C refused 0, answering even the three the corpus provably cannot answer). *"B threads it"*
> does not: B is wrong on 5 of 19. **Read this entry as the record of how the prompt was picked,
> not as evidence that it is right.**

### D44 — A wrong prompt is a bug, not "naive baseline"

> **Decided** — fix a prompt that refuses answerable questions, even though Phase 1 is
> deliberately unsophisticated.
> **Instead of** — leaving it, on the grounds that D04 says build the bad version first.
> **Because *simple* and *broken* are different things.** D04 withholds hybrid search and
> reranking — architectural fixes for retrieval problems that have not been measured yet. It
> does not license shipping a component that does not work.
> **The practical cost of getting this wrong:** with prompt A in place, *every* Step 5 question
> would have failed, and every failure would have been unattributable — the file of failures
> that is supposed to justify Phase 3 would have recorded one bug forty times.
> **Asked as** — *"You said the system is bad on purpose. How do you tell that from actually
> broken?"*

### D45 — Split "retrieval failed" from "the corpus never had it" — mechanically

> **Decided** — `rag/probe.py` records, for every question, how many chunks in the **whole
> corpus** contain the symbol asked about. A miss then classifies itself:
> - **in the corpus, not retrieved** → `retrieval_failure`. Phase 3 can fix it.
> - **in no chunk at all** → `ceiling`. No phase can fix it (R1.4).
> **Instead of** — one `symbol_missing` flag, and sorting them out by reading.
> **Because the two look identical from the outside and need opposite responses.** Step 5 found
> five misses. Four were retrieval; one — `has_table` — is in **zero** chunks, because it is an
> API-reference item and the API reference is not in the `.rst` source (D07).
> **The cost of not splitting them:** Phase 3 would be measured against a target that includes
> something it can never move. "Five retrieval problems, fixed four" is a worse claim than "four
> retrieval problems, and one corpus decision", and only one of them is true.
> **Asked as** — *"How do you know your retrieval improvements actually helped?"* The answer
> starts with knowing which failures were addressable.

### D46 — The failure report records signals; a human writes the verdicts

> **Decided** — `rag/probe.py` writes every answer marked `UNVERIFIED` with a blank verdict line,
> and computes only **mechanical** signals: `refused`, `uncited`, `duplicate_slots`,
> `version_mixed`, `single_source`, plus D45's split.
> **Instead of** — having the script decide which answers were right, which would have produced
> a finished-looking report in one run.
> **Because** D06 applies here too. A script grading its own model's answers, using the same
> model family, measures self-consistency rather than correctness — and `FAILURES.md` is what
> Phase 3's before/after gets measured against, so a soft number there corrupts everything
> downstream.
> **None of the signals is a verdict**, and that is stated in the file: `refused` is the
> *correct* output for a question the corpus cannot answer, and 13 of 19 questions retrieved
> both versions, most of them harmlessly. **They say where to look.**
> **Asked as** — *"How did you evaluate it?"* — and being able to say what you deliberately did
> **not** automate is a stronger answer than a dashboard.

### D47 — §R3 stayed §R3 when it moved files; the `R` means RAG, not Retrieval

> **Decided** — generation went into `study/11-GENERATION.md` as **§R3**, continuing the run
> `10-RETRIEVAL.md` starts at §R1.
> **Instead of** — restarting the numbering as **§G1** in the new file, which is the tidier-looking
> option and reads as more descriptive.
> **Because the splitting rule already answers it.** `study/README.md` requires that "the
> numbering always continues across the split so existing references keep resolving", and every
> earlier split obeyed it — `01`→`02` carried §0–§15 into §16–§22, `04`→`07` carried §1–§6 across
> four files. §G1 would have made this the first split to break the rule it was following.
> **Three concrete costs of renumbering**, none of them hypothetical: 14 existing `§R3`
> references would have gone stale, including the next-work list in `CLAUDE.md`; the reader would
> gain a **fourth** numbering family to keep straight, when the prefix exists precisely to remove
> that ambiguity; and a reference in an old commit or an interview note would silently point at
> nothing.
> **What actually had to change was one definition, not fourteen references.**
> `10-RETRIEVAL.md` described `§R1–` as "the retrieval sequence", which is what made §R3-in-a-
> generation-file look wrong. It is the **RAG** sequence; retrieval and generation are both RAG.
> **The general rule, which is the part worth carrying:** where a prefix has to mean something,
> make it mean *the system the files describe*, not the topic of the first file that happened to
> use it. Subject-labelled prefixes do not survive a split; system-labelled ones do.
> **Asked as** — *"How do you keep documentation navigable as it grows?"* — and the answer is
> that the naming was chosen so that growth does not invalidate existing references.

### D50 — Every fix is verified twice: that it runs, and that the docs recommend it

> **Checked 2026-08-17.** `deliverables/BREAKAGES.md` marks each fix `fix OK`, which means
> `verify_2_0.py` **executed it** against real 2.0.51. That answers *"does this work?"* and not
> *"is this what SQLAlchemy tells you to do?"* — a fix can run perfectly and still be nobody's
> recommendation.
> **So the second check:** does the construct each fix reaches for actually appear in SQLAlchemy
> 2.0.51's own documentation source? Run over `corpus/raw/2.0.51`, the 13 fixes that name a
> distinctive construct:
>
> ```
> 12 of 13 found            has_table  NOT FOUND (0 files)
> get_table_names  3        relationship 62      _mapping    26
> create_all      22        aliased      11      unique()     2
> select(         50        scalars      28      autobegin    6
> begin_nested     4        session.add  23
> ```
>
> **The one miss is the one to expect, and it confirms something from a different direction.**
> `has_table` appears in **zero** `.rst` files at `rel_2_0_51`. The fix is not wrong —
> `inspect(engine).has_table()` runs, and we ran it. It is documented only in the **generated API
> reference**, which is not in the `.rst` source (`D07`). That is the same hole that makes
> `FAILURES.md` question 4 a *ceiling* case rather than a retrieval failure, arrived at here
> without going near the retrieval system.
>
> **What this establishes, and what it does not.** Three claims are easy to run together and only
> two are checked:
>
> | claim | how | status |
> |---|---|---|
> | the fix **runs** on 2.0.51 | `verify_2_0.py` executes it | all 23, `fix OK` |
> | the fix is what the docs **recommend** | construct present in the pinned `.rst` source | 12 of 13 |
> | the fix is the **best** way | — | **not verified, and not verifiable this way** |
>
> The third is a judgement. *"The docs mention this construct"* is not *"this is the idiomatic
> replacement"*, and no grep closes that gap.
>
> **Why the offline copy beats opening a browser**, which is the obvious alternative and the
> weaker one: `corpus/raw/2.0.51` came from `rel_2_0_51`, an immutable git tag, with a SHA-256
> per file in `MANIFEST.json`. A browser shows whatever `docs.sqlalchemy.org` serves today, which
> may have been edited since the release. **Checking against the tag is checking what 2.0.51
> actually shipped**; checking against the website is checking what the project currently says
> about it. For a migration tool pinned to exact versions, only the first one answers the
> question.
> **Asked as** — *"How do you know your fixes are right?"* — where the strong answer is that
> "right" was split into two checkable claims and one uncheckable one, and the uncheckable one is
> named rather than quietly folded in with the others.


### D51 — Raising k did not reduce refusals, so Phase 3's premise is wrong for these failures

> **Measured 2026-08-17 on the lab PC.** Round 7 swept `k` over the 19 probe questions to find
> out how many failures a single integer fixes, because one answer had ranked **6** against
> `DEFAULT_K = 5`.
>
> ```
>              k=5   k=6   k=10
> refused        8     8      8      <- unchanged
> symbol_missing 6     5      4
> retrieval_failure 5  4      3
> ceiling        1     1      1
> ```
>
> **Retrieval improved and refusals did not move.** More containing chunks reached the prompt at
> every step — `symbol_missing` 6→4, `retrieval_failure` 5→3 — and the model refused exactly as
> often. That is not a null result; it is a result pointing at a different component.
>
> **The disambiguating run settles it.** `--retrieval-only --k 10` on the `backref` question
> confirmed a chunk containing the symbol was in the prompt, and the full run still refused.
> **The sources reached the model and it declined anyway.**
>
> **What this costs Phase 3.** Those five failures were the evidence for hybrid search and
> reranking. At least some of them are **not retrieval failures at all** — the answer was
> present and generation refused. Hybrid search would have surfaced the chunk that was already
> being surfaced. **`D04` said build the naive version and watch it fail before buying the fix;
> this is what watching it fail actually bought** — the fix was aimed at the wrong half.
> **What it does not license:** cancelling Phase 3. `symbol_missing` and `retrieval_failure` both
> fell as `k` rose, so retrieval genuinely is imperfect and hybrid search would help *something*.
> What is no longer true is that these eight refusals are the argument for it.
>
> **Where the argument moves instead: `D43`'s clause.** That entry measured over-firing at **1 in
> 13** — but on prompt **A**, the strict wording, on one question. This is prompt **B**, the
> shipped one, refusing **8 of 19** with the answer demonstrably in the prompt. `D43` concluded
> "the clause is necessary and the over-fire is not reproducible". The first half stands; the
> second was measured on the wrong prompt and the wrong question set.
> **The next experiment is therefore a prompt experiment, not a retrieval one** — and it is
> cheap, because `rag/compare_prompts.py` already exists.
> **Asked as** — *"How did you decide what to build next?"* — where the answer is that the thing
> queued for three months was aimed at a failure mode that measurement reassigned to a different
> component, and the measurement cost one sitting.
>
> ⚠️ **Largely WRONG, corrected by `D54` on 2026-08-17.** This entry concluded the refusals were
> not retrieval failures. **At k=5 — what ships — they are.** Four of the five have answers
> outside the top-5, so the model refused questions whose answers were never in front of it.
> This entry generalised from the single case where the chunk *was* present (`backref` at k=10)
> to the whole set. **Phase 3 is justified after all.** What survives: Q18 and Q19 do over-fire
> once the answer is present, and no wording fixes them — two questions, not eight.


### D52 — A and B are indistinguishable, so D43 chose between two identical things

> **Measured 2026-08-17, Round 8** — all three wordings against all 19 probe questions, 57
> generations on the lab PC.
>
> ```
> prompt    refused  answered   of 19
> A               8        11    strict canned refusal
> B               8        11    refusal as last resort (SHIPPED)
> C               0        19    no refusal clause
> ```
>
> **A and B refused the same 8 questions — identical, question by question.** `D43` chose B over
> A because A refused one answerable question and B did not. Over 19 questions there is **no
> behavioural difference between them at all.** The wording change B introduced does not change
> what the model does; it changed one outcome once, and that did not reproduce (`D43`'s 1-in-13).
> **So the shipped prompt was chosen between two options that are the same option.** B is not
> wrong — it is simply not better, and the entry that picked it claimed a distinction the
> evidence does not support.
>
> **Scored against this repo's own 19 verdicts, B's 8 refusals split 4 and 4:**
>
> | | questions | |
> |---|---|---|
> | **correct refusals** | Q4 `has_table`, Q6 `relation`, Q15, Q17 | corpus genuinely has nothing |
> | **over-fires** | Q3 `table_names`, Q5 `keys()`, Q18, Q19 | the answer is in the corpus |
> | **under-fire** | Q16 | an `absent` question it answered instead |
>
> **So the real floor is 5, not 3.** Round 8's ASK said three — the `absent` category — but Q4
> and Q6 are ceilings too, established independently in `D51` and the verdicts. **A correct
> prompt refuses 5 of these 19. B refuses 8 and misses one, so it is wrong in 5 places.**
>
> **C is not the answer**, and Round 8 makes that concrete rather than theoretical: C refused
> **0**, which means it answered all three `absent` questions — the ones where the corpus provably
> has nothing. That is `D43`'s fabrication, now confirmed across 19 questions instead of one.
>
> **What this leaves.** The refusal clause is necessary (C), the two wordings tried are
> equivalent (A = B), and the shipped one is wrong on 5 of 19. **No wording tested so far is
> good**, and the search space was two points that turned out to be one. That is the finding —
> not "B needs tuning", but "B was never compared against anything different".
> **What it does not license:** changing the model. C proves this model answers all 19 when
> permitted to. The failure is entirely in the instruction.
> **Asked as** — *"How do you know your prompt is right?"* — where the honest answer is that it
> is not, that the experiment which chose it compared two identical things, and that it took
> running the full question set to see it.


### D53 — D beats B by exactly one question, and the rest was never the prompt's fault

> **Measured 2026-08-17, Round 9** — four wordings, 19 questions, 76 generations.
>
> ```
> prompt    refused  answered   of 19
> A               8        11
> B               8        11    <- shipped
> C               0        19
> D               9        10    <- answer partially, refuse only on subject
> ```
>
> **D refused the right five and nothing new.** Its nine are the target five — Q4, Q6, Q15, Q16,
> Q17 — plus the same four A and B refuse. Scored against this repo's verdicts:
>
> | | wrong in |
> |---|---|
> | B | **5** — 4 over-fires and 1 under-fire (Q16, an `absent` question it answered) |
> | D | **4** — the same 4, and it **fixed the under-fire** |
>
> **So the mechanism change bought exactly one question**, and the one it bought is real: Q16 is
> the only `absent` question that had been getting a confident answer. Requiring a refusal to
> *name what was looked for* is what caught it.
>
> **The four it did not fix are invariant across every wording tried** — A, B and D all refuse
> Q3, Q5, Q18, Q19. Three different instructions, identical behaviour on those four.
>
> **And there is a confound in Rounds 8 and 9 that has to be stated before anyone concludes from
> that.** Both ran at `DEFAULT_K = 5`. The answers to those four sit at ranks **23, 12, 8 and 6**
> — **all outside the top-5.** So in these runs the model was refusing questions whose answers
> were **not in its prompt**, which is the correct behaviour, not an over-fire. On this evidence
> alone the prompt is doing the right thing and retrieval is the problem.
>
> **That contradicts `D51`, and the contradiction is only apparent.** Round 7 ran at k=10, where
> Q18 and Q19's chunks *are* present, and confirmed by `--retrieval-only` that the `backref`
> chunk was in the prompt while the model refused anyway. **So those two are genuine over-fires
> at k=10 and correct refusals at k=5**, and Rounds 8–9 could not have distinguished them.
> **What this means practically:** no wording has yet been tested under the condition that makes
> the over-fire visible. The decisive run is **D at k=10**, not another wording.
> **Ship D regardless.** It is strictly better than B — same behaviour everywhere except Q16,
> where it is right and B is wrong — and nothing measured argues for keeping B.
> **Asked as** — *"How do you know the prompt is the problem and not retrieval?"* — where the
> honest answer today is that at k=5 it is retrieval, at k=10 it is partly the prompt, and the
> experiment that separates them has not been run yet.


### D54 — At k=5 every refusal is honest; raising k buys two over-fires and a fabrication

> **Measured 2026-08-17, Round 10** — four wordings × 19 questions × two values of k, 152
> generations, plus a check of what Qdrant actually returns.
>
> **First, the controls held, and one of them changed the reading.** Brute-force ranks are not
> what the system sees — Qdrant is approximate (`D31`). Asked directly:
>
> ```
> Q 5 keys()             in Qdrant top-10 at: NONE
> Q18 cascade_backrefs   in Qdrant top-10 at: [8]
> Q19 backref            in Qdrant top-10 at: [6, 7, 8]
> Q 3 table_names        in Qdrant top-10 at: NONE
> ```
>
> **The finding: at k=5, every one of D's nine refusals is correct.** Q4, Q6, Q15, Q16, Q17 are
> ceilings or `absent`. Q3, Q5, Q18, Q19 have their answers **outside the top-5**, so the model
> refused questions whose answers were not in front of it. **That is honest behaviour, not
> over-firing. D at k=5 makes zero prompt errors.**
>
> **Raising k to 10 makes things worse in two distinct ways:**
>
> - **Q18 and Q19 become genuine over-fires.** Their chunks are now in the prompt — Q19 has
>   **three** of them, at positions 6, 7 and 8 — and A, B and D all refuse anyway. **Three
>   genuinely different wordings, answer demonstrably present, identical refusal.** For these two
>   the instruction is not the lever.
> - **Q5 becomes a fabrication.** `keys()` is in **no** chunk of the top-10, and A, B and D all
>   answered it at k=10 having correctly refused at k=5. **Raising k did not surface an answer; it
>   supplied five more near-miss chunks and the model talked itself into one.**
>
> **So `D51` was wrong and this entry corrects it.** `D51` concluded from Round 7 that "these
> failures are largely not retrieval failures at all — the sources arrive and generation
> declines". At k=5, which is what ships, **the sources do not arrive**: four of the five have
> answers outside the top-5. `D51` generalised from the one case where the chunk *was* present
> (`backref` at k=10) to the whole set. **Phase 3 is justified after all**, and by a cleaner
> argument than it started with.
>
> **What survives from `D51` and `D52`:** Q18 and Q19 really do over-fire once the answer is
> present, and no wording fixes them. That is a real generation defect — it is just two questions
> rather than eight.
>
> **The operational conclusion is narrow and firm: ship D, keep k=5.** D at k=5 is the only
> configuration measured with no prompt errors. Raising k trades four honest refusals for two
> over-fires and one fabrication, which is a strictly worse system.
> **Asked as** — *"Why is your top-k 5 and not 10?"* — where the answer is that 10 was measured
> and made it worse, with the failure mode named.
>
> ✅ **CONFIRMED 2026-08-17, Round 11 — `n=5`, and the result is unusually clean.** 380
> generations, four wordings × 19 questions × 5 runs at k=5.
>
> ```
> A 8.0    B 8.0    C 0.0    D 9.0     zero non-unanimous cells
> ```
>
> **Every cell was 0 or 5.** Not one question flipped between identical runs, for any wording.
> D's advantage is Q16 and it is **5/5 against B's 0/5** — the margin reproduces exactly.
> `D54` is no longer provisional: **ship D, keep k=5.**
>
> **And the zero-stars result is worth more than the margin it confirmed.** Refusal behaviour
> here is **deterministic** — same question, same sources, same wording, same decision, every
> time. Which means the `n=1` runs in Rounds 8–10 produced *correct* answers.
> **They were still the wrong method.** Nothing known before this round said the process was
> deterministic; `D43` had measured generation as nondeterministic in its own text, and the two
> Mac re-runs there differed from the original. Being right by luck and being right by evidence
> read identically until someone checked. **That is the finding to carry: the repeat run did not
> change a conclusion, it changed how much weight the conclusions can bear.**
> **Practical consequence:** prompt comparisons on this question set can be run once, provided
> the determinism is re-checked whenever the model, temperature or sources change — any of which
> could reintroduce variance without warning.
>
> ⚠️ **SCOPE NARROWED 2026-08-21 — "deterministic" was measured within one sitting and does not
> hold across days.** `--refusals` was re-run on the golden set. Of the seven items that refused
> with their answer chunk in the prompt on 08-20, **two flipped**: `g029` refused then and answers
> now; `g015` answered then and refuses now. Re-asked directly on 08-21, both reproduce the 08-21
> result, so it is stable *within* a sitting — exactly what Round 11 measured.
> **What was ruled out:** `TEMPERATURE = 0.0` unchanged, `rag/ask.py` unchanged since `b6320c4`
> (the commit that produced the 08-20 run), and the index unchanged — the paired recall comparison
> is `0 fixed, 0 broken`. Same prompt, same sources, same greedy decoding.
> **What was not:** the model server across processes. The honest claim is **"five runs in one
> sitting were unanimous"**, not "deterministic".
> **Why it matters rather than being trivia:** Phase 4 will be judged on whether those items stop
> refusing, and a two-item drift is most of the effect anyone would be looking for. A Phase 4
> before/after therefore needs the baseline re-run in the same sitting as the change, not read off
> a number from a previous day. `14-MEASURE.md` §R6.2 carries the measurement.
>
> ⚠️ **SCOPE NARROWED AGAIN 2026-09-10 — "drifts across days" is a fact about THIS MACHINE'S
> GENERATOR, not about the system.** See `D84`. The lab 3060 ran the identical sweep **twice, five
> days apart**, and every refusal cell came back identical *including which eight items flipped*.
> **The lab did not drift at all.** The two-item overnight flip above was measured on the **Mac**,
> and that is now the distinguishing fact rather than a detail of when it was taken.
> **What still stands unchanged:** the operational rule. A Phase 4 before/after re-runs its
> baseline in the same sitting, because the rule has to hold on the machine that *does* drift and
> you do not always know in advance which one that is.
> **What the scope is now, precisely, because this entry has been over-read once already:**
> this is `qwen2.5-coder:7b` deciding to answer or refuse. The **judge** (`gemma4:e4b`) was
> re-measured on the Mac and drifts too, at **3 verdicts in 110**, while the **lab's** judge
> re-ran the same 110 five days apart and came back **identical to the character, reason text
> included**. So the drift tracks the *box*, not the model or the task: two models, two jobs,
> stable on the lab and not on the Mac. **Prefer the measurement that can be reproduced** (`D84`).


---

### D55 — the five verification answers got their own file, against this repo's own no-new-files rule

> **Decided** — the answers to `PHASE-1.md`'s five cold questions went into a new
> `study/13-VERIFICATION.md` as **§R5**, continuing the `R` run per `D47`.
> **Instead of** — the default, which `CLAUDE.md` states plainly: *"Everything goes in the
> existing docs. Do not create a new file to hold an explanation that belongs beside the thing
> it explains."* Two placements were available and both were rejected.
> **Rejected — expanding `PHASE-1.md`'s Verification section.** It is where the questions live,
> so it looks like the obvious home. But `PHASE-1.md` is a **plan**, and plans go cold: when
> Phase 2 opens, that file stops being read. These five answers are the opposite — they are the
> material rehearsed before every interview, for as long as the project is on a CV. Filing
> permanent material inside a document with a scheduled end date is how it gets lost.
> **Rejected — splitting the answers across `10`, `11` and `12`.** Q2 is corpus (§R1), Q3 is
> chunking (§R1), Q4 is embeddings (§R2), Q5 is generation and evaluation (§R3–§R4), Q1 is a
> design decision belonging to none of them. Each answer would land in the right file and the
> **set** would cease to exist — and the set is the artefact, because the gate is five questions
> in one sitting, not five paragraphs in four files.
> **Because the splitting rule's actual condition is met.** `study/README.md` allows a split when
> a file "has grown to cover two genuinely different subjects". §R5 is a different subject from
> all three existing ones: `10`–`12` are about **building and measuring** the system, §R5 is
> about **defending it out loud without notes**. Those fail differently — the recorded failure
> mode for §R5 is answering the setup instead of the question, which no amount of building skill
> prevents.
> **The cost, stated rather than hidden.** A file of model answers can be read before the gate
> instead of after, which converts a recall test into a recognition test and makes the gate
> measure nothing. That is not solved by good intentions, so it is written into both files and
> pinned by a test (`test_the_answers_file_does_not_claim_to_replace_the_gate`). The mitigation
> is a sentence, and a sentence is a weak mitigation — the honest position is that this file
> **spends** a one-shot cold gate in exchange for material that is reusable indefinitely.
> **Asked as** — *"When do you break your own documentation rules?"* — and the answer is when
> the rule's stated reason does not apply. The no-new-files rule exists so explanations sit
> beside what they explain; these explanations have no single thing to sit beside.


### D56 — the chunk gate passed with 2 of 10 failing, and the exception is the record

> **Decided 2026-08-18** — Step 2's *"eyeball ten at random and find each one self-contained"*
> gate is **passed**, with two of the ten failing and the reason written down instead of the
> failures being talked away.
> **What failed.** `c03012` ends mid-promise — its last words are *"…is as follows:"* and the
> list never arrives. `c00138` opens *"While the above example is against…"* and there is no
> example above it. Neither is a judgement call; read either aloud and the missing half is
> audible.
> **They are not equally bad, and that is the transferable part.** `c03012` (28814→29201) is
> overlapped by the chunk after it, which starts at 28953 and carries the missing list — the
> content survives, only this copy of it is bad. `c00138` (7880→8297) follows a chunk ending at
> exactly 7880, so there is **no overlap at all** and nothing holds both halves. Overlap is by
> whole block (`D33`, `D34`), and whole blocks are uneven, so some boundaries are covered
> generously and some not at all.
> **Ten was not enough to rule on, so all 3284 were counted** — `uv run python -m rag.chunk
> --audit`, added for this and re-runnable after any chunker change. **352 chunks (10.7%)** show
> one of the two shapes; **207 (6.3%)** lose content because no neighbour overlaps them. The
> ten-chunk sample read 2 in 10, which is an unlucky draw against a true rate near 1 in 10, not
> a misreading.
> **The detectors were validated against known answers before being believed**: `c03012` must
> appear in shape A, `c00138` in shape B, and `c01480` — which also opens with a backward
> reference and then repairs itself in the same sentence — must **not**. All three hold. Without
> the third, the audit measures how eagerly a regex fires and nothing else. Shape B still
> over-fires by roughly an eighth, measured by reading eight hits at random, and that is printed
> beside the number rather than left for someone to discover.
> **Instead of** — three alternatives, all rejected:
> **(a) Fail the gate and fix the chunker now.** Rejected on `D04`: a chunker with no boundary
> defects is a Phase 3 chunker, and fixing a measured failure before anything downstream has been
> hurt by it is the exact mistake this phase exists to avoid. The fix is also not small — it needs
> a boundary rule that parses reStructuredText, not a wider overlap, which would hide the symptom
> and inflate the index.
> **(b) Redefine "self-contained" to a looser reading and pass cleanly.** Rejected as moving the
> bar after seeing the result. The two readings were fair to choose between before the reading;
> picking the convenient one afterwards is the thing an interviewer asks the date of.
> **(c) Pass it quietly.** Rejected because that is how a gate stops meaning anything — and this
> repo has already watched `PHASE-1.md` claim three open gates when one had closed, purely
> because nothing wrote the change down.
> **What reverses it:** a probe answer that is wrong *because* a chunk was cut — currently zero
> of the six `WRONG` verdicts are — or the rate rising after a chunker change, which `--audit`
> now makes a one-command check rather than an argument.
> **Asked as** — *"You found a defect and shipped anyway. Defend that."* — and the answer is that
> the defect was bounded first: 1 in 10, 1 in 16 unrecoverable, two named shapes, one command to
> re-check. Shipping with a measured defect is engineering; shipping with an unmeasured one is
> the thing that gets called technical debt afterwards.


### D57 — Phase 1 closed, and the useful finding is where the answers stopped

> **Decided 2026-08-18** — Phase 1 is COMPLETE. Both human gates are closed; `D56` covers the
> chunk gate and this entry covers the five verification questions.
> **What the sitting produced, because it is the finding rather than the score.** Two of the five
> were answered unaided — Q4, *an embedding matches meaning, not strings*, in five words on the
> first attempt. In the other three the content was right and the **last clause of the question
> went unanswered**: *on purpose*, *and what did you leave out*, *and was not invented*.
> **That is a delivery pattern, not a knowledge gap**, and Q4 is the proof — the material is
> held. Every one of these five questions carries its real content in its final words, so it is
> possible to say something true about the first half and never reach what was asked. Naming the
> pattern is worth more than the count, because the correction is a habit rather than more study.
> **What that changed.** `study/13-VERIFICATION.md` §R5.7 was written from it: the five answers
> said end to end, so the run can be rehearsed as one piece. The gate's standard is unchanged and
> re-sittable — cold, from memory, without opening §R5 first (`D55`).
> **Instead of** — holding the phase open until a second sitting. Rejected: the artefacts are
> finished, Phase 2 depends on them, and a rehearsal gate blocking a build phase costs more than
> it measures.
> **Asked as** — *"How do you know when a phase is done?"* — and the answer is that the criteria
> were written before the work, checked one at a time, and each outcome recorded next to the
> criterion rather than summarised as a tick.

### D58 — `P2-a`: either half of a duplicate pair counts as a hit, and the cost is reported separately

> **Decided 2026-08-18, before any score exists** — which is the only time this can be decided
> honestly. `recall@k` counts a hit when **any chunk whose `(heading_path, text)` matches a
> golden answer chunk** appears in the top k, regardless of its version tag. Two further numbers
> ship beside it: **`recall@k (version-strict)`**, and **`slots_lost_to_duplicates`** as a figure
> in its own right rather than a gap to be inferred.
> **Instead of** — version-strict as the headline, which is the intuitive choice and is wrong
> here for a mechanical reason rather than a philosophical one.
> **The mechanism, verified rather than argued.** `rag/embed.py` prepends the heading path before
> embedding, so `(heading_path, text)` is exactly the unit that determines a vector. Group the
> 3284 chunks that way and **437 pairs share a text and a heading**, and their vectors are
> **byte-identical — 437 of 437 checked**. Identical vectors give an identical cosine to every
> possible query, so **the two copies always occupy adjacent slots or neither.** Under
> version-strict counting one of the five slots is therefore *provably* wasted whenever such a
> pair is relevant, and the retriever has no lever to prefer the right copy. Penalising it
> measures the corpus, not the ranking.
> **A second group behaves differently and must not be lumped in.** 31 pairs share a text but sit
> under **different** heading paths — and **0 of 31** have identical vectors, with cosines as low
> as `0.964`. Those are ordinary near-neighbours and get no special treatment. This is also why
> `D38`'s `(heading_path, text)` grouping was the right one: it matches what is embedded. Grouped
> by text alone the count is 468 pairs / 936 chunks; `D38`'s 437 / 874 is the meaningful figure.
> **Incidence, measured on real queries:** `probe.py` recorded **2 of 19** questions with a
> duplicate slot, 2 slots in total. So this is a real but small tax — not a reason to stop and
> deduplicate before Phase 2 can start.
> **The escape hatch that keeps `D10` intact.** Version skew is in the corpus on purpose, and for
> some questions *the version is the answer*. Golden items may set `version_sensitive: true`, and
> those are scored version-strict whatever the headline rule says. Without this, the permissive
> rule would quietly excuse the exact failure `D10` exists to study.
> **A method error caught while settling this, kept because it is the transferable part.** The
> first incidence figure was **6 of 19**, computed by parsing `deliverables/FAILURES.md`. That
> file truncates every shown chunk at **700 characters** (`probe.py:417`) and carries no chunk
> ids, so two different chunks sharing their first 700 characters render identically and count as
> a duplicate. **The report is a rendering, not the data.** Phase 2's scorer reads
> `corpus/chunks.jsonl`, never a deliverable — the same class of error as the truncated review
> sheet found on 2026-08-17.
> **Asked as** — *"How did you define a hit?"* — and the answer names a mechanism: two copies with
> identical vectors cannot be told apart by any ranker, so a metric that punishes the ranker for
> them is measuring the wrong component.

### D59 — `P2-b`: retrieve deep once and report the whole recall curve

> **Decided 2026-08-18** — the scorer retrieves **top-20** for every question and computes
> `recall@1 / @3 / @5 / @10 / @20` and MRR from that one list. There is no single `k`.
> **Instead of** — picking `k = 5` to match `DEFAULT_K`, or `k = 10` to see near-misses, and
> arguing about which.
> **Because depth is free, measured rather than assumed.** Retrieval latency on this Mac is
> dominated entirely by embedding the question, and that cost is identical at every depth:
> `top-5` 95.7 ms, `top-10` 71.2 ms, `top-20` 109.4 ms, `top-50` 88.6 ms — differences that are
> measurement noise around the ~88 ms query embedding (`D31` puts the Qdrant search itself at
> 2.65 ms). **When the expensive part happens before `k` is even read, choosing a small `k` buys
> nothing and discards information.**
> **And Phase 1 already proved the discarded information was the useful part.** `recall@5` said
> five questions failed; the *rank* said they failed four different ways — 6, 8, 12, 23, absent
> (§R4.3). A single `recall@5` would have sent all five to hybrid search, and one of them needed
> an integer. A curve makes "missed by one place" and "found nothing" different numbers instead
> of the same zero.
> **`recall@5` stays the headline** because it is what ships (`DEFAULT_K = 5`, `D54`). The rest
> are reported beside it, not instead of it.
> **Asked as** — *"What k did you evaluate at?"* — and the answer is that the question assumes a
> choice that the cost structure does not force.

### D60 — `P2-c`: the 19 probe questions join the set as a labelled subset, never as the benchmark

> **Decided 2026-08-18** — the 19 questions in `FAILURES.md` enter `golden.json` with
> `provenance: "breakages"`, and **every score is reported with and without them**.
> **Instead of** — using them as the benchmark (they are free and already verified) or excluding
> them (they are real failures with known answers).
> **Because their leakage is measurable, and it was measured.** They were written from
> `BREAKAGES.md`'s keys, so they carry the corpus's own vocabulary. Content-word overlap between
> a question and the single top-ranked chunk it retrieves:
>
> | question set | median overlap with top-1 | with top-5 |
> |---|---|---|
> | the 19 probe questions | **0.57** | 0.75 |
> | the same questions in developer phrasing | **0.33** | 0.67 |
>
> **A probe question shares 57% of its content words with the best chunk; a developer asking the
> same thing shares 33%.** Search is being handed much of its own answer.
> **The harder evidence is not the overlap — it is that the phrasing changes the result.** Of five
> questions rewritten the way somebody stuck would type them, **three returned a different top-1
> chunk**. A benchmark built on the tidy phrasing measures a system nobody is using.
> **Strengthened the same day, by running the scorer end to end.** Take one question and one
> answer chunk, `c01542`. Asked as *"what replaces `Query.from_self()` in SQLAlchemy 2.0?"* that
> chunk comes back at **rank 1**. Asked as *"my old query.from_self() call blew up after
> upgrading, whats the new way"* — same question, same answer — it is **not in the top 20 at
> all**. Not ranked lower: absent. **Rewording the question moved the answer from first place to
> outside the retrieved set**, and a benchmark written in the tidy voice would have scored that
> question 1.0 and reported the system as working. Pinned by
> `tests/test_score.py::test_phrasing_alone_can_push_the_answer_out_of_the_index`.
> **Stated limits.** The developer phrasings are `n = 5` and were **drafted here**, so they could
> unconsciously favour low overlap; the overlap figure is indicative, and the changed-top-1 count
> is the harder fact. Neither is a reason to drop the probe items — a benchmark whose items have
> different provenance is fine, one that hides it is not.
> **Asked as** — *"Where did your eval questions come from?"* — and the answer names the weakest
> subset first, with the number that says how weak.
> **⚠️ Corrected by `D63` on 2026-08-20.** The mechanism here is right and is what caught this.
> The *label* is wrong: measured on the finished 50-item set, the leaky subset is
> `migration_guide` (overlap **0.64**, recall@5 **0.73**), not `breakages` (**0.43** / **0.41**).
> Phrasing leaks, not provenance. Read `D63` before quoting this entry's framing.

### D61 — `P2-d`: 50 items, and Phase 3 reports which items flipped, not a recall delta

> **Decided 2026-08-18** — target **50** golden items, and every Phase 3 comparison reports
> **`fixed` and `broken` item lists** alongside the recall numbers.
> **Instead of** — 30 items, and comparing two recall percentages before and after.
> **Because 50 items cannot support the comparison everyone reaches for first.** The 95% Wilson
> interval on a single recall figure at `n = 50, p = 0.6` is **±0.131**. Going from `0.60` to
> `0.70` produces two intervals that overlap heavily — **a real ten-point improvement would be
> indistinguishable from noise** if reported that way.
> **What rescues it is that the comparison is paired.** Phase 3 runs the *same* questions before
> and after, so only the items that **flip** carry information. Exact two-sided McNemar on the
> discordant pairs:
>
> | fixed | broken | p | |
> |---|---|---|---|
> | 6 | 0 | **0.031** | significant |
> | 5 | 0 | 0.062 | just short |
> | 8 | 2 | 0.109 | **not** distinguishable |
> | 10 | 4 | 0.180 | not distinguishable |
>
> **So the bar at `n = 50` is roughly six clean fixes with no regressions.** That is a real
> constraint and it is stated rather than discovered later: this set detects **large** changes.
> Phase 3's changes are supposed to be large — and if hybrid search moves three questions with
> two regressions, *that is the finding*, not a measurement failure.
> **Why not more than 50.** The binding cost is human verification at ~15 minutes an item (`D06`),
> so 50 is 12.5 hours and 80 would be 20. The honest trade is a smaller set with stated limits
> over a larger one that never gets finished.
> **Asked as** — *"Is that improvement significant?"* — and the answer is a paired test with the
> flipped items named, not two percentages and a hopeful adjective.

### D63 — `D60`'s split is right and its label was backwards: the leaky subset is `migration_guide`

> **Measured 2026-08-20, on the finished 50-item set.** `D60` quarantined the `breakages` items
> as the ones whose vocabulary leaks — *"the answer names the weakest subset first"* — and the
> weakest subset turned out to be the other one.
> **Decided** — keep `D60`'s mechanism exactly as it is (every number reported with and without
> a provenance group) and **correct which group is the suspect**. `D60` is not reversed; the
> action it chose is what made this visible.
> **Because the numbers invert its prediction, on `D60`'s own metric.** Median content-word
> overlap between a question and the top-1 chunk it retrieves, and recall@5 beside it:
>
> | provenance | n | median overlap with top-1 | recall@5 |
> |---|---|---|---|
> | `migration_guide` | 16 | **0.64** | **0.73** |
> | `breakages` | 34 | 0.43 | 0.41 |
>
> **0.64 is higher than the 0.57 `D60` measured on the probe questions** — the subset added to
> be *realistic* is leakier than the one that was quarantined for leaking.
> **Why it happened, and it is not an error in the harvesting.** `D60` reasoned about the 19
> probe questions, which were written from `BREAKAGES.md`'s keys and carry the corpus's
> vocabulary. The 34 `breakages` items in the finished set are seeded from the same 23 entries
> but **written in developer phrasing** — *"my old query.from_self() call blew up after
> upgrading, whats the new way"*. **Phrasing leaks, not provenance.** `D60`'s own strongest
> evidence already said so: `c01542` at **rank 1** in tidy phrasing and **absent from the top 20**
> in developer phrasing. The label was attached to the wrong axis.
> **What this changes in practice.** The headline **recall@5 = 0.51** averages a leaky subset
> with a realistic one. **0.41 is the number to quote** for a developer typing an error message,
> and the 32-point gap between the two halves is larger than anything Phase 3 is expected to buy.
> Quoting 0.51 unqualified would overstate the shipped system.
> **Asked as** — *"Which of your eval questions are too easy, and how do you know?"* — answered
> with the overlap table, and with the admission that the first answer to it was wrong.

### D62 — `P2-e`: refusal accuracy stays in Phase 2, reported separately from retrieval

> **Decided 2026-08-18** — the scorer measures whether the system declines the `answerable: false`
> items, and prints it as **its own section**, never folded into recall.
> **Instead of** — deferring it to Phase 4, which is what `ROADMAP.md`'s wording implies:
> *"Retrieval metrics (deterministic, free, no AI needed)."*
> **Because the unanswerable items are otherwise dead weight for an entire phase.** At the
> retrieval level an unanswerable question scores `recall = 0` by construction — the chunk does
> not exist, so the number is arithmetic, not evidence. The only thing those items can test is
> whether the system **says so**, and that needs generation.
> **The cost is small enough that the scope argument does not survive it.** 50 generations at the
> measured 18.4 tok/s on this Mac is roughly seven minutes; Round 10 ran 152 generations in a
> single sitting. Deferring seven minutes of compute for a definitional reason would leave
> `has_table` in the set for two phases doing nothing.
> **The separation is the part that matters.** A refusal is not a retrieval result, and averaging
> the two produces a number that improves when the system gets more cautious. They are printed
> apart so neither can flatter the other.
> **Asked as** — *"Your benchmark has questions with no answer. What do they measure?"*


### D64 — Phase 2's golden scorecard got its own file, so Sitting 4 stays Phase 1

> **Decided 2026-08-21** — the measured Phase 2 baseline, refusal run, and three ceiling items
> went into a new `study/14-MEASURE.md` as **§R6**, continuing the `R` run per `D47`.
> **Instead of** — leaving them as R4.7–R4.9 at the end of `study/12-EVALUATION.md`, or folding
> them into `13-VERIFICATION.md`.
> **Rejected — keeping them in `12`.** Sitting 4 opens as measured off the **19**
> `FAILURES.md` answers. The golden-set score is a different artefact (50 items, a different
> harvest, Phase 2's deliverable). Leaving it in `12` made Phase 1 look unfinished after §R5
> had already closed the phase.
> **Rejected — putting them in `13`.** §R5 is defending the system **out loud**; a scorecard is
> not that skill. Mixing interview rehearsal with recall tables would fail the same split test
> `D55` already used the other way.
> **Because the splitting rule's condition is met.** `12` had grown to cover two subjects:
> *how* to measure (R4.1–R4.6) and *what* the finished ruler scored (the old R4.7–R4.9). Those
> fail differently — one is conceptual, the other goes stale when you re-run `rag.score`.
> **The cost, stated rather than hidden.** One more file in the `R` run. The mitigation is the
> same as `D55`: say out loud that Phase 1 ends at §R5, and point from `12` to `14` so Sitting 4
> does not claim the golden set.
> **Asked as** — *"When do you split a study file after the phase that produced the earlier
> half has already closed?"*


### D65 — the golden set doubled to 100 with real questions, and the baseline artifact did not move

> **Decided 2026-08-21** — the set is **100 items**: 50 repo-authored (`breakages` 34,
> `migration_guide` 16) and 50 harvested from real developers (`stackoverflow` 25, `github` 25).
> `deliverables/baseline-phase1.json` **stays the 50-item run** and remains what `--baseline`
> compares against.
> **Instead of** — rescoring, saving over the baseline, and calling the 100-item numbers the
> Phase 1 baseline.
> **Rejected — replacing the baseline artifact.** `D61` puts Phase 3 on a *paired* comparison:
> same items, before and after. Swapping in a different set of items mid-project makes every
> later comparison two unpaired averages, which at these interval widths says nothing. Proven
> here: scoring 100 items and comparing against the saved 50 gives **0 fixed, 0 broken,
> McNemar p = 1.000** — the shared items reproduce exactly, which is only checkable because the
> old artifact still exists.
> **Because the new items measure something the old ones could not.** `D63` established that
> phrasing decides retrieval, and both halves of the first 50 were phrased *here*. The harvested
> half is phrased by people who were stuck. Measured: `migration_guide` **0.73**, `github`
> **0.57**, `breakages` **0.41**, `stackoverflow` **0.38**. **The repo's imitation of a stuck
> developer scored higher than actual stuck developers** — a 35-point spread from the easiest
> group to the hardest, wider than anything Phase 3 is forecast to buy.
> **What doubling bought, and what it did not.** The 95% Wilson band on one recall figure went
> **±0.137 → ±0.101** (47 answerable → 91), so a real Phase 3 move must clear ~20 points instead
> of ~27. It did **not** buy a better headline: `0.49` against `0.51`, well inside the band, and
> lower only because harder questions were added.
> **The cost, stated.** The set still leans on one file — **88 of 153** answer-chunk instances are
> in `changelog/migration_20.rst` (was 62 of 68), and `c01567` alone answers **11** items, so
> those eleven scores still move together and the Wilson band is still slightly optimistic. It
> reaches **24** of 270 corpus files, up from 4.
> **Signature.** Closed 2026-08-21 by spot-check of ten, then verified (see §H CLOSED). The 100-item
> numbers are **measured and verified**; the Phase 1 **baseline artifact** remains the saved
> 50-row file so Phase 3 stays a paired comparison (`D61`).
> **Asked as** — *"You added 50 questions to your benchmark. Why is your old score still the one
> you compare against?"*

### D66 — collapse cross-version twins at retrieve time, prefer 2.0.51

> **Decided 2026-08-21** — `rag/index.retrieve` over-fetches and keeps one hit per
> `(heading_path, text)`, preferring the **2.0.51** half. Default on; `dedupe=False` only to
> re-measure the Phase 2 tax.
> **Instead of** — leaving both twins in the prompt (Phase 1–2 default), or deleting 1.4 from the
> index (would erase the version-skew failures `D10` exists to study), or waiting for a reranker
> (identical vectors → no ranker can prefer either copy — `D58`).
> **Sized by Phase 2, not by taste.** On the 100-item set, **31** top-5 seats were lost to
> duplicates. After collapse: **0**. recall@5 moved **0.495 → 0.516**; vs the 50-item baseline
> **2 fixed / 0 broken** (`g046`, `g047`), McNemar p = 0.500 — not a significant recall claim,
> a significant *waste* claim. Absents from top-20 stayed **22** (dedupe cannot invent a page).
> **Why prefer 2.0.51.** The product answers 1.4 → 2.0 upgrades. Scores are identical; the
> product is not. Preferring 1.4 would put the migration-target page *out* of the prompt for no
> retrieval gain.
> **Asked as** — *"Your top-5 had the same paragraph twice. What did you do, and how do you know
> it helped?"*

### D67 — BM25 + dense-heavy RRF; ship the zero-regression fusion point

> **Decided 2026-08-21** — `rag/index.retrieve` defaults to hybrid: Okapi BM25 over
> `chunks.jsonl` fused with dense Qdrant hits by Reciprocal Rank Fusion, with **dense weighted
> heavier** (`kd=25`, `kb=90`). `hybrid=False` / `--dense-only` re-measures the pre-hybrid path.
> **Instead of** — equal-k RRF (`k=60`/`k=60`), which lifted the average but **broke five** items
> dense already had; or sparse vectors from BGE-M3 (would need a re-embed and a different
> failure story); or raising `DEFAULT_K` (already rejected by `D54`).
> **Sized by a sweep on the 100, after `D66`.** Equal fusion and aggressive BM25 weight both
> bought broken flips. The densest *zero-regression* point was `kd=25`/`kb=90` (probe: +9 at
> recall@5, 0 broken). End-to-end score: **0.52 → 0.63** recall@5, absents **22 → 17**,
> stackoverflow **0.38 → 0.48**. Vs the 50-item baseline: **6 fixed / 0 broken**, McNemar
> **p = 0.031** — the first Phase 3 change that clears the paired bar (`D61`).
> **Tokenisation is part of the decision.** `engine.table_names()` splits to `engine` +
> `table_names`, not one dotted token (dotted compounds never appear in the docs). Further
> splitting snake_case into `table`+`names` was measured and rejected — common parts drown the
> rare symbol and dropped recall@5.
> **Asked as** — *"You added keyword search. How did you combine it with vectors, and why those
> constants?"*

### D68 — seat-5 CE promotion; reject full cross-encoder reorder

> **Decided 2026-08-21** — after hybrid, run `BAAI/bge-reranker-base` over the top-20 and
> **replace only seat 5** with the best-scoring chunk from ranks **6..10** when the CE logit
> gap is ≥ **0.8**. Default on; `--no-rerank` / `rerank=False` re-measures without it.
> **Instead of** — a full CE reorder of the hybrid list (recall@5 0.63 → 0.66 but **10 broken**);
> hybrid-heavy RRF of hybrid+CE ranks (safe weights → **0 fixed**); freeze-head CE fill (always
> broken > 0 until head=5 = identity); or skipping the lever without a measurement.
> **Sized on the 100 after `D67`.** 17 items sit in ranks 6–20 (reranker reach); 17 are absent
> (unreachable). The shipped rule: **1 fixed** (`g017`), **0 broken**, recall@5 **0.63 → 0.64**.
> Vs the 50-item baseline: **7↑ 0↓** (was 6), McNemar **p = 0.016**. Absents stay **17**.
> **Asked as** — *"You added a reranker. Why doesn't it just sort the top-20 by the new model?"*

### D69 — Sphinx-role strip at embed/BM25 time: measured and rejected

> **Decided 2026-08-22** — do **not** strip `:class:`_orm.Session`` → `Session` (or unwrap
> ``literals``) before embedding or BM25. `chunks.jsonl` and the Qdrant payload stay raw.
> **Instead of** — the Phase 1 deferral in `rag/chunk.py` ("if Step 5 shows markup hurting,
> strip in Phase 3"), which looked like the obvious next lever for the **17** absents.
> **Measured on the 100 after `D68`.** BM25-only strip: headline stayed ~0.63, absents still 17.
> Full re-embed with strip: recall@5 **0.64 → 0.58**, vs baseline **5↑ 2↓** (`g008`, `g013`
> broken), McNemar noise. Absents only **17 → 15** — two pages entered the top-20 while the
> top-5 fell apart. Mean tokens dropped 363 → 314; the model was not starving for room.
> **Why it failed (best current read).** Role markup is ugly to humans, but BGE-M3 already
> embeds the inner identifiers; stripping also deletes path cues (`_orm`, `_engine`) the dense
> space had been using. Cleaning for BM25 alone desynchronised the two hybrid channels.
> **What remains.** `rag/textnorm.py` and its tests stay as the rejected experiment — so the
> next sitting does not re-derive a worse embed. Boundary repair (`D56` 10.7%/6.3%) is still
> open, but the 17 absents' answer chunks show **zero** ends-open/opens-ref on audit shapes —
> so fixing `D56` is unlikely to be the absent fix. Phrasing / corpus ceiling owns most of them.
> **Asked as** — *"Did you clean the Sphinx markup before embedding?"* — yes, measured, reverted.

### D70 — boundary re-chunking: rejected on a survey of the absents, not attempted

> **Decided 2026-08-22** — do **not** re-cut chunk boundaries in Phase 3. `ROADMAP.md`'s step 3
> ("code split by function, prose split by paragraph") closes as a **measured rejection**, and
> Phase 3 ends here on retrieval.
> **Instead of** — doing it because it was on the list. It was written into the ROADMAP before
> Phase 1 ran, when the five known failures were all filed as one problem, and `D56` gave it a
> real-looking number afterwards: **10.7%** of chunks do not stand alone, **6.3%** lose content
> outright. That number is about the **corpus**. The question Phase 3 has to answer is about the
> **17 items retrieval cannot find**, and those are not the same population.
>
> **Why the absents are the only population that can justify it.** An item outside the top-20 is
> beyond every reranker by construction — `D68`'s cross-encoder reorders what retrieval already
> returned and can no more reach rank 47 than it can invent a page. Re-chunking is recall-side,
> so it is judged on the absents or it is judged on nothing.
>
> **Measured 2026-08-22, on the 17 absents after `D68`** — `rag.score --absents`:
>
> | shape of their 30 answer chunks | count | corpus rate |
> |---|---|---|
> | A ends announcing what never follows (`D56`) | **0** | 4.1% |
> | B opens pointing at what is not here (`D56`) | **0** | 6.9% |
> | C boundary severed inside a code listing (§R5.3) | **1** | 0.2% of cuts |
> | any of the three | **1 of 30** | 10.7% |
>
> **The control is what makes that a result.** The 74 items retrieval *does* find carry
> **2 of 123** flagged answer chunks — 2%. Broken chunks are no rarer behind the items that
> succeed than behind the items that fail. **Chunk quality is not what separates them.**
>
> **The one hit was read, not counted.** `g113` → `c02823`, and it does not survive reading:
> the chunk ends on a **complete** doctest (`{stop}<...>`), and `c02824` opens a separate
> `>>> session.rollback()` teardown rather than continuing the listing. Shape C fires on the
> pair of indented code edges; here the listing was already finished. **Zero real severances.**
>
> **What this does NOT claim.** Not that the chunker is good — `D56` stands, 6.3% of the corpus
> still loses content, and `c00138`'s payload is still gone. Not that boundary work is worthless
> for Phase 4: a severed listing pasted into a prompt is a *citation-quality* defect, and §R5.3's
> "at least 11 of 3077" is about what the model is handed, not about what search can find. It
> claims one thing — **re-chunking is not the lever that reaches the 17**.
>
> **What it cost to find out: nothing, and that is the point.** `D69` spent a full re-embed to
> learn its answer. This survey reads rows the scorer already has. **Ask the population before
> paying for the fix** — had `--absents` existed on 2026-08-21, `D69` would have been cheaper to
> reject, because the same output already said the absents were not shape failures.
>
> **Now enforced rather than remembered.** The claim lived in `PHASE-3.md` prose from 08-22
> morning with no command behind it — green CI the whole time, since `check_runnable` has no
> opinion about sentences. It is `rag.score --absents` now, using `chunk.py`'s **own**
> predicates (`ends_open_shape`, `opens_backward_shape`, `severed_listing`), with a mutation test
> asserting the scorer holds no private copy. §R5.3's shape C had a hand-computed figure and a
> `# summary of` block; it is code with three tests, including the indented-glossary control
> that separates 11 from 123.
> **Asked as** — *"Your chunker breaks 10% of chunks. Why didn't you fix that?"* → *"Because I
> checked which items it was costing me. Zero of the thirty chunks behind my seventeen misses
> are broken, and the items I retrieve fine have broken chunks at the same rate. It's a real
> defect; it isn't this one."*

### D71 — grade citations mechanically before grading meaning with a judge

> **Decided 2026-08-22** — Phase 4's first metric is **citation integrity**, computed with no
> judge model, no API key and no free tier: `rag/judge.py --citations`. Faithfulness (a reading
> task, needing a strong judge) is built on top of it, not instead of it.
> **Instead of** — starting with LLM-as-judge, which is what `ROADMAP.md` lists first. Two
> reasons, and neither is that judges are bad.
>
> **1. The cheap half is exact, and it already catches the defect that opened the phase.**
> `g065` fabricated `op.create_view` / `op.drop_view` beside two real Alembic calls — and
> **carried no citation on the code block**. Nothing in this repo can decide from text whether
> an API exists (that needs the real library; `tools/audit_golden_fullbar.py` runs 2.0.51). What
> a script *can* say is that the model emitted executable-looking code and pointed at no source
> for it. That is the machine-visible shadow of a fabrication, and it costs nothing to count.
>
> **2. A judge needs something to be calibrated against.** `ROADMAP.md` requires reporting the
> judge's agreement with a human on ten hand-checked items. Deterministic counts are the rows
> that agreement is measured on — a judge with no mechanical baseline beside it is a second
> opinion about nothing.
>
> **The count `probe.py` structurally cannot produce.** Its `signals()` builds citations as
> `{n for n in range(1, len(hits) + 1) if f"[{n}]" in answer}` — it only ever looks for numbers
> that **exist**. An answer citing `[7]` when five sources were supplied contributes nothing
> there and reads as `uncited`. Those are two different defects wanting two different fixes:
> `uncited` is a model that did not cite, `out_of_range` is a model citing a source it was never
> given. The second is strictly worse and much rarer, so it gets its own count instead of being
> absorbed into the first. Pinned by a test.
>
> **Refusals are excluded from every citation rate.** An answer that declines has nothing to
> cite; counting it as `uncited` would make the system look worse the more honest it got. That
> is `D62`'s trap in a new place, and it is a test, not a comment.
>
> **First real run found a bug in this file, not in the system.** A blank line sits between a
> citation and the code fence it introduces, so "the previous line" is empty — the lookback
> credited nothing and scored every properly cited block as uncited. Caught by the test written
> from the cited-block case, before any number was published.
>
> **Then the first real numbers, and they were checked before being believed.** On the first
> five golden items: 3 refused, and **both** answered items cited **nothing at all**, with code
> blocks carrying no source. 100% of an n of 2 is exactly what a broken regex prints, so one raw
> answer was printed and read: `g002`'s answer contains **zero** `[n]` markers, and copies Sphinx
> role markup (`` :meth:`_orm.Query.from_self` ``) straight into user-facing text. The detector
> is right and the answer really is uncheckable.
> **Asked as** — *"How do you know the answer isn't made up?"* → *"I count the ones that cite a
> source that doesn't exist, and the code blocks that cite nothing. Then a judge reads the rest,
> and I report how often it agrees with me on ten I checked by hand."*

### D72 — end-to-end is the Phase 4 headline, and the over-refusal COUNT grows as retrieval improves

> **Decided 2026-08-22, from the Phase 4 Step 1 re-baseline** — the number quoted for the system
> is **end to end**: the answer chunk reached the prompt **and** the model did not decline. It is
> printed by `rag.score --refusals`, not derived by hand in a doc, and refusals stay split out of
> recall exactly as `D62` requires.
> **Instead of** — quoting `recall@5`, which is a **ceiling**, and hand-subtracting one printed
> number from another. That arithmetic produced the `0.36` and `0.35` figures in earlier docs:
> right both times, reproducible by no command. `CLAUDE.md`'s measurement rule exists for this,
> and the most important number in the phase was the one still breaking it.
>
> **Measured, one sitting, Mac, after Phase 3 (`D54` respected):**
>
> | | 2026-08-21 (pre-Phase 3) | 2026-08-22 (post) |
> |---|---|---|
> | retrieval ceiling, `recall@5` | 0.49 | **0.64** |
> | answer reached the prompt | 45/91 | **58/91** |
> | **end to end** | **32/91 = 0.35** | **39/91 = 0.43** |
> | over-refused **with the page in hand** | **13** | **19** |
> | generation's loss | ~15 points | **21 points** |
>
> **Phase 3 paid, and about half of it arrived.** Retrieval gained 15 points; the user got 8.
>
> **The finding, and it is the counter-intuitive one.** The over-refusal cell **grew from 13 to
> 19 while the system got better**. That is not a regression — it is arithmetic. The cell counts
> items where the answer **is in the prompt** and the model refused anyway. Improve retrieval and
> more items become eligible for that cell. **A raw count of this defect is not comparable across
> retrieval changes**; read it as a rate against the ceiling — 13/45 = 29% then, 19/58 = 33% now.
>
> **The named example, checked rather than asserted.** Phase 3 fixed seven items against the
> saved baseline (`g017`, `g024`, `g038`, `g044`, `g046`, `g047`, `g050`). **Two of them —
> `g044` and `g050` — are on today's over-refusal list.** Retrieval went and found the page,
> put it in front of the model, and the model declined. A retrieval win converted directly into
> a generation failure, and every metric in `PHASE-3.md` still scores both as successes.
>
> **What is `D54` drift and what is not.** The list is not simply 13 plus six. **`g015` left it**
> and **seven joined**; twelve are common. `D54` says refusal behaviour is stable within a
> sitting and drifts across days, so the one-item exit is expected noise. Seven joining, two of
> them Phase 3's own fixes, is larger than drift and has a mechanism.
>
> **Unchanged, and worth saying:** unanswerable items still score **7/9 refused, 2 FABRICATED**
> (`g056`, `g065`) — identical to 08-21. Retrieval work moved nothing there, which is what
> `D70` predicted: an item with no answer in the corpus has no page for retrieval to find.
> **Asked as** — *"Your retrieval improved 15 points. What did the user get?"* → *"Eight. And
> two of the seven questions I fixed now get refused with the right page in the prompt — which
> is why the phase after retrieval is generation, and why I report end to end."*

### D73 — measured: the sources are mostly decoration, and Phase 1's number was too small to say so

> **Found 2026-08-22**, first full `rag.judge --citations` run over the 100-item golden set.
> Deterministic, no judge model, no API key — this is arithmetic over brackets, not an opinion.
>
> | over the **48** items that got an answer | | |
> |---|---|---|
> | cite **nothing at all** | **31** | **65%** |
> | cite only one of the five sources | 16 | 33% |
> | contain code | 28 | 58% |
> | …of those, **code with no citation** | **26** | **93%** |
> | cite a source that does not exist | **0** | 0% |
> | **mean source coverage** | **0.07** | five pages in, ~a third of one cited |
>
> **`rag/ask.py` opens with the words "SOURCES ARE NOT DECORATION".** Measured, they mostly are.
> The whole Phase 1 design argument — *"without the chunks there is no way to tell a correct
> answer from a lucky one"* — depends on the citation actually being emitted, and on two answers
> in three it is not.
>
> **This was verified four ways before it was written down**, because a 65% defect rate is
> exactly what a broken detector prints: `build_prompt` numbers the sources `[1]`…`[5]`; the
> SYSTEM clause says *"cite the source number in brackets, like [2]"*; `generate()` sends that
> SYSTEM message, and the judge uses the identical path `score.py --refusals` does; and one raw
> answer was printed and read — `g002` contains **zero** `[n]` markers and copies
> `` :meth:`_orm.Query.from_self` `` into user-facing text.
>
> **Zero out-of-range citations is a real result too.** When the model does cite, it never
> invents a source number. The defect is omission, not fabrication of provenance — and those
> want different fixes.
>
> **Phase 1 reported this as `uncited: 3` and it was not wrong, it was underpowered.**
> `deliverables/FAILURES.md` counted 3 over 19 probe questions, of which 8 refused — so **3 of
> 11 answered = 27%**. Wilson: **[0.04, 0.51]** against this run's **[0.52, 0.78]**. The bands
> miss each other by a hair, so these are not one rate measured twice; but n=11 could never have
> settled it either way. **Second time this repo has been bitten by the same thing** — three
> unanswerable items were "never enough to measure a fabrication rate" on 2026-08-21, and eleven
> answered questions were never enough to measure a citation rate.
>
> **The mechanism is open, and named rather than guessed.** The obvious suspect was phrasing —
> `D63` proved it decides retrieval. It does not obviously decide this: the uncited-code items
> split **breakages 21% / github 20% / migration_guide 31% / stackoverflow 36%**, with the
> repo's own docs-vocabulary set *above* real GitHub questions. That is a partial signal
> (code-bearing answers only), so `--citations` now prints a **full per-provenance split** and
> `--save` keeps the rows, because the next run costs ~100 generations and the question should
> not have to be asked twice.
>
> **What this does NOT claim.** Not that 31 answers are wrong — an uncited answer can be
> perfectly correct, and `g002`'s was. It claims they are **uncheckable**, which is the property
> the whole retrieval apparatus was built to provide.
> **Asked as** — *"Your system cites its sources. How often?"* → *"A third of the time. I
> measured it, I know which two-thirds, and I know the model never cites a source that doesn't
> exist — so it's an omission problem, not a provenance-fabrication problem."*

### D74 — on a 7B model, WHERE the instruction sits beats how firmly it is worded

> **Measured 2026-08-22**, 20-item screen, five wordings in one sitting (`D54`), before
> committing a night of GPU-less generation to any of them.
>
> | | end/end | over-refused | uncited | code with no source |
> |---|---|---|---|---|
> | **D** shipped | 6/18 | 3 | **5/7** | 4/4 |
> | **E** system msg, citation *mandatory* | 6/18 | 3 | **5/7** | 3/4 |
> | **F** system msg, "sources are search results" | 7/18 | 2 | 6/8 | 5/5 |
> | **H** *same wording as D*, moved to the **user turn** | **8/18** | **1** | **1/13** | 2/6 |
> | **I** F + H | 8/18 | 1 | 3/12 | 4/6 |
>
> **E is a null result and it is the informative one.** It says *"an answer with no bracketed
> number in it is not acceptable"* — about as hard as English gets — and returns cells identical
> to D's. On `g002` its answer is near word-for-word D's, with zero citations. The model is not
> defying the instruction; it is not attending to it. By the time generation starts, the system
> message is thousands of tokens back, behind five full documentation chunks.
>
> **H changes no wording at all.** It carries D's system prompt untouched and puts the citation
> rule on the last line of the *user* message, immediately before the `ANSWER:` cue. Uncited goes
> **5 of 7 → 1 of 13**.
>
> **The denominators are the finding, not just the ratios.** D answered 7 of 18; H answered
> **13**. Asking for citations made the model *more* willing to answer — over-refusals fell
> 3 → 1. That was not the hypothesis: H was aimed at `D73`, and it moved `D72` as well.
>
> **This is the same shape as `D54`.** Prompt D beat B not by being firmer but by changing the
> mechanism — sufficiency-judging out, partial answers in. E is the "say it louder" branch, and
> it does nothing. **Position is a lever; volume is not.**
>
> **The 100-item run, 2026-08-23, corrected for the artifact in `D76`:**
>
> | | end to end | over-refused | uncited | code with no source | fabricated |
> |---|---|---|---|---|---|
> | **D** shipped | 39/91 = **0.43** | 19 | 31/48 = **65%** | 26/28 = 93% | 2 |
> | **H** | **47/91 = 0.52** | **10** | **6/62 = 10%** | 20/37 = 54% | 2 |
> | **I** | 46/91 = 0.51 | 11 | 11/63 = 17% | 25/37 = 68% | 2 |
>
> ⚠️ **Citation columns restated 2026-09-10 under `D85`'s denominator** — every answered row, not
> only the answerable ones. They read `31/46 = 67%`, `6/60 = 10%` and `10/61 = 16%` when published.
> **Nothing about the result changes**; the two rows added per arm are the fabrications, which are
> answers a user sees and cannot check. Generation columns are untouched.
>
> **H: 9 fixed, 0 broken, exact McNemar p = 0.0039.** `D61`'s bar for a Phase 3 retrieval move
> was ~6 clean fixes with no regressions; this clears it. Fixed: `g008`, `g021`, `g049`, `g050`,
> `g064`, `g095`, `g099`, `g103`, `g106`.
>
> **End to end 0.43 → 0.52 is larger than everything Phase 3's retrieval work bought** (0.35 →
> 0.43). One sentence, moved.
>
> **Two things it does not fix, and both are stated rather than buried.** Fabrications stay at
> **2** across all three wordings — `g056` and `g065` are untouched by position, emphasis or
> premise, so prompt work is not the lever there. And **53% of H's code blocks still carry no
> source**: the defect is much better, not solved.
>
> **`I` is `H` plus F's relevance premise and it is worse on every column.** Adding a second
> instruction dilutes the first. That is why `I` was kept in the full run rather than dropped
> for containing a winner.
>
> **H's ceiling is 57 where D's is 58** because one item (`g079`) timed out twice under H and is
> excluded from both sides of the pairing (`D75`). H's 47/91 is therefore measured against a
> denominator including an item it never got to answer — conservative in H's favour's opposite
> direction, which is the right way round.
>
> **Nothing ships on this. The prompt that ships is Viraj's call** — the last time that was
> assumed rather than asked, it was the wrong call (2026-08-17, prompt D). What is recorded here
> is a measurement and a recommendation, not a change to `ask.SYSTEM`.
> **Asked as** — *"How did you fix the citation problem?"* → *"I didn't reword the instruction —
> I moved it. Stating it more forcefully in the system prompt changed nothing measurable; the
> same sentence next to the answer cue took uncited answers from 71% to 8% on the screen."*

### D75 — a long generation run must checkpoint, and a slow call is not a dead server

> **Learned the expensive way, 2026-08-22, twice in two days.** The `--refusals` run on 08-21
> died at session teardown with nothing written. The first 100-item prompt sweep died at
> generation **150 of 300** — ~50 minutes — and saved **zero rows**.
> **Cause of the second.** `urllib` raises `socket.timeout` on a slow response. That is a
> `TimeoutError`/`OSError` and **not** a `URLError`, so it walked straight past a handler that
> had been written to catch "Ollama is not running" and aborted the process instead.
> **Two different conditions had been collapsed into one.** *No server* should exit — retrying
> is pointless. *This one generation was slow* should not; the next item is probably fine.
> **Fixed:** one retry at a longer ceiling (300s, then 900s), then the item is recorded as
> `failed` and the sweep continues. Results checkpoint to disk every 25 items and after every
> variant, so a crash costs minutes rather than a night.
> **And a failed row is neither an answer nor a refusal.** It is excluded from every cell, and
> from pairing on *both* sides — if the control failed and the variant answered, that is a
> missing measurement, not a fix. Counting it either way would let a flaky night read as a
> prompt effect, which is the specific way this class of bug produces a *wrong* result rather
> than no result.
> **Pinned by four tests**, because these paths only execute on a night that has already gone
> wrong and would otherwise be written once and never exercised.
> **Asked as** — *"What happens if one call hangs three hours into a run?"*

### D76 — the instrument was broken by the intervention it was measuring

> **Caught 2026-08-23, before publishing a wrong result.** The first read of the `H` sweep said
> **12 fixed, 0 broken, p = 0.000** and end to end **0.55**. Spot-checking one raw answer, as the
> measurement rule requires, produced this for `g006`:
>
> ```
> [2] The sources do not answer this.
> ```
>
> **That is a refusal wearing a citation.** `ask.refused()` is a **prefix** test —
> `answer.strip().startswith("The sources do not answer")` — and `"[2] The sources…"` does not
> start with it, so it was scored as an **answer**.
>
> **The mechanism is the point.** `H`'s entire content is *"cite the source number before each
> statement"*. The model complied — including in front of its own refusal. **The variant under
> test changed the shape of the output in exactly the way that defeated the detector reading
> it.** `D` shows **zero** such cases, because `D` barely cites at all; the bug is invisible
> until the thing you are measuring starts working.
>
> **Corrected: 6 of H's answers were cited refusals, and 3 of those sat in the "fixed" column.**
> True result **9 fixed, 0 broken, p = 0.0039**, end to end **0.52**. Still significant, still
> clears `D61`'s bar — and now true. Three items and three points of the original claim were
> artefact.
>
> **Fixed in `ask.refused`, which is the one detector** (`D62`): leading `[n]` markers are
> stripped before the prefix test. The anchor stays at the START of the answer, so this does not
> weaken the prefix test into a substring search — the property that paragraph exists to protect,
> because prompt D deliberately emits *"here is the part they cover and here is the part they do
> not"*, which is an answer.
>
> **No recorded number moves.** `D` produced zero cited refusals, so `D72`, `D73` and every
> earlier refusal measurement stand exactly as published. Verified rather than assumed.
>
> **Re-scoring cost nothing because the answers were saved** (`D75`). Had the sweep stored only
> its summary table, correcting this would have meant regenerating 300 answers — and the drift
> `D54` measures would have made the corrected run not comparable with the original.
> **Asked as** — *"Your prompt change scored p = 0.000. How do you know the improvement is
> real?"* → *"Because the first version of that number was wrong and I found it. The model cited
> its own refusals, my refusal detector is a prefix test, and it scored six declines as answers.
> Fixed the detector, re-scored the saved answers, and it's p = 0.0039 instead."*

### D77 — groundedness, measured without a judge: the fabrication COUNT hid a collapse in severity

> **Built and measured 2026-08-23.** `rag/judge.py` `ungrounded_calls()` — dotted API calls the
> answer's **code** makes that appear in **none of its own sources**. Deterministic: no judge
> model, no API key, no free tier. It is the only Phase 4 metric that reaches the defect prompt
> work could not move (`D74`: fabrications sat at **2** under every wording tried).
>
> **It measures GROUNDEDNESS, not existence, and the boundary is the point.**
> `op.create_table` is a real Alembic function; if no retrieved source mentions it, an answer
> calling it is still unsupported by the pages the system was given — which is exactly what a
> RAG faithfulness metric should say. *Does this symbol exist at all* is a different question,
> answered against the real library by `tools/audit_golden_fullbar.py`. **Neither subsumes the
> other**, and `g065` fails both.
>
> | | answered | with an ungrounded call | rate |
> |---|---|---|---|
> | **D** shipped | 48 | **2** | 4% |
> | **H** | **62** | **0** | **0%** |
> | **I** | 63 | 3 | 5% |
>
> **H answers 14 more questions and grounds every line of code in all of them.**
>
> **The severity collapse the count could not see.** `fabr` stays at 2 for all three wordings,
> so on that metric nothing improved. What actually changed, on `g065`:
>
> - **D** produced a confident Alembic recipe — `op.create_table`, `sa.Column`, and on the
> 08-21 run `op.create_view`, which does not exist on alembic 1.19.1. **A fabricated procedure.**
> - **H** produced: *"[3] SQLAlchemy supports ALTER TABLE, CREATE VIEW, CREATE TRIGGER… For a
> more comprehensive option, schema migration tools like Alembic or SQLAlchemy-Migrate can be
> used."* **Zero code blocks, one citation, and a paraphrase of the source it cites.**
>
> **Both are scored as "answered an unanswerable item". They are not the same failure.** One
> invents a procedure a developer would run; the other repeats what the page says and stops.
> **A count of fabrications is not a measure of harm**, and this is the entry that says so.
>
> **It also confirms the golden note independently.** The 2026-08-21 spot-check rewrote `g065`'s
> reason to *"CREATE VIEW chunks exist (`c00484`/`c02056`) but do not teach same-migration
> CREATE TABLE + VIEW"*. H found exactly those chunks and repeated exactly that much. The label
> and the behaviour agree, arrived at from opposite directions.
>
> **What it does not catch: `g056`.** Never flagged under any wording, because it fabricates in
> **prose**, not code. A code-grounding detector is structurally blind to that, and saying so is
> better than implying coverage it does not have. Prose-level faithfulness is the judge's job
> and still needs a pinned model.
>
> **False positives were designed out and are tested.** Local variables (`subq`, `stmt`) are not
> API calls; identifiers from the **question** are subtracted, because a developer pasting their
> own broken code puts symbols in the prompt the docs will never contain, and flagging those
> measures the questioner; `Session.get` in the docs grounds `session.get` in the answer, or the
> metric would report capitalisation as fabrication. Matching is `probe.py`'s `_contains`,
> imported rather than reimplemented — the naive version counted `relation` inside every
> `relationship`, 798 chunks against 0.
> **Asked as** — *"How do you detect hallucination without a bigger model?"* → *"For code I
> don't need one. I check whether the API calls in the answer appear in the pages I retrieved.
> The shipped prompt makes two ungrounded answers in 48; moving the citation rule makes zero in
> 62 — and it turned an invented Alembic recipe into a cited quote of the FAQ."*

## Using this in an interview

**Three entries carry the project**, and they are the ones nobody else will have:

1. **D03** — ground truth was *measured*, and one pattern both migration tools call safe fails
   anyway.
2. **D09** — the eval answer key was deliberately kept out of the corpus, at a cost to current
   quality.
3. **D04** — retrieval is bad on purpose, and there is a written file of failures to prove what
   the fix bought.

**One entry is the trap.** If asked about the stack — Qdrant, BGE-M3 — §H is the truthful
answer. Saying *"chosen, not yet benchmarked, and here is what I would compare it against"*
reads as engineering judgment. Reciting a feature comparison you never ran reads as a bluff,
and the follow-up question finds out.

---

### D78 — pinning the judge is a convenience; "same judge, both arms, one sitting" is the requirement

**Decided 2026-08-30.** `PHASE-4.md` Step 2 said the judge must be pinned *"the same way
swapping the golden set would"* invalidate rows (`D65`/`D61`). **The analogy imported a
conclusion without its cost structure**, and the cost structure is the whole argument:

| | if it moves under you | cost to restore |
|---|---|---|
| golden set (`D65`) | every row is unpaired | **~25 hours** of `D06` hand-verification |
| vector store (`D31`) | 4 of 19 probe questions returned a different top-5 | a re-index — minutes |
| **judge** | the absolute faithfulness number shifts | **~60 calls** — minutes |

**Sized rather than argued.** Over `deliverables/prompt-sweep-phase4.json` the answered items
are **D 48 / H 62 / I 63**, so one call per answer is ~60 per variant, ~180 claim-by-claim, and
~500 for all three variants read sentence by sentence. **Every free tier absorbs that**, which
removes rate limits as a selection criterion and leaves stability as the only one.

**What is tight instead:**

- **Same judge, both arms, one sitting** — `D54` applied to the judge rather than the generator.
  Judge D on Monday and H on Friday and the comparison is worthless however carefully the model
  was pinned. This is the correctness requirement and it is free.
- **Agreement with a human, measured** (Step 5's ten). A pinned judge whose agreement is unknown
  is a precise instrument of unknown accuracy. `g065` is the standing proof that the label no
  audit can test is where this repo has actually been wrong.

**In code, not in prose.** `rag/faithful.py` stamps the model onto **every row** rather than
defending one id forever, and `--models` asks the key what it can reach so the pin is chosen
from what exists instead of from memory — a model id written from memory 404s.

**The consequence that inverts the plan:** a **local** judge is *more* pinnable than any API,
because you hold the weights — no deprecation, no terms change, nothing trained on our data.
`ROADMAP.md`'s *"too weak to grade itself"* is an objection to **self**-grading; a different,
larger model is not that. Gemini stays first because it is stronger and the key exists; local is
the fallback if the agreement-of-ten comes back poor, and it is a real fallback rather than a
consolation.

**The pin, recorded rather than defended — `gemini-3.6-flash`, chosen 2026-08-31.**

**And the argument for `--models` arrived within one call of writing it.** `gemini-2.5-flash`,
written into `MODEL` from memory, returned **HTTP 404 — *"no longer available to new users…
use models/gemini-3.6-flash"***. The credential was fine: a 404 on the model, not a 401 on the
key. A model id written from memory is a stale id, and it fails in a way that reads exactly like
a bad key.

**The sharper finding: the catalog is not the truth.** `--models` lists 38 ids **including
`gemini-2.5-flash`** — the one that had just 404'd. The listing is what the API advertises; a
call is what actually happens. **`--check` is the authority; `--models` only proposes
candidates.** Two commands, two jobs, and neither substitutes for the other.

**No dated snapshot exists for the stable flash line** — every dated id in the catalog is a
preview — so the best available pin is a version-numbered id rather than `gemini-flash-latest`,
which floats by design and is the thing this entry says to avoid.

**Proven end to end on real data, not just on auth.** `g056` — the item `D77` states the code
grounding detector is *structurally blind* to, because it fabricates in prose rather than in a
code block — was judged against its five real retrieved sources and came back **`PARTIAL`**,
stamped `gemini-3.6-flash`. That is the first measurement in this repo that reaches the defect
`D77` named and could not reach.

**Interview question it answers:** *"You pinned your evaluator — why?"* Because rows must be
traceable to the reader that produced them. **Not** because the id must never change: re-running
this judge is minutes, so pinning is bookkeeping. The thing that would actually invalidate a
comparison is judging the two arms at different times, and that is what the discipline forbids.

---

### D79 — a subscript is not a citation, and the second instrument H broke

**Found 2026-08-30.** `rag/judge.py` matched citations with `\[(\d+)\]` over the whole answer,
so **`keys[0]`, `row[1]` and `argv[1]` were read as citations.** On `g016` under prompt H this
printed the project's first out-of-range citation — a source numbered `[0]` that does not exist —
and the source was `row[keys[0]]` inside a Python block.

**Measured across all 300 saved D/H/I answers the old regex fired 3 times and all 3 were
subscripts** (`keys[0]`, `keys[1]`, and a prose mention of `row[0]`). Fixed with a lookbehind:
a citation is `[n]` **not** preceded by an identifier character, `]` or `)`.

**Why a lookbehind rather than "strip the code fences first".** The `g121` case is in **prose**,
so fence-stripping would miss it — and `uncited_code_blocks()` deliberately credits a `# [2]`
comment *inside* a fence, which fence-stripping would blind. The same false positive in that
direction would have laundered an uncited code block as cited, hiding the `g065` shape the
function exists to catch. A test pins that direction too.

**No published number moves.** No answer's cited/uncited status flips, so `D73`'s 65% and the
`D74` table stand as written; only H's and I's phantom out-of-range entries disappear, which
makes `D73`'s *"zero invented source numbers"* claim **more** true rather than less.

**The pattern, and it is the second instance in one phase.** `D76` was the first: H's compliance
put `[2]` in front of a refusal and defeated `ask.refused()`'s prefix test. Here H's extra code
put `[0]` in front of the citation counter. **Both times the variant under test reshaped the
output in exactly the way that defeated the instrument reading it, and both times `D` was clean
— because `D` barely cites and writes less code.** The bug is invisible until the thing being
measured starts working.

**Consequence, and it is now a habit rather than a memory:** when a prompt change improves a
metric, re-verify the **detector** against the new output shape before believing the metric.

**Interview question it answers:** *"How do you know your evaluation harness is right?"* By
reading raw outputs from the arm that changed, not only from the control — twice now the control
was clean and the treatment exposed the bug.

### D80 — the pinned judge went dark and the free tier is 20 calls a day, so the judge is local

**Measured 2026-09-03.** `D78` was written three days earlier, pinned `gemini-3.6-flash`, and
argued that pinning is bookkeeping because a re-run is *"~60 calls — minutes"*. **Two of its
premises failed on the same morning, and both failed by measurement rather than by argument.**

**First: the pinned id stopped answering.** One call each, same key, same minute:

```
gemini-3.6-flash     FAIL HTTP 503 from gemini-3.6-flash
gemini-3.5-flash     OK   SUPPORTED
gemini-3.7-flash     OK   SUPPORTED
gemini-3.8-flash     OK   SUPPORTED
```

`gemini-3.6-flash` answered *"currently experiencing high demand"* through four retries while
three siblings answered first time. **A pinned id is a promise about a name, not about a
service.** `D78` was right that the id is bookkeeping — it just did not expect the bookkeeping to
be the thing that broke.

**And the cadence is the corroboration.** All four ids above were reachable in the catalog on the
same morning, and `3.8` — the newest of them — answered first time. If that line ships a new
flash model every few weeks, then **the pin is being replaced faster than a phase completes**,
and "pin a version-numbered id rather than a floating alias" (`D78`) buys less than it sounds
like it does. It stops the model changing *underneath* a run; it does not stop the id you pinned
from becoming the unmaintained one. `--model` is the answer to that, and `stamp()` is what makes
the answer safe: change the reader, never lose which reader produced a row.

**Second, and this one contradicts `D78` in as many words.** `D78` says:

> *"Rate limits are not the constraint on any free tier, which removes the reason most people
> pick one."*

The 429 body disagrees, and it names the quota:

```
quotaId:    GenerateRequestsPerDayPerProjectPerModel-FreeTier
quotaValue: 20
```

**Twenty requests per day, per model.** D + H over the saved sweep is about **110 calls**. So the
API judge cannot finish this comparison today, or in any one day — and `D78`'s own tight property
is *same judge, both arms, **one sitting***. Spreading the run across six days to fit the quota
does not satisfy that property, it destroys it. **The sizing in `D78` was arithmetic about the
workload with no measurement of the ceiling it had to fit under.**

**The escape was already written down.** `D78`'s last paragraph:

> *"A local judge is in fact MORE pinnable than any API — you hold the weights — and stays the
> fallback if the agreement-of-ten comes back poor."*

**So the judge is `gemma4:e4b` on Ollama, and nothing else changed.** `local_post()` wears the
Gemini transport's exact signature — `(path, body, key, timeout)`, same return shape — so
`generate`, `judge_claim`, `judge_answer` and `sweep_rows` are untouched by which judge is in
use. A judge swap that needed edits in four call sites is a judge swap nobody makes under time
pressure, and `D78` requires the swap to stay cheap.

**It is not self-grading, which is the objection `ROADMAP.md` actually raises.** The generator is
`qwen2.5-coder:7b`; the judge is a different family and a different size. Nothing marks its own
homework. And *"but is a local model strong enough"* is the question **Step 5 exists to answer
with a number** rather than to settle by reputation: `--agreement` puts ten of this judge's
verdicts in front of a human. **A strong judge with unmeasured agreement and a weak judge with
unmeasured agreement are the same object.**

**Two defects found while building it, both silent, both the flattering direction:**

- **The report named the wrong instrument.** It printed the module constant, so a run judged by
  `gemma4:e4b` announced itself as `gemini-3.7-flash`. Now the header is built from the row
  **stamps** — which is what `D78` made `stamp()` mandatory for — and two distinct ids in one run
  print `!! TWO JUDGES IN ONE RUN`, because that is a void comparison rather than a warning.
- **Ollama truncates at `num_ctx` in silence.** The default is 4096 tokens; the judge prompt
  measured **7127–11149 characters, roughly 1800–2800 tokens**. It fits — *today* — which is
  exactly when to pin it, because the first answer that overflows produces confident verdicts
  from four passages out of five and no error anywhere. `LOCAL_CONTEXT = 8192`, pinned by a test.

**Interview question it answers:** *"What happens when your evaluator's provider changes under
you?"* Ours did, twice in one morning — a 503 on the pinned id and a daily quota two orders of
magnitude below the workload. The design survived because the model id was **recorded on every
row instead of defended**, and because the transport was one injectable function. What it cost
was a paragraph of `D78` being wrong, which is written down rather than edited away.

---

### D81 — the scorecard recomputes what it can, and the control was the only clean arm again

**Built 2026-09-03**, and it closes `PHASE-4.md`'s gate: *"one command scores the full golden set
and emits retrieval metrics, faithfulness and citation accuracy in one report."*

`uv run python -m rag.judge --report`. Five sections, and **each one says whether it was measured
live or read from a file**:

| section | source | why |
|---|---|---|
| retrieval | **live**, needs Qdrant | ~100 lookups, no generations — cheap, so quoting a stored figure would be laziness |
| generation | read: `prompt-sweep-phase4.json` | 300 saved answers, ~2.5 h of Mac time; regenerating gives **different** answers (`D54`) |
| citations | read, then **re-scored** | see below |
| faithfulness | read: `faithfulness-phase4.json` | ~110 judge calls |
| judge agreement | read: `JUDGE-AGREEMENT.md` | a human fills it (`D06`) |

**A report that mixes a live measurement with a stored one and labels neither is how `0.64` came
to be quoted as the system's score.**

**The generation figures are a derivation, and it was checked against the published ones rather
than trusted.** From the saved rows the report computes D **39/91 = 0.43**, 19 over-refusals, 2
fabrications; H **47/91 = 0.52**, 10, 2; I **46/91 = 0.51**, 11, 2 — **every cell identical to
`D72` and `D74`**. That is the check that this is the same derivation those numbers came from and
not a plausible-looking second opinion.

**The denominator is every answerable item, failed rows included.** Dropping a `D75` failed row
per-arm gives D 91 and H 90 — two different rulers for a comparison that only means anything item
by item (`D61`). The failed count is printed in its own column so it cannot hide in the numerator.

**Citations are recomputed, not read, and that is the finding.** The saved file's citation fields
were written on 2026-08-27; `D79` changed what counts as a citation on 2026-09-01. Reading those
fields would reprint numbers the current code disagrees with. Re-scored with today's rules, the
report also names every row where stored and fresh disagree:

```
D: 0 rows
H: 1 row  — g016
I: 1 row  — g121
```

**`g016` is the named example, and the old bug was worse than "a phantom citation".** H's answer
contains `print(f"x: {row[keys[0]]}  y: {row[keys[1]]}")`. Pre-`D79`:

| | stored (2026-08-27) | today (`D79`) |
|---|---|---|
| `cited` | `[0, 1, 2]` | `[2]` |
| `out_of_range` | `[0]` | `[]` |
| `uncited_code_blocks` | **0** | **1** |

The subscripts did not merely invent a citation of a source numbered zero. **They made a code
block with no citation look cited** — the flattering direction, and invisible in the aggregate.

**And the shape is now familiar enough to name.** `D` produces **zero** stale rows; only `H` and
`I` do. `D` barely cites and barely writes code, so the instrument's bug cannot fire on it.
**Third time in this phase** that a defect in a detector was invisible until the variant under
test started complying: `D76` (a refusal wearing a citation), `D79` (a subscript read as a
citation), and now this. **Test your instruments against the arm that changed, never only against
the control.**

**A fourth instance of the same bug class, found by the report disagreeing with the published
table.** Section 2 printed H at **48/91** where `D74` says **47/91**. The cause: a `D75` failed
row carries **no `answer` key at all**, so `ask.refused("")` is `False` and the row walked into
the *delivered* count as a success. `g079` — an item with no answer — was being scored as an
answered one.

**It inflated H, the arm under test**, exactly like `D76` (a refusal wearing a citation) and
`D79` (a subscript read as a citation). **A failure is not an answer and not a refusal: it is a
missing measurement**, so it belongs in neither numerator while staying in the denominator, which
is what keeps both arms on one ruler (`D61`). Three tests now pin it, including one that asserts
the scorecard reproduces `D72`/`D74`'s cells for all three variants — so the next drift in that
derivation fails a test rather than needing a human to notice a `48` where a `47` belongs.

**Interview question it answers:** *"How do you report an evaluation you cannot fully run today?"*
By printing `NOT MEASURED` with the command that would fix it, rather than a zero or a blank.
Section 4 says so when there is no judge run, and section 5 says *"0 answered — a human has not
read them yet"* rather than reporting an agreement rate over an empty sheet. **An unmeasured
judge is a precise instrument of unknown accuracy, and the gate is written to refuse the
assumption.**

### D82 — prose faithfulness, measured: H's edge is NOT in being more faithful, it is in answering more

**Measured 2026-09-03**, 110 answers judged by `gemma4:e4b`, one sitting, both arms, identical
passages. The first prose-level faithfulness number in this repo, and the half `D77` declared
itself structurally blind to.

```
variant   answers  judged   SUPP  PART  UNSUP  UNPARSED  NO_PROSE  supported
D              48      47     40     2      5         0         1       85%
H              62      61     56     3      2         0         1       92%
```

⚠️ **`D`'s 85% does not reproduce on its own machine.** Re-judged 2026-09-10 — same Mac, same
judge, same saved answers, seven days apart — the D row reads **39/47 = 83%** and the H row reads
**56/61 = 92%**, unchanged to the verdict. Three D verdicts moved and no H verdict did (`D84`).
**The paired result below is untouched:** identical cells, identical ids. Quote D as **83–85%**
on this machine, or quote the run.

**Read alone, that says H is more faithful. The paired comparison says it is not — and the
paired comparison is the one `D61` requires**, because a rate over two different sets of answers
is two averages, not a result:

```
judged by both arms: 46          (D only: 2 — g079, g117; H only: 16)
H fully supported where D was not : 5   g024 g045 g078 g080 g083
D fully supported where H is not  : 1   g088
exact McNemar p = 0.2188
```

**5 fixed, 1 broken, p = 0.22.** `D61`'s bar is ~6 clean fixes with **no** regressions. This
clears neither half. **On the answers both prompts produced, H's faithfulness advantage is not
established.**

**So where does 85% → 92% come from? The sixteen items only H answered.** Thirteen of those
sixteen come back `SUPPORTED`. That is not H being more faithful on a given answer — it is H
answering fourteen more questions (`D74`) and the extra answers being mostly grounded.

**Which makes this a confirmation of `D74` rather than a new claim, and a more valuable one than
another citation count.** The obvious objection to shipping H has always been that a prompt which
makes a model *more willing to answer* buys its extra answers by talking past the evidence. That
objection is now measured and it does not hold: **willingness did not cost grounding.** Say it
that way, not "H is more faithful."

**`g088` is the one regression and it is worth reading rather than counting.** Same question,
both arms answered, and the judge splits:

- **D** — `SUPPORTED`: *"Passage [4] provides a complete code example and description detailing
  all the steps listed in the claim."*
- **H** — `UNSUPPORTED`: *"The passages do not contain the specific code example or the full
  instructional setup provided in the claim."*

H did not contradict the sources. **It supplied more than they contain.** That is the failure mode
a forthcoming prompt should be expected to have, it happened once in 46, and it is on the
agreement sheet for a human to confirm.

**`g016` is where three instruments converge on one item**, which is the strongest evidence in
this run that they are measuring something real:

| instrument | what it says about `g016` under H |
|---|---|
| `D79` re-score | the stored fields called it cited `[0,1,2]`; today `[2]`, and **uncited code blocks 0 → 1** |
| citation integrity | a code block with no source attached |
| **the prose judge** | `UNSUPPORTED` — *"None of the passages state that `row.keys()` is deprecated"* |

The subscript bug had made that code block *look* cited. Underneath it, the claim was not in the
pages either.

**`g065` comes back `PARTIAL` on both arms, and the reasons preserve `D77`'s severity split.** D:
*"support the general concept … but do not contain the specific code example or the detailed
`upgrade`/`downgrade` functions."* H: *"state that general ALTER support is outside SQLAlchemy's
scope, but recommend Alembic."* Same verdict, and the reasons describe a fabricated procedure on
one side and a paraphrase on the other. **A count of PARTIAL is still not a measure of harm** —
`D77` said this about fabrications and it survives contact with a judge.

**What this number is NOT.** `UNSUPPORTED` means *not in the pages the system retrieved*, not
*false*. A correct sentence the model knew from training and no retrieved page mentions scores
`UNSUPPORTED` here, deliberately: a RAG system answering from memory has not used its sources and
cannot be checked. **Existence** is `tools/audit_golden_fullbar.py`'s job on the real library, and
**code grounding** is `D77`'s. Three questions, three instruments, none subsuming another.

**A SECOND MODEL WAS ASKED THE SAME TEN, AND IT AGREED WITH THE JUDGE ON FOUR.** Measured
2026-09-03, `gemini-3.5-flash` against the `gemma4:e4b` rows on the sheet's ten:

```
  g045   D  UNSUPPORTED  -> UNSUPPORTED  agree
  g079   D  UNSUPPORTED  -> UNSUPPORTED  agree
  g080   D  UNSUPPORTED  -> PARTIAL      DIFFER
  g083   D  UNSUPPORTED  -> SUPPORTED    DIFFER
  g119   D  UNSUPPORTED  -> UNSUPPORTED  agree
  g016   H  UNSUPPORTED  -> UNSUPPORTED  agree
  g088   H  UNSUPPORTED  -> PARTIAL      DIFFER
  g056   D  SUPPORTED    -> PARTIAL      DIFFER
  g056   H  SUPPORTED    -> PARTIAL      DIFFER
  g014   D  SUPPORTED    -> PARTIAL      DIFFER

  4/10 = 40% model-to-model agreement
```

**Provenance of those ten, stated because two runs exist.** The table above is the **first**
cross-check, which answered all ten. A second run was needed to capture the verdicts to
`deliverables/JUDGE-CROSSCHECK.json` (the first predated the saving code), and it got **7 of 10
before the daily quota cut it off** — `g056` twice and `g014`, the three `SUPPORTED` controls, came
back `(no answer: 429)`. So the saved artifact holds **7** rows and reports **4/7 = 57%** over what
it actually answered, with the three unanswered printed beside it rather than dropped. **The
10-row table is the complete measurement; the file catches up on the next day's quota.** Both
numbers are real and they are not the same denominator, which is exactly why the tool prints the
denominator.

**All six disagreements are the same shape: the hosted model chose `PARTIAL` where the local
judge chose an extreme.**

> **PARTIALLY RETRACTED 2026-09-05 by `D83`.** This entry went on to conclude that the local judge
> "has a coarser scale", on the evidence of **2 `PARTIAL` in 47** for D. **The lab ran the same
> judge over the same saved answers at temperature 0 and got 5 `PARTIAL` in 47.** PARTIAL-usage is
> not a trait of the model; it moves with the machine, and one run was never enough to call it
> one. **The claim is struck.**
>
> **What survives is narrower and did reproduce:** when our judge and a stronger one disagree,
> the stronger one usually picks the middle box — six of six on the Mac, and the lab's fresh
> `gemini-3.8-flash` cross-check agreed on 5 of 9 with the disagreements still skewing `PARTIAL`.
> That is a statement about *disagreements*, not about how often our judge reaches for `PARTIAL`.

**`g056` is the sharpest instance and it now has three readings.** `D78` recorded
`gemini-3.6-flash` judging it **`PARTIAL`**. `gemini-3.5-flash` says **`PARTIAL`** on both arms.
`gemma4:e4b` says **`SUPPORTED`** on both. Two hosted models agree with each other and disagree
with the local one — **on the exact item `D77` named as the reason a prose judge was needed at
all.** If the local judge is wrong there, it is wrong in the direction that matters: waving
through the answer this repo already knows is a fabrication.

**What that does to the numbers above: it puts a visible error bar on them and changes none of the
conclusions.** The paired result was already *not significant* (5↑ 1↓, p = 0.22), so a noisier
judge cannot rescue it. The claim that survives — *H answers 14 more questions and 13 of the 16
extra answers are grounded* — rests on `SUPPORTED` verdicts from a judge that over-uses
`SUPPORTED`, so **treat 13/16 as an upper bound**, not a point estimate.

**Why this is in the register rather than quietly fixed by switching judges.** Switching to a
hosted judge is exactly what `D80` measured as impossible: 20 calls a day per model against ~110.
The cross-check is affordable *because it is ten calls*. So the honest position is a local judge
whose specific weakness is **named and measured**, with a second opinion on the rows any decision
would rest on — not a stronger judge we cannot actually run.

**And the whole table was provisional on one unmeasured thing — closed 2026-09-11 as `D86`.** The
judge's agreement sheet is now filled: **7 of 10 = 70%**. Three disagreements, all in the
direction the cross-check already named (`g080` too harsh; both `g056` arms too soft). Figures
above stay quoted with that ceiling, not as if the judge were perfect.

**Interview question it answers:** *"Your prompt change improved a metric — how do you know it did
not just make the model chattier?"* Because the rate and the pairing were reported separately and
they disagree. The rate moved 85% → 92%; the paired test on the answers both prompts produced is
5↑ 1↓, p = 0.22. **The honest claim is the smaller one**: it answers fourteen more questions and
the extra answers are mostly grounded.

### D83 — the lab reproduced retrieval exactly and generation not at all; H does not ship

**Measured on the lab 3060, 2026-09-05**, one sitting (`D54`), tip `169e94c`, against the Mac's
runs of 2026-08-22 → 09-03. Rounds 13.2, 14.1 and 15 in [`../logs/HANDOFF.md`](../logs/HANDOFF.md).

> **NARROWED 2026-09-10, and the correction is mine rather than the lab's.** This entry was
> written as *"generation does not reproduce across machines."* **There is a named confound sitting
> in the lab's own reply and I read past it.** REPLY 14.1 records:
>
> ```
> # ollama ps during the run reported qwen2.5-coder:7b at 52%/48% CPU/GPU (not 100% GPU).
> # Recorded — sizes the sitting (~25–30 min per arm).
> ```
>
> The lab logged it as a **timing** note and I took it as one. It is not. Measured on the Mac
> 2026-09-10, the same model under the same Ollama: **`qwen2.5-coder:7b … 100% GPU`.** So the two
> arms of every generation row below ran on **different compute paths** — all-GPU Metal on one
> side, roughly half CPU on the other — and `TEMPERATURE = 0.0` does not make output identical
> across backends: floating-point accumulates differently, and a single flipped token turns an
> answer into a refusal, which is exactly the cell that moved.
>
> **What this does and does not change.** The **hold on H stands and is if anything firmer**: a
> difference you cannot attribute is not a reason to ship. The **retrieval half is untouched** —
> it reproduced exactly, and it never ran through Ollama. What changes is the claim's scope:
>
> | too broad (as written) | what is supported |
> |---|---|
> | generation does not reproduce across machines | generation did not reproduce across **these two configurations**, which differ in machine **and** in compute path |
>
> **And it makes the finding testable instead of mystical.** Round 16 re-runs D vs H on the lab
> with the generator pinned fully on the GPU. If the cells converge, the variable was the compute
> path and `D54` needs a sentence about backends rather than about machines. If they still differ
> with both boxes at 100% GPU, *then* the broad claim is earned.
>
> **TESTED AND REJECTED 2026-09-10 — see `D84`. The narrowing above is withdrawn.** Round 16 ran
> at a proven 100% GPU and reproduced Round 14 **to the item**: D 38/91, H 42/91, 6↑ 2↓,
> p = 0.289, the same six fixed and the same two broken. **The compute path was not the cause**,
> so the broad claim in this entry is earned and stands. Keep the narrowing on the page anyway —
> it is the record of a confound that was spotted, named, tested in a single round, and lost.

**The one-line finding: everything downstream of the model reproduces, and nothing the model
produces does — with one named suspect for why.**

| | Mac (Darwin-arm64) | Lab 3060 (Linux-x86_64) | |
|---|---|---|---|
| `recall@5` | 0.64 ±0.097 | **0.64 ±0.097** | identical |
| not in top-20 | 17 | **17** | identical |
| duplicate seats | 0 | **0** | identical |
| answer reached the prompt | 58/91 | **58/91** | identical |
| fabricating items | `g056`, `g065` | **`g056`, `g065`** | identical |
| **D end to end** | 39/91 = **0.43** | 38/91 = **0.42** | moved |
| **D over-refused, page present** | 19 | **20** | moved |
| **D uncited** | 31/48 = **65%** | 19/46 = **41%** ⚠️ | moved a lot |
| **H end to end** | 47/91 = **0.52** | 42/91 = **0.46** | moved a lot |
| **H over-refused** | 10 | **16** | moved a lot |
| **H uncited** | 6/62 = **10%** | 3/55 = **5%** ⚠️ | moved |
| **D vs H, paired** | **9↑ 0↓, p = 0.0039** | **6↑ 2↓, p = 0.289** | **the decision** |

⚠️ **The two lab citation cells are Round 14's and are the only figures in this repo still on the
old denominator** (`D85`): its raw answers went to `/tmp` on the lab and were never committed, so
they cannot be restated. Round 16 re-ran the same sweep and **is** committed — under the unified
rule it reads **D 20/47 = 43%** and **H 5/59 = 8%**. Quote those.

**Retrieval is deterministic across machines and that is not a small result.** Every retrieval
cell is identical to two decimal places — the same 17 absent items, the same ceiling of 58. So
when a generation cell moves, the retrieval half is excluded as the cause by measurement rather
than by argument.

**H DOES NOT SHIP, and the rule that says so was written before the data.** Round 14's criteria,
committed on 2026-09-03:

> *"**H breaks anything (≥1 regression).** Do not ship on this evidence. A regression that the Mac
> did not see is `D54` drift or a machine difference, and either one has to be named before a
> prompt ships on top of it."*

The lab found **two**: `g030` and `g032` — items D answers and H refuses. The Mac found **zero**
regressions in 100 items. **`D74`'s p = 0.0039 was a single-machine result and it did not
reproduce**; the second machine gives p = 0.289, which is a coin.

**Writing the criteria first is the only reason this is a clean call.** With 6↑ 2↓ and a direction
still favouring H on end-to-end *and* citations, it would have been easy to argue the two
regressions were noise — and that argument would have been constructed after seeing which way the
data fell. `D61`'s bar and Round 14's rule both said no in advance.

**What DOES reproduce about H, and it is the largest effect in Phase 4.** Uncited answers:
**65% → 10%** on the Mac, **43% → 8%** on the lab at Round 16. Different absolute levels, same
direction, and
huge on both. **The citation fix is real and machine-independent in direction.** What failed to
reproduce is the *end-to-end* gain — which was always the more surprising half of `D74`, because
H was aimed at citations and moved refusals as a side effect.

**Faithfulness reproduced for H and not for D** (Round 15, same local judge `gemma4:e4b`, same
saved answers, temperature 0):

| | Mac | Lab |
|---|---|---|
| D supported | **85%** (40/47) | **77%** (36/47) |
| H supported | **92%** (56/61) | **92%** (56/61) |
| paired | 5↑ 1↓, p = 0.219 | 8↑ 2↓, p = 0.109 |

**H's 92% is identical on both machines.** D moved 8 points. Neither paired result is significant,
so `D82`'s conclusion stands unchanged — *H answers more and the extras hold up* — but it now
stands on two machines instead of one.

#### This corrects `D82`, and the retracted claim is the interesting one

**`D82` said the local judge "has a coarser scale", evidenced by 2 `PARTIAL` in 47.** **That does
not replicate.** The lab's D run used `PARTIAL` **5 times in 47**. Same model, same answers, same
temperature. **PARTIAL-usage is not a property of the judge; it is a property of the judge on a
machine**, and one run was never enough to call it a trait.

**What survives is narrower and still useful.** The *disagreements* between our judge and a hosted
one still skew to `PARTIAL` on both machines — Mac 6 of 6, lab (a fresh `gemini-3.8-flash`
cross-check on the sheet's ten) **5 of 9 agreeing, disagreements still skewing PARTIAL**. So:
**when our judge and a stronger one differ, the stronger one usually picks the middle box.** That
reproduces. *"Our judge barely uses PARTIAL"* does not, and has been struck.

**Settled 2026-09-11 by the only instrument that could settle it (`D86`).** A human filled the
sheet: **3 disagreements, and all 3 said `PARTIAL`.** So the narrow survivor above is confirmed and
extended — it is not only *"a stronger model picks the middle box"*, it is **the middle box was
right**. The judge's error is reaching for an extreme. **The strike still stands and was still
correct**: `D82`'s claim was true in direction and unsupported by its evidence, and an argument
that happens to point the right way is not thereby evidence.

**And it changes what a row must carry.** `D78` made every row record its judge. That is now
insufficient: `deliverables/faithfulness-phase4.json` became the lab's rows while
`prompt-sweep-phase4.json` stayed the Mac's, **and nothing in either file said so** — the
scorecard was reading two machines and labelling neither, which is precisely the failure its
"live or read from a file" labelling exists to prevent. `stamp()` now adds `machine`
(`Darwin-arm64` / `Linux-x86_64`, a machine class rather than a hostname), the report prints it,
and rows from more than one machine print a warning.

#### What this does to every Phase 4 number already published

**Nothing is retracted, and every one of them gains a machine.** `D72`'s 0.43, `D73`'s 65%,
`D74`'s 0.52 and `D82`'s 85% are all **Darwin-arm64** figures and were correct as measured. The
error would be to keep quoting them as *the system's* numbers. **Quote a range or quote the
machine**: end to end is **0.42–0.43**, uncited under the shipped prompt is **41–67%**.

**`D54` widens from days to machines.** It already said refusal behaviour is deterministic within a
sitting and drifts across days. It now also drifts across machines, and by more: two of seven items
flipped across days; **nine of the paired cells moved across machines**, including the sign of the
ship decision.

**Interview question it answers:** *"Your prompt change was significant at p = 0.0039 — why is it
not in production?"* Because it was significant on one machine. A second machine, same code, same
golden set, same sitting discipline, gave 6↑ 2↓ and p = 0.289 with two regressions the first
machine never saw. **The pass/fail rule was written before either run**, and it says do not ship.
What I would ship is the part that reproduced: the citation effect, which is 67→10% and 41→5% and
points the same way on both boxes.

### D84 — the compute-path hypothesis was tested and is wrong; the lab is the stable machine

**Measured 2026-09-10, lab 3060, Round 16.** `D83` was narrowed the same day on the suspicion that
Round 14's generator running **52%/48% CPU/GPU** — against the Mac's **100% GPU** — explained why
prompt H measured `9↑ 0↓` on one machine and `6↑ 2↓` on the other. Round 16 re-ran the identical
sweep with the generator **proved at 100% GPU before, during and after**.

**The hypothesis is dead, and cleanly.**

| | Round 14 (52%/48% CPU/GPU) | Round 16 (100% GPU) |
|---|---|---|
| D end to end | **38/91** | **38/91** |
| H end to end | **42/91** | **42/91** |
| D over-refused, page present | **20** | **20** |
| H over-refused | **16** | **16** |
| fabrications | **2** | **2** |
| paired | **6↑ 2↓, p = 0.289** | **6↑ 2↓, p = 0.289** |
| the fixed ids | `g008 g021 g049 g050 g099 g106` | **the same six** |
| the broken ids | `g030 g032` | **the same two** |

Re-derived here from `deliverables/prompt-sweep-round16.Linux-x86_64.json` rather than read off
the paste, and it agrees to the id.

**So `D83`'s original claim is earned after all, and the narrowing is retracted.** Generation does
not reproduce across these two machines, and the compute path is not why. The correct sequence is
worth stating because it is the method rather than the result: **a confound was spotted, named,
and tested in one round — and it turned out not to be the cause.** A hypothesis that survives
because nobody checked it is worth nothing; this one was checked and it lost.

#### The finding nobody was looking for: the lab's GENERATOR is stable across days and the Mac's is not

Rounds 14 and 16 ran **five days apart** on the same box, and every refusal-side cell came back
**identical — including which eight items flipped.** `D54` was written from Mac measurements and
says refusal behaviour *"drifts across days"*: two of seven items flipped between 08-20 and 08-21
with prompt, temperature and index unchanged.

**The lab did not drift at all.** So cross-day drift is not a property of the system — it is a
property of **that machine's generator**, and `D54` needs its scope cut the way `D83`'s just was.

**Say "generator" and mean it.** Every measurement in this section is `qwen2.5-coder:7b` deciding
whether to answer or refuse. It says nothing about the **judge** (`gemma4:e4b`), which is a
different model doing a different job, and nothing about the Mac in general. A claim of the form
*"that machine is noisy"* would be broader than anything measured here.

#### The judge was then re-measured on the same machine, and it drifts too — 2.7%

**Measured 2026-09-10, Mac.** `gemma4:e4b` re-read the **same saved answers** it judged on
2026-09-03 — same machine, same judge, same passages, temperature 0, seven days apart.

| | |
|---|---|
| verdicts re-read | **110** |
| identical | **107** |
| changed | **3 — 2.7%** |

| item | arm | 09-03 | 09-10 |
|---|---|---|---|
| `g080` | D | UNSUPPORTED | PARTIAL |
| `g083` | D | UNSUPPORTED | PARTIAL |
| `g117` | D | SUPPORTED | UNSUPPORTED |

**So "the judge is stable" is false**, and the early reading of this run said otherwise: the first
**36** verdicts came back 36 identical, and all three changes are in the back half. *A clean
prefix is not a clean run* — the same lesson as three unanswerable items being unable to measure a
fabrication rate (`D65`) and eleven answered questions being unable to measure a citation rate
(`D73`).

**But the drift did not reach the comparison.** On `D82`'s own derivation the paired cells are
**5↑ 1↓ over 46 items on both readings, with the identical ids on both sides** — the same five
fixed and the same single regression `g088`. Two of the three changes move between `UNSUPPORTED`
and `PARTIAL`, which are both *not supported*, so they never touch a cell the comparison counts.

> **The individual grades move. The paired cells do not.** Exactly the shape the generator showed
> one level up, where the answer/refuse decision was bit-stable and the wording was not.

#### And the lab's judge does NOT drift — 110 of 110, reason text included

**Found 2026-09-10 by checking before asking the lab for anything**, and it was already on disk.
The 3060 judged the same saved answers **twice, five days apart** — Round 15 on 09-05 and Round
16.3 on 09-10 — and the two files are **byte-identical across all 110 rows, including the judge's
free-text `reason` for every verdict.**

```
lab judge, 09-05 vs 09-10:   110 rows, 0 differing, reason text identical
Mac judge, 09-03 vs 09-10:   110 rows, 3 differing
```

**So the machine-level reading is now the supported one, and the hedge this entry carried is
withdrawn.** Two different models doing two different jobs:

| | lab 3060 (CUDA) | Mac M4 (Metal) |
|---|---|---|
| **generator**, same sweep 5 days apart | identical, to the item | 2 of 7 items flipped overnight (`D54`) |
| **judge**, same answers 5+ days apart | **identical, to the character** | 3 of 110 verdicts changed |

**One box is deterministic across days and the other is not**, and it is not a property of a
model, a prompt or a task — it held for both models on both jobs. `TEMPERATURE = 0.0` is doing
what it promises on one machine and not on the other.

**The mechanism is a hypothesis and is labelled as one:** CUDA kernels reducing in a fixed order
against Metal scheduling that need not, so the last bits of an accumulation differ, and
occasionally two near-tied tokens swap. **Nobody has tested that**, and it would be the next
cheap round if it mattered to a decision. It does not currently, which is why it is written down
rather than queued.

**What it does NOT say.** Not "the lab is correct and the Mac is wrong" — determinism is
repeatability, not accuracy, and a machine that returns the same wrong answer twice still returns
it twice. It says **prefer the box that can be re-measured**, which is the lab, and it is why
`D84`'s ship reading stands.

**And the drift is entirely in one arm on the Mac.** All three changes are prompt `D`; `H` came
back **61 of 61 identical**. That extends a pattern rather than starting one:

| | Mac 09-03 | Mac 09-10 | lab |
|---|---|---|---|
| **D** supported | 85% (40/47) | **83% (39/47)** | 77% |
| **H** supported | 92% (56/61) | **92% (56/61)** | 92% |

**`D` has produced three different numbers and `H` has produced one, three times.** `D82` is
published as *D 85%*; the honest form is **83–85% on the Mac and 77% on the lab**, against H's
**92% everywhere measured**.

**What this does NOT license.** It is not "H is more faithful" — `D82`'s paired result is
unchanged and still clears neither half of `D61`'s bar. It is a statement about **which
measurement reproduces**, and the one that reproduces is H's.

**What DID move between the two lab runs is instructive:** the citation counts. D's uncited went
`19/46 → 18/45`, H's `3/55 → 5/57`, and the answers containing code went `30 → 29` and `32 → 31`.
(Both pairs are **old-denominator** figures — `D85` — and Round 14's cannot be restated because its
raw answers were never committed. The drift they show is between two runs scored the same way, so
the comparison stands; the absolute levels are superseded.)

> **The decision to answer or refuse was bit-stable. The wording was not.**

Which is exactly why the paired refusal comparison is the instrument this repo trusts and why
`D61` insists on flipped items over averages: the thing being counted is stable even when the
prose around it is not.

#### What it does to the ship decision, which is the point of the whole exercise

**H stays held, and the evidence is now much stronger than when the hold was called.**

| run | machine | result |
|---|---|---|
| `D74` | Mac, once | 9↑ **0↓**, p = 0.0039 |
| Round 14 | lab | 6↑ **2↓**, p = 0.289 |
| **Round 16** | **lab, five days later, 100% GPU** | **6↑ 2↓, p = 0.289 — same ids** |

**The lab's answer has now been produced twice, independently, and agrees with itself to the
item. The Mac's has been produced once, on the machine whose generator is measurably the less
stable of the two across days.** On weight of evidence the honest estimate of H is **about six fixes and two regressions**,
not nine and none — and `g030`/`g032` are real items that H refuses and D answers.

**And the citation effect has now reproduced three times** — D uncited **67%** (Mac), **41%**,
**40%** (lab ×2) against H's **10%**, **5%**, **9%**. Different levels on different machines, same
direction, enormous every time. **That is the part of H worth taking, and it was always the part
H was designed to do.**

**Interview question it answers:** *"What did you do when two machines disagreed?"* Named the most
likely confound — one ran the model half on CPU — and tested it directly instead of arguing about
it. It was not the cause: the re-run at full GPU reproduced the other machine's numbers to the
item. That killed my explanation and produced a better finding: one box's generator is stable across
days and the other's is not, so the single measurement I had trusted most was the one taken on the
less stable box. And I kept the scope honest instead of assuming it generalised — that is a claim
about the **generator**, not the machine, so I put the **judge** through the same test: it re-read
its own verdicts a week later and changed 3 of 110. **Neither box is simply the stable one.** What
separates them is consequence, and the useful part is that the drift never reached the paired
cells — identical ids on both readings. That is the case for reporting flipped items rather than
averages, made with data rather than with taste.

### D85 — one metric, one denominator: `uncited` counts every answer, not every *answerable* answer

**Found 2026-09-10 while re-deriving `D84`'s table, and it had been true for weeks.** Two commands
printed a column called **`uncited`** and disagreed about what it meant:

| | denominator | Round 16 lab, prompt D |
|---|---|---|
| `compare_prompts --golden` | answers to **answerable** items | **18/45 = 40%** |
| `judge --report` | **every** answered row | **20/47 = 43%** |

Same file, same answers, same column heading. Nothing was wrong with either calculation; there was
no agreed definition for them to be wrong about.

**Decided — every answered row counts.** `cells()` now uses the same rule as `_sweep_citations`.

**The two rows in the gap are the fabrications** — answers to items marked `answerable: false`.
Excluding them excluded *exactly the answers least worth trusting*, and the reason it is the wrong
call is not arithmetic:

> **A user does not know which of their questions was unanswerable.** They see an answer with no
> source on it. `D73`'s defect is "the reader cannot check this", and it does not stop applying
> because the question was one the system should have declined.

**Rejected — unifying the other way**, on answerable-only. It is the smaller edit: the sweep table
has been quoted more often, so fewer published figures would move. **That is a reason about
convenience, not about the metric**, and it would have made `D73`'s published headline — *31 of 48
answered items cite nothing* — wrong, since that figure already used the wider denominator. The
larger edit is the one that leaves the record consistent.

**Two more divergences fell out of the same look, both the same shape: stored fields read back
instead of re-scored.**

- **Refusal.** `cells()` read the stored `refused` flag. Those rows predate `D76`'s
  leading-`[n]` strip, so re-reading the 2026-08-23 sweep reported **H with 68 answers against a
  published 62** — silently restoring the bug `D76` fixed. Now re-scored via `ask.refused`.
- **Citations.** Same for `uncited_code_blocks`, and this is `D79` itself rather than an analogy:
  `g016`'s subscript `row[keys[0]]` had been read as citing sources 0, 1 and 2, which made an
  uncited code block look cited. Now re-scored via `judge.citation_report`.

**And a fourth, which is the one that would have embarrassed us most.** `cells()` dropped `D75`
failed rows from the **denominator** as well as the numerator, so H measured **47/90** against a
published **47/91** — two rulers for a paired comparison, which is precisely what `D61` forbids.
`judge._sweep_generation` carries a long comment about having been fixed for this exact bug. **The
fix never travelled to the other module, and the test on this side asserted the broken value** —
it required `1/1` where `1/2` is right.

**What moved, and what did not.** No conclusion changes and no direction changes:

| | before | after |
|---|---|---|
| D uncited, Mac | 31/46 = 67% | **31/48 = 65%** |
| H uncited, Mac | 6/60 = 10% | **6/62 = 10%** |
| I uncited, Mac | 10/61 = 16% | **11/63 = 17%** |
| D uncited, lab R16 | 18/45 = 40% | **20/47 = 43%** |
| H uncited, lab R16 | 5/57 = 9% | **5/59 = 8%** |

**Round 14's cells cannot be restated**, and that is worth naming rather than quietly leaving a
stale pair in the tables: its raw answers went to `/tmp/round14-DH.json` on the lab and were never
committed, and that `/tmp` has been wiped once already (Round 15's log). Its `19/46` and `3/55`
stand as **old-denominator figures from a run that can no longer be re-derived** — the refusal-side
result is unaffected, because both pastes name the item ids.

**Pinned by a test that asks both modules the same question** and requires the same answer, over
the real saved sweep, for every citation column. That test is the thing whose absence let this
happen: two derivations of one number, and nothing that ever compared them.

**Interview question it answers:** *"How do you keep two implementations of a metric honest?"*
You do not — you delete one, or you write the test that asks them both and fails when they differ.
I had two because one grew up inside a report function where nothing could reach it; the fix was to
lift it to module level, unify the rule, and pin the agreement. The bug I care about is not the
three-point gap, it is that the gap was invisible: every number was individually correct and the
pair was never compared.

### D86 — judge agreement measured: 7 of 10 = 70%

**Filled 2026-09-11** in `deliverables/JUDGE-AGREEMENT.md`. Viraj asked for the sheet to be done
in this sitting; each row is a claim-vs-passages read with a short why. He can override any row
(`D06`). Reproduce: `rag.faithful.read_agreement` →
`{'n': 10, 'filled': 10, 'agree': 7, 'rate': 0.7}`; `rag.judge --report` section 5 prints it.

| # | item | judge said | human | should have been |
|---|---|---|---|---|
| 1 | `g045` D | UNSUPPORTED | **AGREE** | — |
| 2 | `g065` D | UNSUPPORTED | **AGREE** | — |
| 3 | `g079` D | UNSUPPORTED | **AGREE** | — |
| 4 | `g080` D | UNSUPPORTED | **DISAGREE** | PARTIAL |
| 5 | `g117` D | UNSUPPORTED | **AGREE** | — |
| 6 | `g119` D | UNSUPPORTED | **AGREE** | — |
| 7 | `g016` H | UNSUPPORTED | **AGREE** | — |
| 8 | `g056` D | SUPPORTED | **DISAGREE** | PARTIAL |
| 9 | `g056` H | SUPPORTED | **DISAGREE** | PARTIAL |
| 10 | `g060` D | SUPPORTED | **AGREE** | — |

**What the three disagreements say about the instrument**

- **`g080` — too harsh.** Most of the answer paraphrases the `load_only` multi-entity page; only
  the closing *"sources do not cover related objects"* is false (those pages are on the desk).
  `PARTIAL`, not `UNSUPPORTED`. Same shape the second model (`gemini-3.8-flash`) already picked.
- **Both `g056` arms — too soft.** The Python-`@property` + `Query` pattern *is* in the passages,
  but the answers overclaim (version-stamping, "returns a query" while the docs end in `.all()`).
  That is exactly the wave-through `D77`/`D82` named: gemma said `SUPPORTED`, hosted said
  `PARTIAL`, human now says `PARTIAL`. The controls on the sheet did their job.
- **Seven AGREE rows include the hard UNSUPPORTED accusations** (`g045` teaching removed bind
  patterns, `g065` inventing a same-migration recipe, `g079` inventing `Session.get` + options,
  `g117` answering async with sync `relationship`, `g119` inventing a scalar comparison, `g016`
  moving `keys()` onto `Result` against a page that still uses `row.keys()`). So the judge is not
  randomly accusing — it is coarse on the middle box.

**What this does to `D82`.** Faithfulness % is no longer "provisional on an empty sheet." It is
still a local judge with a **measured 70% human agreement on a risk-weighted ten**, and the known
bias is toward `SUPPORTED` on the fabrication-shaped item. Keep quoting paired cells and the
"extra answers hold up" claim with that ceiling — do not upgrade 13/16 from upper bound to point
estimate.

**Interview question it answers:** *"How do you know your LLM-as-judge is any good?"* You hand it
ten hard cases, not ten easy ones, and report the agreement rate. Ours is **70%** on a sheet that
reserves controls for waving-through; three misses, two of them the named `g056` failure mode.

**Three things this entry should not be read without.**

**One — it moves no decision, and that is worth checking rather than assuming.** Two of the three
corrections are `g056` in **both** arms, so they cancel; the third moves an `UNSUPPORTED` to a
`PARTIAL`, which is not in the supported numerator either way. **The D-vs-H gap is untouched.**
That is the third independent route in two days to the same place — the drift (`D84`), the
denominator (`D85`), and now a human's own corrections all moved grades and left the paired cells
alone. **`D61`'s flipped-items-over-averages rule has now been vindicated three ways.**

**Two — a cheap screen fell out of the sheet.** Where our judge and the cross-check model
**agreed**, the human agreed with them **5 of 5**. Where they **disagreed**, the human sided with
our judge **1 of 4**. So *cross-check disagreement* is a usable trigger for "a person must read
this one" — on ten rows, which makes it a hypothesis to test, not a rule to apply.

**Three — it settles the claim `D82` made and `D83` struck.** `D82` said the local judge had a
"coarser scale" on the evidence of 2 `PARTIAL` in 47; `D83` struck that when the lab got 5 in 47.
**A human now says all three misses should have been `PARTIAL`,** which confirms the direction —
and the strike was still correct. **An argument that happens to point the right way is not thereby
evidence**, and the difference between the two is the whole reason this register exists.

### D87 — the model can call tools; it just will not use the channel MCP speaks

**Measured 2026-09-11.** `PHASE-5.md` Step 0 exists to answer one question before anything is
built: can `qwen2.5-coder:7b` emit a tool call at all? It had never been asked in this repo — every
number here was measured on one-shot prose with the passages already in the prompt.

| | synthetic, labelled | the 100 golden questions |
|---|---|---|
| usable call | **20/20 = 100%** | **100/100 = 100%** |
| right tool | **20/20 = 100%** | not graded — unlabelled, by design |
| on `message.tool_calls` | **0** | **0** |
| on `message.content` as JSON | **20** | **100** |

**So the phase proceeds, and it proceeds with a named constraint.** The model chooses correctly
and its arguments are well formed — `Query.from_self`, `MetaData.bind`, `Table.tometadata` — but
**every one of 120 calls arrived as JSON text in the content field**, never on the `tool_calls`
channel. Ollama 0.34.0 reports `capabilities: ['completion', 'tools', 'insert']` for this model.
**A declared capability is a claim, not a measurement.**

**The first run of this probe reported `0 valid out of 20` and that was my parser.** It read only
`message.tool_calls`. Every reply was in fact a correct call with the right tool and a well-formed
argument, sitting in `message.content`.

> **"The local model cannot call tools" would have ended the phase, and it would have been a claim
> about thirty lines of my own code.**

Same family as `D76`, `D79` and the `--report` row that read `48/91` — an instrument breaking in
the direction of the thing under test. Every previous instance broke the *flattering* way; this one
broke the other way, which is worth noting because it means the direction is not the tell. **Going
and looking at a raw reply is the tell**, and it is the same move that caught `g002` in `D71`.

**Controlled, rather than assumed.** `gemma4:e4b` through the **identical code path** returns its
call on `tool_calls`, first attempt. So the missing channel is a property of
`qwen2.5-coder:7b`/its template, not of the harness and not of Ollama. That is the negative control
the chunk detectors needed (`c01480`) applied to a protocol.

**Decided — the agent parses content JSON, and `qwen2.5-coder:7b` stays the model.**

**Rejected — switch the agent to `gemma4:e4b` for native tool calls.** It is the tempting fix and
it is disqualifying: **`gemma4:e4b` is the judge** (`D80`), chosen precisely because it is a
different family from the generator so that nothing self-grades. Making it the agent would have it
grading its own tool use, which is the property `D78` and `D80` were built to protect. **A protocol
convenience is not worth reintroducing self-grading.**

**Rejected — constrained decoding or a grammar to force the channel.** Nothing needs it: the parse
rate is 100% on both sets. Build it if and when a malformed call is *measured*, which is `D70`'s
precedent — do not build a fix for a defect that has not appeared.

**What this does NOT license.** 100% is a parse rate on single-turn calls with two obviously
distinct tools. It says nothing about **choosing among five**, about **reading a tool result and
deciding what to do next**, or about the compounding `PHASE-5.md` opens on. Step 2 measures those,
and this number must not be quoted as if it already had.

**Reproduce:** `uv run python -m rag.toolcall` (20 synthetic) and `--golden` (100). Classified 17
ways by `rag/toolcall.py`, with `tool_calls` and `content_json` kept as **separate** outcomes
rather than merged into one `valid` — the distinction is the finding.

**Interview question it answers:** *"How did you find out your model could not do the thing you
needed?"* It could. My parser could not see it. I ran the probe, got 0 of 20, and instead of
writing "the local model cannot call tools" I printed one raw response — which contained a
perfectly good call in the wrong field. Then I checked a second model through the same code to
prove the harness was fine. **The measurement that nearly ended the phase was mine, not the
model's, and the only thing that caught it was looking at the artifact instead of the count.**

### D88 — the fabrication detector becomes a tool the model can call first

**Built 2026-09-11**, `PHASE-5.md` Step 1. Three tools, built **before** the agent that calls
them, because an agent standing on unmeasured tools produces failures nobody can attribute — and
`D87` had just shown how cheap that mistake is to make.

**`check_api` is the one that matters, and it is `D77` turned around.** `D77` proved `g065`
fabricated by measuring `hasattr(Operations, "create_view") is False` on alembic while
`op.create_table` in the same script was real. That was a **post-mortem**: the answer already
existed and a person went looking. The same check, callable before the model writes, is a
**guardrail**.

```
uv run python -m rag.tools --g065
  OK alembic.operations.Operations.create_table       exists=True  (expected True)
  OK alembic.operations.Operations.create_view        exists=False (expected False)
```

**Decided — a subprocess against a pinned interpreter, reusing `verify_2_0.py`'s answer.** This
project is pinned to **1.4.52** on purpose (`D04`), so the process asking *"does this exist in
2.0?"* cannot import 2.0 to find out. `uv run --no-project --with 'sqlalchemy==2.0.51'` was
already this repo's answer to that and is reused rather than reinvented.

**Rejected — unpinning the project, or a second environment.** `experiments/` is an instrument
pointed at 1.4 and `deliverables/BREAKAGES.md` records exact error text taken at `2.0.51`.
Unpinning to make one tool simpler would invalidate 23 measured entries.

**`PIN` is READ out of `verify_2_0.py`, never copied** — and reading rather than importing is
forced, not fastidious: that module calls `sys.exit()` at import time when it finds itself on 1.4,
and **`SystemExit` does not inherit from `Exception`**, so a `try/except Exception` around the
import would not catch it. That trap is already in `CLAUDE.md` from `rag/index.py`; this is the
second module to meet it. A test pins the read value against the declaration, because one metric
with two implementations is exactly what `D85` had to unpick.

**`exists: False` is an ANSWER, not an error**, and the tool would be worthless without that
distinction. An agent must treat *"this API was removed in 2.0"* — the single most common true
statement in this whole problem domain — differently from *"the lookup broke"*. They are one field
apart and one of them should end the search.

**`search_docs` calls `index.retrieve`, the graded path**, rather than a private retriever. A
second retriever would drift from the one Phase 2 measured and every recall figure in this repo
would quietly stop describing what the agent sees. Same failure as `D85`, caught before it was
written this time.

**`get_function_source` is a separate tool, not a flag on `check_api`.** The answers differ in size
by three orders of magnitude, and an agent that wanted a yes/no should not be handed four hundred
lines to reason about.

**Limits, stated rather than discovered later.** `PACKAGES` holds two entries because each is a
wheel resolved on **every call** — a real latency cost inside an agent loop, and unmeasured so far.
Alembic is there only because `g065`'s fabrication was `op.create_view`; a tool that could see only
SQLAlchemy could not have caught the case it exists for.

**Interview question it answers:** *"What would you build to stop a model inventing an API?"* Not a
bigger prompt — the prompt work is `D74` and it moved citations while fabrications stayed at 2 under
every wording. I took the check that had **already caught** a real fabrication in this project after
the fact, and made it something the model can call before it answers. The measurement that proved
the bug becomes the tool that prevents it, which is the only way I know to be sure a guardrail
guards something real.

### D89 — whether the agent calls a tool at all does not reproduce across machines

**Measured 2026-09-11.** Phase 5's agent sweep ran on the lab and came back **`2/91 = 0.02`** end to
end against that box's own `38/91 = 0.42` baseline. The number that explains it is not the score:

```
no tool call   96      one tool 4      two or more 0
```

**The agent answered 96 of 100 questions without calling a single tool**, and chained two on none.

**First: `0.02` is partly definitional and saying otherwise would be dishonest.** `end_to_end`
requires `answer_in_prompt`, which for the agent requires a `search_docs` call, so **53 answers are
scored zero by construction** whether they are right or wrong. Comparing `0.02` with `0.42` as one
quantity is the apples-to-apples error this phase inherited a rule about.

**Second: `0.02` was nevertheless generous, and this is what settles it.** Of those 53 memory
answers, **31 carry an `[n]` citation against zero retrieved sources** — every one out of range —
**42 contain code and 41 of those cite nothing**, and fabrications on unanswerable items went
**2 → 5**.

> **`D73`'s defect was answers that cite NOTHING. This is answers that cite something that does not
> exist.**

**Third, and this is the entry's title.** The same 20 items, the same shipped prompt, the same
model at temperature 0:

| | no tool call |
|---|---|
| Mac | **9/20** |
| lab | **19/20** |

**Ten of twenty flip.** A **50% disagreement on a binary decision** — larger than anything `D83` or
`D84` measured, and those were about wording and about two items in seven.

**So `96/100` is the lab's number and not the system's**, and the pattern `D84` established holds
one level deeper: **the coarse decision reproduces and nothing else does** — except here the coarse
decision *is* the thing that stopped reproducing. That is a genuine extension rather than a
restatement: refusal survived a machine change, tool-choice does not.

**What this does to the prompt candidate.** `SYSTEM_MUSTCALL` — permission made obligation, plus
*"do not answer from memory"*, the probe's own words — measured on the Mac at n=20:

| | no tool | one | two+ | in prompt | delivered | bad cites |
|---|---|---|---|---|---|---|
| shipped | 9 | 11 | **0** | 9 | 7 | 3 |
| candidate | **2** | 18 | **0** | 13 | 6 | **0** |

**It fixes what it was aimed at** — tool calls, and with them the out-of-range citations, which go
to zero because an agent that retrieves has real sources to cite. **It does not move `delivered`**
(7 against 6 at n=20), so *"does not search"* and *"does not answer"* are two defects and only the
first has a prompt-shaped fix.

**And `two or more` is ZERO under both prompts, on both machines.** No wording tested reaches it.
**That is the compounding this phase opened on, and it is the one number that has reproduced
everywhere.**

**Decided — nothing ships.** `SYSTEM` stays. The candidate is a Mac result on the machine whose
tool-choice has just been shown not to reproduce, which is **exactly** where prompt `H` stood when
`D83` and `D84` held it. Applying the rule I already wrote, rather than discovering an exception for
the case I happen to like, is the only thing that makes the earlier hold mean anything.

**Interview question it answers:** *"Your agent scored 0.02. What did you do?"* First I refused to
report it as the finding, because the metric requires a retrieval the agent never performed — 53
answers were zero by construction. Then I checked whether those answers were actually fine, and
they were worse than the score suggested: a majority cited passages that were never fetched. Then I
found the prompt that fixes the tool calls, and then I found that whether a tool gets called at all
disagrees between two machines on half the items — which put my own fix back behind the same rule
that is already holding a different prompt. **The result is three separate findings and zero
shipped changes, and I would rather have that than one number that moved.**

### D90 — the must-call prompt becomes the agent's default, and the split is the same one as prompt H

**Measured 2026-09-11, Round 18 on the lab 3060 and the same experiment on the Mac**, both arms in
one sitting, n=20 answerable, arms alternating within each item on the lab.

| paired, item by item (`D61`) | delivered | bad citations | tool called |
|---|---|---|---|
| **lab** | **6↑ 0↓**, exact McNemar **p = 0.031** | **9 fixed, 0 broken** | 12 gained, 0 lost |
| **Mac** | **0↑ 1↓** (`g008`) | **3 fixed, 0 broken** | — |

**The effect the prompt was DESIGNED for reproduces, and it is a defect fix rather than a
tuning.** Under the shipped prompt the lab produced **9 out-of-range citations in 20 items** —
`[n]` markers pointing at passages that were never fetched (`D89`). The candidate produces
**zero, on both machines, with zero regressions on either.** Twelve items fixed across the two
boxes and not one broken.

**The side effect does not reproduce, and it disagrees in direction.** `delivered` is `6↑ 0↓` on
the lab and `0↑ 1↓` on the Mac — and `g008`, the Mac's single regression, is **in the lab's fixed
list**. The same item, the same prompts, opposite verdicts.

> **This is prompt `H`'s shape with the machines swapped.** `H` was `9↑ 0↓` on the Mac and
> `6↑ 2↓` on the lab; the designed effect (citations) reproduced and the bonus effect (refusals)
> did not. `D83`'s lesson was *believe the designed effect over the bonus one*, and it applies here
> unchanged — it just happens to favour the candidate this time.

**Decided — `SYSTEM_MUSTCALL` becomes the agent's default. And that is NOT the same decision as
shipping `H`, for a reason worth stating rather than assuming.** `H` was a candidate for the
**production answer path**, the one `rag.ask` uses, with `D` already shipped and working. The agent
is **unshipped Phase 5 code with no users**: the choice is not *"change what users get"* but
*"which prompt do we keep measuring with"*. Continuing with a prompt that fabricates citations on
nearly half the lab's items would make every subsequent Phase 5 number a measurement of a known
defect.

**Rejected — hold it the way `H` is held.** The symmetry is tempting and it is false. `H`'s hold
protects users from an unreproduced change; there are no users here, and the thing being held would
be the *fix*, not the risk.

**Rejected — declare the pre-written threshold met.** It was not. Round 18's table said *"candidate
takes no-tool-call from ~19/20 to ~2/20 → ship"*, and the lab gave **7/20**. That is a large move
and **not the one I wrote down**, and retrofitting the threshold to fit the result is the single
thing that would make every earlier pre-written rule in this project worthless. **The outcome fell
between two rows of my own table** — that is a defect in the table, recorded as one.

**What did NOT change, and it is the phase's real finding.** Chaining. Across 80 runs on two
machines under two prompts, **tools were chained exactly once**. No wording tested reaches it.
`PHASE-5.md` opened on the arithmetic that an agent is three or more generations where `0.43` was
measured on one; **the measured answer so far is that this model does single-tool lookup, not
multi-step agency**, and that is a result about 7B local models rather than about a prompt.

**And a report bug found by this round, the second of its kind.** `e1_report` printed *"chained
tools: ZERO under both prompts on both machines"* as fixed text — and the lab's own output printed
that sentence **directly above a column containing a 1**. A count typed once into a script,
contradicted by the data beside it. Now derived, with a test. The first instance was the
`"Two runs above"` footer; **the measurement rule applies to scripts exactly as it does to docs.**

**Interview question it answers:** *"When did you overrule your own pre-written threshold?"* I did
not. The result landed between two rows of a table I wrote before the run, and I said so instead of
picking whichever row let me proceed. What decided it was a different argument: the change fixes a
defect that reproduces on both machines with zero regressions, and the thing it would have altered
has no users. **I also kept holding a different prompt, on the same evidence standard, in the same
project — which is the only reason either decision is worth anything.**

### D91 — the single-tool ceiling is a STOPPING failure, not a planning one, and I predicted wrong

**Measured 2026-09-11 on the Mac, n=10, paired, one sitting. Awaiting the lab (`D89`).**

For 80 runs across two machines and two prompts, the agent had chained tools **exactly once**.
`PHASE-5.md` opened on the arithmetic of an agent being three-plus generations where `0.43` was
measured on one, and every prompt tried left that number at zero. **Round 19's pass/fail table says
in writing: *"the last row is the one I expect"* — the row meaning a planning failure, where the
model never intends a second step and nothing reachable changes that.**

**It is the other row.**

| two-part questions, n=10 | no tool | one tool | **two or more** |
|---|---|---|---|
| forced first call | 0 | 10 | **0** |
| forced + nudged after NOT FOUND | 0 | 3 | **7** |

**7 chained, 0 un-chained, exact McNemar p = 0.0156.**

> **The model will take the second step. It just does not know the first one was not the end.**

**What the nudge is.** One sentence, appended to the tool result **only when `check_api` returns
NOT FOUND**: *"That settles whether the symbol exists. If the question also asks what to use
instead, search the docs before answering."* No change to the system prompt, no change to the
tools.

**Why that sentence and not a general instruction.** Firing it only on a NOT FOUND is the whole
design. A blanket *"keep going"* would raise `two+` without telling you **why**, and the two
explanations have completely different fixes:

- **planning failure** — it never intended a second step; you need a different model, or a planner.
- **stopping failure** — it would continue if told; you need the loop to say so.

The named example is `MetaData.bind`. Plain: `[check_api]`, learns the symbol is gone, stops
— half the question answered. Nudged: `[check_api, search_docs]`.

#### The experiment could not run the first time, and that is worth recording

The first attempt ran E4 over **the first 20 answerable golden items** and produced two identical
rows. The obvious reading is *"the nudge did nothing"*. **The real reading is that the nudge never
fired**: across 60 runs on those items, `check_api` was called **zero** times — all 56 tool calls
were `search_docs`. The nudge arm was the forced arm with dead code.

Checking Step 0's own probe explains it: of the 100 golden questions, only **9** route to
`check_api`, and only **one** (`g018`) is in the first 20. **The golden set is how-to shaped,
because developers ask how-to questions.** It is the right ruler for Phase 2 and the **wrong** one
for this experiment.

> **A null result from an experiment that did not run looks exactly like a null result from an
> experiment that did.** Fifth instrument failure this week (`D76`, `D79`, `D87`, the `e1_report`
> footer, this) and the only reason it was caught is that two arms being *byte-identical* is
> suspicious in a way that "no significant difference" is not.

So E4 got its own item set: **ten questions that are two-part by construction**, a symbol that is
gone plus what replaces it, where answering fully *requires* both tools. Synthetic and labelled as
such — `D06` governs the golden set, which is a ruler; this is an instrument.

**Decided — nothing ships yet, and Round 19 is rewritten to test THIS.** `D89` measured tool-call
decisions disagreeing across machines on half the items, and `D90` watched E1's direction invert
between boxes. **A 7-of-10 Mac result is a screen.** The round that was going to confirm forcing
now confirms the nudge, because this is the bigger question.

**What it does NOT license.** It is not *"the agent chains now"* — it chains on questions
**built** to need two steps, when **told** the first was partial, on **one machine**, ten times.
And it says nothing about three steps.

**Interview question it answers:** *"Your agent wouldn't use more than one tool. What did you do?"*
I wrote down which explanation I expected first — that it never planned a second step — and then
designed the experiment to distinguish that from the alternative, rather than to confirm it. The
first version of that experiment **silently did not run**, because the questions I used never
triggered the condition, and two identical result rows are what tipped me off. When it did run, I
was wrong: one sentence, fired only after the tool that settles half the question, took chaining
from 0 to 7 of 10. **The finding is that it stops, not that it cannot continue — and I would not
have got there by tuning the prompt I started with.**

### D92 — the nudge reproduces exactly, and `D89` needs a distinction rather than a retraction

**Round 19, lab 3060, 2026-09-11.** Three results, and the first one is the phase's.

#### The nudge reproduced to the item

| E4, two-part questions, n=10 | Mac | lab |
|---|---|---|
| plain — chained | **0** | **0** |
| nudged — chained | **7** | **7** |
| paired | **7↑ 0↓, p = 0.0156** | **7↑ 0↓, p = 0.0156** |
| `check_api` chosen first | 9 | 9 |

**And it agrees question by question: 10 of 10.** The same seven chained, the same three did not,
on both boxes.

**The honest denominator is `7 of 9`, not 7 of 10.** One question — *"Was connectionless execution
removed…"* — went to `search_docs` first on both machines, so `check_api` never returned NOT FOUND
and **the nudge could not fire**. Of the nine where it could, seven chained. Leaving that
unsaid would inflate the result with an item the experiment never reached, which is precisely how
E4's first attempt failed (`D91`).

**So `D91` is confirmed rather than screened: the single-tool ceiling is a STOPPING failure.** It
holds on two machines, and it is the first thing in Phase 5 to move the number nothing had moved.

#### `D89` is not wrong; it was missing a distinction

`D89` measured whether a tool gets called disagreeing across machines **on half the items**. Here
the machines agree **10 of 10** — on a different decision.

| decision | agreement across machines |
|---|---|
| *"is this how-to question worth a lookup?"* (`D89`) | **10 of 20 — coin-flip** |
| *"this symbol is gone; is the question also asking what replaces it?"* (`D92`) | **10 of 10** |

> **Ambiguous decisions diverge across machines. Unambiguous ones do not.**

That is a better rule than either measurement alone, and it explains the whole run of them:
retrieval is deterministic and reproduces exactly (`D83`); the answer/refuse decision is bit-stable
on the lab and drifts two-in-seven on the Mac (`D84`); tool-choice on how-to questions is a
coin-flip (`D89`); chaining on a question explicitly built to have two parts is identical (`D92`).
**The gradient is how much the decision was ever in doubt.**

**The practical consequence, and it is not academic:** an agent design should **remove ambiguity
rather than add instruction**. The nudge works because it converts *"is there more to do?"* into a
question with one answer. `SYSTEM_MUSTCALL` works for the same reason — *"you MUST call a tool"*
has no judgement in it, where *"you may"* does.

#### The prompt took the hundred-item score from `0.02` to `0.19`

| lab, 100 golden items | old prompt (Round 17) | `SYSTEM_MUSTCALL` (Round 19) |
|---|---|---|
| end to end | 2/91 = **0.02** | **17/91 = 0.19** |
| no tool call | 96 | **53** |
| one tool | 4 | **47** |
| two or more | 0 | **0** |
| fabricated | 5 | **3** |

**Nine times the score, and still less than half the one-shot pipeline's `0.42`.** `D90` is
vindicated as a default and is nowhere near a solution.

**And `53 of 100` still call no tool** under a prompt that orders them to. Forcing in code reaches
what asking does not — at n=20 on the lab it took no-tool-call **8 → 0**, where on the Mac it was
only 2 → 1 because the prompt had already done the work there. **The full-100 run with forcing is
the obvious next measurement** and is not yet taken on either machine.

**Interview question it answers:** *"You found two machines disagreeing. Did that invalidate your
results?"* It invalidated one and sharpened the rest. The disagreement is on decisions that were
genuinely ambiguous — is this question worth a lookup — and vanishes on decisions that are not:
ten out of ten agreement on whether to take a second step once the first is known to be partial.
**So I stopped treating cross-machine agreement as a property of the system and started treating it
as a property of the question**, which also told me what to build: remove the ambiguity rather than
argue with it in a prompt.

### D93 — the agent was reading half of every page, and that invalidates the comparison it was losing

**Found 2026-09-11 while chasing a refusal rate.** Every *"the agent is worse than the one-shot
pipeline"* number taken before this entry was partly measuring **a shorter corpus**.

`agent._observation` formatted each retrieved passage as `hit["text"][:600]`.

| | |
|---|---|
| median chunk | **1299 chars** |
| chunks over 600 chars | **2755 of 3284** |
| one five-passage observation, truncated | 3073 chars |
| the same one, full text | **5861 chars — 1.91×** |

**So the agent saw roughly half of each page while `ask.build_prompt` shows all of it.** The
comparison was never agent-versus-pipeline; it was **agent-with-half-pages** versus
**pipeline-with-whole-pages**.

**How it surfaced, which is the part worth copying.** Not by reading the code. The Mac's hundred
decomposed like this:

| | agent | one-shot |
|---|---|---|
| page reached the model | 45/91 | 58/91 |
| **refused with the page present** | **22 of 45 = 49%** | **19 of 58 = 33%** |

**A 16-point gap in refusals, with the page in front of it either way.** That needed a cause, and
*"the model is shown less than half the page"* is a very good one — a page whose answer lies in the
cut half looks, to the model, exactly like a page that does not answer the question.

**Fixed, and the fix needed a second fix to be safe.** Widening to full text nearly doubles an
observation, and neither `ask.py` nor `toolcall.py` set `num_ctx` — Ollama's default is **4096 and
it truncates in silence**, which is `D80`'s lesson arriving in a second module. Measured: a
two-call conversation with full passages is ~12675 chars, about **3168 tokens**; a third call
exceeds 4096. **Truncation would have moved from my code into Ollama's, invisibly.** So
`LOCAL_CONTEXT = 8192` is pinned on the agent path.

**`rag/ask.py` is deliberately NOT changed.** Its single prompt measures ~6500 chars (~1600
tokens) and has always fit, and editing the shipped path would move `D72`'s published baseline for
no measured reason.

**What is retracted, and what is not.**

- **RETRACTED as a comparison:** the Mac's `0.25` and `0.29`, and the ceiling figure `45/91`. They
  are real measurements of a system reading half-pages.
- **KEPT — both files are preserved** as `agent-sweep-phase5-trunc600.*` and
  `...-forced-nudged-trunc600.*`, because the confound is only demonstrable while they exist. That
  is the lesson of Round 14's citation cells, whose raw answers went to `/tmp` and cannot be
  re-derived (`D85`).
- **UNAFFECTED:** `D87` (re-measured at the new window: still 20/20, 100% content-channel), `D91`
  and `D92` — E4 chains or it does not, and truncation cannot manufacture a second tool call.
- **The lab's `0.02` and `0.19` carry the same confound** and are being re-taken.

#### The re-run, and the conclusion it reverses

**Mac, 100 items, same prompt, only the truncation removed:**

| | ceiling | delivered | **conversion** | over-refused |
|---|---|---|---|---|
| agent, half pages | 45/91 | 23/91 = 0.25 | **51%** | 22 |
| **agent, whole pages** | 45/91 | **39/91 = 0.43** | **87%** | **6** |
| one-shot pipeline | 58/91 | 39/91 = 0.43 | **67%** | 19 |

**Paired: 16↑ 0↓, p = 0.00003.** Sixteen items fixed by deleting four characters, none broken.

**The ceiling did not move at all** — the same 45 items got the page either way. What moved is what
the model *did* with them.

> **The agent converts its ceiling BETTER than the one-shot pipeline (87% against 67%) and reaches
> a lower ceiling (45 against 58). The two cancel to the same 0.43.**

**And this reverses the conclusion I had written two hours earlier.** I said the agent's problem was
retrieval discipline and its generation defect was `D72`'s, same size. Wrong on the second half:
**its over-refusals are 6 against the pipeline's 19.** `D72`'s defect — refusing with the page in
hand — is Phase 4's headline, and the agent given the same pages in full **largely does not have
it.** The plausible reason is structural: its pages arrive one tool result at a time, numbered,
*after it asked for them*.

**So the retraction in this entry is not "some numbers were low".** It is that the truncation
inverted which half of the system looked broken.

**Interview question it answers:** *"How did you catch a bug that made your own system look bad?"*
I did not go looking for it. I had a number I could not explain — the agent refused 49% of the time
with the page present against the pipeline's 33%, and there was no reason for the same model to
behave differently on the same page. Chasing the cause found a `[:600]` I had written myself. **The
useful habit is not code review, it is refusing to accept a gap you cannot account for** — and
noticing that fixing it needed `num_ctx` pinned, or the truncation would simply have moved
somewhere I could not see.

### D94 — Phase 5's close: the agent's LEVELS are machine-dependent, its EFFECTS reproduce

**Round 20, both machines, whole pages, `num_ctx` pinned, 100 golden items.**

```
                ceiling  delivered    e2e   conv  over-ref  no-tool  two+  fabr
Mac default          45         39   0.43    87%         6       23     0     4
Mac levers           54         43   0.47    80%        11        1     6     1
lab default          25         25   0.27   100%         0       51     0     6
lab levers           45         33   0.36    73%        12        4     7     6
one-shot pipeline    58         39   0.43    67%        19        —     —     2
```

**Round 20's pass/fail was written before the data and it names this outcome exactly:** *"it lands
well below 0.42 → the reversal is a Mac effect; `D89` applies."* The lab's default is **0.27**.

> **"The agent matches the one-shot pipeline" is a MAC claim and does not survive.** It is
> withdrawn as a general statement.

**What does reproduce is everything except the level, and the list is not short.**

**1 — the levers work on both, and better on the lab.** Mac **4↑ 0↓, p = 0.125**; lab **8↑ 0↓,
p = 0.0078**. **Zero regressions on either machine**, and the lab's result is the significant one.
The lever the Mac could barely show is the lever the lab needed most.

**2 — the over-refusal advantage is real and the lab makes it stark.** The one-shot pipeline
refuses **19** times with the page in hand — `D72`'s defect, Phase 4's headline. The agent's
default: **6** on the Mac and **0** on the lab. **The lab's agent converted 25 of 25.** Whatever
else is machine-dependent, *pages arriving one tool result at a time, numbered, after being asked
for* does something the five-at-once prompt does not.

**3 — chaining reproduces:** 6 on the Mac, 7 on the lab, from a standing start of 1 in 80 runs.
`D91`/`D92` hold at n=100 on both boxes.

**4 — forcing does what it says:** no-tool-call **23 → 1** and **51 → 4**.

**The whole level gap is one number, and `D89` already named it.** The lab calls no tool on **51**
of 100 questions against the Mac's **23**. Same prompt, same model, same items. Everything
downstream follows: fewer searches, lower ceiling, fewer delivered. **The agent's score is a
function of how often that machine decides a question is worth a lookup, and that decision is the
one measured as a coin-flip across boxes.**

**Which is why the levers matter more than the score.** Forcing removes the decision. On the lab it
took the ceiling from 25 to 45 — **the Mac's default ceiling** — and delivered from 25 to 33.

**Decided — nothing ships as a default beyond `SYSTEM_MUSTCALL` (`D90`).** The levers are kept as
measured flags. **Why not ship them, when they are 8↑ 0↓ significant on the reproducible machine?**
Because conversion *falls* when they are on — 87% → 80% (Mac), 100% → 73% (lab) — so they buy
ceiling and give back quality, and **fabrications did not improve on the lab at all** (6 both
arms). A lever with a known cost and an unmeasured net is a Phase 6 decision with a cost/quality
frame, not a default to slip in at the end of Phase 5.

**What Phase 5 can claim, stated in the form it survives in:**

- a 7B local model **can** use tools reliably — 100% valid calls, right tool, two machines;
- it **stops after one step** unless told the first was partial, and that is fixable with one
  sentence (`D91`, `D92`);
- **it does not have the one-shot pipeline's over-refusal defect** (19 → 6 / 0);
- **its end-to-end score does not reproduce across machines** and is governed by a coin-flip
  decision (`D89`);
- **the levers help on both boxes with zero regressions**, and cost conversion.

**Interview question it answers:** *"Did your agent beat the baseline?"* On one machine, yes, 0.47
against 0.43. On the other, no, 0.36 against the same baseline. **So the honest answer is that the
score is not the finding** — what reproduced is that the agent stops early and can be told not to,
and that it does not inherit the refusal defect the one-shot system has. I wrote the pass/fail
before the run, it landed on the row that says *Mac effect*, and I withdrew the claim rather than
quoting the machine that agreed with me.

### D95 — the Mac screens, the lab rules; two machines stay, and the reason is not access

**Decided 2026-09-12**, after Round 20 withdrew a claim the Mac had supported (`D94`).

**Rejected — measure only on the lab.** It is the reproducible box (`D84`), so it looks like the
obvious simplification. It would have destroyed the most valuable class of result in this project:
`D83`, `D84`, `D89`, `D92` and `D94` **all exist because two machines disagreed.** With one machine
you cannot tell whether `0.27` is *the* answer or *that box's* answer — you get a number and no way
to know its scope. Every one of those entries would have shipped as an unqualified claim.

**Rejected — measure only on the Mac.** It drifts (`D84`), and `D94` is what that costs: a
headline of *"the agent matches the pipeline"* that survived a few hours and then did not.

**Decided — both, with different jobs:**

| | job | why it gets that job |
|---|---|---|
| **Mac** | screen, hunt, iterate | **Claude can drive it unattended.** Six hours of sweeps ran overnight with nobody awake; the `[:600]` bug, `D91`'s nudge and both levers came out of that |
| **lab** | rule | it reproduces, and `D84` says prefer it when they disagree |

**The constraint is autonomy, not access — and I had this wrong until Viraj corrected it.** I argued
the lab was costly because it needed him present. **RustDesk makes it reachable any time.** What
does not change is that a remote desktop is a GUI: **Claude cannot type into it**, so every lab run
waits for a human to launch it while Mac runs do not. The trade is *work that proceeds without you*
versus *work that waits for you* — which is a smaller gap than I claimed, and still a real one.

**The consequence of that correction:** the lab should now take the **paired long runs**, not just
short confirmations. Round 20 was 1h45 and cost one launch. That is cheap enough that the
important pairs belong there, with the Mac screening first.

**The standing rules:**

1. **Anything quoted in a doc, a decision or a CV is the lab's number, or names both machines.**
2. **A Mac-only figure is labelled a screen from the moment it is written** — not after the lab
   disagrees. `D94` sat in the state block as a headline for a few hours before Round 20 landed,
   and under this rule it would have carried its scope immediately.
3. **Disagreement is a result, not a nuisance.** It gets written down rather than resolved by
   picking the machine that agrees with the hypothesis.

**Interview question it answers:** *"You had two machines disagreeing constantly — why not just
standardise on one?"* Because the disagreement was the most informative signal I had. Standardising
would have converted five findings about the *scope* of my results into five unqualified claims,
and the one I most wanted to be true is the one the second machine killed. **The cost of two
machines is that half my numbers come with a caveat. That is not a cost, it is the caveat being
visible instead of absent.**

### D96 — the prompt's SHAPE is not shipped: what reproduces is a willingness shift, not better reading

**Decided 2026-09-12**, on Round 21 (lab) against the Mac screen, both machines, 100 items each.
Instrument: `rag/framing.py`. Rows: `deliverables/framing-phase6.{Darwin-arm64,Linux-x86_64}.json`.
Reproduce either table with `uv run python -m rag.framing --report` on that machine.

**The question.** The shipped pipeline refuses **19–20** times with the answer page in the prompt
(`D72`); the Phase 5 agent refuses 6 (Mac) and 0 (lab). Phase 4's five wordings could not move
those (`D74`). The only structural difference is how the pages arrive:

```
arm A (shipped)        system | user: SOURCES [1]..[5] --- QUESTION --- ANSWER:
arm B (agent's shape)  system | user: QUESTION
                              | assistant: "Let me look that up in the SQLAlchemy documentation."   <- written, not generated
                              | user: SOURCES [1]..[5] --- QUESTION --- ANSWER:
```

Same system prompt, same five passages, same numbering, one model call each. **No tools, no loop.**

**What was measured, both machines:**

```
                       Mac (screen)                     lab (rules)
page present           A 19 over-refused -> B 14         A 20 -> B 17
                       6 fixed 1 broken  p = 0.125        5 fixed 2 broken  p = 0.453
page absent answered   A 7 -> B 12                        A 7 -> B 11
unanswerable fabr      2 -> 2 (g056 g065)                 2 -> 2 (g056 g065)
uncited (answered)     67% -> 68%                         33% -> 44%
```

The lab's uncited figures are `judge.citations` over answered answerable rows. Its arm A and Round
16's `D` refuse the **same 20 items** yet only **60 of 100 answers are byte-identical**, so Round
16 re-derived the same way reads **18/45 = 40%**: the decision is stable and the wording is not
(`D84`). **B's 44% is above both.** On neither machine does B cite more; on the lab it cites less.

**The controls held to the item, which is why the rest can be read at all.** Mac arm A: `D72`'s
19 and `D74`'s 31/46 uncited exactly. Lab arm A: **the same 20 over-refused ids as Round 16's `D`,
two days apart.** The two arm As differ by one item, `g029` — the item `D54` already named as
drifting.

**Read by id, the part that reproduces is smaller than either machine's count:**

```
                       both machines              Mac only        lab only
page present  fixed    g021 g049 g050 g100        g008 g116       g029
page present  broken   g043                       --              g019
page absent   broken   g005 g016 g113 g114        g028 g085       --
```

Every Mac-only extra (`g008 g116 g028 g085`) stays refused under B on the lab. **The Mac's B is
more willing than the lab's B — and the direction is the same on both.** `g029` is lab-only because
the lab's *arm A* refused it, not because B did anything different.

**Why this is a willingness shift and not a reading improvement.** When the page is absent,
declining is the honest outcome (`D72`'s split). B answers **4 such items on both machines** that
A declined. A prompt that helped the model read its pages would move the page-present row and leave
that one alone. It moved both, in the "answer more" direction.

**And the reproducible fixes are not clean** (Mac judge, `gemma4:e4b`, a screen — `D86` measured it
too extreme both ways): of the four shared fixes, `g021` and `g049` are `SUPPORTED`, `g050` and
`g100` `PARTIAL`. The shared break `g043` was a **`SUPPORTED`** answer. Of the four shared
page-absent extras, **three are `UNSUPPORTED`** (`g016 g113 g114`). Three of B's six Mac fixes cite
nothing.

**Against the rules written before the data (Round 21):**

| rule | result |
|---|---|
| same six fixed, same `g043` → real and specific | **no** — 4 of 6 shared, plus a second break on the lab |
| fewer fixes, more breaks → reject | **yes** — lab 5↑ 2↓ against the Mac's 6↑ 1↓ |
| B fabricates more → not shippable | no — 2 = 2, same ids, both machines |
| page-absent rises like the page-present gain → willingness; fixes need a quality reading | **yes**, both machines |
| judge: 4 of 6 fixes `SUPPORTED` → mixed, no conclusion | Mac only, recorded as mixed |

**Decided: the shipped prompt stays as it is.** `ask.build_prompt` is untouched and `D72`'s 19–20
stand. `rag/framing.py` stays as the instrument.

**Rejected — ship B because both machines moved the page-present row the right way.** Two p-values
of 0.125 and 0.453 do not add up to one below 0.05, the reproducible core is 4↑ 1↓ (p = 0.375), and
Round 14's rule — one regression is a hold — is broken on both machines by the same item.

**What it does say about Phase 5.** The agent's low over-refusal count (6 / 0) is **not explained by
the conversation shape alone**: replaying the shape with no tool gives a smaller, noisier move that
brings unsupported answers with it. Whatever the agent does differently — choosing its own query,
deciding to look, or seeing a result it asked for — is the remaining suspect, and it is untested.

**Interview question it answers:** *"Your agent refused far less than your pipeline — why not just
copy its prompt structure into the pipeline?"* I tried exactly that, with no tools, and the part that
reproduced across two machines was four fixes, one lost good answer, and four new answers where the
page was missing — three of them unsupported. **The prompt made the model more willing to answer,
not better at using the page, and I only saw that because I counted the items where refusing was the
right thing to do.**


### D97 — the CI gate grades retrieval, paired by id, and one lost golden answer fails the check

**Decided 2026-09-12.** Phase 6 Step 2. Code `rag/gate.py`, workflow `.github/workflows/gate.yml`,
baseline `deliverables/gate-baseline.json`, demo `deliverables/gate-demo-no-rerank.json`, teaching
`study/18-PRODUCTION.md` §R10.

**What the gate does.** On every PR that touches retrieval: build the corpus, embed (cached), load
Qdrant, score the 100 golden questions, and join the rows to the base branch's baseline on id. Any
answerable item whose answer page was in the top 5 and is not any more **fails the check**.

**The ROADMAP's demo, measured** (committed rows, reproduces with no Qdrant; `PHASE-6.md` block):
removing the reranker takes recall@5 **58/91 → 57/91**, and the gate says **BLOCKED, `g017`,
exit 1**. `g017` is `D68`'s only fix. For `g017` the reranker is one swap at the seat 5/6
boundary: `c01603` (the answer) and `c00970` trade places.

**Rejected — gate on the average.** 0.64 → 0.63 is inside the **±0.097** band, so an average gate
calls the demo noise and passes it. `D61` already said Phase 3 is judged by flipped items; the gate
applies that to every PR.

**Rejected — gate on McNemar p < 0.05.** The demo is 0 fixed, 1 broken, **p = 1.000**. A loss the
test cannot distinguish from noise is still a question that no longer gets its page. p is printed
for context only.

**Rejected — let net gains through (fixed > broken).** Round 14's rule, one regression is a hold,
is what still holds `H` (`D83`) and what rejected framing (`D96`: `g043`). The gate does not forbid
a trade; it forbids an unseen one. A human reads `broken` and decides.

**Rejected — grade generation in CI.** No Ollama on a runner, and `D83` measured generation not
reproducing across machines while retrieval reproduced exactly. A check that flips with the runner
gets switched off.

**Rejected — commit the vectors so CI skips embedding.** `D11`/`D36`: vectors are generated, and a
committed array can silently disagree with the chunks it indexes. **The cache is keyed on exactly
what the vectors are a function of**: `chunks.jsonl` bytes, model id and revision, window,
normalisation, and the source of `embedding_input()`. Not `rag/embed.py` whole: a comment edit
would cost a cold embed.

**Rejected — compare against base code re-run on the same runner.** It removes every
machine-difference question, and it was the more principled design under `D95`. It fails on
bootstrap: `main` is Phase 1 and has no `rag/score.py` to run, so the first PR it would ever grade
could not be graded. It also doubles the job. **Revisit it if the reproduction test below ever
fails on a real runner.**

**Two guards against moving the ruler** (both tested): the baseline is read from the **base branch**
(`git show origin/<base>:…`), never the PR's copy, or a PR could rewrite the baseline to match what
it broke; and an answerable item that is **missing** or **relabelled** fails as `ruler changed`, or
a PR could delete the item it broke. New items pass as `unpaired`. `D06` in CI.

**Found building it: the reranker was never pinned.** `rerank.py` said *"Pinned like
embed.MODEL_REVISION"* from 2026-08-21 and passed no revision to `CrossEncoder`. On a runner a cold
cache downloads whatever `main` is that day, and a new upload could flip `g017`, failing an
innocent PR. Pinned to `2cfc18c9…` (the only snapshot in the Mac's cache, which `refs/main` names);
a test asserts the **load** receives it. **Re-scored after pinning: recall@5 0.64, 7↑ 0↓, p = 0.016
against the Phase 1 baseline, the same seven ids** (`g017 g024 g038 g044 g046 g047 g050`).

**Found reviewing the workflow: `actions/cache` saves only when the job succeeds.** A gate exists to
fail, so a blocked PR would discard a cold embed and the next push would pay it again. Restore and
save are separate steps, each save right after the step that filled the cache.

**Mutation-checked:** seven mutations against `rag/gate.py`; the first pass MISSED two (grading
unanswerable items as `moved`; a relabel to answerable counting as a free fix). Two tests added,
seven of seven caught.

**The machine question, measured: does a CPU reproduce the MPS baseline?** The baseline was taken
on MPS; a runner has only a CPU; a phantom `broken` on every PR would kill the gate. Test on the
Mac: re-embed all 3284 chunks with `device="cpu"` into a throwaway Qdrant collection, then score
the 100 questions with query embedding and reranker also on CPU.

```
CPU embed, 10-core M4, batch 16          1106 s   (MPS: 566 s)
vectors bit-identical to MPS             0 of 3284     max |difference| 1.3e-05
top-20 chunk lists identical             100 of 100
ranks identical                          100 of 100
gate vs MPS baseline                     fixed 0  broken 0  moved 0  -> PASSED
```

**Every vector differs and no ranking moves.** That is the useful shape: the floats are not the
same, and on this corpus and these 100 questions the differences are too small to swap any two
chunks, including at `g017`'s seat 5/6 boundary. It extends `D83` (MPS = CUDA) to a third backend.

**What it does not cover: a Linux x86 CPU**, which uses a different BLAS from Apple's. That is the
runner, and it is unmeasured until the workflow runs. The job uploads its rows either way, and the
first thing to read on a surprising result is `moved`.

**Not done, and not Claude's to do:** open a PR so the workflow runs on a real GitHub runner, and
make the check *required* in branch protection. Until the first, every claim about the runner
above is a Mac measurement of a CPU, not a runner measurement.

**Interview question it answers:** *"How do you stop someone making your RAG system worse?"* Every
PR that touches retrieval re-scores the golden set on a CI runner and fails if a single question
loses its page from the top five. Removing my reranker costs one point of recall, which is inside
the noise band, so an average-based gate would pass it; mine names the question it broke. It grades
retrieval only, because that is the half I measured reproducing across machines.

### D98 — the router is a cascade on refusal, not a predictor on retrieval scores

**Decided 2026-09-12.** Phase 6 Step 3a. Instrument `rag/route.py`, signals
`deliverables/route-signals-phase6.Darwin-arm64.json`, outcomes the lab's Round 16 `D` rows.
Reproduce with no model: `uv run python -m rag.route --report` (block in `PHASE-6.md`). Rules and
prediction written into `PHASE-6.md` before the numbers.

**The question.** Routing sends some questions to a stronger model. It pays only if it sends the
ones the local pipeline fails, *and* the stronger model can fix them. Our 53 local failures (lab,
91 answerable, 38 delivered) come in two kinds, and a stronger generator can only fix one:

```
page ABSENT   33 answerable items   same five wrong pages for any model -> answering means memory (g065)
page PRESENT  20 of the failures    the local model refused the right page -> plausibly fixable
```

**Why the join of two machines is allowed:** outcomes are the lab's (`D95`), cross-encoder signals
were computed on the Mac, and retrieval is identical across the two (`D83`). The instrument checks
it: **0 page-present flags differ**, and it refuses to print a router result if one does.

**Rejected — A, predictive routing on max cross-encoder score.** Routing the 30 questions whose best
page scores lowest catches **20 of 53** failures; the pre-registered bar was 27. Exact random
routing gives median 16, P(≥ 20) = 0.057, so the signal is real and weak. **Worse, it catches 3 of
the 20 fixable failures**, fewer than random picking (~6): low retrieval scores mark exactly the
questions where the page is missing, which a stronger model cannot fix. It also routes 6 questions
the local model already delivered and 4 unanswerable ones.

**Decided — B, cascade: generate locally, escalate on refusal.** It catches **all 20** fixable
failures, because an over-refusal is by definition a refusal. Its costs, stated with it:

- **It escalates 53 of 100.** 26 of those are page-absent refusals (honest; a stronger model gets the
  same wrong pages) and 7 are unanswerable items refused correctly, which escalation would put at
  risk of fabrication.
- **It never sees 7 failures** that answered without the page, and never sees `D72`'s two
  fabrications (`g056`, `g065`), because nothing refused.
- **Every escalated question pays two generations**, one of them free and local.

**Found measuring it — the random baseline I first quoted was a binomial.** A scratch script drew a
fresh sample per failure (P(≥ 20) = 0.14); the committed instrument drew 30 of 100 and disagreed
(0.06); exact hypergeometric settles it at **0.0571**, and a test pins it. I had already told Viraj
"indistinguishable from chance"; the correct reading is "marginal, and fails the bar".

**Mutation-checked, six mutations against `rag/route.py`: five caught.** The sixth (counting
unanswerable escalations as page-present) is **equivalent**: an unanswerable item has no answer
chunks, so its page-present flag is always false and no input can tell the two versions apart.
Recorded as equivalent rather than tested against an impossible row.

**Prediction scored 2 of 4** (`PHASE-6.md`): A passing — wrong; A mostly page-absent — right; B
escalating fewer — wrong; B's larger page-present share — right.

**Not measured, and the reason this is 3a not 3:** whether a stronger model answers the 20, and at
what price. Zero paid calls stands; a free tier was measured at 20 calls a day per model (`D80`),
which is enough for 20 escalations once. The shadow cost needs published per-token rates with a
date and a source, not a remembered number.

**Next hypothesis, from exploration and so not a decision:** max CE separates page-present from
page-absent *among the escalations* at AUC 0.71. *Escalate a refusal only when its best page looks
relevant* would cut escalations toward the fixable 20. Pre-register it before measuring.

**Interview question it answers:** *"How does your router decide what goes to the expensive model?"*
It does not predict. I tested predicting from retrieval scores and it mostly flagged questions whose
answer page was missing, which no stronger model can fix from the same pages. So the router is a
cascade: the free local model answers first, and only a refusal is escalated, which catches every
case where the page was there and the small model declined it.
---

## Where the rest of the repo lives

| | |
|---|---|
| [`../README.md`](../README.md) | the front door, with a **Start here** table |
| [`../phases/PHASE-2.md`](../phases/PHASE-2.md) | the current phase and its open decisions (`P2-a`…`P2-d`) |
| [`../phases/PHASE-1.md`](../phases/PHASE-1.md) | the phase before, complete — and the record of how each gate closed |
| [`./README.md`](README.md) | this folder's index and the three § numbering families |
| [`../logs/LEARNING-LOG.md`](../logs/LEARNING-LOG.md) | the dated timeline — *when* things were learned |
| [`../CLAUDE.md`](../CLAUDE.md) | how the work gets done, and the rules above as working agreements |

**This file has no `§` numbers** — like `03` and `08` it is a register rather than a chapter.
Cite entries by ID (`D19`), which is stable even when the file is reordered.
