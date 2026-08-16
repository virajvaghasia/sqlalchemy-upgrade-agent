# Migration — SQLAlchemy 1.4 → 2.0

The companion to `01-CONCEPTS.md`. That file covers SQLAlchemy **as it is** (§0–§15: the
relational shapes, the ORM layer, the session at runtime). This one covers **why it changed**,
and — the part that matters more — how to tell a real breakage from a style preference.

Section numbering continues from `01-CONCEPTS.md`, so a reference to "§18" is never ambiguous.

| | file | sections |
|---|---|---|
| the model, the ORM, the session | `01-CONCEPTS.md` | §0 – §15 |
| **the 1.4 → 2.0 upgrade** | **this file** | **§16 – §22** |

---

## Contents

- **§16 — Why 2.0 exists: one API instead of two**
- **§17 — The Result API: rows, scalars, and the most common 2.0 papercut**
  — *ends with `cascade_backrefs`, the one breakage in this chapter that doesn't raise*
- **§18 — Autobegin: when a transaction actually starts**
- **§19 — Reading the warnings: four classes, two of them silent by default**
- **§20 — `future=True`: run 2.0's rules without installing 2.0**
- **§21 — What 2.0 does *not* fix**
- **§22 — The migration recipe, in order**
- **Predictions** — *deliberately unanswered; you settle these by running the upgrade*

Blocks are labelled `# runnable`, `# summary of` or `# illustration`, with the contracts
defined in [`01-CONCEPTS.md` Part 0](CONCEPTS.md#part-0--how-to-use-this). These commands produce
all of it — the seed goes first, because §7 counts queries against the 200-issue database:

```bash
# seed first — §7 counts queries against the 200-issue database
uv run python -m experiments.sqlalchemy_1_4_vs_2_0.seed

uv run python -m experiments.sqlalchemy_1_4_vs_2_0.migration     # §16–§21, sections 1–9

SQLALCHEMY_WARN_20=1 uv run python -W always::DeprecationWarning \
    -m experiments.sqlalchemy_1_4_vs_2_0.app                     # §19, one module

uv run python -m experiments.sqlalchemy_1_4_vs_2_0.sweep         # §19, every module
```

One more, which backs no block in this file but is the tool §20 points at for planning the
upgrade — it lists patterns worth testing, **not** breakages:

```bash
uv run python -m experiments.sqlalchemy_1_4_vs_2_0.candidates
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
        └─ .where(...)                           └─ .filter(...)
```

Two APIs meant two mental models, two vocabularies for the same idea (`filter` vs `where`),
and constant low-grade friction of the form *"is this a Core thing or an ORM thing?"*

**Check that vocabulary claim before repeating it, though.** By 1.4 this particular gap is
already closed: `Query.where()` exists as a synonym for `.filter()` and runs.
`hasattr(session.query(Issue), "where")` is `True`, and
`session.query(Issue).where(Issue.status == "open").all()` returns rows. So the split is a
habit by now rather than a hard boundary — the unification story is about `select()` versus
`Query` as *constructs*, not about which verb each one will accept.

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
     SELECT issues.id, issues.title, ... FROM issues WHERE issues.status = ?
     (column lists folded for display; the comparisons below use the full SQL)

     identical from FROM onward: True
     identical from WHERE onward: True
     identical including column labels: False

     Query.get(1) vs Session.get(Issue, 1) — identical SQL: True
```

**Same tables. Same WHERE. Same parameters. Same query plan.** The only difference is that
`Query` adds `AS issues_id` column labels and `select()` doesn't — a labelling difference, not
a difference in work performed.

This is the single most useful fact to hold before migrating:

> **`session.query()` → `select()` is a change in how you write, not in what gets sent.**

No query plans change. No performance changes. Which is exactly why it emits **no deprecation
warning at all** (§19) — and why calling it a "breakage" would be wrong.

**One caveat, and it is a real one.** That claim covers the statement going *out*. It does not
quite cover the results coming *back*: with `joinedload` against a **collection**, `Query`
silently de-duplicated the multiplied rows and `select()` refuses to, raising until you call
`.unique()`. Same SQL, different contract. §17 measures it.

**And keep the scope of this section straight.** "Cosmetic" is a claim about
`session.query()` → `select()`, *not* about the 1.4 → 2.0 upgrade as a whole. The upgrade
changes real behaviour elsewhere — most importantly `cascade_backrefs` (§17), where 2.0 stops
enrolling objects attached by the many-to-one side of a relationship and silently writes fewer
rows. Reading "the migration is cosmetic" off this section is the single most expensive mistake
it could cause.

### The renames worth memorising

| 1.x | 2.0 | is it a breakage? |
|---|---|---|
| `session.query(Model)` | `select(Model)` + `session.execute()` | **no** — Query still works in 2.0 (one caveat: `.unique()`, §17) |
| `.filter(...)` | `.where(...)` | no — vocabulary alignment with Core |
| `Query.get(pk)` | `session.get(Model, pk)` | no — warns, still runs |
| `engine.execute("...")` | `with engine.connect() as c: c.execute(text("..."))` | **yes — this one actually fails** |
| `from sqlalchemy.ext.declarative import declarative_base` | `from sqlalchemy.orm import declarative_base` | no — moved, one-line fix |
| *(no rename)* `comment.issue = issue` to enroll `comment` | `session.add(comment)` | **yes — and it fails silently** (§17) |

Four of those five renames are cosmetic. **One is not.** Telling them apart is the entire skill
this chapter teaches, and §19 is how you do it mechanically instead of by eye.

The last row is not a rename at all, which is why it's the one that gets missed: there is no
old spelling to grep for. It's a behaviour that quietly stops happening.

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

The SQL is identical, so there are no query-plan changes and no performance changes. That is a
completely different category of migration from one that alters what the database does.

One behavioural difference is `.unique()` (§17), and note which way it fails: `select()`
**raises** rather than quietly handing back duplicated rows. A breakage whose worst case is a
loud exception at the call site is the easy kind — you cannot ship it by accident.

**But do not generalise that to the whole migration.** `cascade_backrefs` (§17) is the
counter-example, and it is the dangerous kind: under 2.0, an object attached by writing the
*many-to-one* side (`comment.issue = issue`) is never enrolled in the session, so its `INSERT`
silently doesn't happen. No exception, fewer rows. *That* one can reach production.

So the honest statement is narrower than "not risky": **the query-style rewrite is not risky.
The version bump has at least one item that is**, and it isn't the one that looks scary.

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
  element type : Row                          <- a Row, NOT an Issue
  first element: (<Issue 1 'issue 1'>,)       <- note the trailing comma: a one-tuple
  rows[0][0]   : <Issue 1 'issue 1'>          <- the Issue is INSIDE it

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
| `.unique()` | the same result, de-duplicated | **required** with `joinedload` against a collection |

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

### `.unique()` — the papercut behind the papercut

`.scalars()` is the one everyone hits. This is the one that arrives a week later, once you
start migrating the queries that were *already* optimised, and it is the single exception to
§16's "a change in how you write, not in what gets sent."

`01-CONCEPTS.md` §15 established that `joinedload` **multiplies rows**: an issue with three
comments comes back three times, because that's what a LEFT JOIN does. Someone has to collapse
those rows back into distinct objects. In 1.x, `Query` did it for you, silently. In 2.0,
`select()` refuses to guess:

```
# runnable   →   uv run python -m experiments.sqlalchemy_1_4_vs_2_0.migration     (§6)

  the JOIN returns 6 raw rows for 3 issues  (they have 1, 2 and 3 comments)

  1.x  query(Issue).options(joinedload(...)).all()
       -> 3 Issue objects, no complaint (Query de-duplicated silently)

  2.0  session.execute(stmt).scalars().all()
       -> InvalidRequestError:
          The unique() method must be invoked on this Result, as it
          contains results that include joined eager loads against
          collections

  2.0  session.execute(stmt).unique().scalars().all()
       -> 3 Issue objects
```

Note that `.all()` alone raises too — the requirement is on the `Result`, not on `.scalars()`.

### Rows and columns: which knob does what

`.scalars()` and `.unique()` get confused with each other constantly, because both are
described as "fixing the result." They act on **different axes of the same grid**, and once you
see the grid they stop competing for the same slot in your head.

```
# illustration
                     ← columns →
                  ┌───────────────────────┐
                  │ (Issue 1,)            │
      rows  ↓     │ (Issue 1,)            │   same object, twice — the JOIN multiplied it
                  │ (Issue 2,)            │
                  └───────────────────────┘

  .scalars()  works ACROSS  →   picks ONE column, discards the others.
                                Each row gets narrower. The row COUNT is unchanged.

  .unique()   works DOWN    ↓   drops duplicate rows.
                                The row COUNT shrinks. Each row is unchanged.
```

So they are not alternatives and never substitute for one another:

| | axis | changes | fails how |
|---|---|---|---|
| `.scalars()` | across a row | which column you get | **never raises** — silently takes column 0 |
| `.unique()` | down the rows | how many rows you get | **raises** until you call it, in one specific case |

The asymmetry in that last column is worth pausing on. The same library, in the same release,
guesses in one case and refuses to guess in the other.

### Why 2.0 makes you say `.unique()` — and when it actually asks

Two separate questions, which the phrase "collapsing rows is only correct for entities" runs
together. Measured:

```
# runnable   →   uv run python -m experiments.sqlalchemy_1_4_vs_2_0.migration     (§6)

  When does the requirement fire? Only one of these three:
    select(Issue) + joinedload(collection) -> InvalidRequestError
    select(Issue.id) + joinedload          -> ArgumentError
    select(Issue.id, Issue.title)  plain   -> ok, 3 rows
```

**The error is an entity-only event.** You cannot `joinedload` onto a column select at all, so
the "what if you selected columns" case can never reach the error. That case explains why
`.unique()` isn't *automatic* — a different question from why it *raises here*.

Here's the reason it can't be automatic, with two genuinely distinct issues that share a title:

```
# runnable   →   the same migration.py §6

    entities: two DIFFERENT issues, identical titles, ids [1, 2]
              .unique().scalars().all() -> 2 objects   (dedupes by IDENTITY)
    columns : .all()          -> 2 rows  [('duplicate title',), ('duplicate title',)]
              .unique().all() -> 1 rows  [('duplicate title',)]
                                        ^ a real row destroyed (dedupes by VALUE)
```

**`.unique()` means two different things depending on what you selected.** On entities it
dedupes by primary key, so distinct objects always survive — it can only remove copies the JOIN
invented. On plain rows it has nothing but the values, so two real facts that happen to match
collapse into one.

That's the whole justification. 1.x could assume the ORM case because `Query` *was* the ORM
API. `select()` serves both worlds, and the two worlds want opposite defaults — so it declines
to pick and makes you write it down.

> **`.scalars()` chooses a column. `.unique()` removes rows.** Different axes, different failure
> modes: one guesses silently, the other refuses to. Neither is a bug.

### `cascade_backrefs` — the one that doesn't raise

Everything above fails loudly. This one doesn't, and it is the most dangerous item in this
repository.

`01-CONCEPTS.md` §14 teaches that you don't have to `session.add()` an object if you attach it to
one already in the session — the **save-update cascade** enrolls it for you. In 2.0, **half of
that is still true.** The half that isn't loses rows and says nothing.

Which half depends entirely on **the direction you write the relationship in**:

```
# runnable   →   uv run python -m experiments.sqlalchemy_1_4_vs_2_0.migration     (§8)

  Each row below attaches exactly ONE issue to a project that is already
  in the session, calls flush(), then asks the database:
      SELECT count(*) FROM issues        1 = the INSERT ran, 0 = it did not

  how you attach the one issue       1.4   2.0   verdict
  --------------------------------------------   ----------------------
  project.issues.append(issue)         1     1   survives
  project.issues = [issue]             1     1   survives
  issue.project = project              1     0   SILENT LOSS (1 -> 0)
  Issue(..., project=project)          1     0   SILENT LOSS (1 -> 0)
                                  ^^^^^^^^^^^^
                                  rows in issues
```

**Reading a row:** take line three. You create one `Issue`, attach it by writing
`issue.project = project`, and flush. On 1.4 the database then holds **1** issue — the cascade
enrolled it and the `INSERT` ran. On 2.0 it holds **0**. Same code, same flush, no error
anywhere; the row just isn't there.

Writing the **collection** side is the save-update cascade proper, and 2.0 keeps it. Writing
the **many-to-one** side works in 1.4 only because the `backref` populates the collection
first — and *that* leg is what 2.0 drops. In 1.4 the two forms are interchangeable, so nothing
in your code records which one you happened to pick.

Both routes end at the same place. Only one of them still gets there:

```
# illustration — one severed hop explains the entire failure

  project.issues.append(issue)
       the COLLECTION side  ──────────────┐
                                          │  direct
                                          ▼
                              ┌───────────────────────┐   cascade   ┌──────────┐
                              │    project.issues     │────────────▶│ session  │──▶ INSERT
                              │      populated        │             │ enrolled │
                              └───────────────────────┘             └──────────┘
                                          ▲
                                     ✕    ┊  via the backref
       the MANY-TO-ONE side ─ ─ ─ ─ ─ ─ ─ ┘
  issue.project = project
                                     ↑
                          THIS HOP IS REMOVED IN 2.0.
                          Nothing else about the picture changes — and because
                          the object simply never reaches the session, there is
                          no error to raise. The INSERT is just never issued.
```

**Read what the diagram does *not* contain:** there is no path from `issue.project = project` to
the session that doesn't go through the collection. That's the whole mechanism. The many-to-one
write was never talking to the session directly — it was riding the backref, and 2.0 took the
ride away.

**Note the fourth row.** `Issue(..., project=project)` is a constructor keyword — it looks
nothing like a cascade, and it's the form most likely to be scattered through a codebase.

### What that does to this project's own seed

`seed.py` uses both forms. Only `users`, `projects` and `labels` are ever passed to
`session.add()`; everything else arrives through a relationship:

```
# runnable   →   the same migration.py §8

      table                  1.4   2.0
      projects                 1     1
      users                    1     1
      issues                   3     3
      comments                 6     0   <-- GONE, silently
      issue_assignments        3     0   <-- GONE, silently
```

`issues` survive — they're attached with `projects.issues.append(issue)` (`seed.py:122`).
`comments` and `assignments` do not — they're attached with `comment.issue = issue`
(`seed.py:136`) and `a.issue = issue` (`seed.py:147`).

**The seed would still "succeed."** No exception, no runtime warning, a database that looks
populated. Every comment and every assignment silently absent — and `01-CONCEPTS.md` §15's N+1
demonstration would then fire its 200 `.comments` queries against nothing.

Compare the two shapes of breakage:

| | `engine.execute("...")` | `cascade_backrefs` |
|---|---|---|
| how it fails | `NotImplementedError`, immediately | writes fewer rows, silently |
| when you find out | first run, before you can ship it | whenever someone notices data missing |
| can it reach production? | no | **yes** |
| caught by a test suite? | every test that touches it | only if a test asserts on row counts |

Counted off the mappers, **7 of the 14 relationships in `models.py` are declared with
`backref=`**, so every one of them carries the droppable leg.

**The fix is to say what you meant:** `session.add(comment)`. Relying on the cascade was always
implicit; 2.0 removes the implicitness, not the capability. You can adopt the 2.0 behaviour
today with `relationship(..., cascade_backrefs=False)` or `future=True` on the Session — which
is exactly what the warning tells you to do.

> **The dangerous breakage is not the one that stops your program. It's the one that lets your
> program keep running while doing less than it used to.**

**How this was found, because the method generalises.** It is not in §19's inventory. That
sweep runs `app.py`, and `app.py` only *queries* — it never builds an object graph, so it never
triggers the cascade. The warning appeared only when the sweep was run across **every** module
in the package. A one-file inventory found five items and missed the worst one.

**Drill.**

1. Why does `session.execute(select(Issue)).all()` not give you `Issue` objects?
2. `.first()` vs `.scalar_one()` — when is the difference a bug you'd rather have?
3. You select two columns instead of a whole entity: `select(Issue.id, Issue.title)`. Should you call `.scalars()`?
4. A working 1.4 line, `query(Issue).options(joinedload(Issue.comments)).all()`, raises `InvalidRequestError` once migrated to `select()`. Which of the two versions is doing the surprising thing?

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

**3. Short answer: no** — and the reason it's worth asking is *how* it goes wrong.

```
# runnable   →   uv run python -m experiments.sqlalchemy_1_4_vs_2_0.migration     (§2)

  .scalars() is NOT 'unwrap the row'. It is 'project down to ONE column':
    select(Issue.id, Issue.title).all()        -> [(1, 'issue 1'), (2, 'issue 2'), (3, 'issue 3')]
    ...same select, .scalars().all()           -> [1, 2, 3]
    warnings raised while discarding 'title'   -> NONE
    the index is a parameter: .scalars(1).all()-> ['issue 1', 'issue 2', 'issue 3']
```

Three things in there that the short answer alone doesn't give you:

- **It doesn't raise and it doesn't warn.** `title` is gone and nothing says so. This isn't
  "don't do that" advice — it's a live bug that produces a plausible-looking list of integers.
- **`.scalars()` is not "unwrap the row."** It is *project down to one column*. The
  single-entity case is just where that projection happens to lose nothing.
- **The column index is a parameter.** `.scalars(1)` gives you the titles. Column 0 is a
  default, not a limit.

So the rule isn't "always add `.scalars()`" — which is the reflex you build after meeting the
papercut in the first place. It's **add it when you selected one thing.** Selected several? Keep
the rows; they support `.title`-style access as well as indexing.

Worth putting beside `.unique()` (§17): on a wide select `.scalars()` guesses silently, while
`.unique()` refuses to guess and raises. Same library, same release, opposite postures toward
the same kind of ambiguity — so you cannot reason about one from the other.

**4. Short answer:** the 1.4 version. It was throwing rows away without telling you.

The database returned 6 rows for 3 issues; both versions received all 6. `Query` collapsed them
to 3 and said nothing. `select()` reports that a decision needs making, and `.unique()` is you
making it.

```
6 raw rows  ─┬─  1.x Query      ──▶  3 objects, silently
             └─  2.0 select()   ──▶  InvalidRequestError
                        + .unique()  ──▶  3 objects
```

Which means the migration instruction is *not* "add `.unique()` until the error goes away."
Adding it blindly is fine in the ORM case and wrong the moment you're selecting columns rather
than entities — there, duplicate rows may be two real facts, and de-duplicating is data loss.
Check what you selected first.

The deeper habit: when a migration surfaces an error on code that "worked," ask which version
was making an undeclared assumption. Here it was the old one, and the error is the library
finally saying so out loud.

</details>

---

## §18 — Autobegin: when a transaction actually starts

### "Removing autocommit" is a misleading way to describe it

You'll read that 2.0 "removes autocommit." That phrasing suggests something was taken away.
What actually happened is that the transaction boundary became **predictable** rather than
implicit.

In 1.x, `engine.execute()` used **library-level autocommit**: SQLAlchemy inspected the
statement, and if it looked like DML or DDL (`INSERT`, `UPDATE`, `DELETE`, `CREATE`), committed
it on its own the moment it finished. Not a setting you chose — a guess the library made per
statement. Reading the code did not tell you where a transaction started or ended, because the
answer depended on what kind of statement it was.

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
holding a transaction open. On a real database (not SQLite) that keeps a snapshot alive, which
blocks `VACUUM` from reclaiming rows your transaction might still need — the cause of table
bloat traced back to an app that "only reads."

Whether your *data* also goes stale depends on the isolation level, and this is worth getting
right rather than repeating as folklore:

| isolation level | what a long-open transaction does to your reads |
|---|---|
| `READ COMMITTED` (Postgres/Oracle default) | each statement takes a fresh snapshot — **reads stay current** |
| `REPEATABLE READ` (MySQL InnoDB default) | first statement fixes the snapshot — **reads go stale, silently** |

So the blanket claim "long transactions give you stale data" is only true on the second row.
The resource cost is true on both. Reading is not free of transaction semantics either way.

**2. `commit()` matters even for read-only work.** Not to save anything — there's nothing to
save — but to **end the transaction** so the next read starts fresh. This is the same mechanism
as `expire_on_commit` in `01-CONCEPTS.md` §15, seen from the other side: the commit both ends the
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

- **You hold database resources.** On Postgres, a long-open transaction blocks vacuuming of
  rows your snapshot might still need — a classic cause of table bloat traced back to an app
  that "only reads." True at **every** isolation level.
- **Your data may go stale.** Under `REPEATABLE READ` you keep seeing the snapshot from your
  first query, no matter what else commits; hours later you're reading hours-old data and
  everything looks fine. Under `READ COMMITTED` — Postgres's default — this one does *not*
  apply, because each statement re-snapshots. Know which you're on before you cite it.
- **Your objects never refresh.** `expire_on_commit` (`01-CONCEPTS.md` §15) fires at commit. No
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

The two halves do different jobs, and the second one is routinely explained wrongly:

- `SQLALCHEMY_WARN_20=1` tells **SQLAlchemy** to emit the 2.0 deprecation warnings at all.
  This is the load-bearing half — without it the breakages are simply not reported.
- `-W always::DeprecationWarning` widens **Python's** filter. It is usually justified with
  *"Python hides `DeprecationWarning`s by default"*, which is not quite true and matters here.

Since PEP 565, Python shows a `DeprecationWarning` when it is attributed to `__main__`, and
hides it otherwise. Run a module with `-m` and warnings blamed on *that* module are already
visible; warnings blamed on code it imports are not. Measured on `app.py` with
`SQLALCHEMY_WARN_20=1` set both times:

| | warnings shown | includes both `RemovedIn20Warning`s? |
|---|---|---|
| without `-W` | 4 | **yes** |
| with `-W` | 5 | yes |

The one warning `-W` adds is the `MovedIn20Warning` raised at `models.py:8` — an *imported*
module, hence hidden by the default filter. So `-W` is not what makes breakages visible; it is
what stops you from missing items in the files you didn't run directly. Keep it, for that
reason rather than the usual one.

### Why this matters more than it sounds

Run this project's `app.py` both ways and count what you get:

```
# summary of →   the app.py command below, run with and without the flag
#                (counted by class; see 01-CONCEPTS.md Part 0 for what this label means)

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

That's the same lesson as `01-CONCEPTS.md` §12 (`check.py` printing OK while the schema was
broken), in a different costume: *a passing run only tells you the thing you ran didn't fail.*

### One file is a demonstration, not an inventory

Everything above runs `app.py`, which makes the point about the flag but is a bad inventory —
and the way it's bad is the lesson. **`app.py` only queries.** It never builds an object graph,
so it cannot trigger `cascade_backrefs` (§17), the worst item in this repository. Five findings,
and the dangerous one isn't among them.

Sweep every module and the picture changes shape:

```
# runnable: uv run python -m experiments.sqlalchemy_1_4_vs_2_0.seed >/dev/null 2>&1; \
#           uv run python -m experiments.sqlalchemy_1_4_vs_2_0.sweep 2>&1 \
#           | sed -n "/module  /,/TOTAL/p"
  module        Removed   Moved  Legacy
  -------------------------------------
  check.py            0       1       0
  app.py              2       1       2
  states.py           1       1       0
  explore.py          7       1       0
  migration.py       19       1       2
  seed.py             0       1       0
  -------------------------------------
  TOTAL              29       6       4
```

#### The number moved, and why it moved is the actual lesson

**This table used to read `seed.py 1013` and `TOTAL 1042`.** It was measured honestly and it
sat here for weeks. Then Day 6 added the `is_seeded` guard to `seed.py` — so that on a database
which already has rows, it stops rather than re-inserting — and the 1013 vanished. Nothing
re-ran the command, so the doc kept quoting a state that no longer existed.

**Delete the database and it comes straight back:**

```
# runnable: rm -f issues.db; \
#           uv run python -m experiments.sqlalchemy_1_4_vs_2_0.sweep 2>&1 \
#           | sed -n "/module  /,/TOTAL/p"; \
#           uv run python -m experiments.sqlalchemy_1_4_vs_2_0.seed >/dev/null 2>&1
  module        Removed   Moved  Legacy
  -------------------------------------
  check.py            0       1       0
  app.py              0       1       0
  states.py           1       1       0
  explore.py          7       1       0
  migration.py        8       1       2
  seed.py          1013       1       0
  -------------------------------------
  TOTAL            1029       6       2
```

**Same code. Same command. 29 or 1029, depending on whether a file exists.**

That is a stronger version of the point this section was already making. The original argument
was *"1042 occurrences are only 4 distinct problems"* — occurrences overcount the work. The
measured truth is worse than that:

> **An occurrence count is not a property of your code at all. It is a property of the run.**

The cascade warning fires once per attached object, so its count tracks how many rows the script
inserts — which depends on whether the database was empty, which depends on whether you ran
anything else first. `app.py` swings 2 → 0 and `migration.py` 19 → 8 for the same reason: with no
data to query, the code paths that warn never execute.

**Note also that 1029 ≠ 1042.** Even reproducing the original conditions does not reproduce the
original number, because the code moved too. A number you cannot re-derive is not evidence; it
is a memory. That is the whole of `CLAUDE.md`'s measurement rule, and this section is where the
repo violated it against itself.

**Now read the second number, because the occurrence count is not a workload.** Occurrences are
not problems; the same fix repeated is one entry:

```
# runnable: uv run python -m experiments.sqlalchemy_1_4_vs_2_0.sweep 2>&1 \
#           | grep -A5 "distinct,"
  RemovedIn20Warning  —  4 distinct, 29 occurrences
       24x  "X" object is being merged into a Session along the backref cascade path for relationshi
        2x  The Engine.execute() method is considered legacy as of the 1.x series of SQLAlchemy and 
        2x  Passing a string to Connection.execute() is deprecated and will be removed in version 2.
        1x  Using plain strings to indicate SQL statements without using the text() construct is  de

  MovedIn20Warning  —  1 distinct, 6 occurrences
        6x  The ``declarative_base()`` function is now available as sqlalchemy.orm.declarative_base(

  LegacyAPIWarning  —  1 distinct, 4 occurrences
        4x  The Query.get() method is considered legacy as of the 1.x series of SQLAlchemy and becom

==============================================================================
What to do with this
==============================================================================
```

**Four distinct breakages in the entire project.** That is the `deliverables/BREAKAGES.md` list, and you
could not have got it from any single file: `app.py` contributes rows two and three, `states.py`
contributes row four, and row one — the only one that fails silently — comes from the modules
that write data.

**Four distinct, in both states.** Seeded, the occurrences total 29; unseeded, 1029. The
*distinct* count does not move, because the same fix repeated is still one fix. That is why it
is the number worth reporting: sizing the job by occurrences would have you budget for a
thousand changes when there are four, and budget differently on Tuesday than on Monday
depending on whether a file happened to exist.

> **Sweep every module. Then collapse occurrences into distinct problems, and count *those*.**

`check.py` is worth noticing too: it does nothing but import the models and configure mappers,
and that alone surfaces the `declarative_base` import. A module can carry migration items
without containing any interesting code at all.

### The four classes, and what each one promises

```
# summary of →   SQLALCHEMY_WARN_20=1 uv run python -W always::DeprecationWarning \
#                  -m experiments.sqlalchemy_1_4_vs_2_0.app
#
#                File, line and class are verbatim. The message text is trimmed —
#                Python prints each warning with its full path and source line.

models.py:8   MovedIn20Warning:   declarative_base() is now available as
                                  sqlalchemy.orm.declarative_base()
app.py:68     LegacyAPIWarning:   Query.get() ... is now available as Session.get()
app.py:79     RemovedIn20Warning: Engine.execute() ... will be removed in 2.0
app.py:79     RemovedIn20Warning: Passing a string to Connection.execute() is deprecated
                                  and will be removed in version 2.0
app.py:116    LegacyAPIWarning:   Query.get() ... is now available as Session.get()
```

Five lines, matching the five counted above — `Query.get()` is flagged at **both** call sites,
not once. The tool reports occurrences, not distinct problems, and the distinction matters when
you're sizing the work: two lines here are one fix.

**The class name is the entire message.** Learn to read it and you can triage a codebase in
minutes rather than days. Every construct lands in exactly one of four tiers:

```
# illustration — the triage flow, and the one place the type system lies

                              a construct              run it against EVERY module —
                              in your code             app.py only queries, so it
                                   │                   never sees code that builds
                                   ▼                   an object graph
                       ┌──────────────────────────┐
                       │   SQLALCHEMY_WARN_20=1   │
                       │          sweep           │
                       └───────────┬──────────────┘
                                   │
      ┌─────────────────┬──────────┴───────┬─────────────────────┐
      ▼                 ▼                  ▼                     ▼
  (nothing)         LegacyAPI          MovedIn20             RemovedIn20
                    Warning            Warning               Warning
      │                 │                  │                     │
      ▼                 ▼                  ▼                     ▼
  not a             works in 2.0       new import            STOPS WORKING
  migration         fix at             path — a              fix before
  item              leisure            one-line fix          upgrading
                                                             → deliverables/BREAKAGES.md

                                           └──────────┬──────────┘
                                                      │
                    MovedIn20Warning SUBCLASSES RemovedIn20Warning.
                    isinstance() cannot separate them — filter by EXACT
                    class, or a one-line import move lands in your
                    breakage list.
```

| warning class | what it promises | urgency | `deliverables/BREAKAGES.md`? |
|---|---|---|---|
| `RemovedIn20Warning` | **this stops working in 2.0** | fix before upgrading | **yes** |
| `MovedIn20Warning` | same thing, new import path — but see the flow above | one-line fix, any time | no |
| `LegacyAPIWarning` | works in 2.0, no longer the recommended way | at leisure | no |
| *(no warning at all)* | fully supported in 2.0 | not a migration item | no |

**The tiers are not four independent classes.** Measured:
`issubclass(MovedIn20Warning, RemovedIn20Warning)` is `True`;
`issubclass(LegacyAPIWarning, RemovedIn20Warning)` is `False`. So the table reads as a flat
taxonomy and the type hierarchy doesn't match it. Counting by exact class name is fine — the
counts in this chapter are — but any triage script written with `isinstance` will
over-report breakages.

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

Only the first belongs in `deliverables/BREAKAGES.md` — that file is for things that worked in 1.4 and
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

### And what it stays silent about — read this before using it as a gate

`future=True` swaps in the 2.0 `Engine` and `Session` classes. That is precisely its scope: it
enforces the rules those objects own. It is **not** an upgrade simulator, and a clean run under
it is not a clearance to bump the version.

```
# runnable   →   the same migration.py     (§4)

What future=True stays SILENT about (all real migration items):
  Query.get(1)          -> <Project 1 'apollo'>   (a LegacyAPIWarning item, accepted here)
  declarative_base      -> models.py still imports it from
                           sqlalchemy.ext.declarative, and the future
                           engine built every table from those models
                           without a word. That is a MovedIn20Warning
                           item, and only §19's sweep reports it.
```

Both of those are real migration items. Neither is a `future=True` finding. The two tools are
not stronger and weaker versions of each other — one is contained inside the other:

```
# illustration — the coverage gap, drawn

  EVERYTHING 2.0 OBJECTS TO
  ┌──────────────────────────────────────────────────────────────────────┐
  │                                                                      │
  │   ┌──────────────────────────────────────────────┐                   │
  │   │  what future=True catches                    │                   │
  │   │  — only what fails AT THE ENGINE             │                   │
  │   │                                              │                   │
  │   │      engine.execute("...")   → raises        │                   │
  │   └──────────────────────────────────────────────┘                   │
  │                                                                      │
  │     Query.get(pk)           LegacyAPIWarning    → untouched          │
  │     declarative_base import MovedIn20Warning    → untouched          │
  │     comment.issue = issue   RemovedIn20Warning  → ALREADY BROKEN ✕   │
  │                                                                      │
  └──────────────────────────────────────────────────────────────────────┘
     ▲
     └── only the WARN_20 sweep enumerates the whole box
         (and only if you sweep every module — §17)
```

**The bottom entry is a different animal from the two above it.** Those two are untouched by
the flag — they behave the same either way. The cascade is not: `future=True` *is* how 2.0's
behaviour gets switched on, so under the flag your rows are **already being dropped**. It
doesn't raise, so nothing tells you.

Which means the reassuring step in §22 has a hole in it. Run your test suite under
`future=True`, watch it pass, and you may simply have a suite that never asserts on row counts.

| migration item | under `future=True` | `SQLALCHEMY_WARN_20` |
|---|---|---|
| `engine.execute("...")` | **raises** | `RemovedIn20Warning` |
| `comment.issue = issue` (§17) | **silently drops the row** | `RemovedIn20Warning` |
| `Query.get(pk)` | silent, unaffected | `LegacyAPIWarning` |
| `declarative_base` import location | silent, unaffected | `MovedIn20Warning` |
| `session.query(Model)` | silent, unaffected *(correctly — not an item)* | silent |

> **`future=True` fails what will fail at the engine. It does not enumerate what will warn —
> and one of the things it stays silent about is a real breakage.**

### The three-way split, measured

There is a further wrinkle, and it is the one that keeps a breakage list short without telling
you. Sort a batch of 1.4 patterns by *which tool notices them*:

```
# runnable   →   uv run python -m experiments.sqlalchemy_1_4_vs_2_0.migration     (§9)
  1.4 pattern                     WARN_20 says    future=True says        
  ------------------------------------------------------------------------
  engine.execute('SELECT 1')      RemovedIn20     NotImplementedError     
  select([Issue.id]) list form    RemovedIn20     ok                      
  joinedload('issues') by string  RemovedIn20     ok                      
  engine.table_names()            — nothing —     NotImplementedError     
  Query.filter('raw string')      — nothing —     ArgumentError           
  Row attr access, no .scalars()  — nothing —     AttributeError
```

Three groups, needing three different treatments:

| group | example | why the tool misses it |
|---|---|---|
| both agree | `engine.execute("…")` | — |
| **sweep only** | `select([Issue.id])`, string loader options | construction-time removals; the engine never sees them, so `future=True` runs them happily |
| **silent to the sweep** | `Query.filter("raw string")`, missing `.scalars()` | no deprecation warning exists — the code is legal 1.4 that 2.0 simply rejects |

**Neither tool is the inventory.** Build a breakage list from the sweep and you miss the third
group; build it from `future=True` and you miss the second. Worse, both omissions are invisible
from inside the tool you used — a short list looks exactly like a clean one.

This is precisely why `phases/PHASE-0.md` asks for breakages *"personally caused, hit, and fixed"*
rather than swept. The third group only comes into existence when the code actually runs on 2.0.

`candidates.py` runs this classification over a wider batch — 22 patterns worth testing, split
6 / 11 / 5 across the three groups:

```bash
uv run python -m experiments.sqlalchemy_1_4_vs_2_0.candidates
```

**Read its header before using its output.** It emits *candidates*, not entries. A row there is
a hypothesis about 2.0; a `deliverables/BREAKAGES.md` entry is a result you obtained by hitting the error
yourself. Pasting one into the other is the "grade your own homework with your own answer key"
failure that §21 warns about, wearing a lab coat.

This is why §22 keeps the warning sweep and the flag as **separate steps** rather than treating
the flag as a stronger version of the sweep. They answer different questions: the sweep gives
you the *inventory*, the flag gives you a *verdict* on one tier of it. Skipping the sweep
because "the flag passes" leaves every `Moved` and `Legacy` item undiscovered — none of which
break 2.0, all of which you'd rather know about before someone else finds them.

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
3. Your whole test suite passes with `future=True` everywhere. Are you done? What class of migration item could still be sitting in the code?

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

**3. Short answer:** no. Everything that *warns* rather than *raises* is still there, untouched
and unreported.

Measured on this repo: `Query.get()` and the `sqlalchemy.ext.declarative` import both sail
through a `future=True` run. They're a `LegacyAPIWarning` and a `MovedIn20Warning` — neither
breaks 2.0, so neither is an engine-level failure, so the flag has no opinion about them.

What you've actually proved with a green `future=True` suite:

```
proved      every code path your tests exercise survives 2.0's engine/session rules
NOT proved  that you have found every migration item          ← needs §19's sweep
NOT proved  that untested code paths are clean                ← needs coverage
```

That second line is the trap in the question. The flag is a **verdict**, not an **inventory** —
it can only rule on constructs your tests actually execute, and only on the tier it owns. Run
the sweep too; it's read-only and costs one command.

</details>

---

## §21 — What 2.0 does *not* fix

Not every problem in a 1.4 codebase is a 1.4 problem. Two of the ugliest things in this
project survive the upgrade completely untouched:

| looks like a version problem | actually is | where it's proven |
|---|---|---|
| the N+1 in `issue_report()` | a **loading-strategy** bug — equally slow in both | `01-CONCEPTS.md` §15 |
| `DetachedInstanceError` | a **session-lifecycle** bug — fires identically in 1.4 | `01-CONCEPTS.md` §14 |

Both were *measured* under 1.4 in Part 3 of `01-CONCEPTS.md`, before either was blamed on the
version. Neither emits a migration warning, because neither is a migration issue. Upgrade to
2.0 and the N+1 fires exactly the same number of queries; the detached object still raises.

### Count it, don't estimate it

That number is worth measuring rather than reasoning about, because reasoning about it gets it
wrong. The working estimate for this loop was `1 + 200 + 200 = 401` — two relationships touched
per issue, 200 issues. Reasonable, and off by half. (`01-CONCEPTS.md` §15's 201/202 are a
*different* loop — `apollo.issues` plus per-issue `.labels` — extrapolated from a measured
9-issue run, and correct on their own terms. Two loops, two numbers; don't quote one for the
other.) The real answer here:

```
# runnable   →   uv run python -m experiments.sqlalchemy_1_4_vs_2_0.migration     (§7)
#                (seed first: ... -m experiments.sqlalchemy_1_4_vs_2_0.seed)
  issues in the seed              : 200
  queries fired by issue_report() : 204

     200x  SELECT ... FROM comments
       3x  SELECT ... FROM projects
       1x  SELECT ... FROM issues
```

**Read the breakdown, not the total.** `issue_report()` touches two relationships per issue, so
the obvious estimate is `1 + 200 + 200`. It's off by 197, and the reason is the correction
already made in `01-CONCEPTS.md` §13:

| in the loop | relationship | queries | why |
|---|---|---|---|
| `issue.comments` | one-to-many | **200** | a collection is never in the identity map *as a collection* — every issue pays |
| `issue.project` | many-to-one | **3** | one object, known PK → identity map hit; misses once per distinct project |

Three projects in the seed, three queries. **"A lazy load fires a query" is false for
many-to-one on an object you already have** — and the N+1 here is one bug, not two.

That matters beyond arithmetic: the fix (§15's `selectinload`) needs to target the collection.
Optimising `issue.project` would eliminate 3 queries out of 204 and feel like progress.

### Why this distinction is the whole project

`deliverables/BREAKAGES.md` becomes the Phase 2 golden dataset. Every entry in it is a question a real
developer asks while upgrading. Put *"why is my loop slow?"* in it and you've seeded your
retrieval corpus with a question that has nothing to do with upgrading — and you will then
evaluate your system against it and score yourself on the wrong thing.

> **A breakage is something that worked in 1.4 and stopped working in 2.0. Not "something bad I
> found while migrating."**

Of the five suspicious patterns Step 4 examined, measurement moved **two** off the breakage
list entirely. Both would have looked perfectly plausible sitting in the corpus.

**Drill.**

1. Give the one-sentence test for whether something belongs in `deliverables/BREAKAGES.md`.
2. The N+1 and `DetachedInstanceError` both surfaced during migration work. Why does neither qualify?
3. Why does a wrong entry in `deliverables/BREAKAGES.md` cost more than a missing one?

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
| N+1 in a loop | 204 queries (measured) | 204 queries | no — a loading-strategy bug |
| `DetachedInstanceError` | raises (§14 traced it) | raises | no — a lifecycle bug |

They're real bugs, worth fixing, and worth understanding — they're just not *upgrade* bugs, and
the corpus is specifically about upgrading.

The failure mode to guard against: you spend a week migrating, you meet several problems, and
they all get filed under "2.0 issues" because that's what you happened to be doing at the time.
Measurement is what separates them, which is why `01-CONCEPTS.md` traced both under 1.4 **before**
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
│  EVERY module, not one. A module that only queries cannot report       │
│  the items that only appear when you WRITE — this repo's worst         │
│  breakage is invisible to app.py.                               (§19)  │
│  Then collapse occurrences into DISTINCT problems and count those:     │
│  1029 occurrences here are 4 actual fixes — and 29 on a seeded run.    │
└────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─ 2. TRIAGE ────────────────────────────────────────────────────────────┐
│  RemovedIn20Warning  →  must fix.  These are the deliverables/BREAKAGES.md entries. │
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
│  2.0's rules, 1.4 still installed. Fails what will fail AT THE         │
│  ENGINE — it is silent on the Moved/Legacy tiers, which is why         │
│  it verifies step 1's list rather than replacing it.            (§20)  │
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

These four stay unanswered on purpose. Put your answers in `logs/LEARNING-LOG.md` **first**, then
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
