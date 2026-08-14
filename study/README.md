# Study notes — index

The teaching material for [`sqlalchemy-upgrade-agent`](../README.md). Read in file order; the
number prefix *is* the reading order.

Every number in these files was measured against this repo, and the command that produces it is
given, so any claim can be checked rather than believed. Where a claim turned out to be wrong
when measured, the correction is kept rather than quietly edited out.

| file | what it covers | sections |
|---|---|---|
| [`01-CONCEPTS.md`](01-CONCEPTS.md) | the relational model, the ORM layer, the session at runtime | §0–§15 |
| [`02-MIGRATION-2.0.md`](02-MIGRATION-2.0.md) | the 1.4 → 2.0 upgrade: what breaks, what only looks like it does | §16–§22 |
| [`03-PRACTICE-APP.md`](03-PRACTICE-APP.md) | the app under test — why this schema, and the ten-step runbook | — |
| [`04-DOCKER.md`](04-DOCKER.md) | one container: images, layers, the build cache, the Dockerfile | §1–§3 |
| [`05-COMPOSE.md`](05-COMPOSE.md) | several containers: networking, volumes, healthchecks | §4 |
| [`06-POSTGRES.md`](06-POSTGRES.md) | the database inside one of them | §5 |
| [`07-TESTS.md`](07-TESTS.md) | the test suite, and how to tell whether tests cover anything | §6 |
| [`08-LAB.md`](08-LAB.md) | lab PC from scratch: SSH, Tailscale, clone, Docker Engine, GPU, Ollama. Includes the 2026-08-13 sitting diary in Ubuntu words | — |

## Two numbering families, and why

**File numbers are reading order. Section numbers are subject continuity.** They are different
things and they do not line up — deliberately.

- **`01`–`02` share one § run, `§0`–`§22`.** `02` continues where `01` stops, because they are
  one long argument about SQLAlchemy split at the point it got too long to scroll. A reference
  to "§18" is unambiguous across the pair.
- **`04`–`07` share a second run, `§1`–`§6`**, for the same reason: `05` continues `04`,
  `06` continues `05`. One container, then several, then the database in one, then the tests.
- **`03` and `08` have no sections.** They are runbooks, not references. `03` is the practice
  app; `08` is the lab PC sitting (Phase 0 Day 3 → Day 10).

So `§4.1` means Compose networking and `§18` means the Result API, and neither is ambiguous.
What you cannot do is assume `§5` belongs to the file numbered `05` — check the table above.

Splitting only happens when a file has grown to cover two genuinely different subjects, and the
numbering always continues across the split so existing references keep resolving.

## Where the rest of the repo lives

| | |
|---|---|
| [`../README.md`](../README.md) | the front door and the map — its **Start here** table says which of these files to open for which question |
| [`../phases/ROADMAP.md`](../phases/ROADMAP.md) | the six-phase arc, plus a glossary of every AI term |
| [`../phases/PHASE-1.md`](../phases/PHASE-1.md) | **the current phase** — a deliberately dumb RAG, its five steps, and the decisions already settled |
| [`../phases/PHASE-0.md`](../phases/PHASE-0.md) | the phase before: complete except its Day 3 tunnel, with its gates and deliverables |
| [`../deliverables/BREAKAGES.md`](../deliverables/BREAKAGES.md) | **the Phase 0 deliverable** — 23 verified breakages |
| [`../logs/LEARNING-LOG.md`](../logs/LEARNING-LOG.md) | the dated timeline |

## What is not in here yet

Phase 1 builds the retrieval system in `../rag/`, and its reasoning lives in
[`../phases/PHASE-1.md`](../phases/PHASE-1.md) rather than in a numbered study file — the plan
and the explanation are the same document while a step is still being built. If a subject here
grows past what a phase file should carry, it becomes `09-…` and gets a row above.

## How to read a code block

| label | means |
|---|---|
| `# runnable:` | the command is given and its output is pasted **verbatim** — no hand-editing |
| `# summary of` | honestly cannot be verbatim; the command is still named |
| no label | illustration, not output from a run |
