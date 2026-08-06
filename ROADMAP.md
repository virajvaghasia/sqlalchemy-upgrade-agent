# Roadmap — the six-phase arc

The long view for [`sqlalchemy-upgrade-agent`](README.md): what gets built, in what order,
and why each phase exists. Start at [`README.md`](README.md); the current phase is detailed
in [`PHASE-0.md`](PHASE-0.md).

---

## 1. What you're building, in one paragraph

An **open-book AI assistant** that helps developers upgrade Python code from
SQLAlchemy 1.4 to SQLAlchemy 2.0.

SQLAlchemy is a widely-used Python library for working with databases. Version 2.0
changed a lot of things that worked in 1.4, so people with older code have to rewrite
parts of it. That's tedious and error-prone.

Your system takes a question like *"how do I rewrite this 1.4 query in 2.0 style?"*,
**goes and finds the exact relevant pages** from the real SQLAlchemy documentation,
migration guide, source code, and GitHub issues — and hands those pages to an AI so it
answers from real sources instead of from memory.

That "find the right pages first, then answer" pattern is called **RAG**
(Retrieval-Augmented Generation). It is the heart of this project. Everything else is
machinery to do it *well*, and to *prove* it's done well.

---

## 2. Why you're building it

It's a **portfolio project to get hired.** Targets: Nvidia, Meta, Google, Apple,
Anthropic — plus it works for startups.

It's specifically designed to survive an interviewer poking at it for 30 minutes. Most
portfolio AI projects are "I called an API and it printed something." This one is built
to answer *"how do you know it works?"* with real numbers.

**The two things that actually get you hired** (everything else is supporting cast):

1. **Retrieval quality** — the system finds the *right* pages, and you can prove it.
2. **The evaluation harness** — you measure quality automatically, with real metrics,
   and you can defend those metrics.

These two are the "crown jewels." Protect them. If you run out of time, cut anything
else before you cut these.

---

## 3. Your actual starting point — read this before anything else

**The honest diagnosis:** 2 years of real production experience, but heavily AI-assisted.
You *recognize* the tools without being able to *reason* about them. Not a beginner. Not
the "production-fluent" engineer the original brief assumed. Something in between, and the
plan is built for that specific person.

**Genuinely solid (real skill, keep leaning on it):**
- **Databases and SQL** — schema design, non-trivial queries, indexes. This is real.
- Python (basic scripts), Git, comfortable in a terminal
- SQLAlchemy — rusty, but you've used it and the concepts are recoverable

**Hollow — used, never internalized (this is the gap):**
- **Docker** — can't write a Dockerfile from scratch and debug a failing build
- **CI/CD** — can't build a pipeline from scratch and explain each step
- Cloud, deployment, system design at any depth

**Completely new (and that's fine — nobody expects otherwise):**
- Everything AI/LLM: embeddings, retrieval, evaluation, agents

**Time available:** ~40 hours/week.

### The thing that matters more than this project

Your résumé claims *"strong in deployment, CI/CD, containers, cloud, system design."*
You currently cannot defend that claim under questioning.

**A FAANG systems interview will find this in fifteen minutes, and no portfolio project
survives that discovery.** The gap between what a résumé claims and what a candidate can
reason about is precisely what hiring loops are built to detect.

**So Phase 0 is not beginner onboarding. It is career remediation, and it's the
highest-stakes phase in this plan.** You need Docker and CI whether or not this project
exists.

The upside: this project contains *every single item* on that résumé line — containers,
CI/CD, deployment, cloud, observability, system design. **Build it honestly and you
retroactively earn the résumé you already have.**

### The collaboration rule (non-negotiable)

**On infrastructure — Docker, CI, deployment, system design — YOU write the code. Claude
does not.** Claude explains, reviews, and drills. If Claude writes your Dockerfile, you get
a working container and learn nothing, and the gap stays open — which is exactly how you
got here.

**On the genuinely new AI material — embeddings, retrieval, eval — Claude is hands-on.**
You have no prior claim to that knowledge and no interviewer expects you to arrive with it.

The asymmetry is deliberate: **most help where you're honestly new, least help where you're
supposed to already know.**

### Job-hunting timing

You are job-hunting *now*, and the build is ~4 months. Applying to top-tier companies today
means burning your best shots — referrals, recruiter contacts, the one realistic
application per company — on loops you will fail.

**Keep applying, but treat the next ~3 months of interviews as free practice, not as your
real shot.** Get drilled, find out exactly where you break, come back and fix it. The real
applications start around Phase 4, when you can survive the drill.

---

## 4. Locked decisions (don't reopen these)

| Decision | Choice | Why |
|---|---|---|
| Domain | Codebase / API-migration assistant | Plays to real engineering, universally legible to every target company |
| Corpus | SQLAlchemy 1.4 → 2.0 | Rich mix of code + prose + issues; stable target that won't move mid-build; famous migration nobody will question |
| Budget | **Zero paid API calls** | RTX 3060 (12GB) for local models + free tiers only |
| Language | Python | Your language, and the whole AI stack is Python anyway |

**On the corpus and your rusty SQLAlchemy:** this is fine, and here's your honest answer
when asked. You will spend months living inside this specific migration. By the end you
will know the 1.4→2.0 break *better than most people who use SQLAlchemy daily*. Depth in
one migration beats vague familiarity with the whole library. Phase 0 gets your hands
back on it.

---

## 5. The core idea, explained properly

### How a question actually flows through the system

A developer asks:

> *"In SQLAlchemy 2.0, how do I write what used to be
> `session.query(User).filter(User.name == 'bob')` in 1.4?"*

**Step 1 — The question becomes a "meaning fingerprint."**
Computers can't search by meaning using raw words. So a small AI model converts the
question into a long list of numbers that captures its *meaning*. That list is called an
**embedding**. The model that makes it is an **embedding model**.

The useful property: **things that mean similar things get similar numbers**, even with
zero shared words. "close a session" and "terminate a connection" land near each other.
That's what makes search-by-meaning possible.

**Step 2 — Search the library of chunks.**
Ahead of time, you chopped all the SQLAlchemy docs and code into thousands of small
pieces (**chunks**) — a paragraph here, a function there — and stored each chunk's
fingerprint in a **vector database** (Qdrant). A vector database is built to answer one
question extremely fast: *"given this fingerprint, which stored chunks are closest?"*

**Step 3 — Actually search two ways at once.**
- **Meaning search** (using fingerprints): understands intent, but is fuzzy about exact
  spellings. It might blur `filter` and `filter_by`.
- **Keyword search** (plain word matching, like a smarter Ctrl+F): nails exact strings
  like `session.query` or `2.0`, but is stupid about meaning.

Running both and combining them is **hybrid search**. It matters *specifically* for this
project because code is full of exact symbol names AND fuzzy concepts. Neither search
alone is enough.

The algorithm that merges the two ranked lists is **RRF** (Reciprocal Rank Fusion) —
"anything ranked high on either list bubbles to the top." No tuning knobs.

**Step 4 — Refine down to the best few.**
Hybrid search hands you ~50 plausible chunks. A slower, smarter model called a
**reranker** carefully re-scores those 50 and keeps only the best ~5.

Think: grab an armful of maybe-relevant books cheaply, *then* carefully pick the 5 that
truly matter. Cheap-and-wide first, expensive-and-precise second.

**Step 5 — Hand the 5 chunks to the AI.**
You paste them into a prompt: *"Here are 5 relevant excerpts. Using only these, answer
the question, and cite which excerpt each part comes from."*

**Step 6 — The AI writes a sourced answer.**
Grounded in real documentation, with citations. Not from memory.

### The one line to remember

```
Question → fingerprint → [meaning search + keyword search]
        → merge → rerank to best 5 → hand to AI → sourced answer
```

**Steps 1–4 are all just "find the right 5 pages."** That's where the real engineering
is, and it's why the search is the craft. Step 5–6 (the AI writing) is the easy part —
the answer is only ever as good as the pages you fed it.

---

## 6. The plan

Six phases. Each one **ends with something that works.** You are never half-built.

### Phase 0 — Remediation (~2 weeks) · **HIGHEST STAKES**

**This is not "beginner setup." This is closing the gap between your résumé and reality.**
You would need this even if the project didn't exist.

**You write all of it. Claude explains and drills, but does not produce the code.**

- **Docker, properly.** Not copy-pasting a Dockerfile — *writing* one, watching the build
  fail, and understanding why. Layers. Caching. Why the container can't reach the network.
  Then `docker compose` with two services talking to each other.
- **CI, properly.** A GitHub Actions workflow you wrote, that runs a test and blocks a
  merge when it fails. You must be able to explain every line.
- Python project hygiene: virtual environments, dependencies, project layout, reading a
  traceback.
- **SQLAlchemy hands-on refresher.** Write real 1.4 code, run it, then run it under 2.0 and
  *watch it break with your own eyes.* Your SQL/database knowledge is real — this is where
  you reconnect it to the corpus.

That last one is not busywork. You cannot write good test questions about a migration you
have never personally felt, and it is your interview defense for the corpus choice.

**Done when:** you can write a Dockerfile from a blank file, debug a failing build without
help, explain a CI workflow line by line, and you have personally written a query that
works in 1.4 and breaks in 2.0.

**The bar is "can you defend it," not "does it run."** A container that works because you
copied it teaches you nothing and leaves the résumé gap wide open.

---

### Phase 1 — A deliberately dumb RAG that works end to end (~2–3 weeks)

Build the **simplest possible version**. Meaning-search only. **No** hybrid search,
**no** reranking, **no** agent. Resist every urge to make it good.

- Download the SQLAlchemy corpus (docs, migration guide, source, issues)
- Chop it into chunks
- Embed them, store them in Qdrant
- Search, take the top chunks, feed them to a local AI model (via **Ollama**)
- Print an answer

**New things you'll learn here:** chunking, embeddings, vector databases, Ollama,
prompting.

**Done when:** you type a question in your terminal and get back an answer with sources.
Ugly output is completely fine.

> #### Why "dumb first" — read this twice
>
> Hybrid search and reranking are **fixes for problems.** If you have never watched the
> simple version fail, you cannot explain why the fix exists — and *that is exactly what
> an interviewer will drill you on.*
>
> Build the naive version. Watch it confidently retrieve the wrong chunk. *Then* fix it,
> and measure the fix. Every improvement in Phase 3 becomes a number you personally
> earned rather than a best practice you copied.
>
> This is the single most important change from the original plan.

---

### Phase 2 — Measure it (~2 weeks) · **CROWN JEWEL #1**

Turn "it seems okay" into a number.

- **Golden dataset**: 30–50 questions with known-correct answers, each recording *which
  chunks should have been retrieved* to answer it. These are test fixtures for your AI.
  Include a few **unanswerable** questions, where the correct behavior is for the system
  to say *"I don't know"* instead of inventing something.

> #### You harvest these — you don't invent them
>
> You are **not** expected to pull questions out of your head. You collect them from
> reality:
>
> - Real GitHub issues where people hit the migration and got stuck
> - Real Stack Overflow questions about 1.4 → 2.0
> - The migration guide itself — it enumerates exactly what broke
> - Your own Phase 0 work, where you wrote 1.4 code and watched it break
>
> Real people already asked these questions. Your job is **curation and verification**:
> take a real question, find the genuinely correct answer in the docs, record which chunk
> holds it. ~30–50 items at ~15 min each ≈ 10–15 hours.
>
> **AI can help you draft, reformat, and dig up sources. AI cannot do the verifying.**
> You must be the one who opens the doc, confirms the answer is actually right, and
> records the source.
>
> **Why it can't be auto-generated:** if an AI writes the questions *from your chunks*, it
> writes them in the chunks' own words — so your search finds them trivially, your score
> comes back at 0.95, and it **measures nothing.** You graded your own homework with your
> own answer key. Meanwhile a real developer's messy question ("why does my session.query
> thing not work anymore??") would break the system, and your benchmark would never have
> warned you.
>
> This golden set is the **ruler you measure everything else with.** Every later decision —
> is hybrid search worth it, did the reranker help, should this PR merge — is settled by
> that ruler. A bent ruler makes every downstream number fiction.
>
> It's also the one part of the project that forces you to actually understand the domain —
> which is what makes every *other* part defensible under questioning.
- **Retrieval metrics** (deterministic, free, no AI needed):
  - **recall@k** — "for what fraction of questions was the right chunk anywhere in the
    top k results?" Plainly: *did we even fetch the right thing?*
  - **MRR** — "how high up was the first correct chunk, on average?" Rewards putting the
    right answer at position 1 instead of position 8.

**Done when:** one command runs all your questions through the pipeline and prints a
score. That score will probably be bad. **That's the point** — now you have a baseline
to beat.

---

### Phase 3 — Make it good, and prove every improvement (~3 weeks)

Now you fix it — **one change at a time, measuring after each.**

1. Add keyword search (BM25) + hybrid + RRF → **re-measure**
2. Add the reranker → **re-measure**
3. Improve chunking (code split by function, prose split by paragraph) → **re-measure**

Each step produces a before/after number. Together they become **the metrics table**, the
single highest-value object in the whole repo:

| Setup | recall@k | MRR |
|---|---|---|
| Meaning-search only (Phase 1 baseline) | ? | ? |
| \+ hybrid search | ? | ? |
| \+ reranker | ? | ? |
| \+ better chunking | ? | ? |

This table is your proof that every architectural choice was **earned, not cargo-culted**.
It only exists because you built the dumb version first.

---

### Phase 4 — Judge the *answers*, not just the search (~2 weeks) · **CROWN JEWEL #2**

Phase 2 measured whether you fetched the right pages. Now: is the final answer any good?

- **LLM-as-judge** — you use a *strong* AI to grade your system's answers. (Free tier of
  Google's Gemini. Your local model is too weak to be a trustworthy judge — it's fine for
  quick iteration, but the numbers that go in your README come from the strong judge.)
- **Faithfulness** — does the answer actually stick to the retrieved sources, or did it
  make things up? This is the anti-hallucination metric.
- **Citation accuracy** — do the sources it cites actually exist and actually support the
  claim?

**Judge discipline (this is what separates you from a bootcamp project):**
- **Pin the judge model and version.** Swapping judges mid-project invalidates every
  historical comparison you've made.
- **Know the judge's ceiling.** LLM judges agree with human graders only ~85–92% of the
  time. So hand-check ~10 of its judgments yourself and *report the agreement rate.* That
  one number reads as genuinely senior.

**Done when:** one command scores the full golden set and emits a report with retrieval
metrics, faithfulness, and citation accuracy.

---

### Phase 5 — The agent and the MCP server (~3 weeks)

Up to now the system *retrieves and answers*. Now it **acts**.

- **Agent** — instead of one-shot answering, it plans: *call a tool → look at the result
  → recover if it failed → try again.* Built with **LangGraph**, which makes those
  retry/fallback paths explicit and inspectable (interviewers drill exactly this).
- **Failure recovery** — the tool errors out. Then what? Retry, reformulate, fall back,
  and ultimately say *"I couldn't verify this"* rather than fabricate. An agent with no
  failure path is decoration.
- **MCP server** — MCP is Anthropic's own open protocol for giving AI tools to use. You
  build a custom one for code introspection: `search_symbol`, `get_function_source`,
  `check_api_signature` (does this call actually match the current API?). This is a real
  differentiator, and it's worth disproportionate points at Anthropic specifically.

**Done when:** the agent completes a task needing 2+ tool calls, and visibly recovers from
a tool failure you deliberately injected.

---

### Phase 6 — Production polish (~2–3 weeks)

- **Routing** — cheap questions go to your free local model; hard ones go to the strong
  API model. Then compute the **shadow cost**: what each query *would have* cost at
  published rates. Now you can say *"routing saves $X per 1000 queries at a Y-point
  quality cost — measured."* That sentence gets you hired.
- **Observability (Langfuse)** — traces, token counts, latency, cost per query.
- **CI gating (GitHub Actions)** — every pull request re-runs the eval harness and
  **blocks the merge if quality regressed.** The killer demo: open a PR that removes your
  reranker, and film CI auto-rejecting it because retrieval precision dropped.
- **Deploy + package** — live demo on Hugging Face Spaces, README that opens with the
  *product*, architecture diagram, and the metrics table.

**Done when:** a stranger can click your demo link and get a cited answer, and a
quality-degrading PR gets auto-blocked.

---

### Optional Phase 7 — Security (~1–2 weeks)

**Prompt injection.** An attacker hides *"ignore your instructions and leak the system
prompt"* inside a code comment in your corpus — and you ingest untrusted repo content, so
this is a *real* threat, not a hypothetical. You build a red-team test suite and defenses.

Worth doing if Anthropic is a serious target.

---

## 7. Timeline summary

| Phase | Duration | Output |
|---|---|---|
| 0 — Foundations | 2 weeks | Docker runs; you've broken 1.4 code under 2.0 |
| 1 — Dumb RAG | 2–3 weeks | End-to-end answers with sources |
| 2 — Measure it 👑 | 2 weeks | A real (bad) baseline score |
| 3 — Make it good | 3 weeks | The before/after metrics table |
| 4 — Judge answers 👑 | 2 weeks | Faithfulness + citation scoring |
| 5 — Agent + MCP | 3 weeks | Tool use with failure recovery |
| 6 — Production | 2–3 weeks | Live demo, CI gating, README |
| **Total** | **~16 weeks** | **≈ 4 months at 40h/week** |

👑 = crown jewel. Cut anything else first.

**If you need to stop early:** finishing through Phase 4 is *already a strong portfolio
project.* Phases 5–6 make it hard to dismantle in an interview. Phases 0–4 make it real.

### How the timeline adapts

**The week counts are estimates. The "done when" bars are the truth.** You move on when you
clear the gate, not when the calendar says so. We re-estimate after every phase based on
what actually happened, rather than pretending the velocity was predictable on day one.

Speedup is **not uniform**, so expect this shape:

- **Compresses a lot if you learn fast** — Phases 0, 1, and 6. Mechanical work. Once it
  clicks, it clicks.
- **Barely compresses at all** — Phases 2 and 4. Hand-writing 30–50 good golden questions
  *is* the thinking; you cannot speed-read your way through building a benchmark. These
  are the crown jewels. Don't try to rush them.

**On working more than 40h/week:** extra hours help *building* far more than *learning*.
Past ~40h of genuinely new concepts, comprehension per hour collapses and you start
producing code you can't defend — the worst possible outcome for a project whose entire
value is being able to defend it. Spend surplus hours going **deeper** (bigger golden set,
the security phase, better analysis) rather than **further ahead**.

**The failure mode to watch for:** feeling fast and skipping the dumb-first ordering
("I get it, let's just build hybrid search now"). That saves two weeks and costs you the
metrics table — the most valuable object in the repo. **Speed comes from clearing gates
faster, never from skipping them.**

---

## 8. The stack (don't memorize — you'll meet each one when you need it)

| Tool | What it does | Phase |
|---|---|---|
| **Docker** | Packages software so it runs anywhere | 0 |
| **Ollama** | Runs a free AI model on your own GPU | 1 |
| **Qdrant** | Vector database — search text by meaning | 1 |
| **BGE-M3** | The embedding model (makes the fingerprints) | 1 |
| **bge-reranker** | The reranker (precision pass) | 3 |
| **Gemini free tier** | Strong AI, used as the judge | 4 |
| **RAGAS / DeepEval** | Ready-made RAG evaluation metrics | 4 |
| **LangGraph** | Agent framework (plan → act → recover) | 5 |
| **FastMCP** | Builds your custom MCP tool server | 5 |
| **Langfuse** | Observability — traces, cost, latency | 6 |
| **GitHub Actions** | CI — auto-runs your evals on every PR | 6 |
| **HF Spaces** | Free hosting for the live demo | 6 |

---

## 9. Glossary — every term, anchored

- **RAG (Retrieval-Augmented Generation)** — open-book exam for an AI. Fetch the relevant
  pages first, then answer from them instead of from memory.
- **Chunk** — a small piece of a document (a paragraph, a function). You search chunks,
  not whole files, because you want the specific relevant passage.
- **Embedding** — a list of numbers representing a text's *meaning*. The opposite of a
  hash: a hash scatters similar inputs to unrelated outputs; an embedding pulls similar
  meanings *together*.
- **Embedding model** — the AI that produces embeddings (yours: BGE-M3).
- **Vector database** — a database optimized for *"find the stored items whose fingerprints
  are closest to this one."* (Yours: Qdrant.)
- **Dense retrieval** — search by meaning (using embeddings). Good at paraphrases, fuzzy on
  exact strings.
- **Sparse retrieval / BM25** — plain keyword search. Nails exact symbol names and version
  numbers, dumb about meaning.
- **Hybrid search** — run dense + sparse together, merge the results. Each covers the
  other's blind spot.
- **RRF (Reciprocal Rank Fusion)** — the merge algorithm. Anything ranking high on either
  list bubbles up.
- **Reranker / cross-encoder** — a slow, accurate model that re-scores your ~50 candidates
  down to the best ~5. Too expensive to run over the whole corpus, which is exactly why
  it runs *second*.
- **Golden dataset** — test fixtures for your AI: questions + correct answers + which
  chunks should have been retrieved.
- **recall@k** — did the right chunk appear anywhere in the top k? *Did we fetch the right
  thing at all?*
- **MRR** — how near the top was the first correct chunk, on average?
- **LLM-as-judge** — using a strong AI to grade your system's output at scale.
- **Faithfulness** — does the answer stick to the sources, or did it hallucinate?
- **Hallucination** — the AI confidently making something up.
- **Agent** — an AI that plans and *uses tools* in a loop, rather than answering in one
  shot.
- **Tool use** — the AI calling a real function (search code, check an API signature) and
  reading the result.
- **MCP (Model Context Protocol)** — Anthropic's open standard for exposing tools to an
  AI. You'll build a custom MCP server.
- **Routing** — sending easy questions to the cheap model and hard ones to the expensive
  model.
- **Shadow cost** — what a query *would have* cost at real prices, even though you paid $0.
  It's how you get real cost numbers on a zero budget.
- **Observability** — recording what happened inside each request (time, tokens, cost) so
  you can debug and report it.
- **CI gating** — automatically running your evals on every code change and blocking it if
  quality drops.
- **Prompt injection** — an attack where malicious instructions hide inside content your
  system ingests.

---

## 10. Where you are right now

**Phase 0, not started.** Nothing has been built yet.

**Next step:** Phase 0, Docker + SQLAlchemy hands-on. Say the word and we start.
