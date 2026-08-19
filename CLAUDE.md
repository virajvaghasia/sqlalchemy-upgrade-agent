# Working agreement — how Claude works on this repo

Instructions for the AI assistant. Humans want [`README.md`](README.md), which maps the repo;
this file is about *how the work gets done*, not what the work is.

The project: a RAG system that helps developers upgrade Python code from
**SQLAlchemy 1.4 → 2.0**. Portfolio project targeting Applied AI Engineer roles (Nvidia,
Meta, Google, Apple, Anthropic, and startups).

- **`README.md`** — the front door and the map: every doc, every script, and what each proves.
  **Keep it current** — it is the only file that indexes the whole repo.
- **`phases/ROADMAP.md`** — the full ~4-month arc, six phases, plus a glossary of every AI term.
- **`phases/PHASE-0.md`** — the current phase in detail.
- **`study/01-CONCEPTS.md`** — §0–§15: the relational model, the ORM layer, the session at runtime.
- **`study/02-MIGRATION-2.0.md`** — §16–§22: the 1.4 → 2.0 upgrade. Continues `study/01-CONCEPTS.md`'s section
  numbering, so a reference to "§18" is unambiguous across both files.
- **`deliverables/BREAKAGES.md`** — the Phase 0 Part A deliverable. 23 entries, each with the 1.4 code and
  the real 2.0 error. Generated skeleton; the *fix* and *docs* fields are Viraj's to write.
  Never regenerate over it once filled — diff instead (the file's own header says how).
- **`study/`** — all teaching material, numbered in reading order; `study/README.md` is the
  index and explains the two § numbering families (§0–§22 SQLAlchemy, §1–§6 infrastructure)
  plus the two runbooks (`03`, `08`).
- **`study/08-LAB.md`** — lab PC from-scratch sitting (Day 3 → Day 10). Not pushed until
  Viraj says so.
- **`study/09-DECISIONS.md`** — the decision register, `D01`…`D57`: what was decided, what was
  rejected, why, and the interview question it answers. **Cite entries by ID from other docs.**
  When a decision is made or reversed, update this file in the same commit — a register that
  lags is worse than none, because it is trusted. §H lists choices that are *not yet
  justified*; never invent a rationale to empty it.
- **`tests/`** — 140 tests pinning what the docs claim; see `study/07-TESTS.md`.
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

**State (2026-08-18):** Phase 1 is **COMPLETE.** Both human gates closed 2026-08-18 — the chunk
gate with a recorded exception (`D56`: 8 of 10, population rate 10.7%, 6.3% unrecoverable), the
five verification questions per `D57`. **Next is Phase 2.** **Work is on branch
`phase-1/completion`, not `main`** — `main` is deliberately stale and gets one PR when the phase
closes. **140 tests**, **58/58** `# runnable` blocks, **57** decision entries, **§H empty**,
19 verdicts in sync (`tools.apply_verdicts --check`).

**The chunk gate closed 2026-08-18 — PASSED with a recorded exception (`D56`).** Reading ten at
random turned up two that do not stand alone; `rag.chunk --audit` (new) then counted all 3284 and
put the rate at **10.7%, of which 6.3% is unrecoverable**. It passed because the defect is bounded
and named rather than suspected, and because fixing it now would remove a measured failure before
anything downstream had been hurt by it (`D04`). **The remaining gate is the five cold
verification questions** — sat 2026-08-18 and **not passed**: 2 of 5 unaided, 3 answered the
setup rather than the question. `study/13-VERIFICATION.md` (§R5) is the write-up, and reading it
before a re-sit converts the gate into a recognition test.

**The teaching files are four:** `10-RETRIEVAL.md` §R1–§R2 (retrieval), `11-GENERATION.md` §R3
(generation), `12-EVALUATION.md` §R4 (evaluation), `13-VERIFICATION.md` §R5 (defending it under
questioning). One `R` run across all four — it stands for RAG, not Retrieval (`D47`).

**What today settled, in the order it matters:**

| | |
|---|---|
| **19 verdicts closed** | `CORRECT 10 · PARTIAL 3 · WRONG 6`, in `deliverables/verdicts.json` so a regeneration cannot destroy them |
| **Prompt D shipped** (`D54`) | confirmed at `n=5`, zero non-unanimous cells; beats B on Q16, 5/5 vs 0/5 |
| **`DEFAULT_K` stays 5** | k=10 was measured and is worse — two over-fires and one fabrication |
| **`D31` settled** | pgvector beat Qdrant on every number; Qdrant stays because migrating buys 2 ms |
| **`D48`/`D49`** | 3060 embeds 2.8x faster at **batch 8**; bigger batches are slower on CUDA too |
| **`D50`** | fixes verified twice — they run, and the docs recommend them (12 of 13) |

**Two findings to read before doing anything else:**

- **Refusal behaviour is deterministic** (`D54`, Round 11): every cell 0 or 5 across 5 runs. So
  Rounds 8-10's `n=1` runs were *right* — and still the wrong method, because nothing before
  Round 11 said so and `D43` had measured the opposite. **Re-check determinism whenever the
  model, temperature or sources change.**
- **`D51` is corrected in place by `D54`.** At `k=5` the failures ARE retrieval failures — four
  of five have answers outside the top-5. `D51` generalised from the one case where the chunk was
  present. **Phase 3 is justified**, by a cleaner argument than it started with.

**The open defect no wording fixes:** Q18 and Q19. At k=10 their chunks are in the prompt — Q19
has **three**, at positions 6, 7, 8 — and all four wordings refuse. Two questions, real, unsolved.

**One gate remains and it is a human's:**

| gate | how | where |
|---|---|---|
| ~~eyeball ten chunks~~ | **closed 2026-08-18** — passed with exception, `D56` | `phases/PHASE-1.md` Step 2 |
| the five cold verification questions | from memory, no notes. **Sat 08-18, not passed** | `phases/PHASE-1.md` Verification |

**What the verdicts actually showed, which is not what the phase predicted.** Five of the six
`WRONG` are **refusals** — the system declining questions it could answer — not hallucinations.
And the ranks say those five are three different problems: `backref` ranked **6** and missed the
top-k cut by one place; `keys()` ranked **12**, squarely a reranking case; `table_names` ranked
**23** while the five returned scored `+0.001` and `+0.000` over noise, meaning search found
nothing at all. **Tune `k` before reaching for architecture** is now an evidenced claim.

**Settled by the lab PC, 2026-08-17** (replies are in `logs/HANDOFF.md`, Rounds 5–6):
- **`D43` is 1 refusal in 13** — the over-fire never reproduced. `D48`/`D49` are new.
- **The 3060 embeds 2.8x faster** (19.9 vs 7.2 chunks/s), closing `D27`'s untested half.
- **Bigger batches are *slower* on CUDA too** — batch 8 beats 128 by 2.7x at an eighth of the
  VRAM. Round 5 predicted the opposite. Variable-length chunks make batching pad, not amortise.
- **Retrieval and generation coexist on one 12 GiB card** (~9 GiB together).

**Next work, in order:**

1. ~~**`D31`**~~ — **settled 2026-08-17, and pgvector won on every number**: 0.45 ms against
   2.65 ms, zero extra containers, 40 MB. Qdrant stays because migrating a working Step 3b buys
   2 ms, which is a legitimate reason and not the one originally given. **§H is now empty.**
   The finding worth carrying: the two stores returned **identical top-5 on only 15 of 19**
   probe questions, so the vector store is not a neutral component — swap it and Phase 2's
   numbers move without retrieval improving.
2. ~~**§R4 — evaluation**~~ — **written 2026-08-17** as `study/12-EVALUATION.md`, third subject
   after retrieval and generation, numbering continued per `D47`. Its §R4.3 is the one to reread:
   the rank of the first containing chunk split what was filed as one Phase 3 fix into **four**
   different problems, one of which is a constant being wrong.
3. ✅ **Settled 2026-08-17 — Round 11, `n=5`, zero non-unanimous cells.** D's margin over B is
   Q16 at **5/5 vs 0/5**; `D54` is confirmed and no longer provisional. **Ship D, keep k=5.**
   The bigger finding: refusal behaviour is **deterministic** here — every cell 0 or 5 — so
   Rounds 8–10's `n=1` runs were *right*, and still the wrong method, because nothing before
   this round said the process was deterministic and `D43` had measured the opposite. Re-check
   determinism whenever model, temperature or sources change.
4. **Ship prompt D, keep `DEFAULT_K = 5` — `D54`.** Round 10 (152
   generations, both k values) found that **at k=5 every one of D's nine refusals is correct**:
   four have answers outside the top-5, five are ceilings or `absent`. **D at k=5 is the only
   configuration measured with zero prompt errors.** Raising k to 10 trades four honest refusals
   for **two over-fires** (Q18/Q19 — chunks present, Q19 has three, all wordings refuse) and
   **one fabrication** (Q5 — `keys()` in no top-10 chunk, and A/B/D all answered it).
5. **Phase 3 is justified after all**, and `D51` is corrected in place: at k=5 the sources
   genuinely do not arrive. The residue is Q18/Q19 — a real generation defect no wording fixes,
   but **two questions rather than eight**.
6. ~~Round 10~~ — **done 2026-08-17.** All four wordings
   at **k=5 and k=10**, 152 generations. Rounds 8–9 both ran at k=5, where the four unfixed
   refusals have answers at ranks 23/12/8/6 — **outside the prompt**, so refusing them was
   correct, not an over-fire. Round 7 showed the opposite at k=10 for `backref`. **Compare each
   prompt against itself across the two k values:** refusals dropping means retrieval was the
   problem; staying flat means the instruction is. Q18/Q19 are the watch, Q3/Q5 the control.
7. ~~Ship prompt D regardless of Round 10~~ — it is strictly better than B, wrong in 4 places
   against B's 5, and the one it fixed (Q16) is the only `absent` question that had been getting
   a confident answer.
8. ~~Round 9: prompt D~~ — **done 2026-08-17.** A and B both
   ask the model to judge *sufficiency*; D makes partial answers the expected output, narrows
   refusal to *subject* rather than sufficiency, and requires a refusal to name what was looked
   for. **Target: 5 refusals, and the right five** (Q4, Q6, Q15, Q16, Q17) — the count alone
   proves nothing. **If D also lands on 8, the instruction is not the lever and the model finally
   enters scope.**
9. ~~Write a fourth prompt — `D52`~~ — **written 2026-08-17**, pinned by a test that it differs
   from B in kind rather than degree. Round 8 settled it: A and B refuse the **same 8 questions,
   identically**, so `D43` chose between two options that are the same option. C refuses 0 and
   fabricates. **The correct floor is 5** (3 `absent` + `has_table` + `relation`, both ceilings);
   B refuses 8 and misses one, so it is wrong in **5 of 19**. No wording tested is good, and the
   search space so far was two points that turned out to be one. **Not tuning — a genuinely
   different fourth wording**, then `compare_prompts --all` again. Do not change the model: C
   proves it answers all 19 when permitted to.
10. ~~The next experiment is a PROMPT experiment — `D51`~~ — **done, that was Round 8.** Round 7 came back
   2026-08-17: sweeping `k` moved retrieval and left `refused` at **8 at every value**, and a
   `--retrieval-only` run proved the answer was in the prompt at k=10 while the model still
   declined. **The eight refusals are not the argument for hybrid search.** `D43` measured
   over-firing at 1-in-13 — but on prompt A, on one question; this is prompt **B**, the shipped
   one, refusing 8 of 19 with the answer present. `rag/compare_prompts.py` already exists, so
   testing wordings against the full probe set is cheap.
11. **Phase 3** — still worth building (`symbol_missing` and `retrieval_failure` both fell as `k`
   rose, so retrieval is genuinely imperfect), but **its stated justification needs rewriting
   first**. Do not build it on the eight refusals.

**Working branch: `phase-1/completion`.** Everything for the rest of Phase 1 lands there and it
merges to `main` **once**, when the phase is done — not a PR per change. Push and pull on it
directly. `main` goes stale during the phase, deliberately. **The lab PC checks out this branch
too**, so any ASK block in `logs/HANDOFF.md` must name it rather than `main`.

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
