# Migration — SQLAlchemy 1.4 → 2.0

The companion to `CONCEPTS.md`. That file covers SQLAlchemy **as it is** (§0–§15: the
relational shapes, the ORM layer, the session at runtime). This one covers **why it changed**,
and — the part that matters more — how to tell a real breakage from a style preference.

Section numbering continues from `CONCEPTS.md`, so a reference to "§18" is never ambiguous.

| | file | sections |
|---|---|---|
| the model, the ORM, the session | `CONCEPTS.md` | §0 – §15 |
| **the 1.4 → 2.0 upgrade** | **this file** | **§16 – §22** |

---

## Contents

- **§16 — Why 2.0 exists: one API instead of two**
- **§17 — The Result API: rows, scalars, and the most common 2.0 papercut**
- **§18 — Autobegin: when a transaction actually starts**
- **§19 — Reading the warnings: four classes, two of them silent by default**
- **§20 — `future=True`: run 2.0's rules without installing 2.0**
- **§21 — What 2.0 does *not* fix**
- **§22 — The migration recipe, in order**
- **Predictions** — *deliberately unanswered; you settle these by running the upgrade*

Everything labelled `# runnable` names a command you can paste. Two commands produce all of
it:

```bash
uv run python -m experiments.sqlalchemy_1_4_vs_2_0.migration

SQLALCHEMY_WARN_20=1 uv run python -W always::DeprecationWarning \
    -m experiments.sqlalchemy_1_4_vs_2_0.app
```

**How this file ends.** The predictions at the bottom stay unanswered on purpose. §16–§22
exist so those predictions are *informed* rather than guessed; the answers themselves you
produce by running the upgrade. That exercise is the highest-value hour in Phase 0, and
reading the answer destroys it.

---

## §16 — Why 2.0 exists: one API instead of two

### The problem 2.0 was built to solve

SQLAlchemy 1.x grew two parallel APIs for the same job, and you had to know which world you
were standing in at all times:

```
# illustration — two ways to run one query in 1.x

  CORE                                     ORM
  ────                                     ───
  engine.execute("SELECT * FROM issues")   session.query(Issue).all()
        │                                        │
        ├─ returns Row tuples                    ├─ returns Issue objects
        ├─ connection checked out invisibly      ├─ connection from the session
        ├─ transaction boundary unclear          ├─ transaction from the session
        └─ .filter? no — .where                  └─ .where? no — .filter
```

Two APIs meant two mental models, two vocabularies for the same idea (`filter` vs `where`),
and constant low-grade friction of the form *"is this a Core thing or an ORM thing?"*

Worse, `engine.execute()` did **connectionless execution**: it quietly checked out a
connection from the pool, ran the statement, and handed it back. Convenient — and it made
*"when did my transaction begin, and when will it end?"* genuinely hard to answer from reading
the code.

### What 2.0 actually did

**Unification.** One way to build a statement — `select()`. One way to run it — `.execute()`.
The same construct works in Core and in the ORM. Connections and transactions become things
you can see on the page.

```python
# illustration
# 1.x style
session.query(Issue).filter(Issue.status == "open").all()

# 2.0 style
session.execute(select(Issue).where(Issue.status == "open")).scalars().all()
```

That looks like a big change. **Measure what each one sends before you believe it:**

```
# runnable   →   uv run python -m experiments.sqlalchemy_1_4_vs_2_0.migration     (§1)

1.x  session.query(Issue).filter(...)
     SELECT issues.id AS issues_id, issues.title AS issues_title, ... FROM issues WHERE issues.status = ?

2.0  session.execute(select(Issue).where(...))
     SELECT issues.id,              issues.title,              ... FROM issues WHERE issues.status = ?

     identical from FROM onward:        True
     identical from WHERE onward:       True
     identical including column labels: False

     Query.get(1) vs Session.get(Issue, 1) — identical SQL: True
```

**Same tables. Same WHERE. Same parameters. Same query plan.** The only difference is that
`Query` adds `AS issues_id` column labels and `select()` doesn't — a labelling difference, not
a difference in work performed.

This is the single most useful fact to hold before migrating:

> **`session.query()` → `select()` is a change in how you write, not in what runs.**

No query plans change. No performance changes. Nothing silently returns different rows. Which
is exactly why it emits **no deprecation warning at all** (§19) — and why calling it a
"breakage" would be wrong.

### The renames worth memorising

| 1.x | 2.0 | is it a breakage? |
|---|---|---|
| `session.query(Model)` | `select(Model)` + `session.execute()` | **no** — Query still works in 2.0 |
| `.filter(...)` | `.where(...)` | no — vocabulary alignment with Core |
| `Query.get(pk)` | `session.get(Model, pk)` | no — warns, still runs |
| `engine.execute("...")` | `with engine.connect() as c: c.execute(text("..."))` | **yes — this one actually fails** |
| `from sqlalchemy.ext.declarative import declarative_base` | `from sqlalchemy.orm import declarative_base` | no — moved, one-line fix |

Four of those five are cosmetic. **One is not.** Telling them apart is the entire skill this
chapter teaches, and §19 is how you do it mechanically instead of by eye.

**Drill.**

1. Name the two things 1.x had two of, that 2.0 has one of.
2. `session.query(Issue)` and `select(Issue)` produce near-identical SQL. What follows from that about how urgent, and how risky, this migration is?
3. Of the five renames in the table above, which is the odd one out and why?

<details>
<summary>Answers</summary>

**1. Short answer:** two ways to **build** a statement, and two ways to **run** one.

| | 1.x | 2.0 |
|---|---|---|
| build | `session.query(Issue)` *or* a Core `select()` | `select(Issue)` — always |
| run | `engine.execute(...)` *or* `.all()` on a Query | `.execute(...)` — always |

There's a third, quieter unification: **connection handling.** `engine.execute()` grabbed and
released a connection invisibly; 2.0 makes you write `with engine.connect() as conn:` so the
boundary is visible in the source.

**2. Short answer:** not urgent, and not risky. It's a rename, not a rewrite.

The SQL is identical, so there are no query-plan changes, no performance changes, and no
behavioural changes. Nothing silently returns different rows. That is a completely different
category of migration from one that alters what the database does.

Two practical consequences:

- **You can migrate incrementally**, file by file. A half-migrated codebase is not a broken
  codebase — `Query` and `select()` coexist happily in the same session.
- **It can wait.** Contrast with `engine.execute("...")`, which stops working entirely and must
  be fixed *before* 2.0 will run at all.

Knowing the difference is the whole skill. Treating a style change as an emergency burns a
week; treating a real removal as a style change breaks production.

**3. Short answer:** `engine.execute("...")` — it's the only one that **actually stops
working**.

```
session.query()          still works in 2.0   ← style
.filter()                still works in 2.0   ← style
Query.get()              still works in 2.0   ← style, warns
declarative_base import  still works in 2.0   ← moved, warns
engine.execute("...")    REMOVED              ← breakage
```

And note the asymmetry that makes eyeballing unreliable: `session.query()` *looks* the most
old-fashioned of the five and is the least broken, while `engine.execute()` looks like
perfectly ordinary code and is the one that fails.

</details>

---

## §17 — The Result API: rows, scalars, and the most common 2.0 papercut

### The thing that will bite you first

You migrate a query from `session.query()` to `select()`, it runs without error, and then this
happens:

```python
# illustration
issues = session.execute(select(Issue)).all()
issues[0].title
# AttributeError: 'Row' object has no attribute 'title'
```

Nothing is broken. You've just met the one genuine semantic difference between the two APIs.

### Why it happens

`session.query(Issue).all()` was an *ORM* API, so it did an ORM-shaped thing: it handed back
`Issue` objects.

`select()` is a *Core* construct, so `.execute()` does a Core-shaped thing: it hands back
**rows**. And a row containing one column is still a row — a one-element tuple with your
object inside it.

```
# runnable   →   uv run python -m experiments.sqlalchemy_1_4_vs_2_0.migration     (§2)

session.execute(select(Issue)).all()
  element type : Row                    <- a Row, NOT an Issue
  first element: (<Issue 1 'issue 1'>,)  <- note the trailing comma: a 1-tuple
  rows[0][0]   : <Issue 1 'issue 1'>     <- the Issue is INSIDE it

session.execute(select(Issue)).scalars().all()
  element type : Issue
  first element: <Issue 1 'issue 1'>
```

`.scalars()` says *"take the first column of every row and give me that."* With a single-entity
select, the first column is your object, so you get objects back.

> **`.execute()` returns rows. `.scalars()` unwraps them. `session.query()` did both in one
> step, which is why the extra call feels like it shouldn't be necessary.**

### The full result vocabulary

This is worth learning as a set, because each one encodes a different expectation about how
many rows you're going to get — and 2.0 will enforce it:

| call | returns | use when |
|---|---|---|
| `.all()` | list of `Row` | you selected several columns and want tuples |
| `.scalars().all()` | list of objects | **the normal ORM case** — one entity selected |
| `.scalars().first()` | object or `None` | you want one and don't care if there are more |
| `.scalar_one()` | object, **raises** otherwise | exactly one row must exist |
| `.scalar_one_or_none()` | object or `None`, raises on >1 | at most one row must exist |

The last two are an upgrade over anything 1.x offered, and worth adopting deliberately rather
than reflexively reaching for `.first()`:

```
# runnable   →   the same migration.py §2
scalar_one_or_none() on a 1-row result -> <Issue 1 'issue 1'>
scalar_one() on a 3-row result         -> MultipleResultsFound
    Multiple rows were found when exactly one was required
```

`.first()` on a query you *believed* returned one row will silently hand you an arbitrary one
when your assumption is wrong. `.scalar_one()` states the expectation in code and makes the
database enforce it. **That's a bug caught at the point of the wrong assumption instead of
three functions later.**

**Drill.**

1. Why does `session.execute(select(Issue)).all()` not give you `Issue` objects?
2. `.first()` vs `.scalar_one()` — when is the difference a bug you'd rather have?
3. You select two columns instead of a whole entity: `select(Issue.id, Issue.title)`. Should you call `.scalars()`?

<details>
<summary>Answers</summary>

**1. Short answer:** because `select()` is a Core construct, and Core returns **rows**.

`session.query()` was an ORM API and quietly did two jobs: run the query, *and* unwrap the
single column into an object. `select()` + `.execute()` only does the first. The object is
still there — it's inside a one-element tuple:

```
(<Issue 1 'issue 1'>,)
 └──── your object ──┘└ the tuple
```

`.scalars()` takes column 0 of every row, which restores the old behaviour. The API didn't get
worse; it got **honest about the two steps** it was always doing.

**2. Short answer:** whenever "exactly one" is an assumption your code depends on.

```python
user = session.execute(select(User).where(User.email == addr)).scalars().first()
#  two users somehow share an email  ->  you silently get an arbitrary one,
#  and the bug shows up somewhere else entirely, much later

user = session.execute(select(User).where(User.email == addr)).scalar_one()
#  two users somehow share an email  ->  MultipleResultsFound, right here
```

`.first()` says *"give me one."* `.scalar_one()` says *"there is exactly one — prove it."* When
a unique constraint is missing or a join fanned out unexpectedly, the second one tells you at
the point of the broken assumption. The first hands you plausible-looking wrong data.

**3. Short answer: no.** `.scalars()` would throw away `title`.

```python
rows = session.execute(select(Issue.id, Issue.title)).all()
rows[0]              # (1, 'issue 1')     ← a real 2-column row
rows[0].title        # 'issue 1'          ← Rows support attribute access too

# with .scalars() you would get: [1, 2, 3]  — only column 0. The titles are gone.
```

The rule: **`.scalars()` is for when you selected one thing.** Selected several? Keep the rows
— and note they're not plain tuples, they support `.title`-style access as well as indexing.

</details>

---

## §18 — Autobegin: when a transaction actually starts

### "Removing autocommit" is a misleading way to describe it

You'll read that 2.0 "removes autocommit." That phrasing suggests something was taken away.
What actually happened is that the transaction boundary became **predictable** rather than
implicit.

In 1.x, `engine.execute()` ran statements in a way where each one might commit on its own,
depending on configuration. Reading the code did not tell you where a transaction started or
ended.

2.0 uses **autobegin**: a Session has no transaction until it needs one, then it opens one and
keeps it until you `commit()` or `rollback()`.

```
# runnable   →   uv run python -m experiments.sqlalchemy_1_4_vs_2_0.migration     (§3)

fresh session, nothing done yet   in_transaction: False
after a single SELECT             in_transaction: True
after commit()                    in_transaction: False
```

Read that middle line carefully. **A plain `SELECT` opened a transaction.** Nothing was
explicitly begun; the Session opened one the moment it first needed to talk to the database.

### The two consequences that surprise people

**1. Your reads are inside a transaction.** A long-lived session that only reads is still
holding a transaction open — which on a real database (not SQLite) can hold locks and block
`VACUUM`, and will make your reads see a snapshot that gets staler the longer you hold it.
Reading is not free of transaction semantics.

**2. `commit()` matters even for read-only work.** Not to save anything — there's nothing to
save — but to **end the transaction** so the next read starts fresh. This is the same mechanism
as `expire_on_commit` in `CONCEPTS.md` §15, seen from the other side: the commit both ends the
transaction and marks your cached objects stale, precisely because a new transaction may see
different data.

> **`with Session(engine) as session:` and an explicit `commit()` is the 2.0 shape, and it is
> not ceremony. It is what makes the transaction boundary a thing you can see.**

**Drill.**

1. A brand-new Session — is it in a transaction? What puts it in one?
2. You have a session that only ever runs SELECTs. Is calling `commit()` pointless?

<details>
<summary>Answers</summary>

**1. Short answer:** no. The first statement it sends does.

```
constructed        in_transaction: False   ← nothing has happened yet
one SELECT later   in_transaction: True    ← autobegin fired
after commit()     in_transaction: False   ← closed again
```

That's autobegin: the transaction is opened lazily, on first use, and never before. You don't
call `begin()` and there's no window where you're "outside" a transaction while still using
the session.

**2. Short answer:** no — it ends the transaction, which matters for reasons that have nothing
to do with saving.

A read-only session that never commits holds one transaction open for its entire life. Three
consequences:

- **Your data goes stale.** Under a repeatable-read isolation level you keep seeing the
  snapshot from your first query, no matter what else commits. Hours later you're reading
  hours-old data and everything looks fine.
- **You hold database resources.** On Postgres, a long-open transaction blocks vacuuming of
  rows your snapshot might still need — a classic cause of table bloat traced back to an app
  that "only reads."
- **Your objects never refresh.** `expire_on_commit` (`CONCEPTS.md` §15) fires at commit. No
  commit, no expiry, so cached attribute values are never re-read.

The 1.x habit of leaving a session open indefinitely was survivable partly *because*
autocommit blurred the boundaries. With explicit transactions, "when does this end?" becomes a
question you have to answer — which is the point.

</details>

---

## §19 — Reading the warnings: four classes, two of them silent by default

### The tool

SQLAlchemy 1.4 will tell you what 2.0 thinks of your code, before you upgrade anything:

```bash
SQLALCHEMY_WARN_20=1 python -W always::DeprecationWarning -m your.module
```

Both halves are load-bearing, and this is the part people get wrong:

- `SQLALCHEMY_WARN_20=1` tells **SQLAlchemy** to emit the 2.0 deprecation warnings at all.
- `-W always::DeprecationWarning` tells **Python** to actually display them. Python hides
  `DeprecationWarning`s by default.

### Why this matters more than it sounds

Run this project's `app.py` both ways and count what you get:

```
# runnable   →   with and without the flag, on the same file

WITHOUT SQLALCHEMY_WARN_20:
   1 MovedIn20Warning

WITH SQLALCHEMY_WARN_20=1:
   1 MovedIn20Warning
   2 LegacyAPIWarning
   2 RemovedIn20Warning        ← the only two that mark a real breakage
```

**The two warnings that mark actual breakages are invisible by default.** Run your test suite
normally, watch it pass, and you have learned nothing about whether your code survives 2.0.

> **A green test suite on 1.4 is not evidence about 2.0. You have to ask.**

That's the same lesson as `CONCEPTS.md` §12 (`check.py` printing OK while the schema was
broken), in a different costume: *a passing run only tells you the thing you ran didn't fail.*

### The four classes, and what each one promises

```
# runnable   →   SQLALCHEMY_WARN_20=1 uv run python -W always::DeprecationWarning \
#                  -m experiments.sqlalchemy_1_4_vs_2_0.app

models.py:8   MovedIn20Warning:   declarative_base() is now available as
                                  sqlalchemy.orm.declarative_base()
app.py:68     LegacyAPIWarning:   Query.get() ... is now available as Session.get()
app.py:79     RemovedIn20Warning: Engine.execute() ... will be removed in 2.0
app.py:79     RemovedIn20Warning: Passing a string to Connection.execute() is deprecated
                                  and will be removed in version 2.0
```

**The class name is the entire message.** Learn to read it and you can triage a codebase in
minutes rather than days:

| warning class | what it promises | urgency | `BREAKAGES.md`? |
|---|---|---|---|
| `RemovedIn20Warning` | **this stops working in 2.0** | fix before upgrading | **yes** |
| `MovedIn20Warning` | same thing, new import path | one-line fix, any time | no |
| `LegacyAPIWarning` | works in 2.0, no longer the recommended way | at leisure | no |
| *(no warning at all)* | fully supported in 2.0 | not a migration item | no |

**The fourth row is the one people miss.** `session.query(Model)` — the most obviously
"1.4-looking" construct in this codebase — emits **nothing**, even under `WARN_20`, because
1.x `Query` is fully supported in 2.0. It looks the most legacy and is the least broken.

> **"Looks old" is not a measurement. Run the flag.**

Step 4 of this project nearly got this wrong in both directions: two of five suspicious
patterns turned out not to be version issues at all, and the one that reads most innocently
(`engine.execute("SELECT ...")`) turned out to produce **two** separate `RemovedIn20Warning`s
from a single line.

**Drill.**

1. `RemovedIn20Warning` vs `LegacyAPIWarning` — what does each promise about 2.0?
2. Your test suite passes on 1.4 with no warnings printed. What have you learned about 2.0?
3. `session.query(Model)` looks like the most 1.4-ish thing in the codebase and emits no warning at all. What does that tell you?
4. One line produced *two* `RemovedIn20Warning`s. Why would a single call be two separate problems?

<details>
<summary>Answers</summary>

**1. Short answer:** `RemovedIn20Warning` = *it will stop working.* `LegacyAPIWarning` = *it
will keep working, but it's no longer the recommended way.*

One is a deadline; the other is advice.

Only the first belongs in `BREAKAGES.md` — that file is for things that worked in 1.4 and
**stopped working** in 2.0. Filling it with style preferences would seed the Phase 2 retrieval
corpus with questions no upgrading developer actually asks, and you'd then evaluate the system
against them and score yourself on the wrong thing.

**2. Short answer: nothing at all.**

The 2.0 warnings are **off by default**, and Python hides `DeprecationWarning`s on top of that.
Measured on this repo's own `app.py`: 1 warning without the flag, 5 with it — and *both*
`RemovedIn20Warning`s, the only real breakages, are in the hidden four.

A clean run proves your code works **on 1.4**. That was never in question. The question is what
happens on 2.0, and answering it requires opting in:

```bash
SQLALCHEMY_WARN_20=1 python -W always::DeprecationWarning -m your.module
```

**3. Short answer:** that appearance and compatibility are unrelated, and only one of them is
measurable.

`session.query()` is 1.x *style* but not 1.x-*only*. It's fully supported in 2.0, so there's no
warning to emit — measured directly: it runs fine on a `future=True` session (§20).

Had you triaged by eye, you'd have flagged it as a breakage and been wrong twice: wrong that it
breaks, and wrong to spend migration time on it ahead of `engine.execute()`, which actually
does break.

**4. Short answer:** because `engine.execute("SELECT ...")` does **two** deprecated things at
once.

```python
engine.execute("SELECT count(*) FROM issues")
#      ▲        ▲
#      │        └── problem 2: a bare string instead of text(...)
#      └── problem 1: connectionless execution — no explicit connection
```

Each has its own separate 2.0 replacement, so each gets its own warning:

```python
# the 2.0 form fixes both
with engine.connect() as conn:                            # ← explicit connection
    conn.execute(text("SELECT count(*) FROM issues"))     # ← explicit text()
```

Worth internalising: **warning count ≠ line count.** One call site can hold several
independent migration problems, so "how many lines must I change" systematically
underestimates the work.

*(Why was the bare string deprecated at all? Because `execute("...")` was ambiguous — it might
be a SQL string, or a construct. `text()` makes "this is raw SQL, I mean it" explicit, which
also makes raw SQL grep-able in a codebase audit.)*

</details>

---

## §20 — `future=True`: run 2.0's rules without installing 2.0

### The most useful migration fact in this document

SQLAlchemy **1.4 ships 2.0's behaviour behind a flag.** Pass `future=True` and that engine or
session enforces 2.0's rules immediately — on the version you already have installed:

```python
# illustration
engine  = create_engine("sqlite://", future=True)
Session = sessionmaker(bind=engine, future=True)
```

Measured on 1.4.52, the same call with and without it:

```
# runnable   →   uv run python -m experiments.sqlalchemy_1_4_vs_2_0.migration     (§4)

normal engine : sqlalchemy.engine.base.Engine
future engine : sqlalchemy.future.engine.Engine

engine.execute("SELECT 1") on normal 1.4 engine  -> worked (silently, unless WARN_20 is set)
engine.execute("SELECT 1") on future=True engine -> NotImplementedError:
                                 This method is not implemented for SQLAlchemy 2.0.
```

**You can hit the 2.0 breakage today, on 1.4.52.** No upgrade, no reinstall, no risk to
anything else in the project. And it reverses instantly — delete the flag.

### Equally important: what it does *not* reject

```
# runnable   →   the same migration.py §4
session.query(Project) on a future=True session -> [<Project 1 'apollo'>]
```

`Query` runs perfectly under 2.0 rules. This is the empirical proof of §16's claim that the
query-style migration is cosmetic — you don't have to take the docs' word for it, you can watch
`future=True` decline to complain.

> **`future=True` is a truth-teller in both directions: it fails what will fail, and it accepts
> what will be accepted.**

### Why this changes the shape of the whole migration

Without it, an upgrade is a cliff: you bump the version, and every behaviour changes at once.
When something fails you're debugging against a moving target, with the old version already
uninstalled.

With it, the upgrade becomes incremental and reversible:

```
1. SQLALCHEMY_WARN_20=1         →  inventory: what does 2.0 object to?        (§19)
2. fix every RemovedIn20Warning →  the tier that actually breaks
3. flip future=True             →  prove the fixes hold under 2.0's rules,
                                   while still running 1.4
4. bump to 2.0                  →  should be uneventful by now
```

Step 3 is the one people skip, and it's the one that converts *"I hope this works"* into *"I
watched it work."*

**Drill.**

1. What does `future=True` do, and why would you use it *before* upgrading?
2. `future=True` accepts `session.query()` and rejects `engine.execute()`. What does that pair of results tell you that a docs page can't?

<details>
<summary>Answers</summary>

**1. Short answer:** it makes a 1.4 engine or session enforce 2.0's rules, so you can hit 2.0's
errors while still running 1.4.

Measured: `engine.execute("SELECT 1")` works on a normal 1.4 engine and raises
`NotImplementedError: This method is not implemented for SQLAlchemy 2.0.` on a `future=True`
one.

**Why before upgrading** — it separates *finding* problems from *being broken by* them:

| | without `future=True` | with it |
|---|---|---|
| when you find out | during the upgrade | whenever you choose |
| how many things changed at once | everything | one flag |
| can you go back? | reinstall the old version | delete the flag |
| is 1.4 still working meanwhile? | no, it's gone | yes |

**2. Short answer:** that the classification is *true of your actual code*, not true in general.

A docs page tells you `Query` is still supported. `future=True` demonstrates it **on your
models, your session, your query**, in your codebase. Those aren't the same claim — the docs
describe the library, the flag tests your usage of it.

It also catches the thing docs can't: constructs you didn't know you were using. Nobody greps
for "connectionless execution"; you find it when the flag raises on a line you'd read past a
hundred times.

</details>

---

## §21 — What 2.0 does *not* fix

Not every problem in a 1.4 codebase is a 1.4 problem. Two of the ugliest things in this
project survive the upgrade completely untouched:

| looks like a version problem | actually is | where it's proven |
|---|---|---|
| the N+1 in `issue_report()` | a **loading-strategy** bug — equally slow in both | `CONCEPTS.md` §15 |
| `DetachedInstanceError` | a **session-lifecycle** bug — fires identically in 1.4 | `CONCEPTS.md` §14 |

Both were *measured* under 1.4 in Part 3 of `CONCEPTS.md`, before either was blamed on the
version. Neither emits a migration warning, because neither is a migration issue. Upgrade to
2.0 and the N+1 still fires 201 queries; the detached object still raises.

### Why this distinction is the whole project

`BREAKAGES.md` becomes the Phase 2 golden dataset. Every entry in it is a question a real
developer asks while upgrading. Put *"why is my loop slow?"* in it and you've seeded your
retrieval corpus with a question that has nothing to do with upgrading — and you will then
evaluate your system against it and score yourself on the wrong thing.

> **A breakage is something that worked in 1.4 and stopped working in 2.0. Not "something bad I
> found while migrating."**

Of the five suspicious patterns Step 4 examined, measurement moved **two** off the breakage
list entirely. Both would have looked perfectly plausible sitting in the corpus.

**Drill.**

1. Give the one-sentence test for whether something belongs in `BREAKAGES.md`.
2. The N+1 and `DetachedInstanceError` both surfaced during migration work. Why does neither qualify?
3. Why does a wrong entry in `BREAKAGES.md` cost more than a missing one?

<details>
<summary>Answers</summary>

**1. Short answer:** *did this work in 1.4 and stop working in 2.0?* Yes → it belongs. Anything
else → it doesn't.

Note what that excludes: things that are slow in both, things that were always wrong, things
that merely became unfashionable. **"I encountered it during the upgrade" is not the test** —
that's a fact about your calendar, not about the code.

**2. Short answer:** both fail identically in 1.4, so the version changed nothing about them.

| | in 1.4 | in 2.0 | version-dependent? |
|---|---|---|---|
| N+1 in a loop | 201 queries | 201 queries | no — a loading-strategy bug |
| `DetachedInstanceError` | raises (§14 traced it) | raises | no — a lifecycle bug |

They're real bugs, worth fixing, and worth understanding — they're just not *upgrade* bugs, and
the corpus is specifically about upgrading.

The failure mode to guard against: you spend a week migrating, you meet several problems, and
they all get filed under "2.0 issues" because that's what you happened to be doing at the time.
Measurement is what separates them, which is why `CONCEPTS.md` traced both under 1.4 **before**
any 2.0 work started.

**3. Short answer:** because a missing entry is a gap, but a wrong entry corrupts the thing you
grade yourself with.

A missing breakage means your system can't answer one question. Bad, bounded, and you'll notice
when someone asks it.

A wrong entry is worse in a way that compounds:

- it goes into the golden dataset as a question with a "verified" answer
- Phase 2 evaluates retrieval against it, so the score is measuring the wrong target
- you tune the system to do better on it
- **you now have evidence that your system is improving, generated by a question no real user
  asks**

That's the "grades your own homework with your own answer key" failure the project's design
notes warn about, arrived at from a different direction. The defence is the same in both cases:
measure before you classify.

</details>

---

## §22 — The migration recipe, in order

Everything above, as a sequence. The ordering is the content — each step exists to make the
next one boring.

```
┌─ 1. INVENTORY ─────────────────────────────────────────────────────────┐
│  SQLALCHEMY_WARN_20=1 python -W always::DeprecationWarning -m your.mod │
│                                                                        │
│  Read-only. Changes nothing. Costs one command.                        │
│  Output: every construct 2.0 objects to, classified by tier.    (§19)  │
└────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─ 2. TRIAGE ────────────────────────────────────────────────────────────┐
│  RemovedIn20Warning  →  must fix.  These are the BREAKAGES.md entries. │
│  MovedIn20Warning    →  one-line import change.                        │
│  LegacyAPIWarning    →  optional.                                      │
│  no warning          →  not a migration item at all.            (§19)  │
└────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─ 3. FIX THE REMOVALS ──────────────────────────────────────────────────┐
│  engine.execute("...")  →  with engine.connect() as c:                 │
│                                c.execute(text("..."))           (§16)  │
│  Still on 1.4. Still working. Nothing has been upgraded.               │
└────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─ 4. VERIFY WITH future=True ───────────────────────────────────────────┐
│  create_engine(..., future=True);  sessionmaker(..., future=True)      │
│                                                                        │
│  2.0's rules, 1.4 still installed. Fails what will fail.        (§20)  │
│  ← THE STEP PEOPLE SKIP. It is the one that makes step 5 boring.       │
└────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─ 5. BUMP THE VERSION ──────────────────────────────────────────────────┐
│  Nothing should be left to find.                                       │
└────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─ 6. MODERNISE AT LEISURE (optional, never urgent) ─────────────────────┐
│  session.query()  →  select() + .scalars()                      (§17)  │
│  Query.get()      →  session.get()                                     │
│  backref          →  back_populates                                    │
│                                                                        │
│  None of this is required for 2.0 to run. Doing it during steps 1-5    │
│  mixes cosmetic changes into a functional migration and makes the      │
│  diff impossible to review.                                            │
└────────────────────────────────────────────────────────────────────────┘
```

**The single most important structural point:** step 6 is *after* step 5, and it's optional.
The instinct to "clean it all up while I'm in here" is what turns a two-hour migration into a
two-week one with an unreviewable diff — and it makes a bisect useless when something does
break, because every commit changed both behaviour and style.

**Drill.**

1. Order these and justify the position of each: bump to 2.0 · fix `RemovedIn20Warning`s · flip `future=True` · run `SQLALCHEMY_WARN_20=1`.
2. Why is "convert `session.query()` to `select()`" last, and optional?

<details>
<summary>Answers</summary>

**1. Short answer:**

```
1. run SQLALCHEMY_WARN_20=1      ← inventory: you can't plan what you haven't listed
2. fix the RemovedIn20Warnings   ← the only tier that actually breaks
3. flip future=True              ← verification: prove the fixes hold under 2.0 rules
4. bump to 2.0                   ← should be uneventful by now
```

**Why the warning flag is first:** it's read-only, changes nothing, and costs one command.
There's no reason to guess at scope when you can measure it — and measuring first is what stops
you from spending day one on `session.query()`, which isn't even broken.

**Why fixes come before `future=True`:** the flag is a pass/fail gate. Running it against
unfixed code just reproduces the list you already have from step 1, in a more disruptive form.

**Why `future=True` sits before the version bump:** it's the only step that gives you 2.0's
errors while you still have a working 1.4 environment underneath. Skip it and step 4 becomes
the moment you discover what you missed — with the old version already uninstalled and every
behaviour changed at once.

Steps 1 and 3 are both verification, at opposite ends: **one tells you what to do, the other
tells you whether you did it.**

**2. Short answer:** because it isn't required, isn't risky, and mixing it in makes the real
migration unreviewable.

- **Not required** — `Query` works in 2.0. Measured: it runs on a `future=True` session (§20).
- **Not risky** — the SQL is identical (§16), so there's nothing to regress.
- **Mixing it in is the actual harm.** A migration commit should change *behaviour*. A
  modernisation commit should change *style*. Combine them and the diff is thousands of lines
  where four of them mattered, code review becomes impossible, and `git bisect` stops being
  able to tell you which kind of change broke you.

Do it after, in its own commits, or don't do it at all this quarter. Both are defensible;
doing it *during* is not.

</details>

---

## Predictions — write these down before you run anything

These four stay unanswered on purpose. Put your answers in `LEARNING-LOG.md` **first**, then
run the upgrade and diff your predictions against what actually happened. A prediction you
wrote and got wrong teaches more than an answer you read — and Step 4 has already caught this
project out twice on exactly this kind of question.

Everything you need to reason about them is in §16–§22. That's the point: these are
predictions, not guesses.

1. `SQLALCHEMY_WARN_20=1` on the current code — which lines do you expect it to flag? List
   them **by file and construct**, before running.
2. Which of these breaks in 2.0, and what replaces each: `session.query(Issue)`,
   `Query.get(id)`, `engine.execute("SELECT ...")`, `declarative_base()` imported from
   `sqlalchemy.ext.declarative`? For each, name the **tier** (§19), not just the fix.
3. Predict the `DetachedInstanceError` scenario: what must happen, in what order, for it to
   fire? Does the version matter (§21)?
4. Does `backref` still work in 2.0? Which tier is it, and is "still works" the same as "still
   recommended"?
