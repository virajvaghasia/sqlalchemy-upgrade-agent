# Design decisions — the register

Every decision this project has made, what was rejected, and **why**. Written for revision:
read the bold line, and if the reasoning is already in your head, move on.

**Why this file exists.** The rest of the repo explains *how* things work. Almost nothing in it
answers *"why not the other thing?"* — and that is the entire content of a design interview.
A decision whose alternatives were never written down is a decision you will re-derive badly,
under pressure, in front of someone who has heard the confident version before.

**How to read an entry.** Each has a stable ID (`D01`…`D39`), so other docs can cite `D14` and mean
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
> pages are generated at Sphinx build time from Python docstrings — 660 `.. autoclass::`-family
> directives in the 1.4 tree, 743 in 2.0. So per-method reference pages are absent from the
> corpus, and a question like *"what arguments does `Session.execute` take?"* has nothing to
> retrieve.
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

> **Decided** — three required checks (tests / 2.0 evidence / image builds), branch protection
> with `enforce_admins` on, demonstrated by opening a PR that fails and confirming GitHub
> refuses to merge it.
> **Instead of** — configuring branch protection and assuming it works.
> **Because** "I set up CI" and "I proved CI blocks a bad merge" are different claims, and only
> the second survives *"how do you know?"*

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

**These are chosen but unearned.** They appear in `ROADMAP.md`'s tools table and glossary and
are named as "yours", but no comparison, benchmark or trade-off was ever recorded. Treat this
section as the honest edge of the project.

### D31 — Qdrant as the vector database ⚠️

> **Decided** — Qdrant.
> **Never compared against** — FAISS (a library, not a server, no persistence layer of its
> own), Chroma (simpler, weaker filtering), pgvector (would reuse the Postgres already running
> in Compose), Weaviate, Milvus.
> **What is actually true today:** Qdrant is named in `ROADMAP.md` and nothing more.
> **The honest interview answer:** *"I picked it for metadata filtering and because it runs as
> a container next to everything else. I have not benchmarked it against pgvector, and pgvector
> is the one I would compare first, since Postgres is already in the stack."* That answer is
> stronger than a recited feature list, because it names the alternative you would test.
> **Settle this in Step 3** and replace this entry.

### D32 — BGE-M3 as the embedding model ⚠️

> **Decided** — BGE-M3.
> **Never compared against** — `all-MiniLM-L6-v2` (far smaller and faster, weaker),
> `bge-large-en`, `e5-large`, `nomic-embed-text`, or anything on the MTEB leaderboard.
> **What matters and is not yet measured:** the VRAM it needs alongside Ollama. There are
> **7115 MiB** free with `qwen2.5-coder:7b` loaded (D27), and whether BGE-M3 fits inside that
> is a fact, not a preference. If it does not, either the embedder or the generator has to be
> unloaded between phases — a real architectural consequence.
> **Settle this in Step 3**, with the VRAM number measured on the lab PC.

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
