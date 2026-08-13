# Lab PC — from-scratch runbook (Phase 0 Day 3 → Day 10)

Two different labs. Do not mix them.

| | geochem / ISI | this PC |
|---|---|---|
| what | minmod NAS, paper corpus | Ubuntu box for sqlalchemy-upgrade-agent |
| access you have now | Mac SSH key labelled `-geochem` | **AnyDesk only** |
| Mac key `id_ed25519` | that lab | **do not copy it here** |

This Ubuntu machine is the **build machine**: Dell XPS 8950 (`kj-XPS-8950`),
RTX 3060 **12288 MiB VRAM**, **31 GiB** system RAM. Measured 2026-08-13.
The Mac stays the driver's seat *later*, via SSH. That tunneling is **not this sitting.**

Gates live in [`../phases/PHASE-0.md`](../phases/PHASE-0.md). Docker concepts stay in
[`04-DOCKER.md`](04-DOCKER.md) and [`05-COMPOSE.md`](05-COMPOSE.md) §4.5.

The 12GB-**system**-RAM figure in older docs was a guess. **VRAM is tight. RAM is not.**
Do not plan as if Compose + Ollama will OOM the desktop. Do not get sloppy with
model size — leftover VRAM still has to hold Phase 1 embed + reranker.

**Every command in this file carries a why + an example.** If you only see a
bare command, the file is incomplete — that is a bug, not a style choice.

Clone branch: **`phase-0/repo-structure`** (not default `main`).

Repo is **public**: `https://github.com/virajvaghasia/sqlalchemy-upgrade-agent.git`
HTTPS clone needs no GitHub login. Push from this PC later will, and that push
must be **Viraj's** GitHub, not whoever already uses this box.

**This box already has someone else's git and someone else's Claude.** Same Linux
user = same `~/.gitconfig`, same `~/.claude`, same Cursor login.

**This sitting: clone on their user. Cursor login as you is fine and can stay.
Do not touch their Claude.** No `claude`, no `/logout`, no install, no login.
`~/.claude` is theirs. Do not create a `viraj` Linux user. Do not change
`git config --global`.

Your identity (measured on the Mac, 2026-08-13):

```
# summary of: git config user.name && git config user.email
virajvaghasia
61740198+virajvaghasia@users.noreply.github.com
```

Every commit on this PC must show that pair. Anyone else's name in
`git log` is a wrong setup, not a style issue.

---

## New to Ubuntu? This sitting, explained (2026-08-13)

You are on **Linux Ubuntu**, not macOS. Same idea as a Mac (files, terminal, git),
different words. This section is the **record of what Cursor actually did today**,
in those words. The checklist below is the script; this is the diary. Future
steps (Docker, GPU-in-container, Ollama) get appended here as they happen — do
not rely on chat history.

**Where this clone lives**

```
/home/shaili/Documents/Workspace/SqlUpgradeAgent
```

On Ubuntu, `/home/shaili` is Shaili's home folder. `~` means the same thing.
You are logged in as Linux user **`shaili`**, not `viraj`. That is why their
git name and their Claude live here. We borrowed the account; we did not take
it over.

### 1. Who owns this computer?

```
# summary of: whoami; ls /home; hostnamectl
whoami          shaili
/home           kj   shaili
host            kj-XPS-8950   (Dell XPS 8950, Ubuntu 24.04)
```

- **`whoami`** — prints the Linux login you are using right now.
- **`/home`** — one folder per person. `kj` is someone else on this box.
  `shaili` is who we logged in as. Your project files are under `shaili`.
- **hostname** — the machine's name on the network. Not your GitHub name.

### 2. Snapshot before changing anything

We read **their** git identity and left it alone:

```
# summary of: git config --global user.name; git config --global user.email
Shaili Gandhi
shaili.gandhi@gmail.com
```

**Global** git (`~/.gitconfig`) applies to every repo on this Linux user.
Changing it would make *their* future commits look like you. We did **not**.

### 3. Clone the repo (download the project)

An empty Cursor folder was already open:
`~/Documents/Workspace/SqlUpgradeAgent`. We ran:

```
git clone https://github.com/virajvaghasia/sqlalchemy-upgrade-agent.git .
```

The `.` means "into this folder," not into a new subfolder.
`git clone` copies the GitHub repo onto this disk. HTTPS, so no SSH key needed
for a **public** repo.

Then:

```
git fetch --all --prune
git checkout phase-0/repo-structure
```

- **`fetch`** — download branch names and commits from GitHub. Does not change
  your files yet.
- **`checkout`** — switch which branch your files show. We are on
  `phase-0/repo-structure`, not `main`. That is the working branch.

### 4. Your name on *this repo only*

```
git config user.name "virajvaghasia"
git config user.email "61740198+virajvaghasia@users.noreply.github.com"
```

No `--global`. This writes `.git/config` **inside this clone only**. Delete the
folder later and their machine forgets you.

Check before any commit:

```
# runnable: git config user.name && git config user.email
virajvaghasia
61740198+virajvaghasia@users.noreply.github.com
```

If that prints `Shaili Gandhi`, stop. The commit would be theirs.

### 5. Log into GitHub as you (so you can push)

Ubuntu did not have the `gh` tool. We downloaded GitHub CLI **into your user
space** (`~/.local/bin/gh`), not system-wide — no `sudo` needed.

Then `gh auth login` in the browser, account **`virajvaghasia`**. That token is
now in Shaili's keyring. When you leave for good, §6 says `gh auth logout` so
you do not leave your GitHub login on their user.

**Name on commits** (step 4) and **permission to push** (step 5) are different.
One is a label. The other is a key.

### 6. Do not use Claude Code CLI on this box

You ran `claude` in a terminal. It printed hook errors (`node: not found`) and
**Not logged in**. That does **not** mean the slot is empty.

`~/.claude` already exists under `shaili` — credentials, history, plugins.
`/login` as you would overwrite **their** login. Close that terminal. Work in
**this Cursor chat** (your Cursor account).

### 7. Specs — measured, not guessed

```
# summary of: free -h; nvidia-smi; df -h /
RAM     31Gi total + 8Gi swap     (old plan said 12GB — that was wrong)
GPU     RTX 3060, 12288 MiB VRAM  (this part was right)
Disk    915G, ~698G free
```

- **RAM** = memory for Docker, browser, Cursor. Plenty.
- **VRAM** = memory **on the graphics card**, for models. Still only 12GB.
  That is the tight budget, not RAM.

`nvidia-smi` talks to the NVIDIA driver on the **host**. A Docker container
does not automatically see that GPU. Day 7 is the extra install that connects
them. Not done yet.

### 8. Python without breaking the system

Ubuntu already has `python3` (3.12) and `uv` (0.11.27).

```
cd ~/Documents/Workspace/SqlUpgradeAgent
cp .env.example .env
uv sync --frozen
uv run pytest
uv run python -m experiments.sqlalchemy_1_4_vs_2_0.seed
uv run python -m experiments.sqlalchemy_1_4_vs_2_0.check
```

| command | what it is |
|---|---|
| `cd` | change directory — "go into this folder" |
| `cp .env.example .env` | copy the template secrets file. `.env` is gitignored so passwords never get pushed |
| `uv sync --frozen` | create `.venv` and install **exactly** the versions in `uv.lock`. `frozen` = fail if lockfile is stale, do not silently upgrade |
| `uv run pytest` | run tests using that venv, not system Python. **17 passed, 1 warning** |
| `seed` / `check` | build `issues.db` (SQLite file in the repo folder) and confirm the ORM mappers load |

`.venv` is a private Python for this project. Ubuntu's `/usr/bin/python3` stays
untouched. Never `sudo pip install`.

### 9. Why Docker is waiting on you

```
# summary of: sudo -n -v; command -v docker
sudo: a password is required
docker: not found
```

**`sudo`** = "run this as administrator." You are in the `sudo` group, but
Ubuntu still asks for **Shaili's login password**. Cursor cannot type that for
you. Until you run `sudo -v` in a terminal and enter it, we cannot install
Docker Engine.

When we do: official Docker Engine from Docker's own repo. **Not**
`sudo snap install docker` and **not** `sudo apt install docker.io`. Those are
the wrong packages; the runbook below says why.

### 10. Docs updated today (so the plan matches the machine)

Not code — the plan files, because the 12GB-RAM assumption was false:

- [`CLAUDE.md`](../CLAUDE.md) — hardware + Langfuse reason
- [`../phases/PHASE-0.md`](../phases/PHASE-0.md) — constraints + risks
- this file — inventory + diary

Langfuse still waits until Phase 6. RAM would fit it now; the project is not
ready to observe anything yet.

### Words you will keep seeing

| Ubuntu word | means | Mac-ish cousin |
|---|---|---|
| terminal / shell | the text window that runs commands | Terminal.app |
| `~` | your home folder, `/home/shaili` | `/Users/you` |
| `sudo` | admin; needs their password | macOS admin prompt |
| package (`apt`) | install software system-wide | Homebrew, but needs sudo |
| snap | Ubuntu's other installer. We avoid it for Docker | — |
| PATH | list of folders Ubuntu searches for programs. `~/.local/bin` is yours, no sudo | same idea |
| `.` / `..` | this folder / parent folder | same |
| hidden file | name starts with `.` — `.git`, `.env`, `.claude` | same, Finder hides them |

### 11. Docker Engine install — each command, with an example

**Wrong packages (do not run these):**

```
sudo snap install docker          # Snap: different Docker, awkward permissions
sudo apt install docker.io        # Ubuntu's old package, not Docker Inc's Engine
```

**Right package:** `docker-ce` from Docker's own apt repo. Same Engine CI will use.
Example of why it matters: `docker compose` is a **plugin** (`docker compose version`).
`docker.io` often leaves you with the old `docker-compose` hyphen binary, or none.

A desktop password box may appear (`pkexec`). That is Shaili's Ubuntu password.

#### Step A — refresh apt's catalog

```
sudo apt update
```

Ubuntu keeps a **list** of installable packages. `update` refreshes the list.
It does **not** upgrade installed software (`upgrade` does that).
Example: without `update`, apt might say "package docker-ce not found" even
after we add Docker's repo, because it is still reading yesterday's list.

#### Step B — tools the next steps need

```
sudo apt install -y ca-certificates curl
```

- `curl` — download a file from a URL. Example: fetch Docker's GPG key.
- `ca-certificates` — the trust store so HTTPS is real, not "anyone claiming to be Docker."
- `-y` — answer yes to "install these?" so it does not wait for Enter.

#### Step C — trust Docker's signing key

```
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
```

apt will only install from a third-party repo if the packages are **signed** with
a key we stored. Example: a fake "docker-ce" on a random website would fail this
check. `0755` = directory readable by everyone, writable by root.
`/etc/apt/keyrings/docker.asc` is the key file after this step.

#### Step D — add Docker's apt source

```
sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: noble
Components: stable
Architectures: amd64
Signed-By: /etc/apt/keyrings/docker.asc
EOF
```

This file is a pointer: "also look at Docker Inc's server, Ubuntu 24.04 (`noble`),
64-bit (`amd64`), only packages signed by the key from Step C."
Example: `Suites: jammy` would be Ubuntu 22.04 — wrong on this box, packages
would not match. We use `noble` because `VERSION_CODENAME=noble` on this PC.

Then `sudo apt update` again so the catalog **includes** Docker's packages.

#### Step E — install Engine + Compose plugin

```
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

| package | what you get | example |
|---|---|---|
| `docker-ce` | the daemon (background service) | `dockerd` running as a systemd service |
| `docker-ce-cli` | the `docker` command | `docker ps` |
| `containerd.io` | low-level runtime Engine uses | you do not call this directly |
| `docker-compose-plugin` | `docker compose` | `docker compose up --build` in this repo |
| `docker-buildx-plugin` | newer builder | `docker build` uses it |

#### Step F — start now, and after reboot

```
sudo systemctl enable --now docker
```

`systemctl` talks to systemd (Ubuntu's service manager).
- `enable` — start Docker after a reboot. Example: lab power-cycle tonight, Docker still runs tomorrow.
- `--now` — also start it **this minute**. `enable` alone would wait until reboot.

#### Step G — let user `shaili` run Docker without sudo

```
sudo usermod -aG docker shaili
```

Docker's socket is root-only unless you are in group `docker`.
`-aG` = **append** to groups, do not wipe existing groups (video, sudo, …).
Example of the bug `-a` prevents: `usermod -G docker shaili` (no `-a`) would
**remove** `sudo` and you could not `sudo` anymore.

Group changes apply at **next login**. Until then:

```
newgrp docker
```

opens a subshell that already has the group. Example: `docker ps` works there
without `sudo`; a brand-new terminal might still say `permission denied` until
you log out/in.

#### Step H — prove it

```
docker version
docker compose version
docker run --rm hello-world
```

`hello-world` is a tiny image: Engine downloads it, runs a container, prints
"Hello from Docker!", then `--rm` deletes the container. Example of success:
you see that message. Example of failure: `Cannot connect to the Docker daemon`
(service not running) or `permission denied` (not in group yet).

**Measured on this PC, 2026-08-13** — script `/tmp/install-docker-engine.sh`,
exit 0. Not snap. Not `docker.io`.

```
# summary of: docker version --format 'Engine: {{.Server.Version}}  Client: {{.Client.Version}}'; docker compose version
Engine: 29.7.2  Client: 29.7.2
Docker Compose version v5.4.0
```

**Lived on this PC, same sitting.** Terminal 3 was opened *before* `usermod -aG`.
It still lacked group `docker`, so:

```
# summary of: docker run --rm hello-world   # in the OLD terminal
permission denied while trying to connect to the docker API at unix:///var/run/docker.sock
```

That socket is `root:docker` mode `660`. Old shell → not in group → denied.
Fix: `newgrp docker` in that terminal, or open a **new** terminal. Then:

```
# summary of: sg docker -c 'docker run --rm hello-world'
Hello from Docker!
```

`docker compose up --build` is next, in a shell that already has group `docker`.

Then in this repo (`cp .env.example .env` already done):

```
docker compose up --build
```

Wanted (same as the Mac measurement):

```
database: postgresql+psycopg2://app:***@db:5432/issues
```

---

## Sitting now — borrow, work, revert (AnyDesk)

No Tailscale. No Mac→PC SSH. No geochem key. No Docker, no Ollama. No new Linux user.

**Done when:** you pulled `phase-0/repo-structure`, Cursor is signed in as you
(and may stay that way), their Claude is untouched, their `git config --global`
is untouched, and you did not `gh auth login` as you.

### 0. Snapshot — write this down before you change anything

You need this to revert. If you do not write it, you cannot put their account back.

```
# Linux login name. Example on this box: shaili (not viraj).
whoami

# THEIR git identity for every repo. Write down user.email. Do not change it.
git config --global --list

# Who GitHub CLI is logged in as. Example after this sitting: virajvaghasia.
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

- No `sudo` → stop. **Measured:** `shaili` is in group `sudo`; `sudo -n` fails
  (password required). That is not "no sudo." Type the password when Docker
  install starts.
- Paste that block back. Especially `whoami`, `/home`, and global git.
- If `git config --global user.email` is **not** the noreply address, this
  account is not yours. Do **not** run `git config --global`. Local config on
  the clone only (2b).

Measured on this box, 2026-08-13 (AnyDesk, user `shaili`):

```
# summary of: whoami; ls /home; hostnamectl; lsb_release -a; free -h; df -h /; nvidia-smi; git config --global user.email
whoami          shaili
/home           kj  shaili
host            kj-XPS-8950  (Dell XPS 8950)
OS              Ubuntu 24.04.4 LTS, x86-64
Mem             31Gi total, 8Gi swap
Disk            915G total, ~698G free
GPU             RTX 3060, 12288 MiB, driver 595.71.05, CUDA 13.2
global git      Shaili Gandhi <shaili.gandhi@gmail.com>
sudo            in group, password required
docker          Engine 29.7.2 + Compose v5.4.0 (installed 2026-08-13; not snap / not docker.io)
uv / pytest     17 passed on this clone (CPython 3.11.15 via uv)
```

### 1b. Own Linux user — not today

`sudo adduser viraj` is the real isolation. Skip it this sitting. Come back to
it when this box is yours for more than an afternoon.

### 2. git + clone

On **their** user, without touching global git. This sitting cloned into
`~/Documents/Workspace/SqlUpgradeAgent` (Cursor's folder) instead of
`~/Projects/...`. Same commands, different parent directory.

```
# Refresh Ubuntu's package catalog. Does NOT upgrade installed software.
# Example: without this, apt may say "git not found" even though it exists.
sudo apt update

# Install git (version control), curl (download URLs), ca-certificates (HTTPS trust).
# -y = answer yes automatically. Example: skip -y and apt waits for Enter.
sudo apt install -y git curl ca-certificates

# mkdir -p = create folder and parents; no error if it already exists.
mkdir -p ~/Projects
cd ~/Projects

# Copy the GitHub repo onto this disk. HTTPS = no SSH key needed for a public repo.
# Example: after this, `ls sqlalchemy-upgrade-agent` shows README.md, study/, …
git clone https://github.com/virajvaghasia/sqlalchemy-upgrade-agent.git
cd sqlalchemy-upgrade-agent

# Switch files to the working branch (not main). Example: `git status` then
# says "On branch phase-0/repo-structure".
git checkout phase-0/repo-structure

# Download any commits on that branch you don't have yet.
git pull

# status = what branch / dirty files. log -1 = newest commit only.
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

# Write YOUR name into THIS clone only (.git/config). No --global.
# Example of the bug: `git config --global user.email ...` would relabel
# Shaili's future commits on every other repo on this Linux user.
git config user.name "virajvaghasia"
git config user.email "61740198+virajvaghasia@users.noreply.github.com"

# Show only this-repo settings. You should see user.name and user.email above.
git config --local --list
```

Confirm before any commit (no `--local` needed: git uses local, then global):

```
# Must print exactly this pair. If it prints Shaili Gandhi, stop.
git config user.name
git config user.email
```

Must print exactly the pair above. If it prints someone else, stop.

Do **not** `gh auth login` on this sitting unless you must push from the PC.
Mac push + PC pull does not need `gh` on their user. If you already logged `gh`
in as them, leave it. If you log in as you, you must `gh auth logout` in §6.

### 3. Cursor — sign in as you, leave it

Cursor login as you is allowed and does **not** need reverting.

If Cursor is already installed: sign in with **your** Cursor account (same as
the Mac) if it is not already. Then File → Open Folder →
`~/Projects/sqlalchemy-upgrade-agent`.

If Cursor is not installed:

```
cd ~/Downloads
ls *.deb
sudo apt install -y ./cursor_*.deb
```

Or download the Linux `.deb` from https://cursor.com/download first. Sign in
as you. Leave that login. Do not sign them back in when you disconnect.

Claude Code CLI is still off limits (§4). Cursor Agent on **your** login is
fine — that is your subscription, not theirs.

### 4. Claude Code — do not touch it

Do not install. Do not run `claude`. Do not run `claude /logout`. Do not open
their Claude desktop app. `~/.claude` stays exactly as they left it.

Claude **Code CLI** stays off this box. Cursor Agent on your login is fine.

`uv` + pytest: **done this sitting.** Docker Engine: **installed this sitting.**
Compose up + GPU toolkit + Ollama: still later. Claude Code CLI: still off limits.

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

Then keep going in **your** Cursor on the PC. One branch, two machines: whoever
just edited, pushes; the other pulls before typing. Do not run `claude` on the PC.

### 6. Leave Claude and global git as you found them

Cursor login as you **stays**. Do not sign them back into Cursor.

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

Close the sqlalchemy folder if you are done for the day. Cursor can remain
signed in as you.

---

## Later — tunneling (Mac → this PC)

Skip until the clone + editors work. Then: Tailscale, `sshd`, a **new** Mac→PC key
(not the geochem one), reboot test, VS Code/Cursor Remote-SSH.

AnyDesk stays the emergency GUI. Daily typing through it is miserable; tunneling is
still the plan, just not today.

### L.1 Essentials + SSH that survives reboot

```
# Install the SSH server (sshd). This is what the Mac will connect TO.
sudo apt install -y openssh-server

# enable = start ssh after reboot. --now = also start this minute.
# Example: `start` alone → after a lab power-cycle you are locked out until you visit.
sudo systemctl enable --now ssh

# --no-pager = print status and return to the prompt (don't open `less`).
# Wanted: "active (running)".
sudo systemctl status ssh --no-pager
```

### L.2 Tailscale (both machines)

**Measured 2026-08-13 — already installed and logged in as Shaili, not Viraj:**

```
# summary of: tailscale status; tailscale ip -4
100.72.117.53   kj-xps-8950  shaili.gandhi@  linux
```

Do **not** run `sudo tailscale up` as Viraj on this box. That switches/kicks
**her** Tailscale the same way `/login` on Claude would overwrite `~/.claude`.
Viraj does **not** have her Tailscale password. He also does **not** join her
tailnet. She **shares one node** (`kj-xps-8950`) via a share link.

Message to send her:

```
Hi Shaili — could you share the lab desktop with me on Tailscale? I don't have
your Tailscale password and I shouldn't log in as you.

On this PC, in a browser while YOU are signed into Tailscale:

1. Open https://login.tailscale.com/admin/machines
2. Find kj-xps-8950
3. Click ... on that row → Share → Copy share link
4. Send me that link

What it does: lets my laptop SSH to that one machine only. It does not add me
to your tailnet, does not change anything on the PC, and you can unshare it
any time.

Why: the lab is on 10.25.x and my Mac is on 10.23.x, so they cannot reach each
other on campus Wi-Fi. I will not run tailscale up / login on this PC (that
would replace your Tailscale login).
```

She sends the link. Viraj opens it **on the Mac** signed in as
`virajvaghasia@github`. Do **not** paste the share URL into this repo (public).

If Tailscale were absent (it is not), the original install would be:

```
# Install Tailscale. | sh = run the downloaded script.
curl -fsSL https://tailscale.com/install.sh | sh

# Log this PC into your Tailscale account (browser/auth prompt).
sudo tailscale up

# Survive reboot. Same enable --now idea as Docker and ssh.
sudo systemctl enable --now tailscaled

# Print this PC's Tailscale IPv4 (100.x.x.x). That is the HostName on the Mac.
tailscale ip -4
```

Mac: Viraj's own tailnet (`virajvaghasia@github`). After she shares `kj-xps-8950`,
ping `100.72.117.53`. Do not sign this PC into Viraj's account.

### L.3 A new key for this PC — not geochem

On the **Mac**, make a key whose only job is this Ubuntu box:

```
# -t ed25519 = key type. -C = comment (label only). -f = filename.
# Example of the disaster: omitting -f overwrites ~/.ssh/id_ed25519 (geochem/minmod).
ssh-keygen -t ed25519 -C "viraj@mac-sqlalchemy-lab" -f ~/.ssh/id_ed25519_sqlalchemy_lab
```

Do **not** overwrite `~/.ssh/id_ed25519`. That one is geochem/minmod.

PC:

```
# 700 = only you can enter ~/.ssh. Example: 755 would let others list your keys.
mkdir -p ~/.ssh && chmod 700 ~/.ssh

# Paste ONE line: the Mac's .pub file. nano is a simple text editor (Ctrl+O save, Ctrl+X quit).
nano ~/.ssh/authorized_keys

# 600 = only you read/write that file. sshd ignores it if permissions are too open.
chmod 600 ~/.ssh/authorized_keys
```

Paste one line: `cat ~/.ssh/id_ed25519_sqlalchemy_lab.pub` on the Mac.

Mac `~/.ssh/config` (create it; it does not exist yet):

```
Host sqlalchemy-lab
  HostName 100.72.117.53
  User shaili
  IdentityFile ~/.ssh/id_ed25519_sqlalchemy_lab
  IdentitiesOnly yes
```

Test while AnyDesk is still up: `ssh sqlalchemy-lab`. No password.

### L.4 Reboot test

```
# Reboot this PC. Test ssh FROM THE MAC while AnyDesk is still available as backup.
sudo reboot
```

From the Mac: `ssh sqlalchemy-lab` still works. If AnyDesk also needs a click at the
login screen, unattended access is not done.

**Tunneling done when:** `ssh sqlalchemy-lab` works after a reboot, Cursor Remote opens
the folder, no AnyDesk required for daily work.

**Deferred 2026-08-13 — no reboot for ~20 days (Viraj not in lab).** Do **not**
`sudo reboot` to close Day 3. Prove SSH **without** a reboot first:

```
# from Mac, while AnyDesk is still up as backup
ssh sqlalchemy-lab
```

Wanted: shell as `shaili`, no password. That is enough to work remotely for now.
The reboot half stays open until the next in-person visit — services are already
`enable`d (`ssh`, `docker`, `tailscaled`, `ollama`) so a lab power-cycle *should*
bring them back; we just are not verifying that today.

---

## Later — Docker Engine (not snap, not `docker.io`, not Desktop)

Ubuntu's `docker.io` and the Snap are the wrong packages. Official Engine + Compose plugin.
Install steps: <https://docs.docker.com/engine/install/ubuntu/>
Long Ubuntu-beginner walkthrough: **§11** above.

**Do not run:** `sudo snap install docker` or `sudo apt install docker.io`.
Example: Ubuntu's "docker not found" hint suggests those. They are a different
Docker. This repo needs `docker compose` (plugin) from `docker-ce`.

**Done on this PC, 2026-08-13:** `sudo bash /tmp/install-docker-engine.sh` →
Engine **29.7.2**, Compose **v5.4.0**. Commands below are what that script ran.

```
# Refresh package catalog. Example: without this, apt may not see docker-ce yet.
sudo apt update

# curl = download a URL. ca-certificates = HTTPS trust store.
# -y = don't wait for yes/no. Example: fetch Docker's GPG key in the next step.
sudo apt install -y ca-certificates curl

# Create /etc/apt/keyrings (0755 = everyone can read, only root writes).
sudo install -m 0755 -d /etc/apt/keyrings

# -fsSL: fail on HTTP errors, silent progress, show errors, follow redirects.
# Example: save Docker Inc's signing key so fake packages won't install.
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# tee writes stdin to a file (and prints it). EOF ... EOF is the file contents.
# Suites: noble = Ubuntu 24.04 on this box. jammy would be 22.04 — wrong here.
# Architectures: amd64 = this PC. Mac was arm64; do not rewrite the Dockerfile.
sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

# Update AGAIN so the catalog now includes Docker Inc's packages.
sudo apt update

# docker-ce = daemon. docker-ce-cli = `docker` command.
# docker-compose-plugin = `docker compose` (space, not hyphen).
# containerd.io = runtime Engine uses. buildx = newer `docker build`.
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# enable = start after reboot. --now = also start this minute.
# Example: enable alone → Docker dead until you reboot; start alone → dead after reboot.
sudo systemctl enable --now docker

# -aG = APPEND group docker. Never `usermod -G docker` (no -a): that WIPES sudo.
sudo usermod -aG docker "$USER"
```

Group change applies at next login. Until then, `newgrp docker` or a **new** terminal.

```
# Client + daemon versions. Measured here: Engine 29.7.2 / Client 29.7.2
docker version

# Compose plugin. Measured here: v5.4.0
docker compose version

# Tiny test image. --rm = delete the container when it exits.
# Success example: prints "Hello from Docker!".
# Fail examples: daemon not running, or permission denied (old terminal, not in group).
docker run --rm hello-world
```

In the repo. `.env` is gitignored; `.env.example` is what a fresh clone is supposed to copy:

```
# Copy template secrets. Already done this sitting. .env never gets committed.
cp .env.example .env

# Build the app image and start app + Postgres. --build = rebuild if Dockerfile changed.
# Wanted line in the logs: database: postgresql+psycopg2://app:***@db:5432/issues
docker compose up --build
```

Wanted, same measurement as the Mac (see `README.md` / `phases/ROADMAP.md`):

```
database: postgresql+psycopg2://app:***@db:5432/issues
38 open issues
```

**Measured on this PC, 2026-08-13** (`docker compose up --build`, amd64):

```
# summary of: docker compose up --build   (app-1 logs)
database: postgresql+psycopg2://app:***@db:5432/issues
  users                  5
  projects               3
  issues               200
  ...
38 open issues
app-1 exited with code 0
```

What the lines mean:

| log | example / why |
|---|---|
| `Image postgres:16-alpine Pulled` | downloaded Postgres. Pinned **16**, not `latest` |
| `Image sqlalchemy-upgrade-agent:latest Built` | built **this** Dockerfile on amd64 (Mac was arm64) |
| `Network …_default Created` | private network. `app` reaches Postgres as hostname **`db`** |
| `Volume …_pgdata Created` | database files live here, survive `compose down` (not `-v`) |
| `db-1 … Healthy` | healthcheck passed (`pg_isready`). `app` waited for this, not just "container started" |
| `database: postgresql+…@db:5432/issues` | not SQLite. Host is **`db`**, the service name |
| `38 open issues` | Apollo open-issue query. Same number as the Mac |
| `app-1 exited with code 0` | the app is a one-shot script, not a web server. 0 = success. `db` stays up |
| `sh: locale: not found` on db | Alpine warning. Harmless here |

Compose is still attached. Keys at the bottom:

- **`d`** = detach. Logs stop; containers keep running.
- **Ctrl+C** = stop following **and stop the containers**. Lived: 2026-08-13, trying
  to copy the terminal with Ctrl+C stopped `db-1`. Volume `pgdata` survived.
- Bring it back without attaching logs: `docker compose up -d`
- Later: `docker compose down` (keep volume) or `docker compose down -v` (wipe the DB).

**Copy/paste on Ubuntu terminal (not macOS):**

| you want | Linux terminal | Mac |
|---|---|---|
| copy | **Ctrl+Shift+C** (or select + right-click) | Cmd+C |
| paste | **Ctrl+Shift+V** | Cmd+V |
| stop the running program | Ctrl+C | Ctrl+C |

Ctrl+C in a terminal means **interrupt**, not copy. That is why Compose died.

This is the first **amd64** image you run locally. Every Mac build was arm64. Do **not**
rewrite the Dockerfile. Days 4–6 already happened. You are installing the runtime.

---

## Later — Day 7, GPU inside a container

Host `nvidia-smi` working does not mean containers see the GPU. That is the NVIDIA
Container Toolkit. Concept: [`05-COMPOSE.md`](05-COMPOSE.md) §4.5.
Install: <https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html>

**Why this is a separate install (example):**

```
# summary of: nvidia-smi -L                  # HOST, already works
GPU 0: NVIDIA GeForce RTX 3060

# summary of: docker info | grep Runtimes    # BEFORE toolkit
Runtimes: io.containerd.runc.v2 runc
```

No `nvidia` runtime. A container is isolated: it cannot see `/dev/nvidia0` until
the toolkit wires the driver into Docker. Same pattern as adding Docker's apt
repo (key → source list → apt install → configure).

**Restarting Docker will stop `db`.** Bring it back after: `docker compose up -d`.
Volume `pgdata` survives.

```
# Same pattern as Docker's key: download NVIDIA's signing key, store it for apt.
# gpg --dearmor = convert ASCII key to the binary format apt expects.
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

# Download NVIDIA's apt source list, then inject signed-by= so apt trusts that key.
# sed edits the line in-stream. tee writes the result under /etc/apt/sources.list.d/.
curl -sL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# Refresh catalog (now includes NVIDIA's repo), then install the toolkit.
sudo apt update
sudo apt install -y nvidia-container-toolkit

# Tell Docker: when someone passes --gpus, use NVIDIA's runtime. Then restart Docker.
# Example without this: `docker run --gpus all` fails or silently uses CPU.
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

Gate:

```
# --gpus all = expose the 3060 inside this container. --rm = delete after exit.
# Must print the 3060 FROM INSIDE. Host nvidia-smi already works; that is not the gate.
# Trap: container runs on CPU, ~10× slower, no error. Check the GPU name in the output.
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```

Must print the **3060 from inside the container**. "The container ran" is not the gate.
Silent CPU fallback is the trap: correct output, ~10× slower, no error.

**Measured on this PC, 2026-08-13 — Day 7 gate passed.**

```
# summary of: docker info | grep Runtimes     # AFTER toolkit
Runtimes: io.containerd.runc.v2 nvidia runc
```

```
# summary of: docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
NVIDIA-SMI 595.71.05    Driver Version: 595.71.05    CUDA Version: 13.2
GPU 0: NVIDIA GeForce RTX 3060    538MiB / 12288MiB
```

That table is from **inside** the container, not the host. Host `nvidia-smi` already
worked; this is the hole the toolkit cut. `12288 MiB` is still the model budget.

`--gpus all` = expose every host GPU to this one-shot container. `--rm` = delete
it after exit. Default runtime stays `runc` (normal containers); `nvidia` is used
only when you pass `--gpus`.

---

## Later — Day 10, Ollama on the 3060

Ollama runs **local** models on this GPU. No paid API. Phase 1 still needs leftover
VRAM for an embedding model + reranker after this 7B fits.

```
# Download Ollama's install script and run it. | sh = pipe into a shell.
# Example: installs the `ollama` binary + a systemd service (`ollama serve`).
# Needs sudo (writes under /usr/local). Same password as Docker.
curl -fsSL https://ollama.com/install.sh | sh

# pull = download the model weights onto disk (large). 7b ≈ 7 billion parameters.
ollama pull qwen2.5-coder:7b

# run = load it and send one prompt. Wanted reply: exactly `ok`.
ollama run qwen2.5-coder:7b "Reply with exactly: ok"
```

While it runs, another terminal:

```
# Watch GPU memory. Wanted: an `ollama` row using MiB on the 3060, not 0 MiB / CPU pegged.
nvidia-smi
```

Wanted: the `ollama` process on the GPU, not 0 MiB / 0% util with the CPU pegged.

Write down tokens/sec and MiB VRAM used / 12288. Phase 1 still needs an embedding model
and a reranker in the leftover VRAM. If 7B eats almost all of it, drop quant or size —
measure, do not guess.

**31 GiB system RAM is not the limiter.** Compose + Ollama + a browser can stay up
together. Stop unused stacks anyway: the 3060 still has one VRAM pool, and this is
someone else's desktop.

**Measured on this PC, 2026-08-13 — Day 10 gate passed.**

Install: Ollama **0.32.9**, systemd `active`, script printed `>>> NVIDIA GPU installed.`
Pull: `qwen2.5-coder:7b` → **4.7 GB** on disk (`success`).

```
# summary of: ollama run --verbose qwen2.5-coder:7b "Reply with exactly: ok"
OK
eval rate: 0.62 tokens/s     # 2 output tokens — not a real speed figure
load duration: 19.0s         # first load into VRAM
```

```
# summary of: nvidia-smi   # while that run loaded
5164MiB / 12288MiB
...local/lib/ollama/llama-server    4650MiB
```

`llama-server` on the GPU is the gate, not the 0.62 number. Two output tokens
make tokens/sec look fake. Warm run (model already resident):

```
# summary of: ollama run --verbose qwen2.5-coder:7b "In one short sentence, what is SQLAlchemy?"
SQLAlchemy is an SQL toolkit and Object-Relational Mapping (ORM) library for Python.
eval rate:            62.23 tokens/s
prompt eval rate:     1357.43 tokens/s
load duration:        132.2ms
```

```
# summary of: nvidia-smi --query-gpu=memory.used,memory.total --format=csv
5173 MiB, 12288 MiB
leftover: 7115 MiB / 12288   (~58% free)
```

**62 tok/s on GPU, ~7.1 GB VRAM left.** Enough headroom for Phase 1 BGE-M3 (+ later
reranker). Do not jump to 14B. `--verbose` prints the rates; without it you only
see the text.

---

## Days 8–9 — CI gate (measured 2026-08-13)

`.github/workflows/ci.yml` already existed. `main` already had branch protection
requiring **`tests`**, **`2.0 evidence`**, **`image builds`**, `enforce_admins: true`.
The gate is not "YAML exists." It is: **a red PR cannot merge.**

```
# summary of: gh pr create … #3 + gh pr checks + gh pr merge 3 --merge
tests          fail
2.0 evidence   pass
image builds   pass
mergeStateStatus: BLOCKED
X Pull request #3 is not mergeable: the base branch policy prohibits the merge.
```

PR: https://github.com/virajvaghasia/sqlalchemy-upgrade-agent/pull/3  
Branch: `phase-0/ci-gate-deliberate-fail` — one file, `tests/test_ci_gate.py`,
`assert False` on purpose. Closed **without merging**. Do not land it.

`--admin` would bypass. That would cheat the gate. We did not.

---

## How commands get to this machine

Claude runs on the Mac and **cannot reach this PC** — no inbound route exists until sshd and
a tunnel do, and AnyDesk is a GUI it cannot type into. Commands aimed at the PC were bouncing
back into the chat unrun.

So the exchange is a file: [`../logs/HANDOFF.md`](../logs/HANDOFF.md) on branch `lab/handoff`.
Claude writes ASK blocks, you paste raw output into REPLY blocks, one round per commit.

```bash
git fetch origin && git checkout lab/handoff && git pull --rebase
```

## Still open

- ~~`uv sync` + `uv run pytest`~~ — **done on this PC, 2026-08-13: 17 passed, 1 warning.**
- ~~Docker Engine~~ — **done 2026-08-13: docker-ce 29.7.2 + Compose v5.4.0.**
  Not snap, not `docker.io`.
- ~~`docker run --rm hello-world`~~ — **worked after applying group `docker`.**
  Old terminal: `permission denied` on `docker.sock`. That is the group, not a broken install.
- ~~`docker compose up --build`~~ — **done 2026-08-13 amd64.**
  `database: postgresql+psycopg2://app:***@db:5432/issues` and `38 open issues`.
  `app-1` exited 0. Ctrl+C later stopped `db` too; volume kept. Restart: `docker compose up -d`.
- ~~Day 7: NVIDIA Container Toolkit~~ — **passed 2026-08-13.**
  `docker run --rm --gpus all … nvidia-smi` prints **RTX 3060, 12288 MiB** from inside
  the container. Runtimes now include `nvidia`.
- ~~Day 10: Ollama on the 3060~~ — **passed 2026-08-13.**
  `qwen2.5-coder:7b` on GPU (`llama-server` ~4650 MiB). Warm **62.23 tok/s**.
  Leftover **7115 MiB / 12288**.
- ~~CI gate~~ — **passed 2026-08-13.** PR #3: `tests` red, merge **BLOCKED**,
  closed unmerged. Protection on `main` is real, not advisory.
- Tunneling reboot test. PHASE-0 Day 3 is **not** closed until Mac `ssh sqlalchemy-lab`
  works after a reboot.
  - Tailscale: **already up on this PC as `shaili.gandhi@`**, IP `100.72.117.53`
    (`kj-xps-8950`). Viraj has no Tailscale password for her. Ask her to
    **Share → Copy share link** on `kj-xps-8950` (message in §L.2). Do **not**
    `tailscale up` / login as Viraj on this PC.
  - sshd: install next (`sudo bash /tmp/install-sshd.sh`). Do **not** reboot today
    (shared desktop / AnyDesk).
  - **2026-08-13:** Viraj away ~20 days — **no reboot**. Prove `ssh sqlalchemy-lab`
    from Mac without rebooting. Reboot half waits until next lab visit.

---

## Do not

- Copy the Mac geochem key (`~/.ssh/id_ed25519`) onto this PC.
- Overwrite that key with a new default `id_ed25519` — minmod and GitHub-on-the-Mac break.
- Commit as the other person. If `git config user.email` (local) is not the
  noreply address, the commit is wrong even if the diff is right.
- `git config --global` on their user. Local repo config only.
- Run `claude`, `claude /logout`, or install Claude Code on this box. Their
  Claude stays untouched.
- Sign them back into Cursor. Your Cursor login can stay.
- Create `viraj` this sitting.
- Tailscale / sshd / reboot **this sitting**. Editors first.
- Docker Desktop / Snap Docker / `apt install docker.io`.
- Bake `issues.db` into the image. `entrypoint.sh` seeds at start.
- Start Langfuse. Phase 6, on-demand. RAM is no longer the reason; do not pull it forward.
- Rewrite Docker / Compose / CI "because the PC is new."
- Commit from both Mac *and* PC without pushing. Split-brain.

---

## Suggested order today

1. §0 snapshot → write down their global git email.
2. §1 inventory → paste it here.
3. §2 clone + checkout `phase-0/repo-structure` + `git pull`. No `--global`.
4. §2b local git identity on **this repo only**.
5. §3 Cursor: sign in as you. Leave it. Open the folder.
6. §4 Do not touch Claude.
7. Work. Mac push / PC pull. Cursor Agent on your login is fine.
8. §6 Cursor stays you. Global git still them. Claude never touched.
