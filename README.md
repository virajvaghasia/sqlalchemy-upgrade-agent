# sqlalchemy-upgrade-agent

A retrieval system that helps developers upgrade Python code from **SQLAlchemy 1.4 → 2.0**.

The corpus it retrieves from is not scraped. It is **measured**: a deliberately 1.4-style
application in this repo, run against real 2.0, with every failure recorded as it actually
happened. `BREAKAGES.md` is that record, and it becomes the golden dataset the retrieval
system is later evaluated against.

**Status:** Phase 0, Part A complete. Pinned to SQLAlchemy **1.4.52**; breakages verified
against **2.0.51**. See [`ROADMAP.md`](ROADMAP.md) for the six-phase arc.

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

---

## The documents

Read in this order. Section numbers run continuously across the first two, so a reference
to "§18" is unambiguous in either file.

| file | what it is |
|---|---|
| [`ROADMAP.md`](ROADMAP.md) | the six-phase arc, plus a glossary of every AI term used |
| [`PHASE-0.md`](PHASE-0.md) | the current phase in detail, and its deliverables |
| [`CONCEPTS.md`](CONCEPTS.md) | **§0–§15** — the relational model, the ORM layer, the session at runtime |
| [`MIGRATION-2.0.md`](MIGRATION-2.0.md) | **§16–§22** — the 1.4 → 2.0 upgrade: what breaks, what only looks like it does |
| [`BREAKAGES.md`](BREAKAGES.md) | **the Phase 0 deliverable** — 23 verified breakages; seeds the Phase 2 golden dataset |
| [`PRACTICE-APP.md`](PRACTICE-APP.md) | the design of the app under test, and why this schema |
| [`DOCKER-STUDY.md`](DOCKER-STUDY.md) | **§1–§3, one container** — opens with a one-page plain-language summary, then layers, the build cache, build context, base images and wheels, `CMD`/`ENTRYPOINT`, non-root. Every number measured against this repo |
| [`COMPOSE-STUDY.md`](COMPOSE-STUDY.md) | **§4, more than one container** — Compose, networking and DNS, ports, volumes, healthchecks. Numbering continues from `DOCKER-STUDY.md` |
| [`LEARNING-LOG.md`](LEARNING-LOG.md) | what was learned, dated |
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

### Proofs behind the teaching docs

Each prints what the library actually does. Nothing in these asserts a number it didn't measure.

| module | backs | shows |
|---|---|---|
| `explore.py` | `CONCEPTS.md` §0–§13 | every relationship pattern, with the SQL it emits |
| `states.py` | `CONCEPTS.md` §14–§15 | object states, the identity map, expiry, lazy vs `selectinload` vs `joinedload` |
| `migration.py` | `MIGRATION-2.0.md` §16–§21 | nine sections: `query()` vs `select()`, the Result API, autobegin, `future=True`, `.unique()`, the measured N+1, `cascade_backrefs`, and what each tool misses |

### Migration tooling

| module | what it answers |
|---|---|
| `sweep.py` | *what does 2.0 object to across the whole project?* — runs the warning sweep on every module, then collapses occurrences into distinct problems |
| `patterns.py` | the shared list of 1.4 patterns under test. Imported by the two below so a prediction and its verification cannot drift apart |
| `candidates.py` | *which patterns are worth testing?* — classifies each by whether the sweep sees it, `future=True` sees it, or neither |
| `verify_2_0.py` | *what does real 2.0 actually do?* — runs the same patterns on 2.0.51 and reports the real error. `--stubs` emits the `BREAKAGES.md` skeleton |

---

## Three findings worth knowing before you read anything else

**A green 1.4 test suite is not evidence about 2.0.** The 2.0 warnings are off by default.
`app.py` emits 1 warning normally and 5 under `SQLALCHEMY_WARN_20=1` — and both of the
warnings that mark real breakages are in the hidden four. (§19)

**Neither migration tool is the inventory.** The warning sweep misses patterns that raise
without ever warning; `future=True` misses construction-time removals it never evaluates.
Measured: of 24 patterns, 22 fail on real 2.0, and the two tools each miss a different
subset. One pattern is called *safe* by both and still fails. (§20)

**The most dangerous breakage raises nothing.** Under 2.0, an object attached by the
many-to-one side of a relationship (`comment.issue = issue`) is never enrolled in the
session — the `INSERT` silently never runs. Applied to this repo's own seed, every comment
and every assignment disappears while the seed still reports success. (§17)

---

## Conventions

| thing | convention |
|---|---|
| repo / folder / GitHub | `kebab-case`, all identical |
| Python packages | `snake_case` — hyphens are illegal in imports |
| root docs | `SCREAMING_CASE.md` |
| branches | `phase-N/short-topic` |
| commits | [Conventional Commits](https://www.conventionalcommits.org/) — `feat:`, `fix:`, `docs:` |

`issues.db` is generated, not committed — run `seed.py` to rebuild it identically.
