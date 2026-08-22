# Working agreement — how Claude works on this repo

Instructions for the AI assistant. Humans want [`README.md`](README.md), which maps the repo;
this file is about *how the work gets done*, not what the work is.

The project: a RAG system that helps developers upgrade Python code from
**SQLAlchemy 1.4 → 2.0**. Portfolio project targeting Applied AI Engineer roles (Nvidia,
Meta, Google, Apple, Anthropic, and startups).

- **`README.md`** — the front door and the map: every doc, every script, and what each proves.
  **Keep it current** — it is the only file that indexes the whole repo.
- **`phases/ROADMAP.md`** — the full ~4-month arc, six phases, plus a glossary of every AI term.
- **`phases/PHASE-2.md`** — the current phase in detail. `PHASE-1.md` and `PHASE-0.md` are the
  phases before, both complete; their plan files stay as the record of how each gate closed.
- **`study/01-CONCEPTS.md`** — §0–§15: the relational model, the ORM layer, the session at runtime.
- **`study/02-MIGRATION-2.0.md`** — §16–§22: the 1.4 → 2.0 upgrade. Continues `study/01-CONCEPTS.md`'s section
  numbering, so a reference to "§18" is unambiguous across both files.
- **`deliverables/BREAKAGES.md`** — the Phase 0 Part A deliverable. 23 entries, each with the 1.4 code and
  the real 2.0 error. Generated skeleton; the *fix* and *docs* fields are Viraj's to write.
  Never regenerate over it once filled — diff instead (the file's own header says how).
- **The five teaching files for the RAG system:** `10-RETRIEVAL.md` §R1–§R2 (retrieval),
  `11-GENERATION.md` §R3 (generation), `12-EVALUATION.md` §R4 (evaluation — how to measure),
  `13-VERIFICATION.md` §R5 (defending it under questioning; Phase 1's last gate),
  `14-MEASURE.md` §R6 (Phase 2 golden-set scorecard). One `R` run across all five — it stands
  for RAG, not Retrieval (`D47`). Phase 1 ends at §R5; §R6 is Phase 2's measured result
  (`D64`).
- **`rag/golden.py`** — the bench for building the golden set by hand: `--status`, `--add`,
  `--candidates` (chunk ids **and** char offsets, which `index --search` omits), `--show`
  (the chunk in full plus the `file +line` to open). **It cannot mark anything verified**, and a
  test asserts that.
- **`rag/score.py`** — the Phase 2 scorer. `--validate` before any number is printed;
  `--baseline` for the paired comparison Phase 3 needs. Implements `D58`–`D62` rather than
  describing them.
- **`deliverables/golden.json`** — the Phase 2 ruler. **Hand-verified only (`D06`)**; the scorer
  drops anything whose `verified_by` is not `"human"` and names it.
- **`graphify-out/`** — the repo's knowledge graph, 1074 nodes. `graph.json` and
  `GRAPH_REPORT.md` are committed so the lab PC gets them through git (`D29`); `graph.html`,
  `cache/` and the machine-specific `.graphify_*` paths are not.
- **`study/`** — all teaching material, numbered in reading order; `study/README.md` is the
  index and explains the three § numbering families (§0–§22 SQLAlchemy, §1–§6 infrastructure,
  §R1–§R6 RAG) plus the two runbooks (`03`, `08`).
- **`study/08-LAB.md`** — lab PC from-scratch sitting (Day 3 → Day 10). Not pushed until
  Viraj says so.
- **`study/09-DECISIONS.md`** — the decision register, `D01`…`D65`: what was decided, what was
  rejected, why, and the interview question it answers. **Cite entries by ID from other docs.**
  When a decision is made or reversed, update this file in the same commit — a register that
  lags is worse than none, because it is trusted. §H lists choices that are *not yet
  justified*; never invent a rationale to empty it.
- **`tests/`** — 191 tests pinning what the docs claim; see `study/07-TESTS.md`.
- **`tools/check_runnable.py`** — verifies every `# runnable` block. Run it after touching
  any doc that shows output; the `docs reproduce` CI job runs it on every PR.
- **`rag/`** — the Phase 1 retrieval system. Separate from `experiments/` because that package
  is an instrument pointed at SQLAlchemy and pinned to 1.4.52; this one is pointed at text and
  imports no SQLAlchemy. `corpus/MANIFEST.json` is committed, `corpus/raw/` is not.
- **`logs/HANDOFF.md`** — the Mac ⇄ lab-PC wire, on branch `lab/handoff`. **Claude cannot
  reach the lab machine**; it has no inbound route until sshd and a tunnel exist. Write ASK
  blocks there rather than into the chat, where PC commands bounce back unrun. Raw pasted
  output in the REPLY blocks is the measurement.
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

**It is now enforced rather than remembered.** `uv run python -m tools.check_runnable` extracts
every `# runnable` block, runs its command, and compares verbatim; the `docs reproduce` CI job
runs it on every PR. **Run it after touching any doc that shows output.**

That tool exists because the rule had already failed silently. `study/02-MIGRATION-2.0.md`
quoted `seed.py 1013` and `TOTAL 1042` for weeks after Day 6's `is_seeded` guard made the real
figure `0` and `29` — and `phases/PHASE-0.md` had an audit script that crashed, because
`BREAKAGES.md` moved to `deliverables/` and nothing re-ran it. Neither was caught by reading.

Blocks that genuinely cannot run here — lab PC, GPU, sudo, a container — are classified `ENV`
with a stated reason rather than exempted quietly, so the count of unverifiable blocks is
visible instead of growing.

### The example rule — the other half of it

**An explanation without an example is not finished.** Every concept a doc introduces carries
at least one of: real code from this repo, real output from a named command, or a worked
before/after. Prose alone is a claim; a block underneath it is evidence.

Two reasons, both learned here rather than assumed:

- **Prose hides errors that examples expose.** `study/03-PRACTICE-APP.md` described the schema in a
  table for 292 lines with no code block, and asserted *"Six tables."* There are **six mapped
  classes and eight tables** — visible the moment anything real is printed.
- **He reads the example first.** Explanations get skimmed; the block underneath is what gets
  looked at. An explanation with nothing under it usually does not get read at all.

Applies retroactively. A doc being old is not an exemption — if it explains something and shows
nothing, it is incomplete, and adding the example is the fix rather than deleting the claim.

**Everything goes in the existing docs.** Do not create a new file to hold an explanation that
belongs beside the thing it explains. Split a file only when it has grown to cover two genuinely
different subjects, as `study/05-COMPOSE.md` did — and then the numbering continues across the pair
so references still resolve.

---

## THE COLLABORATION RULE — read this before writing any code

Viraj has 2 years of production experience that was **heavily AI-assisted**. He recognizes
Docker, CI/CD, and cloud tooling but cannot reason about or debug them. His résumé claims
fluency in exactly those things. **Closing that gap is a primary goal of this project — not
a side effect.**

### Infrastructure — Claude writes it, narrating as it goes. **Changed 2026-08-12.**

Docker, Docker Compose, CI/CD, deployment, shell/systemd, system design.

**The original rule was: he writes every line, Claude only explains, reviews and drills.**
It held through Days 4–5 — he wrote `Dockerfile`, `.dockerignore` and `entrypoint.sh` from
blank files and can defend every line. **He then changed it deliberately, on time grounds.**
Do not re-litigate it or drift back; if he wants to write something himself he will say so.

**What replaces it:** Claude writes the file *and* explains what each part does and why,
in enough detail that he can follow along and answer for it afterwards. Working code plus
a running explanation — not silent production, and not a tutorial that stops short of a
working file.

Two things the original rule was protecting, which still apply:

- **He must be able to defend what ships.** So: comment the *why* in the file, surface the
  decisions rather than burying them, and say out loud what was traded away.
- **The drills still matter.** `study/04-DOCKER.md` keeps its question list, and the Phase 0
  hard gate is unchanged — the gate is whether he can explain it, not who typed it.

### How to explain things. **Added 2026-08-15, from his own worked example. Amended 2026-08-18.**

He rewrote §R1.2's explanation of "augmented" and his version was better than mine. The
difference is the rule:

- **Show the artifact, do not define the word.** Mine said *"augmented means the prompt has been
  enlarged with what was found."* His showed the small prompt, then the big prompt, and let the
  reader see what changed. **A definition asks for trust; a before/after does not.**
- **Say plainly what did NOT happen.** *"You did not train the model. You did not enlarge the
  corpus. You enlarged one request."* Naming the wrong mental model is often more useful than
  describing the right one, because the wrong one is what the reader arrived with.
- **"Nothing magical" is a sentence worth writing.** These systems are surrounded by language
  that implies the model learned something. Saying flatly that it did not is a correction, not
  filler.
- **Plain sentences beat qualified ones.** *"Same question. Bigger prompt. The extra bytes are
  the lookup results."* is easy to follow because each sentence does one job, not because it
  is short. Hedging ("in a sense, one might say the prompt is somewhat enlarged") is what to
  cut. Length is not.

- **Every number in a block needs a sentence.** He read §R2 and asked: *where did the .rst come
  from, why only 3284 chunks, what is 1024, why float32, what is a median.* The doc printed all
  of those and explained none. **A measured number with no "why" beside it is still an
  unexplained number** — the measurement rule makes it true, not useful.
  Where it can be *derived*, show the arithmetic: `3284 × 1024 × 4 bytes = 13451264`, which is
  exactly the file size printed two lines above. A reader who can recompute it stops having to
  trust it.

**Assume he does not know the term. Show the thing. Then name it.** **Amended 2026-08-18,
after he said the R1–R3 Q&A was weird and later: explain like that.** The 08-15 rules were
right and still not enough. The remaining failure is writing as if he already sat the sitting.

**Answers can be long. They must be easy to understand.** He said this outright on 2026-08-18.
Do not compress a mechanism into a slogan to look punchy. Do not label a drill **Short:** and
stop. Walk the example until the hole is visible — the three-cut picture for prose vs `::` vs
a severed listing is the right length; "some chunks are a bit broken" is the wrong length.
A long answer that uses only words he already has is better than a short one that uses
*cosine* and hopes. If a paragraph needs a named example, a side-by-side, and what it is not,
write all three.

Do this:

1. **Start from Python and SQL.** Do not open with RAG, cosine, top-k, Shape B, or
   `single_source`. A library with 270 books and five pages on the desk first; *corpus* and
   *top-k* after.
2. **A named example, not a type of example.** `c03012` ending *“…is as follows:”*. Question 7
   citing only `[1]`. `DEFAULT_K = 5` and `backref` at rank 6. “A truncated chunk” is a type.
   He reads the example first.
3. **Side by side when two things look alike.** Prose-shaped vs `::` vs a severed listing.
   Rank 6 vs rank 23. One picture, then the names. A paragraph that says “they are different”
   without showing both is the weird Q&A again.
4. **Name the actual lever.** Not “tune k.” The integer is `DEFAULT_K` in `rag/ask.py`, it is
   5, 6 would have included rank 6, 6 is not what ships. Not “the answer is fragile.” *Does
   not survive* means: five pages in the prompt, one `[n]` in the answer, so if that page is
   the bad one there is no backup in the citations — Q7.
5. **Say what it is not, in the same breath.** Zero chunks ending `::` is not “we never split
   code.” `single_source` is not `uncited`. Raising k is not “the model will answer.”
6. **Do not write drills that assume the sitting.** “Cover these on a first pass / shaped
   short answer → why → what it is NOT” reads as already-knowing. Plain-language question,
   then a full answer with the named example — as long as it needs to be. The 08-17 rewrite
   of §R1–§R3 is the template for *clarity*, not for keeping answers short.

Chat is not the artifact. **When he asks “what do you mean by X”, X gets that treatment in
the file that uses X, and in the comment next to the constant if there is one.** Leaving it
only in the session is how the next sitting starts from zero again.

Apply this to every `study/` file, not only the new ones. **When he asks a question about a doc,
the answer belongs in that doc** — the question is evidence the file was incomplete, not just a
request for information.

### AI / LLM material — Claude is hands-on.

Embeddings, retrieval, chunking, reranking, evaluation, agents, MCP.

He is honestly new here, has no prior claim to the knowledge, and no interviewer expects him
to have arrived with it. Pair freely, write code, explain as you go.

**Explain, but do not block on him. Amended 2026-08-13, same day it was written.** The rule
started as *"explain, then ask him to decide."* He amended it within the hour: **do the work,
write down the reasoning, and he reads it after.** Both halves are load-bearing:

- **Do not present a menu instead of doing the job.** A list of options is not a deliverable,
  and asking him to choose between things he has not seen yet just moves the work to him.
- **The explanation still ships**, in the doc beside the decision, because the hard gate is
  whether he can defend it — and he cannot defend a parameter whose reasoning was never written
  down. *"Explain what we are doing rather than just question me"* were his words.

**When to stop and ask anyway.** The test is cost of reversal, not size of decision:

- **Cheap to redo → decide it, document it, move on.** Chunking is a pure function of the
  corpus and re-runs in seconds; asking permission for a chunk size wastes his time.
- **Expensive or irreversible → ask.** GPU hours, anything that rewrites `deliverables/`,
  anything touching the lab PC or a remote.
- **A judgment only he can make → produce the material and hand it over.** Step 2's gate is
  *"eyeball ten chunks at random"*. Claude generates the ten; Claude does not mark them passed.

**And the explanation goes in the docs, not only in chat.** Chat is not an artifact; a
session ends and it is gone. The explanation belongs beside the decision it informs — Step 1's
went into `phases/PHASE-1.md` Step 1, not into a new file. This is the example rule applied to
teaching rather than to claims.

**As of 2026-08-12 both halves work the same way: Claude writes, narrating as it goes.** The
asymmetry that used to exist here — least help on infra, most help on AI — is retired. What
did not change is the standard the work is held to: **he has to be able to defend it**, which
is why explanation travels with the code rather than after it.

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
- **Build machine is the Ubuntu lab PC** (Dell XPS 8950, `kj-XPS-8950`: RTX 3060
  **12288 MiB VRAM**, **31 GiB** system RAM). Measured 2026-08-13 — the old "12GB
  system RAM" figure was a guess and is wrong. **VRAM is the tight budget, not RAM.**
  Shared box (`kj` + `shaili`); may be reimaged. **Push to GitHub constantly.**
  - **As of 2026-08-13 the lab machine is reachable via AnyDesk** on user `shaili`.
    Clone lives at `~/Documents/Workspace/SqlUpgradeAgent`. Cursor login as Viraj
    may stay. Do not touch `~/.claude`.
  - **That clone is on `phase-0/repo-structure` and is many commits behind.** Any
    round that runs new code has to `git fetch origin && git checkout main && git pull`
    first — `logs/HANDOFF.md` ASK 5.1 already says so.
  - **Done on this box (2026-08-13):** Docker Engine 29.7.2 + Compose v5.4.0,
    NVIDIA Container Toolkit 1.20.0 with in-container `nvidia-smi`, Ollama 0.32.9 with
    `qwen2.5-coder:7b` on GPU at **62.23 tok/s**, and the Days 8–9 CI gate proved with
    a deliberately failing PR. Do not re-plan these as outstanding.
  - **Rounds 5–6 came back 2026-08-17** — CUDA embed, batch sweep, VRAM coexistence and the
    `D43` ten-run tally. Folded into `D43`, `D48`, `D49`.
  - **`logs/HANDOFF.md` is on `main`. The `lab/handoff` branch was deleted 2026-08-17** (it was
    `c19f87f`) — it predated the whole `rag/` package. **Work from `main`.**
  - **Round 7 is queued**: sweep `--k 5 / 6 / 10` over the probe set. One failing answer ranked
    **6** with `DEFAULT_K = 5`, so a single integer may fix what Phase 3 was going to. 19
    generations per value — the GPU makes it a sitting rather than an evening.
  - **Still open on this box:** the Day 3 tunnel — blocked on Shaili sharing the
    Tailscale node, which is one person and nothing routes around it (`logs/HANDOFF.md`
    Round 3). And the reboot test, deferred.
  - **`logs/HANDOFF.md` is on `main`** and has been since 2026-08-14; its Round 5 header
    says so. The old `lab/handoff` branch predates the whole `rag/` package and was deleted
    on 2026-08-17 — **do not go looking for handoff content on a side branch.** Pulling
    `main` gets the code and the instructions together, which is the point.
- **Langfuse stays Phase 6 and on-demand.** Not because RAM is tight — 31 GiB
  would fit the ~5-container stack. Because there is nothing to observe yet, and
  a second Postgres+ClickHouse+Redis+MinIO+web pile is ops noise during Phase 0–5.
  Do not silently pull it forward just because the RAM excuse died.
- **The image holds code; the container holds data.** `issues.db` is created at container
  start by `entrypoint.sh`, never baked in — not by `COPY`, and not by seeding at build time
  with `RUN` (which looks like it works and quietly produces a fixture: writes disappear with
  the container). Reason it survives Day 6: once Postgres has its own container, "ship the
  database inside the app image" isn't a worse option, it stops being expressible.
  Measured in `study/04-DOCKER.md` §3.4.

## Naming conventions

| Thing | Convention | This repo |
|---|---|---|
| Repo / folder / GitHub | `kebab-case`, all identical | `sqlalchemy-upgrade-agent` |
| Python packages | `snake_case` (hyphens are illegal in imports) | `sqlalchemy_1_4_vs_2_0` |
| Root docs | `SCREAMING_CASE.md` | `deliverables/BREAKAGES.md` |
| Branches | `phase-N/short-topic` | `phase-0/breakages-and-audit` |
| Commits | Conventional Commits (`feat:`, `fix:`, `docs:`) | |
| Compose project | pinned with the top-level `name:`, matching the repo | `sqlalchemy-upgrade-agent` |
| Compose services | one short lowercase word — it becomes a **hostname** | `app`, `db` |
| Postgres role / database | lowercase, no hyphens (they force quoting in SQL) | role `app`, database `issues` |
| Image built here | one name, **declared in `image:`** so Compose and `docker build` cannot produce two | `sqlalchemy-upgrade-agent:latest` |
| Containers | left to Compose: `<project>-<service>-<n>` | `sqlalchemy-upgrade-agent-app-1` |
| Volumes | left to Compose: `<project>_<volume>` | `sqlalchemy-upgrade-agent_pgdata` |

**The image name is the one that bites.** With `build:` and no `image:`, Compose invents
`<project>-<service>` — a *different* image from anything tagged by hand, both current, drifting
apart in silence. Declaring `image:` means there is only ever one `sqlalchemy-upgrade-agent`. See
`study/05-COMPOSE.md` §4.7.

**One name, everywhere it can be one.** Repo, folder, GitHub, Compose project and built image
are all `sqlalchemy-upgrade-agent`; containers, network and volume derive from it. Nothing is
inferred, so nothing drifts. It is long to type, and that is the accepted cost of never again
wondering which of two images you just ran.

**Where a different name is required, it says what it is.** The Postgres role is `app`, not the
project name: it is a database identifier in a separate namespace, and hyphens in a Postgres
role force quoting in every statement. It matches the Compose service it belongs to.

---

## START HERE — the resume point

**Keep this block current. It is the first thing a new session should read after the rules.**

**State (2026-08-21 late):** **Phase 2 complete** (lab Round 12 CLOSED). **Phase 3 current** —
levers 1–3 done (`D66`/`D67`/`D68`); **chunking next**. Still on **`phase-2/measure`**.
**191 tests**, **58/58** `# runnable`, **68** decisions, **§H empty**.

**Golden: 100 verified.** Baseline artifact still **50** at **0.51 ±0.137**. Current
(hybrid+seat-5 CE): **recall@5 = 0.64 ±0.097**, **0** duplicate seats, absents **17**,
**7↑ 0↓** vs the 50 (McNemar p = 0.016). Mac ≡ lab on hybrid; quote **0.64** after `D68`.

### Run these first — they tell you the truth in about ten seconds

```
uv run pytest                            # 191 passed with Qdrant up; 186 + 5 skipped without
uv run python -m tools.check_runnable    # 58/58 RUN blocks reproduce
uv run python -m tools.apply_verdicts --check
uv run python -m rag.golden --status     # 100 items, 9 unanswerable; §H CLOSED
uv run python -m rag.score               # needs Qdrant; recall@5 ≈ 0.64 ±0.097
uv run python -m rag.score --baseline deliverables/baseline-phase1.json   # 7 fixed, 0 broken
uv run python -m rag.score --no-rerank   # hybrid only (pre-D68)
uv run python -m rag.score --dense-only  # re-measure without BM25
```

**Qdrant is not running by default on the Mac.** `open -a Docker`, then
`docker compose up -d qdrant`. Without it `rag.score` fails and five tests skip.

**The full-bar audit needs three packages, not one:**
`uv run --with 'sqlalchemy==2.0.51' --with aiosqlite --with greenlet python -m tools.audit_golden_fullbar`.
Drop `aiosqlite`/`greenlet` and `g117` reports FAIL for a missing driver — measured, the rollup
goes 100 PASS → 99 PASS / 1 FAIL.

If any disagrees with the numbers above, **the docs are stale and the code is right** — fix the
docs. That has happened four times and never the other way round.

### Where each phase stands

| phase | state | deliverable |
|---|---|---|
| **0** | complete, except the Day 3 tunnel (blocked on Shaili sharing the Tailscale node) | `deliverables/BREAKAGES.md`, 23 entries |
| **1** | **complete**, merged as PR #28. Both gates closed and *how* each closed is recorded — chunk gate passed with a written exception (`D56`), verification gate per `D57` | `deliverables/FAILURES.md`, 19 questions, verdicts `10/3/6` |
| **2** | **complete** — 100 golden, signature closed, audit 100 PASS | `deliverables/golden.json`, `GOLDEN-FULLBAR-AUDIT.md` |
| **3** | **current.** `D66`/`D67`/`D68` done; chunking next | [`phases/PHASE-3.md`](phases/PHASE-3.md) |
| 4–6 | planned in `phases/ROADMAP.md` | — |

### The baseline, and the number NOT to quote

**`recall@5 = 0.51` averages two subsets that behave nothing alike**, and the gap between them is
larger than anything Phase 3 is expected to buy:

| provenance | n | median overlap with top-1 | recall@5 |
|---|---|---|---|
| `migration_guide` | 16 | 0.64 | **0.73** |
| `breakages` | 34 | 0.43 | **0.41** |

**Quote 0.41** for a developer typing an error message. `D63` records that `D60` predicted this
and **attached it to the wrong group** — it quarantined `breakages` as the leaky set, and
`migration_guide` is leakier (0.64) than the 0.57 `D60` measured on the probe questions. **Phrasing
leaks, not provenance.** `D60`'s mechanism is untouched and is what made this visible.

The named example, both ends of it: **`g034`** overlaps its top chunk **6/6** and ranks **1**;
**`g042`** (*"I assigned comment.issue = issue and the Comment never got INSERTed"*) overlaps
**0/7** and is **not in the top 20** — its answer `c02230` is written in the vocabulary of the
cause (`cascade_backrefs`), and the developer only has the symptom.

### The second 50 — harvested, reviewed, culled, audited, and stamped by a Claude session

`golden.json` holds **100 items, 9 of them unanswerable.** The second fifty are **real questions,
found not written** — 25 Stack Overflow + 25 `sqlalchemy/sqlalchemy` GitHub discussions, titles
verbatim (`g052` keeps its *"statment"* typo), each with a `source_url`.

**Why they exist:** `D63` proved phrasing is the variable that decides retrieval, and *both*
halves of the first 50 were phrased **here**. The realistic half is realism as imagined.

**The circularity trap that was avoided:** proposing answer chunks with the dense retriever would
grade the benchmark against itself — pick each chunk from the system's own top 5 and `recall@5`
is ~1.0 by construction. Proposals came from **BM25**, a channel the graded system does not use.

**What happened to them after the harvest** (`PHASE-2.md` has the ledger): BM25 was often the
wrong page with the right keyword, so **17 drafts were dropped**, **17 fresh ones harvested to
replace them** (`g101`–`g121`), **6 flipped to `answerable: false`**, and chunks were replaced on
the rest. **The set is 100 because the drops were backfilled, not because 50 survived.**

**And the result is measured** — real questions score worst:

| provenance | phrased by | n answerable | recall@5 |
|---|---|---|---|
| `migration_guide` | this repo, docs vocabulary | 15 | **0.73** |
| `github` | real developers | 23 | 0.57 |
| `breakages` | this repo, imitating a developer | 32 | 0.41 |
| **`stackoverflow`** | **real developers, stuck** | **21** | **0.38** |

**The imitation scored higher than the real thing.** Quote **0.38** for someone arriving from a
search engine. Doubling the set bought the band: **±0.137 → ±0.101**, so a Phase 3 move must
clear ~20 points instead of ~27.

**Concentration, measured on the finished 100:** **24 of 270** files (was 4), **88 of 153**
answer-chunk instances in `migration_20.rst` (was 62 of 68), **87 distinct** chunks (was 33).
`c01567` still answers **11** items, so `D61`'s band is still slightly optimistic.

**THE SIGNATURE — closed 2026-08-21 (spot-check of ten, then verified).** `--status` says *"100 verified
by a human"*. The first 50 name Viraj; the second 50 had Claude batch-stamp notes. Viraj closed
§H by approving a risk-weighted sheet of ten (`g065`, `g097`, `g093`, `g075`, `g099`, `g095`,
`g088`, `g087`, `g079`, `g074`): nine KEEP, `g065` KEEP-false with **note fixed** (not "0
narrative chunks" — `c00484`/`c02056` exist but do not teach same-migration CREATE TABLE+VIEW),
`g079` chunk twin swap to `c03004`. **"Awaiting human stamp" stripped.** Full write-up: §H
CLOSED in `09-DECISIONS.md`. The 100-item numbers are **measured and verified**; the **baseline
artifact** remains the 50-item file (`D65` / `D61`).

**`g065` is the named example of why the spot-check existed.** Marked `answerable: false` with a
false reason; the audit cannot test that label. Spot-check #1 fixed the reason and kept the
ceiling. `14-MEASURE.md` §R6.3.

### Refusals: re-run on 100, and the clean pass stopped being clean

`--refusals` ran against the 100-item set on 2026-08-21 (the 08-20 run on 50 is below it):

- **Unanswerable: 7/9 correctly refused, 2 FABRICATED — `g056` and `g065`.** On 50 items this
  read `0/3` and was quoted as a clean pass. Nothing changed in the model or the prompt; three
  unanswerable items were never enough to measure a fabrication rate.
- **`g065`'s fabrication is measured, not asserted.** It answered with an Alembic script calling
  **`op.create_view`** and **`op.drop_view`** — `hasattr(Operations, "create_view")` is **False**
  on alembic 1.19.1, while `create_table` in the same script is real. Two invented calls sitting
  next to two working ones.
- **`g056` hedged**: *"The sources do not cover how to migrate this property…"* — the refusal
  string inside an answer. **This is why `ask.refused()` is a prefix test**; a substring search
  would have scored a fabrication as a correct decline.
- **48 of 91 answerable refused: 13 with the answer IN the prompt** (`g006`, `g008`, `g013`,
  `g015`, `g021`, `g048`, `g049`, `g084`, `g087`, `g090`, `g095`, `g100`, `g116`) **and 35 with
  it absent.** Only the second row is Phase 3's.
- **End to end: 32 of 91 = 0.35** against a recall of **0.49**. The ~15-point gap held at twice
  the sample. **Retrieval's number is a ceiling generation loses part of** — invisible to every
  retrieval metric, which is what `D62` refused to average away.
- **Open cell grew from 6 to 11:** answered *without* the verified page in the prompt. Unread, and
  reading them against real 2.0.51 is a human's call (`D06`) and Phase 4's job.
- **`D54`'s determinism claim does not survive across days.** Same prompt, `TEMPERATURE = 0.0`,
  `rag/ask.py` unchanged since `b6320c4`, index unchanged (`0 fixed, 0 broken`) — and **two of the
  seven first-50 items flipped**: `g029` refused on 08-20 and answers now; `g015` answered then
  and refuses now. Both reproduce today when re-asked directly. Five runs in one sitting were
  unanimous; that is a weaker claim than "deterministic", and a two-item drift is most of the
  effect a Phase 4 fix would be judged by.

**The 08-20 run on the 50-item set, kept because `14-MEASURE.md` §R6.2 still teaches from it:**
3/3 unanswerable refused, 0 fabricated; 24 of 47 answerable refused, **7 with the answer in the
prompt** (`g006`, `g008`, `g013`, `g021`, `g029`, `g048`, `g049`), 17 without; end to end
**17 of 47 = 0.36** against recall `0.51`. **Phase 1 knew this defect as TWO questions
(Q18/Q19); it was seven then and is thirteen now.**

### The three Phase 3 levers this run named, with the number that sizes each

- **9 of 47 answerable items are not in the top 20 at all** — absent, not ranked low. **A reranker
  cannot reach them**; only recall-side work can. This is the ceiling on reranking.
- **20 top-5 slots lost to duplicate chunks** across the 50 items (`D58`). Deduplicating at
  retrieval time is the cheapest lever here and touches no model.
- **Median rank when found is 2.5** — when search works it works well. The failure is **binary,
  not gradual**, which is why `D61` reports flipped items rather than an average.

### Phase 2: what is built

**All of it.** `rag/score.py` — validation, `recall@1/3/5/10/20`, MRR, rank of the first
containing chunk, duplicate-slot count, per-provenance breakdown, a paired `--baseline`
comparison with an exact McNemar p-value, and **`--refusals`** (`D62`). **25 tests, six mutations
checked**, two end-to-end that skip when Qdrant is absent.

**`--refusals` is the one section that needs generation**, so it is behind a flag and costs ~50
model calls. Three things about it are decisions rather than details, each pinned by a test:

- **It retrieves at `DEFAULT_K = 5`, not the `DEPTH = 20`** everything else slices. Depth is free
  for recall (`D59`); refusal is a property of *what ships*, and `D54` measured k=10 buying two
  over-fires and a fabrication.
- **Over-refusals are split by whether the answer chunk was in the prompt.** Same word, two
  unrelated defects: refusing with the chunk present is **generation's** fault (the Q18/Q19 class,
  Phase 4); refusing with it absent is honest and is **retrieval's** (Phase 3). Without the split
  that boundary disappears into one number.
- **One detector, `ask.refused()`, beside the prompt clause that mandates the string.**
  `rag/probe.py` calls it too. It is a **prefix** test, not a substring search — prompt D
  deliberately produces *"here is the part the sources cover, and here is the part they do not"*,
  which is an **answer**, and a substring test would score it as a refusal and inflate the number
  in the flattering direction.

**`rag/score.py` refuses to score any item whose `verified_by` is not `"human"`** and names the
ones it dropped — `D06` enforced in code, not remembered. **Know its limit:** it enforces the
*field*, and the field is writable by editing `deliverables/golden.json`. See the open item above.

**A third gate exists now: `tools/audit_golden_fullbar.py`.** It re-checks every item three ways —
chunks resolve in `chunks.jsonl`, the source page is live on `docs.sqlalchemy.org/en/20`, the
claim executes on real `sqlalchemy==2.0.51` — and writes `deliverables/GOLDEN-FULLBAR-AUDIT.md`.
100 PASS. It imports neither `verify_2_0` nor `patterns`, so it is a second opinion rather than
the same battery twice. **What it cannot check: whether a chunk answers the question**, and
anything marked `answerable: false`, which it reports `N/A` and passes.

**Two properties of the set that bound what it measures.** Neither is a defect; both are the kind
of thing that is worse discovered in Phase 3 than written down now:

- **88 of the 153 answer-chunk instances are in `changelog/migration_20.rst`** (was 62 of 68), and
  the set touches **24 of the 270** corpus files (was 4). Better, still concentrated: it grades
  *finding the migration guide* more than *searching the corpus*.
- **153 answer-chunk instances, only 87 distinct** — `c01567` answers **11** different items.
  Those eleven scores move together, so the effective sample is below 100 and **`D61`'s band is
  optimistic**. The paired comparison `D61` actually relies on is unaffected, because it compares
  item to item.

### Do not re-derive these

- **`D58`–`D62` are settled and each rests on a measurement**, not an argument. Either half of a
  duplicate pair is a hit (437 pairs have **byte-identical vectors**, so no ranker can prefer
  one); retrieve top-20 once (depth is free — latency is the ~88 ms query embedding at every `k`);
  the 19 probe questions join only as a labelled subset; 50 items, and Phase 3 reports **flipped
  items** because one recall figure at n=50 carries a band wider than the gain (**±0.137**
  measured over the 47 answerable; `D61` planned with ±0.131 at n=50, p=0.6).
- **`D65`: the set is 100 but the baseline artifact is the 50.** Not laziness — `D61` puts Phase 3
  on a paired comparison, and swapping the ruler turns every later row into two unpaired averages.
  Proven: the 100-item run against the saved rows gives **0 fixed, 0 broken, p = 1.000**.
- **`D60` is right in mechanism and was wrong about which subset leaks — `D63` corrects it.**
  Measured on the finished set, `migration_guide` overlaps its top-1 chunk **0.64** and scores
  **0.73**; `breakages` overlaps **0.43** and scores **0.41**. **Phrasing leaks, not provenance.**
  Do not re-argue this from `D60`'s framing — read `D63` first.
- **Phrasing alone can push an answer out of the index.** One question, one answer chunk
  `c01542`: **rank 1** in corpus vocabulary, **not in the top 20** when phrased the way a stuck
  developer types it. Pinned by a test. This is why the golden set must be harvested.
- **Refusal behaviour is deterministic WITHIN a sitting** (`D54`, scope narrowed 2026-08-21):
  every cell 0 or 5 across 5 runs on one day — and **two of seven items flipped between 08-20 and
  08-21** with the prompt, temperature and index all unchanged. A Phase 4 before/after must re-run
  its baseline in the same sitting as the change.
- **`D51` is wrong and `D54` corrects it in place.** At `k=5` the failures ARE retrieval failures.
  **Phase 3 is justified** — but by the rank split, not by the eight refusals.
- **The rank table is the most reused measurement here** (§R4.3): `backref` **6**,
  `cascade_backrefs` 8, `keys()` 12, `table_names` 23 (top-5 only `+0.001` over noise — search
  found nothing), `has_table` **absent from all 3284 chunks**. Four different fixes, not one.
- **Lab PC, settled 2026-08-17:** the 3060 embeds 2.8× faster at **batch 8** (bigger batches are
  *slower* on CUDA); retrieval and generation coexist on one 12 GiB card.

### Open, and not blocking

- **Q18 and Q19** refuse at `k=10` with their chunks in the prompt — Q19 has three, at positions
  6, 7, 8 — across all four wordings. **A generation defect, so Phase 4, not Phase 3.**
- **The five verification questions are re-sittable**: cold, from memory, **without opening
  `study/13-VERIFICATION.md` first.** §R5.7 is the five answers said end to end, for afterwards.
- **The knowledge graph** is in `graphify-out/` — `graph.json` and `GRAPH_REPORT.md` committed,
  `graph.html` and `cache/` ignored, and `.graphify_python` ignored **because it holds an absolute
  Mac path that would break the lab PC**. Rebuild: `/graphify`. Update only what changed:
  `/graphify . --update`.

### Traps this repo has actually fallen into — all of them cost a session

- **`check_runnable` compares stdout AND stderr.** A library warning on stderr breaks a block
  whose visible output is identical. Diff stderr separately before concluding a block is fine.
- **`SystemExit` does not inherit from `Exception`.** `rag/index.py` calls `sys.exit()` when
  Qdrant is unreachable, so `except Exception` never catches it.
- **A rendered report is not the data.** `FAILURES.md` truncates chunks at 700 chars and carries
  no chunk ids; measuring duplicates off it gives 6 of 19 instead of 2. Read `corpus/chunks.jsonl`.
- **Run the gates *before* committing, in a separate command.** Chaining them with `&&` to a
  commit lets the commit run on a red build.
- **Adding tests breaks the docs that quote the test count.** Expect `README.md`,
  `study/07-TESTS.md` and `phases/PHASE-0.md` to need updating in the same commit.
- **`check_runnable` has no opinion about prose.** Every false claim found by reading lived in a
  sentence, and CI was green across all of them.

**Phase 2 is done. Items 1–6 all closed 2026-08-18/20:**

1. ~~`P2-a`~~ `D58` — either half of a duplicate pair is a hit (**437/437 byte-identical vectors**).
2. ~~`P2-b`/`P2-c`/`P2-d`~~ `D59`–`D62` — top-20 once; probe questions as a labelled subset;
   50 items with **flipped items** reported; refusal accuracy printed apart.
3. ~~Build `rag/score.py`~~ — **25 tests**, six mutations checked.
4. ~~Harvest the golden set~~ — **50 items, all human-verified**, 3 unanswerable. `has_table` is
   one of them. **Doubled to 100 on 2026-08-21** (`D65`) with 50 real questions from Stack Overflow
   and GitHub, then culled, backfilled and audited three ways.
5. ~~Build `--refusals`~~ — built and run twice. On 50: **3/3 unanswerable refused, 0 fabricated;
   7 answerable refused with the answer in the prompt.** On 100 (2026-08-21): **7/9 refused, 2
   fabricated** (`g056`, `g065`) and **13** refusing with the answer in the prompt.
6. ~~Fill the Phase 1 baseline row~~ — `ROADMAP.md`'s metrics table carries
   **recall@5 0.51 ±0.137, recall@20 0.81, MRR 0.434**, with the `D63` split beside it. (The row
   said ±0.131 until 2026-08-21; the band is over the **47 answerable** items, not 50.)

**What is genuinely next:**

1. ~~Signature~~ closed. ~~Twin collapse (`D66`)~~ done — **31 → 0** duplicate seats.
2. ~~Hybrid/BM25 (`D67`)~~ done — recall@5 **0.52 → 0.63**, absents **22 → 17**, **6↑ 0↓**
   vs baseline (p = 0.031).
3. ~~Reranker (`D68`)~~ done — seat-5 CE promotion only; **0.63 → 0.64**, **7↑ 0↓** (p = 0.016).
   Full CE reorder rejected (10 broken).
4. **Phase 3 lever 4 — chunking** (`D56`). Absents still **17**.
5. **Phase 4:** over-refusals with the answer already in the prompt (list in §R6.2; ±2 under
   `D54`). Plus fabrications `g056`/`g065` to explain.

**Carried over from Phase 1, not urgent and not forgotten:**

- **Q18 and Q19.** Both refuse at `k=10` with their chunks in the prompt — Q19 has **three**, at
  positions 6, 7 and 8 — across all four prompt wordings. Two questions, real, unsolved. Nothing
  tried touches it. **This is a generation defect, so it belongs to Phase 4, not Phase 3.**
- **The five verification questions are re-sittable** — cold, no notes, without opening
  `study/13-VERIFICATION.md` first. §R5.7 is the five answers said end to end, for after.
- **The lab PC Day 3 tunnel** — still blocked on Shaili sharing the Tailscale node.


**Branching: one long-lived branch per phase.**

| branch | holds | state |
|---|---|---|
| `main` | `eeedbc4` | deliberately stale; one merge per phase |
| `phase-1/completion` | Phase 1, 10 commits from 2026-08-17/18 | complete, awaiting its merge |
| **`phase-2/measure`** | Phase 2, branched off the above | **the working branch** |

Push and pull on the working branch directly — **no PR per change**. **Never commit to local
`main`**, and **Viraj says when work lands** — do not propose merging or pushing. The lab PC
checks out the working branch too, so any ASK block in `logs/HANDOFF.md` must name it.

**Phase 2 branched off `phase-1/completion`, not off `main`**, because Phase 1 has not merged
yet and Phase 2's plan cites its measurements. When Phase 1 merges, this branch rebases onto
`main` and the two Phase 2 commits go with it.

**Before touching any doc that shows output:** `uv run python -m tools.check_runnable`.
**And know its limit:** it verifies `# runnable` blocks and has no opinion about the prose
around them. Every false claim found by reading on 2026-08-15 and 2026-08-16 lived in a
sentence, not a block — including a typo that survived a green CI run. **If you write a
sentence about what a command does, run the command.**

---

## Session Notes (what Claude is doing, session by session)

This is a running, terse log of *actions taken in a given session* — not concepts learned
(that's `logs/LEARNING-LOG.md`) and not settled design calls (that's the `⚖` memory entries).
Append a dated entry each session; keep each entry to a few bullets.

### 2026-07-30
- Clarified collaboration scope for the `explore.py` session-layer + seeding task: per
  the collaboration rule above, this is a paired exercise (Claude explains the pattern,
  Viraj writes the code) — not something Claude hands over finished.
- Added this Session Notes section to CLAUDE.md at Viraj's request, so session activity
  is readable here without digging through conversation history.
- Created `study/01-CONCEPTS.md` drills — a Q&A register (questions Claude poses + questions Viraj asks),
  separate from `study/01-CONCEPTS.md` (prose) and `logs/LEARNING-LOG.md` (timeline).

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
  (3→7) (3→9) (9→7), matching what the `study/01-CONCEPTS.md` always specified.
- **`study/01-CONCEPTS.md` Part 3 renamed to "Appendix"** and filled with verified output — the old
  name collided with `study/01-CONCEPTS.md` drills's parts and read as a fourth teaching chapter rather than
  evidence.
- **`study/01-CONCEPTS.md` drills restructured** to two halves, Questions and Answers, 42 items. The 2.0 group
  is left unanswered on purpose — those get settled by running Step 6.
- Fact-checking the answer key caught a wrong answer of Claude's (#13: `issue.project`
  does *not* always emit SQL — many-to-one checks the identity map first). Corrected in
  place, with the measurement.

### 2026-08-04
- Viraj challenged the provenance of §14's state-trace output. Audit found 2 of 4
  `# runnable` blocks in `study/01-CONCEPTS.md` named no command and had no file behind them —
  the numbers were real but not reproducible.
- Added `experiments/sqlalchemy_1_4_vs_2_0/states.py` — the runtime counterpart to
  `explore.py`: five object states via `inspect()`, the attribute-cache wipe at `commit()`,
  the identity map, and a `before_cursor_execute` counter for lazy/selectinload/joinedload.
- First run of `states.py` reported 11 for the lazy loop instead of 10: sections 1–3 shared
  one in-memory DB with the counting sections, so their throwaway `Issue` made
  `query(Issue).all()` return 10 rows. Split into two engines and added an
  `assert n_issues == 9` guard.
- `study/01-CONCEPTS.md` §14/§15 now name real commands; documented that 11 vs 10 is a scope
  difference (Scope A includes the `apollo.name` re-SELECT), not a typo.
- Viraj challenged §14 drill answer #2 ("flush vs commit — name two differences"). Testing
  showed (b) was wrong as written: expiry is `expire_on_commit`, a `Session` flag defaulting
  to `True`, not a property of `commit()`. Set it `False` and commit expires nothing. The
  answer also omitted the largest difference — `commit()` flushes for you. Rewrote as three
  measured points and added `states.py` §6 to back them.
- Rewrote all 15 drill answer sets to one shape: **short plain-language answer → why →
  evidence**. Added the desk/filing-cabinet analogy to §14 (session = desk, database =
  cabinet, objects = photocopies) and an expired-vs-detached comparison table.
- **Part 4 split into `study/02-MIGRATION-2.0.md`** at Viraj's request (CONCEPTS.md had reached 2161
  lines). Section numbering continues across the two files — `study/01-CONCEPTS.md` §0–§15,
  `study/02-MIGRATION-2.0.md` §16–§22 — so cross-references stay unambiguous. Expanded from 4
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
- **Provenance audit of `study/02-MIGRATION-2.0.md`.** Viraj asked whether code and docs were in sync.
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
  `deliverables/BREAKAGES.md` skeleton).
- **`deliverables/BREAKAGES.md` created: 23 entries, target was ≥10.** 22 of 24 patterns fail on 2.0.51.
  Notably one pattern (`row["col"]`) is called *safe* by both 1.4-side tools and still fails —
  the empirical argument for running the real thing.
- **Repo structure pass.** `README.md` was 0 bytes and is now the map; `pyproject.toml`
  description was still the `uv` placeholder; added the package `__init__.py` manifest; deleted
  `CLAUDE.md.bak`. Kept `study/03-PRACTICE-APP.md` and `study/04-DOCKER.md` — checked, both current.
- **Deliberately NOT done:** the actual version bump (Viraj's call), and renaming
  `experiments/sqlalchemy_1_4_vs_2_0/` — ~180 cross-references for modest gain, and the name is
  defensible once `__init__.py` explains the contents.

### 2026-08-08
- Walked deliverables/BREAKAGES.md entry-by-entry in chat. Viraj asked for more explanation *in the file*;
  first refused (fix/docs are his golden-set seed), then he explicitly permitted importing
  the explanations. Expanded deliverables/BREAKAGES.md, then reshaped to the Group A–H "What 1.4 did /
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
  emitted. `deliverables/BREAKAGES.md` header synced so the diff workflow stays clean.
- Full regression re-run: 10 modules pass on 1.4.52; 22 of 24 patterns fail on 2.0.51; no
  `FIX FAILED`. Part A committed and pushed — the Mac is the only copy until the lab is back.

### 2026-08-09 — Docker, Days 4–5
- `Dockerfile` and `.dockerignore` written from blank, line by line — explained before each
  line, not produced. Base image `python:3.11-slim`, chosen against measured sizes and a PyPI
  wheel check.
- `requirements.txt` is **generated and committed** — `uv export --no-hashes --no-emit-project
  -o requirements.txt`. The image build needs it; regenerate it whenever dependencies change.
- `study/04-DOCKER.md` rewritten from scratch. **Rule narrowed, not dropped:** it now quotes the
  repo's own `Dockerfile`, since that one is written, and still contains no
  `docker-compose.yml`, because Day 6 is his to write from blank.
- Two `# runnable` blocks didn't paste back verbatim (a `grep -c` standing in for a count);
  replaced with a command that computes it. Heading structure fixed to one H1.

### 2026-08-10 — injected-failure drill, Days 4–5 complete
- Injected break: `*.txt` in `.dockerignore`. Diagnosed, restored, `git diff` clean.
- **Found: the container had been broken since `.dockerignore` was added** (`no such table:
  issues`). It had been recorded as working on the strength of a green build and an `ls`, with
  the app itself never re-run. Corrected in the doc and the commit record.
- `entrypoint.sh` added — seeds, then `exec "$@"`. `Dockerfile` gains `COPY --chmod=755` and
  `ENTRYPOINT`. Verified: `issues.db` absent from the image, present at runtime.
- `study/04-DOCKER.md` → 999 lines, drill list 7 → 14. **Explanations for all of the above live
  there, not here:** §1.1 writable layer, §1.4 CLI-vs-daemon, §2.3 `COPY` mode reversion,
  §2.5 PID 1 and `tini`, §3.4 the build-time-seed trap.
- **Days 4–5 gate met:** Dockerfile from an empty file unaided, plus an injected failure
  diagnosed with the mechanism explained rather than merely fixed.
- **Next:** non-root user and `pip --no-cache-dir` (both explained in `study/04-DOCKER.md` §3),
  then Day 6 — Compose + Postgres.

### 2026-08-13
- Lab PC sitting is unblocked via AnyDesk. Wrote `study/08-LAB.md`. **Not pushed.**
- Two labs, do not mix: Mac `id_ed25519` comment is `-geochem` (minmod/ISI). This
  Ubuntu PC is unrelated. Do not copy that key here.
- Sitting: clone + local git + **Cursor login as him (may stay).** Do not
  touch the other person's Claude — no `claude`, no `/logout`. Tailscale /
  Mac→PC SSH deferred.

### 2026-08-13 — PC clone (AnyDesk, `shaili` user, XPS 8950)
- Cloned into `~/Documents/Workspace/SqlUpgradeAgent` on `phase-0/repo-structure`.
  Local git identity only: `virajvaghasia` / noreply. **Global still Shaili.**
- `gh auth login` as Viraj (needed to push from this box). Logout in §6 before leaving
  if they should not keep Viraj's token on this user.
- `uv sync --frozen` + `uv run pytest`: **17 passed, 1 warning.** Seed + `check` OK
  on SQLite. `.env` copied from `.env.example` (gitignored).
- Host GPU: RTX 3060, 12288 MiB, driver 595.71.05. **No Docker** — `sudo` needs a
  password, so Engine / NVIDIA Container Toolkit / Ollama not installed this pass.
- Do not touch `~/.claude`. Close the `claude` TUI if still open; do not `/login`.
- Replanned off measured specs: **31 GiB RAM / 12288 MiB VRAM**. VRAM is the
  bottleneck. Langfuse stays Phase 6 for product reasons, not RAM. Docs updated
  in `CLAUDE.md`, `phases/PHASE-0.md`, `study/08-LAB.md`.
- Sitting diary in Ubuntu words added to `study/08-LAB.md` (new to Ubuntu). Further
  PC steps get appended there so chat is not the only record.
- Docker Engine installed (29.7.2 + Compose v5.4.0). Every 08-LAB command block
  now has a why + example inline, not only in §11.
- `newgrp docker` → hello-world OK. `docker compose up --build` on amd64:
  Postgres 16.14, `postgresql+psycopg2://app:***@db:5432/issues`, 38 open issues,
  app-1 exit 0.
- Day 7 gate passed: NVIDIA Container Toolkit 1.20.0. Runtimes include `nvidia`.
  In-container `nvidia-smi`: RTX 3060, 12288 MiB, driver 595.71.05.
- Day 10 gate passed: Ollama 0.32.9, `qwen2.5-coder:7b` (4.7 GB pull). On GPU
  (`llama-server` ~4650 MiB). Warm eval **62.23 tok/s**. Leftover **7115/12288 MiB**.
- Days 8–9 CI gate: PR #3 deliberate fail → `tests` red, merge BLOCKED, closed
  unmerged. Tailscale already `shaili.gandhi@` (`100.72.117.53`); do not relogin.
  sshd running. No reboot ~20 days. Waiting on Shaili to share `kj-xps-8950`
  (Viraj has no Tailscale creds). Message to her is in `study/08-LAB.md` §L.2
  and `logs/HANDOFF.md` REPLY 2.2.

### 2026-08-12 — Day 6 (Compose + Postgres), and the collaboration rule change
- **Collaboration rule changed permanently** at his request, on time grounds — Claude now
  writes infra while narrating. Recorded above with its date so it isn't re-litigated.
- `docker-compose.yml`: app + `postgres:16-alpine`, service-name DNS, `pg_isready`
  healthcheck with `condition: service_healthy`, named volume, no published ports.
  `DATABASE_URL` read from env in `seed.py`, defaulting to SQLite so Part A is untouched.
- **The volume exposed a contradiction:** `seed.py` opened with `drop_all()` on every
  container start. Now seeds only when the database is empty; `--force` still rebuilds.
- Fixed a `print` asserting `seeded issues.db` regardless of the database in use; it reports
  `engine.url` with the password masked.
- **2.0 version pinned to 2.0.51** (`PIN` in `verify_2_0.py`, interpolated into every printed
  command). `>=2.0` had drifted to 2.0.52. Running off-pin now warns loudly, because
  `deliverables/BREAKAGES.md` quotes exact error strings.
- A stale `sqlalchemy-upgrade-agent` image (13h older than the code) silently invalidated a networking
  measurement mid-session. Written up in `study/04-DOCKER.md` §4.0.

### 2026-08-13 — Phase 1, Step 1 (the corpus)
- Explained the step before asking for decisions — he asked for that explicitly, and it is
  now the expectation for every Phase 1 step: what the thing is, why it is a decision, and a
  worked example, *then* the question. Explanations go in the docs, not only in chat.
- `phases/PHASE-1.md` Step 1 gains three subsections (what a corpus is; a measured inventory
  of both doc tags; the version-skew trap on one real line) plus the decision table.
- Corpus decided: `orm/ core/ tutorial/ faq/ errors.rst glossary.rst` from **both** pinned
  tags, plus `changelog/migration_20.rst` from 2.0 only. Out: the rest of `changelog/`,
  `dialects/`, navigation pages, the API reference (absent from `.rst` source), issues/SO,
  library source, and **`BREAKAGES.md`** — it is Phase 2's answer key and stays out of the
  corpus that Phase 2 grades.
- Version skew is **recorded, not filtered.** Every file carries its release; Step 4 retrieves
  across both. Filtering here would delete the failure Phase 3 exists to fix.
- New package `rag/`, new script `rag/corpus.py`: 270 files / 4058424 bytes fetched,
  `corpus/MANIFEST.json` committed (74983 bytes), `corpus/raw/` gitignored. Neither version
  number is typed in it.
- 25 new tests (42 total). Two mutation-checked: a stale total in `PHASE-1.md` and a
  smuggled-in `changelog/` sibling both fail the suite.
- **Docs the change invalidated were fixed, not left:** `README.md`, `study/07-TESTS.md`
  and `CLAUDE.md` now say 42; `phases/PHASE-0.md`'s block names its three files explicitly so
  it stays Phase 0's record and still reproduces.

### 2026-08-15 — Phase 1 Steps 3b, 4 and 5 (all built)
- Qdrant `v1.19.0` pinned; collection name carries model + revision so two revisions cannot mix
  (D41). One published port, `127.0.0.1`-bound, because Qdrant's client is a host script and the
  host genuinely is "outside" — the no-ports rule applied, not bent (D42).
- **A healthcheck that lied.** `CMD-SHELL` runs `/bin/sh`; `/dev/tcp` is a *bash* builtin. The
  container served traffic and reported `unhealthy` forever. Written up in `05-COMPOSE.md` §4.2.
- `rag/ask.py` — the Phase 1 hard gate is met. Generation on the M4 is **18.4 tok/s** against the
  3060's 62.23, which is D27's last unmeasured number and the biggest gap in the project.
- **The prompt was the bug.** Two wrong hypotheses tested and discarded first. The refusal clause
  is load-bearing (without it the model invents API signatures) and over-fires (strict wording
  refused an answerable question). D43, and D44 for why fixing it was correct rather than
  "tuning" — *simple* and *broken* are different.
- `rag/probe.py` → `deliverables/FAILURES.md`, the Phase 1 deliverable. **It records signals and
  never verdicts** (D46). 19 answers marked `UNVERIFIED`, waiting on a human.
- **The split worth keeping:** a retrieval miss is either "in the corpus, not found" (Phase 3 can
  fix) or "in no chunk at all" (the ceiling). 4 and 1. Computed mechanically, not read off by
  eye (D45).
- Still human-only: the 19 verdicts, and the ten Step 2 sample chunks.

### 2026-08-17 — rewrite of §R1–§R3 for the same reader who found the Q&A weird
- `study/10-RETRIEVAL.md` and `study/11-GENERATION.md`: claim-first openers, named examples,
  sitting tables ("after this you can say…"), Q&As restated in plain language. Measured
  `# runnable` blocks and numbers untouched.
- The old Q&A shape (*"cover these on a first pass / shaped short answer → why → what it is
  NOT"*) was the thing that read as already-knowing-the-sitting. Replaced with **Q1–Qn in
  plain language**, then a full answer with a named example. Length is fine; jargon-first is
  not. He later made that explicit: answers can be long if they stay easy to follow.

### 2026-08-19 — the repo's own knowledge graph, and two bugs in one guard

- **`/graphify` run over the repo:** 1074 nodes, 1841 edges, 68 communities. 46 Python files by
  AST (no LLM), 27 markdown files by three parallel agents. **The correction chain is now
  traversable** — `D54→D51`, `D52→D43`, `D58→D38`, `D48→D27`, `D34→D33`, `D56→D33/D34/D04` — so
  *"if this decision is wrong, what else moves"* is a query rather than a memory. God nodes are
  the register (66 edges) and the two deliverables (42, 37), which is the right shape.
- **Two agents read the same decisions from opposite ends** — one the register, one the
  citations — and **40 nodes merged onto the same ids** instead of forking into ghosts. That was
  the test of the id convention.
- **Gitignore decided against sizes, not reflex.** Bulk out, record in, the same rule
  `corpus/raw/` and `MANIFEST.json` already follow. `.graphify_python` holds an **absolute Mac
  path** and would break the lab PC if committed — the reflex answer was wrong in both directions.
- **Two defects in one test guard, both mine, both found by asking whether the work was
  finished.** `except Exception` cannot catch `SystemExit`, so the "skip if Qdrant is absent"
  guard killed the whole suite instead of skipping. Then, silenced, it still wrote a
  `qdrant_client` warning to **stderr** — which `check_runnable` compares — breaking a doc block
  whose visible output was identical. **A guard that only works when it is not needed.**
- **I committed on a red build** by chaining the gate checks and the commit in one shell command.
  Recorded rather than amended away.
- **The graph found a doc drift I had missed by writing:** `study/README.md` said the register
  holds `D01`…`D55`.

### 2026-08-18 (later) — Phase 2's five decisions settled and the scorer built

- **Phase 1 merged** as PR #28, squashed to `main` at `19024c2`, all five CI checks green.
  Phase 2 work had been committed onto `phase-1/completion` by mistake; the three commits moved
  to **`phase-2/measure`** with no force-push, because they were unpushed. **After a squash-merge
  a downstream branch needs `git rebase --onto main <old-tip>`, not a plain rebase** — a plain one
  conflicts, because `main` holds the squash of the same commits.
- **`P2-b`–`P2-e` settled from measurements, not argument** (`D59`–`D62`). Retrieval depth is free
  (~88 ms query embedding at every `k`), so the scorer takes top-20 once and reports the curve.
  The probe questions overlap their own top-1 chunk **0.57** against **0.33** for developer
  phrasing — and **3 of 5 rephrasings returned a different top-1**, which is the harder fact.
  At n=50 one recall figure carries **±0.131**, so Phase 3 must report flipped items; the paired
  bar is ~**6 clean fixes with no regressions**.
- **`rag/score.py` built**, 15 tests, all six mutations caught. It implements `D58`–`D62` rather
  than describing them, and **enforces `D06` in code**: any item whose `verified_by` is not
  `"human"` is dropped, loudly, with its id named.
- **`deliverables/golden.json` exists as a skeleton** — schema, README, three DRAFT items, none
  verified. The 50 questions are Viraj's; drafting is allowed, verifying is not.
- **The scorer had never actually run.** All 15 tests injected a fake retriever, so the real path
  — live Qdrant, the real 3284 chunks, `report()` — had been executed by nobody. Running it found
  no bug and **a stronger finding than `D60` had recorded**: one question, one answer chunk
  `c01542`, **rank 1** in the tidy phrasing and **not in the top 20** in developer phrasing. Not
  ranked lower — absent. Two end-to-end tests now cover that path and skip where the stack is
  missing, rather than the path staying unexercised.
- **Still not built and named as missing:** refusal accuracy (`--refusals`), which `D62` puts in
  scope. The docstring says so rather than advertising a flag that does not exist.

### 2026-08-18 — the chunk gate, taken and passed with an exception

- **Step 2's gate closed. Viraj ruled PASS with 2 of 10 chunks failing**, and the exception is
  written into `PHASE-1.md` Step 2 and `D56` rather than smoothed over. The two failures are
  `c03012` (ends on *"is as follows:"*, list never arrives) and `c00138` (opens *"While the
  above example…"*, and no chunk holds both halves).
- **Ten was not enough to rule on, so `rag/chunk.py --audit` was added** and all 3284 counted:
  **10.7% show one of the two shapes, 6.3% lose content entirely.** Read-only, and its numbers
  now live in the committed `CHUNK_STATS.json` so CI can pin the doc against them — `build()`
  cannot run in CI because `corpus/raw/` is not committed (`D11`).
- **The detectors were validated against known answers before being trusted**, including a
  negative control: `c01480` opens with a backward reference and repairs itself in the same
  sentence, so it must NOT be flagged. Without that check the audit measures regex eagerness.
- **Two of my own errors, both caught by machinery rather than reading.** A test fixture asserted
  `ends_open == 2` for a chunk whose last line was `* one`; and a first pass at "how many answers
  leak Sphinx markup" said 19 of 19 because the split swept in the retrieved-sources block —
  it is **3 of 19**.
- **`--audit` numbers are a `# runnable` block**, so the recorded exception cannot go stale
  silently. Adding 5 tests broke the 3 blocks quoting the test count, again.
- **The remaining gate is the five verification questions**, sat and not passed.

### 2026-08-18 — the five verification answers, written up as §R5

- **A cold sitting on the five `PHASE-1.md` verification questions was run and did not pass.**
  Two of five answered unaided; three answered the *setup* rather than the final clause of the
  question. Recorded because the correction is not more study — one answer was right in five
  words on the first attempt — it is answering the last clause.
- **`study/13-VERIFICATION.md` (§R5) written**, one section per question in a fixed four-part
  shape: plain words → mechanism → the measurement → the sixty-second spoken answer, plus the
  wrong answer each question attracts and the follow-up that kills it. **`D55`** records why it
  is a new file when `CLAUDE.md` says not to create one, and what that costs.
- **A new measurement, and a correction to it made before it shipped.** Q3 is posed
  hypothetically in `PHASE-1.md`; it is not hypothetical. The first count of chunk boundaries
  severing a literal block was **96 of 3077** — and **72 of those are `glossary.rst`**, where
  every definition body is indented under its term. Requiring positive evidence of code gives
  **11**. The honest claim is "at least 11", and both numbers are in the file, because the wrong
  one is the same class of error the file is about.
- **`PHASE-1.md` said three gates were open; the verdicts gate closed on 08-17.** Four places
  fixed. Nothing caught it: every claim was in prose, and `check_runnable` was green across the
  file the whole time.
- **Adding 4 tests broke 4 `# runnable` blocks** in `README.md`, `07-TESTS.md` and `PHASE-0.md`,
  all quoting the test count. That is the mechanism working — the counts went to 133 and 56/56
  at that commit, and have moved since; the current figures are in the state block above.

### 2026-08-18 — explanations that lived only in chat, written into the files

- **Did not rewrite `01`–`08`.** Those already teach SQLAlchemy and Docker in their own shape.
  The confusion was in the RAG files, so that is what moved.
- **`single_source`** — "does not survive" means the answer cited only one of five pages, so if
  that page is the bad one there is no backup in the citations. Q7 is the example. In
  `rag/probe.py` and `deliverables/FAILURES.md`.
- **Which integer** — `DEFAULT_K = 5`; 6 would have included `backref` at rank 6. Comment on
  the constant in `rag/ask.py`; table in `study/12-EVALUATION.md` §R4.3.
- **Prose-shaped vs code-block-shaped vs severed listing** — three different cuts. In
  `phases/PHASE-1.md` Step 2, `rag/chunk.py` `audit()`, and `study/13-VERIFICATION.md` Q3.
- **Explanation style is now a rule, not a mood.** `CLAUDE.md` *How to explain things*
  amended 2026-08-18: assume no jargon, show then name, named examples, side-by-side when
  two things look alike, name the actual lever, put the answer in the file. **He then
  corrected the length bias:** answers can be long; they must be easy to understand. Do not
  slogan a mechanism or stop at **Short:**.

### 2026-08-17 — verdicts closed, prompt D shipped, §H emptied

- **Phase 1's second gate closed.** 19 verdicts (`10/3/6`) drafted from `BREAKAGES.md` keys and
  executed against real 2.0.51, accepted by Viraj. `verdicts.json` is the record; `probe.py`
  renders from it, because it used to hardcode `UNVERIFIED` and a regeneration would have
  destroyed all 19 silently.
- **Eleven lab rounds in one day**, 5 through 11. The arc is worth knowing because each round
  corrected the last: raising `k` doesn't reduce refusals (`D51`) → but Rounds 8–9 ran at k=5
  where the answers weren't retrieved, so `D51` was wrong and `D54` corrects it in place →
  prompt D ships → and Round 11 confirms it at `n=5` with **zero** non-unanimous cells.
- **Two bugs of mine, both found by measuring rather than reading.** The review sheet truncated
  3 of 19 answers at a nested code fence (Q13 showed 295 of 965 chars). `probe.py` matched
  symbols by substring, so `relation` counted inside every `relationship` — 798 recorded, 21
  true, 0 documenting `orm.relation()` — which flipped Q6's verdict and had silenced
  `symbol_missing` on exactly the question it existed for.
- **Workflow changed twice at Viraj's instruction**, both recorded as memory: branch before
  working (never commit to local `main`), and **one long-lived branch per phase** rather than a
  PR per change. `phase-1/completion` is that branch.
- **What I got wrong and he caught:** shipping prompt D when he was asking whether we *should*,
  and holding Rounds 8–10 to an `n=1` standard I had spent the day insisting `D43` should have
  met. Both are recorded in the entries rather than smoothed over.

### 2026-08-20 — `study/13-VERIFICATION.md` enriched to the R1–R3 explanation style

- Whole-file pass: show-then-name, named examples, side-by-sides, “what did not happen,” long
  answers that stay plain. Measured `# runnable` blocks and numbers left alone.
- **Q3** densest: three cuts (prose / `::` / severed listing), char ranges `c00233`/`c00234`
  (85→1528 | 1529→3243), direction table for `relationship("Address")`, overlap diagrams for
  `c03012` vs `c00138`.
- **Q1–Q2, Q4–Q5, R5.0, R5.6–R5.7** brought to the same density (`DEFAULT_K`, answer-key vs
  API-absence, meaning≠string table, citation≠correctness with Q1/Q2 verdicts).
- **Second pass:** every *Say this* / *Do not say* / *Follow-up* expanded to the same density —
  second jabs, named traps, R5.6 trap column, R5.7 rehearsal includes *Do not say* lines.

### 2026-08-20 (later) — `study/12-EVALUATION.md` §R4 clarified

- Added “two report cards” opener (retrieval vs generation) so metrics stop blending into one
  grade. R4.2 now shows recall / MRR / rank on the `backref`@6 example before naming them.
- Softened Round 7 callout into “rank ≠ component”; plain-language R4.4–R4.6 and vocabulary.

### 2026-08-20 (overnight) — Phase 2 finished: the baseline is a number, and it is worse than recall says

- **Started by fixing a red test.** The `13-VERIFICATION.md` rewrite had compressed R5.7's probe
  verdicts to `10 / 3 / 6`, breaking the test that pins those to `verdicts.json`. Fixed the doc,
  not the test: R5.7's own contract says each block matches its section's *Say this*, and a slash
  triple is not sayable in the one section meant to be read aloud.
- **Verified the 50-item golden set mechanically before letting anything rest on it** — `D06` is
  the rule a script must not launder. No duplicate ids or questions, all 68 answer-chunk ids
  resolve, none empty, no unanswerable item carrying chunks. Committed with two limitations
  stated in the message: **62 of 68 answer chunks are in one file** (`migration_20.rst`, 4 of 270
  files touched), and **68 chunks are only 33 distinct** — `c01567` answers seven items, so
  `D61`'s ±0.131 is optimistic.
- **Ran the scorer for real: `recall@5 = 0.51 ±0.131`.** Filled `ROADMAP.md`'s baseline row and
  saved `deliverables/baseline-phase1.json` so Phase 3 is a paired comparison.
- **`D63` — `D60` had the label backwards, and its own metric proves it.** `D60` quarantined the
  `breakages` items as leaky. Measured: `migration_guide` overlap **0.64** / recall **0.73**;
  `breakages` **0.43** / **0.41**. The set added to be *realistic* is leakier (0.64) than the
  probe questions `D60` was worried about (0.57). **Phrasing leaks, not provenance** — `D60`'s own
  `c01542` evidence already said so. Mechanism kept, label corrected, `D60` points forward to it.
- **Built `--refusals` (`D62`), the last named gap.** One detector, `ask.refused()`, moved beside
  the SYSTEM clause that mandates the string; `probe.py` now calls it instead of holding a second
  copy. **Prefix, not substring** — prompt D deliberately says "here is the part they cover and
  here is the part they do not", which is an *answer*, and a substring test would score it as a
  refusal in the flattering direction. Six mutations checked.
- **The refusal run found more than it was built to find.** 3/3 unanswerable correctly refused,
  zero fabrications. But **7 answerable items refused with the answer chunk at rank ≤ 5** —
  Phase 1 knew this as **two** questions (Q18/Q19). And the figure in neither table: of the 24
  whose answer was retrieved, 7 were refused, so the system answered with the right page in hand
  on **17 of 47 = 0.36** against a recall of **0.51**. **Retrieval's number is a ceiling that
  generation loses another 15 points of**, invisible to every retrieval metric.
- **A fabricated example, caught before it shipped.** Writing what is now §R6.1 I invented a
  side-by-side of
  two `from_self` questions with overlap figures `0.8` and `0.29`. There is only **one**
  `from_self` item in the set; the pairing and both numbers were made up. Replaced with the real
  extremes, derived: `g034` at **6/6, rank 1** and `g042` at **0/7, not in the top 20**. The
  measurement rule caught it only because I went to verify — nothing would have flagged it.
- **`# runnable` trap avoided by checking, not by luck.** A block running `rag.score --validate`
  passed here and would have failed CI: `corpus/chunks.jsonl` is gitignored (`D11`). Classified
  ENV with the reason, alongside `rag.golden`. Adding 8 tests (165 → 173) broke the three blocks
  quoting the test count, as it always does.

### 2026-08-21 — Phase 2 scorecard split into `study/14-MEASURE.md`

- **`R4.7`–`R4.9` moved out of `12-EVALUATION.md` into `14-MEASURE.md` as §R6.1–§R6.3.** Sitting 4
  stays how to measure (the 19 probe answers); Phase 1 already ended at §R5. Golden baseline,
  refusals, and three ceilings are Phase 2's result, not an appendix to Sitting 4 (`D64`).
- Indexes updated: `study/README.md`, root `README.md`, `PHASE-2.md`, CLAUDE teaching-files
  line. `13` points forward so the cold gate is not confused with the scorecard.

### 2026-08-21 — the second 50: real questions, harvested

- **Why, in one line:** `D63` proved **phrasing** decides retrieval, and both halves of the first
  50 were phrased *here*. `D60` had already admitted it — *"the developer phrasings are n = 5 and
  were drafted here."* The realistic half was realism as imagined; these are observed.
- **Harvested 25 Stack Overflow + 25 `sqlalchemy/sqlalchemy` GitHub discussions**, titles kept
  verbatim including typos (`g052`: *"How do I migrate this statment"*). Every item carries its
  `source_url`. Sourced by searching the error strings developers actually paste, then filtered
  for genuine 1.4→2.0 relevance — off-topic hits (numpy casting, pandas/mssql perf, 1.3→1.4
  questions, polymorphic loading) excluded explicitly rather than left to dilute the set.
- **The circularity trap, and it would have been invisible.** Proposing answer chunks with the
  dense retriever grades the benchmark against itself: pick each chunk from the system's own top 5
  and `recall@5` is ~1.0 **by construction**, a perfect score measuring nothing. Proposals come
  from **BM25 over `chunks.jsonl`** instead — a channel the graded system does not use — and each
  `answer_note` records the top-5 BM25 hits with scores so the reasoning is inspectable.
  `rag/golden.py`'s docstring already warned about this from the other direction.
- **It fixes the concentration limitation**, if the drafts survive verification: source files
  touched **4 → 32** of 270; share of answer chunks in `migration_20.rst` **91% → 19%**.
- **The baseline did not move**, which is `D06` working rather than luck: `rag/score.py` scores the
  50 verified only and announces it, so `recall@5 = 0.51 ±0.137` is unchanged with 50 new items in
  the file. `--validate` now exits 1 until a human is through them — the gate, not a breakage.
- **Sizing was computed, not guessed.** Wilson half-width at p=0.5: n=50 ±0.134, n=100 ±0.096,
  n=200 ±0.069. 50→100 is the last increment that clearly pays; doubling again buys 19→14 points
  for ~25 more hours of `D06` verification.
- **Not done and it is his:** all 50 drafts. Claude may draft and propose; a test asserts Claude
  cannot set `verified_by`.

### 2026-08-21 (later) — checked the golden set, found a signature that cannot be checked

- **Session started from a working tree nobody had written down.** `golden.json` had been
  rewritten (100 items, all stamped `verified_by: "human"`, 17 drafts dropped and 17 backfilled
  as `g101`–`g121`), plus two untracked files: `tools/audit_golden_fullbar.py` and
  `deliverables/GOLDEN-FULLBAR-AUDIT.md`. `PHASE-2.md` described an earlier state of it. Every
  number below was re-derived here rather than read off that tree.
- **Gates, run first:** 179 tests pass (all of them, once Qdrant is up — 5 skip without it),
  58/58 `# runnable`, 19 verdicts in sync, `rag.score --validate` exits 0.
- **Brought the stack up rather than declaring the number unobtainable.** Docker Desktop was not
  running, so `rag.score` could not reach Qdrant. `open -a Docker` + `docker compose up -d qdrant`
  and the collection was already there.
- **The 100-item score, measured:** `recall@5 = 0.49 ±0.101`, MRR 0.373, 22 answerable items
  absent from the top 20, 31 top-5 slots lost to duplicates. **The provenance split is the
  finding:** `migration_guide` 0.73, `github` 0.57, `breakages` 0.41, **`stackoverflow` 0.38.**
  Real questions score worst, and **the repo's imitation of a stuck developer scored higher than
  actual stuck developers** — `D63` with the imitation removed. `D65` records it.
- **The baseline artifact was NOT overwritten**, and the reason is `D61`: Phase 3 is a paired
  comparison, and swapping the ruler makes every later row two unpaired averages. Proven rather
  than argued — `--baseline` against the saved 50 gives **0 fixed, 0 broken, p = 1.000**, which is
  only checkable because the old artifact still exists.
- **`±0.131` was wrong in `ROADMAP.md` and `CLAUDE.md`.** The scorer always printed **±0.137**;
  recomputing Wilson from `baseline-phase1.json` gives ±0.137. The band is over the **47
  answerable** items, not the 50 in the file. Hand-typed, repeated in two files, green CI
  throughout. Current-state claims corrected; the Session Notes entries above keep the old figure
  because they record what was believed then.
- **The audit report did not reproduce, and that found two things.** Re-running
  `audit_golden_fullbar.py` gave 99 PASS / 1 FAIL: `g117` needs `aiosqlite` **and** `greenlet`,
  which the docstring's command omitted — a missing driver reported as a golden-set failure. With
  the right deps it is 100 PASS. And the report carried a **hand-typed** `## SQL N/A breakdown`
  section the generator never wrote, so it vanished; its content was also wrong (`g064` labelled
  "unanswerable ceiling" — it is an IDE typing question). Both fixed **in the script**, so the
  breakdown regenerates and the docs N/A list prints too. **They are not the same nine items** —
  docs-N/A is the 9 unanswerable, SQL-N/A is 8 of those plus `g064` minus `g001`.
- **`g065` looks mislabelled, and the audit structurally cannot see it.** Its note says
  *"Unanswerable from THIS corpus (0 narrative chunks)"*; `grep -c 'CREATE VIEW'` returns **2** —
  `c00484`/`c02056`, heading *"Does SQLAlchemy support ALTER TABLE, CREATE VIEW, CREATE TRIGGER,
  Schema Upgrade Functionality?"*. The refusal verdict may survive a human's read; the stated
  reason does not. An `answerable: false` item is reported `N/A` on both audit columns and passes
  the rollup with nothing run — **the one label an audit cannot test.**
- **The thing I did not do, and will not:** stamp anything. `--status` says 100 human-verified;
  the notes on `g051`–`g121` say `CLAUDE_REVIEW` / `STAMPED human ... (batch 3)` / `HUMAN stamp
  Batch 7`, and ten still carry *"Awaiting human stamp"* with the field already set. `D06` is
  about **who signs**, not how carefully it was checked — and the audit says the checking was
  real. **It is now an OPEN entry in §H** (which had been empty since 2026-08-17) with three ways
  to close it, and `golden.json`'s own `_README` says so too.
- **Documented in the files, not the chat:** `PHASE-2.md` step 6 (ledger, audit, scorecard, the
  open item), `14-MEASURE.md` §R6.1 (the 100-item run) and §R6.3 (six new ceilings + `g065`),
  `09-DECISIONS.md` (`D65` + the §H entry), `ROADMAP.md` (band fixed, split extended),
  `README.md`, `study/README.md`, and this block.

### 2026-08-21 (evening) — spot-check of ten, then verified; §H empty again

- **Viraj approved** the risk-weighted spot-check sheet (`g065`,`g097`,`g093`,`g075`,`g099`,
  `g095`,`g088`,`g087`,`g079`,`g074`). Nine KEEP; `g065` KEEP-false with note rewritten (CREATE
  VIEW chunks exist; still no same-migration recipe); `g079` `c01189`→`c03004`.
- **"Awaiting human stamp" / "Awaiting full-bar stamp" stripped** from notes. Spot-ten notes
  carry `VERIFIED 2026-08-21`.
- **§H CLOSED** in `09-DECISIONS.md`; `PHASE-2.md`, `14-MEASURE.md`, this START HERE block, `D65`
  signature line updated. Baseline artifact still the 50 (`D65`/`D61`).
- Not committed unless he asks.

### 2026-08-21 (later still) — the refusal run on 100, two fabrications, and D54 narrowed

- **The first `--refusals` attempt died at session teardown with nothing written** — it prints
  only after all 100 generations. Re-launched detached (`nohup … & disown`); ~30 min on the Mac.
- **The clean pass stopped being clean: 7/9 unanswerable refused, 2 FABRICATED** (`g056`, `g065`),
  against `0/3` on the 50-item set. Nothing about the model or prompt changed — **three
  unanswerable items were never enough to measure a fabrication rate.**
- **`g065`'s fabrication was checked, not asserted.** It answered with an Alembic script calling
  `op.create_view` and `op.drop_view`; `hasattr(Operations, "create_view")` is **False** on
  alembic 1.19.1, while `op.create_table` in the same script is real. Two invented calls beside
  two working ones — and no citation on the code block.
- **`g056` hedged with the refusal string inside an answer** (*"The sources do not cover how to
  migrate this property…"*). That is the case `ask.refused()`'s **prefix** test exists for; a
  substring search would have scored a fabrication as a correct decline.
- **`g065` is both things at once** — the item whose `answerable: false` *reason* is measurably
  wrong (2 `CREATE VIEW` chunks exist) and whose *verdict* is vindicated by the invented API.
  **The label decides whether an answer counts as a fabrication**, which is the sharpest argument
  for `D06` in the repo.
- **48 of 91 answerable refused; 13 with the answer in the prompt** (was 7 of 47). End to end
  **32 of 91 = 0.35** against recall `0.49` — the ~15-point generation loss held at twice the
  sample. The open cell grew from 6 to **11**.
- **`D54`'s "refusal behaviour is deterministic" did not survive the re-run and is now narrowed in
  place.** Two of the seven first-50 items flipped between 08-20 and 08-21 — `g029` refused then
  and answers now, `g015` the reverse — with `TEMPERATURE = 0.0`, `rag/ask.py` unchanged since
  `b6320c4`, and the index unchanged (`0 fixed, 0 broken`). Both reproduce today when re-asked, so
  it is stable *within* a sitting. **Consequence: a Phase 4 before/after must re-run its baseline
  in the same sitting as the change.**

### 2026-08-21 (evening) — Phase 3 lever 1: twin collapse (`D66`)

- **`rag/dedup.py`** + `index.retrieve` over-fetch/collapse; prefer 2.0.51.
- Measured: dup seats **31→0**, recall@5 **0.495→0.516**, vs 50-item baseline **2↑ 0↓**
  (`g046`,`g047`), McNemar p=0.500. Absents still 22.
- Docs: `PHASE-3.md`, `D66`, ROADMAP metrics row, 179 tests.
- Uncommitted with the earlier signature/verified edits — commit when he asks.

### 2026-08-21 (later evening) — Phase 3 lever 2: hybrid BM25 + RRF (`D67`)

- **`rag/bm25.py`** + **`rag/hybrid.py`**; `retrieve(..., hybrid=True)` default. Dense-heavy RRF
  `kd=25`/`kb=90` — densest *zero-regression* point on a sweep (equal-k broke five items).
- Measured: recall@5 **0.52 → 0.63 ±0.097**, absents **22 → 17**, SO **0.38 → 0.48**, vs 50-item
  baseline **6↑ 0↓** (`g024`,`g038`,`g044`,`g046`,`g047`,`g050`), McNemar **p=0.031**.
- `--dense-only` on score/search keeps the pre-hybrid path measurable. **186** tests.
- Still uncommitted — ask before commit.

### 2026-08-21 (late) — Phase 3 lever 3: seat-5 CE rerank (`D68`)

- Full CE reorder of hybrid top-20: +3 @5, **10 broken** — rejected.
- Shipped: promote into seat 5 from ranks 6–10 when margin ≥ 0.8 (`BAAI/bge-reranker-base`).
- Measured: recall@5 **0.63 → 0.64**, vs baseline **7↑ 0↓** (`g017`), p=0.016. Absents still 17.
- Lab Round 12 closed in docs; **191** tests.
