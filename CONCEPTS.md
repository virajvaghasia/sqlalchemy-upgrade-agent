# Concepts — the SQLAlchemy relationship model, derived once

This is the **teaching** file: one canonical explanation per concept, built up from SQL
first. It is not a diary. The chronological record — what you hit, when, and the mistakes
along the way — lives in `LEARNING-LOG.md`, and each dated entry there links back to a
section number here (`§0`–`§15`). Those numbers are **stable anchors**; don't renumber them
casually, or the log's links rot.

If you find the same idea explained twice in this file, that's a bug — report it. The old
learning log explained `backref` three times in three different framings, and that is
exactly what made it impossible to read.

---

## Contents

**Part 0 — How to use this**

**Part 1 — From SQL, first** *(the database is the truth; the ORM only wraps it)*
- §0 — The whole schema on one screen
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

**Part 3 — Runtime** *(what happens when the code runs)*
- §14 — The session: staging, flushing, and the unit of work
- §15 — Expiry and lazy loading: where N+1 comes from

**Part 4 — Looking ahead to 2.0** *(unanswered on purpose)*

Each `§` is self-contained: the explanation, the **proof** from a real `explore.py` run, and a
**drill** with collapsed answers. You should never need a second file to finish a concept.

---

## Part 0 — How to use this

**Every claim about runtime behaviour in this file has a command that proves it.** That
command is `explore.py`, which builds the schema, seeds 21 traceable rows, and prints the
SQL SQLAlchemy actually emits for each relationship. Each section carries its own output,
under **Proof**.

The rule, which you will be tempted to break: **predict before you run.** Given a traversal,
write down what you think it returns *before* looking. A prediction is a derivation from the
rules in Parts 1–2, not a lookup — if you can't predict it, the mechanism isn't in your head
yet, and reading the answer won't put it there. The gap between your prediction and the real
output is the exact shape of what you misunderstood. Each section ends with a **Drill** whose
answers are collapsed — attempt them before expanding.

> **Don't take API claims on trust — make the library say it.** This file was written by a
> fallible author (human and AI both). The **Proof** blocks are where the library speaks
> for itself.

Code blocks are labelled: `# runnable` means it executes as written; `# illustration` means
it's a fragment or a "what SQL this becomes" sketch, not something to paste and run.

---

## Part 1 — From SQL, first

You know SQL. So don't start from SQLAlchemy — start from the tables, and let the ORM fall
out of them. Every "why" in Part 2 has a SQL answer here underneath it.

### §0 — The whole schema on one screen

Before any single pattern, the map. Six tables, four shapes, and every arrow is a real
`ForeignKey`:

```
# illustration

                        ┌────────────┐
                        │  projects  │
                        └─────┬──────┘
                              │ 1
                              │            §2  one-to-many
                              │            FK sits on the MANY side
                            ∞ ▼
   ┌────────┐  1      ∞ ┌────────────┐ ∞      1  ┌────────┐
   │ labels │◄──────────┤   issues   ├──────────►│ users  │
   └───┬────┘           └──┬──────┬──┘           └────┬───┘
       │                   │      │                   │
       │  ┌────────────────┘      └───────┐           │
       │  │                               │           │
       ▼  ▼                               ▼           ▼
  ┌──────────────┐   ┌──────────────┐  ┌──────────────────────┐
  │ issue_labels │   │ issue_blocks │  │  issue_assignments   │
  ├──────────────┤   ├──────────────┤  ├──────────────────────┤
  │ issue_id  FK │   │ blocker_id FK│  │ issue_id          FK │
  │ label_id  FK │   │ blocked_id FK│  │ user_id           FK │
  └──────────────┘   └──────┬───────┘  │ role         ← DATA! │
   §3  bare junction        │          │ assigned_at  ← DATA! │
   no data of its own       │          └──────────────────────┘
                            │           §4  junction WITH data
                     both FKs point                │
                     back at issues                ▼
                     §5  self-referential    must become a CLASS (§7)


   comments ── FK ──► issues        two FKs, two parents
   comments ── FK ──► users         (§2 twice over)
```

**Read it as four questions, in order:**

| Question | Answer | Section |
|---|---|---|
| How many of B does one A have? | one → FK on A. many → FK on B | §2 |
| Do *both* sides have many? | you need a third table | §3 |
| Does the link itself carry data? | yes → that table becomes a class | §4, §7 |
| Do both FKs point at the *same* table? | you must name the two joins yourself | §5, §9 |

Everything in Parts 1–2 is one of those four questions. If you can ask them in order about an
unfamiliar schema, you can derive its relationships without looking anything up.

### §1 — The one law: a column holds exactly one value

> **A column holds exactly one value.**

That is the whole foundation. Every relationship pattern in every ORM ever written is a
consequence of that one constraint. The next four sections are just that law, applied to
harder and harder shapes.

Here is the thing SQL will not let you write, and everything else follows from its absence:

```
# illustration
projects
| id | name   | issue_ids     |
| 1  | Apollo | [4, 7, 12, 88]│  ← ILLEGAL. a cell is not a list.
                └──────┬─────┘
                       │
        every pattern below exists to work around this one cell
```

You cannot store the list. So you have exactly three moves available, and there are no
others:

```
# illustration
  move 1 ─ put a single FK on the other table          → §2  one-to-many
  move 2 ─ invent a table whose ROWS are the links     → §3  many-to-many
  move 3 ─ give those link-rows their own columns      → §4  junction with data
```

That is the entire design space. §5 is not a fourth move — it's move 2 applied to a table and
*itself*, which creates an ambiguity but no new mechanism.

**Drill.**

1. Why can't `projects.issue_ids` hold `[4, 7, 12]`? Answer without using the word "normalisation".
2. Name the three moves available once you accept that constraint.

<details>
<summary>Answers</summary>

**1.** Because a column holds exactly one value, and a list is many values. There is nowhere
to put the second element. (Postgres arrays and JSON columns exist and do break this — but
they also give up the FK constraint, indexing behaviour and join semantics that make the
relational model worth using, which is why the ORM patterns are all built on the one-value
assumption.)

**2.** A single FK on the many side (§2); a junction table whose rows are the links (§3);
that same junction with extra columns of its own (§4).

</details>

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


**Proof — from a real run.**

**Emitted SQL:**
```sql
SELECT issues.id, issues.title, issues.description, issues.status,
       issues.created_at, issues.project_id
FROM issues
WHERE ? = issues.project_id
```
**Result:** all 9 `Issue` objects.

**What it proves.** One SELECT against `issues` alone — no join, because the FK lives *on the
issues table* (§2). The parameter is `apollo.id`. Note also that `project_id` came out `1` for
all nine although it was never assigned by hand: attaching via `apollo.issues.append(...)`
let the unit of work resolve the object reference into an integer at flush time.

**Drill.**

1. Why is the FK forced onto the *many* side? Answer from the one-value-per-column law, not from convention.
2. You write `issue.project = apollo` before `apollo` has ever been flushed, so `apollo.id` is still `None`. Does it work? What is stored on `issue` at that moment?
3. Which emits a join: `apollo.issues`, or `issue.project`?

<details>
<summary>Answers</summary>

**1.** One column holds one value. A project has many issues, so an `issue_id` column on `projects` would need many values — illegal. Each issue has exactly one project, so `project_id` fits on `issues` as a single value. The FK lands on the many side because that is the only side where it *fits*.

**2.** It works. `issue.project` holds a **reference to the Python object** — plain in-memory identity, no SQL involved. At flush the unit of work walks the graph, inserts `apollo` first if needed, reads its new PK, and uses it as `issue.project_id`. This is why relationship attributes beat hand-written FKs: insert ordering is solved for you.

**3.** Neither. `apollo.issues` is one SELECT against `issues` filtered by `project_id`; `issue.project` is a SELECT against `projects` by PK. The FK is a column on one table, so no join is needed either way. Joins appear for `secondary=` (§8).

    But `issue.project` often emits **nothing at all** — many-to-one has a "use get" optimisation: SQLAlchemy already has `project_id`, so it checks the session's identity map by PK first and only queries on a miss. Measured: first access in a fresh session emits the SELECT, the second emits nothing. So "does this attribute emit SQL?" has no fixed answer — it depends what the session has already seen. It is also why a `.project` loop over nine issues fires **one** query while a `.labels` loop fires nine (§15).

</details>

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


**Drill.**

1. Why is a third table unavoidable for issues↔labels? Derive it, don't assert it.

<details>
<summary>Answers</summary>

**1.** One issue has many labels and one label has many issues. `label_id` on `issues` breaks the one-value law for any issue with two labels; `issue_id` on `labels` breaks it the other way. Neither existing table can hold it, so the link needs a table of its own — one row per pair.

</details>

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


**Drill.**

1. What is the *one* question that decides between a bare `Table` and a mapped class?
2. `IssueAssignment` has a composite PK `(issue_id, user_id)`. What does that permit, and what does it forbid?

<details>
<summary>Answers</summary>

**1.** *Does the link itself carry information?* No → bare `Table`. Yes → mapped class. Equivalently §7's phrasing: do I want an object for this row?

**2.** Permits: the same user on many issues, and many users on one issue. Forbids: the same `(issue, user)` pair twice — so Bob cannot be both owner *and* reviewer on issue 1 under this schema. Confirmed by triggering it: `IntegrityError: UNIQUE constraint failed: issue_assignments.issue_id, issue_assignments.user_id`. A real modelling constraint, not an accident.

</details>

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

**Why `issue_labels` has no such problem, side by side:**

```
# illustration

  issue_labels                          issue_blocks
  ┌──────────┬──────────┐               ┌────────────┬────────────┐
  │ issue_id │ label_id │               │ blocker_id │ blocked_id │
  └────┬─────┴─────┬────┘               └─────┬──────┴──────┬─────┘
       │           │                          │             │
       ▼           ▼                          ▼             ▼
   issues      labels                      issues        issues
   ════════════════════                    ══════════════════════
   DIFFERENT tables.                       SAME table.
   "which one is the Issue side?"          "which one is ME?"
   → the FK target answers it.             → NOTHING answers it.
   → SQLAlchemy infers it.                 → YOU must say. (§9)
```

Starting from an `Issue` and walking into `issue_labels`, exactly one of the two columns
points back at `issues` — so there is no choice to make. Walking into `issue_blocks`, **both**
do. The engine has two equally valid options and no way to prefer one.

That ambiguity is the only place in this schema where you must speak up and say which column
is which. In the ORM, that's §9.


**Drill.**

1. `issue_labels` needs no `primaryjoin`. `issue_blocks` does. What changed?

<details>
<summary>Answers</summary>

**1.** In `issue_labels` the two FKs point at **different** tables, so which side is which can be inferred. In `issue_blocks` both point at `issues.id` — genuinely ambiguous. You must say which column means "me" and which means "them".

</details>

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


**Drill.**

1. What does `relationship()` create in the database?

<details>
<summary>Answers</summary>

**1.** **Nothing.** It is pure Python-side convenience. `ForeignKey` creates the actual constraint. Delete every `relationship()` and the schema is unchanged; delete the `ForeignKey` and the database stops enforcing anything.

</details>

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


**Proof — from a real run.**

**Result:**
```
issue3.assignments         -> [<IssueAssignment issue=3 user=2 role='owner'>]
issue3.assignments[0].role -> owner
issue3.assignments[0].user -> <User 2 'Bob'>
```

**What it proves — the contrast with §8 above.** `issue3.labels` gave back `Label` objects
directly, one hop. Here the first hop lands on an `IssueAssignment` — the junction row *as an
object* — and `.user` is a second hop. That extra hop is the entire cost of the association
object, and the reason it buys you `role`. There is no `issue.users` shortcut.


**Proof — the two objects side by side.**

**Result:**
```
type(Label)             -> DeclarativeMeta          # a class
type(Label.__table__)   -> sqlalchemy.sql.schema.Table
type(issue_labels)      -> sqlalchemy.sql.schema.Table
Label.__mapper__        -> mapped class Label->labels
hasattr(issue_labels, "__mapper__") -> False
```

**What it proves.** `Label.__table__` and `issue_labels` are **the same kind of object** — both
plain `Table`. The only difference is that a mapper was attached to one of them. That is the
literal content of §7's rule: *a mapped class is a Table plus a mapper.* Ask "do I want an
object for this row?" — if no, stop at the `Table`.

**Drill.**

1. Why can `role` not live on a `secondary=` relationship? Be specific about what `secondary=` hands back.
2. What does the association object cost you at every traversal, forever?
3. `Label.__table__` and `issue_labels` — what type is each?

<details>
<summary>Answers</summary>

**1.** Because `secondary=` hands back the **target** objects (`User`) and hides the junction row entirely. `role` describes the *link*, not the user — Bob is not globally "a reviewer", he is a reviewer *on issue 1*. With the row hidden there is no object to hang it on. So the row is promoted to a class: the association object.

**2.** One extra hop. No `issue.users`; you go `issue.assignments → .user`. That is the price of the payload.

**3.** Both are `sqlalchemy.sql.schema.Table`. The *only* difference is that a mapper is attached to one (`hasattr(issue_labels, "__mapper__")` → `False`). A mapped class **is** a Table plus a mapper.

</details>

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

**The two hops, and which one you can see:**

```
# illustration

  issue.labels                          issue.assignments
  ────────────                          ─────────────────

  Issue(3)                              Issue(3)
     │                                     │
     │ hop 1  primaryjoin                  │ hop 1  ordinary one-to-many
     ▼                                     ▼
  ┌───────────────────┐                 ┌──────────────────────────┐
  │ issue_labels row  │  ← hidden       │ IssueAssignment object   │ ← VISIBLE
  │ (3, 1)            │     from you    │ .role = 'owner'          │    you hold it
  └───────────────────┘                 │ .assigned_at = ...       │
     │                                  └──────────────────────────┘
     │ hop 2  secondaryjoin                 │
     ▼                                     │ hop 2  you write it: .user
  ┌───────────┐                            ▼
  │ Label(1)  │  ← what you get         ┌──────────┐
  │ .name     │                         │ User(2)  │
  └───────────┘                         └──────────┘

  ONE expression, TWO joins.            TWO expressions, TWO joins.
  Junction discarded → no room          Junction kept as an object →
  for role.                             role has somewhere to live.
```

That picture is the whole §7-vs-§8 decision. `secondary=` collapses both hops into one
attribute access and throws the middle away; the association object stops at the middle and
makes you take the second hop by hand. You are trading a keystroke for a place to put data.

And that is precisely why `secondary=` **cannot** express `issue_assignments`: it throws the
junction row away and hands you the far-end objects, so there is physically nowhere for
`role` to be. The moment a link carries a fact, `secondary=` is the wrong tool and you need
the association object (§7).


**Proof — from a real run.**

**Emitted SQL:**
```sql
SELECT labels.id, labels.name
FROM labels, issue_labels
WHERE ? = issue_labels.issue_id AND labels.id = issue_labels.label_id
```
**Result:** `[<Label 1 'bug'>, <Label 3 'ui'>]`

**Both halves of the question, answered:**
- *Does `issue_labels` appear in the SQL?* **Yes** — it must, it holds the link.
- *Does it appear in the Python result?* **No** — you get `Label` objects only. `secondary=`
  traverses the junction and then hides it. That is the whole point of §8, and precisely why
  it cannot carry a payload (§4, §7) — there is no object handed back to hang `role` on.

**Drill.**

1. `issue1.labels.append(bug)` — at flush, which tables get written to?
2. Where does `bug.issues` come from, given `Label` declares no such attribute?

<details>
<summary>Answers</summary>

**1.** Only `issue_labels`, with `INSERT INTO issue_labels (issue_id, label_id)`. **Neither `issues` nor `labels` is touched** — no column on either changes. That is the structural difference from the FK case, where an existing row's column is updated.

**2.** From `backref="issues"` on `Issue.labels`. One declaration, two attributes (§10).

</details>

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

**The same three rows, walked in both directions.** This is the picture worth memorising:

```
# illustration          issue_blocks
                     ┌────────────┬────────────┐
                     │ blocker_id │ blocked_id │
                     ├────────────┼────────────┤
                     │     3      │     7      │
                     │     3      │     9      │
                     │     9      │     7      │
                     └────────────┴────────────┘

  issue9.blocks  ("what do I block?")   issue9.blocked_by ("who blocks me?")
  ───────────────────────────────────   ───────────────────────────────────
  primaryjoin  : id = blocker_id        primaryjoin  : id = blocked_id
       9 ──────────► rows (9, 7)             9 ──────────► rows (3, 9)
                          │                                    │
  secondaryjoin: id = blocked_id        secondaryjoin: id = blocker_id
                          ▼                                    ▼
                     ┌────────┐                          ┌────────┐
                     │Issue(7)│                          │Issue(3)│
                     └────────┘                          └────────┘

           ▲                                       ▲
           └──────── the SAME two conditions, ─────┘
                     used in opposite roles
```

Read the two columns of that diagram top to bottom: `primaryjoin` picks *which rows are
mine*, `secondaryjoin` picks *which column of those rows is the answer*. Trade the two
conditions and "what do I block" becomes "who blocks me" — same table, same three rows, no
new SQL concept.

Swap `primaryjoin` and `secondaryjoin` and you get the exact opposite meaning — that's §10.


**Proof — from a real run.**

The load-bearing comparison. Both queries, verbatim, differing in exactly two places:

```sql
--  issue3.blocks                                    -- issue7.blocked_by
SELECT issues.* FROM issues, issue_blocks            SELECT issues.* FROM issues, issue_blocks
WHERE ? = issue_blocks.blocker_id                    WHERE ? = issue_blocks.blocked_id
  AND issues.id = issue_blocks.blocked_id              AND issues.id = issue_blocks.blocker_id
```

| call | result |
|---|---|
| `issue3.blocks` | `[<Issue 7>, <Issue 9>]` |
| `issue7.blocked_by` | `[<Issue 3>, <Issue 9>]` |
| `issue3.blocked_by` | `[]` — nothing blocks issue 3 |
| `issue9.blocks` | `[<Issue 7>]` |
| `issue9.blocked_by` | `[<Issue 3>]` — issue 9 is on **both** sides |

**What swapped.** Read straight off the mapper, not inferred:

```
Issue.blocks       primaryjoin  : issues.id = issue_blocks.blocker_id
                   secondaryjoin: issues.id = issue_blocks.blocked_id
Issue.blocked_by   primaryjoin  : issues.id = issue_blocks.blocked_id
                   secondaryjoin: issues.id = issue_blocks.blocker_id
```

The same two conditions, in opposite order. `primaryjoin` is *me → junction*; `secondaryjoin`
is *junction → them*. Only the first pair was written by hand — `backref="blocked_by"`
generated the second by trading them.

**Why it matters.** Had `backref` reused the joins unswapped, `blocked_by` would filter on
`blocker_id` too and return byte-identical results to `blocks` — two names for one direction,
and no way to ask "who is blocking me?". `issue9` proves the swap fires: it returns `[7]` one
way and `[3]` the other, from the same three rows.

**Drill.**

1. In your own words: what does `primaryjoin` mean? What does `secondaryjoin` mean?
2. Given rows `(blocker_id, blocked_id) = (3,7) (3,9) (9,7)`, work out by hand: `issue3.blocks`, `issue3.blocked_by`, `issue9.blocks`, `issue9.blocked_by`, `issue7.blocks`.
3. Why is issue **9** the important one in that dataset?

<details>
<summary>Answers</summary>

**1.** `primaryjoin` = how to get from **me** to the junction table. `secondaryjoin` = how to get from the junction table to **them**.

**2.** `[7, 9]` · `[]` · `[7]` · `[3]` · `[]`

**3.** It appears on **both** sides — it blocks 7 and is blocked by 3. So it returns different, non-empty answers in each direction, making it the only row that can actually *prove* the swap fired. Issues 3 and 7 each return `[]` one way, which a broken implementation could produce by accident too.

</details>

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
happen* in §9's proof, not take on faith.

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


**Proof — from a real run.**

**Result:**
```
c3 -> <Comment 3 issue=3 user=1> | author: <User 1 'Alice'> | issue: <Issue 3 '...'>
```

**What it proves.** `Comment`'s class body declares **neither** `.author` **nor** `.issue`.
Both were injected from *other* classes: `User.comments = relationship(..., backref="author")`
and `Issue.comments = relationship(..., backref="issue")`. Two attributes appearing on a class
from two lines written elsewhere in the file — the readability cost §10 warns about, and
exactly why 2.0 prefers `back_populates`.

**Drill.**

1. `Issue` has `project_id` in its class body but no `project`. So why does `issue.project = apollo` work?
2. What happens if you declare the reverse side by hand as well? Quote the shape of the error.
3. `IssueAssignment` declares `backref="assignments"` on **both** relationships. Why is that not a collision?
4. Why does 2.0 prefer `back_populates`? Why is this repo keeping `backref` anyway?

<details>
<summary>Answers</summary>

**1.** `Project` declares `issues = relationship("Issue", backref="project")`. That `backref` generates `.project` **on `Issue`**, from a line in a different class. Nothing in `Issue`'s body reveals it.

**2.** `ArgumentError: Error creating backref 'X' on relationship 'A.b': property of that name exists on mapper 'mapped class B'` — *I went to auto-create that attribute and found one already there, and I will not silently clobber it.*

**3.** The two generated attributes land on **different classes** — `Issue.assignments` and `User.assignments`. "Is this name taken?" is a question about a class, not a file.

**4.** `back_populates` is declared explicitly on *both* sides, each naming the other — more typing, no attributes materialising on your class from a line elsewhere. This repo keeps `backref` **on purpose**: it is the 1.4-ism and a future `BREAKAGES.md` entry. Don't "fix" it.

</details>

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


**Drill.**

1. Why are target classes written as `"Comment"` in quotes rather than bare `Comment`?

<details>
<summary>Answers</summary>

**1.** Deferred resolution. When `User` is being defined, `Comment` may not exist yet. The string resolves later, at mapper configuration — which is also why a typo in it surfaces then rather than at import.

</details>

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


**Drill.**

1. Why is `check.py` printing green not proof the mappers are right?

<details>
<summary>Answers</summary>

**1.** It only forces mapper *configuration*. It proves the mappers can be built — not that they express what you meant. It has printed `OK` while `issue_labels` was wired to nothing at all. Green means "not obviously broken", never "correct".

</details>

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


**Drill.**

1. Does this schema use `remote_side`? If not, what *is* it for?

<details>
<summary>Answers</summary>

**1.** No. `remote_side` is for a self-referential **one**-to-many (adjacency list — the `employee.boss` shape), where one table has an FK into itself and there is no junction table. Yours is a self-referential *many*-to-many, which uses `primaryjoin`/`secondaryjoin`. The runbook originally got this wrong; corrected in `cbc94e1`.

</details>

---

---

## Part 3 — Runtime: the session, and when SQL actually fires

Parts 1–2 are about *shape*. This part is about *behaviour at run time* — what the session
does with your objects, and when a plain attribute access turns into a query.

**The seed.** Deliberately asymmetric, so the swap in §10 has something to prove:

| table | rows |
|---|---|
| `users` | `alice`(1), `bob`(2) |
| `projects` | `apollo`(1) |
| `issues` | 1–9, all `project_id=1` |
| `labels` | `bug`(1), `urgent`(2), `ui`(3) |
| `issue_labels` | (1,1) (1,2) (2,3) (3,1) (3,3) (7,2) |
| `comments` | c1→issue1/alice, c2→issue1/bob, c3→issue3/alice |
| `issue_assignments` | (1,alice,owner) (1,bob,reviewer) (3,bob,owner) |
| `issue_blocks` | **(3→7) (3→9) (9→7)** |

Issue **9** sits on *both* sides. Issue **3** blocks two things and is blocked by nothing.
Issue **7** is blocked by two things and blocks nothing.

### §14 — The session: staging, flushing, and the unit of work

`sessionmaker` is a **class**. `Session = sessionmaker(bind=engine)` makes `Session` an
**instance** of it — a configured, *callable* factory. `session = Session()` produces the
genuine `sqlalchemy.orm.Session`, a third object, the one that talks to the database. The
capital-S naming is a SQLAlchemy idiom, not a Python rule.

Binding the engine at construction is a **configuration-object** pattern, not a requirement:
`sessionmaker()` can be built unbound and overridden per call with `Session(bind=other)`. You
set what rarely changes once, then call the factory many times.

**`add()` stages. `flush()` writes. `commit()` ends the transaction.**

```
# runnable   →   uv run python -m experiments.sqlalchemy_1_4_vs_2_0.explore
before add   -> None None None
after add    -> None None None
after flush  -> 1 2 1
```

`add()` emits no SQL and assigns no key. `flush()` emits the INSERTs, and the database's
generated PKs are written back onto the Python objects. `commit()` does that *and* closes the
transaction — so flushing mid-script keeps a whole seed as one atomic unit that a later
failure rolls back together.

> **The save-update cascade.** Attaching an object to something already in the session
> enrolls it too. `explore.py` never calls `session.add()` on 8 of its 9 issues — they arrive
> via `apollo.issues.append(...)`, and setting the other direction (`issue.project = apollo`)
> works the same way, because the `backref` populates `apollo.issues` in memory first.

**The five states an object can be in.** Nearly every confusing SQLAlchemy error is really
"this object was not in the state you assumed":

```
# illustration

   Issue(title="x")          ← you just constructed it
        │
        │  TRANSIENT   not in a session, no row anywhere
        │
        ▼  session.add()  /  cascade from an attached parent
   ┌─────────────┐
   │   PENDING   │  in the session, still no row in the DB
   └──────┬──────┘
          │  session.flush()   ← INSERT runs, PK comes back
          ▼
   ┌──────────────────────────────────┐
   │           PERSISTENT             │  row exists in the DB
   │  ┌────────────────────────────┐  │
   │  │ expired flag: on / off     │◄─┼── commit() turns it ON
   │  │ on  → next read re-SELECTs │  │   a read turns it back off
   │  └────────────────────────────┘  │
   └───────────────┬──────────────────┘
                   │  session.close()  /  session goes out of scope
                   ▼
            ┌─────────────┐
            │  DETACHED   │  row exists, object alive, NO session behind it.
            └─────────────┘  → unloaded attributes raise DetachedInstanceError
```

**Note the shape of that middle box.** "Expired" is *not* a fifth state — it is a flag on a
persistent object. `inspect(obj)` reports `persistent` both before and after `commit()`; what
changes is `inspect(obj).expired`. Worth getting right, because "expired" and "detached" sound
similar and behave completely differently: an expired object silently re-queries, a detached
one raises.

Traced with `inspect()`, one line per moment — measured, not sketched:

| moment | state | `.expired` | `issue.id` | reading `issue.labels` |
|---|---|---|---|---|
| `Issue(...)` | `transient` | — | `None` | `[]` — empty list, no query |
| `issue.project = p` | `pending` | — | `None` | `[]` |
| `session.flush()` | `persistent` | `False` | `1` | SELECT fires |
| `session.commit()` | `persistent` | **`True`** | re-SELECTs | SELECT fires |
| `session.close()` | `detached` | — | `1` (already loaded) | **raises** |

```
# runnable   →   the exact output the table above was built from
constructed : transient  | id: None | labels: []
after attach: pending    | id: None
after flush : persistent | id: 1
after commit: persistent | expired attrs: True
identity map: a is b -> True
after close : detached   | id still readable: 1
   i.labels -> DetachedInstanceError CONFIRMED
```

The last row is the one that bites people, and it is the whole mechanism behind the
`DetachedInstanceError` question in Part 4: returning an ORM object out of a function whose
session has closed, then touching a relationship on it in the caller. Note the asymmetry —
`issue.id` still works because it was loaded before the close; `issue.labels` was never
loaded, and now there is no session left to load it with.

> **The identity map.** Inside one session, one row = one Python object, always. Query the
> same issue twice and you get the *same* object back (`a is b` → `True`), not two copies.
> That's also the "use get" optimisation from §2's drill: a many-to-one like `issue.project`
> checks this map by primary key before it considers emitting SQL.

**Drill.**

1. What exactly does `session.add(obj)` do — and what does it *not* do?
2. `flush()` vs `commit()` — name two differences.
3. You only ever do `apollo.issues.append(issue)`, never `session.add(issue)`. Does it get inserted? Name the mechanism.
4. `apollo.id` is `1` and `alice.id` is also `1`. Is something broken?

<details>
<summary>Answers</summary>

**1.** Stages it as pending. No SQL, no primary key, no contact with the database.

**2.** (a) `flush()` leaves the transaction **open**, `commit()` ends it. (b) `commit()` also
expires every loaded attribute (§15).

**3.** Yes. The default **`save-update` cascade** — attaching to an object already in the
session enrolls the attached object too.

**4.** No. Different tables have independent autoincrement counters.

</details>

### §15 — Expiry and lazy loading: where N+1 comes from

Start with the question that catches everyone:

> **You `commit()`. Then you read `apollo.name` — a plain string that was sitting in memory a
> microsecond ago. Does SQL fire?**

**Yes.** Measured:

```sql
SELECT projects.id, projects.name, projects.created_at
FROM projects WHERE projects.id = ?
```

`Session` defaults to `expire_on_commit=True`. Committing flips the expired flag on every
persistent object (§14), so the *next* attribute access re-reads the row. It is not a
performance bug — it is a correctness trade. After your commit, another transaction may have
changed that row; the value in memory is no longer guaranteed true.

Now combine that with the *other* default — relationships are `lazy="select"`, meaning they
load on first touch, one query each. Put a loop around them and you have N+1:

```
# illustration — the real timeline from explore.py §7

  session.commit()          ← everything is now expired
       │
       ▼
  apollo.name         ──────────────────────────► SELECT projects  ... 1
       │
       ▼
  apollo.issues       ──────────────────────────► SELECT issues    ... 1
       │                                                              ─────
       │  ┌── issue 1 ─► issue.labels ──► SELECT labels  ┐              2 so far
       │  │   issue 2 ─► issue.labels ──► SELECT labels  │
       │  │   issue 3 ─► issue.labels ──► SELECT labels  │
       └──┤   issue 4 ─► issue.labels ──► SELECT labels  ├─ 9 queries ... 9
          │   ...                                        │   ONE PER ROW
          │   issue 9 ─► issue.labels ──► SELECT labels  ┘              ─────
          └── the "+N"                                                   11
```

**The "1" is the collection query. The "+N" is one query per row inside the loop.** That is
the whole definition, and the reason it scales so badly: at 200 issues (Step 3) this same
loop becomes **202 queries**, and each one is a full network round trip.

**The two standard fixes**, both one keyword:

```python
# illustration
from sqlalchemy.orm import selectinload, joinedload

session.query(Issue).options(selectinload(Issue.labels))   # 2 queries total
session.query(Issue).options(joinedload(Issue.labels))     # 1 query total
```

| | queries | how | when it's wrong |
|---|---|---|---|
| `lazy="select"` (default) | 1 + N | one SELECT per parent, on touch | any loop |
| `selectinload` | 2 | second SELECT with `WHERE id IN (...)` | almost never — good default for collections |
| `joinedload` | 1 | LEFT JOIN, rows multiplied then de-duplicated | large collections — the JOIN returns parent columns repeated per child |

**Counted, not claimed** — same 9 issues, same loop, a query counter on the engine:

```
# runnable  →  loop 9 issues, touch .labels on each
lazy (default)           10 queries      ← 1 + 9
selectinload              2 queries
joinedload                1 queries
```

`selectinload` is the better default for collections precisely because it doesn't multiply
rows; `joinedload` earns its keep on many-to-one (`issue.project`), where there is exactly one
row on the far side and no duplication to pay for.

> **Write the number down.** 11 queries for 9 issues is the baseline. Step 5 asks for the same
> count at ~200 rows, and the before/after is the story you tell an interviewer — "I found a
> 202-query page and made it 2" is a sentence with evidence behind it.

**Drill.**

1. What is `expire_on_commit`, and what is the argument for leaving it on?
2. Walk the query count: commit, read `apollo.name`, read `apollo.issues`, then loop all 9 issues reading `issue.labels`. Total?
3. Which part is the N+1, and what are the two standard fixes?

<details>
<summary>Answers</summary>

**1.** The `Session` flag that marks loaded attributes stale at commit. Leaving it on trades
queries for correctness: after a commit another transaction may have changed the row, so
cached values are no longer guaranteed true.

**2.** **11.** One for `apollo.name`, one for `apollo.issues`, nine for the labels.

**3.** The 9 label queries — one query for the collection, then N more inside the loop. Fixes:
`selectinload()` (a second SELECT with `IN (...)`) or `joinedload()` (one SELECT with a JOIN).
`selectinload` is usually the better default for collections.

</details>

---

## Part 4 — Looking ahead to 2.0

Deliberately unanswered. These get settled by *running* Step 6, not by reading — write your
predictions in `LEARNING-LOG.md` first so the comparison is real.

1. `SQLALCHEMY_WARN_20=1` on the current code — which lines do you expect it to flag? List
   them by file and construct **before** running.
2. Which of these breaks in 2.0, and what replaces each: `session.query(Issue)`,
   `Query.get(id)`, `engine.execute("SELECT ...")`, `declarative_base()` imported from
   `sqlalchemy.ext.declarative`?
3. Predict the `DetachedInstanceError` scenario: what must happen, in what order, for it to
   fire?
4. Does `backref` still work in 2.0? Is "still works" the same as "still recommended"?
