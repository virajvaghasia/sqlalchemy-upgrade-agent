# Working agreement — how Claude works on this repo

Instructions for the AI assistant. Humans want [`README.md`](README.md), which maps the repo;
this file is about *how the work gets done*, not what the work is.

The project: a RAG system that helps developers upgrade Python code from
**SQLAlchemy 1.4 → 2.0**. Portfolio project targeting Applied AI Engineer roles (Nvidia,
Meta, Google, Apple, Anthropic, and startups).

- **`README.md`** — the front door and the map: every doc, every script, and what each proves.
  **Keep it current** — it is the only file that indexes the whole repo.
- **`ROADMAP.md`** — the full ~4-month arc, six phases, plus a glossary of every AI term.
- **`PHASE-0.md`** — the current phase in detail.
- **`CONCEPTS.md`** — §0–§15: the relational model, the ORM layer, the session at runtime.
- **`MIGRATION-2.0.md`** — §16–§22: the 1.4 → 2.0 upgrade. Continues `CONCEPTS.md`'s section
  numbering, so a reference to "§18" is unambiguous across both files.
- **`BREAKAGES.md`** — the Phase 0 Part A deliverable. 23 entries, each with the 1.4 code and
  the real 2.0 error. Generated skeleton; the *fix* and *docs* fields are Viraj's to write.
  Never regenerate over it once filled — diff instead (the file's own header says how).
- **`experiments/sqlalchemy_1_4_vs_2_0/__init__.py`** — the package manifest: what each of the
  eleven modules is for, in run order.

### The measurement rule — applies to every doc and every script

**Never assert a number, a count, or an output you did not derive.** If a doc shows output, a
`# runnable` command must reproduce it verbatim — folding, wrapping and annotations are the
*script's* job, never hand-editing in the markdown. If a script prints a count, it must compute
it, not carry a literal someone typed once.

This is not style. Every time it has been violated in this repo, Viraj caught it and the
underlying claim turned out to be wrong or unreproducible — the §14 state trace with no file
behind it, the hardcoded `issue_id in (1, 3)`, the flush/commit answer, the `1013 / 7 / 8`
table. Assume the same will happen again.

---

## THE COLLABORATION RULE — read this before writing any code

Viraj has 2 years of production experience that was **heavily AI-assisted**. He recognizes
Docker, CI/CD, and cloud tooling but cannot reason about or debug them. His résumé claims
fluency in exactly those things. **Closing that gap is a primary goal of this project — not
a side effect.**

### Infrastructure — HE writes it. Claude does NOT.

Docker, Docker Compose, CI/CD, deployment, shell/systemd, system design.

Claude's role is to **explain, review, and drill**. Not to produce.

If Claude writes the Dockerfile, he gets a working container and learns nothing, and the
résumé gap stays open. **That dependency is exactly what caused the problem.** Writing it
"just to save time" is the single most damaging thing Claude can do on this project.

When he's stuck on infra: ask what he's tried, explain the concept, point at the docs, let
him write it. Then drill him on *why* it works.

### AI / LLM material — Claude is hands-on.

Embeddings, retrieval, chunking, reranking, evaluation, agents, MCP.

He is honestly new here, has no prior claim to the knowledge, and no interviewer expects him
to have arrived with it. Pair freely, write code, explain as you go.

**The asymmetry is deliberate: most help where he's honestly new, least help where he's
supposed to already know.**

---

## Tone

He explicitly asked for a principal-engineer mentor who **pushes back hard and does not
flatter**. Confront contradictions directly. Soft feedback is what let the skill gap open in
the first place.

## Genuine strength to build on

**Databases and SQL** — real and verifiable. It's why the SQLAlchemy corpus is defensible,
and why Postgres (rather than something unfamiliar) is the right prop for teaching Docker
networking.

---

## Key design decisions (don't silently reverse these)

- **Build the naive version first.** Phase 1 is dense-retrieval-only, deliberately bad.
  Hybrid search and reranking are *fixes for problems* — he must watch the simple version
  fail before the fix means anything, or he can't defend it under questioning.
- **The golden dataset is hand-verified, never auto-generated.** AI may draft and reformat;
  only Viraj verifies. An auto-generated golden set grades your own homework with your own
  answer key.
- **Zero paid API calls.** Local models on the RTX 3060 + free tiers only.
- **Build machine is the Ubuntu lab PC** (3060, 12GB VRAM, 12GB system RAM), reached over
  SSH. **Push to GitHub constantly** — it's a shared lab machine that may be reimaged.
  - **As of 2026-08-04 the lab machine is not reachable.** All work is happening on the Mac
    and will be pulled down at the lab later. This *inverts* the risk the "push constantly"
    rule was written for: GitHub is no longer the backup of the lab machine, it is the
    **handoff channel to it**, and the Mac is now the only copy of anything uncommitted.
    Commit and push at the end of every session — an unpushed commit is invisible at the lab.
  - **What this does and does not unblock.** Phase 0 Part A (Days 0–2: `uv`, the 1.4 app,
    the 2.0 migration, `BREAKAGES.md`) needs nothing but Python and runs fine here. Parts B
    and C (Docker, Compose, GPU-in-container, CI, Ollama) need the lab machine and are
    blocked — those are also precisely the infra items Viraj must write himself, so they
    cannot be worked around by having Claude produce them early.
- **Langfuse is deferred to Phase 6 and run on-demand** — ~5 containers won't fit in 12GB
  alongside everything else.

## Naming conventions

| Thing | Convention |
|---|---|
| Repo / folder / GitHub | `kebab-case`, all identical |
| Python packages | `snake_case` (hyphens are illegal in imports) |
| Root docs | `SCREAMING_CASE.md` |
| Branches | `phase-N/short-topic` |
| Commits | Conventional Commits (`feat:`, `fix:`, `docs:`) |

---

## Session Notes (what Claude is doing, session by session)

This is a running, terse log of *actions taken in a given session* — not concepts learned
(that's `LEARNING-LOG.md`) and not settled design calls (that's the `⚖` memory entries).
Append a dated entry each session; keep each entry to a few bullets.

### 2026-07-30
- Clarified collaboration scope for the `explore.py` session-layer + seeding task: per
  the collaboration rule above, this is a paired exercise (Claude explains the pattern,
  Viraj writes the code) — not something Claude hands over finished.
- Added this Session Notes section to CLAUDE.md at Viraj's request, so session activity
  is readable here without digging through conversation history.
- Created `CONCEPTS.md` drills — a Q&A register (questions Claude poses + questions Viraj asks),
  separate from `CONCEPTS.md` (prose) and `LEARNING-LOG.md` (timeline).

### 2026-08-02
- Built out `explore.py` sections 1–8: users/project, issues, labels, comments,
  IssueAssignment, self-referential blocks, a lazy-load/N+1 demo, and row counts.
- Added `description` column to `Issue` and `__repr__` to all mapped classes.
- `explore.py` now runs end to end and seeds 15 rows across all six patterns.

### 2026-08-03
- Replaced §6's three assertion `print()`s with the join conditions read live off the
  mapper — Viraj challenged them, correctly: a script whose purpose is watching the library
  behave shouldn't contain "trust me" prints.
- **Seed mismatch resolved.** `explore.py` grown to 9 issues with `issue_blocks` rows
  (3→7) (3→9) (9→7), matching what the `CONCEPTS.md` always specified.
- **`CONCEPTS.md` Part 3 renamed to "Appendix"** and filled with verified output — the old
  name collided with `CONCEPTS.md` drills's parts and read as a fourth teaching chapter rather than
  evidence.
- **`CONCEPTS.md` drills restructured** to two halves, Questions and Answers, 42 items. The 2.0 group
  is left unanswered on purpose — those get settled by running Step 6.
- Fact-checking the answer key caught a wrong answer of Claude's (#13: `issue.project`
  does *not* always emit SQL — many-to-one checks the identity map first). Corrected in
  place, with the measurement.

### 2026-08-04
- Viraj challenged the provenance of §14's state-trace output. Audit found 2 of 4
  `# runnable` blocks in `CONCEPTS.md` named no command and had no file behind them —
  the numbers were real but not reproducible.
- Added `experiments/sqlalchemy_1_4_vs_2_0/states.py` — the runtime counterpart to
  `explore.py`: five object states via `inspect()`, the attribute-cache wipe at `commit()`,
  the identity map, and a `before_cursor_execute` counter for lazy/selectinload/joinedload.
- First run of `states.py` reported 11 for the lazy loop instead of 10: sections 1–3 shared
  one in-memory DB with the counting sections, so their throwaway `Issue` made
  `query(Issue).all()` return 10 rows. Split into two engines and added an
  `assert n_issues == 9` guard.
- `CONCEPTS.md` §14/§15 now name real commands; documented that 11 vs 10 is a scope
  difference (Scope A includes the `apollo.name` re-SELECT), not a typo.
- Viraj challenged §14 drill answer #2 ("flush vs commit — name two differences"). Testing
  showed (b) was wrong as written: expiry is `expire_on_commit`, a `Session` flag defaulting
  to `True`, not a property of `commit()`. Set it `False` and commit expires nothing. The
  answer also omitted the largest difference — `commit()` flushes for you. Rewrote as three
  measured points and added `states.py` §6 to back them.
- Rewrote all 15 drill answer sets to one shape: **short plain-language answer → why →
  evidence**. Added the desk/filing-cabinet analogy to §14 (session = desk, database =
  cabinet, objects = photocopies) and an expired-vs-detached comparison table.
- **Part 4 split into `MIGRATION-2.0.md`** at Viraj's request (CONCEPTS.md had reached 2161
  lines). Section numbering continues across the two files — `CONCEPTS.md` §0–§15,
  `MIGRATION-2.0.md` §16–§22 — so cross-references stay unambiguous. Expanded from 4
  sections to 7 while moving: added §17 (the Result API — `session.execute()` returns `Row`
  tuples, hence `.scalars()`), §18 (autobegin — a plain SELECT opens a transaction), and §22
  (the ordered migration recipe, with modernisation explicitly *after* the version bump).
- **Measured finding worth keeping:** the 2.0 warnings are off by default. `app.py` emits 1
  warning normally and 5 under `SQLALCHEMY_WARN_20=1` — and *both* `RemovedIn20Warning`s,
  the only real breakages, are in the hidden four. A green 1.4 test run is not evidence
  about 2.0.
- **Superseded (earlier the same day):** Part 4 was first built out from 4 bare questions
  into a chapter (§16–§19), matching Parts
  1–3's teach-then-drill shape: §16 why 2.0 exists (unification; `query()` vs `select()`
  emit near-identical SQL — a rename, not a rewrite), §17 the four warning classes
  (`RemovedIn20Warning` / `MovedIn20Warning` / `LegacyAPIWarning` / silence), §18
  `future=True` as the migration bridge, §19 what 2.0 does *not* fix.
  **The four prediction questions are left unanswered** — per the Days 1–2 design decision,
  those are settled by running the upgrade. §16–§19 exist so the predictions are informed.
- Added `experiments/sqlalchemy_1_4_vs_2_0/migration.py` to back Part 4's runnable blocks:
  measures the `query()`/`select()` SQL diff and demonstrates `future=True` raising
  `NotImplementedError` on `engine.execute()` under 1.4.52.
- Viraj caught a hardcoded `issue_id in (1, 3)` in `states.py` §7 — an assertion about the
  seed dressed up as an observation of the join. Now counted with `Counter` and derived from
  the returned rows.
- §15's selectinload/joinedload table described the SQL instead of showing it, so the
  difference wasn't visualisable. Added `states.py` §7: prints the actual statements for all
  three strategies (the `params` line makes it obvious — nine `(1,)` `(2,)`… vs one
  `(1..9)`), plus the 11-raw-rows-for-9-issues output that makes joinedload's row
  multiplication concrete rather than asserted.

### 2026-08-05 / 08-06
- **Provenance audit of `MIGRATION-2.0.md`.** Viraj asked whether code and docs were in sync.
  40 doc lines didn't match real output; now 0 across 106 blocks. Fixes went into the *scripts*
  — `states.py` §7 derives its `←` notes and folds its own N+1 middle, `migration.py` folds
  column lists and wraps long errors — so a `# runnable` block is a literal paste. Added a third
  block label, `# summary of`, for the two blocks that honestly can't be.
- **Claim-by-claim review of §16–§22 found six errors.** The `-W` explanation (PEP 565: the
  flag reveals *imported-module* warnings, not all of them), `Query.where()` exists in 1.4,
  `MovedIn20Warning` **subclasses** `RemovedIn20Warning` (so `isinstance` triage over-reports),
  §19's inventory was one file, and `.scalars()` truncates *silently* with the index as a
  parameter.
- **`cascade_backrefs` — the biggest finding, and it wasn't in the chapter at all.** Under 2.0
  an object attached by the *many-to-one* side is never enrolled: no exception, the `INSERT`
  just never runs. The collection side survives. Applied to `seed.py`'s own pattern, every
  comment and assignment vanishes while the seed reports success. Confirmed on real 2.0.51.
- **New tooling.** `sweep.py` (warning inventory across every module — 1042 occurrences collapse
  to 4 distinct problems), `patterns.py` (shared case list so prediction and verification can't
  drift), `candidates.py` (classifies by which tool can see it), `verify_2_0.py` (runs the
  patterns on real 2.0 via `uv run --no-project --with`, no upgrade needed; `--stubs` emits the
  `BREAKAGES.md` skeleton).
- **`BREAKAGES.md` created: 23 entries, target was ≥10.** 22 of 24 patterns fail on 2.0.51.
  Notably one pattern (`row["col"]`) is called *safe* by both 1.4-side tools and still fails —
  the empirical argument for running the real thing.
- **Repo structure pass.** `README.md` was 0 bytes and is now the map; `pyproject.toml`
  description was still the `uv` placeholder; added the package `__init__.py` manifest; deleted
  `CLAUDE.md.bak`. Kept `PRACTICE-APP.md` and `DOCKER-STUDY.md` — checked, both current.
- **Deliberately NOT done:** the actual version bump (Viraj's call), and renaming
  `experiments/sqlalchemy_1_4_vs_2_0/` — ~180 cross-references for modest gain, and the name is
  defensible once `__init__.py` explains the contents.

### 2026-08-08
- Walked BREAKAGES.md entry-by-entry in chat. Viraj asked for more explanation *in the file*;
  first refused (fix/docs are his golden-set seed), then he explicitly permitted importing
  the explanations. Expanded BREAKAGES.md, then reshaped to the Group A–H "What 1.4 did /
  What 2.0 does" layout he said is easier to reread later. Measured 1.4 code, 2.0 errors,
  fix snippets, Also-defensible blocks, docs links, and tier lines untouched. #17 tier
  contradiction (`row["col"]` looks safe on 1.4 tools, fails on real 2.0) is in the file.
- **Verified the expansion by diffing, not by trusting it.** Regenerated the skeleton on real
  2.0.51 and compared: all 23 entry headings and every `Fix`/`Tier`/`Docs` line byte-identical;
  the 30 diverging lines are old prose the Group A–H rewrite replaced. No measured field moved.
- **Measurement-rule violation found and fixed.** `verify_2_0.py` printed the literal
  *"Six entries carry an Also defensible block"* — right by luck, typed by hand. Now derived:
  counts `patterns.ALTERNATIVES` hits among the failures plus the one hand-appended
  cascade_backrefs entry (`HAND_APPENDED_WITH_ALTERNATIVES`). Prints `6`, and 6 blocks are
  emitted. `BREAKAGES.md` header synced so the diff workflow stays clean.
- Full regression re-run: 10 modules pass on 1.4.52; 22 of 24 patterns fail on 2.0.51; no
  `FIX FAILED`. Part A committed and pushed — the Mac is the only copy until the lab is back.

### 2026-08-09 — Docker session 1 (Part C, Days 4–5)
- **Viraj wrote `Dockerfile` and `.dockerignore` himself, line by line.** Claude explained each
  instruction before he typed it and never produced the file. Collaboration rule held.
- **Base image chosen on measurement, not vibes.** First answer was `python:3.11` "because it
  has everything"; pushed back. He pulled both and measured: **1.62GB vs 214MB on disk, 416MB
  vs 48MB to download** — 7.6× / 8.7×. Then verified on PyPI that 1.4.52 ships a
  `manylinux_2_17_aarch64` cp311 wheel, so `-slim` needs no compiler. Build confirmed it:
  wheel downloaded by that exact filename, install in **4.3s**, no gcc.
- **He caught a Claude overstatement.** Highlighted `musllinux` in `uv.lock` against the claim
  that Alpine has no wheels. Checked: SQLAlchemy 1.4.52 publishes **0** musllinux wheels, but
  *greenlet* does. Real lesson is sharper than the original: **platform coverage is per-package,
  not per-project** — one holdout dependency puts you back on compile-from-source.
- **Layer cache demonstrated, not asserted.** After the source-only edit: `COPY requirements.txt`
  and `RUN pip install` both `CACHED`, `COPY . .` rebuilt. Drill question #1 answered from his
  own build output.
- **Two failures he diagnosed.** `CMD ["python","-m","app.py"]` built green three times and only
  failed at `docker run` — `CMD` is metadata, never validated at build time. And `__pycache__/`
  in `.dockerignore` silently missed nested dirs: **docker-ignore matches full paths from the
  context root, gitignore matches slash-less patterns at any depth.** Fixed with `**/__pycache__`.
- Build context **13.51MB → 1.53kB**. `.venv` (macOS `*-darwin.so`, unloadable on Linux), `.git`
  (history carries deleted secrets) and `issues.db` no longer ship. `tiers.json` kept on purpose
  — `verify_2_0.py` reads it at runtime.
- **`requirements.txt` is generated** (`uv export --no-hashes --no-emit-project -o
  requirements.txt`) and committed, because the image build needs it. Regenerate it whenever
  dependencies change or the build installs stale versions.
- **Deliberately NOT done (next session):** non-root user, `pip --no-cache-dir`, `CMD` vs
  `ENTRYPOINT`, multi-stage builds, and the hard-gate drill — a build failure Claude injects for
  him to diagnose cold. Day 6 (Compose + Postgres) after that.
