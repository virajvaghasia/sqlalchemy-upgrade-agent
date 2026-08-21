# sqlalchemy-upgrade-agent

A retrieval system that helps developers upgrade Python code from **SQLAlchemy 1.4 → 2.0**.

The corpus it retrieves from is not scraped. It is **measured**: a deliberately 1.4-style
application in this repo, run against real 2.0, with every failure recorded as it actually
happened. `deliverables/BREAKAGES.md` is that record, and it becomes the golden dataset the retrieval
system is later evaluated against.

**Status:** Phase 0 complete except its Day 3 tunnel, which is blocked on someone else rather
than on work. **Phase 1 is built, not complete** — a question typed at a terminal returns an answer with its
sources, and all five steps run. Three of the phase's own gates are still open, and all three
are human: ten chunks to eyeball, 19 answer verdicts, five cold questions. Pinned to SQLAlchemy
**1.4.52**; breakages verified against **2.0.51**. See [`phases/ROADMAP.md`](phases/ROADMAP.md)
for the six-phase arc.

---

## Start here

This repo is 17 documents and about 11,000 lines, which is a book, and reading it front to back
is the wrong move. **Almost none of it is meant to be read in order.** Pick the question you
actually have:

| if you want to… | read, in this order | roughly |
|---|---|---|
| **know where the project is** | this Status line → [`phases/PHASE-1.md`](phases/PHASE-1.md) → the last entry of [`logs/LEARNING-LOG.md`](logs/LEARNING-LOG.md) | 15 min |
| **understand what was built most recently** | [`phases/PHASE-1.md`](phases/PHASE-1.md) Steps 1–2 → `rag/corpus.py`, `rag/chunk.py` → `tests/test_chunk.py` | 30 min |
| **learn what Phase 1 is actually doing** | [`study/10-RETRIEVAL.md`](study/10-RETRIEVAL.md) §R1 — from zero, no retrieval background assumed | 45 min |
| **revise for an interview** | [`study/09-DECISIONS.md`](study/09-DECISIONS.md) — every decision, what was rejected, and why. **Start here for this**, not with the study files | 1 hour |
| **go deeper on the evidence** | [Three findings](#three-findings-worth-knowing-before-you-read-anything-else) below → [`deliverables/BREAKAGES.md`](deliverables/BREAKAGES.md) Groups A–H → [`study/02-MIGRATION-2.0.md`](study/02-MIGRATION-2.0.md) §16–§22 | a few hours |
| **learn SQLAlchemy properly** | [`study/README.md`](study/README.md), then follow its numbering | days |
| **learn the Docker/CI side** | [`study/04-DOCKER.md`](study/04-DOCKER.md) §1 opens with a one-page plain-language summary — start there, not at §1.1 | half a day |
| **work on the lab PC** | [`study/08-LAB.md`](study/08-LAB.md) — it is a runbook, so jump to the section you need | as needed |

**The three long files are reference, not reading.** `study/01-CONCEPTS.md` (1875 lines),
`study/02-MIGRATION-2.0.md` (1458) and `deliverables/BREAKAGES.md` (1266) are things you look
*into* when you have a specific question. Nobody, including the person who wrote them, reads
them straight through.

**If you only open one file, open [`phases/PHASE-1.md`](phases/PHASE-1.md).** It says what the
current phase is, what the next step is, and why each decision already made was made.

---

## Quickstart

```bash
uv sync
uv run python -m experiments.sqlalchemy_1_4_vs_2_0.seed      # build issues.db
uv run python -m experiments.sqlalchemy_1_4_vs_2_0.check     # smoke-test the mappers
```

Everything below runs on 1.4 and changes nothing.

```bash
uv run python -m experiments.sqlalchemy_1_4_vs_2_0.explore     # relationships, live SQL
uv run python -m experiments.sqlalchemy_1_4_vs_2_0.states      # session runtime, N+1
uv run python -m experiments.sqlalchemy_1_4_vs_2_0.migration   # the 2.0 mechanics
uv run python -m experiments.sqlalchemy_1_4_vs_2_0.sweep       # 2.0 warnings, every module
uv run python -m experiments.sqlalchemy_1_4_vs_2_0.candidates  # patterns worth testing
```

To see what **real 2.0** does — without upgrading anything. `uv` builds a throwaway
environment while `pyproject.toml` stays pinned to 1.4:

```bash
uv run --no-project --with 'sqlalchemy==2.0.51' \
    python -m experiments.sqlalchemy_1_4_vs_2_0.verify_2_0
```

Phase 1 starts by fetching the retrieval corpus — 270 `.rst` files from the two pinned
SQLAlchemy release tags. It is not committed; this rebuilds it, and `corpus/MANIFEST.json`
records where every file came from and which release it documents.

```bash
uv run python -m rag.corpus            # fetch if absent, then report
uv run python -m rag.corpus --check    # re-hash every file against the manifest
uv run python -m rag.chunk             # cut it into 3284 retrievable chunks
uv run python -m rag.chunk --sample 10 # print ten at random to eyeball

uv sync --extra embed                  # torch + sentence-transformers (big; not in the image)
uv run python -m rag.embed             # 3284 x 1024 vectors -> corpus/embeddings.npy
docker compose up -d qdrant
uv run python -m rag.index             # load them into Qdrant
uv run python -m rag.index --search "why can't I call engine.execute any more?"
uv run python -m rag.ask "why can't I call engine.execute any more?"   # answer + sources
uv run python -m rag.probe             # 19 probe questions -> deliverables/FAILURES.md
uv run python -m rag.compare_embedders # BGE-M3 vs a 25x smaller model, on retrieval
```

---

## Repository layout

```
README.md              this file — the map
CLAUDE.md              how the AI assistant works on this repo
phases/                the plan: the six-phase arc, and each phase in detail (PHASE-2 is current)
study/                 the teaching material, numbered in reading order
deliverables/          what a phase produced — BREAKAGES.md is Phase 0's, FAILURES.md is Phase 1's
logs/                  the dated timeline
experiments/           the code under study: the 1.4 app and the measurement harness
rag/                   the Phase 1 retrieval system — corpus in, answer with sources out
tools/                 check_runnable.py — every `# runnable` block, verified
corpus/                MANIFEST.json + CHUNK_STATS.json. raw/ and chunks.jsonl are generated
tests/                 173 tests pinning what the docs claim
.github/workflows/     CI — tests, the 2.0 evidence, and the image
```

## The documents

Read in this order. Section numbers run continuously across the first two, so a reference
to "§18" is unambiguous in either file.

| file | what it is |
|---|---|
| [`phases/ROADMAP.md`](phases/ROADMAP.md) | the six-phase arc, plus a glossary of every AI term used |
| [`phases/PHASE-2.md`](phases/PHASE-2.md) | **the current phase** — turn "it seems okay" into a number. The golden set is finished (50 items, all human-verified) and the baseline is measured; `--refusals` covers `D62`'s generation half |
| [`phases/PHASE-1.md`](phases/PHASE-1.md) | **complete 2026-08-18** — a deliberately dumb RAG, why it must be bad first, and how both human gates closed (`D56`, `D57`) |
| [`phases/PHASE-0.md`](phases/PHASE-0.md) | **the phase before** — complete except its Day 3 tunnel, and its deliverables |
| [`study/`](study/README.md) | **the teaching material, in reading order** — the index explains the three § numbering families, and carries a **by-phase view** (`01`–`08` Phase 0, `10`–`13` Phase 1, `09` all of them) for reading it phase by phase instead |
| [`study/01-CONCEPTS.md`](study/01-CONCEPTS.md) | **§0–§15** — the relational model, the ORM layer, the session at runtime |
| [`study/02-MIGRATION-2.0.md`](study/02-MIGRATION-2.0.md) | **§16–§22** — the 1.4 → 2.0 upgrade: what breaks, what only looks like it does |
| [`deliverables/FAILURES.md`](deliverables/FAILURES.md) | **the Phase 1 deliverable** — 19 questions, where retrieval breaks, and the split between failures Phase 3 can fix and the corpus ceiling it cannot. Verdicts closed 2026-08-17: **10 correct, 3 partial, 6 wrong**, hand-written and kept in `verdicts.json` so a regeneration cannot destroy them |
| [`deliverables/BREAKAGES.md`](deliverables/BREAKAGES.md) | **the Phase 0 deliverable** — 23 verified breakages; seeds the Phase 2 golden dataset |
| [`deliverables/golden.json`](deliverables/golden.json) | **the Phase 2 ruler** — **100 items: 50 hand-verified, 50 harvested drafts** awaiting verification, each with the chunk that answers it. `rag/score.py` refuses to score any item a human has not verified (`D06`). Baseline **recall@5 = 0.51 ±0.131** — but read `D63` first: that averages `migration_guide` at **0.73** with `breakages` at **0.41**, and 0.41 is the honest number |
| [`deliverables/baseline-phase1.json`](deliverables/baseline-phase1.json) | **the Phase 1 baseline rows** — what `rag/score.py --baseline` compares against, so every Phase 3 result is a *paired* comparison with the flipped items named, not two percentages (`D61`) |
| [`study/03-PRACTICE-APP.md`](study/03-PRACTICE-APP.md) | the design of the app under test, and why this schema |
| [`study/04-DOCKER.md`](study/04-DOCKER.md) | **§1–§3, one container** — opens with a one-page plain-language summary, then layers, the build cache, build context, base images and wheels, `CMD`/`ENTRYPOINT`, non-root. Every number measured against this repo |
| [`study/05-COMPOSE.md`](study/05-COMPOSE.md) | **§4, more than one container** — Compose, networking and DNS, ports, volumes, healthchecks. Numbering continues from `study/04-DOCKER.md` |
| [`study/06-POSTGRES.md`](study/06-POSTGRES.md) | **§5, the database inside one of them** — psql without a published port, the three databases, what `create_all()` emits on Postgres vs SQLite, roles |
| [`study/07-TESTS.md`](study/07-TESTS.md) | **§6, the test suite** — what the tests pin, mutation-checking, fixtures, and what is deliberately not covered |
| [`study/08-LAB.md`](study/08-LAB.md) | lab PC from scratch — SSH / Tailscale / clone / Docker Engine / GPU-in-container / Ollama. A runbook, like `03`, plus the sitting diary in Ubuntu words |
| [`study/10-RETRIEVAL.md`](study/10-RETRIEVAL.md) | **§R1–§R2 — RAG from zero.** Why we look things up instead of asking from memory; why 270 files is a ceiling; why more docs can make answers worse; what the 1024 numbers on disk actually are. Two sittings — stop after the first |
| [`study/11-GENERATION.md`](study/11-GENERATION.md) | **§R3 — after search.** The prompt as a component: three wordings of one sentence (C fabricates 3/3, A over-refused 1/3, B ships), how the cause was found by removing search, and why fixing it did not violate "build the naive version first". The `R` run continues here — it stands for RAG, not retrieval (**D47**) |
| [`study/12-EVALUATION.md`](study/12-EVALUATION.md) | **§R4 — measuring a thing with no right answer.** What a script can score and what it cannot, why the golden set is hand-verified, and the rank measurement that split one planned Phase 3 fix into four different problems |
| [`study/13-VERIFICATION.md`](study/13-VERIFICATION.md) | **§R5 — defending it without notes.** The five questions Phase 1 closes on, answered four ways each: plain words, mechanism, the measurement that makes it checkable, and the spoken version. Includes the wrong answer each question attracts, the follow-up that kills it, and **§R5.7** — all five said end to end, for rehearsing as one piece |
| [`study/14-MEASURE.md`](study/14-MEASURE.md) | **§R6 — Phase 2's scorecard.** The 50-item golden baseline (and why not to quote `0.51` alone), the refusal run (seven generation defects with the page in hand), and the three ceiling questions |
| [`study/09-DECISIONS.md`](study/09-DECISIONS.md) | **the decision register** — 64 entries, each with what was rejected and why. Includes a §H of choices that are *not yet justified*, which is the honest edge of the project |
| [`logs/LEARNING-LOG.md`](logs/LEARNING-LOG.md) | what was learned, dated |
| [`CLAUDE.md`](CLAUDE.md) | how the AI assistant is expected to work on this repo |

### How to read a code block in the docs

Every fenced block carries one of three labels, and the contract differs:

| label | contract |
|---|---|
| `# runnable` | paste the named command and you get **exactly this text** — folding, wrapping and annotations are all done by the script, never by hand |
| `# summary of` | real output from the named command, abridged by hand because the raw form is unreadable. Numbers measured, layout not a paste |
| `# illustration` | a fragment or a sketch. Not something to run |

---

## The code

One package, `experiments/sqlalchemy_1_4_vs_2_0/`. Three roles.

### The app under test

Deliberately written in 1.4 style, with known 2.0 problems left in place.

| module | what it is |
|---|---|
| `models.py` | six mapped classes covering every relationship pattern — 1:M, M:M, association object, self-referential |
| `seed.py` | 200 issues from a fixed random seed, so every measured count is reproducible |
| `app.py` | the query layer: `Query.get()`, `engine.execute("…")`, an unoptimised N+1 |
| `check.py` | smoke test — forces mapper configuration so a broken relationship fails here, not at runtime |

### Tests

```
# runnable: uv run pytest --collect-only 2>&1 | grep -E 'collected'
173 tests collected in 0.37s
```

Three of them skip when Qdrant is not running, so a run reports 114 passed with it up and 111
passed / 3 skipped without. The block counts what is *collected* because that does not depend on
what happens to be running.

They pin what the docs claim, not what SQLAlchemy does: the row counts in `study/03-PRACTICE-APP.md`,
the six-mapped-classes/eight-tables split, that seeding twice produces byte-identical data, and
the `is_seeded` guard that stops the container's startup seed dropping a populated Postgres
volume. Each was mutation-checked — break the thing it describes and it fails.

`tests/test_corpus.py` pins the Phase 1 corpus decision the same way: that only one file was
taken out of `changelog/`, that no dialect pages got in, that `BREAKAGES.md` stayed out so it
can still serve as Phase 2's answer key, and that the totals quoted in `phases/PHASE-1.md` are
the ones `rag/corpus.py` actually measured.

### Proofs behind the teaching docs

Each prints what the library actually does. Nothing in these asserts a number it didn't measure.

| module | backs | shows |
|---|---|---|
| `explore.py` | `study/01-CONCEPTS.md` §0–§13 | every relationship pattern, with the SQL it emits |
| `states.py` | `study/01-CONCEPTS.md` §14–§15 | object states, the identity map, expiry, lazy vs `selectinload` vs `joinedload` |
| `migration.py` | `study/02-MIGRATION-2.0.md` §16–§21 | nine sections: `query()` vs `select()`, the Result API, autobegin, `future=True`, `.unique()`, the measured N+1, `cascade_backrefs`, and what each tool misses |

### Migration tooling

| module | what it answers |
|---|---|
| `sweep.py` | *what does 2.0 object to across the whole project?* — runs the warning sweep on every module, then collapses occurrences into distinct problems |
| `patterns.py` | the shared list of 1.4 patterns under test. Imported by the two below so a prediction and its verification cannot drift apart |
| `candidates.py` | *which patterns are worth testing?* — classifies each by whether the sweep sees it, `future=True` sees it, or neither |
| `verify_2_0.py` | *what does real 2.0 actually do?* — runs the same patterns on 2.0.51 and reports the real error. `--stubs` emits the `deliverables/BREAKAGES.md` skeleton |

---

## Three findings worth knowing before you read anything else

**A green 1.4 test suite is not evidence about 2.0.** The 2.0 warnings are off by default —
`app.py` emits 1 normally and 5 with the flag, and both warnings marking real breakages are in
the hidden four. (§19)

```
# runnable: SQLALCHEMY_WARN_20=1 uv run python -m experiments.sqlalchemy_1_4_vs_2_0.sweep \
#             2>&1 | grep 'distinct,'
  RemovedIn20Warning  —  4 distinct, 29 occurrences
  MovedIn20Warning  —  1 distinct, 6 occurrences
  LegacyAPIWarning  —  1 distinct, 4 occurrences
```

**Neither migration tool is the inventory.** The warning sweep misses patterns that raise
without ever warning; `future=True` misses construction-time removals it never evaluates. Each
tool misses a different subset, and one pattern is called *safe* by both and still fails. (§20)

```
# runnable: uv run --no-project --with 'sqlalchemy==2.0.51' \
#             python -m experiments.sqlalchemy_1_4_vs_2_0.verify_2_0 2>&1 \
#             | grep 'patterns FAIL'
  22 of 24 patterns FAIL on 2.0.51
```

**The most dangerous breakage raises nothing.** Under 2.0, an object attached by the
many-to-one side of a relationship (`comment.issue = issue`) is never enrolled in the session —
the `INSERT` silently never runs. Applied to this repo's own seed, every comment and every
assignment disappears while the seed still reports success. (§17)

```
# runnable: the same verify_2_0 command as above, final section
  attached with project.issues.append(...)  -> in database: True
  attached with issue.project = project     -> in database: False
  rows in issues: 1   titles: ['attached by append']
```

Two objects, one line of code different, and only one of them exists afterwards. **No exception
is raised** — which is why a passing test suite says nothing about it.

---

## Conventions

| thing | convention | here |
|---|---|---|
| repo / folder / GitHub | `kebab-case`, all identical | `sqlalchemy-upgrade-agent` |
| Python packages | `snake_case` — hyphens are illegal in imports | `sqlalchemy_1_4_vs_2_0` |
| root docs | `SCREAMING_CASE.md` | `deliverables/BREAKAGES.md` |
| branches | `phase-N/short-topic` | `phase-0/breakages-and-audit` |
| commits | [Conventional Commits](https://www.conventionalcommits.org/) | `feat:`, `fix:`, `docs:` |
| Compose project + built image | one name, **declared** so nothing is inferred | `sqlalchemy-upgrade-agent` |
| Compose services | one lowercase word — it becomes a hostname | `app`, `db` |
| Postgres role / database | lowercase, no hyphens (they force quoting in SQL) | `app` / `issues` |

The Docker rows are not decoration. With `build:` and no `image:`, Compose invents a name from
project and service — a second image, built from the same Dockerfile, drifting apart from
anything you tagged by hand. That cost an hour once; `study/05-COMPOSE.md` §4.7 has the
measurement.

`issues.db` is generated, not committed — run `seed.py` to rebuild it identically.
