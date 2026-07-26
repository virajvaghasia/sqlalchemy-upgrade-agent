# Concepts — the SQLAlchemy relationship model, derived once

This is the **teaching** file: one canonical explanation per concept, built up from SQL
first. It is not a diary. The chronological record — what you hit, when, and the mistakes
along the way — lives in `LEARNING-LOG.md`, and each dated entry there links back to a
section number here (`§1`–`§13`). Those numbers are **stable anchors**; don't renumber them
casually, or the log's links rot.

If you find the same idea explained twice in this file, that's a bug — report it. The old
learning log explained `backref` three times in three different framings, and that is
exactly what made it impossible to read.

---

## Contents

**Part 0 — How to use this**

**Part 1 — From SQL, first** *(the database is the truth; the ORM only wraps it)*
- §1 — The one law: a column holds exactly one value
- §2 — One-to-many: why the FK is forced onto the "many" side
- §3 — Many-to-many: why a third table is unavoidable
- §4 — A junction that carries facts: where `role` has nowhere to live
- §5 — Self-referential: one table, two FKs, a real ambiguity

**Part 2 — Then the ORM** *(convenience on top of the truth)*
- §6 — `relationship()` creates nothing; `ForeignKey` is the database's truth
- §7 — `Table` vs mapped class: "do I want an object for this row?"
- §8 — `secondary=`: the two joins you didn't write
- §9 — `primaryjoin` / `secondaryjoin`: naming those two joins yourself
- §10 — `backref`: one declaration, two attributes, and the swap
- §11 — Quoted vs bare names: deferred resolution
- §12 — Mappers configure lazily: why `check.py` exists
- §13 — `remote_side`: what it IS for, and why *your* schema doesn't use it

**Part 3 — Verify it yourself** *(real output from `explore.py`, per pattern)*

---

## Part 0 — How to use this

**Every claim about runtime behaviour in this file has a command that proves it.** That
command is `explore.py`, which builds the schema, seeds ~12 traceable rows, and prints the
SQL SQLAlchemy actually emits for each relationship. Part 3 holds that output.

The rule, which you will be tempted to break: **predict before you run.** For each traversal
in Part 3, write down what you think it returns *before* you look at the output. A prediction
is a derivation from the rules in Parts 1–2, not a lookup — if you can't predict it, the
mechanism isn't in your head yet, and reading the answer won't put it there. The gap between
your prediction and the real output is the exact shape of what you misunderstood.

> **Don't take API claims on trust — make the library say it.** This file was written by a
> fallible author (human and AI both). Part 3 is where the library speaks for itself.

Code blocks are labelled: `# runnable` means it executes as written; `# illustration` means
it's a fragment or a "what SQL this becomes" sketch, not something to paste and run.

---

## Part 1 — From SQL, first

You know SQL. So don't start from SQLAlchemy — start from the tables, and let the ORM fall
out of them. Every "why" in Part 2 has a SQL answer here underneath it.

### §1 — The one law: a column holds exactly one value

> **A column holds exactly one value.**

That is the whole foundation. Every relationship pattern in every ORM ever written is a
consequence of that one constraint. The next four sections are just that law, applied to
harder and harder shapes.

### §2 — One-to-many: why the FK is forced onto the "many" side

One project has many issues. Each issue has one project.

Try putting the link on `projects`:

```
# illustration
projects
| id | name   | issue_id      |
| 1  | Apollo | 4? 7? 12? 88?  |   ← broken: one column, many issues
```

A project has many issues, and that column holds one value. You'd need a list in a cell, and
SQL doesn't do that. Now put it on `issues`:

```
# illustration
issues
| id | title       | project_id |
| 4  | Login fails | 1          |
| 7  | Slow query  | 1          |   ← each issue points at ONE project. works.
```

Many rows can point at the same project — that's what makes it "many."

> **The foreign key lives on the side that has ONE of the other thing.** Not a convention —
> forced by §1.

"Give me the project's issues" is just that query run backwards:
`SELECT * FROM issues WHERE project_id = 1`. This is why the FK is on `Issue` but the
`relationship()` can be declared on either class (§10).

### §3 — Many-to-many: why a third table is unavoidable

An issue has many labels. A label is on many issues. **Now both sides need a list**, and
neither column can hold one (§1). There is nowhere to put the link — so you invent a table
whose *rows are the links*:

```
# illustration
issue_labels
| issue_id | label_id |
| 4        | 1        |
| 4        | 2        |
| 7        | 1        |
```

Each row is one pairing. Issue 4 has labels 1 and 2; label 1 is on issues 4 and 7. Both
"lists" are now rows, and rows are unlimited. The primary key is the **pair**
(`issue_id`, `label_id`) — that's what stops the same label being attached to the same issue
twice.

> **A junction table exists because a column can't hold a list.** §1, applied twice.

### §4 — A junction that carries facts: where `role` has nowhere to live

Same shape as §3 — until the pairing carries a fact of its own:

```
# illustration
issue_assignments
| issue_id | user_id | role     | assigned_at |
| 4        | 2       | owner    | 2026-07-13  |
| 4        | 5       | reviewer | 2026-07-14  |
```

Where does `role` belong? Not to the user — Alice isn't globally an "owner", she's the owner
*of issue 4* and a reviewer *of issue 9*. Not to the issue — issue 4 doesn't have one role,
it has one per person.

> **`role` is a fact about the PAIRING. It belongs to neither end.**

So the junction row needs to be a thing you can hold and read `.role` off of — a row with
attributes of its own. In SQL that's just a table with extra columns. The ORM consequence
(that this table must become a *class*, not a bare junction) is §7.

**The one-column test** — the whole rule, and a drill question:

> Does the fact that connects A and B have any attributes of its own?
> **No** → plain junction (§3). **Yes** → junction-with-data (§4).

### §5 — Self-referential: one table, two FKs, a real ambiguity

Issue #7 is blocked by issue #3. Both sides are `issues` — one table, related to itself.
It's still many-to-many (an issue can block several and be blocked by several), so it still
needs a junction (§3). Both foreign keys point at the same table:

```
# illustration
issue_blocks
| blocker_id | blocked_id |
| 3          | 7          |   ← issue 3 blocks issue 7
  FK→issues.id  FK→issues.id
```

Here's what makes this one hard, and it's a genuine SQL fact, not an ORM quirk: **both FKs
point at `issues`, so the two columns are interchangeable as far as the schema is
concerned.** When you later ask "what does issue 3 block?", something has to know that
`blocker_id` means "me" and `blocked_id` means "them." The database doesn't know that — the
meaning lives in the *names*, and names are not semantics. `blocker_id` means something to
you; to the engine it's just a string.

That ambiguity is the only place in this schema where you must speak up and say which column
is which. In the ORM, that's §9.

---

## Part 2 — Then the ORM

The database is the truth. The ORM is a convenience layer that writes the SELECTs for you.
Everything here sits on top of Part 1 — if an ORM section confuses you, drop back to its SQL
section and the confusion usually dissolves.

### §6 — `relationship()` creates nothing; `ForeignKey` is the database's truth

These two get conflated constantly. They are **not** alternatives — you need both, and they
live in different worlds.

- **`ForeignKey`** is a *database* constraint. It's in the DDL, in the actual table, enforced
  by the database whether or not Python is running. `project_id = Column(Integer,
  ForeignKey("projects.id"))` creates a real column with a real constraint.
- **`relationship()`** is a *Python* convenience. It creates nothing in the database — not a
  column, not a constraint, not a table. It's the thing that lets you write `issue.project`
  and get an object back instead of writing the JOIN yourself.

```python
# illustration
project_id = Column(Integer, ForeignKey("projects.id"))  # the database's truth
project    = relationship("Project")                     # Python's convenience
```

You could delete every `relationship()` from `models.py` and the schema on disk would be
**identical** — you'd just have to hand-write every JOIN. When you touch `project.issues`,
SQLAlchemy emits `SELECT * FROM issues WHERE project_id = 1` (§2, run backwards) and hands
you objects. That's all it is.

> **`ForeignKey` = the database's truth. `relationship()` = Python's convenience.**

### §7 — `Table` vs mapped class: "do I want an object for this row?"

The insight that makes the whole schema click:

> **A declarative class IS a `Table` — plus a mapper that turns rows into Python objects.**

When you write `class Label(Base)`, SQLAlchemy builds a `Table` under the hood. You can see
it: `Label.__table__` is a real `Table`, the same kind of object as `issue_labels`. The class
adds exactly one thing on top — the mapper. So "should this be a bare `Table` or a class?" is
really one question:

> **Do I ever want a Python object for a row of this table?**

- `issue_labels` (§3) → **no.** A row is `(4, 1)` — pure linkage, no facts. An `IssueLabel`
  object would carry nothing you don't already have from the `Issue` and the `Label`. So skip
  the mapper: declare only the `Table`.
- `Label` → **yes, obviously.** A row is a real thing with a `name`, and you want
  `label.name`.
- `issue_assignments` (§4) → **yes** — and this is the one people get wrong. The row carries
  `role` and `assigned_at`. A bare `Table` has nowhere to hand those to you. So it *must*
  become a mapped class:

```python
# illustration
class IssueAssignment(Base):
    __tablename__ = "issue_assignments"
    issue_id    = Column(Integer, ForeignKey("issues.id"), primary_key=True)
    user_id     = Column(Integer, ForeignKey("users.id"),  primary_key=True)
    role        = Column(String)          # ← the reason this class exists
    assigned_at = Column(DateTime)
    issue = relationship("Issue", backref="assignments")
    user  = relationship("User",  backref="assignments")
```

**One extra column is the entire difference** between §3 and §4 at the ORM level. Build them
back to back so you feel it.

### §8 — `secondary=`: the two joins you didn't write

```python
# illustration
labels = relationship("Label", secondary=issue_labels, backref="issues")
```

This says: *"to get from an issue to its labels, hop through `issue_labels`."* It generates:

```sql
-- illustration
SELECT labels.* FROM labels
JOIN issue_labels ON labels.id = issue_labels.label_id
WHERE issue_labels.issue_id = 4
```

Note what comes back: **`Label` objects.** The junction appears in the SQL and then vanishes
from the Python. `issue.labels[0]` is a `Label`; you never see an `IssueLabel`, because there
is no such class (§7). To read a label's name you go `issue.labels[0].name` — the `.labels`
hop gives you Label objects, `.name` reads a column off one.

> **`secondary=` means "this table is plumbing — hide it from me."**

And that is precisely why it **cannot** express `issue_assignments`: `secondary=` throws the
junction row away and hands you the far-end objects, so there is physically nowhere for
`role` to be. The moment a link carries a fact, `secondary=` is the wrong tool and you need
the association object (§7). This is the association *table* vs association *object*
distinction, and it's a drill question.

### §9 — `primaryjoin` / `secondaryjoin`: naming those two joins yourself

`secondary=` is always **two** joins, even in the simple §8 case. They have names:

- **`primaryjoin`** — how I get from **me** to the junction table.
- **`secondaryjoin`** — how I get from the junction table to the **target**.

You never wrote them for labels because SQLAlchemy could *infer* them: `issue_labels` has one
FK to `issues` and one to `labels`, so "me" and "them" were obvious. In the self-referential
case (§5) that inference breaks — both FKs point at `issues` — so you must say it explicitly:

```python
# illustration  (this is the real line from models.py, wrapped for reading)
blocks = relationship(
    "Issue",
    secondary=issue_blocks,
    primaryjoin=id == issue_blocks.c.blocker_id,     # me   → junction: I am the blocker
    secondaryjoin=id == issue_blocks.c.blocked_id,   # junction → them: they are blocked
    backref="blocked_by",
)
```

Two pieces of syntax to notice:

- **`.c`** — to reference a column of a bare `Table` (not a mapped class) you use `.c`, for
  *columns*: `issue_blocks.c.blocker_id`. A mapped class exposes columns as plain attributes
  (`Issue.id`); a raw `Table` keeps them in `.c`. That difference is the visible seam between
  Core and ORM.
- **`id == issue_blocks.c.blocker_id`** — that `==` compares nothing. It **builds a
  WHERE-clause object.** Same machinery as `session.query(Issue).filter(Issue.status ==
  "open")` — the `==` is overloaded to construct SQL, not to evaluate a boolean.

Swap `primaryjoin` and `secondaryjoin` and you get the exact opposite meaning — that's §10.

### §10 — `backref`: one declaration, two attributes, and the swap

`backref` declares one side of a relationship and **generates the other**, from one line:

```python
# illustration
comments = relationship("Comment", backref="author")   # on User
```

That single line gives you both `user.comments` (a list) and `comment.author` (an object).
So you declare it **once, on one side only.** Declaring the reverse side by hand as well is
the classic crash:

```
# illustration
sqlalchemy.exc.ArgumentError: Error creating backref 'author' on relationship
'User.comments': property of that name exists on mapper 'mapped class Comment->comments'
```

Translation: *"I went to auto-create that attribute for you and found one already there, and
I won't silently clobber it."* The reverse name doesn't have to match the class name —
`backref="author"` reads better than `comment.user` would.

**The swap.** On a self-referential `secondary=` relationship (§9), `backref` generates the
reverse side by **swapping `primaryjoin` and `secondaryjoin`.** So `blocks` (I am the
blocker) becomes `blocked_by` (I am the blocked) — same table, same rows, read in the other
direction. **If it didn't swap them, `blocked_by` would be identical to `blocks`** and the
whole relationship would be pointless. This is the single most important thing to *watch
happen* in Part 3, not take on faith.

> One more `backref` subtlety, since it looks like it should collide but doesn't:
> `IssueAssignment` declares `backref="assignments"` on **both** its relationships. Fine —
> they create attributes on **different classes** (`Issue.assignments` and
> `User.assignments`). "Is the name taken?" is a question about a *class*, not about the
> file. The §10 crash above is two declarations fighting over the *same attribute on the same
> class*; this is two classes with one attribute each.

**2.0 note:** 2.0 prefers `back_populates`, declared explicitly on *both* sides, each naming
the other — more typing, but no invisible attributes appearing on your classes from a line in
some other file. This project uses `backref` **on purpose**, because it's the 1.4-ism and a
future `BREAKAGES.md` entry. Don't "fix" it.

### §11 — Quoted vs bare names: deferred resolution

```python
# illustration
class Issue(Base):
    comments = relationship("Comment", backref="issue")   # "Comment" — in quotes
```

`Comment` is defined *below* `Issue` in the file, so when Python executes that line the name
`Comment` doesn't exist yet. Unquoted, it would be an instant `NameError`. The string dodges
that: `"Comment"` is just text, and Python stores it without resolving anything.

Later, when `configure_mappers()` runs (§12), every class has been defined and `Base` has
been collecting them in a **registry** — a name→class dictionary. SQLAlchemy looks up
`"Comment"`, finds the class, and wires the relationship.

> **Deferred resolution: store a name now, look it up later, once the world is complete.**

This is exactly why `secondary=issue_labels` is different from `"Label"` on the same line:

```python
# illustration
labels = relationship("Label", secondary=issue_labels, backref="issues")
#                      ^^^^^^^            ^^^^^^^^^^^^
#                      string             bare Python name
#                      → deferred          → evaluated RIGHT NOW
```

`"Label"` resolves late, so it can sit above its class. `issue_labels` is a bare variable —
Python evaluates it on the spot — so the `Table` **must** be defined above `class Issue`.
(You *could* write `secondary="issue_labels"` as a string to defer it too, but the bare-object
form is what real 1.4 code uses, so: just put the `Table` above the class.)

> **A quoted name is a promise to resolve later. A bare name is a demand to resolve now.**

### §12 — Mappers configure lazily: why `check.py` exists

Importing `models.py` does **not** wire up the relationships. SQLAlchemy defers that work
until something first needs it, so a broken relationship stays completely silent at import
time. `configure_mappers()` forces the wiring to happen now — which is the whole job of
`check.py`:

```python
# runnable   →   uv run python -m experiments.sqlalchemy_1_4_vs_2_0.check
from sqlalchemy.orm import configure_mappers
from experiments.sqlalchemy_1_4_vs_2_0 import models  # noqa: F401
configure_mappers()
print("mappers configured OK")
```

The larger lesson is worth more than the API fact:

> **"It imported fine" ≠ "it works." A green result only tells you the thing you ran didn't
> fail. It says nothing about the thing you didn't run.**

`check.py` has printed `OK` while a schema had a duplicate-backref conflict, and while
`issue_labels` was wired to nothing at all — because those paths weren't exercised. This
instinct (run the thing that would actually fail) is worth more in an interview than any
single API detail.

### §13 — `remote_side`: what it IS for, and why *your* schema doesn't use it

`remote_side` is real and worth knowing — but it is **not** what your `blocks` /
`blocked_by` relationship uses, and the runbook was wrong to say so (now fixed).

`remote_side` is for a **self-referential *one*-to-many** — the *adjacency list*, where a row
carries a foreign key to its own table:

```python
# illustration  — NOT in this project; this is what remote_side is for
class Employee(Base):
    __tablename__ = "employees"
    id        = Column(Integer, primary_key=True)
    boss_id   = Column(Integer, ForeignKey("employees.id"))
    reports   = relationship("Employee", backref=backref("boss", remote_side=[id]))
```

Here there's **one** FK (`boss_id`) and **no junction table**. The ambiguity is different:
SQLAlchemy needs to know which side of the self-join is the "one" (the boss). `remote_side=[id]`
says "the `id` column is the far/parent end." That's its entire job.

Your `blocks` relationship is a **self-referential *many*-to-many** (§5): a junction table
(`issue_blocks`) with **two** FKs, resolved with `primaryjoin` / `secondaryjoin` (§9). Two
different self-referential shapes, two different knobs:

| Shape | Link lives in | Disambiguated by |
|---|---|---|
| self-ref one-to-many (adjacency list) | one FK column on the table | `remote_side` |
| self-ref many-to-many (yours) | a junction table, two FKs | `primaryjoin` / `secondaryjoin` |

If you ever need "issue → sub-issues" (a parent pointer), *that* would use `remote_side`. The
blocking graph does not.

---

## Part 3 — Verify it yourself

Run `explore.py` and paste its real output here — one entry per pattern. **Fill each
`OUTPUT PENDING` with verbatim output**, and write your prediction next to it. This section is
what turns every claim above from "the author said so" into "I watched the library do it."

```
# runnable   →   uv run python -m experiments.sqlalchemy_1_4_vs_2_0.explore
```

The seed (from the plan) is deliberately asymmetric so the swap in §10 has something to prove:
issue **9** sits on *both* sides of `issue_blocks`, and issue **3** is blocked by nothing.
`issue_blocks` rows: **(3→7), (3→9), (9→7)**.

### §2 — one-to-many · `apollo.issues`
- **Predict:** _(write it before running)_
- **Emitted SQL:** `<!-- OUTPUT PENDING -->`
- **Result:** `<!-- OUTPUT PENDING -->`

### §10 — backref with a renamed reverse · one comment's `.author`
- **Predict:**
- **Emitted SQL:** `<!-- OUTPUT PENDING -->`
- **Result:** `<!-- OUTPUT PENDING -->`

### §8 — `secondary=` · `issue3.labels`
- **Predict** — and answer both: does `issue_labels` appear in the SQL? in the Python result?
- **Emitted SQL:** `<!-- OUTPUT PENDING -->`
- **Result:** `<!-- OUTPUT PENDING -->`

### §7 — association object · `issue3.assignments[0].role` and `.user`
- **Predict** — note this is two hops, not one:
- **Emitted SQL:** `<!-- OUTPUT PENDING -->`
- **Result:** `<!-- OUTPUT PENDING -->`

### §9/§10 — the swap · `blocks` vs `blocked_by`
The load-bearing comparison. Put the two SQL statements **side by side** and mark what
swapped (the join vs. the WHERE).

| call | predict | emitted SQL | result |
|---|---|---|---|
| `issue3.blocks` | | `<!-- OUTPUT PENDING -->` | |
| `issue7.blocked_by` | | `<!-- OUTPUT PENDING -->` | |
| `issue3.blocked_by` | | `<!-- OUTPUT PENDING -->` | |
| `issue9.blocks` | | `<!-- OUTPUT PENDING -->` | |
| `issue9.blocked_by` | | `<!-- OUTPUT PENDING -->` | |

**What swapped:** `<!-- OUTPUT PENDING — mark the primaryjoin/secondaryjoin difference -->`

### §7 — a class IS a Table + a mapper · `Label.__table__` next to `issue_labels`
- **Predict:** what *kind* of object is each?
- **Result:** `<!-- OUTPUT PENDING -->`

### The surprise · does reading `issue3.title` after `commit()` emit SQL?
- **Predict** (don't look it up):
- **Emitted SQL:** `<!-- OUTPUT PENDING -->`
- **What this teaches:** `<!-- OUTPUT PENDING -->`
