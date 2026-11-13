"""
The retrieval system: documentation in, answer with cited sources out.

Separate from `experiments/sqlalchemy_1_4_vs_2_0/` on purpose: that package is
an instrument pointed at SQLAlchemy, and it is pinned to 1.4.52 because the
thing it measures is a 1.4 app. This package is pointed at *text*, imports no
SQLAlchemy at all, and would work the same if the corpus were something else.

Files under `deliverables/` and comments in this package label a result with
the phase and step it was produced in ("Phase 6, Step 3b"). That numbering is
the order the work was done in, and this is the key to it:

    Phase 1   the naive pipeline
              1 corpus.py   2 chunk.py   3a embed.py   3b index.py
              4 ask.py      5 probe.py (break it on purpose)
    Phase 2   a hand-verified golden set (golden.py) and its scorer
              (4 score.py)
    Phase 3   retrieval improvements, each measured against Phase 2's
              baseline: dedup.py, bm25.py + hybrid.py, rerank.py
    Phase 4   grading the answer rather than the search: judge.py,
              faithful.py, compare_prompts.py
              5 the judge's agreement with a human (faithful.py --agreement)
    Phase 5   an agent with tools
              0 toolcall.py   1 tools.py   2 agent.py
              3 the golden set run through the agent
    Phase 6   production
              1 framing.py    2 gate.py    3a route.py
              3b-3d escalate.py (3b refusals with the page present, 3c the
                    full cascade priced, 3d judged against verified pages)
              3e tools/check_escalated.py
              4 demo.py and space/ (4c tools/check_page.py, 4d the hosted
                model on all 100 questions, 4e one judge on both models,
                4f tools/check_nemotron_all.py, 4g the judge given headings)
    Phase 7   prompt injection
              0 inject.py   1 fence.py   2 the hosted model attacked
              2b fencing on the hosted model

Build the index and answer a question:

    corpus.py      fetch the documentation source for both pinned releases;
                   writes corpus/MANIFEST.json, which records where every file
                   came from and which version it documents
    chunk.py       cut 270 files into 3284 chunks. `--audit` counts the ones
                   that do not stand alone
    embed.py       3284 x 1024 float32 vectors, BGE-M3, saved to a file
    index.py       load Qdrant (or search in memory); `retrieve()` is the one
                   entry point every other module searches through
    dedup.py       collapse the 1.4 and 2.0 copies of the same passage
    bm25.py        keyword search, the channel dense retrieval lacks
    hybrid.py      rank fusion over the dense and keyword channels
    rerank.py      cross-encoder promotion into the fifth seat. Not a full
                   re-sort: re-sorting the top 20 broke ten questions
    textnorm.py    REJECTED. Stripping Sphinx roles before embedding cost six
                   points of recall. Kept so nobody re-derives a worse index
    ask.py         question in, answer plus the passages it came from. Holds
                   the prompt, DEFAULT_K, and `refused()`, the single refusal
                   detector

Measure retrieval:

    golden.py      the bench for building the golden set by hand. It cannot
                   mark anything verified, and a test asserts that
    score.py       recall@k, MRR, a paired `--baseline` comparison with an
                   exact McNemar p-value, `--refusals` and `--absents`
    gate.py        the CI quality gate: fails a pull request that pushes any
                   answer page out of the top five
    probe.py       19 questions chosen to break the pipeline; writes
                   deliverables/FAILURES.md
    compare_embedders.py   two embedding models on the same questions
    bench.py       how long each retrieval stage takes, p50 and p95 over the
                   golden questions; checks it timed the path that ships

Measure answers:

    judge.py       citation integrity and ungrounded API calls, computed with
                   no model; `--report` prints every report card
    faithful.py    is an answer's prose supported by the pages it was given?
                   Needs a judge model; runs locally
    compare_prompts.py     several prompt wordings over the golden set in one
                           run, scored on refusals and citations
    framing.py     the same prompt in two conversation shapes

Agent:

    toolcall.py    can the local model emit a valid tool call, and on which
                   channel does it arrive
    tools.py       the three tools: search the docs, check whether an API
                   exists on real SQLAlchemy 2.0, read a passage
    agent.py       the loop, its step budget and its failure paths

Routing and cost:

    route.py       which questions are worth sending to a stronger model
    escalate.py    send them, judge the answers, price the result
    usage.py       a ledger of hosted-model tokens

Security:

    inject.py      prompt-injection attempts against the pipeline, counted
    fence.py       marking untrusted text in the prompt, as measured arms

Serving:

    demo.py        the hosted page's logic: rate limit, model fallback,
                   rendering
    server.py      the web server around it: status codes, health checks,
                   one JSON log line per question
    mcp_server.py  the three agent tools over the Model Context Protocol
    cli.py         the `sqla-upgrade` command: ask, serve, mcp

Each module's docstring holds its own reasoning.
"""
