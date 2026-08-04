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

**Part 4 — Looking ahead to 2.0** *(why it changed, and how to triage it)*
- §16 — Why 2.0 exists: one way to do things, instead of two
- §17 — Reading the warnings: four classes, only one is an emergency
- §18 — `future=True`: run 2.0's rules without installing 2.0
- §19 — What 2.0 does *not* fix
- Predictions — *deliberately unanswered; you settle these by running the upgrade*

Each `§` is self-contained: the explanation, the **proof** from a real run, and a **drill**
with collapsed answers. You should never need a second file to finish a concept.

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

**1. Short answer:** a cell holds **one** value. `[4, 7, 12]` is three. There is physically
nowhere to put the 7 and the 12.

Picture the table. One row, one column, one box:

```
projects
| id | name   | issue_ids |
| 1  | Apollo |    4      |  ← where do 7 and 12 go? There is no second box.
```

*Side note, not the main point:* Postgres does have array and JSON columns that would let you
cram a list in. But you lose foreign-key checking, normal indexing, and the ability to join on
it — the three things that make a relational database worth using. Every ORM pattern in this
document assumes the one-value rule, so that's the rule we work from.

**2. Short answer:** put the link on the many side, or invent a table for the links, or give
that table extra columns.

| move | what it looks like | section |
|---|---|---|
| one FK column | `issues.project_id` | §2 |
| a table of links | `issue_labels(issue_id, label_id)` | §3 |
| that table, plus columns | `issue_assignments(..., role)` | §4 |

Everything else in Part 1 is one of these three.

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

**1. Short answer:** because the many side is the only side where it *fits*.

Ask "how many of the other thing does each row have?"

- A **project** has many issues → an `issue_id` box on `projects` would need to hold many
  values. Illegal.
- An **issue** has exactly one project → a `project_id` box on `issues` holds one value. Legal.

The FK isn't placed on the many side by convention or by taste. It's the only placement that
doesn't break the one-value rule.

**2. Short answer:** yes, it works — and at that moment `issue` stores **the Python object
itself**, not a number.

Walk it through:

```
1. issue.project = apollo     →  issue now points at the apollo OBJECT in memory.
                                 No SQL. No id needed. apollo.id is still None.
2. session.flush()            →  SQLAlchemy sees issue depends on apollo, so:
                                   INSERT apollo   →  database returns id = 1
                                   reads that 1 back onto apollo.id
                                   INSERT issue with project_id = 1
```

**Why this matters:** SQLAlchemy worked out the *insert order* for you. If you had assigned
`issue.project_id = apollo.id` by hand, you'd have stored `None`, because `apollo.id` doesn't
exist until after its INSERT. Using the relationship attribute lets you ignore ordering
entirely.

**3. Short answer:** neither one joins.

| you write | SQL shape | why no join |
|---|---|---|
| `apollo.issues` | `SELECT * FROM issues WHERE project_id = 1` | the FK is a column *on* `issues` |
| `issue.project` | `SELECT * FROM projects WHERE id = 1` | the FK value is already in hand |

A join is only needed when you must pass *through* a third table to get somewhere — that's
`secondary=` (§8).

> **A wrinkle worth knowing: `issue.project` often emits no SQL at all.**
>
> `issue` already holds `project_id = 1`. Before querying, SQLAlchemy checks the session's
> identity map — its private "row 1 of projects = this Python object" lookup — and if project 1
> is already there, it just hands it over. Free.
>
> Measured: the **first** `issue.project` in a fresh session emits the SELECT; the **second**
> emits nothing.
>
> This is also why a loop reading `.project` on nine issues costs **1** query, while the same
> loop reading `.labels` costs **9** (§15). All nine issues share one project, so the map hits
> eight times out of nine. Labels differ per issue, so nothing can be reused.

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

**1. Short answer:** both sides need a list, and neither table can hold one — so the link gets
its own table.

Try both placements and watch each one fail:

```
attempt 1: put label_id on issues
| id | title       | label_id |
| 1  | Login fails |   bug    |  ← issue 1 also has "urgent". No box for it. ✗

attempt 2: put issue_id on labels
| id | name | issue_id |
| 1  | bug  |    1     |  ← "bug" is also on issue 3. No box for it. ✗
```

Two failures, same cause: one box, two values. Since neither existing table can hold the link,
you make a table **whose rows *are* the links**:

```
issue_labels
| issue_id | label_id |
| 1        | 1        |  ← issue 1 is "bug"
| 1        | 2        |  ← issue 1 is ALSO "urgent"   ← the second value now has a home
| 3        | 1        |  ← "bug" is ALSO on issue 3
```

Rows are unlimited, so both "lists" fit. That's the whole derivation.

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

**1. Short answer:** *"Does the link itself carry information?"*

- **No** → bare `Table`. The link is just "these two are connected."
- **Yes** → mapped class. The link has something to say.

Compare the two in this project:

```
issue_labels        | issue_id | label_id |              ← nothing but the pairing
issue_assignments   | issue_id | user_id | role | ...|   ← the pairing KNOWS something
```

§7 asks the same question from the Python side: *do I want an object I can read `.role` off of?*

**2. Short answer:** it permits many-to-many, and forbids listing the same pair twice.

A composite primary key means **the combination** must be unique — not each column on its own.

| | allowed? | why |
|---|---|---|
| alice on issue 1, alice on issue 3 | ✅ | different pairs |
| alice on issue 1, bob on issue 1 | ✅ | different pairs |
| bob on issue 1 as `owner`, bob on issue 1 as `reviewer` | ❌ | **same pair, twice** |

That last row is the interesting one. Under this schema **one person gets one role per issue** —
Bob cannot be owner *and* reviewer of the same issue. Confirmed by actually trying it:

```
IntegrityError: UNIQUE constraint failed:
    issue_assignments.issue_id, issue_assignments.user_id
```

That's a real modelling decision, not an accident. If you needed Bob to hold two roles, the PK
would have to become `(issue_id, user_id, role)`.

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

**1. Short answer:** in `issue_labels` the two columns point at **different** tables, so
SQLAlchemy can work out which is which. In `issue_blocks` they point at the **same** table, so
it can't.

Put yourself in SQLAlchemy's position. You're standing on an `Issue` and you want to walk
across the junction. You must pick which column is "me":

```
issue_labels                          issue_blocks
| issue_id | label_id |               | blocker_id | blocked_id |
     ↓          ↓                            ↓            ↓
  issues     labels                       issues       issues

"which is the issue side?"            "which one is ME?"
Only one points at issues.            BOTH point at issues.
→ no choice to make. ✅                → two equally valid answers. ✗
```

**The trap:** the names *look* like they settle it. They don't. `blocker_id` means something
to you; to SQLAlchemy it's just a string of characters — it has no idea "blocker" implies
"the one doing the blocking." Meaning lives in names, and **names are not semantics.**

So you have to say it out loud, in code. That's what `primaryjoin` / `secondaryjoin` are for
(§9), and this is the only place in the whole schema where you need them.

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

**1. Short answer: nothing.** Not a column, not a constraint, not a table.

The clearest way to see it is to imagine deleting each one:

| you delete | what happens to the database | what happens to your Python |
|---|---|---|
| every `relationship()` | **nothing — schema is identical** | you must hand-write every JOIN |
| a `ForeignKey` | the column loses its constraint; bad data can get in | mostly still works, until it doesn't |

`ForeignKey` is a rule the **database** enforces, even at 3am with no Python running.
`relationship()` is a convenience that exists only while your program does — it's the reason
you can type `issue.project` instead of writing the SELECT yourself.

They are not alternatives. You need both, and they solve different problems.

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

**1. Short answer:** `secondary=` throws the junction row away, so there's nothing left to put
`role` on.

Trace what you actually receive:

```
issue.assignments[0]  →  an IssueAssignment object   ← the junction row itself.
                                                        role has a home. ✅

issue.labels[0]       →  a Label object              ← the junction row was used
                                                        to GET here, then discarded.
                                                        Where would role go? ✗
```

And it can't go on the `User` either, because **`role` isn't a fact about the user.** Bob is
not "a reviewer" in general — he's a reviewer *on issue 1* and an owner *on issue 3*. The fact
belongs to the pairing. So the pairing has to become an object you can hold. That's the
association object.

**2. Short answer:** one extra hop, every single time, forever.

```
with secondary=          issue.users              ← doesn't exist. There is no shortcut.
with association object  issue.assignments[0].user
                         └──── hop 1 ────┘└hop 2┘
```

That second hop is the price. You pay it on every traversal in exchange for having somewhere
to keep `role`. It's a real trade, not a free upgrade.

**3. Short answer:** both are exactly the same type — `sqlalchemy.sql.schema.Table`.

```
type(Label.__table__)               -> sqlalchemy.sql.schema.Table
type(issue_labels)                  -> sqlalchemy.sql.schema.Table   ← identical
Label.__mapper__                    -> mapped class Label->labels
hasattr(issue_labels, "__mapper__") -> False                         ← the only difference
```

This is the sentence to remember: **a mapped class is a `Table` plus a mapper.** Writing
`class Label(Base)` doesn't create some different species of thing — it builds the same
`Table` and clips a mapper onto it. The mapper is the part that turns rows into objects.

So "class or bare `Table`?" is really "do I want objects for these rows?" If no, skip the
mapper and stop at the `Table`.

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

**1. Short answer:** only `issue_labels`. One INSERT, and nothing else is touched.

```sql
INSERT INTO issue_labels (issue_id, label_id) VALUES (1, 1)
```

Neither `issues` nor `labels` changes — **no column on either row is modified.** That's the
structural difference from a one-to-many:

| | what changes |
|---|---|
| `issue.project = apollo` (§2) | an existing `issues` row gets `project_id = 1` — an **UPDATE** to a column |
| `issue1.labels.append(bug)` (§8) | a brand-new row appears in the junction — an **INSERT**, no column touched |

Adding a label doesn't alter the issue or the label at all. It only adds a fact *between*
them.

**2. Short answer:** from `backref="issues"` in `Issue.labels`.

```python
labels = relationship("Label", secondary=issue_labels, backref="issues")
                                                       └──────┬───────┘
                                    this one word creates Label.issues,
                                    even though Label declares nothing.
```

`backref` is **one declaration that builds two attributes** — the one you wrote, and the
reverse one on the other class. That's §10, and it's also why `Label` looks suspiciously empty
when you read `models.py`.

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

**1. Short answer:** they're the two legs of one trip.

```
   ME  ──── primaryjoin ────►  junction table  ──── secondaryjoin ────►  THEM
```

- **`primaryjoin`** answers *"which junction rows are mine?"*
- **`secondaryjoin`** answers *"which column of those rows is the answer I want?"*

Every `secondary=` relationship makes this two-leg trip. For `issue.labels` you never wrote
them because SQLAlchemy could guess (§5). For `issue_blocks` it can't guess, so you write them.

**2. Short answer:** `[7, 9]` · `[]` · `[7]` · `[3]` · `[]`

Work it by hand against the three rows — cover the answers and do it yourself first:

```
issue_blocks:   (3,7)  (3,9)  (9,7)
                 ▲ ▲
        blocker──┘ └──blocked
```

| question | how to read it | rows that match | answer |
|---|---|---|---|
| `issue3.blocks` | find rows where **blocker** = 3, take **blocked** | (3,**7**) (3,**9**) | `[7, 9]` |
| `issue3.blocked_by` | rows where **blocked** = 3, take **blocker** | none | `[]` |
| `issue9.blocks` | rows where **blocker** = 9, take **blocked** | (9,**7**) | `[7]` |
| `issue9.blocked_by` | rows where **blocked** = 9, take **blocker** | (**3**,9) | `[3]` |
| `issue7.blocks` | rows where **blocker** = 7, take **blocked** | none | `[]` |

Notice the pattern: `blocks` and `blocked_by` **read the same three rows in opposite
directions.** Which column you filter on, and which you return, simply trade places.

**3. Short answer:** issue 9 is the only one that appears on **both** sides, so it's the only
one that can prove the swap actually happened.

Look at what each issue returns in both directions:

| | `.blocks` | `.blocked_by` | proves anything? |
|---|---|---|---|
| issue 3 | `[7, 9]` | `[]` | weak — one side is empty |
| issue 7 | `[]` | `[3, 9]` | weak — one side is empty |
| **issue 9** | **`[7]`** | **`[3]`** | **strong — different, non-empty, both ways** |

Here's the trap. Suppose `backref` were broken and `blocked_by` just re-ran `blocks`. Issue 3
would still return `[]` for `blocked_by`, and you'd see nothing wrong. **An empty list is what
both a correct answer and a broken one look like.**

Issue 9 returns `[7]` one way and `[3]` the other. Two different non-empty answers from the
same three rows — a broken implementation cannot fake that. This is why the seed data was
deliberately built asymmetric.

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

**1. Short answer:** because `Project` created it, from a line inside a different class.

```python
class Project(Base):
    issues = relationship("Issue", backref="project")
                                   └───────┬───────┘
                                   creates Issue.project

class Issue(Base):
    project_id = Column(...)   # ← this is all you see here.
                               #   .project is nowhere in this class body.
```

This is exactly the readability cost §10 warns about: **you cannot learn a class's full
interface by reading that class.** An attribute can be installed on it by a line you never
scrolled to. It's the reason 2.0 prefers `back_populates`.

**2. Short answer:** it raises `ArgumentError` at mapper-configuration time.

```
ArgumentError: Error creating backref 'author' on relationship 'User.comments':
property of that name exists on mapper 'mapped class Comment->comments'
```

In plain words: *"I went to create that attribute for you, found one already sitting there,
and I refuse to silently overwrite it."*

Note **when** this fires — not at import, but the first time the mappers configure (§12). That
delay is precisely why `check.py` exists.

**3. Short answer:** because the two attributes land on **different classes**.

```python
class IssueAssignment(Base):
    issue = relationship("Issue", backref="assignments")  → creates Issue.assignments
    user  = relationship("User",  backref="assignments")  → creates User.assignments
```

Same word, two homes. `Issue.assignments` and `User.assignments` are unrelated attributes on
unrelated classes.

**The rule:** *"is this name taken?"* is a question about **one class**, never about the file.
Question 2's crash was two declarations fighting over the same attribute on the *same* class —
a real collision. This is two classes holding one attribute each — no collision at all.

**4. Short answer:** `back_populates` makes you name both sides explicitly, so nothing appears
by magic.

```python
# 1.4 style — one line, one invisible attribute
class Project(Base):
    issues = relationship("Issue", backref="project")

# 2.0 style — two lines, each pointing at the other, both visible
class Project(Base):
    issues  = relationship("Issue",   back_populates="project")
class Issue(Base):
    project = relationship("Project", back_populates="issues")
```

More typing. In exchange, reading `Issue` tells you the truth about `Issue`.

**But do not change this repo.** The `backref` usage here is deliberate — it's the 1.4 idiom
this project exists to migrate, and a future `BREAKAGES.md` entry. Migrating it early destroys
the before/after you're building.

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

**1. Short answer:** because when `User` is being defined, the `Comment` class doesn't exist
yet.

Python reads a file top to bottom. Watch the clock:

```python
class User(Base):
    comments = relationship(Comment)   # ← Python runs this line NOW.
                                       #   Comment is defined 40 lines below.
                                       #   → NameError: name 'Comment' is not defined

class Comment(Base):                   # ← too late.
    ...
```

A quoted `"Comment"` sidesteps this because **a string is just text.** Python stores it and
resolves nothing. Later, when the mappers configure (§12), every class exists and `Base` holds
a name→class registry — SQLAlchemy looks `"Comment"` up then, and wires it.

> **A quoted name is a promise to resolve later. A bare name is a demand to resolve now.**

**The consequence to remember:** a typo in the string is not caught at import. `"Commnet"`
imports perfectly happily and blows up at mapper configuration. That's §12, and it's why
importing cleanly proves so little.

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

**1. Short answer:** it proves the mappers can be **built**, not that they say what you meant.

Two very different questions:

| question | does `check.py` answer it? |
|---|---|
| Can SQLAlchemy assemble these relationships without erroring? | ✅ yes |
| Do these relationships express the thing I intended? | ❌ **no** |

This isn't hypothetical. `check.py` has printed `mappers configured OK` while `issue_labels`
was wired to nothing at all — a completely broken schema, green light. The wiring was
*buildable*; it was just wrong.

> **Green means "the thing I ran didn't fail." It never means "correct."** A passing check
> says nothing whatsoever about the paths it didn't exercise.

That's why `explore.py` exists alongside `check.py`: it actually *inserts rows and reads them
back*, so a relationship that's wired to nothing has somewhere to visibly fail.

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

**1. Short answer: no.** This schema uses `primaryjoin`/`secondaryjoin`. `remote_side` solves a
different shape entirely.

Both shapes are "a table related to itself" — that's why they get confused. The difference is
**where the link lives**:

```
remote_side  (NOT this project)         primaryjoin/secondaryjoin  (this project)
────────────────────────────────        ──────────────────────────────────────────
employees                               issues        issue_blocks
| id | name  | boss_id |                | id |        | blocker_id | blocked_id |
| 1  | Alice |  NULL   |                | 3  |        |     3      |     7      |
| 2  | Bob   |    1    |                | 7  |
        └── FK to itself, ON the row              └── a SEPARATE junction table

ONE foreign key, NO junction.           TWO foreign keys, IN a junction.
Each employee has ONE boss.             Each issue blocks MANY, is blocked by MANY.
→ self-referential ONE-to-many          → self-referential MANY-to-many
```

Both are ambiguous, but about different things:

| | the ambiguity | the fix |
|---|---|---|
| adjacency list | in this self-join, which side is the boss? | `remote_side=[id]` |
| junction (yours) | which junction column means "me"? | `primaryjoin`/`secondaryjoin` |

**When you'd actually need `remote_side` here:** if you added "issue → sub-issues" — a
`parent_issue_id` column on `issues`. That's one FK pointing at its own table, no junction, so
it's the adjacency-list shape. The blocking graph isn't that, and never was.

*(Historical note: the runbook originally claimed `blocks` used `remote_side`. It doesn't;
corrected in `cbc94e1`.)*

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

**First, the picture that makes the rest of this section easy.** Forget SQLAlchemy for a
moment:

> The database is a **filing cabinet in another room.** You can't work in there. So you walk
> over, photocopy some rows, and bring the copies back to **your desk**. You scribble on the
> copies. Later you walk back and file the changes.
>
> - the filing cabinet = **the database**
> - your desk = **the session**
> - the photocopies on it = **your Python objects** (`issue`, `apollo`, `alice`)

Every confusing thing in §14 and §15 is a question about the **desk**, not the cabinet. Where
is this photocopy? Is it still trustworthy? Is the desk even there any more?

**The five states an object can be in.** Nearly every confusing SQLAlchemy error is really
"this object was not in the state you assumed":

| state | in desk terms |
|---|---|
| **transient** | a note you wrote by hand — not on the desk, not in the cabinet |
| **pending** | you put it on the desk; still nothing filed |
| **persistent** | filed *and* on your desk |
| **detached** | the desk was taken away; you're holding a loose photocopy |

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

**Note the shape of that middle box. "Expired" is *not* a fifth state** — it's a rubber stamp
on the photocopy reading *STALE, re-copy before trusting.* The object hasn't moved.
`inspect(obj)` says `persistent` both before and after `commit()`; only
`inspect(obj).expired` changes.

This matters because "expired" and "detached" sound alike and behave nothing alike:

| | expired | detached |
|---|---|---|
| the desk | **still there** | **gone** |
| reading a missing value | silently re-queries, you get the value | **raises `DetachedInstanceError`** |
| do you notice? | only in the query log | immediately — it crashes |

Expired can heal itself, because there's still a session to fetch with. Detached can't —
there's no desk to walk back from.

Traced with `inspect()`, one line per moment — measured, not sketched:

| moment | state | `.expired` | `issue.id` | reading `issue.labels` |
|---|---|---|---|---|
| `Issue(...)` | `transient` | `False` | `None` | `[]` — empty list, no query |
| `issue.project = p` | `pending` | `False` | `None` | `[]` |
| `session.flush()` | `persistent` | `False` | `1` | SELECT fires |
| `session.commit()` | `persistent` | **`True`** | re-SELECTs | SELECT fires |
| `session.close()` | `detached` | `False` | `1` (already loaded) | **raises** |

`.expired` reads `False` in four of the five rows, but it only *means* anything in the
persistent ones — a transient object has no row to be stale against, and a detached one has no
session to refresh from.

```
# runnable   →   uv run python -m experiments.sqlalchemy_1_4_vs_2_0.states
constructed            transient   expired=False  cached=['status', 'title']
issue.project = p      pending     expired=False  cached=['project', 'status', 'title']
                       issue.id is None — no INSERT has run yet
session.flush()        persistent  expired=False  cached=['id', 'project', 'project_id', ...]
                       issue.id is 1 — the database assigned it
session.commit()       persistent  expired=True   cached=[]
                       cached is empty — every loaded value was discarded

session.close()        detached    expired=False  cached=['created_at', 'description', ...]
    issue.title  -> 'login button broken'   (was loaded before the close)
    issue.labels -> DetachedInstanceError
```

**`cached` is the payoff column.** It's `inspect(obj).dict` — the values actually held on the
Python object. Watch it go empty at `commit()`: *that* is what expiry physically is. Not a
move, not a flag with mystical meaning — the cached values are discarded, so the next read has
nothing to return and must go back to the database.

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

**1. Short answer:** it puts the object on the desk. That's all.

| `add()` does | `add()` does **not** do |
|---|---|
| move the object from transient → **pending** | emit any SQL |
| enroll it so the next flush will insert it | assign a primary key (`obj.id` stays `None`) |
| | touch the database in any way |

The database has no idea this object exists yet. Nothing reaches it until `flush()` — or a
`commit()`, which flushes for you (see #2).

**2.** They are not two parallel options — `flush()` is a **subset** of `commit()`.

(a) `commit()` **flushes for you.** Measured: `session.add(p); session.commit()` with no
`flush()` call anywhere still inserts the row. You call `flush()` explicitly only when you
need the database-assigned primary key *before* you are ready to end the transaction.

(b) `flush()` leaves the transaction **open** — the INSERT has been sent, but a `rollback()`
still erases it. `commit()` ends the transaction; a new one begins on next use.

(c) `commit()` expires every persistent instance in the session (§15) — **but that is
`expire_on_commit`, a `Session` flag that merely defaults to `True`, not something intrinsic
to `commit()`.** Measured, same commit both times:

```
# runnable   →   uv run python -m experiments.sqlalchemy_1_4_vs_2_0.states     (§6)
(a) committed without ever calling flush() -> rows: 1
(b) after flush: rows visible=1, transaction open=True -> after rollback: rows=0
(c) expire_on_commit=True  -> expired=True  cached=[]              queries reading p.name: 1
    expire_on_commit=False -> expired=False cached=['id', 'name']  queries reading p.name: 0
```

**3. Short answer:** yes, it gets inserted. The mechanism is the **`save-update` cascade**,
which is on by default.

The rule: **attach an object to something that's already in the session, and it joins the
session too.**

```
session.add(apollo)              → apollo is on the desk
apollo.issues.append(issue)      → issue is attached to apollo
                                 → so issue is dragged onto the desk as well
                                 → flush inserts BOTH
```

It works from either direction, too. `issue.project = apollo` does the same thing, because the
`backref` (§10) puts `issue` into `apollo.issues` in memory first — and then the cascade sees
it.

This is why `explore.py` calls `session.add()` on only one of its nine issues. The other eight
arrive by attachment.

**4. Short answer:** nothing is broken. Each table counts from 1 on its own.

```
projects: id 1 = apollo        users: id 1 = alice
                                      id 2 = bob
```

`projects.id` and `users.id` are separate autoincrement counters in separate tables. They
collide constantly and it means nothing — `apollo.id == alice.id` is comparing a project
number to a user number, which is not a meaningful question.

Ids are only unique **within one table.** That's exactly why a foreign key must name its
target (`ForeignKey("projects.id")`) — "id 1" on its own doesn't identify anything.

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
# runnable   →   uv run python -m experiments.sqlalchemy_1_4_vs_2_0.states
issues in this database: 9

Scope A — starting from an expired project object:
  apollo.name + apollo.issues + 9x .labels    11 queries   (1 + 1 + 9)

Scope B — starting from a query, no project read:
  lazy (default)                              10 queries   (1 + 9)
  selectinload                                 2 queries
  joinedload                                   1 queries
```

**Two scopes, differing by exactly one query.** The timeline above starts at a `commit()`, so
it pays an extra SELECT to re-read `apollo.name`; the loading-strategy comparison starts from
a query and never touches the project. That is the whole difference between **11** and **10**
— neither is a typo. The N+1 itself is the **9** in both, one per row in the loop.

`selectinload` is the better default for collections precisely because it doesn't multiply
rows; `joinedload` earns its keep on many-to-one (`issue.project`), where there is exactly one
row on the far side and no duplication to pay for.

> **Write the number down.** 11 queries for 9 issues (Scope A) is the baseline. Step 5 asks for the same
> count at ~200 rows, and the before/after is the story you tell an interviewer — "I found a
> 202-query page and made it 2" is a sentence with evidence behind it.

**Drill.**

1. What is `expire_on_commit`, and what is the argument for leaving it on?
2. Walk the query count: commit, read `apollo.name`, read `apollo.issues`, then loop all 9 issues reading `issue.labels`. Total?
3. Which part is the N+1, and what are the two standard fixes?

<details>
<summary>Answers</summary>

**1. Short answer:** it's a `Session` flag (default `True`) that throws away every cached value
at commit, so the next read re-fetches from the database.

Physically, "expiring" means **emptying the object's attribute cache**:

```
before commit:  cached = ['id', 'name', 'created_at']
after  commit:  cached = []          ← the values are gone
next read:      → SELECT ... WHERE id = 1
```

**The argument for leaving it on: correctness beats speed here.**

Your commit ends your transaction. The moment it does, someone else's transaction may change
that row. The value on your desk was true *inside* your transaction; outside it, it's just an
old photocopy. SQLAlchemy would rather cost you a query than hand you a number that quietly
went stale.

Turn it off (`sessionmaker(expire_on_commit=False)`) and you keep the cached values and emit
zero queries — but you've accepted that they might be wrong. That's a real trade with real
uses; just make it deliberately.

**2. Short answer: 11.**

| step | queries | why |
|---|---|---|
| `session.commit()` | 0 | commit itself doesn't read anything |
| `apollo.name` | **1** | expired by the commit → re-SELECT the project row |
| `apollo.issues` | **1** | relationship never loaded → SELECT the 9 issues |
| `issue.labels` × 9 | **9** | one SELECT per issue, every time round the loop |
| | **11** | |

The trap in this question is the first line. It's tempting to answer 10 and forget that
`apollo.name` — a plain string that was in memory a microsecond ago — costs a query too.

**3. Short answer:** the N+1 is the **9**. The two fixes are `selectinload` and `joinedload`.

Split the number apart:

```
   1     +     9
   ▲           ▲
   │           └── the "+N": one query PER ROW, inside the loop.  ← the problem
   └── the "1": fetch the collection.  Unavoidable, and fine.
```

The 1 is honest work. The 9 is the bug — and it scales with your data, which is why it's
invisible in dev and fatal in production. At 200 issues it's 201 queries; at 200,000 it's
unusable.

Both fixes work by telling SQLAlchemy the children are wanted **upfront**, so it never has to
go back per row. Here is the same loop under all three, with the real SQL:

```
# runnable   →   uv run python -m experiments.sqlalchemy_1_4_vs_2_0.states     (§7)

--- lazy (default): 10 statement(s), 9 Issue objects ---
  1. SELECT ... FROM issues                          ← get the issues
  2. SELECT ... FROM labels, issue_labels WHERE ? = issue_labels.issue_id
     params: (1,)                                    ← "labels for issue 1?"
  3. ... params: (2,)                                ← "labels for issue 2?"
  4. ... params: (3,)                                ← and again, and again
     ...                                                one round trip per issue
  10. ... params: (9,)

--- selectinload: 2 statement(s), 9 Issue objects ---
  1. SELECT ... FROM issues                          ← get the issues
  2. SELECT ... FROM issues AS issues_1 JOIN issue_labels ... JOIN labels
     params: (1, 2, 3, 4, 5, 6, 7, 8, 9)             ← ALL nine ids in ONE query

--- joinedload: 1 statement(s), 9 Issue objects ---
  1. SELECT ... FROM issues LEFT OUTER JOIN (issue_labels JOIN labels ...)
                                                     ← issues and labels together
```

**Now the difference is visible.** Look at the `params` line:

- **lazy** asks nine separate questions, one id at a time: `(1,)` `(2,)` `(3,)` …
- **`selectinload`** asks one question containing all nine ids: `(1,2,3,4,5,6,7,8,9)`. That's
  the `IN (...)` — same information, one round trip instead of nine.
- **`joinedload`** doesn't ask a second question at all; it glues labels onto the first query
  with a JOIN.

**So why isn't `joinedload` always the winner?** Because a JOIN *multiplies rows*. An issue
with two labels comes back twice:

```
# runnable   →   the same states.py §7
its JOIN returns 11 raw rows to describe 9 issues:
    issue 1  label=bug       <-- appears 2x
    issue 1  label=urgent    <-- appears 2x
    issue 2  label=ui
    issue 3  label=bug       <-- appears 2x
    issue 3  label=ui        <-- appears 2x
    issue 4  label=None
    ...
11 rows for 9 issues = 2 duplicated rows, caused by the
2 issues that carry more than one label: [1, 3]
```

**Why exactly issues 1 and 3?** Because a JOIN emits **one row per match**, and those are the
only two issues carrying more than one label — `(1,1) (1,2)` and `(3,1) (3,3)` in the seed. One
label → one row. Two labels → two rows, and the issue's columns are copied into both. Issues
4, 5, 6, 8, 9 have no labels at all and still appear once each, with `label=None`, because it's
a **LEFT** join — that's what stops a label-less issue from vanishing.

**11 rows to describe 9 issues.** SQLAlchemy quietly folds them back into 9 objects, so you
never notice in Python — but the database still built and shipped every duplicate, and each
duplicate carries *all six issue columns* again (title, description, status, created_at…).

At two labels per issue, that's cheap. At **20** labels per issue it's 180 rows, each repeating
the full issue row. `selectinload` never does this: its second query returns exactly one row
per label, no repetition.

| fix | queries | rows over the wire | reach for it when |
|---|---|---|---|
| `selectinload` | 2 | one per child, no repeats | **collections** (`.labels`, `.issues`) — the default choice |
| `joinedload` | 1 | parent repeated per child | **many-to-one** (`.project`) — one row on the far side, so nothing repeats |

**The rule in one line:** `joinedload` trades bandwidth for a round trip. That's a good trade
when the far side is one row (many-to-one) and a bad one when it's a collection.

</details>

---

## Part 4 — Looking ahead to 2.0

Parts 1–3 are about SQLAlchemy as it is. This part is about **why it changed**, and how to
tell a real breakage from a style preference — the distinction the whole project rests on.

**A note on how this part ends.** The four prediction questions at the bottom stay unanswered
on purpose. Everything above them is here so those predictions are *informed* rather than
guesses; the answers themselves you produce by running the upgrade. That exercise is the
highest-value hour in Phase 0 and reading the answer destroys it.

### §16 — Why 2.0 exists: one way to do things, instead of two

SQLAlchemy 1.x grew two parallel APIs for the same job:

```
# illustration — two ways to run one query in 1.x

  CORE                                    ORM
  ────                                    ───
  engine.execute("SELECT * FROM issues")  session.query(Issue).all()
        │                                        │
        │  returns rows                          │  returns objects
        │  connection handled invisibly          │  connection from the session
        │  transaction boundary unclear          │  transaction from the session
```

Two APIs meant two mental models, two sets of rules, and constant questions of the form *"is
this a Core thing or an ORM thing?"* Worse, `engine.execute()` did **connectionless
execution** — it quietly checked out a connection, ran the statement, and returned it. Handy,
and it made "when did my transaction begin, and when will it end?" genuinely hard to answer.

**2.0's central move is unification.** One way to build a statement (`select()`), one way to
run it (`.execute()`), whether or not the ORM is involved. Connections and transactions become
explicit.

```python
# illustration
# 1.x style
session.query(Issue).filter(Issue.status == "open").all()

# 2.0 style
session.execute(select(Issue).where(Issue.status == "open")).scalars().all()
```

**But look at what each actually sends** — this is the measurement that tells you whether
you're facing a rewrite or a rename:

```
# runnable   →   uv run python -m experiments.sqlalchemy_1_4_vs_2_0.migration     (§1)
1.x  SELECT issues.id AS issues_id, issues.title AS issues_title, ... FROM issues WHERE issues.status = ?
2.0  SELECT issues.id,              issues.title,                 ... FROM issues WHERE issues.status = ?

     identical from FROM onward:        True
     identical from WHERE onward:       True
     identical including column labels: False
```

**Same tables, same WHERE, same parameters.** The only difference is that `Query` adds `AS
issues_id` column labels and `select()` doesn't. The database is doing identical work.

That is the single most useful thing to know before you migrate: **`session.query()` → `select()`
is a change in how you write, not in what runs.** Which is why it emits no warning at all
(§17), and why calling it a "breakage" would be wrong.

> **Unification is the theme. Most of the 2.0 diff is one API absorbing the other, not
> behaviour changing underneath you.**

**Drill.**

1. Name the two things 1.x had two of, that 2.0 has one of.
2. `session.query(Issue)` and `select(Issue)` produce near-identical SQL. What follows from that about how urgent this migration is?

<details>
<summary>Answers</summary>

**1. Short answer:** two ways to **build** a statement, and two ways to **run** one.

| | 1.x | 2.0 |
|---|---|---|
| build | `session.query(Issue)` *or* a Core `select()` | `select(Issue)` — always |
| run | `engine.execute(...)` *or* `.all()` on a Query | `.execute(...)` — always |

Plus a third, quieter unification: connection handling. `engine.execute()` grabbed and released
a connection invisibly; 2.0 makes you write `with engine.connect() as conn:` so the boundary is
on the page.

**2. Short answer:** it is not urgent, and it is not risky. It's a rename, not a rewrite.

The SQL is the same, so no query plan changes, no performance changes, no behaviour changes.
Nothing silently returns different rows. That's very different from a migration that alters
what the database does.

The practical consequence: **you can migrate this incrementally, file by file, and nothing
half-migrated is broken.** Contrast with `engine.execute("...")`, which genuinely stops
working — that one you must fix before 2.0 will run at all.

Knowing the difference is the whole skill. Treating a style change as an emergency wastes a
week; treating a real removal as a style change breaks production.

</details>

### §17 — Reading the warnings: four classes, only one is an emergency

SQLAlchemy 1.4 will tell you what 2.0 thinks of your code, *before* you upgrade:

```bash
SQLALCHEMY_WARN_20=1 python -W always::DeprecationWarning -m your.module
```

That flag turns on the 2.0 deprecation warnings. Run it on this project's `app.py` and you get
four distinct messages — and they are **not all the same severity**:

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

**The class name is the whole message.** Learn to read it and you can triage a codebase in
minutes:

| warning class | what it promises | urgency |
|---|---|---|
| `RemovedIn20Warning` | **this stops working in 2.0** | fix before upgrading — real breakage |
| `MovedIn20Warning` | same thing, new import path | one-line fix, do it any time |
| `LegacyAPIWarning` | still works in 2.0, but is no longer the way | fix at leisure |
| *(no warning at all)* | fully supported in 2.0 | not a migration item |

**The fourth row is the one people miss.** `session.query(Model)` — the most obviously
"1.4-looking" thing in this codebase — emits **nothing**, even under `WARN_20`, because 1.x
`Query` is still supported in 2.0. It looks the most legacy and is the least broken.

> **"Looks old" is not a measurement. Run the flag.**

This project's own Step 4 nearly got this wrong in both directions: two of the five suspicious
patterns turned out not to be version issues at all, and the one that reads most innocently
(`engine.execute("SELECT ...")`) turned out to emit *two* `RemovedIn20Warning`s from a single
line — one for the connectionless execution, one for the bare string.

**Drill.**

1. `RemovedIn20Warning` vs `LegacyAPIWarning` — what does each promise about 2.0?
2. `session.query(Model)` looks like the most 1.4-ish thing in the codebase and emits no warning at all. What does that tell you?
3. One line produced *two* `RemovedIn20Warning`s. Why would a single call be two separate problems?

<details>
<summary>Answers</summary>

**1. Short answer:** `RemovedIn20Warning` = *it will stop working.* `LegacyAPIWarning` = *it
will keep working, but it's no longer the recommended way.*

One is a deadline; the other is advice. Only the first belongs in `BREAKAGES.md` — that file
is for things that worked in 1.4 and **stopped working** in 2.0. Filling it with style
preferences would seed the Phase 2 corpus with questions no upgrading developer actually asks.

**2. Short answer:** that appearance and compatibility are unrelated, and only one of them is
measurable.

`session.query()` is 1.x *style* but not 1.x-*only*. It is fully supported in 2.0, so there is
no warning to emit. Had you triaged by eye you'd have flagged it as a breakage — and been
wrong twice over: wrong that it breaks, and wrong to spend migration time on it before fixing
`engine.execute()`, which actually does break.

**3. Short answer:** because `engine.execute("SELECT ...")` does **two** deprecated things at
once.

```python
engine.execute("SELECT count(*) FROM issues")
#      ▲        ▲
#      │        └── problem 2: a bare string instead of text(...)
#      └── problem 1: connectionless execution — no explicit connection
```

Each has its own 2.0 replacement, so each gets its own warning:

```python
# the 2.0 form fixes both
with engine.connect() as conn:                     # ← explicit connection
    conn.execute(text("SELECT count(*) FROM issues"))   # ← explicit text()
```

Worth internalising: **warning count ≠ line count.** One call site can hold several
independent migration problems, and a naive "how many lines must I change" estimate misses
them.

</details>

### §18 — `future=True`: run 2.0's rules without installing 2.0

The most useful migration fact in this document, and it needs no upgrade at all.

SQLAlchemy **1.4 ships 2.0's behaviour behind a flag.** Pass `future=True` and that engine or
session enforces 2.0 rules immediately:

```python
# illustration
engine  = create_engine("sqlite://", future=True)
Session = sessionmaker(bind=engine, future=True)
```

Measured on 1.4.52 — the same call, with and without the flag:

```
# runnable   →   uv run python -m experiments.sqlalchemy_1_4_vs_2_0.migration     (§2)
normal engine : sqlalchemy.engine.base.Engine
future engine : sqlalchemy.future.engine.Engine

engine.execute("SELECT 1") on normal 1.4 engine   -> worked
engine.execute("SELECT 1") on future=True engine  -> NotImplementedError:
                                 This method is not implemented for SQLAlchemy 2.0.
```

**You can experience the 2.0 breakage today, on the version you already have.** No upgrade, no
reinstall, no risk to the rest of the project.

Which makes the real migration strategy incremental rather than a big-bang rewrite:

```
1. SQLALCHEMY_WARN_20=1     →  get the full list of what 2.0 objects to      (§17)
2. fix every RemovedIn20Warning  →  the things that actually break
3. flip future=True         →  prove the fixes hold under 2.0 rules,
                               while still running 1.4
4. only then bump to 2.0    →  by which point nothing should be left to find
```

Step 3 is the one people skip, and it's the one that converts "I hope this works" into "I
watched it work." You get the errors on your own schedule instead of during an upgrade with
everything moving at once.

> **You do not have to choose between "still on 1.4" and "already on 2.0." `future=True` is
> the bridge, and it makes the upgrade boring — which is what you want an upgrade to be.**

**Drill.**

1. What does `future=True` do, and why would you use it *before* upgrading?
2. Order these correctly: bump to 2.0 · fix `RemovedIn20Warning`s · flip `future=True` · run `SQLALCHEMY_WARN_20=1`. Justify the position of the last two.

<details>
<summary>Answers</summary>

**1. Short answer:** it makes a 1.4 engine or session enforce 2.0's rules, so you can hit 2.0's
errors while still running 1.4.

Measured: `engine.execute("SELECT 1")` works on a normal 1.4 engine and raises
`NotImplementedError: This method is not implemented for SQLAlchemy 2.0.` on a `future=True`
one.

**Why before upgrading:** it separates *finding* problems from *being broken by* them. An
upgrade changes every behaviour at once, so when something fails you're debugging against a
moving target. `future=True` lets you change one thing, watch it break, fix it, and repeat —
with a working 1.4 environment underneath the whole time. It also reverses instantly: delete
the flag.

**2. Short answer:**

```
1. run SQLALCHEMY_WARN_20=1      ← inventory first: you can't plan what you haven't listed
2. fix the RemovedIn20Warnings   ← the only tier that actually breaks
3. flip future=True              ← verification: prove the fixes hold under 2.0 rules
4. bump to 2.0                   ← should be uneventful by now
```

**Why the warning flag is first:** it's read-only. It changes nothing and costs one command,
so there is no reason to guess at scope when you can measure it.

**Why `future=True` sits before the version bump:** it's the only step that gives you 2.0's
errors while you still have a working 1.4 environment to fall back to. Skip it and step 4
becomes the moment you discover what you missed — with the old version already uninstalled.

Steps 1 and 3 are both verification, at opposite ends: one tells you what to do, the other
tells you whether you did it.

</details>

### §19 — What 2.0 does *not* fix

Not every problem in a 1.4 codebase is a 1.4 problem. Two of the ugliest things in this
project survive the upgrade completely untouched:

| looks like a version problem | actually is | proof |
|---|---|---|
| the N+1 in `issue_report()` | a **loading-strategy** bug — equally slow in both | §15 |
| `DetachedInstanceError` | a **session-lifecycle** bug — fires identically in 1.4 | §14 |

Both were *measured* under 1.4 in Part 3, before either was blamed on the version. Neither
emits a migration warning, because neither is a migration issue. Upgrade to 2.0 and the N+1
still fires 201 queries; the detached object still raises.

**Why this matters more than it sounds.** `BREAKAGES.md` becomes the Phase 2 golden dataset.
Every entry is a question a real developer asks while upgrading. Put "why is my loop slow?" in
it and you have seeded your retrieval corpus with a question that has nothing to do with
upgrading — and you will then evaluate your system against it and score yourself on the wrong
thing.

> **A breakage is something that worked in 1.4 and stopped working in 2.0. Not "something bad
> I found while migrating."**

Of the five suspicious patterns Step 4 examined, measurement moved **two** out of the breakage
list entirely. Both would have looked perfectly plausible in the corpus.

**Drill.**

1. Give the one-sentence test for whether something belongs in `BREAKAGES.md`.
2. The N+1 and `DetachedInstanceError` both surfaced during migration work. Why does neither qualify?

<details>
<summary>Answers</summary>

**1. Short answer:** *did this work in 1.4 and stop working in 2.0?* Yes → it belongs. Anything
else → it doesn't.

Note what the test excludes: things that are slow in both, things that were always wrong,
things that merely became unfashionable. "I encountered it during the upgrade" is not the test.

**2. Short answer:** both fail identically in 1.4, so the version changed nothing about them.

| | in 1.4 | in 2.0 | version-dependent? |
|---|---|---|---|
| N+1 in a loop | 201 queries | 201 queries | no — a loading-strategy bug |
| `DetachedInstanceError` | raises (§14 traced it) | raises | no — a lifecycle bug |

They're real bugs and worth fixing. They're just not *upgrade* bugs, and the corpus is
specifically about upgrading.

The failure mode to guard against: you spend a week migrating, you meet several problems, and
they all get filed under "2.0 issues" because that's what you were doing at the time.
Measurement is what separates them — which is why Part 3 traced both under 1.4 *before* any
2.0 work started.

</details>

### Predictions — write these down before you run anything

These four stay unanswered on purpose. Put your answers in `LEARNING-LOG.md` **first**, then
run the upgrade and diff your predictions against what actually happened. A prediction you
wrote and got wrong teaches more than an answer you read.

Everything you need to reason about them is in §16–§19. That's the point — these are
predictions, not guesses.

1. `SQLALCHEMY_WARN_20=1` on the current code — which lines do you expect it to flag? List
   them by file and construct **before** running.
2. Which of these breaks in 2.0, and what replaces each: `session.query(Issue)`,
   `Query.get(id)`, `engine.execute("SELECT ...")`, `declarative_base()` imported from
   `sqlalchemy.ext.declarative`? For each, name the **tier** (§17), not just the fix.
3. Predict the `DetachedInstanceError` scenario: what must happen, in what order, for it to
   fire? Does the version matter (§19)?
4. Does `backref` still work in 2.0? Which tier is it, and is "still works" the same as "still
   recommended"?
