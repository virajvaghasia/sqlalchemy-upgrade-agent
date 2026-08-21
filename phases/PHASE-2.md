# Phase 2 — Measure it (~2 weeks) · **CROWN JEWEL #1**

The current phase. [`ROADMAP.md`](ROADMAP.md) §6 defines it; this file plans it.
[`PHASE-1.md`](PHASE-1.md) is the phase before, complete as of 2026-08-18.

## Where this phase is

| step | state | machine | what exists |
|---|---|---|---|
| [1. decide what a question is](#1-decide-what-a-question-is) | **done** 2026-08-18 | Mac | `deliverables/golden.json` — schema, README, the item shape |
| [2. harvest the questions](#2-harvest-the-questions) | **done** 2026-08-20 | Mac | 50 items: 47 answerable, 3 unanswerable; `breakages` 34, `migration_guide` 16 |
| [3. record the answer chunk](#3-record-which-chunk-holds-the-answer) | **done** 2026-08-20 | Mac | 68 answer-chunk ids, all resolving; every item human-verified (`D06`) |
| [4. score it](#4-score-it-with-one-command) | **done** 2026-08-20 | Mac | `rag/score.py`, 25 tests, six mutations checked; baseline row filled |
| [5. refusal accuracy](#5-refusal-accuracy-d62) | **built** 2026-08-20 | Mac | `--refusals`, the one section that needs generation |

**The phase is measured.** The headline is **recall@5 = 0.51 ±0.131** over the 50 hand-verified
items, saved to `deliverables/baseline-phase1.json` and written into `ROADMAP.md`'s metrics
table as the row every Phase 3 change is compared against.

**Read it with `D63`.** That 0.51 averages two subsets that behave very differently —
`migration_guide` at **0.73** and `breakages` at **0.41** — and `D63` records that `D60` had the
label backwards about which of them leaks. **0.41 is the honest number** for a developer typing
an error message.

| | decision | settled |
|---|---|---|
| `P2-a` | a duplicate under the other version counts as a hit | `D58` |
| `P2-b` | retrieve top-20 once; report `recall@1/3/5/10/20` | `D59` |
| `P2-c` | the 19 probe questions join as a labelled subset | `D60`, corrected by `D63` |
| `P2-d` | 50 items, and Phase 3 reports which items flipped | `D61` |
| `P2-e` | refusal accuracy is in Phase 2, printed separately | `D62` |

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

**Settled 2026-08-18 as `D58`, before any score existed — which is the only honest time to settle
it.** Either copy counts as a hit. The reason is mechanical rather than philosophical:

`rag/embed.py` prepends the heading path before embedding, so **`(heading_path, text)` is exactly
the unit that decides a vector.** Grouped that way, **437 pairs share both** — and their vectors
are **byte-identical, 437 of 437 checked.** Identical vectors score identically against every
possible query, so the two copies **always occupy adjacent slots or neither**. No ranker can
prefer the right one. A metric that penalises the ranker for that is scoring the corpus.

A second group behaves differently and is deliberately not lumped in: **31 pairs share a text but
sit under different headings**, and **0 of 31** have identical vectors — cosines go as low as
`0.964`. Those are ordinary near-neighbours.

Two numbers ship beside the headline so nothing is hidden: **version-strict recall**, and
**`slots_lost_to_duplicates`** as a figure in its own right rather than a gap to be inferred.
`probe.py` measured **2 of 19** questions losing a slot this way — a real tax, and a small one.

And the escape hatch that keeps `D10` intact: an item marked **`version_sensitive: true`** is
always scored strictly, because for some questions the version *is* the answer, and the permissive
default would otherwise excuse the exact failure the skew was kept to study.

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
- **`version_sensitive`** (default `false`) — set it when the *version* is part of the right
  answer. Those items are scored version-strict regardless of `D58`'s permissive default.
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

**`rag/golden.py` is the bench for this**, built 2026-08-19:

```
uv run python -m rag.golden --status                  # how many verified, what each still needs
uv run python -m rag.golden --add "question text"     # append a draft, never verified
uv run python -m rag.golden --candidates "question"   # top-10 chunks with ids AND offsets
uv run python -m rag.golden --show c01542             # the chunk in full, and the file:line to open
```

`--show` prints the exact line to open, e.g. `corpus/raw/2.0.51/changelog/migration_20.rst +40`,
which is the clerical half of the 15 minutes. **`--candidates` ranks with the same dense search
the system under test uses**, so the top hit is *what the system found*, not *what is correct* —
and on a developer-phrased question the right chunk may not be listed at all. When that happens,
record the chunk you found by reading: that item is now evidence of a retrieval failure (`D60`).

Two more tools already exist and should be used rather than rebuilt:

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

**`P2-a` is settled — `D58`.** Either half of a duplicate pair counts as a hit, because the 437
same-heading pairs have **byte-identical vectors** and therefore an identical score to every
possible query: no ranker can prefer the right copy, so a metric that penalises it is scoring the
corpus rather than retrieval. Version-strict recall ships beside it, and
**`slots_lost_to_duplicates`** ships as its own number rather than as a gap to be inferred —
`probe.py` measured 2 of 19 questions losing a slot. Items marked `version_sensitive: true` are
always scored strictly, so `D10`'s skew questions are not quietly excused.

**The scorer reads `corpus/chunks.jsonl`, never `deliverables/FAILURES.md`.** That file truncates
each shown chunk at 700 characters and carries no chunk ids; measuring duplicates off it returns
6 of 19 instead of 2. A rendered report is not the data.

### Built 2026-08-18, run for real 2026-08-20 — `rag/score.py`

```
# runnable: uv run python -m rag.score --validate
golden set OK: 50 items, 3 unanswerable
```

**The validator runs before any number is printed**, because the golden set is the ruler and a
bent ruler does not announce itself — it produces plausible numbers wrong in the same direction
every time. It catches: a missing field, a duplicate id, an unknown provenance, an
`answer_chunks` naming a chunk id that is not in the index (which would score 0 forever and look
like a retrieval failure), an answerable item with no note, and **any item a human has not
verified**.

**What it does not check, and what was therefore checked by hand** when the set was finished:
duplicate *questions* (as opposed to duplicate ids), empty chunk text behind a valid id, and how
concentrated the answers are. The last one found something worth stating: **62 of the 68 answer
chunks are in `changelog/migration_20.rst`, and the set touches 4 of the 270 corpus files.** The
set grades *finding the migration guide* more than it grades *searching the corpus*. That is a
fair description of the product's job, but it bounds what a recall number here means.

**One consequence for `D61`'s arithmetic, stated rather than buried.** There are 68 answer chunks
but only **33 distinct** ones — `c01567` is the answer to seven different items. Those seven
scores rise and fall together, so the effective sample is smaller than 50 and the **±0.131**
interval `D61` computed is optimistic. It is still the right order of magnitude, and the paired
comparison `D61` actually relies on is unaffected, because that compares item to item.

**`--baseline` does the paired comparison** `D61` requires: which items were fixed, which broke,
and the exact McNemar p-value — rather than two recall percentages whose intervals overlap. The
Phase 1 run is saved at `deliverables/baseline-phase1.json`.

**Done when:** one command prints a score, and that score is committed as the Phase 1 baseline
row of `ROADMAP.md`'s metrics table — **done 2026-08-20**, and the three Phase 3 levers it names
are in that table too: 9 items absent from the top 20, 20 top-5 slots lost to duplicates, and a
median rank of 2.5 when search works at all.

---

## 5. Refusal accuracy (`D62`)

`--refusals` is the one section of the scorer that needs **generation**. Everything else is
retrieval — set membership, decidable by a script with no model running. A refusal only exists
once something has been asked to answer.

```
uv run python -m rag.score --refusals
```

**It is printed apart from recall and never averaged into it**, which is the whole of `D62`. A
combined "accuracy" would count correct refusals and correct answers in the same numerator, so
**the score would rise as the system became more cautious** — a metric that rewards saying
nothing. The two columns are supposed to move in opposite directions.

**It retrieves at `DEFAULT_K = 5`, not at the `DEPTH = 20` everything else uses.** Depth is free
for recall (`D59`), but refusal is a property of *what ships*, and `D54` measured that k=10 buys
two over-fires and a fabrication. Scoring refusals at 20 would report the behaviour of a system
nobody is running. A test pins the difference.

**The split that makes the section worth printing.** An over-refusal — declining an answerable
question — is two unrelated defects wearing the same word, and only one of them is generation's
fault:

| | the model refused | what it means |
|---|---|---|
| answer chunk **was** in the prompt | it had what it needed and declined anyway | **generation defect** — the Q18/Q19 class, Phase 4 |
| answer chunk **was not** in the prompt | it declined because nothing relevant was there | **honest** — retrieval's failure, Phase 3 |

Phase 1 left exactly this unsolved: Q18 and Q19 refuse at k=10 with their chunks in the prompt —
Q19 has three, at positions 6, 7 and 8 — across all four prompt wordings. Without the split, both
rows read as one number and the Phase 3 / Phase 4 boundary disappears.

**One detector, and it lives beside the prompt clause that demands it.** `ask.refused()` is a
**prefix** test against `ask.REFUSAL_OPENING`, the exact sentence `SYSTEM` asks the model to open
with. `rag/probe.py` calls the same function. Two copies of that string was the alternative, and
it is how the two would eventually disagree about the same run. A test asserts the string is
still inside `SYSTEM`, so rewording the prompt without updating the detector fails loudly instead
of silently reporting every real refusal as an answer.

It is a **prefix** test rather than a substring search on purpose: prompt D deliberately produces
*"here is the part the sources cover, and here is the part they do not"*. That is an **answer**.
A substring test would count it as a refusal and inflate refusal accuracy in the flattering
direction.

**Run 2026-08-20, against the finished set:**

```
# summary of: uv run python -m rag.score --refusals. ENV in check_runnable —
#   needs Ollama, Qdrant and the generated corpus/chunks.jsonl (D11).
  unanswerable items                3
    refused — correct               3/3  (100%)
    answered — FABRICATED           0/3  (0%)
  answerable items                  47
    refused — over-refusal          24/47  (51%)
      with the answer IN the prompt   7   g006, g008, g013, g021, g029, g048, g049
      with the answer absent         17   honest — retrieval never supplied it
```

**The unanswerable items pass cleanly** — 3 of 3 declined, nothing invented, `has_table` included.

**And the split immediately paid for itself.** Phase 1 knew the "refuses with the answer in the
prompt" defect as **two** questions, Q18 and Q19. On the golden set it is **seven**, all confirmed
against the separate retrieval run to have had their answer chunk at rank ≤ 5. Two questions is an
anecdote that invites *"your prompt is slightly off"*; seven items harvested independently of the
prompt work is a measured property of the generation step.

**The figure that is in neither table.** Of the 24 answerable questions whose answer *was*
retrieved, 7 were refused — so the system answered with the right page in front of it on
**17 of 47 = 0.36**, against a recall@5 of **0.51**. **Retrieval's number is a ceiling that
generation loses another 15 points of.** That is the whole argument for `D62`: fold refusals into
recall and this disappears, because from retrieval's side those 7 are successes.

**Open, and named rather than averaged away:** 6 items answered *without* the verified page in the
prompt. They may be right from an adjacent page, partial, or invented — no retrieval metric and no
refusal count can tell, and deciding it means a human reading six answers against real 2.0.51.
That is Phase 4's job (`D06`).

**Done when:** the refusal section runs against the finished golden set and its numbers are
recorded here — **done 2026-08-20**.

---

## Decisions to make before writing code

**All five were settled on 2026-08-18, before any score existed** — which is the only honest
time, because a metric chosen after seeing the numbers is the flattering one.

| | decision | why it cannot be deferred |
|---|---|---|
| ~~**P2-a**~~ | ~~duplicate-pair counting~~ — **settled 2026-08-18, `D58`.** Either half counts as a hit; version-strict and `slots_lost_to_duplicates` reported beside it; `version_sensitive` items always scored strictly | the 437 same-heading pairs have **byte-identical vectors**, so no ranker can prefer one — punishing it measures the corpus, not retrieval |
| ~~**P2-b**~~ | ~~`k` for `recall@k`~~ — **`D59`: neither. Retrieve top-20 once and report the whole curve** | depth is free — latency is the ~88 ms query embedding and is identical at `k=5` and `k=50`, so a small `k` buys nothing and discards the rank |
| ~~**P2-c**~~ | ~~whether the 19 probe questions enter~~ — **`D60`: yes, labelled, and every score reported with and without them** | overlap with their own top-1 chunk is **0.57** against **0.33** for developer phrasing — and rewording one question moved its answer chunk from **rank 1 to outside the top 20** |
| ~~**P2-d**~~ | ~~30 or 50~~ — **`D61`: 50, and Phase 3 reports flipped items, not a recall delta** | at n=50 the 95% interval on one recall figure is **±0.131**, so a real ten-point gain is invisible. Paired, the bar is ~**6 clean fixes with no regressions** |
| ~~**P2-e**~~ | ~~does refusal accuracy belong in Phase 2~~ — **`D62`: yes, printed separately** | unanswerable items score `recall = 0` by construction; the only thing they can test needs generation, and 50 generations is ~7 minutes |

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
