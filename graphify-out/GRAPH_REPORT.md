# Graph Report - sqlalchemy-upgrade-agent  (2026-08-19)

## Corpus Check
- 73 files · ~207,929 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1074 nodes · 1841 edges · 68 communities (61 shown, 7 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 103 edges (avg confidence: 0.86)
- Token cost: 333,718 input · 0 output

## Community Hubs (Navigation)
- Breakages and Failures Registry
- Phase 2 Scorer
- Corpus Fetch and Manifest
- The Six-Phase Roadmap
- Probe Signals and Tests
- Compose Stack and CI
- Embedding Pipeline
- Session Runtime States
- Embedding and Index Decisions
- Prompt Wording Experiment
- Corpus Selection Rules
- Evaluation Method Decisions
- Chunk Audit Tests
- Qdrant Index Tests
- Prompt Assembly Tests
- Retrieval Study Notes
- Seeding the Database
- SQLAlchemy ORM Concepts
- The Mapped Model Schema
- Prompt Variant Comparison
- Lab PC Runbook
- Database Connection Config
- Verification Doc Tests
- The 2.0 Migration Chapter
- Docker Image Fundamentals
- Model Schema Tests
- Runnable Block Checker
- Study Index and Numbering
- Compose and Postgres Notes
- Build Naive First
- The Query Layer App
- Migration Measurement Script
- Pytest Fixtures
- Warning Class Sweep
- The Chunker
- Review Sheet Builder
- Phase 2 Metric Decisions
- Prompt Comparison Harness
- Qdrant Client
- The Practice App Schema
- Probe Report Generator
- Corpus and Version Skew
- Test Suite Notes
- Backref and Result API
- Chunk Boundary Decisions
- Chunk File Assembly
- Section Splitting
- Pattern Verification on 2.0
- Content Atom Filter
- Chunk Packing
- Test Purpose Notes
- Compose Networking
- The Ask Entrypoint
- Volumes and Image Traps
- Block Splitting
- Image Naming Traps
- Mapper Configuration Check
- Glossary Chunking
- Base Image Choice
- The ORM Explorer Script
- Refusal Clause Tests
- Container Entrypoint
- Experiments Package Manifest
- RAG Package Manifest
- How To Explain Things
- Branch Per Phase
- Project Root

## God Nodes (most connected - your core abstractions)
1. `Design decisions — the register (D01…D62)` - 66 edges
2. `BREAKAGES.md — the Phase 0 Part A deliverable` - 42 edges
3. `ROADMAP — the six-phase arc` - 38 edges
4. `FAILURES.md — the Phase 1 deliverable` - 37 edges
5. `Retrieval — study notes (§R1–§R2)` - 25 edges
6. `Evaluation — study notes (§R4)` - 24 edges
7. `01-CONCEPTS.md — SQLAlchemy concepts (§0–§15)` - 21 edges
8. `Phase 2 — Measure it (Crown Jewel #1)` - 18 edges
9. `Generation — study notes (§R3)` - 17 edges
10. `04-DOCKER.md — Docker study notes (§1–§3)` - 16 edges

## Surprising Connections (you probably didn't know these)
- `D39 — The Query.get() prediction did not reproduce` --semantically_similar_to--> `D43 — The refusal clause is necessary and over-fires`  [INFERRED] [semantically similar]
  phases/PHASE-1.md → CLAUDE.md
- `D20 — image: is declared explicitly in Compose` --semantically_similar_to--> `D41 — Collection name carries model and revision`  [INFERRED] [semantically similar]
  study/09-DECISIONS.md → CLAUDE.md
- `The scorer reads corpus/chunks.jsonl, never FAILURES.md` --semantically_similar_to--> `D46 — probe.py records signals and never verdicts`  [INFERRED] [semantically similar]
  phases/PHASE-2.md → CLAUDE.md
- `D18 — python:3.11-slim, not Alpine` --semantically_similar_to--> `D48 — The 3060 embeds 2.8x faster than the M4`  [INFERRED] [semantically similar]
  study/09-DECISIONS.md → CLAUDE.md
- `The 'eyeball ten at random' gate` --semantically_similar_to--> `The verdict test: write the code, run it, compare against the verified fix`  [INFERRED] [semantically similar]
  phases/PHASE-1.md → deliverables/FAILURES.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **The Phase 1 pipeline: corpus to chunks to vectors to Qdrant to an answer with sources** — phases_phase_1_step_1_corpus, phases_phase_1_step_2_chunk, phases_phase_1_step_3_embed, phases_phase_1_step_4_ask, phases_phase_1_step_5_probe [EXTRACTED 1.00]
- **The refusal-clause experiment: four wordings, eleven lab rounds, three decisions correcting each other** — phases_phase_1_prompt_a, phases_phase_1_prompt_b, phases_phase_1_prompt_c, phases_phase_1_prompt_d, study_09_decisions_d43, study_09_decisions_d51, study_09_decisions_d52, study_09_decisions_d54, logs_handoff_round_8, logs_handoff_round_10, logs_handoff_round_11 [EXTRACTED 1.00]
- **Designing the Phase 2 ruler: five decisions settled before any score existed** — phases_phase_2_golden_set, phases_phase_2_score_py, study_09_decisions_d58, study_09_decisions_d59, study_09_decisions_d60, study_09_decisions_d61, study_09_decisions_d62, study_09_decisions_d06 [EXTRACTED 1.00]
- **Where N+1 comes from: expiry, lazy loading, and the two eager strategies** — study_01_concepts_section_15, study_01_concepts_expire_on_commit, study_01_concepts_lazy_loading, study_01_concepts_n_plus_1, study_01_concepts_selectinload, study_01_concepts_joinedload [EXTRACTED 1.00]
- **Container readiness: depends_on is not ready, healthcheck closes the gap, retry generalises** — study_05_compose_section_4_2, study_05_compose_healthcheck, study_05_compose_cmd_shell_trap, study_05_compose_app_side_retry [EXTRACTED 1.00]
- **The infrastructure § sequence continuing across four files (§1–§6)** — study_04_docker_section_1, study_04_docker_section_2_1, study_04_docker_section_3_1, study_05_compose_section_4_0, study_06_postgres_section_5_1, study_07_tests_section_6_1 [INFERRED 0.90]
- **The prompt-wording experiment arc (Rounds 8–11): four wordings, 19 questions, two values of k** — study_09_decisions_d43, study_09_decisions_d52, study_09_decisions_d53, study_09_decisions_d54, study_11_generation_prompt_a, study_11_generation_prompt_b, study_11_generation_prompt_c, study_11_generation_prompt_d, study_10_retrieval_default_k [EXTRACTED 1.00]
- **The §R1–§R5 RAG run across four files (D47: the R stands for RAG)** — study_10_retrieval_r1, study_10_retrieval_r2, study_11_generation_r3, study_12_evaluation_r4, study_13_verification_r5, study_09_decisions_d47, study_readme_numbering_families [EXTRACTED 1.00]
- **Phase 2's metric decisions P2-a…P2-e, decided before any score exists** — study_09_decisions_d58, study_09_decisions_d59, study_09_decisions_d60, study_09_decisions_d61, study_09_decisions_d62, study_12_evaluation_recall_at_k, study_09_decisions_mcnemar_test [EXTRACTED 1.00]

## Communities (68 total, 7 thin omitted)

### Community 0 - "Breakages and Failures Registry"
Cohesion: 0.05
Nodes (71): The 'Also defensible' blocks, BREAKAGES.md — the Phase 0 Part A deliverable, BREAKAGES #1 — engine.execute(string), BREAKAGES #10 — orm.relation() alias, BREAKAGES #11 — Query.filter(raw string), BREAKAGES #12 — Query.from_self(), BREAKAGES #13 — Query.join(aliased=True), BREAKAGES #14 — joinedload(string) (+63 more)

### Community 1 - "Phase 2 Scorer"
Cohesion: 0.06
Nodes (54): aggregate(), compare(), dedup_key(), duplicate_slots(), load_chunks(), load_golden(), main(), mcnemar_exact() (+46 more)

### Community 2 - "Corpus Fetch and Manifest"
Cohesion: 0.06
Nodes (50): build_manifest(), check(), download(), extract(), is_selected(), main(), pin_1_4(), pin_2_0() (+42 more)

### Community 3 - "The Six-Phase Roadmap"
Cohesion: 0.06
Nodes (47): The collaboration rule, The golden dataset is hand-verified, never auto-generated, The lab PC (Dell XPS 8950, kj-XPS-8950), Langfuse stays Phase 6 and on-demand, Session Notes — the per-session action log, Zero paid API calls, Round 3 — share the Tailscale node, Round 4 — Phase 1 has started, and this PC is the GPU half (+39 more)

### Community 4 - "Probe Signals and Tests"
Cohesion: 0.08
Nodes (41): needs_report, _contains(), corpus_chunk_count(), Whole-symbol match, not substring. Naive `symbol in text` counted `relation`…, How many chunks in the whole corpus contain this string. This is the number…, Mechanical only. Nothing here is an opinion about correctness., signals(), hit() (+33 more)

### Community 5 - "Compose Stack and CI"
Cohesion: 0.07
Nodes (40): tools/check_runnable.py, ENV-classified blocks, The example rule, The image holds code; the container holds data, The measurement rule, Naming conventions — one name everywhere it can be one, Diff, never regenerate over this file, db healthcheck: pg_isready with the real role (+32 more)

### Community 6 - "Embedding Pipeline"
Cohesion: 0.07
Nodes (35): load_chunks(), main(), Settle D32 — is BGE-M3 the right embedding model, or just the one we picked? uv…, score(), embedding_input(), load_chunks(), main(), peak_memory() (+27 more)

### Community 7 - "Session Runtime States"
Cohesion: 0.07
Nodes (28): annotate(), _count(), describe(), print_stmt(), states.py — SQLAlchemy 1.4 runtime behaviour, measured rather than asserted.…, Run `work` with a clean session cache and return the SQL count., Say what a statement is FOR, derived from the statement itself. Deriving beats…, One line per moment: where the object is, and what it still remembers.… (+20 more)

### Community 8 - "Embedding and Index Decisions"
Cohesion: 0.11
Nodes (35): Round 5 — embed on the 3060, Phase 1 Step 3 — embed and store, Why a database at all, when a dot product already worked, Design decisions — the register (D01…D62), D01 — A codebase migration assistant, not a chatbot, D02 — SQLAlchemy 1.4 → 2.0 as the subject, D03 — The corpus is measured, not scraped, D05 — Zero paid API calls (+27 more)

### Community 9 - "Prompt Wording Experiment"
Cohesion: 0.14
Nodes (32): The healthcheck that lied (/dev/tcp under CMD-SHELL), Round 1 — sshd and the LAN address, Round 10 — the run that separates the prompt from retrieval, Round 11 — run it to a conclusion, not to another round, Round 2 — the LAN is not a route, so Tailscale is the only way in, Round 6 — settle D43's A cell, which the Mac cannot, Round 7 — does raising k fix failures Phase 3 was going to fix?, Round 8 — is the refusal clause the reason, or the model? (+24 more)

### Community 10 - "Corpus Selection Rules"
Cohesion: 0.08
Nodes (25): decision, API reference, changelog/ (except migration_20.rst), deliverables/BREAKAGES.md, dialects/, index/contents/copyright/intro .rst, files, generated_by (+17 more)

### Community 11 - "Evaluation Method Decisions"
Cohesion: 0.20
Nodes (24): Phase 1 Step 5 — break it on purpose (rag/probe.py), Two failures that look identical and need opposite fixes, The rank of the first correct chunk is worth more than recall, D06 — The golden dataset is hand-verified, never auto-generated, D09 — BREAKAGES.md stays out of the retrieval corpus, D31 — Qdrant stays although pgvector won on every number, D40 — Qdrant over a NumPy dot product — and not for speed, D45 — Split retrieval failure from the corpus ceiling (+16 more)

### Community 12 - "Chunk Audit Tests"
Cohesion: 0.09
Nodes (21): _c(), What the chunker must never do, pinned. Phase 1 Step 2 has two rules that are…, chunks.jsonl is generated and gitignored, so this skips in CI., The committed stats describe the code as it stands, not a past run., If the median sat at HARD_MAX the packer would be cramming rather than…, Oversized means one code block bigger than HARD_MAX, emitted whole. That is the…, PHASE-1.md pastes this module's report. Fails if the chunker moves and the doc…, c00138's actual opening. If this stops matching, the audit stops seeing the… (+13 more)

### Community 13 - "Qdrant Index Tests"
Cohesion: 0.13
Nodes (22): needs_qdrant, collection_name(), Project name, model, and the first 8 of the revision that produced it., _live_client(), needs_stats, What the Qdrant collection must never silently become. The failure this guards…, Step 3's stated gate: the count in the database matches the count of chunks. A…, COSINE with unit vectors. A collection built as DOT or EUCLID would still… (+14 more)

### Community 14 - "Prompt Assembly Tests"
Cohesion: 0.14
Nodes (21): build_prompt(), hit(), What the answering step must not quietly lose. Two properties, both easy to…, Prompt D, shipped 2026-08-17 (D54). This used to assert the B wording — "prefer…, A stand-in for a Qdrant point — only .payload and .score are used., The model is told to cite [2]. If numbering starts at 0, every citation it…, Retrieval is unfiltered on purpose, so both releases arrive together. A prompt…, Same reason the chunker keeps it and the embedder prepends it: a passage saying… (+13 more)

### Community 15 - "Retrieval Study Notes"
Cohesion: 0.21
Nodes (21): Retrieval — study notes (§R1–§R2), The 270-file corpus (4058424 bytes, both pinned tags), 3284 chunks / corpus/chunks.jsonl, The API-reference hole / the 270-file ceiling (R1.4), BGE-M3 (BAAI/bge-m3), Cosine similarity — the angle, not a percentage, Cross-version duplicate chunks eating top-k slots, DEFAULT_K = 5 (+13 more)

### Community 16 - "Seeding the Database"
Cohesion: 0.15
Nodes (17): is_seeded(), seed.py — build a database big enough for the problems to show up. `explore.py`…, Does this database already hold data? seed() starts with drop_all(). That was…, seed(), _counts(), The seed is deterministic, idempotent, and does not eat existing data. Every…, Two fresh databases, same fixed RANDOM_SEED, identical content. Not just…, Re-running rebuilds rather than appending. seed() opens with drop_all()… (+9 more)

### Community 17 - "SQLAlchemy ORM Concepts"
Cohesion: 0.11
Nodes (19): logs/LEARNING-LOG.md, 01-CONCEPTS.md — SQLAlchemy concepts (§0–§15), Association object, Deferred resolution of quoted names, ForeignKey, primaryjoin / secondaryjoin, remote_side, §0 — The whole schema on one screen (+11 more)

### Community 18 - "The Mapped Model Schema"
Cohesion: 0.18
Nodes (12): Base, new_issue(), seed(), seed_shape(), Comment, Issue, IssueAssignment, Label (+4 more)

### Community 19 - "Prompt Variant Comparison"
Cohesion: 0.13
Nodes (18): The shipped variant IS ask.SYSTEM; the others rebuild it around a different…, system_prompt(), Pin the three D43 prompt variants. These tests never call Ollama. They check…, D must differ from B in kind, not degree. D52: A and B refused the same 8…, Only the refusal sentence may vary, or the comparison measures something else., B must BE ask.SYSTEM — the object identity check — AND ask.SYSTEM must still…, Strip the refusal sentence from each and the remainder must be identical., One answerable, one the corpus provably cannot answer — the point of the test. (+10 more)

### Community 20 - "Lab PC Runbook"
Cohesion: 0.17
Nodes (16): CLAUDE.md — working agreement, logs/HANDOFF.md, docker-compose.yml (app + db), §4.5 — GPU in a container (Day 7), 08-LAB.md — lab PC from-scratch runbook, Borrow, work, revert — leave the shared box as you found it, Days 8–9 CI gate — a deliberately failing PR must block merge, Docker Engine install (not snap, not docker.io, not Desktop) (+8 more)

### Community 21 - "Database Connection Config"
Cohesion: 0.14
Nodes (15): make_engine(), Single source of truth for the DB location, imported by app.py in Step 4.…, Block until the database accepts a connection, then return. Compose's…, wait_for_db(), Database location and reachability — the two things Compose changed.…, With no env var set, Part A behaviour is unchanged. This is the property that…, Compose sets this; the app reads it. No code change, no edit., The happy path costs one connection and no sleeping. (+7 more)

### Community 22 - "Verification Doc Tests"
Cohesion: 0.15
Nodes (15): `study/13-VERIFICATION.md` answers the questions `phases/PHASE-1.md` asks. Two…, The questions as PHASE-1.md states them, in order., The gate is 'the five cold verification questions'. If that stops being five,…, Each question appears word for word in the answers file. Rewording one in…, R5.1-R5.5 are one section per question, and each carries a 'Say this' block.…, The gate is 'cold, from memory, no notes' (PHASE-1.md). A file of model answers…, R5.7 is the five answers said end to end, for rehearsing as one piece. It only…, Every figure quoted in R5.7 is one this repo measured. If a chunker or corpus… (+7 more)

### Community 23 - "The 2.0 Migration Chapter"
Cohesion: 0.15
Nodes (14): classify(), candidates.py — a shortlist of 1.4 patterns worth TESTING for…, Block contracts — # runnable / # summary of / # illustration, Predict before you run, 02-MIGRATION-2.0.md — the 1.4 → 2.0 upgrade (§16–§22), A real breakage vs a style preference, future=True, Predictions — deliberately unanswered (+6 more)

### Community 24 - "Docker Image Fundamentals"
Cohesion: 0.15
Nodes (14): 04-DOCKER.md — Docker study notes (§1–§3), The build cache, The last layer to touch a path wins, §1 — The mental model, §1.1 — Image vs container, §1.2 — Layers, §1.3 — The layer cache, §2.2 — WORKDIR (+6 more)

### Community 25 - "Model Schema Tests"
Cohesion: 0.14
Nodes (13): The schema is what the docs describe. These are not "does SQLAlchemy work"…, Nothing is only wired up lazily. Mapper configuration is deferred until first…, PRACTICE-APP.md's headline numbers. They differ because issue_labels and…, issue_labels is a plain secondary table: two FKs and nothing else., issue_assignments is an association OBJECT — it has columns of its own. This is…, Issue points at Issue, in both directions, through issue_blocks., create_all() emits a schema the database accepts., test_association_object_carries_its_own_data() (+5 more)

### Community 26 - "Runnable Block Checker"
Cohesion: 0.23
Nodes (10): Block, execute(), main(), normalise(), parse(), Path, Check that every `# runnable` block in the docs actually reproduces. uv run…, Extract runnable blocks. The command may span several `#` lines. (+2 more)

### Community 27 - "Study Index and Numbering"
Cohesion: 0.21
Nodes (13): Phase 1 verification — five questions asked cold, Phase 2 verification — five questions asked cold, D23 — The Postgres role is app, not the project name, D30 — One name, everywhere it can be one, D47 — One R run across retrieval, generation and evaluation, D55 — The five verification answers got their own file, against this repo's own no-new-files rule, D57 — The five cold verification questions are closed, Verification — study notes (§R5) (+5 more)

### Community 28 - "Compose and Postgres Notes"
Cohesion: 0.19
Nodes (13): README.md — the repo map, 05-COMPOSE.md — multi-container notes (§4), §4.3 — Why Postgres for the exercise, §4.6 — POSTGRES_USER does not give you a limited account, 06-POSTGRES.md — Postgres study notes (§5), postgres is the maintenance database, not yours, §5.2 — The psql survival kit, §5.3 — Three databases, two of which are machinery (+5 more)

### Community 29 - "Build Naive First"
Cohesion: 0.21
Nodes (12): Build the naive version first, Aug 15 — Phase 1 Steps 3-5, and three things that turned out wrong, The predicted Query.get() failure did not happen, Why 'dumb first' — read this twice, Dense retrieval, D04 — Build the naive version first, D39 — The Query.get() prediction did not reproduce, D50 — The fixes are verified twice (+4 more)

### Community 30 - "The Query Layer App"
Cohesion: 0.17
Nodes (11): count_issues_raw(), fetch_issue_then_close(), get_issue(), issue_report(), open_issues_for_project(), app.py — the query layer, written badly on purpose. Every function here works…, Returns a *detached* Issue: the session that loaded it is already closed by the…, Legacy Query API. Measured: emits **no warning** even under WARN_20, and still… (+3 more)

### Community 31 - "Migration Measurement Script"
Cohesion: 0.18
Nodes (10): attach_trial(), fold_columns(), fresh_engine(), print_wrapped(), migration.py — the 1.4 → 2.0 migration mechanics, measured on 1.4.52.…, Abbreviate the SELECT list for DISPLAY only, so the line fits a doc block.…, Attach an Issue to a Project by `build`, flush, count what landed., Print a long library message across several lines, wrapped HERE. SQLAlchemy's… (+2 more)

### Community 32 - "Pytest Fixtures"
Cohesion: 0.20
Nodes (11): fixture(), Two projects' worth of rows, built the way that works on both versions., db_path(), empty_schema(), engine(), Shared fixtures. Every test gets its own throwaway SQLite file. Deliberately…, A fresh SQLite path, thrown away after each test., An engine on an empty database, schema not yet created. (+3 more)

### Community 33 - "Warning Class Sweep"
Cohesion: 0.20
Nodes (11): normalise(), sweep.py — step 1 of the migration recipe, done across the WHOLE package.…, Run one module under the 2.0 warning flags and return its warnings., sweep_module(), LegacyAPIWarning, MovedIn20Warning, RemovedIn20Warning, §19 — Reading the warnings: four classes, two silent by default (+3 more)

### Community 34 - "The Chunker"
Cohesion: 0.27
Nodes (11): audit(), build(), main(), _non_blank(), Phase 1, Step 2 — cut the corpus into chunks, without cutting anything that has…, Count chunks that do not stand on their own, and say how many are lost. Two…, report(), report_audit() (+3 more)

### Community 35 - "Review Sheet Builder"
Cohesion: 0.23
Nodes (11): breakages(), build(), fix_of(), key_for(), main(), Condense FAILURES.md into a sheet the 19 verdicts can actually be judged from.…, The whole sheet, as markdown., Write the sheet, or print it with --stdout. (+3 more)

### Community 36 - "Phase 2 Metric Decisions"
Cohesion: 0.18
Nodes (11): Phase 1 — A deliberately dumb RAG, Phase 1 Step 4 — retrieve and answer (rag/ask.py), Phase 2 — Measure it (Crown Jewel #1), The 19 probe questions cannot be the golden set, P2-b k for recall@k, P2-c whether the 19 probe questions enter, P2-d 30 or 50 items, P2-e does refusal accuracy belong in Phase 2 (+3 more)

### Community 37 - "Prompt Comparison Harness"
Cohesion: 0.27
Nodes (10): generate(), main(), Re-run D43 — is the refusal clause necessary, and does the strict wording over-…, One Ollama call with an overridden system message. Mirrors ask.generate()., The canned sentence is the refusal signal, matched on its stable prefix.…, Every probe question against each wording, counting refusals. D43 chose prompt…, refused(), sweep_all() (+2 more)

### Community 38 - "Qdrant Client"
Cohesion: 0.33
Nodes (10): build(), client(), load_inputs(), main(), query_vector(), Phase 1, Step 3b — load the vectors into Qdrant. docker compose up -d qdrant #…, Embed one question, using the corpus's own settings. Every one of these must…, Top-`limit` hits, newest-first by score. Shared by --search and rag.ask. (+2 more)

### Community 39 - "The Practice App Schema"
Cohesion: 0.22
Nodes (10): deliverables/BREAKAGES.md, secondary= table, §5 — Self-referential: one table, two FKs, a real ambiguity, §8 — secondary=: the two joins you didn't write, 03-PRACTICE-APP.md — the app under test, The five 1.4 patterns the schema must force, issue_blocks — the self-referential table, issue_labels — the plain secondary table (+2 more)

### Community 40 - "Probe Report Generator"
Cohesion: 0.29
Nodes (9): classify(), Return (warning classes under WARN_20, outcome under 2.0 rules).…, main(), Phase 1, Step 5 — run questions with known answers and record where it fails.…, Confirmed verdicts, so a regeneration preserves them (see…, run(), summarise(), _verdicts() (+1 more)

### Community 41 - "Corpus and Version Skew"
Cohesion: 0.31
Nodes (10): 26.6% of the index is a cross-version duplicate, Phase 1 Step 1 — decide the corpus, and write down why, Cross-version duplicates break recall@k unless the metric says what it counts, P2-a duplicate-pair counting, 437 duplicate pairs with byte-identical vectors, D07 — The API reference is not in the .rst source, D08 — Narrative prose only; changelog/ excluded except migration_20.rst, D10 — Version skew is recorded, not filtered (+2 more)

### Community 42 - "Test Suite Notes"
Cohesion: 0.22
Nodes (10): App-side retry (wait_for_db) — the fix that generalises, CMD-SHELL is /bin/sh — the healthcheck that lied, Healthcheck with condition: service_healthy, §4.2 — depends_on does not mean ready, 07-TESTS.md — test suite study notes (§6), conftest.py — where pytest finds shared fixtures, §6.3 — Fixtures, and where pytest finds them, §6.4 — Making the suite runnable at all (+2 more)

### Community 43 - "Backref and Result API"
Cohesion: 0.25
Nodes (8): back_populates (the 2.0 style pair), backref, §10 — backref: one declaration, two attributes, and the swap, cascade_backrefs — the breakage that doesn't raise, The Result API, §17 — The Result API: rows, scalars, and the common 2.0 papercut, .unique() — the papercut behind the papercut, §6.5 — The tests must not use the idioms this repo documents as broken

### Community 44 - "Chunk Boundary Decisions"
Cohesion: 0.43
Nodes (8): The chunk-boundary audit — shapes A and B, The 'eyeball ten at random' gate, Phase 1 Step 2 — chunk it, D33 — Chunk overlap carries whole prose blocks or nothing, D34 — Overlap is by whole block rather than by character, D35 — The 'eyeball ten at random' gate is not ceremony, D56 — The chunk-boundary defect is bounded and named, not fixed, §R5.3 Q3 — 'Your chunker split a code block. Why does that matter more than it sounds?'

### Community 45 - "Chunk File Assembly"
Cohesion: 0.25
Nodes (8): chunk_file(), merge_small(), Path, Fold anything under `floor` into its neighbour rather than emitting it. Merging…, Step 2's "Done when" asks for source file, heading path AND character range.…, An offset that is present but wrong is worse than one that is absent., test_a_chunk_reports_where_in_the_source_it_came_from(), test_the_range_actually_brackets_the_chunk()

### Community 46 - "Section Splitting"
Cohesion: 0.25
Nodes (8): Return (heading_path, start_line, end_line) for every section in a file.…, split_sections(), `===` / title / `===` is one heading. Missed, the overline becomes a…, A chunk saying "this was removed" needs the heading naming what "this" is. Per…, An adornment shorter than the line above it is a table rule, not a title., test_heading_path_carries_ancestry(), test_overlined_title_is_not_its_own_section(), test_table_rule_is_not_read_as_a_heading()

### Community 47 - "Pattern Verification on 2.0"
Cohesion: 0.29
Nodes (4): patterns.py — the 1.4 patterns under test, shared by candidates.py and…, emit_stubs(), verify_2_0.py — run the candidate patterns against REAL SQLAlchemy 2.0.…, Print a deliverables/BREAKAGES.md skeleton with the two halves we actually…

### Community 48 - "Content Atom Filter"
Cohesion: 0.33
Nodes (7): is_content(), Does this atom say anything, or is it scaffolding? Strip the lines that exist…, parametrize, These retrieve nothing but can still win a short query, so they are worse than…, note / versionadded / seealso are content, and often the most quotable content…, test_markup_only_atoms_are_dropped(), test_real_content_survives()

### Community 49 - "Chunk Packing"
Cohesion: 0.29
Nodes (7): pack(), Greedily fill chunks up to `target`, never splitting a block. Returns (text,…, The first version carried `tail[-200:]` and produced a chunk opening with the…, A duplicated half-example is the failure this module exists to avoid., test_code_is_never_carried_forward(), test_overlap_carries_whole_blocks_only(), test_pack_never_splits_a_block()

### Community 50 - "Test Purpose Notes"
Cohesion: 0.29
Nodes (7): Six mapped classes, eight tables, A green build proves nothing — CMD never runs at build time, PID 1 and signal handling, §2.5 — CMD vs ENTRYPOINT, Count collected, not passed — a headline that moves with the environment is not a headline, Every test pins a claim some document makes, §6.1 — What these tests are for

### Community 51 - "Compose Networking"
Cohesion: 0.29
Nodes (7): The repo's Dockerfile, ports: is only for traffic from outside, §4.0 — Compose does not replace the Dockerfile, §4.1 — Networking: why the container can't reach anything, Service-name DNS — the service name is a hostname, User-defined network — DNS plus isolation, §5.1 — Getting a shell without opening a port

### Community 52 - "The Ask Entrypoint"
Cohesion: 0.47
Nodes (5): ask(), generate(), main(), Phase 1, Step 4 — ask a question, get an answer and the chunks it came from. uv…, One non-streaming call to Ollama. Returns the answer and its timings. Ollama…

### Community 53 - "Volumes and Image Traps"
Cohesion: 0.47
Nodes (6): The build-time-seed trap — the image holds code, the container holds data, entrypoint.sh — seed, then exec "$@", §3.4 — The image is not self-sufficient, Bind mount — you own the storage, Named volume — Docker owns the storage, §4.4 — Volumes and persistence

### Community 54 - "Block Splitting"
Cohesion: 0.40
Nodes (5): Break a section body into atoms: ("code"|"prose", text, first_line, last_line).…, split_blocks(), In RST the line ending `::` is the last line of the introducing paragraph.…, test_code_atom_keeps_the_sentence_that_introduces_it(), test_code_block_is_one_atom()

### Community 55 - "Image Naming Traps"
Cohesion: 0.40
Nodes (5): .dockerignore is not .gitignore, §1.4 — Build context, Declaring image: so Compose cannot invent a second image, §4.7 — Naming: declare it, or Compose invents it, The stale image trap

### Community 56 - "Mapper Configuration Check"
Cohesion: 0.50
Nodes (3): Smoke test: force SQLAlchemy to actually wire up the relationships. Importing…, Mappers configure lazily, §12 — Mappers configure lazily: why check.py exists

### Community 57 - "Glossary Chunking"
Cohesion: 0.50
Nodes (4): glossary_entries(), One atom per glossary term. Terms sit at the directive's base indent;…, glossary.rst is ONE directive holding every term — 69236 bytes at 2.0. Unsplit…, test_glossary_splits_per_term()

### Community 58 - "Base Image Choice"
Cohesion: 0.83
Nodes (4): Alpine is a trap for Python, python:3.11-slim base image, §2.1 — FROM, and why it was worth arguing about, Wheels — the concept that decides the base image

### Community 60 - "Refusal Clause Tests"
Cohesion: 0.67
Nodes (3): parametrize, The refusal clause is load-bearing and was measured, not assumed: without it…, test_system_prompt_keeps_its_three_jobs()

## Ambiguous Edges - Review These
- `D13 — Handoff round decision` → `D53 — Handoff round decision`  [AMBIGUOUS]
  logs/HANDOFF.md · relation: conceptually_related_to

## Knowledge Gaps
- **73 isolated node(s):** `generated_by`, `decision`, `doc_root`, `orm`, `core` (+68 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **7 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `D13 — Handoff round decision` and `D53 — Handoff round decision`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `run()` connect `Probe Report Generator` to `Probe Signals and Tests`, `Qdrant Client`, `Prompt Assembly Tests`, `The Ask Entrypoint`, `The 2.0 Migration Chapter`?**
  _High betweenness centrality (0.453) - this node is a cross-community bridge._
- **Why does `classify()` connect `Probe Report Generator` to `Migration Measurement Script`?**
  _High betweenness centrality (0.442) - this node is a cross-community bridge._
- **Why does `02-MIGRATION-2.0.md — the 1.4 → 2.0 upgrade (§16–§22)` connect `The 2.0 Migration Chapter` to `Warning Class Sweep`, `Session Runtime States`, `Test Suite Notes`, `Backref and Result API`, `Seeding the Database`, `SQLAlchemy ORM Concepts`, `Migration Measurement Script`?**
  _High betweenness centrality (0.281) - this node is a cross-community bridge._
- **What connects `generated_by`, `decision`, `doc_root` to the rest of the system?**
  _73 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Breakages and Failures Registry` be split into smaller, more focused modules?**
  _Cohesion score 0.05472837022132797 - nodes in this community are weakly interconnected._
- **Should `Phase 2 Scorer` be split into smaller, more focused modules?**
  _Cohesion score 0.05639097744360902 - nodes in this community are weakly interconnected._