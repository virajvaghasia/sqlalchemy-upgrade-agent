# Phase 0 — Foundations & Environment (~2 weeks)

**Complete**, except its Day 3 tunnel. See [`../README.md`](../README.md) for the repo map and
[`../phases/ROADMAP.md`](../phases/ROADMAP.md) for the phases either side of this one.

## Context

This repository builds a RAG system for SQLAlchemy 1.4 → 2.0 migrations. The full arc is in
`phases/ROADMAP.md` — six phases, ~14–16 weeks. **This plan covers Phase 0 only.**

Phase 0 comes first because the later phases assume two things that have to be true before
they are worth starting:

**Infrastructure you can defend, not just run.** Every phase after this one ships inside a
container, is exercised by CI, and eventually runs a model on a GPU. Copied configuration
gets you a working stack and nothing else — the moment it breaks, or someone asks *why* it is
written that way, you are stuck. So the standard here is not "does it run." It is the drill
list at the end of this file: **why does it work, and what happens when I change this line.**

**A migration you have felt, not read about.** `deliverables/BREAKAGES.md` is the deliverable, and it is
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

### Hardware decision (settled, numbers measured 2026-08-13)

Dell XPS 8950, hostname `kj-XPS-8950`, Ubuntu 24.04.4 LTS, x86-64. Linux users
`kj` and `shaili` (we work on `shaili`). Inventory: [`../study/08-LAB.md`](../study/08-LAB.md) §1.

```
# summary of: free -h; nvidia-smi; df -h /
Mem:     31Gi total
Swap:     8Gi
Disk:   915G, ~698G free
GPU:    NVIDIA GeForce RTX 3060, 12288 MiB, driver 595.71.05, CUDA 13.2
```

- **Build machine: this PC.** CUDA-first (fewer platform bugs eating the learning
  budget); two memory pools (**12GB VRAM for models + 31 GiB RAM for Docker/desktop**)
  beat the Mac's single contended 16GB; daily SSH/Docker/GPU on Linux **is itself
  the practice.** The old "12GB system RAM" figure was a guess. **VRAM is tight.
  System RAM is not.**
- **Mac (M4, 16GB): editor and driver's seat only**, via SSH once tunneling exists.
  Until then: AnyDesk + this Cursor login.
- **RustDesk/AnyDesk: keep, but scope them.** Fine for this sitting and emergency
  recovery. **Not** for daily coding — typing through a laggy video stream is miserable
  and teaches nothing.

### Operating constraints (these shape the plan)

- **Part A already ran on the Mac.** SQLAlchemy work needed no GPU. The PC is now
  reachable via AnyDesk; remaining Phase 0 is install + gates on this box.
- **Tunneling (Tailscale + sshd + reboot test) is still required** before Day 3
  closes. It is not the first hour. AnyDesk stays the fallback until `ssh` works
  after a reboot.
- **Shared lab machine** (`kj` + `shaili`) — may be rebooted, reimaged, or
  reassigned. **Push to GitHub constantly.** Do not take over `~/.claude` or
  `git config --global`. Local repo identity only. A dead PC must cost one day,
  not four months.
- **VRAM is the model budget, not RAM.** 7B + embed + reranker must fit in
  **12288 MiB**. Langfuse stays Phase 6 and on-demand because it is observability
  for later phases (~5 containers of ops), not because 31 GiB cannot hold it.
  Qdrant is light and can stay up. Compose + Ollama + a browser can coexist;
  stop unused stacks for VRAM/GPU hygiene, not RAM panic.
- **`sudo`: in the group, password required.** `sudo -n` fails. Docker Engine and
  the NVIDIA Container Toolkit wait on a typed password — not a missing-sudo
  replanning. Do not use snap Docker / `docker.io`.

---

## Part A — On the Mac, starting now (no lab needed)

### Day 0 — The repo and the naming system

**Project name: `sqlalchemy-upgrade-agent`** — one name for the folder, the git repo, and
the GitHub URL. *"Upgrade,"* not *"migration"*: in the SQLAlchemy world "migration" means
**Alembic schema migrations**, and this project is about **code/API** upgrades. The wrong
word costs thirty seconds of interviewer confusion for no reason.

- Create `~/Documents/Projects/sqlalchemy-upgrade-agent`. **No spaces in the path** — spaces
  break Docker mounts, shell scripts, and CI in annoying ways.
- Move `phases/ROADMAP.md` and `CLAUDE.md` in. Abandon the old `Project 1` folder.
- `git init`, create the GitHub remote, push. (Also unblocks Ultraplan, which requires a git
  repo.)
- Write `phases/PHASE-0.md` (this plan) into the repo.

**Naming conventions — decided once, applied everywhere:**

| Thing | Convention | Example |
|---|---|---|
| Folder / repo / GitHub | `kebab-case`, all identical | `sqlalchemy-upgrade-agent` |
| Python package + modules | `snake_case` (hyphens are illegal in Python imports) | `src/sqlalchemy_upgrade_agent/retrieval/` |
| Root-level docs | `SCREAMING_CASE.md` — signals "read me first" | `phases/ROADMAP.md`, `deliverables/BREAKAGES.md` |
| Branches | `phase-N/short-topic` | `phase-0/docker-basics` |
| Commits | Conventional Commits | `feat: add hybrid retrieval`, `docs: log 1.4 breakages` |

**Structure — created lazily, not all at once (YAGNI).** Only what each phase needs:

```
sqlalchemy-upgrade-agent/
├── README.md              # product framing first — written properly in Phase 6
├── phases/ROADMAP.md             # the 4-month arc
├── phases/PHASE-0.md             # this plan
├── deliverables/BREAKAGES.md           # Part A deliverable → seeds the Phase 2 golden dataset
├── pyproject.toml         # uv-managed
├── experiments/
│   └── sqlalchemy_1_4_vs_2_0/    # Part A practice code (SQLite, no infra)
├── src/sqlalchemy_upgrade_agent/ # grows from Phase 1 on
├── eval/                         # Phase 2 on — the crown jewel
├── tests/
└── .github/workflows/            # Phase 0 Part C
```

**Done when:** the repo exists on GitHub with `phases/ROADMAP.md` and `phases/PHASE-0.md` pushed.

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

**Deliverable: `deliverables/BREAKAGES.md`** — every failure hit in person: the 1.4 code, the exact
error, the 2.0 fix, and the doc section that explains it. **Target: ≥10 distinct
breakages.**

> `deliverables/BREAKAGES.md` is not busywork. It is **the seed of the Phase 2 golden dataset** — real
> questions with verified answers and known source locations, which is exactly the shape a
> golden record needs. It is also the answer to *"why this corpus?"*

**Done when:** ≥10 documented breakages caused, hit, and fixed in person — committed
and pushed.

---

## Part B — At the lab, next visit (in person, one sitting)

### Day 3 — The machine · **DO THIS PHYSICALLY AT THE LAB**

Concrete commands: [`../study/08-LAB.md`](../study/08-LAB.md). This section is the gate;
that file is the sitting checklist.

**2026-08-13 sitting order (deliberate deferral):** AnyDesk is already up. First sitting
is **clone on their Linux user + local git identity + Cursor as Viraj (login may
stay). Do not touch their Claude.** Do not change their `git config --global`.
Tailscale / Mac→PC SSH come after. Geochem/minmod is a different lab; do not
reuse that Mac SSH key here.

The one day that must happen in person. Everything after it is remote. The tunneling
half of Day 3 is still required before the phase gate; it is just not the first hour.

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
| `deliverables/BREAKAGES.md` | A | Real migration failures → **seeds the Phase 2 golden dataset** |
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
#   b = pathlib.Path('deliverables/BREAKAGES.md')
#   rows = [
#    ('deliverables/BREAKAGES.md', f\"{len(re.findall(r'^### ', b.read_text(), re.M))} entries (target 10)\"),
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
deliverables/BREAKAGES.md           23 entries (target 10)
experiments/sqlalchemy_1_4_vs_2_0/  12 modules
Dockerfile                          yes
.dockerignore                       yes
entrypoint.sh                       yes
docker-compose.yml                  yes
tests/                              12 files
.github/workflows/                  1 workflows
```

**`.github/workflows/` is the remaining work on this machine.** It comes last for a reason:
CI's gate is *"a PR with a deliberately failing test that GitHub refuses to merge"*, which needs
tests to exist before a workflow can run them.

```
# runnable: uv run pytest tests/test_db_config.py tests/test_models.py tests/test_seed.py 2>&1 | tail -1
17 passed, 1 warning in 0.46s
```

(Named file by file on purpose. A bare `uv run pytest` now also collects Phase 1's
`tests/test_corpus.py`; these three are Phase 0's, and this block is Phase 0's record.)

Those 17 pin claims the docs make rather than testing the library: the counts in
`study/03-PRACTICE-APP.md`, the six-classes/eight-tables split, seed determinism, and the `is_seeded`
guard that stops `entrypoint.sh` dropping a populated Postgres volume.

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
| No `sudo` on the lab machine | `shaili` is in group `sudo`; password required. Typed password unblocks Docker/toolkit. Missing-sudo replan only if that stops working. |
| Lab PC rebooted / reimaged / reassigned by someone else | Everything pushed to GitHub continuously. A dead PC costs one day, not the project. Shared users `kj` + `shaili`. |
| Locked out remotely, can only visit once/day | `sshd` + Tailscale as systemd services, tested across a real reboot **before leaving the lab.** AnyDesk is up now; it is the fallback, not the daily path. |
| 12GB VRAM exhausted (not system RAM) | Size 7B / embed / reranker against `nvidia-smi` leftover MiB / 12288. Langfuse stays Phase 6 for product reasons, not RAM. |
| Split-brain between Mac and PC | The **PC is the single source of truth.** The Mac is an editor, not a second workspace. |

---

## What comes next (not this plan)

**Phase 1 — a deliberately dumb RAG.** Meaning-search only. No hybrid search, no
reranking, no agent. Build the naive version and *watch it fail*, so that every improvement
in Phase 3 comes with a before/after number earned in person. Details in `phases/ROADMAP.md`.
