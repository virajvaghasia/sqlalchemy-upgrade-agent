# Verification — study notes

Part of [`sqlalchemy-upgrade-agent`](../README.md). **§R5**, continuing the `R` run that
[`10-RETRIEVAL.md`](10-RETRIEVAL.md) starts at §R1, [`11-GENERATION.md`](11-GENERATION.md)
carries at §R3 and [`12-EVALUATION.md`](12-EVALUATION.md) carries at §R4. The `R` is for RAG,
not Retrieval (`09-DECISIONS.md` **D47**).

**Why this is a fourth file.** §R1–§R2 build retrieval, §R3 builds generation, §R4 measures both.
**§R5 is none of those: it is defending the result out loud, without notes.** That is a different
skill from building it, it fails in its own characteristic way, and — unlike the other three —
it spans every subject at once. There is no single file the five answers belong beside, which is
the only reason this is a new file rather than five paragraphs added to the other three.
Phase 2's measured scorecard continues afterwards in [`14-MEASURE.md`](14-MEASURE.md) §R6 —
that is not Sitting 6 of Phase 1.

> **Sitting 5 is §R5.** It assumes §R1–§R4 have landed. Every number here is measured against
> this repo and carries the command that produces it. Where a measurement in this file was wrong
> on the first attempt, the wrong version is kept next to the right one — that is the house rule
> and this file is not exempt from it.

---

## §R5 — The five questions, and what a good answer to each contains

### R5.0 What these questions are

[`../phases/PHASE-1.md`](../phases/PHASE-1.md) closes with five questions to be answered **cold,
from memory, with no notes**. They are the phase's last gate. They are not a quiz about
terminology — every one of them asks about a **decision or a defect in this specific system**,
and none can be answered from a general understanding of RAG.

Think of them as five interview questions about *your* build, not five definitions. An
interviewer who has never opened this repo can still ask *"why dense-only?"* — and the answer
that survives is not *"because RAG tutorials start that way."* It is the rank table, the
`DEFAULT_K = 5` constant, and what would have been mis-credited if hybrid search had gone in
first.

| | question | what it is really testing | the last clause that must land |
|---|---|---|---|
| **Q1** | Why is your retrieval bad on purpose? | whether the simplicity was chosen or merely reached | *on purpose* |
| **Q2** | What is in your corpus and what did you leave out? | whether the exclusions have reasons | *and what did you leave out* |
| **Q3** | Your chunker split a code block. Why does that matter more than it sounds? | whether you know how this system fails *silently* | *more than it sounds* |
| **Q4** | Dense retrieval missed a question containing an exact symbol name. Why? | whether you know the mechanism, not the fix | *why* (meaning ≠ string) |
| **Q5** | How do you know the answer came from the sources and was not invented? | whether you know what the system *cannot* prove | *and was not invented* |

#### The shape of a good answer

Each section below is written in the same four parts, because that is the order the answer has
to be *built* even though only the last part gets said out loud:

1. **In plain words** — the version with no jargon in it. If this part cannot be written, the
   idea is not understood yet, and every technical sentence after it will be recital.
2. **The mechanism** — what is actually happening, in the system's own terms. Prefer a picture
   or a named example (`c00233`, `DEFAULT_K`, question 7) over a definition of a word.
3. **The evidence** — the measurement from this repo that makes the claim checkable rather than
   plausible. This is the part almost no candidate has.
4. **Say this** — the sixty-second spoken answer, which is parts 1–3 compressed.

And two guards, because a wrong answer is usually not empty — it is a nearby right-sounding
thing. **These are not footnotes.** They are as load-bearing as *Say this*:

- **Do not say** — the specific wrong answer these questions attract, why it dies, and the
  named counterexample that kills it (`backref` at rank 6 for scarcity; Q1 vs Q2 verdicts for
  “because it has citations”).
- **The follow-up** — the one question an interviewer asks next, plus the second jab that often
  comes after. A weak answer cannot survive either.

**How to use this file.** Read plain words → mechanism → evidence until *Say this* feels like
something you could invent again. Read *Do not say* until you can hear yourself almost saying
the wrong line and stop. Then close the file and sit the five cold. Reading it *during* a
sitting converts the gate into recognition, which measures nothing — see the closing section.

#### The failure mode these five questions are built to catch

**Answering the setup instead of the question.** Every one of the five has its real content in
its *final clause* — *on purpose*, *and what did you leave out*, *more than it sounds*, *why*,
*and was not invented*. It is possible to say something true and relevant about the first half
of each and never reach the part being asked about.

A cold sitting on 2026-08-18 produced exactly this on three of the five: correct descriptions of
what the system is, offered in place of why it is that way. That is worth naming because the
correction is not more study — the material was already known, and one of the five was answered
in five words on the first attempt. **The correction is to answer the last clause.**

```
Q3:  "Your chunker split a code block.  |  Why does that matter more than it sounds?"
      └─────────── setup ──────────────┘     └─────────── the question ────────────┘
           describing this is not
           an answer to that

Q1:  "Why is your retrieval bad  |  on purpose?"
      describing dense-only        └─ the decision ─┘
      is not answering *why it was left that way*
```

---

### R5.1 Q1 — "Why is your retrieval bad on purpose?"

#### In plain words

Because a fix you have not watched something fail without is a fix you cannot defend.

Phase 1 searches by **meaning only** — no keyword search, no second-pass reorder. When those
get added later, they must be answers to failures **measured here**, not features copied from a
tutorial. The value is not “we kept it simple.” The value is a failure list with **causes
attached**, and the causes turned out not to be the ones the plan guessed.

#### The mechanism

As built, the system does one thing: put the question on the same map as the 3284 pages, take
the five nearest, paste them into a prompt. Everything a mature RAG system adds *on top* —
keyword search (BM25), a reranker, query rewriting, an agent loop — is deliberately absent
(`D04`).

```
BUILD ORDER A — everything at once
  corpus ──► dense + BM25 + reranker ──► answers
                                            │
                                            ▼
                        "it works"   ← no way to say which part
                                       is carrying it, or whether any
                                       part is carrying nothing

BUILD ORDER B — this repo
  corpus ──► dense only ──► answers ──► MEASURE ──► 4 distinct causes
                                                      │
                          each fix now has a failure it is answering
```

#### The evidence — one table that split one planned fix into four

§R4.3 measured, for each failing symbol question, the **rank of the first chunk that actually
contains the answer**, out of 3284. They had all been filed as: *"dense retrieval missed it,
hybrid search will fix it."* They are four problems:

| symbol | in corpus | rank | what you actually change |
|---|---|---|---|
| `backref` | 80 chunks | **6** | **`DEFAULT_K` in `rag/ask.py`.** It is 5. The page sat at 6. One integer |
| `cascade_backrefs` | 12 | 8 | rerank a *wider* list (take 20, keep 5). Search unchanged |
| `keys()` | 7 | 12 | same reranker — 6 is not enough |
| `table_names` | 6 | 23 | top-5 scored `+0.001` over noise — **search found nothing**. Keyword search |
| `has_table` | **0** | none | ceiling. No `k`, no reranker, ever (`D45`) |

*(Measured 2026-08-17; full write-up in [`12-EVALUATION.md`](12-EVALUATION.md) §R4.3.)*

**Read row one again.** Search ranked the first `backref` page **6th**. The chatbot only sees
the top **k** pages. With `k = 5`, rank 6 never gets pasted in. Change the constant to **6** and
that page is in the prompt — no hybrid search, no new model.

**Caveat already measured:** raising k *gets the page in*. It does not automatically get an
answer. Round 7 left refusals at 8 at every k; at k=10 the `backref` page was in the prompt and
the model still refused (`D51`). k=10 also bought over-fires. **D54 kept `DEFAULT_K = 5`.** So
6 is the integer that fixes the *retrieval miss*. It is not the integer that ships.

Had hybrid search gone in during week one, retrieval would have improved, and hybrid search
would have been credited for all four — including a constant.

#### Say this

> Phase 1 is meaning-search only — no keyword search, no reranker — because those are **fixes**,
> and I wanted the failures they fix to be measured rather than assumed. That paid off in a way I
> did not predict. I had five failing questions all filed as one problem: *"dense retrieval missed
> it, hybrid search will fix it."* When I measured where the right page actually ranked, they were
> **four different problems**.
>
> `backref` was at **rank 6** and I show the top **5** — that is a constant being wrong,
> `DEFAULT_K` in `rag/ask.py`, not an architecture problem. Changing it to 6 would put that page
> in the prompt; I measured that raising k does *not* automatically get an answer, and D54 kept
> 5, but the miss itself is still one integer. Two other failures sat at ranks 8 and 12 — a
> reranker on a wider list fixes those without touching search. One sat at 23 with the top five
> scoring `+0.001` over noise, meaning search found nothing — that is the only one keyword search
> helps. And one symbol is in **zero** chunks, so nothing retrieval can do will fix it.
>
> If I had built hybrid search first, all four numbers would have moved and I would have credited
> hybrid search for fixing a constant. The naive version is what made the four causes visible.

#### Do not say

- *"It's just dense retrieval, no reranking, meaning search only."* — That is what it **is**.
  The question asks **why**. Said alone it lands as *"I haven't built the good version yet,"*
  which is the assumption the interviewer already arrived with. The answer has to name the
  measurement that made the choice defensible: the rank table that split one planned fix into four.
- *"I wanted to keep it simple."* — Simple and broken are different things (`D44`). Simplicity
  is not a defence on its own. The defence is: without the naive run, `backref` at rank 6 would
  have looked like a hybrid-search win.
- *"We're going to add hybrid search and reranking in Phase 3."* — That is the roadmap, not the
  reason. Anyone can say what comes next. The question is why Phase 1 was left incomplete **on
  purpose**.
- Listing the missing features (BM25, reranker, agents) without the rank numbers. Features are
  the setup. `backref` at 6 with `DEFAULT_K = 5` is the punchline.

#### The follow-up

**"Why didn't you just build the good version?"**

A weak answer has nothing after this — or retreats to cost/time. The strong answer is that the
good version would have **concealed which component was doing the work**, and the rank table
proves the concealment would have been real, not hypothetical: one of the four "dense misses"
was a constant, and hybrid search would have been thanked for it.

Second follow-up that often comes: **"So just raise k to 6?"** Yes for that one retrieval miss;
no as a shipped fix — Round 7 left refusals at 8 at every k, and at k=10 the page was in the
prompt and the model still refused (`D51`/`D54`). Name both halves so it does not sound like you
forgot the generation side.

---

### R5.2 Q2 — "What is in your corpus and what did you leave out?"

#### In plain words

A **corpus** here is the set of pages the system is allowed to look things up in — like a library
of books on a shelf. Search cannot invent a book that was never shelved.

This library holds **270 files** of narrative documentation from SQLAlchemy's own git tags —
tutorials, ORM, Core, FAQ, error index, glossary — plus **exactly one** changelog file: the 2.0
migration guide. Two pinned versions sit side by side: **1.4.52** and **2.0.51**. Everything
else in the doc tree is out, and each exclusion has a reason.

**What did *not* happen.** The pages were not scraped from the live website (that would be one
version at a time). They were not "every `.rst` file in the tree." Roughly **60% of the doc
tree by bytes** was rejected on purpose.

The question's weight is on the second half: *what did you leave out?* Listing the 270 is setup.
Naming two exclusions **with their reasons** is the answer.

#### The mechanism — fetched from tags, counted from the manifest

The corpus is fetched from **git tags**, not scraped from the rendered website (`D07`). Two tags:
`rel_1_4_52` and `rel_2_0_51`. The rendered docs site shows one version at a time; this system
deliberately holds both, because the upgrade problem *is* the skew between them.

```
# runnable: uv run python -c "import json,collections; m=json.load(open('corpus/MANIFEST.json')); c=collections.Counter((f['sqlalchemy_version'], f['source_path'].removeprefix('doc/build/').split('/')[0]) for f in m['files']); [print(f'{v:8} {d:14} {n:4}') for (v,d),n in sorted(c.items())]; print('total'.ljust(23), f'{sum(c.values()):4}')"
1.4.52   core             33
1.4.52   errors.rst        1
1.4.52   faq               9
1.4.52   glossary.rst      1
1.4.52   orm              70
1.4.52   tutorial         12
2.0.51   changelog         1
2.0.51   core             33
2.0.51   errors.rst        1
2.0.51   faq               9
2.0.51   glossary.rst      1
2.0.51   orm              87
2.0.51   tutorial         12
total                    270
```

**126 files at 1.4.52** (33 + 1 + 9 + 1 + 70 + 12) and **144 at 2.0.51** (the same six, with
`orm` grown from 70 to 87, plus the one changelog file) — **270 in total**. The `orm` difference
is not noise: 2.0 documents seventeen ORM topics that 1.4 does not have.

| kept (named) | left out (and why) |
|---|---|
| `orm/`, `core/`, `tutorial/`, `faq/` | rest of `changelog/` — per-release bug notes; ~60% of bytes |
| `errors.rst`, `glossary.rst` | `dialects/` — backend specifics, not migration material |
| `changelog/migration_20.rst` only | navigation / licence pages — not teaching content |
| both tags, every kept file labelled | — |

#### The exclusions, which are the actual question

```
      SQLAlchemy doc/build/  ──────────────────────────────────────┐
                                                                   │
   KEPT                              REJECTED — and why            │
   ───────────────────────           ────────────────────────────  │
   orm/       core/                  changelog/  (except one)      │
   tutorial/  faq/                     ~60% of bytes; per-release  │
   errors.rst glossary.rst             bug entries, and migration  │
                                       guides for 1.0–1.4          │
   changelog/migration_20.rst        dialects/                     │
     2.0 only, named individually      backend specifics, not      │
                                       migration material          │
                                     index/contents/copyright      │
                                       navigation and licence      │
                                                                   │
   NOT IN THE REPO AT ALL  ◄────────────────────────────────────────┘
   the API reference — generated from docstrings at Sphinx
   build time.  It was never excluded.  It does not exist in .rst.

   OUT ON PURPOSE, FROM A DIFFERENT DIRECTORY
   deliverables/BREAKAGES.md — seeds the Phase 2 golden dataset
```

Two of those carry the answer. Say them differently so they do not blur:

**1. `BREAKAGES.md` — out on purpose (`D09`).** It holds 23 breakages with verified fixes. It is
the Phase 2 **answer key**. The corpus is what Phase 2 grades. Leave the key in the index and
the system retrieves the answer at query time, then gets marked against the same file. That is
grading your own homework with your own marking scheme.

```
  WITHOUT BREAKAGES.md in the corpus          WITH it in the corpus
  ───────────────────────────────             ─────────────────────
  question → docs → answer → score            question → BREAKAGES.md
  against BREAKAGES.md later                    (the key) → "perfect"
                                               score against the same key
```

**2. The API reference — not excluded; absent.** SQLAlchemy generates it from docstrings when
Sphinx builds. It is not in the `.rst` source, so no fetch of the `.rst` tree can contain it.
The consequence is specific and measurable: `has_table` appears in **zero** of 3284 chunks. So
`FAILURES.md` question 4 is a **ceiling** (`D45`) — no value of `k`, no reranker, no hybrid
search will ever retrieve it, because the text was never embedded. `D50` reached the same hole
from the fix-verification side without going near retrieval.

**Version skew is recorded, not filtered** (`D10`). Every file carries its release; retrieval
runs across both. Filtering to 2.0 would have deleted the exact failure the project exists to
study — a system that answers a 2.0 question with 1.4 text.

#### Say this

> A corpus is the set of pages search is allowed to open — like a library of books. Mine has
> **270 files** of narrative documentation from SQLAlchemy's own git tags — **1.4.52 and 2.0.51**,
> both, on purpose. Four directories: ORM, Core, tutorial, FAQ. Two single files: the error index
> and the glossary. Plus exactly one changelog file, the 2.0 migration guide. That is **126 at
> 1.4 and 144 at 2.0**. I did not scrape the live site — that would be one version at a time —
> and I did not take every `.rst` file. I rejected about **60% of the doc tree by bytes**: the
> rest of the changelog is per-release noise, and the dialect docs are backend specifics, not
> migration material.
>
> The weight of the question is what I left out. Two exclusions matter, and they are different
> shapes. **`BREAKAGES.md` is out on purpose** because it seeds the Phase 2 golden dataset, and
> the corpus is what Phase 2 grades — leave it in and the system retrieves the answer key at
> query time, then gets marked against the same file. That is grading your own homework.
>
> **The API reference is not excluded — it is absent.** SQLAlchemy generates it from docstrings
> when Sphinx builds; it does not exist in the `.rst` source, so no fetch of that tree can
> contain it. That became a measured ceiling: `has_table` appears in **zero** of my 3284 chunks,
> so one of my nineteen probe questions can never be answered by any amount of retrieval work.
> I know that structurally, without running a query. Version skew I kept on purpose — every file
> labelled with its release, both in the index — because filtering to 2.0 would have deleted the
> failure this project exists to study.

#### Do not say

- *"All the `.rst` files from the repo."* — Not close to all. Four directories, two root files, one
  named changelog file. Recasting a set of decisions as a sweep erases the answer.
- Naming an exclusion without its reason. *"We excluded the breakages"* is a fact about a file.
  *"…because it is Phase 2's answer key and the corpus is what Phase 2 grades"* is the answer.
- Getting the pins loose (*"1.4 and 2.0"*). They are **1.4.52** and **2.0.51**. `D16` exists
  because `>=2.0` silently drifted to 2.0.52 once, and `BREAKAGES.md` quotes error strings that
  only reproduce on the pin.
- *"We left out the API docs because they are too big / too noisy."* — They were never in the
  `.rst` tree. Size was not the lever; absence was. Saying "excluded" for something that was
  never fetchable collapses the two interesting cases into one.
- Stopping after listing the 270. That is the first half of the question. The interviewer is
  waiting for *what did you leave out* and *why*.

#### The follow-up

**"What can your system never answer, and how do you know?"**

Lead with the API-reference hole: structural, not empirical — knowable without a single query.
Name `has_table` and **zero of 3284 chunks**. Then distinguish it from a retrieval miss: no
value of `k`, no reranker, no hybrid search moves a string that was never embedded.

Second follow-up: **"Why keep both versions if that causes version-mixed answers?"** Because
filtering to 2.0 would hide the failure the product is built to catch (`D10`). Skew is recorded
on every file and measured; it is not an accident that slipped in.

---

### R5.3 Q3 — "Your chunker split a code block. Why does that matter more than it sounds?"

#### In plain words

Because a broken piece of English looks broken and a broken piece of code does not.

Half a paragraph ends mid-sentence — you hear the hole when you read it. Half a code example
is still valid Python, correctly indented, and looks like something a person wrote on purpose.
Nothing in the pipeline can tell the difference. The half-example embeds, scores, gets retrieved,
and lands in the prompt like any other chunk.

This system's output is **code someone pastes**. So a silent half-example is not a search
annoyance. It is advice that does not run — or runs and silently does the wrong thing.

#### Three different cuts — do not mix them up

The Step 2 audit and this question sound alike. They are not the same defect. Three cuts:

```
PROSE-SHAPED (Shapes A / B)         CODE-BLOCK-SHAPED (::)          SEVERED LISTING (this question)
───────────────────────────         ──────────────────────          ──────────────────────────────
"...is as follows:"                 "For example::"                 >>> class User(Base):
         ▲                                    ▲                     ...     relationship("Address"...
  English promises more,              RST: listing starts now,                 ▲
  the next paragraph is gone          body never in this chunk         valid Python. Address is
  (you HEAR it)                       (audit found 0 of these)         in the NEXT chunk
                                                                       (you do NOT hear it)
```

| cut | what it is | measured |
|---|---|---|
| **Prose-shaped** | Chunk ends *“…is as follows:”* or opens *“While the above example…”* | ~10.7% of chunks; ~6.3% lose content (`rag/chunk.py --audit`) |
| **Code-block-shaped** | Chunk ends on `::` — announced a listing and dropped it | **0** chunks. Real positive result |
| **Severed listing** | Cut falls **inside** the body of a listing | **at least 11** of 3077 boundaries — **this question** |

Zero chunks ending `::` means: we never split *at the line that introduces* a listing. It does
**not** mean “we never split code.” This question is about splits *inside the body*.

#### The mechanism — character ranges, not vibes

A chunk stores where it came from in the source file: `char_start` and `char_end`. Think of the
`.rst` file as one long string of characters, numbered from the start. Two neighbouring chunks
either **share** some characters (overlap) or they do not.

```
# illustration — adjacent, zero overlap (the bad case for code)
file characters:   85 .................... 1528 | 1529 .................... 3243
                   └──────── c00233 ────────┘   └──────── c00234 ────────┘
                   ends here                    begins here
                   (no shared characters)
```

Nothing downstream detects a half-example. There is no step that asks “is this a complete
doctest?” Embedding, scoring, retrieval, and the prompt all treat it like any other page.

```
  PROSE SPLIT — visible                CODE SPLIT — invisible
  ───────────────────────              ────────────────────────
  "...the post-rollback state          >>> class User(Base):
   of the session is as follows:"      ...     id = Column(Integer, ...)
                    ▲                  ...     addresses = relationship(
          a colon with nothing         ...         "Address", back_populates="user")
          after it.  A reader          ...     def __repr__(self):
          sees the truncation.         ...         return f"User(...)"
                                                        ▲
                                       valid Python.  Correct indentation.
                                       Complete-looking class.  And the
                                       class named "Address" is only in
                                       the NEXT chunk.
```

Three consequences, in order of seriousness:

1. **Pasteable advice.** A half-example becomes something a developer runs. An example whose
   `session.add()` is in one chunk and whose `commit()` is in the next demonstrates work that
   never persists. Same failure *shape* as this repo's `cascade_backrefs` finding: no exception,
   the INSERT simply never happens.
2. **The version tell lives in the code.** `session.query(User)` versus
   `session.execute(select(User))` *is* the 1.4/2.0 difference. Separate a listing from the
   heading that dates it and an unlabelled snippet enters an index that holds both versions on
   purpose (`D10`).
3. **Not a corner case.** Three quarters of the index has code in it:

```
# runnable: uv run python -c "import json; s=json.load(open('corpus/CHUNK_STATS.json')); print('chunks', s['n_chunks'], '| with a code block', s['with_code'], '=', f\"{s['with_code']/s['n_chunks']:.1%}\")"
chunks 3284 | with a code block 2461 = 74.9%
```

#### The evidence — and a correction made while measuring it

The question is posed hypothetically in `PHASE-1.md`. It is not hypothetical. Measured
2026-08-18:

```
# summary of: chunk boundaries falling inside an indented literal block, computed
#   over corpus/chunks.jsonl by comparing each chunk's last non-blank line with the
#   next chunk's first non-blank line in the same source file, and checking whether
#   the boundary is covered by overlap (char_start < previous char_end).
chunk boundaries, total                                     3077
  inside an indented literal block                           123
    repaired by whole-block overlap                           27
    SEVERED — no overlap, no chunk holds the block entire      96
      of which glossary.rst                                   72   ← NOT code
  severed with positive evidence of code on either side        11
```

**The first number produced was 96, and it was wrong.** The rule *"indented on both sides of the
boundary"* is a good proxy for a literal block in most files and a terrible one in `glossary.rst`,
where every definition body is indented under its term — so three quarters of the 96 were the
glossary's ordinary shape, not split code. Requiring positive evidence of code on one side (a
doctest prompt, an `import`, a `class`/`def`, an assignment) gives **11**.

Honest claim: **"at least 11 of 3077 boundaries sever a code block, and the looser count is
inflated by glossary formatting."** A regex is not an RST parser. The gap between 11 and 96 is
where that shows.

#### The worked example — which half has what

`core/operators.rst`, chunks `c00233` (chars **85→1528**) and `c00234` (**1529→3243**).
Adjacent. **Zero overlap** — 1528 then 1529, next door, nothing in common.

In the **original file**, one continuous doctest teaches `User` then `Address`. The chunker
closed a box at 1528 because the next whole block would not fit under the 1800 budget (`D33`).
It does not cut mid-line; it cuts **between blocks**. Here the next block was the start of
`Address`.

```
c00233 ENDS (first half)               c00234 BEGINS (second half)
──────────────────────────────────     ──────────────────────────────────
    ...     addresses = relationship(      >>> class Address(Base):
    ...         "Address",                 ...     __tablename__ = "address"
    ...         back_populates="user")     ...     id = Column(Integer, ...)
    ...     def __repr__(self):            ...     user_id = Column(
    ...         return f"User(...)"        ...         Integer, ForeignKey(...))
```

**Direction check — easy to flip, and wrong if flipped:**

| | where it lives |
|---|---|
| the line `relationship("Address", …)` | **first** half (`c00233`) |
| the class `Address` that name points at | **second** half only (`c00234`) |

So: the first half **declares** a relationship to a class that **only exists** in the second
half. Both halves are valid Python. Retrieve `c00233` alone and you get a mapping that cannot
work, presented as a complete example.

(The other way also holds: `c00234` has `relationship("User", …)` and `User` only exists in
`c00233`. The spoken answer only needs one direction.)

#### Overlap — when the neighbour shares characters (prose contrast)

Overlap means: the **next** chunk’s start is **before** the previous chunk’s end. Shared
characters = the missing half can still live somewhere.

```
# illustration — overlap repaired it (c03012 / c03013)
28814                    28953              29201                    31244
  |──── c03012 ────────────|                   |
  |                        |──── c03013 ─────────────────────────────|
  |         SHARED         |
```

| chunk | boundary | what happens |
|---|---|---|
| `c03012` (28814→29201) | next chunk `c03013` starts at **28953** — *inside* it | Overlap repaired it. `c03012` ends *“…is as follows:”* (bad). The paragraph **and** the bullet list both live in `c03013`. Content not lost; search might still return the bad chunk |
| `c00138` (7880→8297) | previous chunk `c00137` ends at **exactly 7880** | Zero overlap. Opens *"While the above example is against…"* — the example is only in `c00137`. **Nothing recovers this one** |

Overlap is by **whole block**, not “copy the last 200 characters” (`D33`, `D34`). Blocks are
uneven sizes, so some boundaries get generously covered and some get none at all. Same rule.
Different sizes. Different outcomes.

#### Say this

> Because **broken English announces itself and broken code does not.** A truncated sentence ends
> on a colon — you hear the hole when you read it. A truncated code example is still valid Python,
> correctly indented, and looks like something a person wrote on purpose. Nothing in the pipeline
> can tell the difference: it embeds, scores, and gets retrieved like any other chunk.
>
> That matters here specifically because this system's output is **code somebody pastes**. A
> half-example becomes advice that does not run — or worse, runs and silently does nothing, which
> is the same failure shape as the `cascade_backrefs` breakage I documented, where the INSERT
> never happens and there is no error. Separating a listing from the heading that dates it also
> drops an unlabelled snippet into an index that holds 1.4 and 2.0 on purpose.
>
> I measured it instead of assuming. **At least 11 of my 3077 chunk boundaries cut inside a code
> listing** with no overlap to repair it. One concrete case: `core/operators.rst`, chunks
> `c00233` and `c00234`, characters **1528 then 1529** — adjacent, zero overlap. The first half
> ends with `relationship("Address", back_populates="user")`. The class `Address` only exists in
> the second half. Both halves look complete. Retrieve the first alone and you get a mapping that
> cannot work, presented as a finished example.
>
> Do not mix that up with two other cuts. About **1 in 10** chunks has a **prose-shaped** hole —
> ends *“…is as follows:”* or opens *“While the above…”* — and about **1 in 16** loses content.
> **Zero** chunks end on `::`, the marker that *introduces* a listing. That means we never split
> at the introduction. It does **not** mean we never split code. This question is about splits
> *inside the body*.

#### Do not say

- *"The model can only see the retrieved chunk, not the whole document."* — True of every chunk
  in the index, including prose. It cannot explain why **code** is worse, which is the question.
  The word doing the work is **silently**.
- *"It loses context."* — So does every chunk boundary. Vague. Name the silent half-example and
  the paste risk.
- *"We never split code because zero chunks end on `::`."* — Zero `::` means we never split at
  the *introduction*. The 11 are splits *inside the body*. Mixing those three cuts (prose /
  `::` / severed listing) is the most common wrong shape of a right-sounding answer.
- Stopping at *"I measured 11."* without a named example. The number alone is forgettable;
  `c00233` ending on `relationship("Address", …)` with `Address` only in `c00234` is not.
- *"So I will fix it with overlap."* — Overlap already exists (`D33`/`D34`, whole-block). It
  repaired `c03012`/`c03013` and **failed** on `c00138` (exact boundary at 7880). Same rule,
  uneven block sizes, different outcomes. Overlap is not a free fix for every severed listing.

#### The follow-up

**"So detect it and fix the chunker."**

Detecting it is harder than it sounds, and this file's own **96-versus-11** correction is the
demonstration: a regex over "indented on both sides" mistook 72 glossary entries for split code,
because glossary bodies are indented under their terms by nature. Doing it properly needs an RST
parser — a real piece of work, not a guard clause — and that is a defensible reason for it to be
open rather than done. Honest claim: *at least* 11, and the looser count is inflated by glossary
formatting.

Second follow-up: **"Does overlap fix it?"** Sometimes. Show `c03012` (repaired — next chunk
starts inside it at 28953) next to `c00138` (unrecovered — previous ends exactly at 7880). Same
overlap rule; different sizes; different outcomes.

---

### R5.4 Q4 — "Dense retrieval missed a question containing an exact symbol name. Why?"

> **Read this first — the confusion this section causes.**
>
> Dense retrieval returns **pages**, not API names. It did **not** “give us `Query.get`
> instead of `Session.get`.”
>
> | | role | what happened on this corpus |
> |---|---|---|
> | `Query.get` / `Session.get` | **teaching picture** only | *what replaces `Query.get()`?* → right page ranked **#1** (`D39`) |
> | `backref` at rank **6** | **measured miss** | right page one below `DEFAULT_K = 5`, never pasted |
>
> If you only remember one line: **teaching pair ranked 1; real miss is `backref` at 6.**

#### In plain words — start from SQL you already know

In SQLAlchemy 1.4 you often wrote:

```python
# 1.4 style — still works in 2.0, but warns
issue = session.query(Issue).get(1)
```

In 2.0 the preferred form is:

```python
# 2.0 style
issue = session.get(Issue, 1)
```

**Same job.** Both mean: “look up one row by primary key and give me the object.” Same SQL under
the hood on this repo’s measurements (`02-MIGRATION-2.0.md`). The upgrade question a stuck
developer types is:

> *what replaces `Query.get()`?*

The answer is on a page that literally says `Query.get` and `Session.get` near each other.

#### Why meaning search can struggle here

**Dense retrieval = meaning search** (same as R4.4). Every page is a point on a map. Search
returns pages whose meaning is nearest to the question. It does **not** run `grep` for the
letters `Q-u-e-r-y-.-g-e-t`.

Now put two pages on that map:

| page talks about | what a person hears | what the map hears |
|---|---|---|
| `Query.get(...)` | fetch one row by PK | “fetch one row by PK” |
| `Session.get(...)` | fetch one row by PK | “fetch one row by PK” |

To a person learning the migration, those names are different — **that difference is the whole
point of the question.** To the meaning map, they are almost the **same idea**, so they sit
almost on top of each other.

```
  WHAT YOU CARE ABOUT (the characters)     WHAT MEANING SEARCH COMPARES

  Query.get     ←── letters differ ──→     both sit here ●──● Session.get
  Session.get       (Q vs S, …)              "fetch one row by primary key"
                                             almost the same spot on the map
```

Count the characters if it helps: `Query.get` vs `Session.get` — most letters differ, but the
*job description* does not. Meaning search ranks by job description. So the exact symbol name —
often the **most precise** part of a developer’s question — is the part meaning search is
structurally worst at reading.

**Keyword search** (`grep`-like / BM25) looks at the letters. That is the missing channel.
Phase 3’s hybrid search = meaning search **plus** letter search. Not “a bigger meaning model.”

#### What this example is — and what it is not

| | |
|---|---|
| **It is** | a picture of *why* meaning search can blur two near-synonym APIs |
| **It is not** | “search returned `Query.get` when we needed `Session.get`” |
| **It is not** | “our system failed on `Query.get`” |

**What people mishear.** Dense retrieval does not hand you one API name instead of the other.
It hands you **pages**. The worry is: a question that hinges on the *letters* `Query.get` might
pull pages that are only “about fetching by PK” in meaning — including pages that talk about
`Session.get` — and rank those as near as the page that literally documents the rename.

**What we actually measured (`D39`).** The question *what replaces `Query.get()`?* put a
containing chunk at **rank 1 of 3284**. Meaning search **nailed** that one — the right page
came first. So do **not** say “we got Query instead of Session.” Keep the pair as the
*mechanism* picture (why letter-sensitive questions are a weak spot for meaning search). Use
**`backref` at rank 6** as the *measured* miss on this corpus: the right page existed, sat one
below `DEFAULT_K = 5`, and never got pasted in.

#### The mechanism in one sentence

Every page → 1024 numbers on a map → search = nearest neighbours by **meaning**. Closeness is
not “does the string `table_names` appear.” A rare exact identifier is often the best clue in
the question and the worst clue for dense retrieval.

```
   MEANING MAP (dense / Phase 1)              LETTER MATCH (grep / BM25 — not in Phase 1)

        Query.get()  ●                          Query.get()     ← string match finds this
                      ● Session.get()           Session.get()   ← different string
        almost the same meaning                 letters differ
        (two close dots = similar job)          dense never looks at these letters
```

**What this picture does *not* say.** It does **not** mean “dense returned the wrong API” or
“dense cannot answer *what replaces Query.get?*.” Dense does not stamp a page with the label
`Query.get` or `Session.get`. It only ranks pages by how close their **meaning** is to the
question. The picture is why that ranking *can* blur two near-synonym APIs.

**What we measured.** For *what replaces `Query.get()`?* the right page still came **first**
(rank 1 — `D39`). So on this corpus, dense **did** mark that question right. The weakness is
real; that particular failure did not show up. The failure that *did* show up is `backref` at
rank 6.

#### The evidence — scarcity is not the mechanism

Three failures that look alike from outside, three different owners — **these are the measured
ones**, not the `Query.get` teaching pair:

| symbol | in corpus | rank / shape | what that proves |
|---|---|---|---|
| `backref` | **80** chunks | rank **6** (cut is `k=5`) | Not scarce. Meaning-neighbours outranked the exact name |
| `table_names` | 6 | rank **23**; top-5 scores `+0.001` over noise | Search found **nothing** — not “ranked low” |
| `has_table` | **0** | absent from all 3284 | Ceiling (`D45`) — not a dense-search miss at all |

`backref` alone kills the rarity story. Whatever went wrong at rank 6, scarcity was not it.
Rarity is an **IDF** idea — it is what makes BM25 (letter search) work. A dense retriever holds
no term-frequency statistics; there is nothing for rarity to act on.

`table_names` is a different shape again: its returned top-5 scored `+0.001` and `+0.000` over
noise (random pairs average ~0.540 — §R2.5). Search did not rank the answer low. It found
nothing and filled five slots with near-random text. Reranking that list cannot help; keyword
search can.

And `has_table` is not a ranking miss: **0 chunks**. Same-looking wrong answer from outside;
different owner.

#### Say this

> Because **an embedding matches meaning, not strings.** You already know both APIs:
> `session.query(Issue).get(1)` and `session.get(Issue, 1)` — same job, fetch one row by PK.
> Meaning search hears that shared job, so the two **names** sit almost on top of each other on
> the map. It does not `grep` the letters. That is why letter-sensitive upgrade questions are a
> weak spot for dense retrieval, and why Phase 3 adds keyword search (BM25) — not a bigger
> embedding model.
>
> **Important — do not confuse the picture with the measurement.** Dense retrieval returns
> **pages**, not “Query instead of Session.” On *this* corpus, *what replaces `Query.get()`?*
> ranked the right page **#1** (`D39`). So that pair is only a teaching picture of the weakness.
> The **real miss we measured** is `backref`: in **80** chunks, still rank **6** under
> `DEFAULT_K = 5` — right page never pasted. Not rarity. `table_names` at 23 found nothing
> useful; `has_table` is in **zero** chunks — a ceiling.

#### Do not say

- *"We got Query.get instead of Session.get."* — Wrong shape. Search returns pages. And on this
  corpus that question ranked **1** — it did not fail that way.
- *"Because the symbol is rare in the docs."* — The most attractive wrong answer. **Rarity is
  an IDF concept** — it is what makes BM25 work (the *fix*). A dense retriever holds no
  term-frequency statistics; there is nothing for rarity to act on. `backref` in 80 chunks at
  rank 6 is the counterexample you should have ready before the interviewer asks.
- *"It needs a better embedding model."* — Capacity is not the gap; the lexical channel is
  missing. A model 25× smaller matched on R@5 (`D32`).
- *"Hybrid search will fix all of these."* — Only the ones where the string is in the corpus and
  dense search failed to prefer it. It does not create `has_table` out of zero chunks, and it is
  not what `backref` at rank 6 primarily needs (that one is one integer of depth).
- Stopping at the slogan *"meaning not strings"* without separating **teaching pair**
  (`Query.get` / `Session.get`, ranked 1) from **measured miss** (`backref` at 6).

#### The follow-up

**"Where in the embedding does rarity appear?"** — asked of anyone who reaches for scarcity.
There is no answer, because it does not appear. Have `backref` / 80 chunks / rank 6 ready.

For the correct answer, the next jab is usually **"So a bigger model would fix it?"** No. The
channel is missing, not undersized. BM25 (or any lexical match) is the missing half; model size
is not.

Third jab: **"Then why didn't hybrid search land in Phase 1?"** Point back to Q1 — so the
failures that justify it are measured, not assumed. This question is the mechanism; Q1 is why
the mechanism was left naked on purpose.

---

### R5.5 Q5 — "How do you know the answer came from the sources and was not invented?"

#### In plain words

From the answer alone, you do not.

A citation like `[3]` is text the model generated — exactly like the rest of the answer. The
model emitted those characters the same way it emitted every other word. What this system
provides is not **proof** of grounding. It is a **cheap path for a human to check**, plus
nineteen answers where a human walked that path.

#### The mechanism

There is no automatic grounding check anywhere in Phase 1. The one mechanical signal that
exists is narrower than it sounds:

```python
# rag/probe.py — the uncited signal
"uncited": not citations and len(answer.split()) > 15,
```

That detects the **absence of an `[n]` marker** in a substantial answer. It never opens the
cited chunk. Nothing in the pipeline compares a claim against the source it cites.

```
   claim in the answer
        │
        │  "[3]"  ← generated text.  The model emitted this the same
        │            way it emitted every other token.
        ▼
   chunk 3 ──── source_path ────► doc/build/orm/session_basics.rst
            ├── heading_path ───► Session Basics > ... > Rolling Back
            └── char_start/end ─► 28814 → 29201
                                        │
                                        ▼
                        a person opens the file at that offset
                        and reads whether the claim is there
                                        │
        ┌───────────────────────────────┘
        ▼
   THIS LINK IS TRAVERSED BY A HUMAN.  No code walks it.
```

`char_start` / `char_end` are not bookkeeping. They are the only mechanical link between a
claim and the exact place its evidence should be. They were **missing until 2026-08-15** —
chunks carried `n_chars`, a length, which names a file but not a place in it.

**A related warning flag: `single_source`.** Search returned several pages; the answer cites
only one. If that one page is misleading, the answer has no backup in the citations — even if
`[2]` in the prompt contradicted it. Question 7 is the case: cited only `[1]` (a 2.0 page
saying *“In 1.4, pass `future=True`”*) while `[2]` already said the flag is legacy on 2.0.
*Does not survive* means: no safety net in the citations. Still not a verdict — a place to look.

#### The evidence — citation and correctness are independent, and it is measured

The nineteen hand-written verdicts contain counterexamples in **both** directions:

| | verdict | note |
|---|---|---|
| **Q1** | `PARTIAL` | *"Names `aliased` and **cites the right migration section**, but omits its second argument… the same query returns `['a','e']` instead of `['a']`"* |
| **Q2** | `CORRECT` | *"emits SQL byte-identical to BREAKAGES #13's fix; **the only flaw is `uncited`**, so a reader cannot check it without running it"* |
| **Q12** | `PARTIAL` | *"the ordered steps match the migration guide, but **the answer cites nothing**… and ordering is the whole content of this question"* |
| **Q16** | `WRONG` | *"An `absent` question that did NOT refuse… from real text, and **cited nothing**"* |

**Q1 cites correctly and is wrong. Q2 cites nothing and is right.** A citation is neither
necessary nor sufficient for a grounded answer in this system. That is a measurement, not an
argument.

What does establish grounding is human verification, recorded so a regeneration cannot destroy
it:

```
# runnable: uv run python -c "import json,collections; d=json.load(open('deliverables/verdicts.json')); v=[x[0] for k,x in d.items() if not k.startswith('_')]; print(len(v), 'verdicts:', dict(collections.Counter(v)))"
19 verdicts: {'PARTIAL': 3, 'CORRECT': 10, 'WRONG': 6}
```

```
# runnable: uv run python -m tools.apply_verdicts --check
in sync: 19 verdicts
```

Two design decisions sit behind those two commands:

- **`D06` — the golden dataset is hand-verified, never auto-generated.** A model scoring its
  own output measures self-consistency and reports it as truth.
- **`D46` — the script records signals; a human writes the verdicts.** `probe.py` computes
  `refused`, `uncited`, `version_mixed`, `symbol_missing`, `single_source`. **None of them is
  automatically a failure** — `refused` is the *correct* output for a question the corpus
  cannot answer. They say where to look, not what is true.

The verdicts live in `deliverables/verdicts.json` rather than in the generated `FAILURES.md`,
because `probe.py` generates that file — and before the split, regenerating it overwrote all
nineteen human judgements with `UNVERIFIED` and reported nothing.

**`D50` went one step further** on the fix side: every fix in `BREAKAGES.md` verified twice —
that it runs against real 2.0.51, and that the documentation recommends it. Twelve of thirteen
passed both; the one miss is `has_table`, which is the API-reference hole from R5.2 arriving
from a third direction.

#### Say this

> **From the answer alone, I do not — and that is the honest starting point.** A citation like
> `[3]` is generated text, exactly like every other word in the answer. The model emitted those
> characters the same way it emitted the claim. My one mechanical signal, `uncited`, only detects
> the *absence* of an `[n]` marker in a long answer. It never opens the cited chunk. Nothing in
> my pipeline checks that a cited source supports the claim.
>
> What the system does instead is make checking **cheap**. Every answer prints the chunks it was
> given, and every chunk carries its source file, heading path, and **character offsets**
> (`char_start` / `char_end`) — so anyone can open the original at that exact position. Those
> offsets were missing until 2026-08-15; before that chunks only had a length, which names a file
> but not a place in it. Then a **human** walks that link. I hand-verified all **19** probe
> answers against real SQLAlchemy **2.0.51**: **10 correct, 3 partial, 6 wrong.** Never
> auto-graded — a model scoring its own output measures self-consistency and reports it as truth
> (`D06`). The script records signals (`refused`, `uncited`, `single_source`, …); a human writes
> the verdicts (`D46`). None of those signals is automatically a failure — `refused` is the
> *correct* output when the corpus cannot answer.
>
> And the verdicts prove citations are not the mechanism, in **both** directions. **Question 1
> cites exactly the right migration section and is still wrong** — it omits `aliased`'s second
> argument, and the query returns `['a','e']` instead of `['a']`. **Question 2 cites nothing and
> is exactly right** — its SQL is byte-identical to the verified fix. Citation and correctness
> are independent here, and that is measured, not argued.
>
> A related warning: `single_source`. Search returned several pages; the answer cites only one.
> Question 7 cited only `[1]` (a 2.0 page talking about 1.4) while `[2]` in the same prompt
> already contradicted it. *Does not survive* means: no backup in the citations if that one page
> is bad. Still a place to look, not a verdict.

#### Do not say

- *"Because it has citations."* — The answer this question is built to catch. The repo's own
  verdicts refute it in both directions (Q1 cites and is wrong; Q2 does not cite and is right).
- *"Because the prompt tells it to only use the sources."* — `11-GENERATION.md` §R3 measured
  wordings of that instruction. Without a refuse sentence the model fabricates. Even the shipped
  wording has questions (Q18, Q19) that refuse with the answer sitting in the prompt. The
  instruction is a real lever and it is not a guarantee.
- *"Because we check grounding automatically."* — There is no automatic grounding check in
  Phase 1. `uncited` is absence of a marker. Full stop.
- *"Because retrieval returned the right chunks."* — Retrieval puts pages in the prompt. It does
  not make the model use them, cite them correctly, or avoid inventing. Generation is a separate
  failure mode (Q18/Q19 refuse with chunks present).

#### The follow-up

**"And if it cites a chunk that doesn't say that?"**

A weak answer ends here — or invents an automatic check that does not exist. The strong answer
already conceded it in the first sentence, named the character offsets as the human check, and
has the **Q1 verdict** ready as the case where citation was correct and the answer was still
wrong.

Second follow-up: **"So how do you stop inventing?"** You do not, fully, from the answer alone.
You make checking cheap (offsets + printed sources), you refuse when the corpus cannot answer
(prompt D), and you hand-verify a probe set so the failure modes are named. Phase 2's golden set
extends that under `D06` — humans verify; the scorer drops anything that is not.

---

### R5.6 The five on one page

For revision. The first column is the compressed claim; the second is the trap that kills a
weak answer. The full *Say this* / *Do not say* / *Follow-up* live in the sections above.

| | the one sentence | do not land on |
|---|---|---|
| **Q1** | Dense-only on purpose — rank table split one planned fix into four; one was `DEFAULT_K=5` vs `backref` at 6 | “it’s just dense / I kept it simple” |
| **Q2** | 270 files from two tags; `BREAKAGES.md` out = answer key; API ref absent = ceiling (`has_table` in 0) | “all the `.rst` files” / “API too big” |
| **Q3** | Broken prose is visible, broken code is not; ≥11/3077 severed listings — `c00233`/`c00234` at 1528\|1529 | “we never split code” (zero `::` ≠ zero body splits) |
| **Q4** | Meaning ≠ strings; teaching pair `Query.get`/`Session.get` ranked **1** (`D39`); measured miss = `backref`@6 | “we got Query not Session” / “symbol is rare” |
| **Q5** | From the answer alone you cannot; offsets + human 19; Q1 cites&wrong, Q2 uncited&right | “because it has citations” |

### R5.7 The five, spoken end to end

The table above is a memory card. **This is the answer as it would actually be said**, all five
in a row, so the run can be rehearsed as one piece rather than five lookups. Each block matches
the *Say this* in its section; each *Follow-up* matches the section’s follow-up (including the
second jab).

Read it aloud. If a sentence is hard to say, it is hard to follow, and it needs rewriting here
rather than improvising at the time.

#### 1. Why is your retrieval bad on purpose?

> Phase 1 is meaning-search only — no keyword search, no reranker — because those are **fixes**,
> and I wanted the failures they fix to be measured rather than assumed. That paid off in a way I
> did not predict. I had five failing questions all filed as one problem: *"dense retrieval missed
> it, hybrid search will fix it."* When I measured where the right page actually ranked, they were
> **four different problems**.
>
> `backref` was at **rank 6** and I show the top **5** — that is a constant being wrong,
> `DEFAULT_K` in `rag/ask.py`, not an architecture problem. Changing it to 6 would put that page
> in the prompt; I measured that raising k does *not* automatically get an answer, and D54 kept
> 5, but the miss itself is still one integer. Two other failures sat at ranks 8 and 12 — a
> reranker on a wider list fixes those without touching search. One sat at 23 with the top five
> scoring `+0.001` over noise, meaning search found nothing — that is the only one keyword search
> helps. And one symbol is in **zero** chunks, so nothing retrieval can do will fix it.
>
> If I had built hybrid search first, all four numbers would have moved and I would have credited
> hybrid search for fixing a constant. The naive version is what made the four causes visible.

*Follow-up:* **"Why not just build the good version?"** It would have hidden which component was
doing the work — and the rank table proves the hiding would have been real. **"So just raise k
to 6?"** Fixes that one retrieval miss; Round 7 left refusals at 8 at every k, and at k=10 the
page was in the prompt and the model still refused.

*Do not say:* “It’s just dense retrieval” (what it *is*, not *why*); “I wanted to keep it
simple”; listing Phase 3 features without the rank numbers.

#### 2. What is in your corpus and what did you leave out?

> A corpus is the set of pages search is allowed to open — like a library of books. Mine has
> **270 files** of narrative documentation from SQLAlchemy's own git tags — **1.4.52 and 2.0.51**,
> both, on purpose. Four directories: ORM, Core, tutorial, FAQ. Two single files: the error index
> and the glossary. Plus exactly one changelog file, the 2.0 migration guide. That is **126 at
> 1.4 and 144 at 2.0**. I did not scrape the live site — that would be one version at a time —
> and I did not take every `.rst` file. I rejected about **60% of the doc tree by bytes**: the
> rest of the changelog is per-release noise, and the dialect docs are backend specifics, not
> migration material.
>
> The weight of the question is what I left out. Two exclusions matter, and they are different
> shapes. **`BREAKAGES.md` is out on purpose** because it seeds the Phase 2 golden dataset, and
> the corpus is what Phase 2 grades — leave it in and the system retrieves the answer key at
> query time, then gets marked against the same file. That is grading your own homework.
>
> **The API reference is not excluded — it is absent.** SQLAlchemy generates it from docstrings
> when Sphinx builds; it does not exist in the `.rst` source. That became a measured ceiling:
> `has_table` appears in **zero** of my 3284 chunks, so one of my nineteen probe questions can
> never be answered by any amount of retrieval work. I know that structurally, without running a
> query.

*Follow-up:* **"What can your system never answer?"** API-reference hole — `has_table` in zero
chunks; structural, no query needed. **"Why keep both versions?"** Filtering to 2.0 would hide
the failure the product exists to catch (`D10`).

*Do not say:* “all the `.rst` files”; exclusion without reason; loose pins (“1.4 and 2.0”);
“API docs too big” (they were never in `.rst`).

#### 3. Your chunker split a code block. Why does that matter more than it sounds?

> Because **broken English announces itself and broken code does not.** A truncated sentence ends
> on a colon — you hear the hole. A truncated code example is still valid Python, correctly
> indented, and looks deliberate. Nothing downstream can tell: it embeds, scores and gets
> retrieved like any other chunk.
>
> That matters here specifically because this system's output is **code somebody pastes**. A
> half-example becomes advice that does not run — or worse, runs and silently does nothing, which
> is the same failure shape as the `cascade_backrefs` breakage I documented, where the INSERT
> never happens and there is no error.
>
> I measured it instead of assuming. **At least 11 of my 3077 chunk boundaries cut inside a code
> listing** with no overlap to repair it. One concrete case: `core/operators.rst`, chunks
> `c00233` and `c00234`, characters 1528 then 1529 — adjacent, zero overlap. The first half
> ends with `relationship("Address", back_populates="user")`. The class `Address` only exists
> in the second half. Both halves look complete.
>
> Separately: **prose-shaped** holes (~1 in 10; ~1 in 16 unrecoverable). **Zero** end on `::` —
> we never split at the *introduction*. That is not the same as never splitting code. This
> question is about splits *inside the body*.

*Follow-up:* **"So fix the chunker."** First count was 96; 72 were glossary indent — needs an
RST parser, not a regex. **"Does overlap fix it?"** Sometimes (`c03012` repaired) and sometimes
not (`c00138` unrecovered) — same whole-block rule, uneven sizes.

*Do not say:* “model only sees the chunk” (true of prose too); “we never split code” because
zero `::`; “overlap will fix it” as a free pass.

#### 4. Dense retrieval missed a question containing an exact symbol name. Why?

> Because **an embedding matches meaning, not strings.** You already know both APIs:
> `session.query(Issue).get(1)` and `session.get(Issue, 1)` — same job. Meaning search hears the
> shared job, so those names sit almost on top of each other on the map. It does not `grep`
> letters. BM25 adds that channel — not a bigger model.
>
> **Do not say we got Query instead of Session.** Search returns pages. On this corpus *what
> replaces `Query.get()`?* ranked **#1** (`D39`) — teaching picture only. The **measured miss**
> is `backref`: **80** chunks, still rank **6** under `DEFAULT_K = 5`. Not rarity.
> `table_names` at 23 found nothing; `has_table` is **zero** chunks.

*Follow-up:* **"Where in the embedding does rarity appear?"** It does not — have `backref`/80/6
ready. **"So a bigger model?"** No. Channel missing, not undersized.

*Do not say:* “we got Query not Session”; “the symbol is rare”; “needs a better model”; “hybrid
fixes all of these” (including the ceiling and the k=5 miss).

#### 5. How do you know the answer came from the sources and was not invented?

> **From the answer alone, I do not — and that is the honest starting point.** A citation like
> `[3]` is generated text like everything else. My `uncited` signal only detects the *absence*
> of an `[n]` marker; it never opens the chunk. Nothing checks that a cited source supports the
> claim.
>
> What the system does is make checking **cheap**: source file, heading path, **character
> offsets** — open the original at that position. Then a human walks the link. I hand-verified
> all **19** probe answers against real 2.0.51: **10 correct, 3 partial, 6 wrong.** Never
> auto-graded (`D06`). Signals are not verdicts (`D46`).
>
> Citations are not the mechanism: **Q1 cites the right section and is wrong**; **Q2 cites
> nothing and is right**. `single_source` (Q7) is a related warning — one citation, no backup —
> still a place to look, not a verdict.

*Follow-up:* **"And if it cites a chunk that does not say that?"** Already conceded; offsets are
the check; Q1 is the case. **"So how do you stop inventing?"** You do not, fully, from the
answer alone — cheap checks, refuse when the corpus cannot, hand-verify the probe set.

*Do not say:* “because it has citations”; “because the prompt says so”; “we check grounding
automatically”; “retrieval returned the right chunks.”

### What this file does not claim

Three things are easy to run together here and only two are established:

- **These are good answers to these five questions.** Claimed, and each carries its measurement.
- **They are the only good answers.** Not claimed. Q1 in particular has a legitimate alternative
  framing — cost — that is not made here because it is not the reason this repo chose it.
- **Being able to write them means being able to say them.** Not claimed, and the distinction is
  the entire point of the gate being *cold, from memory, no notes*. This file is what the gate
  is taken **against**, not a substitute for taking it. Reading it before a sitting converts the
  sitting into recognition, which measures nothing.

---

## Where the rest of the repo lives

[`../README.md`](../README.md) maps everything. Directly relevant here:
[`../phases/PHASE-1.md`](../phases/PHASE-1.md) (the questions and the phase's gates),
[`09-DECISIONS.md`](09-DECISIONS.md) (`D04`, `D06`, `D07`, `D09`, `D10`, `D33`, `D34`, `D45`,
`D46`, `D50`), [`12-EVALUATION.md`](12-EVALUATION.md) §R4.3 (the rank measurement),
[`../deliverables/FAILURES.md`](../deliverables/FAILURES.md) and
[`../deliverables/verdicts.json`](../deliverables/verdicts.json) (the nineteen answers and their
verdicts).
