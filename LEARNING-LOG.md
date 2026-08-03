# Learning log — the timeline

The **chronological** record of Phase 0: what got built, when, and what it took to get there.
It is deliberately *not* a place to explain concepts — those live in `CONCEPTS.md`, one
canonical explanation each, and every entry below links to a section number (`§0`–`§15`)
there.

This split is why the log stays readable: an idea gets one explanation in `CONCEPTS.md`, and a
*recurrence* here becomes a new dated link rather than a fresh re-explanation.

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
- ✅ **`explore.py`** — built and running. Seeds 21 rows across all six patterns and prints
  the emitted SQL, including a live N+1. Closes Step 2's "real database" item.
- ✅ **`CONCEPTS.md`** — every `§` now carries its own **Proof** (verified output) and
  **Drill** (42 questions, collapsed answers). §0 schema map and §14/§15 runtime added.
- ✅ **Step 3** — `seed.py` builds `issues.db`: 200 issues, 710 comments, 387 label links,
  303 assignments, 60 blocking pairs. Deterministic and idempotent.
- ⬜ **Steps 4–10** — the 1.4 query layer, baseline query counts, `SQLALCHEMY_WARN_20`, the
  2.0 upgrade, `BREAKAGES.md`. **← you are here. No breakage work has started.**

**Immediate next action:** Step 4 — `app.py`, half a dozen functions in deliberately bad 1.4
style: `session.query(...)`, `Query.get()`, a raw `engine.execute("SELECT ...")` without
`text()`, an N+1 report loop, and a function that returns an `Issue` after its session closed
(the future `DetachedInstanceError`, → §14).

---

## Coverage — every concept has a lived entry

The "won't miss things" guarantee: every `CONCEPTS.md` section is reached from at least one
dated entry below, and every entry links to a section or is marked `(event only)`. Nothing
is orphaned in either direction, so this table doubles as a checklist.

| § | Concept | First hit |
|---|---|---|
| §0 | the whole schema on one screen | Aug 3 |
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
| §14 | session states, flush vs commit | Aug 3 |
| §15 | expiry, lazy loading, N+1 | Aug 3 |

---

## Timeline

### Jul 11 — scaffold `(event only)`
Repo created; `ROADMAP.md`, `PHASE-0.md`, and the collaboration rule written. Practice-app
design + the 10-step breakage runbook drafted (`PRACTICE-APP.md`).

### Jul 12 — environment `(event only, → Step 1)`
Relocated into the dedicated git repo. Pinned **Python 3.11.15 + SQLAlchemy 1.4.52**, exact
versions, so "it broke" is never ambiguous later. `uv.lock` committed.

### Jul 13 — the schema, and three standing rules → §1 §2 §3 §6 §8 §10 §11 §12
Wrote `models.py`: `User`, `Project`, `Issue`, `Comment`, `Label`, plus `issue_labels`
(plain junction `Table`) and `IssueAssignment` (association object). Deriving the shapes from
SQL first (§1, §2, §3) and understanding that `relationship()` only wraps the FKs (§6, §8).
Three things surfaced the same afternoon, each of which became a standing rule:
- **backref declared on both sides** → crash, on `Project`/`Issue` and again on
  `Issue`/`Label`. → §10
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
the mechanism isn't in your head yet. This is now the operating rule for `CONCEPTS.md` drills.

### Jul 25 — self-ref committed `(event only)`
The self-referential `models.py` work committed & pushed (`6d6679e`) after sitting green but
uncommitted.

### Jul 26 — docs reorganised → §13
Split the concept material out of this log into `CONCEPTS.md` (deduped, one explanation each,
SQL-first spine). Rebuilt this file as the timeline. Fixed a real contradiction: the runbook
had said the self-referential relationship "needs `remote_side`" — wrong; that's the
adjacency-list knob for a self-referential *one*-to-many. Yours uses
`primaryjoin`/`secondaryjoin`. → §13

### Jul 30 – Aug 2 — `explore.py`: the patterns, running → §2 §7 §8 §9 §10
Built the session layer and seeded a live database, covering every relationship pattern in
`models.py`.

What the run actually proved, as opposed to asserted:
- **PKs arrive at `flush()`, not `add()`.** `None → 1`, watched live. `add()` only stages.
- **The save-update cascade is real.** Three issues and two labels were never passed to
  `session.add()`; attaching them to something already in the session enrolled them. → §6
- **FKs get resolved from object references.** `project_id` came out `1 1 1` with no manual
  assignment anywhere. → §2
- **`secondary=` writes to a third table and touches neither mapped class.**
  `issue_labels` rows `[(1,1) (1,2) (2,3) (3,1) (3,3) (7,2)]`. → §8
- **`Comment` carries two attributes its own class body never declares** — `.issue` and
  `.author`, both injected by `backref=` from *other* classes. → §10
- **The swap, observed rather than argued.** `issue_blocks` rows `[(3,7) (3,9) (9,7)]`;
  `issue9.blocks → [7]` while `issue9.blocked_by → [3]`. Same table, two directions —
  and the join conditions read off the mapper show `primaryjoin`/`secondaryjoin` traded.
  → §9 §10
- **N+1 caught in the act.** With `engine.echo = True` after `commit()`: one SELECT to
  re-load the expired project, one for its issues, then one *per issue* for labels.
  `expire_on_commit=True` is why the first one happens at all.

Also: added `description` to `Issue` — the declarative constructor rejects unknown kwargs
outright, so a missing column fails loudly at `__init__` rather than silently — and `__repr__`
to every mapped class.

### Aug 3 — Step 3, the seed that hurts `(event only, → Step 3)`
`seed.py` writes a real SQLite **file** (`issues.db`), not in-memory — Step 4 opens the same
database from a separate process. Generated in a loop from a fixed `RANDOM_SEED`, so the
counts never move between runs; if they moved, the "202 queries before, 2 after" comparison
in Step 9 would mean nothing.

```
users 5 · projects 3 · issues 200 · labels 8
comments 710 · issue_assignments 303 · issue_labels 387 · issue_blocks 60
open 106 · in_progress 40 · closed 54
```

Two schema constraints shaped the generator, both from Part 1: `IssueAssignment`'s PK is
`(issue_id, user_id)`, so assignees are sampled *without replacement* — the same person can't
hold two roles on one issue (§4). And `issue_blocks` pairs are deduplicated in both directions
with self-blocks skipped (§5). Verified in SQLite rather than through the ORM: 0 orphan rows,
0 self-blocks, 0 duplicate pairs.

### Aug 3 — docs consolidated, runtime sections added → §0 §14 §15
Folded the separate drills file into `CONCEPTS.md` so each `§` is self-contained: explanation,
**Proof** from a real run, then a **Drill** with collapsed answers. No more bouncing between
files to finish one concept.

New material, all verified rather than asserted:
- **§0** — the six-table schema map, plus the four questions that generate every pattern.
- **§14** — object states traced with `inspect()`: transient → pending → persistent →
  detached, and the identity map. Corrected a Claude error here: "expired" is a *flag on a
  persistent object*, not a fifth state.
- **§15** — N+1 drawn as a timeline, with loading strategies counted on a real engine:
  lazy `10`, `selectinload` `2`, `joinedload` `1`.
- **§5, §8, §9** — diagrams for the FK ambiguity, the two-hop join path, and the swap.

`explore.py` grew to 9 issues with `issue_blocks` rows (3→7) (3→9) (9→7) — the asymmetric
shape where issue 9 sits on both sides, which is the only arrangement that can actually prove
the swap fired.

**Not done here:** the `CONCEPTS.md` is still `OUTPUT PENDING` throughout. Its
**Predict** fields are deliberately yours (the Jul 23 rule), and the seed there assumes a
different dataset — issues 3/7/9 with `issue_blocks` rows (3→7), (3→9), (9→7) — than the
three-issue set `explore.py` currently builds. One of the two has to move.

---

## Gotchas — the ones this schema actually hits

Standing rules, each earned by hitting the thing it prevents. The concept behind each is in
`CONCEPTS.md`; this is just the rule and its tell.

- **Declare a `backref` once, on one side only.** The tell when you don't: *"property of that
  name exists on mapper"*. → §10
- **A class body runs top-to-bottom at import**, so a bare name must already exist above it.
  Strings are the exception — and that's precisely *why* `relationship("Issue")` takes one.
  → §11
- **Don't reach for the 2.0 idiom here.** `from sqlalchemy.orm import declarative_base`,
  `back_populates` — normally the right instinct, but on this project code that doesn't break
  produces no `BREAKAGES.md` entry. The 1.4-isms are the deliverable.
- **Read docs for syntax, not for a data model.** The tutorial's `name`/`fullname`/`nickname`
  `User` is an illustration, not a schema.
- **Column type is the first positional arg** — `Column(String)`, and `sqlalchemy.types.Enum`
  is not Python's `enum.Enum`.
- **Claude's, for the record:** I said `sqlalchemy.ext.declarative` was **removed** in 2.0.
  It's **moved and deprecated** (`MovedIn20Warning`) — an API fact asserted without checking.
  I also pointed at a 1.4 docs page teaching the *new* import and then objected to it being
  used. Both were pushed back on, correctly. **Don't take my API claims on trust — make the
  library say it** (that's what the **Proof** blocks are for).

---

## The boundary — what goes in `BREAKAGES.md` and what doesn't

**`BREAKAGES.md` is only for things that worked in 1.4 and stopped working in 2.0.**

Bugs in your own code — a duplicate backref, a missing import, a misused type — do **not**
go in it. Those are ordinary bugs, not version breakages.

Why it matters: `BREAKAGES.md` becomes the seed of the Phase 2 golden dataset. Padding it
with local typos poisons it with questions no real user would ask, and the corpus stops being
defensible.

---

## Breakages found so far (candidates for `BREAKAGES.md`)

Target is ≥10. These get written up properly — exact error text, 2.0 fix, migration-guide
link — in Step 7, after the real 2.0 run in Step 8.

1. **`declarative_base()` imported from `sqlalchemy.ext.declarative`** → `MovedIn20Warning`;
   now lives at `sqlalchemy.orm.declarative_base`. *Found by argument + test, not by reading.*
2. **`backref=`** → discouraged in 2.0 in favour of explicit `back_populates` on both sides.
   *(Not yet verified against a real 2.0 run — confirm in Step 8 before writing it up.)*
