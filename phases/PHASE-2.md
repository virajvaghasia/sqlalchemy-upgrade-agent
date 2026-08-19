# Phase 2 — Measure it (~2 weeks) · **CROWN JEWEL #1**

The current phase. [`ROADMAP.md`](ROADMAP.md) §6 defines it; this file plans it.
[`PHASE-1.md`](PHASE-1.md) is the phase before, complete as of 2026-08-18.

## Where this phase is

| step | state | machine | what exists |
|---|---|---|---|
| [1. decide what a question is](#1-decide-what-a-question-is) | **planned** | Mac | this file |
| [2. harvest the questions](#2-harvest-the-questions) | not started | — | `deliverables/BREAKAGES.md` is the seed |
| [3. record the answer chunk](#3-record-which-chunk-holds-the-answer) | not started | — | — |
| [4. score it](#4-score-it-with-one-command) | not started | — | — |

**Nothing here is built yet.** This file is the plan, written the day Phase 1 closed, while what
Phase 1 measured is still exact rather than remembered.

## What this phase is, in one sentence

**Turn *"it seems okay"* into a number**, using questions whose right answers a human confirmed,
so that every later change — hybrid search, a reranker, better chunking — can be shown to have
helped rather than argued to have helped.

**What it is not.** It is not making the system better. Nothing in Phase 2 changes retrieval,
the prompt, the chunker or the model. If the score comes back bad, that is the deliverable
working. `ROADMAP.md` says it plainly: *"That score will probably be bad. That's the point."*

---

## What Phase 1 hands this phase

Four results, and each one constrains the design rather than merely informing it.

### The 19 probe questions cannot be the golden set

`deliverables/FAILURES.md` holds 19 questions with human verdicts — **10 correct, 3 partial,
6 wrong**, closed 2026-08-17. They look like a ready-made benchmark. They are not, for one
reason: **they were written from `BREAKAGES.md`'s own keys**, which means they use the
vocabulary of the thing being searched for.

That is the leakage `ROADMAP.md` warns about, arriving from a direction the warning did not
name. The warning is about questions written *from the chunks*. These were written from the
*breakages* — closer to real, still not real. A developer hitting this migration does not type
`Query.from_self`; they type *"why does my session.query thing not work anymore??"*

**They are still useful, as a labelled subset with a known property.** Keep them, mark their
provenance in the data, and report scores with and without them. A benchmark whose items have
different provenance is fine; a benchmark that hides it is not.

### `has_table` must be in the golden set, and it must be unanswerable

`ROADMAP.md` asks for *"a few unanswerable questions, where the correct behavior is for the
system to say I don't know."* Phase 1 found one and proved it structurally rather than by
observation: **`has_table` appears in zero of the 3284 chunks**, because SQLAlchemy generates
its API reference from docstrings at Sphinx build time and it is not in the `.rst` source
(`D07`, `D50`).

That makes it the best unanswerable item available — the correct answer is *"I don't know"*,
and the reason is checkable with `grep` rather than a judgement.

### Cross-version duplicates break `recall@k` unless the metric says what it counts

This is the sharp one, and it has to be settled before any number is printed.

**874 of the 3284 chunks are one half of a cross-version duplicate pair** (`D38`) — the same
paragraph embedded twice, once under `1.4.52` and once under `2.0.51`, because much of
SQLAlchemy's prose did not change between releases. `errors.rst` alone holds 27 such pairs.

So when the golden set says *"chunk `c00403` holds the answer"* and search returns `c01965` —
**byte-identical text, different version tag** — is that a hit or a miss?

| answer | consequence |
|---|---|
| **hit** — either copy counts | `recall@k` measures *did we find the text*. Honest, and blind to a real failure: answering a 2.0 question from a 1.4 page is the thing `D10` kept version skew in the corpus to study |
| **miss** — only the tagged copy counts | punishes the system for a duplicate it did not create, and the score moves when the corpus is deduplicated, not when retrieval improves |

**Neither is wrong; picking silently is.** The plan below records both and reports the pair,
because the gap between them *is* a measurement of how much duplication is costing.

### The rank of the first correct chunk is worth more than recall

Phase 1's most useful evaluation finding was not a score. It was that `recall@5` said *five
questions failed* and the **rank** said they failed in four different ways — rank 6, ranks 8 and
12, rank 23, and not-present (§R4.3). Recall alone would have sent all five to hybrid search;
one of them needed an integer.

So the scorer records **rank of the first containing chunk** from the start, not as a later
addition.

---

## 1. Decide what a question is

Before harvesting anything, the shape of one item has to be fixed, because 30–50 of them get
written by hand and reshaping later means redoing that work.

**Proposed shape**, one JSON object per question, in `deliverables/golden.json` — a separate
committed file for the same reason `verdicts.json` is one: **`probe.py` used to hardcode
`UNVERIFIED` and a regeneration silently destroyed human work.** Hand-written data does not live
in a generated file.

```
{
  "id": "g007",
  "question": "why does my session.query thing not work anymore??",
  "provenance": "github",          // github | stackoverflow | migration_guide | breakages
  "source_url": "https://github.com/sqlalchemy/sqlalchemy/issues/…",
  "answerable": true,
  "answer_chunks": ["c01296"],     // ids that genuinely contain the answer
  "answer_note": "the 2.0 tutorial section on select(); confirmed by reading it",
  "verified_by": "human",
  "verified_on": "2026-08-…"
}
```

**Every field earns its place:**

- **`provenance`** — so the score can be reported per source. If the `breakages`-derived items
  score far higher than the `github` ones, that gap is the leakage measurement, and it is
  invisible without this field.
- **`answerable`** — the unanswerable items are not failures to be filtered out; they are the
  only way to measure whether the system says *"I don't know"* when it should. `has_table` is
  the first.
- **`answer_chunks` is a list** — more than one chunk can legitimately hold the answer, and with
  874 duplicate halves in the index, sometimes both members of a pair do.
- **`answer_note`** — the sentence a human wrote after opening the file. Without it, a year from
  now nobody can tell a verified item from a guessed one.

**Done when:** the shape is written down here and one item exists as a worked example.

## 2. Harvest the questions

**30–50 items, harvested rather than invented** (`ROADMAP.md`, `D06`). Sources in the order they
are worth using:

| source | why | rough share |
|---|---|---|
| **`deliverables/BREAKAGES.md`** | 23 entries, already verified against real 2.0.51, each with the 1.4 code and the real error | seed only — mark provenance and expect them to score high |
| **real GitHub issues** | the actual words developers use when stuck | the most valuable and the slowest |
| **Stack Overflow** | same, plus the question is usually already phrased badly, which is the point | |
| **the migration guide** | enumerates what broke, so coverage gaps are visible | fills holes |

**The rule that makes this expensive and worth it:** a question must be *found*, not written.
The moment an item is phrased using the corpus's own words, it stops measuring retrieval and
starts measuring string matching.

**Done when:** 30–50 items in `golden.json`, each with a `source_url` that resolves, and at least
three `answerable: false`.

## 3. Record which chunk holds the answer

For each question, open the corpus and find the chunk that genuinely answers it. **This is the
part no script does** (`D06`), and it is roughly 15 minutes an item.

Two tools already exist and should be used rather than rebuilt:

- `uv run python -m rag.chunk --sample N` prints chunks with `source_path`, `heading_path` and
  `char_start`/`char_end`, so the original `.rst` can be opened at the exact offset.
- `rag.probe`'s signal machinery already separates *"the symbol is in the corpus and search
  missed it"* from *"the symbol is in no chunk at all"* (`D45`).

**Done when:** every `answerable: true` item names at least one chunk id that a human opened and
read.

## 4. Score it, with one command

`uv run python -m rag.score` prints, for the whole set and per provenance:

| metric | what it answers | what it is blind to |
|---|---|---|
| **recall@k** | was a correct chunk anywhere in the top k | *where* — rank 1 and rank 5 score the same |
| **MRR** | how high the first correct chunk landed, as `1 ÷ rank` averaged | whether the answer built from it was any good |
| **rank of first hit** | how far off a miss was — the Phase 1 finding | nothing about the other slots |
| **refusal accuracy** | on `answerable: false` items, did it correctly decline | nothing about answerable ones |

Reported **twice** where duplicates matter: once counting either half of a cross-version pair as
a hit, once counting only the tagged half. The difference is the cost of `D38`.

**Done when:** one command prints a score, and that score is committed as the Phase 1 baseline
row of `ROADMAP.md`'s metrics table — the row every Phase 3 change is measured against.

---

## Decisions to make before writing code

| | decision | why it cannot be deferred |
|---|---|---|
| **P2-a** | duplicate-pair counting: either-half, tagged-only, or both reported | changes every recall number; deciding after seeing the scores is choosing the flattering one |
| **P2-b** | `k` for `recall@k` — 5 to match `DEFAULT_K`, or 10 to see near-misses | 5 measures what ships; 10 measures what a reranker could reach. Probably both |
| **P2-c** | whether the 19 probe questions enter the set at all | they are labelled and free, and they are the leakiest items available |
| **P2-d** | target size: 30 or 50 | 15 min an item means 7.5 vs 12.5 hours, and a small honest set beats a large padded one |

Each gets an entry in [`../study/09-DECISIONS.md`](../study/09-DECISIONS.md) when settled, with
what was rejected.

## Verification

Cold, no notes:

1. *"Why can't you generate the golden dataset with an LLM?"*
2. *"Your recall@5 is 0.62. What does that number not tell you?"*
3. *"Two chunks in your index have identical text. What does that do to your score?"*
4. *"Why is an unanswerable question in a benchmark?"*
5. *"Your Phase 1 baseline is bad. Why is that a good result?"*

**Hard gate:** one command, one score, and a written argument for why that score is honest —
including the parts of it that flatter the system.
