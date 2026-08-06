# Practice App — the thing you break

Phase 0, Days 1–2. See `PHASE-0.md` for where this sits in the plan.

**You write all of the code in here. Claude explains, reviews, and drills — it does not
produce the code.** That rule is the point of the phase, not a formality.

---

## Why an issue tracker

The domain is irrelevant. What matters is the **surface area of 1.4 patterns the schema
forces you to write.** A `User` table with one column breaks in zero interesting ways.

The app must make all five of these unavoidable:

1. **one-to-many** with default lazy loading — where `DetachedInstanceError` lives, and the
   most common real-world 2.0 bite
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

Six tables.

| Table | What it forces |
|---|---|
| `users` | one-to-many to `comments`; many-to-many to `issues` through the assignment association object |
| `projects` | one-to-many to `issues` |
| `issues` | belongs to a project; has many comments; many-to-many to `labels` through a plain `secondary` table; **self-referential** `blocked_by` / `blocks` |
| `comments` | belongs to an issue and to a user |
| `labels` | many-to-many back to issues |
| `issue_assignments` | the **association object** — `issue_id`, `user_id`, plus real columns of its own: `role` (`"owner"` / `"reviewer"`) and `assigned_at` |

`issue_labels` is a plain association *table* (`secondary=`) — no extra columns.
`issue_assignments` is an association *object* — a mapped class with two `relationship()`s.
Having both, side by side, is deliberate: the difference between them is exactly what
people get wrong, and the errors it produces under 2.0 are the confusing ones.

Do not cut the association object. It is the one everybody cuts.

Database is **SQLite**. No Docker, no Postgres, no infrastructure. That comes in Part B.

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

The warning flag does not catch everything. Two categories only appear as real tracebacks
once 2.0 is installed:

- things that are **gone**, not deprecated (e.g. `engine.execute`)
- things that are **runtime behaviour**, not API surface (`DetachedInstanceError` on a lazy
  load after the session closed; the N+1 blowing up)

You need both passes to reach ten distinct breakages.

---

## The deliverable — `BREAKAGES.md`

Target: **≥10 distinct breakages you personally caused, hit, and fixed.**

One entry per failure. Four fields, no prose:

1. **The 1.4 code** — the actual lines
2. **The exact error text** — pasted, not paraphrased. The error string is what a real user
   would paste into a search box, and in Phase 2 it becomes retrieval *query* text.
3. **The 2.0 fix**
4. **The migration-guide section that explains it** — link + section name

Field 4 is the one you will want to skip and the one that matters most. It is what turns
`BREAKAGES.md` from a diary into a **labelled dataset with known ground-truth source
locations** — the seed of the Phase 2 golden set, and your answer to *"why this corpus?"*

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

### 2. The schema — six tables, bad 1.4 on purpose

Create `experiments/sqlalchemy_1_4_vs_2_0/models.py`.

Tables: `users`, `projects`, `issues`, `comments`, `labels`, plus `issue_labels`
(plain `secondary` table) and `issue_assignments` (association **object** — a mapped class
with `role` and `assigned_at`).

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
  then reads `issue.comments` from the caller — your future `DetachedInstanceError`

**Done when:** it all runs green under 1.4. That's the baseline you're about to destroy.

*Commit:* `feat: 1.4-style query layer`

---

### 5. Turn on echo and count the queries

Re-run the report loop with `create_engine(..., echo=True)`.

Count the `SELECT`s. You should see roughly 1 + 200 + 200. **Write that number down** —
you'll compare against it in step 9, and the before/after is the story you tell an
interviewer.

*Commit:* `docs: record baseline query counts`

---

### 6. Pass 1 — make 1.4 tell you what 2.0 will reject

Still on 1.4. Set `SQLALCHEMY_WARN_20=1` and promote `RemovedIn20Warning` to an error, then
run everything again.

The library now points at your own lines. Each one it flags is a breakage — log it.

**Done when:** you've collected every warning the flag produces, with the file and line.

---

### 7. Start `BREAKAGES.md`

Log the pass-1 findings. Four fields each: the 1.4 code, the **exact** error text (pasted,
not paraphrased), the 2.0 fix, and the migration-guide section that explains it.

Do not skip field 4. It's what makes this a dataset instead of a diary.

*Commit:* `docs: log 1.4 deprecation warnings`

---

### 8. Pass 2 — actually upgrade, and watch it fail for real

- `uv add "sqlalchemy==2.0.36"`
- Run everything again. **Do not fix anything yet.** Read the tracebacks first.

This is where the ones the warning flag *couldn't* catch surface: `engine.execute` is simply
gone; the detached-instance read blows up at runtime; imports move.

**Done when:** you've hit and logged every failure — target ten or more distinct breakages
across both passes.

*Commit:* `docs: log 2.0 hard failures`

---

### 9. Fix them, one at a time, against the official guide

Work through `BREAKAGES.md` top to bottom. For each: apply the 2.0 fix, cite the guide
section, re-run.

Then fix the N+1 with `selectinload` and re-count the queries from step 5. **402 → 2 or 3.**
That number is your Phase 3 rehearsal — the same before/after shape you'll produce when
hybrid search fixes naive retrieval.

**Done when:** everything runs green on 2.0 and `BREAKAGES.md` has a verified fix in every
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
