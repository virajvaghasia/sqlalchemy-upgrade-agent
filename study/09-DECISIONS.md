# Design decisions — the register

Every decision this project has made, what was rejected, and **why**. Written for revision:
read the bold line, and if the reasoning is already in your head, move on.

**Why this file exists.** The rest of the repo explains *how* things work. Almost nothing in it
answers *"why not the other thing?"* — and that is the entire content of a design interview.
A decision whose alternatives were never written down is a decision you will re-derive badly,
under pressure, in front of someone who has heard the confident version before.

**How to read an entry.** Each has a stable ID (`D01`…`D46`), so other docs can cite `D14` and mean
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
**D31 left this section on 2026-08-17**, measured against pgvector — which won on every number, and the entry says so rather than reporting a tie. **§H is now empty, and that is a claim to be suspicious of**: it means every choice has a recorded comparison, not that every choice is right.

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


---

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

## Where the rest of the repo lives

| | |
|---|---|
| [`../README.md`](../README.md) | the front door, with a **Start here** table |
| [`../phases/PHASE-1.md`](../phases/PHASE-1.md) | the current phase and its open steps |
| [`./README.md`](README.md) | this folder's index and the two § numbering families |
| [`../logs/LEARNING-LOG.md`](../logs/LEARNING-LOG.md) | the dated timeline — *when* things were learned |
| [`../CLAUDE.md`](../CLAUDE.md) | how the work gets done, and the rules above as working agreements |

**This file has no `§` numbers** — like `03` and `08` it is a register rather than a chapter.
Cite entries by ID (`D19`), which is stable even when the file is reordered.
