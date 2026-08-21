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
| [`09-DECISIONS.md`](09-DECISIONS.md) | **every design decision, what was rejected, and why** — written for interview revision. Cite entries by ID (`D19`) | — |
| [`10-RETRIEVAL.md`](10-RETRIEVAL.md) | **RAG from zero** — why we look things up instead of asking from memory (§R1); what the 1024 numbers on disk actually are (§R2). Two sittings; stop after the first | §R1–§R2 |
| [`11-GENERATION.md`](11-GENERATION.md) | what happens *after* search: the prompt as a component. Three wordings of one sentence; C fabricates, A over-refused once, B ships (§R3) | §R3– |
| [`12-EVALUATION.md`](12-EVALUATION.md) | how you find out whether any of it worked: what a script can and cannot score, and the rank measurement that split one planned fix into four different problems (§R4) | §R4– |
| [`13-VERIFICATION.md`](13-VERIFICATION.md) | **defending it out loud** — the five cold questions Phase 1 closes on, each with the plain answer, the mechanism, the measurement and the spoken version, plus the wrong answer it attracts. §R5.7 runs all five end to end for rehearsal (§R5) | §R5– |

## By phase — which file belongs to what

**File numbers are reading order. This table is phase order.** They nearly agree, and where
they do not, the difference is the point: `09` belongs to no single phase and `08` outlived the
one that produced it.

**The files do not move into per-phase folders, and will not.** A `study/phase-0/` tree would be
tidier to look at and would break **408** references to these paths across the repo's markdown,
Python and YAML — every doc cross-link, every test that reads a doc, and every `# runnable`
block that names one. The same trade was refused once before for
`experiments/sqlalchemy_1_4_vs_2_0/`. A view costs nothing; a move costs 408 edits and buys
tidiness.

### Phase 0 — Remediation: closing the gap between the résumé and reality

Deliverable: [`../deliverables/BREAKAGES.md`](../deliverables/BREAKAGES.md) — 23 verified
breakages. Plan: [`../phases/PHASE-0.md`](../phases/PHASE-0.md).

Phase 0 runs in three parts — **A** on the Mac, **B** in person at the lab, **C** remote on the
lab PC — and the study files line up with its days:

| file | § | part · day | what it was for |
|---|---|---|---|
| [`01-CONCEPTS.md`](01-CONCEPTS.md) | §0–§15 | A · Days 1–2 | the SQLAlchemy refresher — *"you cannot write good test questions about a migration you have never personally felt"* |
| [`02-MIGRATION-2.0.md`](02-MIGRATION-2.0.md) | §16–§22 | A · Days 1–2 | running 1.4 code under 2.0 and watching it break. Produced the 23 breakages |
| [`03-PRACTICE-APP.md`](03-PRACTICE-APP.md) | — | A · Days 1–2 | the app the breakages were found in, and why this schema |
| [`04-DOCKER.md`](04-DOCKER.md) | §1–§3 | C · Days 4–5 | one container — the Dockerfile written from a blank file |
| [`05-COMPOSE.md`](05-COMPOSE.md) | §4 | C · Day 6 | more than one container: *two services talking* |
| [`06-POSTGRES.md`](06-POSTGRES.md) | §5 | C · Day 6 | the database inside one of them — Postgres is the second of those two services |
| [`07-TESTS.md`](07-TESTS.md) | §6 | C · Days 8–9 | the test suite and the CI gate, from a blank file |
| [`08-LAB.md`](08-LAB.md) | — | B · Day 3, then C · Days 7 and 10 | the lab PC from scratch: the machine, then GPU-in-container, then Ollama |

**`08-LAB.md` is the one file that does not sit in a single part.** It spans Day 3 (in person,
Part B), Day 7 (GPU in a container) and Day 10 (Ollama) — because they are all *the same
machine*, and splitting a runbook by calendar would make it useless as a runbook. It also did
not stop being used when Phase 0 closed: it is the reference for the box that ran Phase 1's
eleven measurement rounds, and will be for Phase 3's. **Phase ownership here means which phase
produced a file, not when it stops mattering.**

### Phase 1 — A deliberately dumb RAG

Deliverable: [`../deliverables/FAILURES.md`](../deliverables/FAILURES.md) — 19 questions with
human verdicts. Plan: [`../phases/PHASE-1.md`](../phases/PHASE-1.md).

| file | § | what it was for |
|---|---|---|
| [`10-RETRIEVAL.md`](10-RETRIEVAL.md) | §R1–§R2 | why look things up at all; the corpus, chunking, and what the 1024 numbers on disk are |
| [`11-GENERATION.md`](11-GENERATION.md) | §R3 | what the model does with what it was handed — the prompt as a component |
| [`12-EVALUATION.md`](12-EVALUATION.md) | §R4 | how you find out whether any of it worked |
| [`13-VERIFICATION.md`](13-VERIFICATION.md) | §R5 | defending the result out loud, cold — the phase's five closing questions |

### Every phase — the register

| file | § | what it is |
|---|---|---|
| [`09-DECISIONS.md`](09-DECISIONS.md) | — | `D01`…`D63`. Phase 0, 1 and 2 decisions in one register, because a decision is cited from wherever it is relevant and would go stale the moment it was filed under the phase that happened to make it |

### Phases 2–6

**No study files yet, and that is the honest state rather than an omission.** Phase 2 is
measurement, Phase 3 is hybrid search and reranking, Phase 4 judges answers, Phase 5 is the
agent and MCP, Phase 6 is production polish — see [`../phases/ROADMAP.md`](../phases/ROADMAP.md)
§6. Teaching material is written *after* the thing it teaches has been measured here, never
ahead of it, which is why `12-EVALUATION.md` could not have been written before the 19 verdicts
existed.

## Three numbering families, and why

**File numbers are reading order. Section numbers are subject continuity.** They are different
things and they do not line up — deliberately.

- **`01`–`02` share one § run, `§0`–`§22`.** `02` continues where `01` stops, because they are
  one long argument about SQLAlchemy split at the point it got too long to scroll. A reference
  to "§18" is unambiguous across the pair.
- **`04`–`07` share a second run, `§1`–`§6`**, for the same reason: `05` continues `04`,
  `06` continues `05`. One container, then several, then the database in one, then the tests.
- **`10`–`13` share a third run, `§R1`–, for the RAG system.** The `R` prefix is not decoration:
  without it, `§1` would mean Docker in one family and RAG in another. A letter makes a collision
  impossible rather than merely unlikely. `11` continues `10`, `12` continues `11` and `13`
  continues `12` — §R1–§R2 are retrieval, §R3 is generation, §R4 is evaluation, and §R5 is
  defending the result under questioning.

  **The `R` is for RAG, not for Retrieval**, and the distinction only became visible when §R3
  moved into `11`. A subject-labelled prefix would have forced `§G1` there and a fourth family on
  the reader; a system-labelled one lets the run continue, which is what the splitting rule above
  requires. Where a prefix has to mean something, make it mean the *thing the files are about*
  rather than the topic of the first file that happened to use it.
- **`03`, `08` and `09` have no sections.** They are not chapters. `03` is the practice-app
  runbook; `08` is the lab PC sitting (Phase 0 Day 3 → Day 10); `09` is a **register** whose
  entries carry stable IDs (`D01`…) so they stay citable when the file is reordered.

So `§4.1` means Compose networking, `§18` means the Result API and `§R1` means why retrieval
exists — none of them ambiguous.
What you cannot do is assume `§5` belongs to the file numbered `05` — check the table above.

Splitting only happens when a file has grown to cover two genuinely different subjects, and the
numbering always continues across the split so existing references keep resolving.

**Worked example — why `§R2` did not get its own file.** It is the obvious candidate, and the
answer is no. §R1 and §R2 are one subject at two depths, not two subjects: §R1.3 defers to
*"§R2 takes all of this apart properly"*, §R1.5 introduces cosine similarity and says to ask §R2
for the mechanism, and §R2.6 reaches back to correct a claim §R1 made. Splitting turns each of
those into a file-hop. Size is not the trigger either — at the time of asking, `10` was shorter
than **both** halves of the pair that *was* split.

**Where the seam was — and this one has now happened.** §R1 and §R2 are both *retrieval* — corpus,
chunks, vectors, search. §R3 is the prompt: what the model does with what it was handed. That is
*generation*, a different subject, so it went into `11-GENERATION.md` with the numbering
continuing unchanged. Both tests agreed by then: a genuinely different subject, and `10` had grown
past `02-MIGRATION-2.0.md` while §R3 was still unwritten.

Note what the split does **not** do. `11` starts small — far shorter than `10` — and that is
fine, because a file is a container for a subject rather than a quota to fill. The alternative was
appending a second subject to a file that already covered one, which is the thing the rule
forbids.

## Where the rest of the repo lives

| | |
|---|---|
| [`../README.md`](../README.md) | the front door and the map — its **Start here** table says which of these files to open for which question |
| [`../phases/ROADMAP.md`](../phases/ROADMAP.md) | the six-phase arc, plus a glossary of every AI term |
| [`../phases/PHASE-2.md`](../phases/PHASE-2.md) | **the current phase** — a hand-verified golden set and one command that prints a score |
| [`../phases/PHASE-1.md`](../phases/PHASE-1.md) | complete 2026-08-18 — a deliberately dumb RAG, its five steps, and the four constraints it hands Phase 2 |
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
