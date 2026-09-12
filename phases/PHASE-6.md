# Phase 6 — Production: a change that makes it worse cannot merge quietly

Part of [`sqlalchemy-upgrade-agent`](../README.md). **Teaching file:
[`../study/18-PRODUCTION.md`](../study/18-PRODUCTION.md) (§R10) — read that first;** this file is
the measured plan, that one is the sitting. Follows [`PHASE-5.md`](PHASE-5.md), closed on
measurement (`D94`): the agent's levels are machine-dependent and its effects reproduce.
Spec: [`ROADMAP.md`](ROADMAP.md) Phase 6.

**Done when (ROADMAP):** a stranger can click a demo link and get a cited answer, **and a
quality-degrading PR gets auto-blocked.**

---

## The order, and why it is this order

| step | what | state |
|---|---|---|
| **1** | source framing — does the prompt's shape move `D72`'s over-refusals? | **closed, rejected** (`D96`) |
| **2** | **CI quality gate** — a PR that loses a golden answer fails a check | **built, demo reproduces locally** (`D97`); first run on a real runner not yet taken |
| 3 | routing with shadow cost — cheap questions local, hard ones to a strong model, priced | not started |
| 4 | deploy + package — a demo link and a README that opens with the product | not started |
| 5 | Langfuse — traces, tokens, latency, cost per query | last, on demand (standing decision) |

**The gate comes before routing and deploy** because both of those change the system, and every
change after this point should arrive with the gate already watching. Built last, it would grade
nothing that mattered.

---

## Step 1 — source framing (CLOSED, `D96`)

Arm B replayed the agent's conversation shape with no tools. Page-present over-refusals fell on
both machines (Mac 19 → 14, lab 20 → 17), but read by id the part that reproduces is **4 fixes, 1
break (`g043`) and 4 page-absent answers** where declining was the honest outcome, three of them
unsupported. **A willingness shift, not better reading.** Shipped prompt unchanged. Full write-up
`study/17-AGENT.md` §R9.7d; Round 21 in `logs/HANDOFF.md`.

---

## Step 2 — the CI quality gate (`D97`)

### What it grades

Retrieval only, recall@5, **paired by golden id**. Any answerable item whose answer page was in the
top 5 on the base branch and is not in this PR's run **fails the check**, whatever else improved.
Generation is not graded in CI: no Ollama on a runner, and `D83` measured generation not
reproducing across machines at all, while retrieval reproduced exactly.

### The pieces

| file | job |
|---|---|
| `rag/gate.py` | the join, the buckets (`fixed` / `broken` / `moved` / `unpaired`), the exit code |
| `deliverables/gate-baseline.json` | the rows the gate compares against, with provenance |
| `deliverables/gate-demo-no-rerank.json` | the ROADMAP's demo, measured: the reranker removed |
| `.github/workflows/gate.yml` | builds corpus → embeds (cached) → Qdrant service → scores → gates |
| `tests/test_gate.py` | 12 tests, seven mutations checked, all caught |

### The ROADMAP's demo, measured

*"Open a PR that removes your reranker, and film CI auto-rejecting it."* Run locally against the
committed rows, no Qdrant needed:

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

**`g017` is `D68`'s only fix**, so the gate blocks exactly the item the reranker was shipped for. A
one-point drop in recall (0.64 → 0.63) is inside the ±0.097 band and would pass an average-based
gate; the paired gate does not let it through.

### Found while building it: the reranker was never pinned

`rag/rerank.py` said *"Pinned like embed.MODEL_REVISION"* from 2026-08-21, and `CrossEncoder` was
given no revision. Harmless on one Mac with one cached snapshot; **fatal for a CI gate**, where a
fresh runner downloads whatever `main` points at and a new upload could flip `g017` with no code
change. Pinned to `2cfc18c9…`, the only snapshot in the Mac's cache and the one `refs/main` named.
**Verified to change nothing:** the re-score gives recall@5 **0.64** and **7↑ 0↓, p = 0.016**
against the Phase 1 baseline, the same seven ids as `D66`–`D68`.

### Still open — and it is the one that decides whether the gate is trustworthy

**The baseline was taken on MPS; a GitHub runner has only a CPU.** If CPU floats reorder a near-tie
at the rank 5/6 boundary, every PR would show a phantom `broken` item. `D83` measured MPS and CUDA
reproducing exactly; CPU is a third backend. **Measured on the Mac CPU (`D97`): 0 of 3284 vectors
bit-identical to MPS (max difference 1.3e-5), and 100 of 100 top-20 lists identical — gate `moved
0`, PASSED.** Linux x86 CPU, which is what a runner is, stays unmeasured until the workflow runs.

**Not done, and not Claude's to do:** open a PR so the workflow runs on a real runner, and mark the
check *required* in branch protection. Both are actions on the GitHub repository.
