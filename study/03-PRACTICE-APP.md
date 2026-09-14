# Practice App — the thing you break

Phase 0, Days 1–2. See `phases/PHASE-0.md` for where this sits in the plan.

**You write all of the code in here. Claude explains, reviews, and drills — it does not
produce the code.** That was the rule when this runbook was written, and Part A was built under it.
It changed on 2026-08-12 (`CLAUDE.md`, *Infrastructure — Claude writes it, narrating as it goes*):
Claude now writes and explains. What did not change is the bar: you must be able to defend every
line, which is what Step 10's drill tests.

---

## Stop — how to read this file

| You see | What it is | What it is **not** |
|---|---|---|
| **Step 1 … Step 10** | The Phase 0 Days 1–2 runbook order | Section numbers from `01` / Docker `§` |
| **six mapped classes / eight tables** | Counted from `models.py` — two numbers on purpose | “Six tables” (that claim was wrong once) |
| **`secondary=`** | A junction *table* with no extra columns of its own | An association *object* (mapped class with its own fields) |
| **N+1** | One query for parents + one query **per** parent for children | “Slow SQL” in general |

This file is the **thing you break** — the practice app. Concepts live in `01`; breakages live in
`deliverables/BREAKAGES.md`.

---

## Why an issue tracker

The domain is irrelevant. What matters is the **surface area of 1.4 patterns the schema
forces you to write.** A `User` table with one column breaks in zero interesting ways.

The app must make all five of these unavoidable:

1. **one-to-many** with default lazy loading — where `DetachedInstanceError` lives. That error is
   a session-lifecycle bug that fires identically on 1.4 and 2.0 (`02-MIGRATION-2.0.md` §21), so
   it is here to be understood, not logged as a breakage
2. **many-to-many via a `secondary` table** — exercises `relationship()` string config and
   `backref`
3. **an association object** — a join table that has *extra columns of its own*, so it
   cannot be a plain `secondary=` and must be a mapped class
4. **a self-referential relationship** (`primaryjoin`/`secondaryjoin`) — hardest to get
   right, best interview story
5. **enough rows that a naive loop produces an N+1** — so you *feel* why `joinedload` and
   `selectinload` exist rather than reciting it

An issue tracker hits all five without contriving anything. A music library was the runner-up
but is weak on self-reference.

---

## The schema

**Six mapped classes, eight tables.** The two numbers differ, and the difference is the whole
point of this schema — see below.

```
# runnable: uv run python -c "
#   from experiments.sqlalchemy_1_4_vs_2_0 import models
#   print(len(models.Base.registry.mappers), 'mapped classes')
#   print(len(models.Base.metadata.tables), 'tables')"
6 mapped classes
8 tables
```

Six classes: `User`, `Project`, `Issue`, `Comment`, `Label`, `IssueAssignment`. The two extra
tables — `issue_labels` and `issue_blocks` — exist in the database with no class of their own.

| Table | What it forces |
|---|---|
| `users` | one-to-many to `comments`; many-to-many to `issues` through the assignment association object |
| `projects` | one-to-many to `issues` |
| `issues` | belongs to a project; has many comments; many-to-many to `labels` through a plain `secondary` table; **self-referential** `blocked_by` / `blocks` |
| `comments` | belongs to an issue and to a user |
| `labels` | many-to-many back to issues |
| `issue_assignments` | the **association object** — `issue_id`, `user_id`, plus real columns of its own: `role` (`"owner"` / `"reviewer"`) and `assigned_at` |
| `issue_labels` | **no class.** A bare `secondary=` table: `issue_id`, `label_id`, nothing else |
| `issue_blocks` | **no class.** A bare table whose two foreign keys, `blocker_id` and `blocked_id`, both point at `issues` — the self-referential link |

Eight rows, because there are eight tables. The last two are the ones a "six tables" count misses:
they exist in the database and have no Python class, so they never show up when you list the
classes in `models.py`.

### The two kinds of many-to-many, side by side

`issue_labels` is a plain association *table* (`secondary=`) — no extra columns.
`issue_assignments` is an association *object* — a mapped class with two `relationship()`s.

The database makes the difference obvious. Both are junction tables; only one carries data:

```
# runnable: uv run python -c "
#   import sqlite3
#   c = sqlite3.connect('issues.db')
#   for t in ['issue_labels','issue_assignments']:
#       print(c.execute(f\"select sql from sqlite_master where name='{t}'\").fetchone()[0], '\n')"
CREATE TABLE issue_labels (
	issue_id INTEGER NOT NULL,
	label_id INTEGER NOT NULL,
	PRIMARY KEY (issue_id, label_id),
	FOREIGN KEY(issue_id) REFERENCES issues (id),
	FOREIGN KEY(label_id) REFERENCES labels (id)
)

CREATE TABLE issue_assignments (
	issue_id INTEGER NOT NULL,
	user_id INTEGER NOT NULL,
	role VARCHAR,
	assigned_at DATETIME,
	PRIMARY KEY (issue_id, user_id),
	FOREIGN KEY(issue_id) REFERENCES issues (id),
	FOREIGN KEY(user_id) REFERENCES users (id)
)
```

Both have the same composite primary key and the same two foreign keys. The difference is the
two lines in the middle of the second one: **`role` and `assigned_at` belong to the
relationship itself**, not to the issue and not to the user. There is nowhere else to put them.

**That is the rule, stated as a schema question:** if the join carries nothing but the two
foreign keys, `secondary=` is enough and it needs no class. The moment it has a column of its
own — a role, a timestamp, an amount — it is an entity, and pretending otherwise is what
produces the confusing 2.0 errors.

Having both side by side is deliberate. The difference is exactly what people get wrong.

Do not cut the association object. It is the one everybody cuts.

### How much data

Enough that an N+1 is a measurement rather than a curiosity:

```
# runnable: uv run python -c "
#   import sqlite3; c = sqlite3.connect('issues.db')
#   for t in ['users','projects','labels','issues','comments','issue_labels','issue_assignments','issue_blocks']:
#       print(f'{t:<20}', c.execute(f'select count(*) from {t}').fetchone()[0])"
users                5
projects             3
labels               8
issues               200
comments             710
issue_labels         387
issue_assignments    303
issue_blocks         60
```

200 issues, not 9. The report in step 5 fires **204 queries** against this — 1 for the issues,
200 for `.comments`, 3 for `.project` (`1 + 200 + 3 = 204`, counted in `02-MIGRATION-2.0.md` §21).
Over nine rows that is a curiosity; over two hundred it is a bug you can put a number on.

**Why `.project` costs 3 and not 200.** There are 3 projects. The first time an issue from project
2 reads `.project`, SQLAlchemy loads project 2; every later issue in project 2 finds it already in
the session's identity map and sends no SQL. `.comments` is a collection, which the identity map
cannot answer, so every issue pays.

### Which database

**SQLite by default**, so Part A needs no infrastructure at all — no Docker, no Postgres.

Since Phase 0 Part C the URL is read from the environment, so the same code runs against
Postgres in the Compose stack without editing anything:

```
# runnable: uv run python -c "
#   from experiments.sqlalchemy_1_4_vs_2_0 import seed; print(seed.DB_URL)"
sqlite:///issues.db
```

```
# runnable: docker compose up --build   (DATABASE_URL comes from .env)
database: postgresql+psycopg2://app:***@db:5432/issues
```

The default is what keeps Part A infrastructure-free; the override is what let Part C move the
database into its own container without touching a query. See `05-COMPOSE.md` §4.0.

---

## Write it in genuinely bad 1.4

The exercise is worthless if you accidentally write 2.0-compatible code. Use the old idioms
on purpose:

- `declarative_base()` imported from `sqlalchemy.ext.declarative`, not `sqlalchemy.orm`
- `session.query(Issue).filter(...)` — never `select()`
- `Query.get(id)` — not `session.get()`
- `engine.execute("SELECT ...")` — connectionless execution, **removed outright** in 2.0
- raw SQL strings passed without wrapping them in `text()`
- `relationship("Comment", backref="issue")` — `backref`, not `back_populates`
- default lazy loading everywhere — then close the session and touch `issue.comments`
  afterwards
- a loop over ~200 issues that reads `issue.project.name` inside the loop — that's your N+1

Seed enough data that the N+1 actually costs something. A handful of rows hides it.

---

## Break it in two passes, not one

This is the part people get wrong.

### Pass 1 — still on 1.4

SQLAlchemy 1.4 ships a deprecation mode built for exactly this migration. Set
`SQLALCHEMY_WARN_20=1` and promote `RemovedIn20Warning` to an error. The library then points
at *your own lines* and tells you what 2.0 will reject — before you upgrade. This is why
you are not hunting blind.

### Pass 2 — actually install 2.0

The warning flag does not catch everything. Some 1.4 code is perfectly legal, warns about
nothing, and still fails on 2.0. `candidates.py` counts **5** such patterns, and one of them is
in `BREAKAGES.md` as entry #17:

```
row["id"]     1.4.52: works, no warning      2.0.51: TypeError: tuple indices must be integers or slices, not str
```

Others in that group: `engine.table_names()`, `Query.filter("raw string")`, reading `.title` off a
`Row` without `.scalars()`. Only running the code finds them. Some fail under 1.4's `future=True`
flag too (`engine.table_names()` raises `NotImplementedError` there); `row["id"]` runs fine even
under the flag and fails only on real 2.0 (`02-MIGRATION-2.0.md` §20).

**What Pass 2 is NOT for.** When this runbook was first written, this list also named
`engine.execute` and `DetachedInstanceError` / the N+1. Measured since, all three are wrong
examples: `engine.execute` **does** warn on 1.4 (`RemovedIn20Warning`, so Pass 1 finds it), and the
detached read and the N+1 behave **identically** on 1.4 and 2.0, so they are not breakages at all
(§21).

You need both passes to reach ten distinct breakages.

---

## The deliverable — `deliverables/BREAKAGES.md`

Target: **≥10 distinct breakages you personally caused, hit, and fixed.**

One entry per failure. Four fields, no prose:

1. **The 1.4 code** — the actual lines
2. **The exact error text** — pasted, not paraphrased. The error string is what a real user
   would paste into a search box, and in Phase 2 it becomes retrieval *query* text.
3. **The 2.0 fix**
4. **The migration-guide section that explains it** — link + section name

Field 4 is the one you will want to skip and the one that matters most. It is what turns
`deliverables/BREAKAGES.md` from a diary into a **labelled dataset with known ground-truth source
locations** — the seed of the Phase 2 golden set, and your answer to *"why this corpus?"*

**What was actually delivered:** 23 entries against the target of 10, in eight groups (A–H), each
with the 1.4 code, the real 2.0.51 error, a fix executed on 2.0.51, the docs, and a tier. The fields
grew past four; the file's own header table lists where each one comes from.

---

## Before you start

**Pin Python 3.11.** SQLAlchemy 1.4 on Python 3.13 is a coin flip. `uv python install 3.11`
up front, rather than losing an afternoon to a C-extension build error and thinking it's
your fault.

**Done when:** ≥10 documented breakages, committed and pushed.

---

## Steps

Ten steps. Commit after each one — the lab PC is shared and may be reimaged, and a granular
history is also the thing you'll walk an interviewer through.

Where a step says *ask Claude*, that means ask for an explanation or a review — not for the
code.

---

### 1. Environment

- `uv python install 3.11`
- `uv init` in the repo root, then pin the interpreter to 3.11
- `uv add "sqlalchemy==1.4.52"` — pin the **exact** 1.4 version, so "it broke" is never
  ambiguous later
- `.gitignore` — at minimum `.venv/`, `__pycache__/`, `*.db`

**Done when:** a Python REPL prints `sqlalchemy.__version__` as `1.4.x`.

*Commit:* `chore: pin python 3.11 and sqlalchemy 1.4`

---

### 2. The schema — six mapped classes, eight tables, bad 1.4 on purpose

Create `experiments/sqlalchemy_1_4_vs_2_0/models.py`.

Tables: `users`, `projects`, `issues`, `comments`, `labels`, plus `issue_labels`
(plain `secondary` table), `issue_blocks` (plain table for the self-referential link) and
`issue_assignments` (association **object** — a mapped class with `role` and `assigned_at`). Eight
tables; six of them get a class.

Relationships to wire up:
- `Project.issues` — one-to-many
- `Issue.comments` — one-to-many
- `Comment.author` → `User`
- `Issue.labels` ↔ `Label.issues` — many-to-many via `secondary=issue_labels`
- `Issue.assignments` → `IssueAssignment` → `User` — the association object
- `Issue.blocked_by` / `Issue.blocks` — **self-referential many-to-many** via
  `secondary=issue_blocks`, needs explicit `primaryjoin` / `secondaryjoin` (**not**
  `remote_side` — that's the adjacency-list knob for a self-referential *one*-to-many)

Use the deprecated idioms deliberately: `declarative_base()` from
`sqlalchemy.ext.declarative`, `backref` rather than `back_populates`, default lazy loading
everywhere.

**Done when:** `Base.metadata.create_all(engine)` builds the SQLite file without error.
Open the `.db` in any SQLite browser and check the foreign keys landed — this is your home
turf, use it.

*The self-referential one is the only genuinely fiddly part. If the `primaryjoin` /
`secondaryjoin` config fights you, ask Claude to explain what it's actually doing before you
brute-force it.*

*Commit:* `feat: 1.4-style issue tracker schema`

---

### 3. Seed data — enough to hurt

`seed.py`. Roughly: 5 users, 3 projects, **~200 issues**, 2–5 comments each, 8 labels
scattered across issues, assignments with mixed roles, and some issues blocking others.

Don't hand-write 200 rows — generate them in a loop.

**Done when:** `SELECT COUNT(*)` on `issues` returns ~200 and the join tables are populated.

*Commit:* `feat: seed data`

---

### 4. The app — write the queries the old way

`app.py`. Half a dozen functions that *do* something, all in 1.4 style:

- list open issues for a project — `session.query(Issue).filter(...)`
- fetch one issue — `Query.get(id)`, not `session.get()`
- a raw-SQL count — `engine.execute("SELECT COUNT(*) FROM issues")`, string not wrapped in
  `text()`
- a report loop over all ~200 issues that reads `issue.project.name` and `len(issue.comments)`
  **inside the loop** — your N+1
- something that returns an `Issue` from a function, **after the session has closed**, and
  then reads `issue.comments` from the caller — your `DetachedInstanceError` (it fires on 1.4
  already; that is the point of §21)

**Done when:** it all runs green under 1.4. That's the baseline you're about to destroy.

*Commit:* `feat: 1.4-style query layer`

---

### 5. Turn on echo and count the queries

Re-run the report loop with `create_engine(..., echo=True)`.

Count the `SELECT`s. **Predict first**: two relationships per issue suggests `1 + 200 + 200 = 401`.
The measured count is **204**, and the 197-query gap is the identity map answering `.project` from
memory (see "How much data" above). **Write your own number down** — you'll compare against it in
step 9, and the before/after is the story you tell an interviewer.

*Commit:* `docs: record baseline query counts`

---

### 6. Pass 1 — make 1.4 tell you what 2.0 will reject

Still on 1.4. Set `SQLALCHEMY_WARN_20=1` and promote `RemovedIn20Warning` to an error, then
run everything again.

The library now points at your own lines. Only a `RemovedIn20Warning` marks something that stops
working; `MovedIn20Warning` is a one-line import move and `LegacyAPIWarning` still works on 2.0
(`02-MIGRATION-2.0.md` §19). Log the first kind as breakages. Filter by the **exact** class name:
`MovedIn20Warning` is a subclass of `RemovedIn20Warning`, so an `isinstance` check puts import
moves in your breakage list.

**Done when:** you've collected every warning the flag produces, with the file and line.

---

### 7. Start `deliverables/BREAKAGES.md`

Log the pass-1 findings. Four fields each: the 1.4 code, the **exact** error text (pasted,
not paraphrased), the 2.0 fix, and the migration-guide section that explains it.

Do not skip field 4. It's what makes this a dataset instead of a diary.

*Commit:* `docs: log 1.4 deprecation warnings`

---

### 8. Pass 2 — actually upgrade, and watch it fail for real

- `uv add "sqlalchemy==2.0.51"` — the version every measured error in `BREAKAGES.md` came from
  (`PIN` in `verify_2_0.py`, `D16`). This runbook first said `2.0.36`; the project later pinned 2.0.51,
  because `BREAKAGES.md` quotes exact error strings and those can change between releases.
- Run everything again. **Do not fix anything yet.** Read the tracebacks first.

This is where the ones the warning flag *couldn't* catch surface: legal-looking 1.4 code such as
`row["id"]` that warned about nothing and now raises. (What does *not* newly surface here: the
detached read and the N+1, which already fail the same way on 1.4, and `engine.execute`, which Pass 1
already flagged.)

**This repo did not do this step on its own environment.** The project stays on 1.4.52 by design
(`D17`: the app is the specimen and must stay broken), and the 2.0 errors were collected by running each pattern in a throwaway 2.0.51 interpreter
(`uv run --no-project --with 'sqlalchemy==2.0.51'`, `verify_2_0.py`) instead.

**Done when:** you've hit and logged every failure — target ten or more distinct breakages
across both passes.

*Commit:* `docs: log 2.0 hard failures`

---

### 9. Fix them, one at a time, against the official guide

Work through `deliverables/BREAKAGES.md` top to bottom. For each: apply the 2.0 fix, cite the guide
section, re-run.

Then fix the N+1 with `selectinload` and re-count the queries from step 5. **204 → n**, where n is
what you count. (This line used to say "402 → 2 or 3": 402 matched neither the estimate, 401, nor the
measurement, 204, and the "after" had never been counted. It still has not been counted in this
repo, so it is written as n.) That number is your Phase 3 rehearsal — the same before/after shape
Phase 3 later produced for retrieval (`15-IMPROVE.md`).

**Done when:** everything runs green on 2.0 and `deliverables/BREAKAGES.md` has a verified fix in every
entry.

*Commit:* `fix: migrate to sqlalchemy 2.0`

---

### 10. The drill

Push everything, then tell Claude you're ready. You get grilled, cold, no notes:

- name three things that broke and explain **why the library changed them**
- why is `secondary=` wrong for `issue_assignments`?
- why did the detached read work inside the function and fail outside it?
- what does `selectinload` actually emit, and when is `joinedload` the better call?

**Phase 0 Part A is done when you can answer those without looking.** Then you go to the lab.
