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

| | question | what it is really testing |
|---|---|---|
| **Q1** | Why is your retrieval bad on purpose? | whether the simplicity was chosen or merely reached |
| **Q2** | What is in your corpus and what did you leave out? | whether the exclusions have reasons |
| **Q3** | Your chunker split a code block. Why does that matter more than it sounds? | whether you know how this system fails *silently* |
| **Q4** | Dense retrieval missed a question containing an exact symbol name. Why? | whether you know the mechanism, not the fix |
| **Q5** | How do you know the answer came from the sources and was not invented? | whether you know what the system *cannot* prove |

#### The shape of a good answer

Each section below is written in the same four parts, because that is the order the answer has
to be *built* even though only the last part gets said out loud:

1. **In plain words** — the version with no jargon in it. If this part cannot be written, the
   idea is not understood yet, and every technical sentence after it will be recital.
2. **The mechanism** — what is actually happening, in the system's own terms.
3. **The evidence** — the measurement from this repo that makes the claim checkable rather than
   plausible. This is the part almost no candidate has.
4. **Say this** — the sixty-second spoken answer, which is parts 1–3 compressed.

And two guards, because a wrong answer is usually not empty — it is a nearby right-sounding
thing:

- **Do not say** — the specific wrong answer these questions attract, and why it dies.
- **The follow-up** — the one question an interviewer asks next, which a weak answer cannot
  survive.

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
```

---

### R5.1 Q1 — "Why is your retrieval bad on purpose?"

#### In plain words

Because a fix you have not watched something fail without is a fix you cannot defend. Phase 1
searches by meaning only — no keyword search, no reranker — so that when those get added, they
are answers to failures that were **measured here**, not features copied from a tutorial.

#### The mechanism

The system as built does one thing: embed the question, find the nearest chunks in meaning-space,
put them in a prompt. Everything a mature RAG system has *on top of* that — hybrid search,
reranking, query rewriting, an agent loop — is deliberately absent (`D04`).

The value is not the simplicity. It is that the simplicity produces a **failure list with
causes attached**, and the causes turn out not to be the ones a plan would have guessed.

```
BUILD ORDER A — everything at once
  corpus ──► dense + BM25 + reranker ──► answers
                                            │
                                            ▼
                        "it works"   ← and no way to say which part
                                       is carrying it, or whether any
                                       part is carrying nothing

BUILD ORDER B — this repo
  corpus ──► dense only ──► answers ──► MEASURE ──► 4 distinct causes
                                                      │
                          each fix now has a failure it is answering
```

#### The evidence

This is the part that turns `D04` from a slogan into an argument. §R4.3 measured the **rank of
the first chunk that actually contains the answer** for the five failing questions, out of 3284
chunks. They had all been filed as one problem — *"dense retrieval missed it, hybrid search will
fix it."* They are four problems:

| symbol | in corpus | rank | what it actually is |
|---|---|---|---|
| `backref` | 80 chunks | **6** | `DEFAULT_K = 5`. **A constant is wrong.** One integer fixes it |
| `cascade_backrefs` | 12 | 8 | ranking roughly right, cut too tight — a reranker fixes it |
| `keys()` | 7 | 12 | same: a reranking case, search unchanged |
| `table_names` | 6 | 23 | top-5 scored `+0.001` over noise — **search found nothing**. Only here does keyword search help |
| `has_table` | **0** | none | the corpus ceiling. No `k`, no reranker, ever (`D45`) |

*(Measured 2026-08-17; the table is reproduced from [`12-EVALUATION.md`](12-EVALUATION.md) §R4.3,
where the command that produces it lives.)*

**Read row one again.** Had hybrid search gone in during week one, retrieval would have improved,
and hybrid search would have been credited for all four. One of them is `DEFAULT_K` being 5 when
the answer sits at 6. The architecture would have been given the credit for a constant.

#### Say this

> Phase 1 is dense-retrieval-only on purpose, because hybrid search and reranking are fixes and
> I wanted the failures they fix to be measured rather than assumed. That paid off in a way I
> didn't predict: when I measured the rank of the first containing chunk for my five failures,
> they weren't one problem, they were four. One was at rank 6 with `k` set to 5 — a constant
> being wrong, not a retrieval architecture problem. If I'd built hybrid search first I'd have
> watched the numbers improve and credited the wrong component. Now every fix in Phase 3 has a
> specific failure it answers, and I can name which ones it will *not* fix.

#### Do not say

- *"It's just dense retrieval, no reranking, meaning search only."* — That is what it **is**.
  The question asks **why**. Said alone it lands as *"I haven't built the good version yet,"*
  which is the assumption the interviewer already arrived with.
- *"I wanted to keep it simple."* — Simple and broken are different things, and `D44` exists
  because that distinction got blurred once already in this repo. Simplicity is not a defence
  on its own; the measurement it enabled is.

#### The follow-up

**"Why didn't you just build the good version?"** A weak answer has nothing after this. The
strong answer is that the good version would have concealed which component was doing the work —
and the rank table proves the concealment would have been real, not hypothetical.

---

### R5.2 Q2 — "What is in your corpus and what did you leave out?"

#### In plain words

Narrative documentation from SQLAlchemy's own repository, at two pinned versions — the tutorials,
the ORM and Core guides, the FAQ, the error index and the glossary — plus exactly one file from
the changelog: the 2.0 migration guide. Everything else in the doc tree is out, and each
exclusion has a reason.

#### The mechanism

The corpus is fetched from **git tags**, not scraped from the rendered website (`D07`). Two tags:
`rel_1_4_52` and `rel_2_0_51`. That matters because the rendered site is one version at a time
and this system deliberately holds both.

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

**"All the `.rst` files" is wrong and undersells the work.** Four directories, two root files and
one named changelog file were chosen. Roughly 60% of the doc tree's bytes were rejected.

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

Two of those carry the answer.

**`BREAKAGES.md` is out because the corpus is what Phase 2 grades** (`D09`). It holds 23
breakages with their verified fixes — it is the answer key. Leave it in the index and the system
retrieves the answer key at query time, then gets marked against it. That is marking your own
homework with your own marking scheme and reporting the score.

**The API reference is not an exclusion. It is an absence, and it became a measured hole.**
SQLAlchemy generates its API reference from docstrings when Sphinx builds; it is not in the
`.rst` source, so no fetch of the `.rst` tree can contain it. The consequence is specific:
`has_table` appears in **zero** `.rst` files at `rel_2_0_51`. So `FAILURES.md` question 4 is a
**ceiling** case — no value of `k`, no reranker and no hybrid search will ever retrieve it,
because the text was never embedded. `D50` reached the same conclusion from the fix-verification
side, without going near the retrieval system.

**Version skew is recorded, not filtered** (`D10`). Every file carries its release and retrieval
runs across both. Filtering to 2.0 would have deleted the exact failure the project exists to
study — a system that answers a 2.0 question with 1.4 text.

#### Say this

> 270 files of narrative documentation from SQLAlchemy's own git tags — 1.4.52 and 2.0.51 —
> covering the tutorials, ORM, Core, FAQ, error index and glossary, plus one changelog file, the
> 2.0 migration guide. I left out the rest of the changelog and the dialect docs, about 60% of
> the bytes, as per-release noise. Two exclusions are the interesting ones. `BREAKAGES.md` is out
> because it seeds the Phase 2 golden dataset and the corpus is what Phase 2 grades — leaving it
> in means retrieving the answer key at query time. And the API reference isn't in the corpus
> because it isn't in the source at all; it's generated from docstrings at build time. That
> turned into a measured ceiling: `has_table` is in zero `.rst` files, so one of my nineteen
> probe questions can never be answered by any amount of retrieval work.

#### Do not say

- *"All the `.rst` files from the repo."* — Not close to all, and it recasts a set of decisions
  as a sweep.
- Naming an exclusion without its reason. *"We excluded the breakages"* is a fact about a file.
  The reason is the answer.
- Getting the pins loose (*"1.4 and 2.0"*). They are **1.4.52** and **2.0.51**. `D16` exists
  because `>=2.0` silently drifted to 2.0.52 once, and `BREAKAGES.md` quotes error strings that
  only reproduce on the pin.

#### The follow-up

**"What can your system never answer, and how do you know?"** The API-reference hole is the
answer, and it is a strong one because it is structural rather than empirical — it is knowable
without running a single query.

---

### R5.3 Q3 — "Your chunker split a code block. Why does that matter more than it sounds?"

#### In plain words

Because a broken piece of English looks broken and a broken piece of code does not. Half a
paragraph ends mid-sentence and anyone can see it. Half a code example is still valid Python,
correctly indented, and looks like something a person wrote on purpose.

#### The mechanism

Nothing downstream can detect it. The chunk embeds normally, scores normally, is retrieved
normally and is placed in the prompt normally. There is no step in the pipeline where a
half-example is distinguishable from a whole one.

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
                                       `Address` it points at is in the
                                       NEXT chunk.
```

Three consequences, in increasing order of seriousness:

1. **The output of this system is code people paste.** It is a migration assistant, not a search
   engine. A silently truncated example becomes advice that does not run — or worse, runs and
   does something different. An example whose `session.add()` is in one chunk and whose
   `commit()` is in the next demonstrates work that never persists. That is the exact shape of
   this repo's own `cascade_backrefs` finding: no exception, no error, the INSERT simply never
   happens.
2. **The version tell lives in the code, not the prose.** `session.query(User)` versus
   `session.execute(select(User))` *is* the 1.4/2.0 difference. Separate a code block from the
   heading that dates it and an unlabelled snippet enters an index that holds both versions on
   purpose (`D10`).
3. **It is not a corner case.** Three quarters of the index has code in it:

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

The honest statement is therefore **"at least 11 of 3077 boundaries sever a code block, and the
looser count is inflated by glossary formatting"** — not a single confident figure. A regex is
not an reStructuredText parser and the gap between 11 and 96 is where that shows.

**The worked example is unambiguous.** `core/operators.rst`, chunks `c00233` (chars 85→1528) and
`c00234` (1529→3243) — adjacent, **zero overlap**:

```
c00233 ends                            c00234 begins
──────────────────────────────────     ──────────────────────────────────
    ...     addresses = relationship(      >>> class Address(Base):
    ...         "Address",                 ...     __tablename__ = "address"
    ...         back_populates="user")     ...     id = Column(Integer, ...)
    ...     def __repr__(self):            ...     user_id = Column(
    ...         return f"User(...)"        ...         Integer, ForeignKey(...))
```

One doctest session in the source, cut in half. Both halves are valid Python. And chunk `c00233`
declares `relationship("Address", back_populates="user")` — pointing at a class that exists only
in `c00234`. Retrieve the first without the second and the answer is a mapping that cannot work,
presented as a complete example.

**The contrast that makes the point.** Two prose boundaries from the Step 2 sample behave
differently, and the difference is instructive:

| chunk | boundary | what happens |
|---|---|---|
| `c03012` (28814→29201) | next chunk `c03013` starts at **28953** — *inside* it | overlap repaired it. The paragraph and its list both live in `c03013`. The content is not lost; `c03012` is just a bad chunk |
| `c00138` (7880→8297) | previous chunk `c00137` ends at **exactly 7880** | zero overlap. It opens *"While the above example is against…"* and the example is in a chunk that does not overlap it. **Nothing recovers this one** |

Overlap is by whole block, not by character (`D33`, `D34`) — which is why it covers some
boundaries completely and others not at all.

#### Say this

> Because you can see a broken paragraph and you can't see broken code. A truncated sentence ends
> on a colon; a truncated code example is still valid Python with correct indentation and looks
> deliberate. Nothing downstream can tell — it embeds, scores and retrieves like any other chunk.
> And this system's output is code someone pastes, so a half-example becomes advice that doesn't
> run, or runs and silently does nothing, which is the same failure shape as the
> `cascade_backrefs` breakage I documented. I measured it rather than assumed it: at least 11 of
> my 3077 chunk boundaries sever a code block with no overlap to repair it — including one that
> cuts a doctest between two mapped classes, where the first half declares a relationship to a
> class that's only in the second half. Both halves look complete.

#### Do not say

- *"The model can only see the retrieved chunk, not the whole document."* — True of every chunk
  in the index, including prose. It cannot explain why **code** is worse, which is the question.
- *"It loses context."* — So does every chunk boundary. The word doing the work is **silently**.

#### The follow-up

**"So detect it and fix the chunker."** The answer is that detecting it is harder than it sounds,
and this file's own 96-versus-11 correction is the demonstration: a regex over indentation
mistakes a glossary for a code listing. Doing it properly needs an RST parser, which is a real
piece of work rather than a guard clause — and that is a defensible reason for it to be open
rather than done.

---

### R5.4 Q4 — "Dense retrieval missed a question containing an exact symbol name. Why?"

#### In plain words

**An embedding matches meaning, not strings.** The exact characters of `Query.get` are the only
thing separating it from `Session.get`, and meaning-space is precisely where that difference does
not exist.

#### The mechanism

Embedding maps text to a point in 1024 dimensions. Two texts that mean nearly the same thing land
nearly in the same place — that is the entire value of the technique, and it is also the defect.
A rare, exact identifier is the **highest-precision signal in the question**, and it is the signal
dense retrieval is structurally worst at, because there is no channel in the model where the
literal characters are compared.

```
   MEANING SPACE (what dense search uses)     STRING SPACE (what it has none of)

        Query.get()  ●                            Query.get()
                      ● Session.get()             │││││││││││
                                                  Session.get()
        ~indistinguishable: both are              ▲
        "fetch one row by primary key"            9 of 13 characters differ.
                                                  The distinction is entirely
                                                  here, and dense search has
                                                  no way to look here.
```

#### The evidence

`backref` appears in **80 chunks** — it is one of the most common symbols in the corpus — and
dense retrieval still placed the first containing chunk at **rank 6**, one place below the cut
(§R4.3, table reproduced in R5.1 above). Whatever went wrong there, scarcity was not it.

And `table_names`, at rank 23, has a different shape again: its returned top-5 scored `+0.001`
and `+0.000` over noise. Search did not rank the answer low — it found nothing at all and filled
five slots with near-random text. Reranking a list of noise cannot help; keyword search can.

#### Say this

> Because an embedding matches meaning, not strings. `Query.get` and `Session.get` mean almost
> exactly the same thing, so they sit almost on top of each other in the vector space, and the
> only thing that distinguishes them is the literal characters — which is the one thing dense
> retrieval has no channel for. That's the argument for hybrid search: BM25 adds the missing
> channel. It's not that a bigger embedding model would fix it.

#### Do not say

- *"Because the symbol is rare in the docs."* — This is the most attractive wrong answer, and it
  is wrong in an instructive way: **rarity is an IDF concept.** It is the thing that makes BM25
  work — the *fix*. A dense retriever holds no term-frequency statistics anywhere; there is
  nothing for rarity to act on. Using it to explain the failure imports the cure's mechanism into
  the diagnosis. The follow-up — *"where in the embedding does rarity appear?"* — has no answer,
  because it does not appear.
- *"It needs a better embedding model."* — `D32` measured a model 25× smaller matching the
  shipped one. The gap is not capacity; it is the absence of a lexical channel.

#### The follow-up

**"Where in the embedding does rarity appear?"** — asked of anyone who reaches for scarcity. And
for the correct answer: **"So a bigger model would fix it?"** No. The channel is missing, not
undersized.

---

### R5.5 Q5 — "How do you know the answer came from the sources and was not invented?"

#### In plain words

From the answer alone, you do not. A citation is text the model generated, exactly like the rest
of the answer. What this system provides is not proof of grounding — it is a **cheap path for a
human to check**, plus nineteen answers where a human walked that path.

#### The mechanism

There is no automatic grounding check anywhere in Phase 1. The one mechanical signal that exists
is narrower than it sounds:

```python
# rag/probe.py:179
"uncited": not citations and len(answer.split()) > 15,
```

That detects the **absence of an `[n]` marker** in a substantial answer. It never opens the cited
chunk. Nothing in the pipeline compares a claim against the source it cites.

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

`char_start` / `char_end` are not bookkeeping. They are the only mechanical link between a claim
and the exact place its evidence should be, and they were **missing until 2026-08-15** — chunks
carried `n_chars`, a length, which names a file but not a place in it.

#### The evidence — citation and correctness are independent, and it is measured

The nineteen hand-written verdicts contain counterexamples in **both** directions:

| | verdict | note |
|---|---|---|
| **Q1** | `PARTIAL` | *"Names `aliased` and **cites the right migration section**, but omits its second argument… the same query returns `['a','e']` instead of `['a']`"* |
| **Q2** | `CORRECT` | *"emits SQL byte-identical to BREAKAGES #13's fix; **the only flaw is `uncited`**, so a reader cannot check it without running it"* |
| **Q12** | `PARTIAL` | *"the ordered steps match the migration guide, but **the answer cites nothing**… and ordering is the whole content of this question"* |
| **Q16** | `WRONG` | *"An `absent` question that did NOT refuse… from real text, and **cited nothing**"* |

**Q1 cites correctly and is wrong. Q2 cites nothing and is right.** A citation is neither
necessary nor sufficient for a grounded answer in this system, and that is a measurement rather
than an argument.

What does establish it is human verification, recorded so a regeneration cannot destroy it:

```
# runnable: uv run python -c "import json,collections; d=json.load(open('deliverables/verdicts.json')); v=[x[0] for k,x in d.items() if not k.startswith('_')]; print(len(v), 'verdicts:', dict(collections.Counter(v)))"
19 verdicts: {'PARTIAL': 3, 'CORRECT': 10, 'WRONG': 6}
```

```
# runnable: uv run python -m tools.apply_verdicts --check
in sync: 19 verdicts
```

Two design decisions sit behind those two commands:

- **`D06` — the golden dataset is hand-verified, never auto-generated.** A model scoring its own
  output measures self-consistency and reports it as truth.
- **`D46` — the script records signals; a human writes the verdicts.** `probe.py` computes
  `refused`, `uncited`, `version_mixed`, `symbol_missing`, `single_source`. **None of them is
  automatically a failure** — `refused` is the *correct* output for a question the corpus cannot
  answer. They say where to look, not what is true.

The verdicts live in `deliverables/verdicts.json` rather than in the generated `FAILURES.md`,
because `probe.py` generates that file — and before the split, regenerating it overwrote all
nineteen human judgements with `UNVERIFIED` and reported nothing.

**`D50` went one step further** on the fix side: every fix in `BREAKAGES.md` verified twice —
that it runs against real 2.0.51, and that the documentation recommends it. Twelve of thirteen
passed both; the one miss is `has_table`, which is the API-reference hole from R5.2 arriving from
a third direction.

#### Say this

> Strictly, from the answer alone I don't — and I think that's the honest starting point. A
> citation is generated text like everything else; my `uncited` signal only detects the *absence*
> of a citation marker, it never opens the chunk. Nothing in the pipeline checks that a cited
> source supports the claim. What the system does instead is make checking cheap: every answer
> prints the chunks it was given, and every chunk carries its source file, heading path and
> character offsets, so anyone can open the original at that exact position. Then a human walks
> that link — I hand-verified all nineteen probe answers against real SQLAlchemy 2.0.51, ten
> correct, three partial, six wrong, never auto-graded, because a model scoring its own output
> measures self-consistency. And the verdicts prove citations aren't the mechanism: one answer
> cites the right section and is still wrong, another cites nothing and is exactly right.

#### Do not say

- *"Because it has citations."* — The answer this question is built to catch, and the repo's own
  verdicts refute it in both directions.
- *"Because the prompt tells it to only use the sources."* — `11-GENERATION.md` §R3 measured four
  wordings of that instruction across 19 questions. Prompt C, permitted to answer freely,
  fabricates. Prompt D at `k=5` is the only configuration measured with zero prompt errors — and
  even it has two questions (Q18, Q19) that refuse with the answer sitting in the prompt. The
  instruction is a real lever and it is not a guarantee.

#### The follow-up

**"And if it cites a chunk that doesn't say that?"** A weak answer ends here. The strong answer
already conceded it, named the offsets as the check, and has the Q1 verdict ready as the case
where it happened.

---

### R5.6 The five on one page

For revision. Each line is the compressed claim; the section above it is why the claim holds.

| | the one sentence |
|---|---|
| **Q1** | Dense-only on purpose, so the fixes answer measured failures — and the measurement split one expected fix into four, one of which was a constant being wrong |
| **Q2** | 270 files, narrative docs from two git tags; `BREAKAGES.md` out because it is Phase 2's answer key, and the API reference absent because it is generated at build time — which is a permanent ceiling, not a retrieval bug |
| **Q3** | Broken prose is visible and broken code is not; at least 11 of 3077 boundaries sever a code block, including one splitting a doctest between two mapped classes |
| **Q4** | An embedding matches meaning, not strings — and `backref` at rank 6 despite 80 chunks proves scarcity is not the mechanism |
| **Q5** | From the answer alone you cannot; offsets make checking cheap and a human checked all nineteen — one verdict cites correctly and is wrong, another cites nothing and is right |

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
