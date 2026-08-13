# Phase 0 — Foundations & Environment (~2 weeks)

The current phase, in detail. See [`README.md`](README.md) for the repo map and
[`ROADMAP.md`](ROADMAP.md) for the phases either side of this one.

## Context

This repository builds a RAG system for SQLAlchemy 1.4 → 2.0 migrations. The full arc is in
`ROADMAP.md` — six phases, ~14–16 weeks. **This plan covers Phase 0 only.**

Phase 0 comes first because the later phases assume two things that have to be true before
they are worth starting:

**Infrastructure you can defend, not just run.** Every phase after this one ships inside a
container, is exercised by CI, and eventually runs a model on a GPU. Copied configuration
gets you a working stack and nothing else — the moment it breaks, or someone asks *why* it is
written that way, you are stuck. So the standard here is not "does it run." It is the drill
list at the end of this file: **why does it work, and what happens when I change this line.**

**A migration you have felt, not read about.** `BREAKAGES.md` is the deliverable, and it is
the seed of the Phase 2 golden dataset. Real questions with verified answers and known source
locations cannot be invented later — they come from breaking the thing on purpose and writing
down what happened. It is also the honest answer to *"why this corpus?"*

The order is deliberate: the SQLAlchemy work needs nothing but Python and runs anywhere, so it
goes first while the machine setup waits on physical access.

### How the work is split

**Claude writes infrastructure and explains each part as it goes** — enough that every line can
be accounted for afterwards. Changed 2026-08-12, on time grounds; before that every
infrastructure file was written from an empty buffer, which is how the `Dockerfile`,
`.dockerignore` and `entrypoint.sh` in this repo came to be.

The gate did not move. **It has always been whether the thing can be explained, not who typed
it** — the drill list below, cold, with no notes. See `CLAUDE.md` for the current rule.

### Hardware decision (settled)

- **Build machine: the Ubuntu lab PC — RTX 3060 (12GB VRAM) + 12GB system RAM.** Chosen
  over the M4 Mac because the AI ecosystem is CUDA-first (fewer fragile platform bugs
  eating the learning budget); because two separate memory pools (12GB VRAM for models +
  12GB RAM for Docker) beat the Mac's single contended 16GB; and because daily
  SSH/Docker/GPU work on a remote Linux box **is itself the practice.**
- **Mac (M4, 16GB): editor and driver's seat only**, via SSH + VS Code Remote.
- **RustDesk/AnyDesk: keep, but scope them.** Fine for initial setup and emergency
  recovery (machine won't boot, network config broken). **Not** for daily coding — typing
  through a laggy video stream is miserable and teaches nothing.

### Operating constraints (these shape the plan)

- **The lab is ~2 days away.** So the phase is **reordered**: the
  SQLAlchemy work — which needs no GPU, no Docker, no Linux, just Python — happens
  **first, on the Mac, starting now.** The machine setup happens on the next lab visit.
  Nothing is wasted and nothing is learned twice.
- **Lab access is roughly once per day.** So the machine setup is done **physically at the
  machine**, in one sitting: SSH, Tailscale, and auto-start-on-boot, verified across a real
  reboot before leaving the room. After that no physical access is needed again.
- **It's a lab machine — it may be rebooted, reimaged, or reassigned by someone else.**
  Therefore: **everything is committed and pushed to GitHub constantly.** A dead PC must
  cost one day, not four months. This is non-negotiable.
- **12GB system RAM is tight.** Consequence: **Langfuse is deferred and run on-demand**,
  not left running. It's really ~5 containers (Postgres + ClickHouse + Redis + MinIO + web)
  and would eat half the system RAM. It was a Phase 6 tool anyway. Qdrant is light and can
  stay up.
- **Blocking check on Day 1: is there `sudo` on that machine?** Installing Docker and
  the NVIDIA Container Toolkit requires it. Without it the hardware plan changes and we
  reassess before writing a line of code.

---

## Part A — On the Mac, starting now (no lab needed)

### Day 0 — The repo and the naming system

**Project name: `sqlalchemy-upgrade-agent`** — one name for the folder, the git repo, and
the GitHub URL. *"Upgrade,"* not *"migration"*: in the SQLAlchemy world "migration" means
**Alembic schema migrations**, and this project is about **code/API** upgrades. The wrong
word costs thirty seconds of interviewer confusion for no reason.

- Create `~/Documents/Projects/sqlalchemy-upgrade-agent`. **No spaces in the path** — spaces
  break Docker mounts, shell scripts, and CI in annoying ways.
- Move `ROADMAP.md` and `CLAUDE.md` in. Abandon the old `Project 1` folder.
- `git init`, create the GitHub remote, push. (Also unblocks Ultraplan, which requires a git
  repo.)
- Write `PHASE-0.md` (this plan) into the repo.

**Naming conventions — decided once, applied everywhere:**

| Thing | Convention | Example |
|---|---|---|
| Folder / repo / GitHub | `kebab-case`, all identical | `sqlalchemy-upgrade-agent` |
| Python package + modules | `snake_case` (hyphens are illegal in Python imports) | `src/sqlalchemy_upgrade_agent/retrieval/` |
| Root-level docs | `SCREAMING_CASE.md` — signals "read me first" | `ROADMAP.md`, `BREAKAGES.md` |
| Branches | `phase-N/short-topic` | `phase-0/docker-basics` |
| Commits | Conventional Commits | `feat: add hybrid retrieval`, `docs: log 1.4 breakages` |

**Structure — created lazily, not all at once (YAGNI).** Only what each phase needs:

```
sqlalchemy-upgrade-agent/
├── README.md              # product framing first — written properly in Phase 6
├── ROADMAP.md             # the 4-month arc
├── PHASE-0.md             # this plan
├── BREAKAGES.md           # Part A deliverable → seeds the Phase 2 golden dataset
├── pyproject.toml         # uv-managed
├── experiments/
│   └── sqlalchemy_1_4_vs_2_0/    # Part A practice code (SQLite, no infra)
├── src/sqlalchemy_upgrade_agent/ # grows from Phase 1 on
├── eval/                         # Phase 2 on — the crown jewel
├── tests/
└── .github/workflows/            # Phase 0 Part C
```

**Done when:** the repo exists on GitHub with `ROADMAP.md` and `PHASE-0.md` pushed.

### Days 1–2 — SQLAlchemy 1.4 → 2.0, felt personally · **HIGHEST VALUE IN THE PHASE**

Needs nothing but Python. **SQLite** as the database, so there is zero infrastructure to
stand up. Databases first, infrastructure second — one new variable at a time.

- Set up `uv`, a virtual environment, `pyproject.toml`, `.gitignore`.
  - **Likely first obstacle:** the Mac has Python 3.13, and SQLAlchemy **1.4** may not
    install on it. Fix: pin an older Python (3.11/3.12) with `uv python install`. Expect
    this; it's not a setback.
- Write **real 1.4-style code** — `session.query(User).filter(...)`, `Query.get()`,
  implicit autocommit, lazy-loading patterns. Run it under 1.4 and confirm it works.
- **Upgrade to 2.0 and watch it break.** Then fix each break using the official migration
  guide.

**Deliverable: `BREAKAGES.md`** — every failure hit in person: the 1.4 code, the exact
error, the 2.0 fix, and the doc section that explains it. **Target: ≥10 distinct
breakages.**

> `BREAKAGES.md` is not busywork. It is **the seed of the Phase 2 golden dataset** — real
> questions with verified answers and known source locations, which is exactly the shape a
> golden record needs. It is also the answer to *"why this corpus?"*

**Done when:** ≥10 documented breakages caused, hit, and fixed in person — committed
and pushed.

---

## Part B — At the lab, next visit (in person, one sitting)

### Day 3 — The machine · **DO THIS PHYSICALLY AT THE LAB**

The one day that must happen in person. Everything after it is remote.

- **First, the blocking check:** confirm `sudo` works. No sudo → stop, tell Claude, we
  reassess the hardware plan before writing another line.
- Install **Tailscale** on both machines (free; works across networks, through NAT, no port
  forwarding, survives the lab's IP changing).
- **SSH key auth** from Mac → PC. No passwords.
- **Make it survive a reboot:** `sshd` and Tailscale enabled as systemd services, so a lab
  power-cycle doesn't lock you out until the next visit. Set the BIOS to power on after
  power loss if possible.
- **VS Code Remote-SSH** — open a folder on the PC, edit as if local.
- Verify GPU: `nvidia-smi` reports the 3060. Install the NVIDIA driver if not.
- `git clone` the repo onto the PC. **From here, the PC is the source of truth.**

**Done when:** you can walk away from the lab and, from the Mac: `ssh pc` connects with no
password, VS Code edits files on the PC, and `nvidia-smi` reports the 3060 — **after a
reboot.** Test the reboot *before leaving the room.*

---

## Part C — Remote, on the PC

### Days 4–5 — Docker, from a blank file

A `Dockerfile` for a trivial Python app, written from an empty file. Then deliberately broken
and fixed. The point is not a working container — it's understanding.

Must be able to reason about, not recite:
- Image layers and **build cache invalidation** — why reordering two lines changes build time
- `COPY` vs `ADD`, and why `COPY requirements.txt` before `COPY .` is not a style choice
- `.dockerignore` and why the build context matters
- Why a container can't reach the host / the network
- `CMD` vs `ENTRYPOINT`

**Done when:** a Dockerfile is written from an empty file, unaided, and a build
failure Claude injects — explaining *why* it failed, not just fixing it.

### Day 6 — Docker Compose, two services talking

A `docker-compose.yml` with a Python app + Postgres that actually communicate.
(Postgres deliberately — its behaviour is not what is under test, so the *new* thing here
is Docker networking, not the database.)

Concepts: service networking and DNS-by-service-name, volumes and persistence, env vars
and secrets, port mapping vs internal ports, `depends_on` and why it does **not** mean
"wait until ready."

**Done when:** the app queries Postgres across the compose network, and you can explain how
the app resolved the database's hostname.

### Day 7 — GPU inside a container

Install the **NVIDIA Container Toolkit** and run a container that sees the GPU. This is the
real-world pattern for every GPU workload and it's directly reusable in Phase 1.

**Done when:** `docker run --gpus all ...` reports the 3060 from inside a container.

### Days 8–9 — CI, from a blank file

A GitHub Actions workflow that runs `pytest` and **blocks a merge when tests fail**. Then turns on branch protection so the block is real, not advisory.

Concepts: triggers (`on:`), jobs vs steps, runners, caching dependencies, secrets, and
what "required status check" actually enforces.

**Done when:** a PR containing a deliberately failing test is opened, and **GitHub refuses
to let it merge.** Every line of the YAML can be explained.

> This exact pipeline becomes the skeleton of the Phase 6 eval gate, where a PR that
> *degrades retrieval quality* gets auto-blocked. Same machinery, higher stakes.

### Day 10 — Ollama and the first local model

Pull a local model (Qwen2.5-Coder-7B class) and confirm it runs **on the GPU, not the
CPU**. Measure tokens/sec. Confirm there's VRAM headroom left for the embedding model and
reranker that arrive in Phase 1.

**Done when:** the local model answers a prompt on the 3060, its tokens/sec can be stated,
and the remaining VRAM is known.

---

## Files this phase produces

| File | Part | Purpose |
|---|---|---|
| `BREAKAGES.md` | A | Real migration failures → **seeds the Phase 2 golden dataset** |
| `experiments/sqlalchemy_1_4_vs_2_0/` | A | 1.4 vs 2.0 comparison code, SQLite by default — no infra needed |
| `Dockerfile` + `.dockerignore` + `entrypoint.sh` | C | Container for the app; foundation for every later phase |
| `docker-compose.yml` | C | Multi-service stack; Qdrant plugs in at Phase 1 |
| `tests/` | C | What CI has to run — the gate below needs something to fail |
| `.github/workflows/ci.yml` | C | Test gate; becomes the **eval gate** in Phase 6 |

### Where it actually stands

Counted rather than remembered, so this section cannot quietly go stale:

```
# runnable: uv run python -c "
#   import pathlib, re
#   def n(p):
#       q = pathlib.Path(p)
#       return len(list(q.glob('*.py'))) if q.is_dir() else 0
#   b = pathlib.Path('BREAKAGES.md')
#   rows = [
#    ('BREAKAGES.md', f\"{len(re.findall(r'^### ', b.read_text(), re.M))} entries (target 10)\"),
#    ('experiments/sqlalchemy_1_4_vs_2_0/', f'{n(\"experiments/sqlalchemy_1_4_vs_2_0\")} modules'),
#    ('Dockerfile', 'yes' if pathlib.Path('Dockerfile').exists() else 'MISSING'),
#    ('.dockerignore', 'yes' if pathlib.Path('.dockerignore').exists() else 'MISSING'),
#    ('entrypoint.sh', 'yes' if pathlib.Path('entrypoint.sh').exists() else 'MISSING'),
#    ('docker-compose.yml', 'yes' if pathlib.Path('docker-compose.yml').exists() else 'MISSING'),
#    ('tests/', f'{n(\"tests\")} files' if pathlib.Path('tests').is_dir() else 'NOT BUILT'),
#    ('.github/workflows/', f'{len(list(pathlib.Path(\".github/workflows\").glob(\"*.yml\")))} workflows'
#        if pathlib.Path('.github/workflows').is_dir() else 'NOT BUILT'),
#   ]
#   w = max(len(a) for a,_ in rows)
#   for a,c in rows: print(f'{a:<{w}}  {c}')"
BREAKAGES.md                        23 entries (target 10)
experiments/sqlalchemy_1_4_vs_2_0/  12 modules
Dockerfile                          yes
.dockerignore                       yes
entrypoint.sh                       yes
docker-compose.yml                  yes
tests/                              NOT BUILT
.github/workflows/                  NOT BUILT
```

**The two `NOT BUILT` lines are the remaining work on this machine**, and they are in order:
CI's gate is *"a PR with a deliberately failing test that GitHub refuses to merge"*, which
needs a test to exist before a workflow can run one.

The rest of Part C — Day 7 (GPU) and Day 10 (Ollama) — is blocked on the lab machine, not on
anything here.



---

## Verification — how we know Phase 0 actually landed

**Not "does it run." "Can it be defended."** A container that works because it was copied
teaches nothing, and the gap only shows up under questioning.

These are asked cold, with no notes. Failing them means the phase isn't done:

1. *"I moved `COPY . .` above `COPY requirements.txt`. Your build got slow. Why?"*
2. *"Your container can't reach Postgres. Walk me through how you'd diagnose it."*
3. *"What's the difference between `CMD` and `ENTRYPOINT`, and when does it bite you?"*
4. *"Your CI passes locally but fails in Actions. What are the three usual causes?"*
5. *"`depends_on` says Postgres starts first, but your app still crashes on startup. Why?"*
6. *"Name three things that broke going 1.4 → 2.0 and explain why the library changed them."*
7. *"How do you know your model is on the GPU and not silently running on CPU?"*

**Hard gate:** a Dockerfile and a CI workflow written from a blank file, unaided,
and debug a failure Claude injects into each.

## Risks

| Risk | Mitigation |
|---|---|
| No `sudo` on the lab machine | Checked Day 1 **before** anything else. If missing, we replan the hardware. |
| Lab PC rebooted / reimaged / reassigned by someone else | Everything pushed to GitHub continuously. A dead PC costs one day, not the project. |
| Locked out remotely, can only visit once/day | `sshd` + Tailscale as systemd services, tested across a real reboot **before leaving the lab on Day 1.** AnyDesk kept as GUI fallback. |
| 12GB system RAM exhausted | Langfuse deferred to Phase 6 and run on-demand only. Qdrant is light and stays up. Ubuntu desktop kept minimal. |
| Split-brain between Mac and PC | The **PC is the single source of truth.** The Mac is an editor, not a second workspace. |

---

## What comes next (not this plan)

**Phase 1 — a deliberately dumb RAG.** Meaning-search only. No hybrid search, no
reranking, no agent. Build the naive version and *watch it fail*, so that every improvement
in Phase 3 comes with a before/after number earned in person. Details in `ROADMAP.md`.
