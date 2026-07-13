# Learning log

Running notes from Phase 0. Written as we go, so the lessons survive the chat window.

This is **not** `BREAKAGES.md`. See "The boundary" at the bottom — keeping the two apart
matters.

---

## Where you are right now

**Step 2 of 10 — the schema.** (`PRACTICE-APP.md` has the full runbook.)

Done:
- ✅ Step 1 — Python 3.11.15 + SQLAlchemy 1.4.52 pinned, `uv.lock` committed
- 🔄 Step 2 — `models.py`: `User`, `Project`, `Issue`, `Comment`, `Label`, `issue_labels`
  written. **Three things still missing** (below).

### The three things left in step 2

1. **`Comment` has no `body` and no `created_at`.** Right now it's two foreign keys and
   nothing else — a comment with no text in it.
2. **`issue_labels` is defined *below* `class Issue`, and needs to be above it.** When you
   write `secondary=issue_labels`, you're passing the actual Python object, so the name must
   already exist by the time the class body runs. Python reads top to bottom.
3. **`Issue` has no `labels` relationship.** The `issue_labels` table exists but nothing
   references it. Add:
   `labels = relationship("Label", secondary=issue_labels, backref="issues")`

Then still to come in step 2: the **association object** (`IssueAssignment`) and the
**self-referential** `blocked_by` / `blocks`.

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
| 4 | ⬜ `Issue` ↔ `Label` | **many-to-many** | neither table — in `issue_labels` | `issue.labels` (list) and `label.issues` (list) |
| 5 | ⬜ `Issue` ↔ `User` | **many-to-many with data** | in `issue_assignments`, *plus* `role` + `assigned_at` | `issue.assignments` → `IssueAssignment` objects → `.user` |
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
