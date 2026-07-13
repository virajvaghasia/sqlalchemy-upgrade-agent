# Learning log

Running notes from Phase 0. Written as we go, so the lessons survive the chat window.

This is **not** `BREAKAGES.md`. See "The boundary" at the bottom — keeping the two apart
matters.

---

## Where you are right now

**Step 2 of 10 — the schema.** (`PRACTICE-APP.md` has the full runbook.)

- ✅ **Step 1** — Python 3.11.15 + SQLAlchemy 1.4.52 pinned, `uv.lock` committed
- 🔄 **Step 2** — `models.py`
  - ✅ `User`, `Project`, `Issue`, `Comment`, `Label`
  - ✅ `issue_labels` — plain join `Table` (many-to-many, no extra columns)
  - ✅ `IssueAssignment` — association *object* (`role`, `assigned_at`)
  - ⬜ **`issue_blocks` + `Issue.blocks` / `blocked_by` — the self-referential one.** ← you
    are here
  - ⬜ then `create_all()` → a real `.db` file on disk

`uv run python -m experiments.sqlalchemy_1_4_vs_2_0.check` is green. Run it after every
change.

### Next: the self-referential many-to-many

The only relationship SQLAlchemy cannot figure out alone. See **"Self-referential: why it
needs `primaryjoin`"** below for the full derivation. Short version:

1. A junction `Table` — `issue_blocks`, with `blocker_id` and `blocked_id`, **both**
   `ForeignKey("issues.id")`, both `primary_key=True`. Define it **above** `class Issue`.
2. On `Issue`, one relationship: `blocks`, with `secondary=issue_blocks`, an explicit
   `primaryjoin` and `secondaryjoin`, and `backref="blocked_by"`.

**Predict before you run it:** the `backref` produces `blocked_by` by **swapping**
`primaryjoin` and `secondaryjoin`. That swap *is* the "read the same table in the other
direction" idea, done for you. If it didn't swap them, `blocked_by` would be identical to
`blocks` and the whole thing would be pointless.

---

## The relationship map — what connects to what

Keep this open while you write `models.py`. ✅ = built. ⬜ = still to do.

```
                          ┌──────────┐
                          │ projects │
                          └────┬─────┘
                               │ 1
                               │
                               │ many          ┌────────┐
                          ┌────┴─────┐  M:M    │ labels │
              ┌───────────┤  issues  ├─────────┤        │
              │           └──┬────┬──┘ via     └────────┘
              │ 1            │    │    issue_labels
              │              │    │
         many │         self-ref  │ M:M via issue_assignments
              │       blocked_by/ │      (+ role, assigned_at)
       ┌──────┴─────┐   blocks    │
       │  comments  │             │
       └──────┬─────┘        ┌────┴────┐
              │ many         │  users  │
              └──────────────┤         │
                       1     └─────────┘
```

### Every relationship, one line each

| # | Relationship | Kind | Where the FK lives | Gives you |
|---|---|---|---|---|
| 1 | ✅ `Project` ↔ `Issue` | one-to-many | `issues.project_id` | `issue.project` (object) and `project.issues` (list) |
| 2 | ✅ `Issue` ↔ `Comment` | one-to-many | `comments.issue_id` | `issue.comments` (list) and `comment.issue` (object) |
| 3 | ✅ `User` ↔ `Comment` | one-to-many | `comments.user_id` | `user.comments` (list) and `comment.author` (object) |
| 4 | ✅ `Issue` ↔ `Label` | **many-to-many** | neither table — in `issue_labels` | `issue.labels` (list) and `label.issues` (list) |
| 5 | ✅ `Issue` ↔ `User` | **many-to-many with data** | in `issue_assignments`, *plus* `role` + `assigned_at` | `issue.assignments` → `IssueAssignment` objects → `.user` |
| 6 | ⬜ `Issue` ↔ `Issue` | **self-referential M:M** | in `issue_blocks` | `issue.blocked_by` (list) and `issue.blocks` (list) |

### Reading the table

**One-to-many (1, 2, 3).** One project has many issues; each issue belongs to exactly one
project. **The foreign key always lives on the "many" side** — `issues.project_id`, not
`projects.issue_id`. A project can't hold a list of ids in one column, so the child points
at the parent. This is why the FK is on `Issue` but the `relationship()` can be declared on
either class.

**Many-to-many (4).** An issue has many labels; a label is on many issues. **Neither table
can hold the foreign key** — so a third table does. Each row of `issue_labels` is one
(issue, label) pairing and nothing more. You never touch it directly: `secondary=` makes
SQLAlchemy hop through it and hand you `Label` objects.

**Many-to-many *with data* (5) — the association object.** Same shape as (4), except the
pairing carries facts of its own: *this user is the **owner** of this issue, assigned **on
Tuesday***. Those facts belong to the *pairing*, not to the user and not to the issue.
`secondary=` has nowhere to put them. So the join table becomes a real class, and you
traverse it in two hops: `issue.assignments[0].role` and `issue.assignments[0].user`.

**The one-column test:** does the fact that connects A and B have any attributes of its own?
No → association table (4). Yes → association object (5). That's the whole rule, and it's a
drill question.

**Self-referential (6).** Issue #7 is blocked by issue #3. Both sides are `issues` — one
table, related to itself. It's still many-to-many (an issue can block several, and be
blocked by several), so it still needs a join table (`issue_blocks`, with `blocker_id` and
`blocked_id`, both pointing at `issues.id`).

This is the one that fights you, because SQLAlchemy now has an ambiguity it can't resolve
alone: **both foreign keys point at the same table**, so when you ask for `issue.blocks`, it
genuinely cannot tell which column means "me" and which means "them." That's what
`primaryjoin` / `secondaryjoin` are for — you tell it explicitly. (For a self-referential
*one*-to-many, the equivalent knob is `remote_side`.) Don't fight this one blind — ask me to
explain it when you get there.

---

## From SQL to ORM — why every relationship looks the way it does

You know SQL. So don't start from SQLAlchemy. **Start from the tables, and let the ORM fall
out of them.** Every "why" below has a SQL answer underneath it.

### The one law everything derives from

> **A column holds exactly one value.**

That's it. Every relationship pattern in every ORM ever written is a consequence of that one
constraint. Watch.

### One-to-many: why the FK is always on the "many" side

One project has many issues. Each issue has one project.

Try putting the link on `projects`:

| id | name | issue_id |
|---|---|---|
| 1 | Apollo | 4? 7? 12? 88? |

**Broken.** A project has many issues and that column holds one value. You'd need a list in
a cell, and SQL doesn't do that.

Now put it on `issues`:

| id | title | project_id |
|---|---|---|
| 4 | Login fails | 1 |
| 7 | Slow query | 1 |

**Works.** Each issue points at *one* project — one value, one column. Many rows can point
at the same project, and that's what makes it "many."

> **The foreign key lives on the side that has ONE of the other thing.** It's not a
> convention. It's forced.

And "give me the project's issues" is just the query run backwards:
`SELECT * FROM issues WHERE project_id = 1`.

### Many-to-many: why a third table is unavoidable

An issue has many labels. A label is on many issues. **Now *both* sides need a list**, and
neither column can hold one. There is nowhere to put the link.

So you invent a table whose *rows are the links*:

**issue_labels**

| issue_id | label_id |
|---|---|
| 4 | 1 |
| 4 | 2 |
| 7 | 1 |

Each row = one pairing. Issue 4 has labels 1 and 2. Label 1 is on issues 4 and 7. Both
"lists" are now rows, and rows are unlimited.

> **A junction table exists because a column can't hold a list.** Same law, applied twice.

The primary key is the **pair** (`issue_id`, `label_id`) — that's what stops you attaching
the same label to the same issue twice.

### Now the ORM — and the thing to get straight first

**`relationship()` creates nothing in the database.** Not a column, not a constraint, not a
table. It's Python-side only.

The `ForeignKey` is the real thing — it's in the DDL, the database enforces it, it exists
whether or not Python is running.

`relationship()` is a **convenience layer that writes the SELECTs for you.** When you touch
`project.issues`, SQLAlchemy emits `SELECT * FROM issues WHERE project_id = 1` and hands you
objects. That's all it is. You could delete every `relationship()` from `models.py` and the
schema on disk would be **identical** — you'd just have to write the joins yourself.

> **`ForeignKey` = the database's truth. `relationship()` = Python's convenience.**
> You need both, and they're not alternatives.

### Why `Table` for `issue_labels` but `class` for the others

Here's the insight that makes it click:

> **A declarative class IS a `Table` — plus a mapping to a Python class.**

When you write `class Label(Base)`, SQLAlchemy builds a `Table` object under the hood. You
can *see* it: `Label.__table__` is a real `Table`, indistinguishable in kind from
`issue_labels`. The class adds one thing on top: **a mapper, which turns rows into Python
objects.**

So "should this be a `Table` or a class?" is really one question:

> **Do I ever want a Python object for a row of this table?**

For `issue_labels`: **no.** What would you even do with it? A row is `(4, 1)` — pure
linkage, no facts. An `IssueLabel` object would carry no information you don't already have
from the `Issue` and the `Label`. So you skip the mapper and declare only the `Table`.

For `Label`: **yes, obviously.** A row is a real thing with a name, and you want
`label.name`.

**That's the entire rule.** Not style. Not preference. Just: *is there anything worth
putting in an object?*

### What `secondary=` actually does

```python
labels = relationship("Label", secondary=issue_labels, backref="issues")
```

You're telling SQLAlchemy: *"to get from an issue to its labels, **hop through**
`issue_labels`."* It generates:

```sql
SELECT labels.* FROM labels
JOIN issue_labels ON labels.id = issue_labels.label_id
WHERE issue_labels.issue_id = 4
```

Note what comes back: **`Label` objects.** The junction table appears in the SQL and then
**vanishes from the Python.** `issue.labels[0]` is a `Label`. You never see an `IssueLabel`,
because there is no such class — that's the point.

> **`secondary=` means "this table is plumbing, hide it from me."**

### And why `issue_assignments` CANNOT be `secondary=`

Same shape as labels — until you add one column:

**issue_assignments**

| issue_id | user_id | role | assigned_at |
|---|---|---|---|
| 4 | 2 | owner | 2026-07-13 |
| 4 | 5 | reviewer | 2026-07-14 |

Now ask: **where does `role` live?**

It isn't a fact about the user — Alice isn't globally an "owner", she's the owner *of issue
4* and a reviewer *of issue 9*. It isn't a fact about the issue either — issue 4 doesn't
have one role, it has one per person.

> **`role` is a fact about the PAIRING. It belongs to neither end.**

And `secondary=` hands you `User` objects and throws the junction row away. So there is
**physically nowhere for `role` to be.** You'd write `issue.users[0]` and get a `User` —
`role` isn't on a `User`. It's gone.

**So the junction row must become an object.** The moment a link carries a fact, that fact
needs somewhere to live, and "somewhere" is a Python object, and a Python object needs a
class:

```python
class IssueAssignment(Base):
    __tablename__ = "issue_assignments"
    issue_id    = Column(Integer, ForeignKey("issues.id"), primary_key=True)
    user_id     = Column(Integer, ForeignKey("users.id"),  primary_key=True)
    role        = Column(String)          # ← the reason this class exists
    assigned_at = Column(DateTime)
    issue = relationship("Issue", backref="assignments")
    user  = relationship("User",  backref="assignments")
```

**This is the price, and it's the lesson:**

```
issue.labels[0]              →  a Label        ONE hop   (junction hidden)
issue.assignments[0].user    →  a User         TWO hops  (junction is an object)
issue.assignments[0].role    →  "owner"        ← only reachable because of the object
```

You traded a hop for a place to keep `role`. **You cannot have both.**

> **The one-column test:** does the fact that connects A and B have attributes of its own?
> **No** → association *table* (`secondary=`). **Yes** → association *object* (a class).
> That's the whole rule, and it's a drill question.

### Why `backref="assignments"` twice doesn't collide

`IssueAssignment` declares `backref="assignments"` on **both** its relationships — and
unlike the duplicate-backref crash you hit twice, this one is fine.

Why? Because they create attributes on **different classes**:

- `issue = relationship("Issue", backref="assignments")` → creates **`Issue`**`.assignments`
- `user  = relationship("User",  backref="assignments")` → creates **`User`**`.assignments`

Two classes, one attribute each. No conflict. The earlier crash was two declarations fighting
over the *same attribute on the same class*.

**"Is the name taken?" is a question about a class, not about the file.**

### Self-referential: why it needs `primaryjoin`

#### First: `secondary=` is always TWO joins

Go back to labels. The SQL SQLAlchemy generated was never one join — it was two:

```sql
SELECT labels.* FROM labels
JOIN issue_labels ON issue_labels.label_id = labels.id   ← junction → target
WHERE issue_labels.issue_id = 4                          ← me → junction
```

Those two joins have names:

- **`primaryjoin`** — how I get from **me** to the junction table
- **`secondaryjoin`** — how I get from the junction table to the **target**

You never wrote them for labels **because SQLAlchemy could infer them.** It looked at
`issue_labels`, saw one FK pointing at `issues` and one at `labels`, and the assignment was
obvious: the `issues` one is *me*, the `labels` one is *them*.

#### The ambiguity

```
issue_blocks
┌────────────┬────────────┐
│ blocker_id │ blocked_id │
├────────────┼────────────┤
│     3      │     7      │    ← issue 3 blocks issue 7
└────────────┴────────────┘
   FK→issues.id  FK→issues.id
```

**Both foreign keys point at `issues`.** So when you ask for `issue.blocks`, SQLAlchemy sees
two columns that — as far as the *schema* is concerned — are completely interchangeable.
Which one means *me*? Which means *them*?

The database has no idea. **The meaning lives in the column names, and names are not
semantics.** `blocker_id` means something to you; to SQLAlchemy it's just a string.

That's the ambiguity, and it's the only place in this schema where you must speak up.

#### What you tell it

For `Issue.blocks` — *"the issues that I block"*:

- **`primaryjoin`**: my `id` = `issue_blocks.blocker_id` → **I am the blocker**
- **`secondaryjoin`**: `issue_blocks.blocked_id` = the target's `id` → **they are the blocked**

**Swap those two and you get the exact opposite meaning — `blocked_by`.** Same table, same
rows, read in the other direction. That is the entire trick, and it's why this relationship
is conceptually interesting rather than merely fiddly.

#### The syntax: the `.c` accessor

To reference a column of a bare `Table` (not a mapped class), use **`.c`** — for *columns*:

```python
issue_blocks.c.blocker_id     # a Table keeps its columns in .c
Issue.id                      # a mapped class exposes them as attributes
```

**This is the visible seam between Core and ORM.** Mapped classes give you attributes; raw
`Table`s give you `.c`.

And the join conditions are just **SQL expressions written in Python**:

```python
Issue.id == issue_blocks.c.blocker_id
```

That `==` compares nothing. It **builds a WHERE-clause object.** Same machinery as
`session.query(Issue).filter(Issue.status == "open")` — the `==` is overloaded to construct
SQL, not to evaluate a boolean.

#### The backref swap

`backref="blocked_by"` will generate the reverse side by **swapping `primaryjoin` and
`secondaryjoin` for you.**

Which is precisely the "read it in the other direction" idea, automated. **If it didn't
swap them, `blocked_by` would be identical to `blocks`** — and the relationship would be
useless. Predict this before you run it; then check the emitted SQL and confirm.

---

## Concepts, in the order you hit them

### 1. SQLAlchemy configures mappers *lazily*

Importing `models.py` does **not** wire up the relationships. SQLAlchemy defers that work
until something first needs it. So a broken relationship stays completely silent at import
time.

This is why `check.py` exists — `configure_mappers()` forces the wiring to happen now, so
errors surface on demand instead of ambushing you at runtime.

**The bigger lesson: "it imported fine" ≠ "it works".** You hit a version of this three
separate times in one hour:

- the import test that printed `ok` while the schema had a duplicate-backref conflict in it
- my deprecation test that showed "no warning" because I probed the *import* and the warning
  fires on the *call*
- `check` passing while `issue_labels` was wired to nothing at all

**A green result only tells you that the thing you ran didn't fail. It says nothing about
the thing you didn't run.** This instinct is worth more in an interview than any single API
fact.

### 2. `ForeignKey` and `relationship()` are different things

People conflate these constantly. They are not alternatives — you need both.

- **`ForeignKey`** is a *database* constraint. It lives in the SQL, in the actual table.
- **`relationship()`** is a *Python* convenience. It tells the ORM how to hand you objects.

`project_id = Column(Integer, ForeignKey("projects.id"))` creates the column.
`project = relationship("Project")` is what lets you write `issue.project` and get an object
back.

### 3. `backref` declares one side and generates the other

`Issue.project = relationship("Project", backref="issues")` gives you **both**
`issue.project` *and* `project.issues` — from one line.

So you declare it **once, on one side only.** Declaring both sides is what produced:

```
sqlalchemy.exc.ArgumentError: Error creating backref 'project' on relationship
'Project.issues': property of that name exists on mapper 'mapped class Issue->issues'
```

Translation: *"I tried to auto-create `Issue.project` for you, but `Issue` already has one,
and I won't silently clobber it."*

The reverse name doesn't have to match the class name — `User.comments =
relationship("Comment", backref="author")` gives you `comment.author`, which reads better
than `comment.user`.

**2.0 prefers `back_populates`**, which is the opposite style: declared explicitly on *both*
sides, each naming the other. More typing, but no invisible attributes appearing on your
classes because of a line in some other file. **We are deliberately using `backref` because
it's the 1.4-ism — it's a future `BREAKAGES.md` entry.**

### 3b. Why relationships take a **string**: deferred resolution

```python
class Issue(Base):
    comments = relationship("Comment", backref="issue")   # "Comment" — in quotes
```

`Comment` is defined *below* `Issue` in the file. So when Python executes that line, the
name `Comment` **does not exist yet**. Unquoted, it would be an instant `NameError`.

The string dodges that. `"Comment"` is just text — Python happily stores the characters and
resolves nothing.

Later, when `configure_mappers()` runs (i.e. your `check.py`), every class *has* been
defined, and `Base` has quietly been collecting them in a **registry** — a name→class
dictionary. SQLAlchemy walks that registry, looks up `"Comment"`, finds the class, and wires
the relationship.

**Deferred resolution: store a name now, look it up later, once the world is complete.**
`ForeignKey("issues.id")` is the same trick against the *table* registry.

#### This is exactly why `issue_labels` broke and `"Label"` didn't

```python
labels = relationship("Label", secondary=issue_labels, backref="issues")
#                      ^^^^^^^            ^^^^^^^^^^^^
#                      string             bare Python name
#                      → deferred         → evaluated RIGHT NOW
```

`"Label"` is fine below its class. `issue_labels` is not — it's a plain variable reference,
and Python evaluates it on the spot.

Two ways out:

- `secondary=issue_labels` — the object. **Must be defined above the class.** ← do this
- `secondary="issue_labels"` — the string. Deferred, works anywhere in the file.

**The rule: in SQLAlchemy, a quoted name is a promise to resolve later. An unquoted name is
a demand to resolve now.**

### 4. Association *table* vs association *object*

This is the distinction the whole schema was designed to teach, and it's a drill question.

**`issue_labels` — a plain `Table`, not a class.** It holds nothing but two foreign keys.
There's no data on that row worth a Python object, so it doesn't get one. You hand it to
`relationship(..., secondary=issue_labels)` and SQLAlchemy traverses *through* it, handing
you `Label` objects directly. The join table stays invisible.

**`issue_assignments` — a real mapped class.** Because it has columns of its own (`role`,
`assigned_at`), and a bare `Table` has nowhere to put them. `secondary=` can't express it:
there is no way to ask "give me the label objects, and also this extra field that lives on
the join." So it becomes a class with two `relationship()`s, and you traverse it in two
hops.

**One extra column is the entire difference.** Build them back to back so you feel it.

### 5. Deprecation warnings are OFF by default in 1.4

`RemovedIn20Warning` (and its subclass `MovedIn20Warning`) are **silent unless you set
`SQLALCHEMY_WARN_20=1`.** Without it, 1.4 says nothing and you sail on believing your code
is fine.

With it, the old `declarative_base()` import produces:

```
MovedIn20Warning: The ``declarative_base()`` function is now available as
sqlalchemy.orm.declarative_base(). (deprecated since: 1.4)
```

That env var is the mechanism behind step 6 — it turns 1.4 into a migration linter that
points at your own lines.

**Two Python `warnings` gotchas that will bite you:**

- Python **deduplicates** warnings — the same warning from the same line fires *once per
  process* and is silent forever after. `warnings.simplefilter("always")` disables that.
  Otherwise your test prints nothing and you conclude, wrongly, that there's no deprecation.
- Warnings often fire at **call time, not import time.** Probing the wrong place gives you a
  clean bill of health that means nothing.

The version you'll actually use in step 6 promotes them to hard errors, so the traceback
points at your file and line:

```
SQLALCHEMY_WARN_20=1 uv run python -W error::DeprecationWarning <your script>
```

### 6. I was wrong about "removed"

I told you `sqlalchemy.ext.declarative` was *removed* in 2.0. It isn't — it's *moved and
deprecated* (`MovedIn20Warning`). I asserted an API fact without checking it.

**Don't take my API claims on trust. Make the library say it.** You caught that one by
pushing back, and pushing back was correct.

---

## Mistakes made (mine and yours) — and the patterns behind them

Not shameful; they're the point. But **three of these are the same mistake twice**, and the
pattern is worth more than the individual fixes.

### The recurring one: declaring both sides of a `backref`

Hit it on `Project`/`Issue`. Fixed it. Then hit the **identical** thing on `Issue`/`Label`
forty minutes later.

```
Issue.labels  = relationship("Label", secondary=..., backref="issues")   # creates Label.issues
Label.issues  = relationship("Issue", secondary=..., backref="labels")   # creates Issue.labels
                                                                          # → both declared twice
```

**`backref` declares one side and generates the other. So you write it ONCE.** If you find
yourself typing a relationship on the second class, stop — you already have it.

The tell in the error message is always the phrase *"property of that name exists on
mapper"*: SQLAlchemy is saying *"I went to create this attribute for you and found one
already there, and I refuse to silently overwrite it."*

### The other recurring one: using a name before defining it

`issue_labels` was written *below* `class Issue`, which used it. Twice.

Python executes a module **top to bottom**. A class body runs at import time, so any plain
name it references must already exist. `NameError`.

The exception — and it's why `relationship("Issue")` takes a **string** — is that
SQLAlchemy resolves *string* names lazily, after every class is defined. That's the whole
reason for the quotes. `secondary=` accepts a string too (`secondary="issue_labels"`), which
sidesteps ordering entirely. But the plain-object form is what real 1.4 code uses, so: just
put the `Table` above the class.

### Reaching for the 2.0 idiom by reflex

Twice you wrote the modern, correct thing:

- `from sqlalchemy.orm import declarative_base` (2.0) instead of `sqlalchemy.ext.declarative` (1.4)
- `back_populates` (2.0) instead of `backref` (1.4)

Ordinarily that instinct is good. **Here it's the enemy** — code that doesn't break produces
no `BREAKAGES.md` entry, and the deliverable is the breakages. Suppressing this reflex for
two days is genuinely hard, and worth noticing every time it happens.

### Copying the docs' example instead of the design

The first `User` had `name` / `fullname` / `nickname` — straight from the SQLAlchemy
tutorial, not from our schema.

Reading the docs for **syntax** is exactly right. Pasting their **data model** is the
copying reflex, and it's precisely the reflex this whole phase exists to break.

### Smaller ones

- **`Column(String, enum=IssueStatus)`** — `enum=` isn't a `Column` keyword; the type is the
  *first argument*. And `sqlalchemy.types.Enum` (a column type) is a completely different
  thing from Python's `enum.Enum` (a class you subclass) — they just share a name.
- **`body` on `Label`** — a label has a `name` ("bug", "urgent"); the *comment* is the thing
  with text. Field on the wrong class.
- **A trailing `\`** at the end of a relationship line — that's a line-continuation
  character, gluing two statements into one. `SyntaxError`, and it blocks Python from ever
  reaching the real problems below it.

### Mine

- I told you `sqlalchemy.ext.declarative` was **removed** in 2.0. It's **moved and
  deprecated** (`MovedIn20Warning`). I asserted an API fact without checking it.
- I pointed you at the 1.4 docs page for `declarative_base` — which teaches the *new* import
  — and then criticised you for using it. You were right to push back.

**Don't take my API claims on trust. Make the library say it.**

---

## The boundary — what goes in `BREAKAGES.md` and what doesn't

**`BREAKAGES.md` is only for things that worked in 1.4 and stopped working in 2.0.**

Your own bugs — the duplicate backref, the missing import, the misused `Enum` — do **not**
go in it. They're just mistakes, and every programmer makes them.

Why this matters: `BREAKAGES.md` becomes the seed of the Phase 2 golden dataset. Pad it with
your own typos and you poison it with questions no real user would ever ask, and you can no
longer defend it in an interview.

Your own mistakes go **here**, in the learning log. Different file, different purpose.

---

## Breakages found so far (candidates for `BREAKAGES.md`)

1. **`declarative_base()` imported from `sqlalchemy.ext.declarative`** → `MovedIn20Warning`,
   now lives at `sqlalchemy.orm.declarative_base`. *Found by argument + test, not by reading.*
2. **`backref=`** → discouraged in 2.0 in favour of explicit `back_populates` on both sides.
   *(Not yet verified against a real 2.0 run — do that in step 8 before writing it up.)*

Target is ≥10. These get written up properly, with exact error text and a migration-guide
link, in step 7.
