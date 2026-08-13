# Lab PC — from-scratch runbook (Phase 0 Day 3 → Day 10)

Two different labs. Do not mix them.

| | geochem / ISI | this PC |
|---|---|---|
| what | minmod NAS, paper corpus | Ubuntu box for sqlalchemy-upgrade-agent |
| access you have now | Mac SSH key labelled `-geochem` | **AnyDesk only** |
| Mac key `id_ed25519` | that lab | **do not copy it here** |

This Ubuntu machine is the **build machine** (RTX 3060, 12GB VRAM, 12GB RAM). The Mac stays
the driver's seat *later*, via SSH. That tunneling is **not this sitting.**

Gates live in [`../phases/PHASE-0.md`](../phases/PHASE-0.md). Docker concepts stay in
[`04-DOCKER.md`](04-DOCKER.md) and [`05-COMPOSE.md`](05-COMPOSE.md) §4.5.

Nothing below is `# runnable` lab-PC output. These commands have not been run there yet.

Clone branch: **`phase-0/repo-structure`** (not default `main`).

Repo is **public**: `https://github.com/virajvaghasia/sqlalchemy-upgrade-agent.git`
HTTPS clone needs no GitHub login. Push from this PC later will, and that push
must be **Viraj's** GitHub, not whoever already uses this box.

**This box already has someone else's git and someone else's Claude.** Same Linux
user = same `~/.gitconfig`, same `~/.claude`, same Cursor login. You cannot "just
open the repo" on their account. Isolate first, then clone.

Your identity (measured on the Mac, 2026-08-13):

```
# summary of: git config user.name && git config user.email
virajvaghasia
61740198+virajvaghasia@users.noreply.github.com
```

Every commit on this PC must show that pair. Anyone else's name in
`git log` is a wrong setup, not a style issue.

---

## Sitting now — own user, git, Cursor, Claude Code (AnyDesk)

No Tailscale. No Mac→PC SSH. No geochem key. No Docker, no Ollama.

**Done when:** you are logged in as **your** Linux user, the repo is open in
**your** Cursor on `phase-0/repo-structure`, `claude` is **your** account, and
`git config user.email` in that repo is the noreply address above.

### 1. Inventory — stop if sudo fails

```
whoami
id
ls /home
hostnamectl
lsb_release -a
sudo -v
free -h
df -h /
git --version
git config --global --list
```

- No `sudo` → stop.
- Paste that block back. Especially `whoami`, `/home`, and global git.
- If `git config --global user.email` is **not** the noreply address, this
  account is not yours. Do not commit from it.

### 1b. Your own Linux user — do this if `whoami` is someone else

Same OS user as the other person means you will keep kicking each other out of
Cursor and Claude. A second Linux user is the actual fix.

```
sudo adduser viraj
sudo usermod -aG sudo viraj
```

Log out of AnyDesk's desktop session, log in as `viraj`, then continue **all**
steps below as that user. Clone into `/home/viraj/Projects/...`, not into the
other person's home.

If you cannot create a user this sitting: you can still set **local** git
config on the repo (step 2b) so commits are yours, but Cursor/Claude on a
shared home directory will remain one-login-at-a-time. Sign them out of the
other account before you sign in. That is a workaround, not isolation.

### 2. git + clone

As **your** user:

```
sudo apt update
sudo apt install -y git curl ca-certificates

mkdir -p ~/Projects
cd ~/Projects
git clone https://github.com/virajvaghasia/sqlalchemy-upgrade-agent.git
cd sqlalchemy-upgrade-agent
git checkout phase-0/repo-structure
git pull
git status
git log -1 --oneline
```

Wanted: `On branch phase-0/repo-structure`. If the clone happened before this
commit was pushed, `git pull` is what picks up `study/08-LAB.md`.

Do **not** run `ssh-keygen` yet. Do **not** paste the Mac geochem `.pub` here.
HTTPS is enough to pull a public repo.

### 2b. Pin **this repo** to your git identity

Local, not `--global`. Leaves the other person's global config alone.

```
cd ~/Projects/sqlalchemy-upgrade-agent
git config user.name "virajvaghasia"
git config user.email "61740198+virajvaghasia@users.noreply.github.com"
git config --local --list
```

Confirm before any commit:

```
git config user.name
git config user.email
```

Must print exactly the pair above. If it prints someone else, stop.

Push from this PC later: `gh auth login` as **you** (browser, AnyDesk), or a
**new** SSH key created on this PC for GitHub. Check `gh auth status` first —
if it is already logged in as the other person, `gh auth logout` then login
as you. That is PC→GitHub, not Mac→PC tunneling.

### 3. Cursor — your account only

GUI session as **your** Linux user.

Easiest: browser → https://cursor.com/download → Linux `.deb` → then:

```
cd ~/Downloads
ls *.deb
sudo apt install -y ./cursor_*.deb
```

Or the official apt repo (amd64):

```
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://downloads.cursor.com/keys/anysphere.asc \
  | gpg --dearmor \
  | sudo tee /etc/apt/keyrings/cursor.gpg > /dev/null
echo 'deb [arch=amd64 signed-by=/etc/apt/keyrings/cursor.gpg] https://downloads.cursor.com/aptrepo stable main' \
  | sudo tee /etc/apt/sources.list.d/cursor.list
sudo apt update
sudo apt install -y cursor
```

Open Cursor. If it is already signed in as someone else: **Cursor Settings →
Account → Sign out**, then sign in with **your** Cursor account (same as the
Mac). Then File → Open Folder → `~/Projects/sqlalchemy-upgrade-agent`.

Do not work in a window that still shows the other person's avatar.

### 4. Claude Code CLI — your account only

Separate from Cursor. Native installer:
<https://code.claude.com/docs/en/install>

```
curl -fsSL https://claude.ai/install.sh | bash
```

New terminal so `PATH` picks up `~/.local/bin`:

```
claude --version
cd ~/Projects/sqlalchemy-upgrade-agent
claude /logout
claude
```

`/logout` first if this home directory already had someone else's Claude.
Sign in as **you** (Pro / Max / Console — free claude.ai does not include
Claude Code).

`uv`, pytest, Docker: **not this sitting.**

### 5. How work continues after a Mac push

Mac (this repo):

```
git push -u origin HEAD
```

PC (your user, this clone):

```
cd ~/Projects/sqlalchemy-upgrade-agent
git checkout phase-0/repo-structure
git pull
```

Then keep going in **your** Cursor on the PC. One branch, two machines, no
split-brain: whoever just edited, pushes; the other pulls before typing.

---

## Later — tunneling (Mac → this PC)

Skip until the clone + editors work. Then: Tailscale, `sshd`, a **new** Mac→PC key
(not the geochem one), reboot test, VS Code/Cursor Remote-SSH.

AnyDesk stays the emergency GUI. Daily typing through it is miserable; tunneling is
still the plan, just not today.

### L.1 Essentials + SSH that survives reboot

```
sudo apt install -y openssh-server
sudo systemctl enable --now ssh
sudo systemctl status ssh --no-pager
```

`enable --now` = start now **and** after reboot. `start` alone dies on reboot.

### L.2 Tailscale (both machines)

PC:

```
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
sudo systemctl enable --now tailscaled
tailscale ip -4
```

Mac: same Tailscale account, ping the `100.x` address.

### L.3 A new key for this PC — not geochem

On the **Mac**, make a key whose only job is this Ubuntu box:

```
ssh-keygen -t ed25519 -C "viraj@mac-sqlalchemy-lab" -f ~/.ssh/id_ed25519_sqlalchemy_lab
```

Do **not** overwrite `~/.ssh/id_ed25519`. That one is geochem/minmod.

PC:

```
mkdir -p ~/.ssh && chmod 700 ~/.ssh
nano ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

Paste one line: `cat ~/.ssh/id_ed25519_sqlalchemy_lab.pub` on the Mac.

Mac `~/.ssh/config` (create it; it does not exist yet):

```
Host sqlalchemy-lab
  HostName 100.x.x.x
  User <pc-username>
  IdentityFile ~/.ssh/id_ed25519_sqlalchemy_lab
  IdentitiesOnly yes
```

Test while AnyDesk is still up: `ssh sqlalchemy-lab`. No password.

### L.4 Reboot test

```
sudo reboot
```

From the Mac: `ssh sqlalchemy-lab` still works. If AnyDesk also needs a click at the
login screen, unattended access is not done.

**Tunneling done when:** `ssh sqlalchemy-lab` works after a reboot, Cursor Remote opens
the folder, no AnyDesk required for daily work.

---

## Later — Docker Engine (not snap, not `docker.io`, not Desktop)

Ubuntu's `docker.io` and the Snap are the wrong packages. Official Engine + Compose plugin.
Install steps: <https://docs.docker.com/engine/install/ubuntu/>

```
sudo apt update
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
```

Log out and back in (or `newgrp docker`) so the group applies.

```
docker version
docker compose version
docker run --rm hello-world
```

In the repo. `.env` is gitignored; `.env.example` is what a fresh clone is supposed to copy:

```
cp .env.example .env
docker compose up --build
```

Wanted, same measurement as the Mac (see `README.md` / `phases/ROADMAP.md`):

```
database: postgresql+psycopg2://app:***@db:5432/issues
38 open issues
```

This is the first **amd64** image you run locally. Every Mac build was arm64. Do **not**
rewrite the Dockerfile. Days 4–6 already happened. You are installing the runtime.

---

## Later — Day 7, GPU inside a container

Host `nvidia-smi` working does not mean containers see the GPU. That is the NVIDIA
Container Toolkit. Concept: [`05-COMPOSE.md`](05-COMPOSE.md) §4.5.
Install: <https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html>

```
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -sL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt update
sudo apt install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

Gate:

```
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```

Must print the **3060 from inside the container**. "The container ran" is not the gate.
Silent CPU fallback is the trap: correct output, ~10× slower, no error.

---

## Later — Day 10, Ollama on the 3060

```
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5-coder:7b
ollama run qwen2.5-coder:7b "Reply with exactly: ok"
```

While it runs, another terminal:

```
nvidia-smi
```

Wanted: the `ollama` process on the GPU, not 0 MiB / 0% util with the CPU pegged.

Write down tokens/sec and MiB VRAM used / 12288. Phase 1 still needs an embedding model
and a reranker in the leftover VRAM. If 7B eats almost all of it, drop quant or size —
measure, do not guess.

12GB **system** RAM is still tight. Do not leave Compose + Ollama + a browser all up
unless you need both.

---

## Still open (not this sitting)

- `uv sync` + `uv run pytest` (17 passed on the Mac).
- CI gate: failing PR + branch protection. `.github/workflows/ci.yml` already exists.
- Tunneling reboot test. PHASE-0 Day 3 is not closed until that exists.

---

## Do not

- Copy the Mac geochem key (`~/.ssh/id_ed25519`) onto this PC.
- Overwrite that key with a new default `id_ed25519` — minmod and GitHub-on-the-Mac break.
- Commit as the other person. If `git config user.email` is not the noreply
  address, the commit is wrong even if the diff is right.
- Set `git config --global` on a shared OS user. Local repo config only, or
  your own Linux user with its own global.
- Stay signed into the other person's Cursor or Claude. Sign out first.
- Tailscale / sshd / reboot **this sitting**. Editors first.
- Docker Desktop / Snap Docker / `apt install docker.io`.
- Bake `issues.db` into the image. `entrypoint.sh` seeds at start.
- Start Langfuse. ~5 containers, Phase 6, 12GB RAM.
- Rewrite Docker / Compose / CI "because the PC is new."
- Commit from both Mac *and* PC without pushing. Split-brain.

---

## Suggested order today

1. §1 inventory → paste `whoami`, `/home`, and `git config --global --list`.
2. §1b new Linux user `viraj` if `whoami` is someone else. Log in as that user.
3. §2 clone + `git checkout phase-0/repo-structure` + `git pull`.
4. §2b local git identity. Confirm email before any commit.
5. §3 Cursor → sign out other account → sign in as you → open the folder.
6. §4 `claude /logout` then `claude` as you.
7. Stop. Tunneling is the next sitting, on purpose.
