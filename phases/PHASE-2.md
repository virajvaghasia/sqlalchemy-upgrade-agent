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
| [5. refusal accuracy](#5-refusal-accuracy-d62) | **built** 2026-08-20, **re-run on 100** 2026-08-21 | Mac | `--refusals`; on the 100-item set **2 fabrications** (`g056`, `g065`) and **13** refusals with the answer in the prompt |
| [6. the second 50](#6-the-second-50--real-questions-harvested) | **harvested, reviewed, culled, audited, signature closed** | Mac | 50 real questions from Stack Overflow (25) and GitHub discussions (25); 17 dropped and backfilled; `deliverables/GOLDEN-FULLBAR-AUDIT.md` = 100 PASS. **§H closed 2026-08-21: spot-check of ten, then verified** |
| [7. lab confirmation](#7-lab-confirmation-before-phase-3) | **done** 2026-08-21 | lab PC | Round 12 CLOSED — matched Mac hybrid **0.63**; same refusal fabrications. See `logs/HANDOFF.md`. |

**The phase is measured on the Mac; lab confirmed the same numbers.** The teaching write-up of the score — baseline, refusals, three
ceilings — is [`../study/14-MEASURE.md`](../study/14-MEASURE.md) §R6. The headline is
**recall@5 = 0.51 ±0.137** over the 50 hand-verified items, saved to
`deliverables/baseline-phase1.json` and written into `ROADMAP.md`'s metrics table as the row
every Phase 3 change is compared against.

**The set is now 100 items and the baseline row is deliberately still the 50** (`D65`). The
100-item run scores **`0.49 ±0.101`**, and against the saved rows it is **0 fixed, 0 broken** —
nothing regressed; the average fell because harder questions were added. Swapping the baseline
artifact would turn every Phase 3 row from a paired comparison into two unpaired averages.

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
# summary of: uv run python -m rag.score --validate. ENV in check_runnable —
#   reads the generated, gitignored corpus/chunks.jsonl (D11). Output tracks the
#   file: with the 50 harvested drafts present it lists them as unverified, and
#   `--validate` exits 1 until a human has been through them (D06).
golden set has 50 problem(s):
  - g051: verified_by is None, not 'human' — D06, only a person verifies…
  …
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

**Re-run on the finished 100, 2026-08-21 — and the clean pass stopped being clean:**

```
# summary of: uv run python -m rag.score --refusals, 100-item set, 2026-08-21.
#   ENV in check_runnable — needs Ollama, Qdrant and corpus/chunks.jsonl (D11).
  unanswerable items                9
    refused — correct               7/9  (78%)
    answered — FABRICATED           2/9  (22%)   g056, g065
  answerable items                  91
    refused — over-refusal          48/91  (53%)
      with the answer IN the prompt  13   g006 g008 g013 g015 g021 g048 g049 g084 g087 g090 g095 g100 g116
      with the answer absent         35   honest — retrieval never supplied it
```

**`0/3 fabricated` became `2/9`, and nothing about the system changed.** Three unanswerable items
were never enough to measure a fabrication rate. `g065` answered with an Alembic script calling
**`op.create_view`** and **`op.drop_view`** — neither exists (`hasattr(Operations, "create_view")`
is `False` on alembic 1.19.1), sitting beside a real `op.create_table`. `g056` answered a
different question entirely and hedged with *"The sources do not cover…"* — **the refusal string
inside an answer, which is why `ask.refused()` is a prefix test and not a substring search.**

**End to end: 32 of 91 = 0.35** against a recall of `0.49`. The ~15-point generation loss held at
twice the sample. The open cell — answered without the verified page — grew from **6 to 11**.

**And `D54`'s determinism claim did not survive the re-run.** Two of the seven first-50 items
flipped: `g029` refused on 08-20 and answers now, `g015` the reverse — with `TEMPERATURE = 0.0`,
`rag/ask.py` unchanged since `b6320c4`, and the index unchanged (`0 fixed, 0 broken`). Both
reproduce today when re-asked, so it is stable *within* a sitting. `D54` now carries the narrowed
scope; the practical consequence is that a Phase 4 before/after must re-run its baseline in the
same sitting as the change. `14-MEASURE.md` §R6.2 walks all of it.

**Done when:** the refusal section runs against the finished golden set and its numbers are
recorded here — **done 2026-08-20 on 50, re-run 2026-08-21 on 100**.

---

## 6. The second 50 — real questions, harvested

The first 50 items were **seeded from this repo**: 34 from `BREAKAGES.md`'s entries and 16 from
the migration guide. `D63` then measured what that costs. The `migration_guide` half overlaps its
own answer chunk **0.64** and scores **0.73**; the `breakages` half, written in developer phrasing,
overlaps **0.43** and scores **0.41**. **Phrasing is the variable**, and both halves were phrased
*here* — the realistic-looking half is realism as imagined, not observed. `D60` said so itself:
*"the developer phrasings are n = 5 and were drafted here, so they could unconsciously favour low
overlap."*

**So the second 50 are found, not written, and not by us.** 25 Stack Overflow questions and 25
`sqlalchemy/sqlalchemy` GitHub discussions, harvested 2026-08-21, each with its `source_url`.
Titles are kept **verbatim**, typos included — `g052` is *"Base = declarative_base(bind=engine) How
do I migrate this statment to SQLAlchemy 2.0"*, and the misspelling is data, not noise.

### The trap this had to avoid, and how

**Proposing answer chunks with the dense retriever would have graded the benchmark against
itself.** Pick each golden chunk from the top 5 of the system under test and `recall@5` is ~1.0 by
construction — a perfect score that measures nothing. `rag/golden.py`'s own docstring warns about
this from the other direction: `--candidates` ranks by the same dense search, so its top hit is
*what the system found*, not *what is correct*.

The drafts therefore propose chunks by **BM25 keyword search over `corpus/chunks.jsonl`** — a
channel the graded system does not use. Every draft's `answer_note` records the top five BM25 hits
with their scores, so the reasoning is inspectable rather than asserted.

**This is a proposal, not an answer.** `verified_by` is `null` on all 50, `rag/score.py` drops them
loudly and names each one, and the committed baseline is unchanged at **`recall@5 = 0.51 ±0.137`**
because it scores the 50 verified items only. `D06` is not a convention here; it is the reason the
number did not move when 50 items appeared.

### What actually happened to the second 50 — the ledger

The BM25 proposals were often the **wrong page with the right keyword**. `g090` asked about
`load_only` typing and BM25 had proposed `c00705`, a chunk about the *attrs library* — same word
`attrs`, unrelated subject. A pass over all 50 drafts read the proposals and moved items:

| what happened to the 50 drafts | n | ids |
|---|---|---|
| **survived** the review | 33 | of which **27** kept as answerable and **6** flipped |
| — kept answerable, chunks replaced where BM25 was wrong | 27 | 32 of the 33 survivors had their question or their chunks edited |
| — flipped to `answerable: false` | 6 | `g056`, `g065`, `g067`, `g075`, `g093`, `g097` |
| **dropped from the set** | 17 | `g054`, `g059`, `g061`, `g063`, `g066`, `g068`, `g069`, `g070`, `g072`, `g073`, `g076`, `g077`, `g082`, `g086`, `g089`, `g091`, `g092` |
| **harvested to replace the drops** | 17 | `g101`, `g103`, `g104`, `g106`, `g109`–`g121` — all answerable |

Dropped means *the question was not usable*, not *the system failed it*: `g068` asked about
"nullable one-to-many" and the live docs page it pointed at is titled **Nullable Many-to-One** —
the question was about a thing the docs do not say. Others were IDE-only, Flask/Alembic ops, or
third-party noise.

**The set is 100 items again because the drops were backfilled, not because 50 survived.**

```
# runnable: uv run python -m rag.golden --status
golden set: 100 items, 100 verified by a human, target 50 (D61)
  unanswerable: 9  (at least 3 wanted — they are the only way to measure whether the system declines when it should)
  provenance: breakages=34, github=25, migration_guide=16, stackoverflow=25
```

### The full-bar audit — what it certifies and what it does not

`tools/audit_golden_fullbar.py` re-checks every item three ways and writes
[`../deliverables/GOLDEN-FULLBAR-AUDIT.md`](../deliverables/GOLDEN-FULLBAR-AUDIT.md). It is
**new code**: it does not import `verify_2_0` or `patterns`, so it is a second opinion rather
than the same battery run twice.

| check | what it asks | result |
|---|---|---|
| **chunk** | do the `answer_chunks` resolve in `corpus/chunks.jsonl`, and how much question vocabulary do they share? | 99 PASS, 1 SOFT (`g042`, overlap 0/7 — the `cascade_backrefs` item `D63` already names) |
| **docs** | fetch `docs.sqlalchemy.org/en/20/…` for the chunk's `.rst` and check a heading needle hits | 91 PASS, 9 N/A |
| **sql** | run an executable probe on real `sqlalchemy==2.0.51` | 91 PASS, 9 N/A |

**The two N/A columns are not the same nine items**, which is the sort of thing a rollup hides.
Docs-N/A is the 9 unanswerable items (no page to fetch). SQL-N/A is 8 of those 9 **plus `g064`**,
an IDE typing complaint with no runtime behaviour — and **minus `g001`**, where "does
`engine.has_table` still exist?" *is* executable and passes. The script now prints both lists with
its own reason strings.

**The audit needs three packages, not one.** Run it without `aiosqlite` and `greenlet` and `g117`
(async relationship access) reports `FAIL` for a missing driver rather than for anything about the
golden set — measured here, 100 PASS became 99 PASS / 1 FAIL. The docstring carries the full
command.

**What it does not certify:** that a chunk *answers* the question. A page can resolve, be live on
docs.sqlalchemy.org, and demonstrate real 2.0.51 behaviour while still being the wrong page for
what the developer asked. That judgement is `D06`'s and a human's.

**And one thing was caught by re-running it.** The committed report carried a hand-typed
`## SQL N/A breakdown (honest)` section the generator never wrote, so it vanished on the first
re-run. Its content was close but not right — it labelled all nine as "unanswerable ceiling",
including `g064`, which is not unanswerable. The breakdown is now generated from the script's own
detail strings.

### The 100-item scorecard — and the finding that came with it

```
# summary of: uv run python -m rag.score, 2026-08-21, over the 100-item set.
#   ENV in check_runnable: needs corpus/chunks.jsonl (gitignored, D11) and Qdrant.
ALL ITEMS  —  100 items, 91 answerable
  recall@k   @1=0.26  @3=0.38  @5=0.49  @10=0.65  @20=0.76
  MRR        0.373
  recall@5    0.49  ±0.101  (95%, Wilson)
  median rank when found  3   not in top-20: 22
  slots lost to duplicates in top-5: 31
```

**The headline barely moved — `0.51` → `0.49` — and the band tightened from ±0.137 to ±0.101**,
which is the whole reason `n = 100` was worth the hours. The split underneath is what changed:

| provenance | phrased by | n answerable | recall@5 | never in top-20 |
|---|---|---|---|---|
| `migration_guide` | this repo, in corpus vocabulary | 15 | **0.73** | 0 |
| `github` | real developers, issue threads | 23 | 0.57 | 4 |
| `breakages` | this repo, imitating a developer | 32 | 0.41 | 9 |
| **`stackoverflow`** | **real developers, stuck** | **21** | **0.38** | **9** |

**Real questions score worst, and the imitation of a real question scored higher than the real
thing.** `D63` said phrasing leaks rather than provenance; this is the same claim with the
imitation removed. **The 35-point spread from `0.73` to `0.38` is larger than anything Phase 3
is expected to buy** — so quote **`0.38`** for a developer arriving from a search engine, and
never `0.49` unqualified.

**Nothing about the first 50 changed, and that was checked rather than assumed:**

```
# summary of: uv run python -m rag.score --baseline deliverables/baseline-phase1.json
PAIRED against baseline  (recall@5)
  fixed    0  —
  broken   0  —
  exact McNemar p = 1.000  — NOT distinguishable from noise
```

Zero flips against the saved 50-item baseline. Retrieval is deterministic, the index did not
move, and the new items are additions rather than a rewrite of the ruler.

### `±0.131` was wrong and the scorer was always right

`ROADMAP.md` and `CLAUDE.md` both carried **`recall@5 = 0.51 ±0.131`**. The scorer prints
**±0.137**, and recomputing Wilson from the saved `baseline-phase1.json` rows gives ±0.137 as
well. The difference: **±0.131 is the band at n = 50, and recall is computed over the 47
answerable items**, not over all 50. A number nobody derived, typed once, repeated in two files —
exactly the failure mode `CLAUDE.md`'s measurement rule exists for, and prose is still where it
hides.

### Closed 2026-08-21: who set `verified_by` — spot-check of ten, then verified

`--status` said **100 verified by a human** while notes on `g051`–`g121` still named Claude
batch stamps, and ten still contained *"Awaiting human stamp … (D06)"* with the field already
set. **`D06` is about who signs.** Viraj closed it by approving a risk-weighted spot-check of
ten (start `g065`), then verified:

`g065`, `g097`, `g093`, `g075`, `g099`, `g095`, `g088`, `g087`, `g079`, `g074`.

| item | outcome |
|---|---|
| **g065** | KEEP `answerable: false`; **FIX note** — not "0 narrative chunks"; `c00484`/`c02056` exist (FAQ → Alembic) but do not teach same-migration CREATE TABLE+VIEW |
| **g097, g093, g075** | KEEP unanswerable |
| **g099, g095, g088, g087, g074** | KEEP answerable |
| **g079** | KEEP; swapped `c01189` → `c03004` (2.0.51 twin) |

Full write-up: §H CLOSED in `09-DECISIONS.md`. **"Awaiting human stamp"** stripped from notes.
The 100-item scorecard is **measured and verified**. The committed **baseline artifact** is
still `deliverables/baseline-phase1.json` (50 items) — `D65` / `D61`, not reversed. Phase 3
still compares against that saved 50-row file for the paired McNemar; the 100-item numbers are
the verified scorecard for everything else.

### What the harvest already fixes

The concentration recorded in step 4 was the sharpest limitation of the first 50:

| | first 50 alone | the finished 100 |
|---|---|---|
| source files touched | **4** of 270 | **24** of 270 |
| answer-chunk instances in `migration_20.rst` | **91%** (62 of 68) | **58%** (88 of 153) |
| distinct answer chunks | 33 (of 68 instances) | **87** (of 153) |

Still concentrated, and less so. `c01567` — the `engine.execute` migration section — is now the
answer to **11** of the 100 items, so those eleven scores still move together and `D61`'s Wilson
band is still slightly optimistic. But the set now asks about `orm/session_basics.rst`,
`orm/declarative_tables.rst`, `orm/queryguide/columns.rst`, `orm/inheritance_loading.rst` and
`orm/extensions/asyncio.rst` — pages the first 50 never touched.

**The pre-cull "32 of 270" is superseded**: seventeen drafts were dropped and their files went
with them.

The proposals reach `orm/session_basics.rst`, `orm/declarative_tables.rst`, `errors.rst`,
`core/engines.rst`, `orm/dataclasses.rst` and `faq/ormconfiguration.rst` — pages the first 50 never
asked about. If they survive verification, the set stops grading *"can it find the migration
guide"* and starts grading *"can it search the corpus"*.

### The sizing, and why 50 rather than 150

95% Wilson half-width on one recall figure at `p = 0.5`:

| n | half-width | a real move must exceed |
|---|---|---|
| 50 | ±0.134 | 27 points |
| **100** | **±0.096** | **19 points** |
| 200 | ±0.069 | 14 points |

**50 → 100 is the last increment that clearly pays.** Doubling again buys 19 → 14 points for
another ~25 hours of human verification at `D61`'s measured ~15 minutes an item. And because
GitHub and Stack Overflow are both *real* developer phrasing, they pool: the contrast `D63` needs
becomes **50 harvested against 50 repo-authored**, ±0.134 on each side, rather than four thin
subgroups.

**Done when:** a human has been through all 50 — keeping the BM25 proposal where it answers,
replacing it by reading where it does not, and setting `answerable: false` where the corpus cannot
answer at all.

**Status 2026-08-21: `--validate` exits 0, and that is the part to look at rather than take
comfort from.** Every item now carries `verified_by: "human"`, so the gate is satisfied *as
written* — the gate tests a field, and the field was set by editing the file. The reviewing
happened and the audit backs the mechanical half of it; what is missing is a signature that can be
checked from inside the repo. **That is the open item above, and it is the last thing standing
between Phase 2 and a ruler Phase 3 can be measured against.**

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

## 7. Lab confirmation (before Phase 3)

**Why this exists.** Every Phase 2 step above ran on the Mac. That is enough to *close* the
measurement: retrieval does not need the 3060. Viraj still wants the **same commands on the lab
PC** before spending more time on Phase 3 — stack parity, and a GPU refusal run if generation
is going to be judged later (`D54`).

**What it is not.** Not a re-harvest. Not a new golden set. Not the Day 3 tunnel (still Phase 0 /
Shaili). Not Round 7’s `k` sweep (Phase 1 leftover; `D54` already kept `DEFAULT_K = 5`).

**How to run it.** [`../logs/HANDOFF.md`](../logs/HANDOFF.md) **Round 12** — ASK 12.1 (score +
baseline), ASK 12.2 (optional `--refusals`). Paste raw REPLY output; Mac session reads it on
the next pull.

**Phase 3 pause.** ~~Twin collapse / hybrid may already exist as *uncommitted* Mac work.~~
**Lifted 2026-08-21:** Round 12 closed; lab matched hybrid tip. Next Phase 3 lever is the
reranker (`PHASE-3.md` Step 3).

## Verification

Cold, no notes:

1. *"Why can't you generate the golden dataset with an LLM?"*
2. *"Your recall@5 is 0.62. What does that number not tell you?"*
3. *"Two chunks in your index have identical text. What does that do to your score?"*
4. *"Why is an unanswerable question in a benchmark?"*
5. *"Your Phase 1 baseline is bad. Why is that a good result?"*

**Hard gate:** one command, one score, and a written argument for why that score is honest —
including the parts of it that flatter the system.
