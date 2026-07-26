# Learning log — the timeline

The **chronological** record of Phase 0: what you hit, when, and the mistakes along the way.
It is deliberately *not* a place to explain concepts — those live in `CONCEPTS.md`, one
canonical explanation each, and every entry below links to a section number (`§1`–`§13`)
there.

This split is the fix for why the old log became unreadable: concepts got re-explained every
time you hit them again, three times over in places. Here, a *recurrence* of an idea becomes
a new dated link — never a fresh re-explanation.

> **The standing rule:** append a dated **event** to the timeline here; edit concept **prose**
> in `CONCEPTS.md`. If you're about to explain *how something works* in this file, stop —
> that belongs in a `§` section, and this entry just links to it.

---

## Where you are right now

**Step 2 of 10 is essentially done.** (`PRACTICE-APP.md` has the full 10-step runbook.)

- ✅ **Step 1** — Python 3.11.15 + SQLAlchemy 1.4.52 pinned, `uv.lock` committed.
- ✅ **Step 2** — `models.py`: all six relationship patterns built, including the
  self-referential `issue_blocks` / `blocks` / `blocked_by`. Committed & pushed (`6d6679e`).
  `uv run python -m experiments.sqlalchemy_1_4_vs_2_0.check` prints `mappers configured OK`.
- ✅ **Docs reorganised** — concepts moved to `CONCEPTS.md`; this log is now the timeline.
- ⬜ **`explore.py`** — you write it (spec + skeleton already given). Builds the schema,
  seeds ~12 traceable rows, prints the emitted SQL for every pattern. **← you are here.**
  It closes Step 2's "real database" item and fills in Part 3 of `CONCEPTS.md`.
- ⬜ **Steps 3–10** — seed ~200 rows, the 1.4 query layer, `SQLALCHEMY_WARN_20`, the 2.0
  upgrade, `BREAKAGES.md`.

**Immediate next action:** write your Part 3 predictions (in the timeline below, or straight
into `CONCEPTS.md`), *then* write `explore.py` and run it.

---

## Coverage — every concept has a lived entry

The "won't miss things" guarantee: every `CONCEPTS.md` section is reached from at least one
dated entry below, and every entry links to a section or is marked `(event only)`. Nothing
is orphaned in either direction, so this table doubles as a checklist.

| § | Concept | First hit |
|---|---|---|
| §1 | one law: a column holds one value | Jul 13 |
| §2 | one-to-many, FK on the many side | Jul 13 |
| §3 | many-to-many needs a third table | Jul 13 |
| §4 | junction with facts (`role`) | Jul 19 |
| §5 | self-referential ambiguity (SQL) | Jul 20 |
| §6 | `relationship()` vs `ForeignKey` | Jul 13 |
| §7 | `Table` vs mapped class | Jul 19 |
| §8 | `secondary=` hides the junction | Jul 13 |
| §9 | `primaryjoin` / `secondaryjoin` | Jul 21 |
| §10 | `backref` + the swap | Jul 13 |
| §11 | deferred resolution (quoted names) | Jul 13 |
| §12 | mappers configure lazily | Jul 13 |
| §13 | `remote_side` is a *different* knob | Jul 26 |

---

## Timeline

### Jul 11 — scaffold `(event only)`
Repo created; `ROADMAP.md`, `PHASE-0.md`, and the collaboration rule written. Practice-app
design + the 10-step breakage runbook drafted (`PRACTICE-APP.md`).

### Jul 12 — environment `(event only, → Step 1)`
Relocated into the dedicated git repo. Pinned **Python 3.11.15 + SQLAlchemy 1.4.52**, exact
versions, so "it broke" is never ambiguous later. `uv.lock` committed.

### Jul 13 — the schema, and three lessons in one hour → §1 §2 §3 §6 §8 §10 §11 §12
Wrote `models.py`: `User`, `Project`, `Issue`, `Comment`, `Label`, plus `issue_labels`
(plain junction `Table`) and `IssueAssignment` (association object). Deriving the shapes from
SQL first (§1, §2, §3) and understanding that `relationship()` only wraps the FKs (§6, §8).
Three failures the same afternoon, all instructive:
- **backref declared on both sides** → crash. Hit it on `Project`/`Issue`, fixed it, then hit
  the *identical* thing on `Issue`/`Label` 40 minutes later. → §10
- **`issue_labels` referenced above where it was defined** → `NameError`. The use-before-define
  that string forward-refs exist to avoid. → §11
- **`check.py` printed `OK` while `issue_labels` was wired to nothing** → the "green ≠ correct"
  lesson, and the reason `check.py` exists at all. → §12

### Jul 19 — the association object → §4 §7
Worked out where `role` and `assigned_at` can possibly live, and why that forces
`issue_assignments` to be a mapped class, not a `secondary=` table (§4, §7). Also sketched the
self-referential pattern in prose ahead of building it.

### Jul 20 — Pattern 6 built → §5 §9 §10
Implemented the self-referential many-to-many: the `issue_blocks` junction (two FKs into
`issues`) plus `Issue.blocks`. Re-derived the backref collision rule and why
`backref="assignments"` twice does *not* collide (different classes). → §5, §9, §10

### Jul 21 — proving the self-ref mechanics → §9 §10
Worked through it cold: what `id` binds to in the class body, which column is blocker vs.
blocked, how `primaryjoin`/`secondaryjoin` name the two joins (§9), and the prediction that
`backref="blocked_by"` produces its reverse by **swapping** them (§10). `check.py` green.

### Jul 23 — predict before you run → §0 (Part 0)
The "how do I answer what a traversal returns without data?" question — and the answer that a
prediction is a *derivation from the rows you chose*, not a lookup. If you can't predict it,
the mechanism isn't in your head yet. This is now the operating rule for Part 3 of
`CONCEPTS.md`.

### Jul 25 — self-ref committed `(event only)`
The self-referential `models.py` work committed & pushed (`6d6679e`) after sitting green but
uncommitted.

### Jul 26 — docs reorganised → §13
Split the concept material out of this log into `CONCEPTS.md` (deduped, one explanation each,
SQL-first spine). Rebuilt this file as the timeline. Fixed a real contradiction: the runbook
had said the self-referential relationship "needs `remote_side`" — wrong; that's the
adjacency-list knob for a self-referential *one*-to-many. Yours uses
`primaryjoin`/`secondaryjoin`. → §13

---

## Mistakes made — and the patterns behind them

Not shameful; they're the point. But several are the *same* mistake twice, and the pattern is
worth more than the individual fix. The concept each one teaches is in `CONCEPTS.md`; here is
just the pattern.

- **Declaring both sides of a `backref`** (twice: `Project`/`Issue`, then `Issue`/`Label`).
  The tell is always *"property of that name exists on mapper"*. Rule: write it **once**. → §10
- **Using a name before defining it** (`issue_labels` above `class Issue`, twice). A class body
  runs top-to-bottom at import; bare names must already exist. Strings are the exception, and
  that's *why* `relationship("Issue")` takes a string. → §11
- **Reaching for the 2.0 idiom by reflex** — `from sqlalchemy.orm import declarative_base`,
  `back_populates`. Normally the right instinct; **here it's the enemy**, because code that
  doesn't break produces no `BREAKAGES.md` entry. Suppressing this for two days is genuinely
  hard — notice it each time.
- **Copying the docs' example instead of the design** — the first `User` had
  `name`/`fullname`/`nickname`, straight from the tutorial. Read docs for *syntax*; never
  paste their *data model*.
- **Smaller ones:** `Column(String, enum=...)` (the type is the first positional arg, and
  `sqlalchemy.types.Enum` ≠ Python's `enum.Enum`); `body` on `Label` (wrong class); a trailing
  `\` line-continuation gluing two statements into one.
- **Mine (Claude's):** I told you `sqlalchemy.ext.declarative` was **removed** in 2.0. It's
  **moved and deprecated** (`MovedIn20Warning`) — I asserted an API fact without checking. And
  I pointed you at the 1.4 docs page that teaches the *new* import, then criticised you for
  using it. You were right to push back both times. **Don't take my API claims on trust — make
  the library say it** (that's what Part 3 is for).

---

## The boundary — what goes in `BREAKAGES.md` and what doesn't

**`BREAKAGES.md` is only for things that worked in 1.4 and stopped working in 2.0.**

Your own bugs — the duplicate backref, the missing import, the misused `Enum` — do **not** go
in it. They're just mistakes, and they live in the timeline above.

Why it matters: `BREAKAGES.md` becomes the seed of the Phase 2 golden dataset. Pad it with
your own typos and you poison it with questions no real user would ask, and you can no longer
defend the corpus in an interview.

---

## Breakages found so far (candidates for `BREAKAGES.md`)

Target is ≥10. These get written up properly — exact error text, 2.0 fix, migration-guide
link — in Step 7, after the real 2.0 run in Step 8.

1. **`declarative_base()` imported from `sqlalchemy.ext.declarative`** → `MovedIn20Warning`;
   now lives at `sqlalchemy.orm.declarative_base`. *Found by argument + test, not by reading.*
2. **`backref=`** → discouraged in 2.0 in favour of explicit `back_populates` on both sides.
   *(Not yet verified against a real 2.0 run — confirm in Step 8 before writing it up.)*
