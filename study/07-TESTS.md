# Tests — study notes

Part of [`sqlalchemy-upgrade-agent`](../README.md). **§6** in the infrastructure sequence —
see [`../README.md`](../README.md) for how the numbering works.

Phase 0 Days 8–9 end with *"a PR containing a deliberately failing test, and GitHub refuses to
let it merge."* That needs tests to exist first, which is what this file is about. CI itself is
next.

---

## The short version

- **These tests do not test SQLAlchemy.** They pin claims the docs make, so code drift breaks a
  test instead of quietly making a document wrong (§6.1)
- **A test that cannot fail is worth nothing.** Every claim here was mutation-checked — break
  the thing, watch the right test go red (§6.2)
- **Fixtures use a throwaway database**, never the repo's `issues.db`, or the measured numbers
  in the docs would depend on whether tests had been run (§6.3)
- **`conftest.py`** is where pytest looks for shared fixtures automatically — no import needed
  (§6.3)
- **The tests are written in 2.0-compatible style**, because writing them in the idioms
  [`../deliverables/BREAKAGES.md`](../deliverables/BREAKAGES.md) documents as broken would be absurd (§6.5)

---

## §6 — the test suite

### 6.1 What these tests are for

```
# runnable: uv run pytest --collect-only 2>&1 | grep -E 'collected'
129 tests collected in 0.37s
```

**Collected, not passed — and the difference is the point.** `uv run pytest` reports *114 passed*
here and *111 passed, 3 skipped* on CI, because three `test_index.py` checks skip when no Qdrant
is reachable. A headline number that changes with the environment is not a headline number, so
the block counts what is collected, which does not move. The CI job that verifies every
`# runnable` block found this; reading never would have.

Nine files, and none of them check that SQLAlchemy works:

```
# runnable: uv run pytest --collect-only -q | grep '^tests/'
tests/test_ask.py: 12
tests/test_chunk.py: 27
tests/test_compare_prompts.py: 9
tests/test_corpus.py: 25
tests/test_db_config.py: 5
tests/test_embed.py: 12
tests/test_index.py: 9
tests/test_models.py: 6
tests/test_probe.py: 18
tests/test_seed.py: 6
```

`test_db_config.py`, `test_models.py` and `test_seed.py` are Phase 0's, and are what the rest
of this section describes. The other two arrived with Phase 1 and pin a different kind of claim
— not what the app does, but **what went into the retrieval index**:

- `test_corpus.py` (Step 1) — what is in the corpus and what was deliberately left out.
- `test_chunk.py` (Step 2) — what the chunker must never do: split a code block, sever a
  sentence from the example it introduces, carry a partial block as overlap, or index Sphinx
  markup as if it were content. One of its tests found a bug the eye had missed — RST treats
  overlined and underlined `===` as different heading levels, and conflating them silently
  stripped every section of its parent heading.

The decisions they guard are in [`../phases/PHASE-1.md`](../phases/PHASE-1.md) Steps 1–2; the
shape is the same one §6.1 argues for, which is why they live here rather than somewhere new.

**Every test pins a claim some document makes.** That is the design, and it comes from a real
failure: [`03-PRACTICE-APP.md`](03-PRACTICE-APP.md) asserted *"Six tables"* in prose for 292
lines. There are six mapped classes and **eight** tables. Nothing caught it because nothing
could — prose has no test.

So:

| test | the claim it pins | where the claim lives |
|---|---|---|
| `test_six_mapped_classes_eight_tables` | 6 classes, 8 tables | `03-PRACTICE-APP.md` |
| `test_seed_produces_the_documented_counts` | 200 issues, 710 comments, 387 label links… | `03-PRACTICE-APP.md` |
| `test_association_object_carries_its_own_data` | the association-object distinction | `03-PRACTICE-APP.md` |
| `test_seed_is_deterministic` | every before/after number in the repo | `02-MIGRATION-2.0.md` |
| `test_is_seeded_true_after_seeding` | the guard on the Postgres volume | `05-COMPOSE.md` §4.4 |
| `test_db_url_defaults_to_sqlite` | that Part A measurements are still valid | `../BREAKAGES.md` |
| `test_wait_for_db_gives_up_rather_than_hanging` | retry has a ceiling | `05-COMPOSE.md` §4.2 |

**The rule this encodes:** a number in a doc should have a test under it, in the same way it
should have a command under it. The measurement rule says *derive it*; this says *keep deriving
it.*

### 6.2 A test that cannot fail is worth nothing

Writing a passing test proves nothing on its own — a test asserting `True == True` also passes.
The only way to know a test works is to break the thing it watches.

Three mutations, three different tests caught them:

```
# runnable: change RANDOM_SEED = 20260803 to 12345, then uv run pytest
FAILED tests/test_seed.py::test_seed_produces_the_documented_counts
1 failed, 16 passed
```

```
# runnable: make is_seeded() return False unconditionally, then uv run pytest
FAILED tests/test_seed.py::test_is_seeded_true_after_seeding - assert False is True
1 failed, 16 passed
```

```
# runnable: delete the DATABASE_URL lookup in seed.py, then uv run pytest
FAILED tests/test_db_config.py::test_database_url_overrides_the_default
1 failed, 16 passed
```

Note what each of those says. **One mutation, one failure** — not a cascade. Tests that all fail
together are testing one thing under seven names; tests that fail independently are covering
seven things.

**Do this to any suite you inherit.** Break something obvious and see whether anything goes red.
It is faster than reading the tests and it answers a different question.

### 6.3 Fixtures, and where pytest finds them

`conftest.py` is special: pytest loads it automatically for every test in that directory and
below. Nothing imports it — that is the point.

```python
@pytest.fixture
def engine(db_path):
    eng = create_engine(f"sqlite:///{db_path}")
    yield eng
    eng.dispose()
```

A function name in the argument list is how a test asks for a fixture:

```python
def test_schema_creates_cleanly(engine):   # pytest builds `engine` and passes it in
```

`yield` splits setup from teardown — everything after it runs once the test finishes, pass or
fail. And `tmp_path` is pytest's own fixture handing out a fresh directory per test, which is
what makes the databases disposable.

**Two deliberate choices worth defending:**

**Never the repo's `issues.db`.** A suite that seeded the real file would make the row counts in
`03-PRACTICE-APP.md` and the 204-query measurement in `02-MIGRATION-2.0.md` depend on whether
tests had been run. That is exactly the hidden coupling this repo keeps finding and removing.

**A file, not `:memory:`.** SQLite in memory is faster and would work here. `seed.py` writes a
real file on purpose — `app.py` opens the same database in a separate process — so the tests
run on the same footing as the thing they describe. When the code under test cares about a
detail, the test should not quietly opt out of it.

### 6.4 Making the suite runnable at all

The first run failed before a single test:

```
# runnable: uv run pytest   (before the config existed)
ModuleNotFoundError: No module named 'experiments'
```

`python -m experiments...` works from the repo root because `-m` puts the working directory on
`sys.path`. **pytest does not do that.** Three ways out, and they are not equal:

| | |
|---|---|
| scatter `__init__.py` files | changes the package layout to satisfy a test runner |
| depend on the working directory | works until something runs pytest from elsewhere |
| **declare it** | `pythonpath = ["."]` in `pyproject.toml` — states the fact once |

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
addopts = "-q"
```

`testpaths` stops pytest walking `.venv`. `addopts` makes quiet output the default so a green
run is one line.

### 6.5 The tests must not use the idioms this repo documents as broken

The first draft of the row-count helper used `table.count()`:

```
# runnable: uv run pytest   (first draft)
AttributeError: 'Table' object has no attribute 'count'
2 failed, 15 passed
```

`Table.count()` was removed in 1.4. The replacement is the form that also runs on 2.0:

```python
conn.execute(select(func.count()).select_from(table)).scalar()
```

A test suite for a repo about migrating off legacy idioms should not be written in legacy
idioms. Worth checking any helper you add here against
[`../deliverables/BREAKAGES.md`](../deliverables/BREAKAGES.md) before committing it.

### 6.6 What is deliberately not tested

Saying what a suite does not cover is part of describing it honestly.

- **The 2.0 patterns.** `verify_2_0.py` already runs all 24 against real 2.0 under a pinned
  version, in a throwaway environment. Duplicating that in pytest would mean either installing
  2.0 alongside 1.4 — impossible in one environment — or asserting on strings it already
  measures.
- **The container.** Nothing here builds an image or starts Compose. Those need Docker, which a
  CI runner may not have, and the stack is verified end to end by running it.
- **`app.py`'s output.** It is the 1.4 specimen; its whole value is being unmodified. Pinning
  its behaviour in tests would make the file harder to leave alone.

The gap worth closing next is a test that *fails on purpose*, so CI's blocking behaviour can be
demonstrated. That is Day 8–9's gate, not this file's.

---

## Drills

1. *"Your suite is green. What have you actually learned?"*
2. *"How do you tell whether a test is covering anything?"*
3. *"Why does `conftest.py` need no import?"*
4. *"The tests seed a database. Why not the one the project already has?"*
5. *"`pytest` cannot import your package but `python -m` can. Why?"*

## The docs

- pytest, getting started — https://docs.pytest.org/en/stable/getting-started.html
- Fixtures — https://docs.pytest.org/en/stable/how-to/fixtures.html
- `tmp_path` — https://docs.pytest.org/en/stable/how-to/tmp_path.html
- Configuration — https://docs.pytest.org/en/stable/reference/customize.html
- `monkeypatch` — https://docs.pytest.org/en/stable/how-to/monkeypatch.html
