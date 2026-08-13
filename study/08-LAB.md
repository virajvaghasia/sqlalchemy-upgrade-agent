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
user = same `~/.gitconfig`, same `~/.claude`, same Cursor login.

**This sitting: clone on their user. Do not touch their Claude.** No `claude`,
no `/logout`, no install, no login. `~/.claude` is theirs. AI help stays on the
Mac. Do not create a `viraj` Linux user. Do not change `git config --global`.

Your identity (measured on the Mac, 2026-08-13):

```
# summary of: git config user.name && git config user.email
virajvaghasia
61740198+virajvaghasia@users.noreply.github.com
```

Every commit on this PC must show that pair. Anyone else's name in
`git log` is a wrong setup, not a style issue.

---

## Sitting now — borrow, work, revert (AnyDesk)

No Tailscale. No Mac→PC SSH. No geochem key. No Docker, no Ollama. No new Linux user.

**Done when:** you pulled `phase-0/repo-structure`, their Claude is untouched,
their `git config --global` is untouched, and you did not `gh auth login` as you.

### 0. Snapshot — write this down before you change anything

You need this to revert. If you do not write it, you cannot put their account back.

```
whoami
git config --global --list
gh auth status
```

Write down **their `git config --global user.email`**. Do not "remember it."
Do not snapshot Claude in order to log it out — you are not touching Claude.

If global git is already yours, stop and tell Claude — that would mean someone
already overwrote their identity.

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
  account is not yours. Do **not** run `git config --global`. Local config on
  the clone only (2b).

### 1b. Own Linux user — not today

`sudo adduser viraj` is the real isolation. Skip it this sitting. Come back to
it when this box is yours for more than an afternoon.

### 2. git + clone

On **their** user, without touching global git:

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

Local, not `--global`. Leaves their global config alone. Deleting the clone
later deletes this too.

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

Do **not** `gh auth login` on this sitting unless you must push from the PC.
Mac push + PC pull does not need `gh` on their user. If you already logged `gh`
in as them, leave it. If you log in as you, you must `gh auth logout` in §6.

### 3. Cursor — open the folder, do not steal the account

If Cursor is already installed and signed in as them: **File → Open Folder →
`~/Projects/sqlalchemy-upgrade-agent`.** Do not Sign out. Do not Sign in as you.
Do not use Cursor Agent / Composer there — that is their subscription.

If Cursor is not installed, use any editor already on the box (`gedit`, `nano`,
VS Code if it is theirs). Same rule: do not switch accounts.

AI help for this project stays on the **Mac** (this chat). The PC is clone +
terminal + files.

### 4. Claude Code — do not touch it

Do not install. Do not run `claude`. Do not run `claude /logout`. Do not open
their Claude desktop app. `~/.claude` stays exactly as they left it.

If you need Claude while on AnyDesk, keep using the Mac.

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

Then keep going in the editor on the PC (their Cursor login, no Agent). One
branch, two machines: whoever just edited, pushes; the other pulls before typing.
Claude for this repo stays on the Mac.

### 6. Leave their machine as you found it

You should not have logged into Claude, Cursor, or `gh` as you. Confirm that:

```
# 1. You never ran claude. Do not run it now "to check."
# 2. GitHub CLI: only if you broke the rule and logged in as you
gh auth status
# if that shows YOU:  gh auth logout

# 3. Global git still them
git config --global --list
# user.email must still be THEIRS, from the §0 snapshot

# 4. Optional: remove the clone so their home is clean
#    Skip this if you will pull again tomorrow on the same box.
# cd ~ && rm -rf ~/Projects/sqlalchemy-upgrade-agent
```

Close the sqlalchemy folder in Cursor. Leave **their** Cursor account signed in.

If you accidentally signed into Cursor as you: Sign out, sign **them** back in.

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
- Commit as the other person. If `git config user.email` (local) is not the
  noreply address, the commit is wrong even if the diff is right.
- `git config --global` on their user. Local repo config only.
- Run `claude`, `claude /logout`, or install Claude Code on this box. Their
  Claude stays untouched.
- Sign out of their Cursor / sign in as you. Open the folder only.
- Create `viraj` this sitting.
- Tailscale / sshd / reboot **this sitting**. Editors first.
- Docker Desktop / Snap Docker / `apt install docker.io`.
- Bake `issues.db` into the image. `entrypoint.sh` seeds at start.
- Start Langfuse. ~5 containers, Phase 6, 12GB RAM.
- Rewrite Docker / Compose / CI "because the PC is new."
- Commit from both Mac *and* PC without pushing. Split-brain.

---

## Suggested order today

1. §0 snapshot → write down their global git email.
2. §1 inventory → paste it here.
3. §2 clone + checkout `phase-0/repo-structure` + `git pull`. No `--global`.
4. §2b local git identity on **this repo only**.
5. §3 Open the folder in their Cursor. Do not switch accounts. Do not use Agent.
6. §4 Do not touch Claude. AI stays on the Mac.
7. Work. Mac push / PC pull.
8. §6 close the folder. Global git still them. Claude never touched.
