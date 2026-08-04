# sqlalchemy-upgrade-agent

A RAG system that helps developers upgrade Python code from **SQLAlchemy 1.4 → 2.0**.
Portfolio project targeting Applied AI Engineer roles (Nvidia, Meta, Google, Apple,
Anthropic, and startups).

- **`ROADMAP.md`** — the full ~4-month arc, six phases, plus a glossary of every AI term.
- **`PHASE-0.md`** — the current phase in detail.

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
- **Part 4 built out from 4 bare questions into a real chapter** (§16–§19), matching Parts
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
