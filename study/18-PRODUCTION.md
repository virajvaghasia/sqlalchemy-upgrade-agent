# §R10 — Phase 6: a change that makes it worse cannot merge quietly

Plan and measurements: [`../phases/PHASE-6.md`](../phases/PHASE-6.md). Decisions: `D96` (framing,
rejected), `D97` (the gate). This file is the sitting; the plan is the record.

---

## R10.0 — Where to start

**Plain job.** Until now, every improvement in this repo was checked by someone remembering to run
`rag.score` and read the result. This phase makes the check run on its own, on GitHub, every time
someone proposes a change, and makes the proposal fail if the check fails.

**What did NOT change.** No new metric. No new model. The golden set is the same 100 questions.
The gate re-uses `rag.score` and the paired comparison Phase 3 was already judged by (`D61`). It
moves an existing check from "someone runs it" to "it runs".

---

## R10.1 — What "CI gating" means, starting from a pull request

A **pull request** (PR) is a proposal: *here are my commits, please merge them into `main`.* GitHub
can run programs against those commits before anyone merges, and show a green tick or a red cross
next to each one. Those programs are **checks**. The file that says what to run is a **workflow**,
in `.github/workflows/`.

This repo already had four checks in `ci.yml`: the tests, the `# runnable` blocks, the 2.0 evidence,
the Docker image. They answer *"is the code broken?"*. None of them answers *"did the answers get
worse?"*. A PR could delete the reranker and every one of the four would stay green.

**Gating** means a check whose red cross **blocks the merge**. Technically, blocking is a
repository setting ("required status check") on top of a check that exits non-zero. The check is
in this repo; the setting is Viraj's to switch on.

---

## R10.2 — The gate in Python and SQL terms

Two tables, one row per golden question:

```
baseline (the branch you merge INTO)        this run (your PR)
id     answerable  rank                     id     answerable  rank
g017   true        5                        g017   true        6
g013   true        3                        g013   true        3
g056   false       -                        g056   false       -
```

Join on `id`. For each answerable row, ask one yes/no question on both sides: **was the answer page
in the top 5?** Rank 5 is yes, rank 6 is no, because `DEFAULT_K = 5` is how many pages reach the
prompt.

```
was yes, now no    -> BROKEN   the check fails
was no,  now yes   -> FIXED    reported
same on both sides -> unchanged (or MOVED, if the top 5 ids reshuffled)
```

In SQL it is one query:

```sql
SELECT b.id
FROM baseline b JOIN this_run r USING (id)
WHERE b.answerable AND b.rank <= 5 AND (r.rank IS NULL OR r.rank > 5);
-- any row returned = the gate fails
```

That is the whole gate. `rag/gate.py`, `paired()` and `blocked()`.

---

## R10.3 — The demo: remove the reranker

The ROADMAP's picture of this phase is *"open a PR that removes your reranker, and film CI
rejecting it."* The rows for that PR were measured on the Mac (`rag.score --no-rerank`) and
committed, so the gate's verdict reproduces on any machine with no Qdrant:

```
# runnable: uv run python -m rag.gate --baseline deliverables/gate-baseline.json --rows deliverables/gate-demo-no-rerank.json; echo "exit $?"
QUALITY GATE — retrieval, recall@5, paired by golden id

  baseline   58/91 = 0.64
  this run   57/91 = 0.63

  fixed        0  -
  broken       1  g017
  moved        3  (top-5 ids changed, found/not-found did not)
  unpaired     0  (new items, no baseline yet)
  exact McNemar p = 1.000  (context only; the gate reads `broken`)

BLOCKED — 1 golden answer(s) left the top 5: g017

baseline provenance: {"machine": "Darwin-arm64", "embed_model": "BAAI/bge-m3", "embed_revision": "5617a9f61b028005a4858fdac845db406aefb181", "embed_device": "mps", "rerank_model": "BAAI/bge-reranker-base", "rerank_revision": "2cfc18c9415c912f9d8155881c133215df768a70"}
exit 1
```

**Read every number:**

- **`58/91` → `57/91`.** 91 is the answerable items (100 minus the 9 unanswerable). One item left
  the top 5. **`0.64` → `0.63` is inside the ±0.097 band**, so a gate that compared averages would
  call this noise and pass it.
- **`broken 1 g017`.** The item. This is `D68`'s only fix, so the gate blocks exactly the question
  the reranker was shipped to answer.
- **`moved 3`.** `g013`, `g037`, `g041` had their top 5 reshuffled, still found or still not found.
  Not a failure. It is the line to read first when a result surprises you.
- **`p = 1.000`.** One broken, zero fixed: no evidence of a *systematic* change. The gate ignores
  p on purpose. A statistically invisible loss of one answer is still a lost answer for whoever asks
  `g017`.
- **`exit 1`.** What makes GitHub draw the red cross. A gate that prints BLOCKED and exits 0 is a
  comment. There is a test for exactly that (`test_main_exits_nonzero_and_writes_the_job_summary`).

**What the reranker actually does for `g017`**, the top 6 chunk ids from the two committed files:

```
with reranker      c02103 c02890 c01347 c00965 [c01603] c00970     answer at rank 5: reaches the prompt
without            c02103 c02890 c01347 c00965  c00970 [c01603]    answer at rank 6: does not
```

**One swap at the seat 5/6 boundary.** That is the entire lever (`D68`: promote into seat 5 from
ranks 6–10 when the cross-encoder margin is at least 0.8). Same shape as `backref` at rank 6 in
Phase 1 (§R4.3): the page was found, one seat short.

---

## R10.4 — Why one broken item fails, even when five others were fixed

**Side by side, two hypothetical PRs** (made-up numbers, to show the shape, not a measurement):

```
PR A    fixed 5   broken 0    recall 0.64 -> 0.70    PASS
PR B    fixed 6   broken 1    recall 0.64 -> 0.70    BLOCKED
```

Same average. PR B took an answer away from someone. The gate does not say PR B is wrong. It says
**a human must look at `broken` and decide**, instead of the loss riding in unseen under a better
average.

**This is not new strictness invented for CI.** It is the rule this repo already applied by hand:
Round 14 wrote *one regression is a hold* before its data, and that rule is what still holds prompt
`H` back (`D83`); it is what rejected the source framing (`D96`: `g043`).

**What it is not:** a claim that recall must never drop. A PR that deliberately trades `g017` for
something bigger can still merge. It just cannot merge *silently*.

---

## R10.5 — The ruler cannot be moved by the thing being graded

The obvious way to pass a gate that joins on id: **delete the item you broke.** Nothing to join,
nothing broken. Or flip it to `answerable: false`, and it stops being graded.

```
baseline: g017 answerable rank 5      PR deletes g017 from golden.json     naive join: PASS
                                                                          this gate: BLOCKED, "ruler changed"
```

Both fail as `ruler changed` (`missing`, `relabelled`). New items pass as `unpaired`, because there
is no baseline for them yet. And **the baseline is read from the base branch**, never from the PR's
own copy of `gate-baseline.json`, or a PR could rewrite the baseline to match what it broke.

This is `D06` enforced in CI: who verifies the golden set is a human decision, and a PR that edits
it should be reviewed as that, on its own.

---

## R10.6 — What CI can and cannot run, and where the hours go

| step | on a CI runner | cost |
|---|---|---|
| fetch corpus, chunk | yes, same steps as `docs reproduce` | small; not separately timed |
| **embed 3284 chunks with bge-m3** | yes, **CPU only** | **the long pole** — 1106 s on the Mac's 10-core CPU (`D97`); a runner's time is unmeasured |
| Qdrant | yes, a **service container**, same `v1.19.0` pin as Compose (`D41`) | seconds |
| BM25, query embedding, reranker for 100 questions | yes, CPU | minutes |
| **generation (Ollama)** | **no** | not graded here |

**The embeddings are cached**, keyed on exactly what they are a function of: the chunk file's bytes,
the model and revision, the window, normalisation, and the source of `embedding_input()`. A PR that
only changes retrieval code (the reranker demo) never re-embeds. A PR that changes `rag/chunk.py`
pays the full cost, and that is correct: it changed the thing the cache holds.

**What did NOT happen:** the vectors were not committed (`D11`, `D36`), and no GPU was rented.

**Why generation is not in the gate:** `D83`. Retrieval reproduced exactly across two machines;
generation reproduced nowhere. A check that flips depending on which runner GitHub assigns would be
switched off within a week, which is how measurement rules die.

---

## R10.7 — The bug the gate found before it ever ran

`rag/rerank.py`, since 2026-08-21:

```python
# Pinned like embed.MODEL_REVISION — changing it means re-measure, not retune.
MODEL_ID = "BAAI/bge-reranker-base"
...
_MODEL = CrossEncoder(MODEL_ID, device=embed.pick_device(None))     # no revision
```

The comment said pinned. **Nothing was pinned.** On one Mac with one cached snapshot, that never
mattered. On a CI runner, every cold cache downloads whatever the Hugging Face repo's `main` points
at *that day*. The reranker's only contribution is `g017`, decided by a margin of 0.8 at one seat
boundary, so a new upload could flip it with no code change, and **the gate would fail an innocent
PR.**

Now `MODEL_REVISION = "2cfc18c9…"`, passed to the load, and a test asserts the *load* receives it
(asserting the constant exists would have passed under the old bug). **Re-scored: 0.64, 7↑ 0↓,
p = 0.016, the same seven ids.** Pinning changed nothing, because it pinned what was already
there.

**The lesson, plainly:** a comment is a claim. `check_runnable` checks blocks and has no opinion
about comments. This one was wrong for three weeks and green the whole time.

---

## R10.8 — The machine question (`D97`)

The baseline rows were produced on the Mac: **MPS** for embeddings, queries and the reranker. The
runner will use a **CPU**. Two different pieces of hardware doing float arithmetic can disagree in
the last digits, and at a rank 5/6 boundary decided by a 0.8 margin, the last digits can matter.

**Why that would be fatal:** a phantom `broken` on every PR, from the hardware, not the code. `D83`
measured MPS and CUDA agreeing exactly; CPU had never been measured.

**So it was measured.** All 3284 chunks re-embedded on the Mac's CPU into a throwaway collection,
and the 100 questions scored with every model on CPU:

```
vectors bit-identical to MPS      0 of 3284      largest difference 0.000013
top-20 chunk lists identical      100 of 100
gate against the MPS baseline     fixed 0  broken 0  moved 0  -> PASSED
```

**Read the two lines together.** Not one vector is the same number. Not one ranking changed. The
hardware really does produce different floats, and the differences are far too small to swap two
chunks. Saying "CPU and GPU give the same vectors" would be false; "they give the same rankings
here" is what was measured.

**What it is not:** a measurement of the runner. The runner is a Linux x86 CPU with a different
math library from Apple's. If the first real run shows `moved` items on a PR that changed no
retrieval code, that is this question coming back, and `D97` names the fallback design.

---

## R10.9 — Say this out loud

**Say this:** “Every PR that touches retrieval rebuilds the index on a CI runner, scores the 100
golden questions, and fails if any question whose answer was in the top five no longer is. Removing
the reranker costs one point of recall, inside the noise band, and the gate blocks it by naming the
one question, `g017`. It grades retrieval only, because retrieval reproduced exactly across my
machines and generation didn't.”

**Do not say:** “CI blocks any quality regression.” It blocks *retrieval* regressions on the golden
set. A prompt change that makes answers worse passes it, and saying otherwise is the first follow-up
that sinks you.

**Follow-up:** *"Why not gate on the average?"* Because the average moved 0.64 → 0.63 for a lost
answer, and the band is ±0.097. An average gate passes it. The paired gate names the item.

**Follow-up:** *"What stops someone deleting the question they broke?"* The gate reads the baseline
from the base branch, and a missing or relabelled answerable item fails as "ruler changed".

---

## After this you can say

- what a required status check is, and which half of it lives in the repo
- why the gate is paired by id and ignores p
- why generation is not in CI, with the decision that measured it
- how the embedding cache key is built, and why hashing `rag/embed.py` whole would be wrong
- that the reranker was unpinned for three weeks, and how the gate would have turned that into a
  false failure
