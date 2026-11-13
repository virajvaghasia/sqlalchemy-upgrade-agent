# deliverables/

Every result the project quotes is a file here. Scripts read these files to print their
reports, so a number can be traced to the rows it was computed from without re-running a
model. A filename ending in `.Darwin-arm64.json` or `.Linux-x86_64.json` says which machine
produced the rows (an M4 Mac, or a Linux box with an RTX 3060); the same experiment was often
run on both, and they do not always agree. `phaseN` in a name is the stage of the project the
run belongs to; the key is in [`rag/__init__.py`](../rag/__init__.py).

## Start here

| file | what it is |
|---|---|
| [`BREAKAGES.md`](BREAKAGES.md) | 23 things that break between SQLAlchemy 1.4.52 and 2.0.51: the 1.4 code, the error 2.0.51 actually raised, and a fix that was executed. Generated as a skeleton by `verify_2_0 --stubs`, then explained by hand. |
| [`golden.json`](golden.json) | The test set: 100 questions (91 answerable, 9 with no answer in the docs), each with the passages that answer it. Half were written here, half are real questions from Stack Overflow and GitHub. Every item was verified by a person; `rag.score` refuses any that was not. |
| [`GOLDEN-FULLBAR-AUDIT.md`](GOLDEN-FULLBAR-AUDIT.md) | A second check of every golden item: the passages exist, the source page is live, and the claim executes on real 2.0.51. Written by `tools/audit_golden_fullbar.py`. |
| [`FAILURES.md`](FAILURES.md) | 19 questions chosen to break the first, naive pipeline, with what was retrieved and what was answered. Written by `rag.probe`; verdicts come from `verdicts.json`. |

## Retrieval

| file | what it is | produced by |
|---|---|---|
| `baseline-phase1.json` | Per-question retrieval ranks for the naive pipeline, on the first 50 golden questions. Every later retrieval change is compared against it question by question. | `rag.score --save` |
| `gate-baseline.json` | Ranks for the shipped retrieval on all 100 questions. The CI quality gate fails a pull request that loses any top-5 hit against this file. | `rag.score --save` |
| `gate-demo-no-rerank.json` | The same run with the reranker removed: the rows behind the demonstration that the gate blocks a regression. | `rag.score --no-rerank --save` |
| `route-signals-phase6.Darwin-arm64.json` | Per-question reranker scores, used to test whether a router could predict which questions the local model will fail. | `rag.route --signals` |
| `latency.Darwin-arm64.memory.mps.json`, `latency.Darwin-arm64.memory.cpu.json` | How long each retrieval stage took per question, on the Mac's GPU (all 100) and its CPU (the first 20), with p50 and p95. The reranker is nearly all of it. | `rag.bench` |

## Answers: refusals, citations, faithfulness

| file | what it is | produced by |
|---|---|---|
| `prompt-sweep-phase4.json` | Every golden question answered under three prompt wordings in one run (Mac). | `rag.compare_prompts --golden --save` |
| `prompt-sweep-round16.Linux-x86_64.json` | The same comparison for two wordings on the Linux GPU box. Several later experiments reuse these answers as the local model's baseline. | `rag.compare_prompts --golden --save` |
| `faithfulness-phase4.<machine>.json` | A judge model's verdict (supported, partial, unsupported) on each saved answer, per machine. | `rag.faithful --sweep --local` |
| `faithfulness-phase4.json` | The same rows at the path both machines used before per-machine files existed. Kept because the report de-duplicates by content and older clones only have this path. | (legacy) |
| `faithfulness-phase4-headings.Linux-x86_64.json` | The judge re-run with each passage shown exactly as the model saw it, heading included. | `rag.faithful --sweep --local --headings` |
| `JUDGE-AGREEMENT.md` | Ten of the judge's verdicts re-read against the passages, risk-weighted toward the doubtful ones: 7 of 10 agree. | `rag.faithful --agreement`, then filled in |
| `JUDGE-CROSSCHECK.json` | A second model's verdicts on the same ten. | `rag.faithful --cross-check` |
| `OPEN-CELL-REVIEW.md` | Answers given without the verified page in the prompt, laid out for a person to rule on. | `rag.judge --open-cell` |
| `verdicts.json` | The verdicts on the 19 probe answers. `FAILURES.md` renders from it. | edited by hand, applied with `tools.apply_verdicts` |
| `framing-phase6.<machine>.json`, `framing-judge-phase6.Darwin-arm64.json` | The same prompt in two conversation shapes, and the judge's verdicts on the Mac run. | `rag.framing` |

## Agent

| file | what it is | produced by |
|---|---|---|
| `agent-sweep-phase5.<machine>.json` | The golden set run through the agent with its default prompt. | `rag.agent --golden` |
| `agent-sweep-phase5-forced-nudged.<machine>.json` | The same with two changes: the first tool call is required, and a hint is appended when a lookup finds nothing. | `rag.agent` |
| `agent-sweep-phase5*-trunc600.*.json` | Earlier runs made while a bug cut every retrieved passage to 600 characters. Kept because the bug is only demonstrable while both sets exist; not quoted as results. | `rag.agent` |
| `e1-phase5`, `e2-phase5`, `e4-phase5` | Three paired experiments: a prompt that orders a tool call, a loop that requires one, and the hint after an empty lookup. | `rag.agent --e1`, `--e2`, `--e4` |

## Routing to a stronger model

| file | what it is | produced by |
|---|---|---|
| `escalate-phase6.json`, `escalate-rest-phase6.json` | The local model's refusals re-asked of a hosted model: the 20 where the answer page was in the prompt, and the other 33. | `rag.escalate` |
| `ESCALATE-PARTIAL-REVIEW.md` | The escalated answers the judge called partial, each re-read against the five passages the model was given, with a verdict and a one-line reason. | `rag.escalate --report --sheet`, then filled in |
| `nemotron-all-phase6.json`, `nemotron-all-repeat-phase6.json` | The hosted model on all 100 questions, and the first 20 asked again to measure repeatability. | `rag.escalate --all` |
| `nemotron-all-delivered.json` | The ids of the hosted model's delivered answers; the input to `tools/check_nemotron_all.py`, which executes each answer's central claim. | `rag.escalate` |
| `qwen-lab-judged-phase6.json` | The local model's answers graded by the same judge as the hosted model's. | `rag.escalate --judge-qwen` |
| `prices-phase6.json` | One reseller's per-token list prices, fetched on 2026-09-12 and used to price the cascade. The calls themselves ran on free credits. | fetched |

## Prompt injection

| file | what it is | produced by |
|---|---|---|
| `inject-phase7.Linux-x86_64.json` | 30 injection attempts against the pipeline with the local model. | `rag.inject` |
| `inject-phase7-step1.Linux-x86_64.json` | The same attempts with untrusted text marked in the prompt, two ways, plus a control. | `rag.inject` |
| `inject-phase7-demo.Darwin-arm64.json`, `inject-phase7-demo-fenced.Darwin-arm64.json` | The attempts against the hosted model, without and with the marking. | `rag.inject` |
| `inject-phase7-prompth.Linux-x86_64.json`, `inject-phase7-prompth-control2.Linux-x86_64.json` | The attempts against the prompt that later shipped, and a second run of the control taken the same day. | `rag.inject` |
| `CANARY-REVIEW-*.md` | One sheet per run above. The automatic check only sees whether the attacker's token appears in the answer, which cannot tell obeying from quoting it to refuse, so each attempt was read and marked COMPLIED or REPORTED. | `rag.inject --review`, then filled in |

`uv run python -m rag.judge --report` and `uv run python -m rag.inject --report <file>` print the
figures from these rows.
