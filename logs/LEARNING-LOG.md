# Learning log — the timeline

The **chronological** record of Phase 0: what got built, when, and what it took to get there.
It is deliberately *not* a place to explain concepts — those live in `study/01-CONCEPTS.md`, one
canonical explanation each, and every entry below links to a section number (`§0`–`§15`)
there.

This split is why the log stays readable: an idea gets one explanation in `study/01-CONCEPTS.md`, and a
*recurrence* here becomes a new dated link rather than a fresh re-explanation.

> **The standing rule:** append a dated **event** to the timeline here; edit concept **prose**
> in `study/01-CONCEPTS.md`. If you're about to explain *how something works* in this file, stop —
> that belongs in a `§` section, and this entry just links to it.

---

## Where you are right now

**All ten steps are done.** (`study/03-PRACTICE-APP.md` has the runbook.) Phase 0 Part A is complete
and Part C is most of the way; `phases/ROADMAP.md` §10 has the per-part status, computed.

```
# runnable: grep -c '^### ' deliverables/BREAKAGES.md
23

# runnable: uv run --no-project --with 'sqlalchemy==2.0.51' \
#             python -m experiments.sqlalchemy_1_4_vs_2_0.verify_2_0
  22 of 24 patterns FAIL on 2.0.51
```

The list below is the state as of **Aug 3**; everything after it is in the timeline.

- ✅ **Step 1** — Python 3.11.15 + SQLAlchemy 1.4.52 pinned, `uv.lock` committed.
- ✅ **Step 2** — `models.py`: all six relationship patterns built, including the
  self-referential `issue_blocks` / `blocks` / `blocked_by`. Committed & pushed (`6d6679e`).
  `uv run python -m experiments.sqlalchemy_1_4_vs_2_0.check` prints `mappers configured OK`.
- ✅ **Docs reorganised** — concepts moved to `study/01-CONCEPTS.md`; this log is now the timeline.
- ✅ **`explore.py`** — built and running. Seeds 21 rows across all six patterns and prints
  the emitted SQL, including a live N+1. Closes Step 2's "real database" item.
- ✅ **`study/01-CONCEPTS.md`** — every `§` now carries its own **Proof** (verified output) and
  **Drill** (42 questions, collapsed answers). §0 schema map and §14/§15 runtime added.
- ✅ **Step 3** — `seed.py` builds `issues.db`: 200 issues, 710 comments, 387 label links,
  303 assignments, 60 blocking pairs. Deterministic and idempotent.
- ✅ **Step 4** — `app.py`: five functions in deliberately bad 1.4 style, all green.
- ✅ **Steps 5–10** — baseline query counts (**204**, counted not estimated), the
  `SQLALCHEMY_WARN_20` sweep, verification against real 2.0, and `deliverables/BREAKAGES.md`. Done Aug 4–6;
  see the timeline.

**Immediate next action:** `tests/`, then CI. The Day 8–9 gate is *"a PR containing a
deliberately failing test that GitHub refuses to merge"*, and there is nothing for a workflow
to run yet.

---

## Coverage — every concept has a lived entry

The "won't miss things" guarantee: every `study/01-CONCEPTS.md` section is reached from at least one
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
Repo created; `phases/ROADMAP.md`, `phases/PHASE-0.md`, and the collaboration rule written. Practice-app
design + the 10-step breakage runbook drafted (`study/03-PRACTICE-APP.md`).

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
the mechanism isn't in your head yet. This is now the operating rule for `study/01-CONCEPTS.md` drills.

### Jul 25 — self-ref committed `(event only)`
The self-referential `models.py` work committed & pushed (`6d6679e`) after sitting green but
uncommitted.

### Jul 26 — docs reorganised → §13
Split the concept material out of this log into `study/01-CONCEPTS.md` (deduped, one explanation each,
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

### Aug 3 — Step 4, and a correction worth more than the code `(→ Step 4)`
`app.py`: five functions, all green under 1.4.52, all deliberately bad. Legacy `Query` API,
`Query.get()`, a raw `engine.execute()` with an unwrapped string, an N+1 report over all 200
issues, and a function returning a detached `Issue`.

**The finding.** The first draft's docstring claimed all of these were "2.0 problems". Testing
each one under `SQLALCHEMY_WARN_20=1` instead of assuming produced three different answers:

```
session.query(...).all()     -> NO WARNING        legacy, still works in 2.0
Query.get(42)                -> LegacyAPIWarning  deprecated, still works
engine.execute(str)          -> RemovedIn20Warning  actually removed
```

Only the third genuinely breaks. `DetachedInstanceError` isn't a version issue at all — it
fires identically in 1.4 (§14 has it traced). Neither is the N+1.

This is exactly the trap the boundary rule below exists for: three plausible-looking
"breakages", two of which would have poisoned the Phase 2 golden dataset with questions no
upgrading user would ask. Assertion caught by measurement, before it reached `deliverables/BREAKAGES.md`.

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
Folded the separate drills file into `study/01-CONCEPTS.md` so each `§` is self-contained: explanation,
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

**Not done here:** the `study/01-CONCEPTS.md` is still `OUTPUT PENDING` throughout. Its
**Predict** fields are deliberately yours (the Jul 23 rule), and the seed there assumes a
different dataset — issues 3/7/9 with `issue_blocks` rows (3→7), (3→9), (9→7) — than the
three-issue set `explore.py` currently builds. One of the two has to move.

---

## Gotchas — the ones this schema actually hits

Standing rules, each earned by hitting the thing it prevents. The concept behind each is in
`study/01-CONCEPTS.md`; this is just the rule and its tell.

- **Declare a `backref` once, on one side only.** The tell when you don't: *"property of that
  name exists on mapper"*. → §10
- **A class body runs top-to-bottom at import**, so a bare name must already exist above it.
  Strings are the exception — and that's precisely *why* `relationship("Issue")` takes one.
  → §11
- **Don't reach for the 2.0 idiom here.** `from sqlalchemy.orm import declarative_base`,
  `back_populates` — normally the right instinct, but on this project code that doesn't break
  produces no `deliverables/BREAKAGES.md` entry. The 1.4-isms are the deliverable.
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

## The boundary — what goes in `deliverables/BREAKAGES.md` and what doesn't

**`deliverables/BREAKAGES.md` is only for things that worked in 1.4 and stopped working in 2.0.**

Bugs in your own code — a duplicate backref, a missing import, a misused type — do **not**
go in it. Those are ordinary bugs, not version breakages.

Why it matters: `deliverables/BREAKAGES.md` becomes the seed of the Phase 2 golden dataset. Padding it
with local typos poisons it with questions no real user would ask, and the corpus stops being
defensible.

---

## Breakages found so far (candidates for `deliverables/BREAKAGES.md`)

Target is ≥10. These get written up properly — exact error text, 2.0 fix, migration-guide
link — in Step 7, after the real 2.0 run in Step 8.

Sorted by severity, because the distinction turned out to matter more than expected — see
the Aug 3 Step 4 entry. Only the REMOVED tier is a true breakage.

**Removed — these actually fail in 2.0:**
1. **`engine.execute("SELECT ...")`** → two `RemovedIn20Warning`s from one line: connectionless
   execution *and* the bare string. Fix: `with engine.connect() as c: c.execute(text(...))`.
   *Measured under 1.4.52 with `SQLALCHEMY_WARN_20=1`.*
2. **`declarative_base()` imported from `sqlalchemy.ext.declarative`** → `MovedIn20Warning`;
   now at `sqlalchemy.orm.declarative_base`. Moved and deprecated, **not** removed.

**Deprecated — warns, still runs:**
3. **`Query.get(pk)`** → `LegacyAPIWarning`. Fix: `session.get(Model, pk)`.

**Legacy — silent, still runs. Probably NOT `deliverables/BREAKAGES.md` material:**
4. **`session.query(Model)`** → emits **no warning at all**, even under `WARN_20`, and works
   in 2.0. The 2.0 *style* is `select()`, but 1.x `Query` remains supported. Listed here so
   the eventual write-up says "style migration", not "breakage".
5. **`backref=`** → discouraged in favour of `back_populates`. *(Still unverified against a
   real 2.0 run — confirm in Step 8.)*

**Not version issues — do not put these in `deliverables/BREAKAGES.md`:** the N+1 in `issue_report()`
(equally slow in both) and `DetachedInstanceError` (fires in 1.4 too, → §14).

### Aug 4 — the runtime, and a wrong answer caught → §14 §15

- `states.py` added: five object states via `inspect()`, the attribute-cache wipe at
  `commit()`, the identity map, and a query counter for lazy / selectinload / joinedload.
- **Two of four `# runnable` blocks in `study/01-CONCEPTS.md` named no command.** The numbers were real
  and not reproducible. That is where the measurement rule in `CLAUDE.md` comes from.
- **A drill answer was wrong.** "flush vs commit — name two differences" claimed commit expires
  objects. Expiry is `expire_on_commit`, a `Session` flag; set it `False` and commit expires
  nothing. The answer also missed the largest difference: commit flushes for you.
- Part 4 split into `study/02-MIGRATION-2.0.md` — `study/01-CONCEPTS.md` had reached 2161 lines. Numbering
  continues across the pair, which is the same split `study/05-COMPOSE.md` gets later.

### Aug 5–6 — the four-tool harness, and `deliverables/BREAKAGES.md` → §16–§22

- **Provenance audit:** 40 doc lines did not match real output; 0 across 106 blocks afterwards.
  The fixes went into the *scripts*, so a `# runnable` block is a literal paste.
- **Six wrong claims found in §16–§22.** The largest: `MovedIn20Warning` **subclasses**
  `RemovedIn20Warning`, so `isinstance()` triage over-reports.
- **`cascade_backrefs` — the biggest finding, and it was not in the chapter at all.** An object
  attached by the many-to-one side is never enrolled under 2.0: no exception, the `INSERT`
  simply never runs.
- Built `sweep.py`, `patterns.py`, `candidates.py`, `verify_2_0.py` — measuring real 2.0
  without upgrading the project.
- **`deliverables/BREAKAGES.md`: 23 entries against a target of 10.** One pattern (`row["col"]`) is called
  *safe* by both 1.4-side tools and still fails on real 2.0 — the empirical argument for
  running the real thing.

### Aug 8 — `deliverables/BREAKAGES.md` made rereadable `(event only)`

Reshaped into groups A–H with a "What 1.4 did / What 2.0 does" reading per entry. Every
measured field left untouched, verified by regenerating and diffing.

### Aug 9–10 — Docker, Days 4–5 `(→ study/04-DOCKER.md)`

- `Dockerfile`, `.dockerignore`, `entrypoint.sh` written from empty files.
- **Base image chosen on measurement:** 214MB vs 1.62GB on disk, 48MB vs 416MB to download,
  against a PyPI check showing a `manylinux_2_17_aarch64` wheel exists — so `-slim` needs no
  compiler. The build confirmed it: that exact wheel, 4.3s, no gcc.
- **Injected failure diagnosed cold** — `*.txt` in `.dockerignore` broke `COPY requirements.txt`
  with *"not found"* while the file sat on disk. The answer is that the CLI filters the context
  on the host and the daemon runs `COPY` inside the VM; the file never crossed.
- **A stale image fooled both of us for an hour.** It was 13 hours older than the code, ignored
  `DATABASE_URL`, and produced believable output that proved nothing.

### Aug 12 — Day 6, Compose and Postgres `(→ study/05-COMPOSE.md)`

- Two services, service-name DNS, `pg_isready` healthcheck with `condition: service_healthy`,
  named volume, no published ports.
- **The volume exposed a contradiction:** `seed.py` opened with `drop_all()` on every start —
  harmless against a disposable SQLite file, destructive against a volume that exists so data
  survives. It now seeds only when the database is empty.
- **`--network` does two jobs, and only one had been measured.** DNS, yes — but also isolation:
  a container on the default bridge cannot reach a user-defined network *even by IP*. It times
  out.
- **`POSTGRES_USER` does not create a limited account**; it renames the superuser. `rolsuper = t`.

### Aug 13 — one name, and the example rule `(event only)`

- The image was `sqlagent` while everything else was `sqlalchemy-upgrade-agent`; the Postgres
  role was *also* `sqlagent`. Now one name for the project and image, and `app` for the role,
  which cannot take a hyphen without forcing quotes in every statement.
- **An example audit across all eleven docs** found one outlier: `study/03-PRACTICE-APP.md`, 292 lines
  explaining a schema with zero code blocks — and asserting *"Six tables"* where there are six
  mapped classes and eight tables. Prose is where a wrong claim survives.
- `CLAUDE.md` gains the **example rule** beside the measurement rule, applying retroactively.

### Aug 13 — lab PC sitting, Ubuntu diary `(→ study/08-LAB.md)`

AnyDesk on user `shaili`, Dell XPS 8950. Clone + local git identity + `gh` as
Viraj + Cursor as Viraj. `uv sync --frozen` / pytest **17 passed** on this box.
Hardware measured: **31 GiB RAM**, RTX 3060 **12288 MiB** VRAM. The 12GB-system-RAM
plan was a guess; VRAM is the real budget. Langfuse stays Phase 6 for product
reasons, not RAM. Docker blocked on typed `sudo`. Do not touch `~/.claude`.

The sitting is written out in Ubuntu words in `study/08-LAB.md` ("New to Ubuntu?
This sitting, explained"). Further PC steps get appended there, not only in chat.

### Aug 13 — Phase 1 Step 1, the corpus `(→ phases/PHASE-1.md, rag/corpus.py)`

- **A corpus is a ceiling, not a download.** Retrieval, reranking and the agent all find the
  right chunk faster; none of them can find a chunk that is not there. So Step 1 caps every
  number the next three months will report — and a corpus that is *too large* is also worse,
  because every irrelevant page is one more thing search can confidently return instead.
- **Version skew, seen rather than described.** Same file, both pinned tags:
  1.4's `tutorial/engine.rst:37` teaches `create_engine(..., echo=True, future=True)`;
  2.0's `tutorial/engine.rst:36` has dropped the flag. `future=True` appears in 15 files of
  the 1.4 docs and 3 of the 2.0 docs. Ask *"should I pass `future=True`?"* and dense retrieval
  returns a genuinely excellent 1.4 passage — **confident, correctly sourced, wrong.**
  Recorded on every chunk, deliberately **not** filtered: that failure is Phase 3's argument.
- **The API reference is not in the docs source.** 660 `.. autoclass::`-family directives in
  the 1.4 tree, 743 in 2.0 — instructions to read a Python docstring at Sphinx build time.
  "Docs source" and "the API reference" are two corpora, and only the first was fetched.
- **`changelog/` is ~60% of the bytes and almost none of the answers.** One file taken out of
  it (`migration_20.rst`, 93197 bytes); the other ~33 left behind.
- **`BREAKAGES.md` stayed out of the corpus** because it seeds the Phase 2 golden dataset.
  Retrieval that can find its own answer key does not produce a Phase 2 number worth quoting.
- **Neither version is typed into the fetcher.** 1.4.52 comes from `pyproject.toml`'s pin,
  2.0.51 from `verify_2_0.PIN` — read as source text, since that module `sys.exit()`s on
  import under 1.4 by design. The corpus cannot document a release the repo is not on.
- **A manifest with a timestamp is a manifest nobody reads.** `corpus/MANIFEST.json` carries
  none, so it is a pure function of the two tags and the selection rules and a diff on it
  means the corpus really moved. Checked rather than claimed: `--force` re-downloads both
  tarballs and reproduces the file byte-for-byte.

### Aug 15 — Phase 1 Steps 3–5, and three things that turned out wrong `(→ phases/PHASE-1.md)`

- **The `Query.get()` example never reproduced.** Cited from the roadmap onward as the case
  dense retrieval fumbles; BGE-M3 ranked it **1 of 3284**. Corrected in all three places that
  claimed it. The *underlying* claim survived on other symbols — see below.
- **26.6% of the index is a cross-version duplicate.** 437 texts appear twice, every one of
  them 1.4-text == 2.0-text, none within a version. It cost a top-k slot on the very first
  query run.
- **Bigger batches are slower on Metal** — 64 → 3.6 chunks/s against 7.4 at batch 4. And
  `--limit` takes the *first* n chunks rather than a sample, so that sweep ran on a
  shorter-than-average slice. Both worth saying out loud rather than reporting the ranking as
  if it were clean.
- **The worst bug was in the prompt, the one component nobody suspects** because it is
  hand-written rather than measured. A "say exactly: the sources do not answer this" clause
  made the model refuse a question whose answer was *in the prompt*. Two wrong hypotheses were
  tested first (duplicates eating slots; retrieval ranking it too low) and both were ruled out
  by experiment before the real cause was found. Removing the clause entirely made it invent a
  method signature. The clause is necessary AND over-fires; the wording that threads it was
  chosen by testing both failure directions.
- **`simple` and `broken` are different.** D04 withholds hybrid search and reranking. It does
  not license shipping a component that does not work — with the bad prompt in place, every
  Step 5 failure would have been unattributable.
- **The finding that makes Phase 3 measurable:** a retrieval miss means two different things.
  The symbol is in the corpus and search missed it (**fixable**), or it is in no chunk at all
  (**the ceiling**). Step 5 found 4 and 1. Without the split, Phase 3 would be graded against a
  target including something it can never move.
- **The report does not grade itself.** 19 answers, all marked `UNVERIFIED`. A script scoring
  its own model's output with the same model family measures self-consistency, not truth.
