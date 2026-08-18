# Handoff — Mac ⇄ lab PC

Claude runs on the **Mac** and cannot reach the lab PC: that machine has no inbound
route until `sshd` and a tunnel exist, which is the very thing being set up. AnyDesk is
a GUI, not something Claude can type into.

So this file is the wire. Claude writes **ASK** blocks; Viraj runs them on the PC and
pastes the output into the matching **REPLY** block; Claude reads it on the next pull.

## The loop

```
Claude (Mac)                          Viraj (lab PC, via Cursor)
  writes ASK  ──push──►  lab/handoff  ──pull──►  runs it
                                                 pastes raw output into REPLY
  reads REPLY ◄──pull──  lab/handoff  ◄──push──  pushes
```

**Branch: `lab/handoff`.** Not `main` — protection there requires a PR with green CI, and
these commits are notes rather than code. Merge to `main` when a round is finished and
worth keeping.

```bash
# on either machine, first time
git fetch origin && git checkout lab/handoff

# every round
git pull --rebase
# ...edit...
git commit -am "handoff: round N reply" && git push
```

If both sides edited, `git pull --rebase` will conflict on this file. Keep **both** blocks
— an ASK and its REPLY are never really in conflict, they belong to different sections.

## Rules that make this work

- **Paste raw output.** Not "it worked". The exact text is the measurement, and a summary
  has already thrown away whatever was surprising in it.
- **Say which machine** if it is not obvious. `apt`, `systemctl`, `nvidia-smi` = PC.
  `brew`, this repo's working copy = Mac.
- **Errors are the useful case.** A failure pasted in full is worth more than a success,
  and there is no need to fix it before reporting.
- **One round per commit**, so `git log` reads as a conversation.
- **Nothing secret in here.** It is a public repo. Private keys, passwords and tokens do
  not go in a REPLY. IPs and usernames on a lab LAN are fine.

---

# Round 1 — sshd and the LAN address

**Status: CLOSED 2026-08-13.** All three answered. sshd `enabled` + `active`, user `shaili`,
key installed with `-rw-------`. Your read on the LAN was right and is now measured — see Round 2.

## ASK 1.1 — is sshd running

```bash
sudo bash /tmp/install-sshd.sh
sudo systemctl enable --now ssh
sudo systemctl status ssh --no-pager
```

`enable --now` means start now *and* on every boot. `start` alone dies at the next reboot,
which is the failure the Day 3 gate is written to catch.

### REPLY 1.1

```
# /tmp/install-sshd.sh not re-run: ssh already enabled+active (installed earlier this sitting).
enabled
active
● ssh.service - OpenBSD Secure Shell server
     Loaded: loaded (/usr/lib/systemd/system/ssh.service; enabled; preset: enabled)
     Active: active (running) since Thu 2026-08-13 14:41:54 PDT; 48min ago
TriggeredBy: ● ssh.socket
       Docs: man:sshd(8)
             man:sshd_config(5)
    Process: 1862812 ExecStartPre=/usr/sbin/sshd -t (code=exited, status=0/SUCCESS)
   Main PID: 1862813 (sshd)
      Tasks: 1 (limit: 34671)
     Memory: 1.2M (peak: 1.9M)
        CPU: 9ms
     CGroup: /system.slice/ssh.service
             └─1862813 "sshd: /usr/sbin/sshd -D [listener] 0 of 10-100 startups"
```

## ASK 1.2 — who and where

```bash
whoami
ip -4 addr show | grep -v 127.0.0.1 | grep inet
```

Needed because the ssh command is `ssh <user>@<address>`, and that box is set up under
someone else's login — so the username is probably not `virajvaghasia`. Guessing it would
waste a round.

The Mac is on `10.23.35.192`. **If the PC's address also starts `10.23.`, you are on the
same network and SSH works today**, with no Tailscale at all.

### REPLY 1.2

```
shaili
    inet 10.25.102.155/16 brd 10.25.255.255 scope global dynamic noprefixroute wlp5s0
    inet 100.72.117.53/32 scope global tailscale0
    inet 172.17.0.1/16 brd 172.17.255.255 scope global docker0
    inet 172.18.0.1/16 brd 172.18.255.255 scope global br-1e5442b2ded3
```

## ASK 1.3 — install the Mac's public key

Paste this exact line into `~/.ssh/authorized_keys` on the PC:

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILhuSUpOdqb+R/AYjfTZOIZI3fyr9eLhCm/sz7c1onoe viraj@mac-sqlalchemy-lab
```

```bash
mkdir -p ~/.ssh && chmod 700 ~/.ssh
nano ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
ls -l ~/.ssh/authorized_keys
```

It is a **public** key — safe in a public repo, safe to paste anywhere. The private half
never leaves the Mac. The `chmod` values are not decoration: sshd ignores
`authorized_keys` if the file or directory is group- or world-writable, and it fails
silently, which is a genuinely nasty hour to lose.

This key opens **only this PC**. The Mac's `~/.ssh/id_ed25519` (geochem) is untouched and
must never be copied here.

### REPLY 1.3

```
-rw------- 1 shaili shaili 106 Aug 13 15:30 /home/shaili/.ssh/authorized_keys
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILhuSUpOdqb+R/AYjfTZOIZI3fyr9eLhCm/sz7c1onoe viraj@mac-sqlalchemy-lab
```

---

## What happens after Round 1

With `whoami` and the address, Claude tests `ssh` **from the Mac** and writes the
`~/.ssh/config` entry. That closes everything in PHASE-0 Day 3 except the reboot test,
which is deferred ~20 days by
[`08-LAB.md`](../study/08-LAB.md) because the desktop is shared.

Tailscale stays blocked on something Claude and Viraj cannot do alone: the PC is already
signed in as `shaili.gandhi@` (`kj-xps-8950`, `100.72.117.53`) and re-running
`tailscale up` as Viraj would replace her login. The fix is for her to **share that node**
to Viraj's Tailscale account — which first requires him to have one. See
[`08-LAB.md`](../study/08-LAB.md) §L.2.

**Round 1 does not depend on any of that.** LAN SSH proves sshd, the key and the
permissions; Tailscale only changes the address you type.

---

# Round 2 — the LAN is not a route, so Tailscale is the only way in

**Status: OPEN.** Both asks are on the **Mac**, plus one message to Shaili.

## What Round 1 settled

Everything on the PC side is correct and needs no further work:

| | |
|---|---|
| `sshd` | `enabled` + `active (running)`, so it survives a reboot |
| user | `shaili` |
| `authorized_keys` | `-rw-------`, correct key, correct mode |

**The PC is ready to accept the Mac's key.** Nothing below is a problem with that machine.

## What the addresses actually mean — measured, from the Mac

```
# runnable: nc -z -G 6 10.25.102.155 22
no route / filtered

# runnable: ssh -o ConnectTimeout=8 -i ~/.ssh/id_ed25519_sqlalchemy_lab shaili@10.25.102.155
ssh: connect to host 10.25.102.155 port 22: Operation timed out
```

```
Mac  10.23.35.192
PC   10.25.102.155/16   -> its network is 10.25.0.0 – 10.25.255.255
```

Both are `10.x` private addresses, which is what made this look like one LAN. It is not.
A `/16` means the PC considers only `10.25.*` to be local; `10.23.35.192` is outside it, and
the campus network does not route between the two segments.

**Read the error as evidence** (`05-COMPOSE.md` §4.2 makes the same point about containers):

| error | meaning |
|---|---|
| `connection refused` | reached the host, nothing listening |
| **`Operation timed out`** | **nothing answered — no route at all** |

Refused would have meant a firewall or a stopped sshd. Timed out means the packets never
arrived, so no amount of PC-side configuration changes it.

**Consequence: Tailscale stops being the convenient option and becomes the only one.** It
builds an encrypted path between two machines that cannot otherwise see each other, which is
exactly the problem here.

## ASK 2.1 — Tailscale on the Mac (Viraj, own Terminal)

`brew` needs a password prompt Claude's shell cannot provide, so this one has to be typed:

```bash
brew install --cask tailscale
```

Then open Tailscale from Applications and sign in with **GitHub or Google**. That creates
Viraj's own tailnet — free, no card. It does **not** touch the PC, and it is not the
forbidden action: the rule is *never `tailscale up` as Viraj on the PC*, because one
`tailscaled` holds one account and that would replace Shaili's login.

### REPLY 2.1 — done 2026-08-13

```
# runnable: /Applications/Tailscale.app/Contents/MacOS/Tailscale status
100.127.153.97  virajs-macbook-air  virajvaghasia@  macOS  -

account : virajvaghasia@github
tailnet : tail867c8e.ts.net
peers   : 0
```

`peers: 0` is correct, not a fault — this tailnet contains one machine. The PC is on
Shaili's tailnet and becomes visible only once she shares it.

**Note the identity: `virajvaghasia@github`, not an email address.** Signing in with GitHub
makes the Tailscale login `<user>@github`. That changes ASK 2.2 below — asking her to paste
"my email" may match nothing.

## ASK 2.2 — the message to Shaili

Node **sharing** hands one machine across tailnets. Her login, her tailnet and her config
stay exactly as they are, and she can unshare whenever she likes — nothing to revert later,
which is the point.

**Use the share link, not the email field.** A GitHub sign-in gives the identity
`virajvaghasia@github`; the link avoids having to match that at all, and it is fewer steps
for her.

> Hi — could you share the lab desktop with me on Tailscale? In the Tailscale admin console
> → **Machines** → `kj-xps-8950` → the **⋯** menu → **Share** → **Copy share link**, and
> send me the link.
>
> It only lets me SSH to that one machine. It does not add me to your tailnet, does not
> change anything on the PC, and you can unshare it any time. I need it because the lab is
> on `10.25.x` and my laptop is on `10.23.x`, so they cannot reach each other directly.

Viraj then opens that link while signed in to Tailscale and accepts. The machine appears in
his machine list as a shared node.

### REPLY 2.2

```
# 2026-08-13 lab PC: Viraj does NOT have Shaili's Tailscale credentials.
# Did not open the admin console. Did not tailscale up/login/switch.
# Message to send her (copy-paste):

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

## Then — no further PC work needed

Once the node is shared, the Mac gets `100.72.117.53` and Claude runs the `ssh` test and
writes `~/.ssh/config`. **The PC side is already done**, so Day 3 closes on the Mac apart
from the reboot test, which stays deferred ~20 days.

---

# Round 3 — run these on the lab PC

**Status: 3.1 REPLIED 2026-08-13 (lab PC). 3.2 waits on Shaili. 3.3 after she shares.**

Round 2 is a browser action, so it could not be handed over as a command. These are the
parts that *can* be, plus the one line that opens the right page.

**Before anything: the share is Shaili's to grant.** Her admin console, her account. If she
has said go ahead, run these. If not, ASK 3.2 waits — the rest do not.

## ASK 3.1 — what Tailscale on this PC currently is

```bash
tailscale status | head -5
tailscale ip -4
tailscale status --json | grep -m1 '"LoginName"'
```

Confirms three things before anything is changed: that `tailscaled` is up, the address the
Mac will eventually target, and **which account holds it**. If `LoginName` shows anyone other
than Shaili, stop and say so — something has already replaced her login and that is a bigger
problem than the tunnel.

### REPLY 3.1

```
100.72.117.53   kj-xps-8950  shaili.gandhi@  linux    -                          
100.80.115.127  cam          shaili.gandhi@  linux    -                          
100.109.134.31  shaili       shaili.gandhi@  windows  offline, last seen 2h ago  
100.72.117.53
      "LoginName": "shaili.gandhi@gmail.com",
```

## ASK 3.2 — open the console and share the node

```bash
xdg-open https://login.tailscale.com/admin/machines
```

Then, in the browser: find **`kj-xps-8950`** → the **⋯** menu on its row → **Share** →
**Copy share link**.

There is no CLI for this — node sharing exists only in the admin console and the HTTP API,
and the API needs a key that would itself have to be generated from the console. So the
browser is the shortest honest path.

Paste the link into REPLY 3.2 and open it on the **Mac** while signed in as
`virajvaghasia@github`.

**Do not** run `tailscale up`, `tailscale login` or `tailscale switch` on this PC. One
`tailscaled` holds one account; any of those replaces Shaili's login, which is the same class
of mistake as signing into her Claude or committing under her git identity.

Viraj has **no Tailscale password for Shaili.** ASK 3.2 is **her** browser, not his.
He sends the message in REPLY 2.2 / `study/08-LAB.md` §L.2 and waits for the link.

### REPLY 3.2

```
(paste the share link here — it is a one-time invite URL, safe to expire, but delete this
line once accepted since the repo is public)
```

## ASK 3.3 — after the share, confirm from this side

```bash
tailscale status
```

Once the Mac has accepted, `virajs-macbook-air` should appear in this list as a shared peer.
If it does not, the link was not accepted yet — that is a Mac-side step, not a PC one.

### REPLY 3.3

```
(paste here)
```

---

## What Claude does next

Nothing else is needed from the PC. With the share accepted, the Mac reaches
`100.72.117.53` and Claude runs:

```bash
ssh -i ~/.ssh/id_ed25519_sqlalchemy_lab shaili@100.72.117.53 'whoami; hostname'
```

then writes `~/.ssh/config` so it becomes `ssh sqlalchemy-lab`. Day 3 closes apart from the
reboot test, deferred ~20 days.

---

# Round 4 — Phase 1 has started, and this PC is the GPU half

> **PARKED 2026-08-14 — the 3060 is in use by its other user for ~2 days.**
> Nothing below is urgent. Run it when the machine is free again; ASK 4.1 is a few minutes and
> ASK 4.2 is two commands, so the round stays cheap whenever it happens.
>
> **This did not stall Phase 1.** Step 2 (chunking) needs no accelerator, and the outage
> prompted measuring the Mac, which had never been examined: Apple M4, 10 cores, 16 GiB
> unified memory, Docker 29.2.0. Steps 3–4 are being built to take the device as a **flag**
> rather than assuming this box — see `study/09-DECISIONS.md` **D27**, weakened that day.
>
> **ASK 4.2 still matters and is not superseded.** Whatever the Mac turns out to do, the
> question *"does BGE-M3 fit alongside a loaded generator on 12288 MiB of dedicated VRAM"* is
> a different question from what unified memory does, and it is the one that decides whether
> this box can serve both models at once.

**Nothing here is blocked on Tailscale.** Round 3 is still open — Shaili has not shared
`kj-xps-8950` yet — but every command below is run *at* the PC (AnyDesk or the desk itself),
so none of it waits on the tunnel.

## What changed on the Mac side

Phase 1 Step 1 is done. The retrieval corpus is decided and fetched: 270 `.rst` files,
4058424 bytes, from the two pinned SQLAlchemy release tags. The reasoning is in
`phases/PHASE-1.md` Step 1; the decision register entry is `study/09-DECISIONS.md` **D07–D13**.

**The corpus is not in git.** `corpus/raw/` is gitignored on purpose — a script rebuilds it and
a 4.5 MB blob in a repo cannot be verified (`D11`). Only `corpus/MANIFEST.json` is committed,
which is why ASK 4.1 exists: this PC has to build its own copy.

## Where the work splits, and why this PC gets the heavy half

| step | machine | why |
|---|---|---|
| 1. decide + fetch corpus | Mac | text processing, no GPU. **Done.** |
| 2. chunk | Mac | pure text, re-runs in seconds |
| 3. embed the corpus | **this PC** | thousands of passages; the 3060 is the only GPU |
| 3. Qdrant | **this PC** | the vectors live where the database lives |
| 4. Ollama, answer generation | **this PC** | already installed and measured at 62.23 tok/s |

**The reason embedding runs here rather than on the Mac** is not only speed. The vectors are
the one artifact that is both large and regenerable, and moving them across a link that does
not yet exist would be the worst of both. Qdrant lives next to Ollama; the embedder feeds
Qdrant; so the embedder lives here too.

## ASK 4.1 — build the corpus on this box

```bash
cd ~/Documents/Workspace/SqlUpgradeAgent
git status -sb          # this clone was left on phase-0/repo-structure, not main
git checkout main
git pull
uv sync --frozen
uv run python -m rag.corpus
```

That `git checkout main` is not boilerplate. This clone was left on
`phase-0/repo-structure` after the 2026-08-13 sitting, and `rag/` does not exist on that
branch — a bare `git pull` would report success and then `python -m rag.corpus` would fail
with `No module named rag`, which reads like a broken script rather than a wrong branch.

Expected: two tarballs fetched from GitHub (about 9 MB total), then a report ending

```
  TOTAL        270 files   4058424 bytes
```

**If those numbers differ on Linux, that is a real finding, not a nuisance** — it would mean
the fetcher is not platform-independent, and the Mac's manifest and this PC's would disagree
about what the corpus is. Paste whatever it actually prints.

Then verify nothing was corrupted in transit:

```bash
uv run python -m rag.corpus --check
```

Expected: `all 270 files match the manifest`. This re-hashes every file against the SHA-256
recorded on the Mac, so a match means both machines hold byte-identical corpora.

### REPLY 4.1

```
(paste here)
```

## ASK 4.2 — how much VRAM is actually free

This settles an open decision rather than being a status check. `study/09-DECISIONS.md` **D32**
records that BGE-M3 was chosen as the embedding model with **no measurement behind it**, and the
fact that decides whether it is usable is how much VRAM is left with the generator loaded.

```bash
nvidia-smi --query-gpu=memory.total,memory.used,memory.free --format=csv
ollama ps
```

Run it **twice**: once cold, and once right after `ollama run qwen2.5-coder:7b` has answered
something, so the model is resident. The second number is the real budget — the embedder has to
fit alongside a loaded generator, or one of them has to be unloaded between phases, which is an
architectural consequence and not a tuning detail.

Phase 0 measured **7115 MiB** free with the model loaded, out of **12288 MiB** total. Confirming
or contradicting that is the point.

### REPLY 4.2

```
(paste here)
```

## What is NOT being asked

- **No Tailscale commands.** Round 3's rule stands: one `tailscaled` holds one account, and
  `up` / `login` / `switch` would replace Shaili's login.
- **No `~/.claude`, no `claude` TUI, no `/login`.**
- **No Docker or Qdrant work yet.** Qdrant arrives in Step 3, once chunking is done on the Mac
  and there is something to store. Starting a container now would just be a container.

## What Claude does next

Step 2, chunking, runs entirely on the Mac and needs nothing from this PC. Step 3 opens with the
number from REPLY 4.2, because if BGE-M3 does not fit in the free VRAM the model choice changes
before any embedding is run rather than after.

---

# Round 5 — embed on the 3060

Everything below is on `main` as of 2026-08-14. Round 4's ASK 4.1 is superseded by ASK 5.1,
which does the same thing plus the rest of the pipeline.

## Read this before starting: the 10 minutes is not the whole job

The embedding run itself took **627 seconds on the Mac** — about ten minutes. On a fresh clone
this machine also has to download the toolchain and the model first:

| step | roughly | why |
|---|---|---|
| `uv sync --extra embed` | **several GB** | torch built for CUDA is much larger than the Mac's build |
| BGE-M3 download | ~2.2 GB | cached afterwards, so only the first run pays it |
| corpus fetch | ~9 MB | two tarballs from GitHub |
| the actual embed | ~10 min on the Mac, unknown here | the only part that uses the GPU |

**Budget 30–45 minutes for the first run**, mostly network. Every run after that is the ten
minutes.

**The 3060 is in use by its other user until roughly 2026-08-16.** None of ASK 5.1 needs the
GPU — it is downloads and CPU text processing — so it can be done early, leaving only ASK 5.2
for when the card is free.

## ASK 5.1 — set up and rebuild the inputs

```bash
cd ~/Documents/Workspace/SqlUpgradeAgent
git status -sb          # this clone was left on phase-0/repo-structure, not main
git checkout main
git pull

uv sync --extra embed   # the big one: torch + CUDA. Several GB.

uv run python -m rag.corpus     # fetches the 270 .rst files. Not in git (D11).
uv run python -m rag.chunk      # regenerates chunks.jsonl. Also not in git.
```

**What to check, and it is a real portability test.** The Mac produced these:

```
  TOTAL        270 files   4058424 bytes
  3284 chunks   3946041 chars
```

**If Linux produces different numbers, that is a finding, not a nuisance** — it would mean the
chunker is platform-dependent, and the two machines would be embedding different text while
believing they agree. Paste whatever it actually prints.

### REPLY 5.1

```
# lab PC, 2026-08-17, already on main @ 79db576 (pulled this sitting)

# uv sync --extra embed  (torch 2.13.0 + CUDA 13, sentence-transformers 5.7.0, qdrant-client 1.19.0)

===== CORPUS =====
corpus on disk does not match the manifest — refetching
fetching rel_1_4_52 ...
fetching rel_2_0_51 ...
corpus manifest: corpus/MANIFEST.json
  rel_1_4_52   126 files   1903934 bytes   https://github.com/sqlalchemy/sqlalchemy/archive/refs/tags/rel_1_4_52.tar.gz
  rel_2_0_51   144 files   2154490 bytes   https://github.com/sqlalchemy/sqlalchemy/archive/refs/tags/rel_2_0_51.tar.gz
  TOTAL        270 files   4058424 bytes
  by top-level directory:
    orm           157 files   2109455 bytes
    core           66 files    884110 bytes
    tutorial       24 files    446017 bytes
    (root)          4 files    282520 bytes
    faq            18 files    243125 bytes
    changelog       1 files     93197 bytes

===== CORPUS CHECK =====
all 270 files match the manifest

===== CHUNK =====
chunks: corpus/chunks.jsonl
  target=1800  hard_max=2400  overlap_max=400
  3284 chunks   3946041 chars
    1.4.52    1541 chunks
    2.0.51    1743 chunks
  with a code block: 2461   over hard_max: 34
  size  min=120  median=1299  p75=1601  p90=1740  p99=2451  max=5346

# Linux matches the Mac: 270 files / 4058424 bytes, 3284 chunks / 3946041 chars.
```

## ASK 5.2 — embed, and sweep the batch size

Needs the GPU.

```bash
# a short run first, to confirm CUDA is actually being used
uv run python -m rag.embed --limit 256 --device cuda --batch-size 8

# then the batch sweep — see the note below for why this matters here
for b in 8 32 64 128; do
    uv run python -m rag.embed --limit 256 --device cuda --batch-size $b 2>&1 | grep -E '^encode'
done

# then the full run at whichever batch size won
uv run python -m rag.embed --device cuda --batch-size <best>
```

**Why sweep again rather than reuse the Mac's answer.** On Metal, bigger batches were *slower*
— 64 gave 3.6 chunks/s against 7.4 at batch 4. That is a Metal result and there is no reason to
expect it on CUDA, where larger batches usually win. **Copying the Mac's batch size to this
machine would be exactly the kind of unmeasured assumption this repo keeps removing.** The sweep
goes higher here (128) for the same reason.

**The vectors will be compatible with the Mac's**, because `MODEL_REVISION` is pinned to
`5617a9f61b028005a4858fdac845db406aefb181`, `NORMALIZE` is `True` and the dtype is float32. If
this run reports a different revision, **stop** — something is unpinned, and that is a bug
rather than a result (`study/09-DECISIONS.md` D37).

### REPLY 5.2

```
# lab PC, 2026-08-17, RTX 3060 / CUDA. Revision matched the pin — did not stop.

===== SMOKE  --limit 256 --device cuda --batch-size 8 =====
model    BAAI/bge-m3  revision=5617a9f61b028005a4858fdac845db406aefb181
device   cuda   batch_size=8   max_seq_length=2048
chunks   256   307151 chars
loaded in 82.2s
tokens   max=1121  mean=339  truncated=0

--limit run: EMBED_STATS.json left alone

vectors  256 x 1024  float32  -> corpus/embeddings.npy
encode   12.9s   19.9 chunks/s
memory   torch_peak_mib = 2571.1
memory   process_peak_rss_mib = 4342.6

===== BATCH SWEEP  --limit 256 =====
--- batch 8 ---
model    BAAI/bge-m3  revision=5617a9f61b028005a4858fdac845db406aefb181
device   cuda   batch_size=8   max_seq_length=2048
encode   13.2s   19.4 chunks/s
memory   torch_peak_mib = 2571.1
memory   process_peak_rss_mib = 3405.6
--- batch 32 ---
model    BAAI/bge-m3  revision=5617a9f61b028005a4858fdac845db406aefb181
device   cuda   batch_size=32   max_seq_length=2048
encode   16.2s   15.8 chunks/s
memory   torch_peak_mib = 3754.3
memory   process_peak_rss_mib = 3402.5
--- batch 64 ---
model    BAAI/bge-m3  revision=5617a9f61b028005a4858fdac845db406aefb181
device   cuda   batch_size=64   max_seq_length=2048
encode   20.7s   12.4 chunks/s
memory   torch_peak_mib = 5336.6
memory   process_peak_rss_mib = 3403.8
--- batch 128 ---
model    BAAI/bge-m3  revision=5617a9f61b028005a4858fdac845db406aefb181
device   cuda   batch_size=128   max_seq_length=2048
encode   35.3s   7.3 chunks/s
memory   torch_peak_mib = 8496.4
memory   process_peak_rss_mib = 3402.5

# Winner is batch 8 (19.4 chunks/s). Larger batches were slower on CUDA too,
# same direction as Metal, not the "CUDA larger-wins" expectation. Full run
# used --batch-size 8.

===== FULL  --device cuda --batch-size 8 =====
model    BAAI/bge-m3  revision=5617a9f61b028005a4858fdac845db406aefb181
device   cuda   batch_size=8   max_seq_length=2048
chunks   3284   4229821 chars
loaded in 4.5s
tokens   max=1586  mean=363  truncated=0
vectors  3284 x 1024  float32  -> corpus/embeddings.npy
encode   165.7s   19.8 chunks/s
memory   torch_peak_mib = 2739.5
memory   process_peak_rss_mib = 3415.4

# Mac was 627.1s / 5.2 chunks/s on mps. This box is ~3.8× that encode rate.
# corpus/EMBED_STATS.json was NOT committed; Mac file restored in the tree.
# PC stats (not in git):
#   device cuda, batch_size 8, load 4.5s, encode 165.7s, 19.8 chunks/s,
#   torch_peak_mib 2739.5, process_peak_rss_mib 3415.4, complete true
```

## ASK 5.3 — VRAM with both models loaded

This is Round 4's ASK 4.2, unchanged and still not answered. It decides whether this machine can
serve retrieval and generation at the same time.

```bash
# with nothing loaded
nvidia-smi --query-gpu=memory.total,memory.used,memory.free --format=csv

# then load the generator and ask it something, so it is resident
ollama run qwen2.5-coder:7b "say hi" >/dev/null
ollama ps
nvidia-smi --query-gpu=memory.total,memory.used,memory.free --format=csv

# then run the embedder WHILE the generator is loaded, and watch
uv run python -m rag.embed --limit 256 --device cuda --batch-size 32
nvidia-smi --query-gpu=memory.total,memory.used,memory.free --format=csv
```

Phase 0 measured **7115 MiB** free of **12288** with `qwen2.5-coder:7b` resident. BGE-M3 wanted
about **2166 MiB** of torch allocation on the Mac. If both fit here, retrieval and generation can
coexist; if not, every query has to unload one to load the other, which is an architectural
consequence rather than a tuning detail.

### REPLY 5.3

```
# lab PC, 2026-08-17. Both fit. Retrieval and generation can coexist.

===== cold (nothing loaded) =====
memory.total [MiB], memory.used [MiB], memory.free [MiB]
12288 MiB, 597 MiB, 11307 MiB

===== after ollama run qwen2.5-coder:7b "say hi" =====
NAME                ID              SIZE      PROCESSOR    CONTEXT    UNTIL
qwen2.5-coder:7b    dae161e27b0e    4.7 GB    100% GPU     4096       4 minutes from now

memory.total [MiB], memory.used [MiB], memory.free [MiB]
12288 MiB, 5246 MiB, 6658 MiB

===== embed --limit 256 --device cuda --batch-size 32  WHILE generator resident =====
model    BAAI/bge-m3  revision=5617a9f61b028005a4858fdac845db406aefb181
device   cuda   batch_size=32   max_seq_length=2048
chunks   256   307151 chars
loaded in 4.0s
tokens   max=1121  mean=339  truncated=0

--limit run: EMBED_STATS.json left alone

vectors  256 x 1024  float32  -> corpus/embeddings.npy
encode   15.9s   16.1 chunks/s
memory   torch_peak_mib = 3754.3
memory   process_peak_rss_mib = 3403.4

===== after both (embed process has exited; generator still resident) =====
memory.total [MiB], memory.used [MiB], memory.free [MiB]
12288 MiB, 5234 MiB, 6670 MiB

NAME                ID              SIZE      PROCESSOR    CONTEXT    UNTIL
qwen2.5-coder:7b    dae161e27b0e    4.7 GB    100% GPU     4096       4 minutes from now

# No OOM. Generator ~5246 MiB resident; embedder torch peak 3754 MiB at batch 32.
# Together that is ~9 GiB of 12 GiB — they fit. After the embed process exits,
# nvidia-smi returns to generator-only, so the two do not stay stacked unless
# both processes are alive.

# Operational: --limit overwrites corpus/embeddings.npy. After this test the
# file was (256, 1024). Full embed was re-run at batch 8 to restore (3284, 1024)
# before rag.index. Mac EMBED_STATS.json restored; not committed from this PC.
```

## What is still NOT being asked

- **No Tailscale commands.** Round 3's rule stands: one `tailscaled` holds one account.
- **No `~/.claude`, no `claude` TUI, no `/login`.**
- **Do not commit anything from that machine yet.** `corpus/EMBED_STATS.json` is committed and
  currently describes the Mac's run; a second run would overwrite it. Paste the numbers into the
  REPLY blocks and they get recorded from here, so both machines' results survive instead of one
  silently replacing the other.

---

# Round 6 — settle D43's A cell, which the Mac cannot

**Independent of Round 5.** Round 5 embeds; this generates. It needs Ollama and a populated
Qdrant, both of which Round 5's steps leave behind, so run it after — but nothing here touches
the embedding pipeline.

**Why the Mac cannot do it.** `study/09-DECISIONS.md` **D43** recorded that a strictly worded
refusal clause (prompt **A**) made the model refuse a question whose answer was in its own
prompt. Re-run twice on the Mac on 2026-08-16 it **answered both times**, so that claim now
stands at **1 observation in 3** — too few to call a mechanism, too few to call noise. Each run
of `rag/compare_prompts.py` is six generations. The Mac does **18.4 tok/s**; this box measured
**62.23 tok/s**, so ten runs here is one sitting rather than an evening.

**What is not in question.** Prompt **B** — the shipped one — has been correct in every cell of
every run so far, and nothing this round can find would make **A** or **C** preferable. This
settles how confidently `D43` may be *quoted*, not what the system ships.

## ASK 6.1 — ten runs, and the tally

```bash
cd ~/Documents/Workspace/SqlUpgradeAgent
ls rag/compare_prompts.py          # landed in PR #18; if this fails, `git pull` on main first

for i in $(seq 1 10); do
  echo "--- run $i ---"
  uv run python -m rag.compare_prompts 2>/dev/null | grep -E '^[ABC] '
done | tee /tmp/d43-ten-runs.txt

echo
echo "A cell, answerable column:"
grep '^A ' /tmp/d43-ten-runs.txt | awk '{print $2}' | sort | uniq -c
```

**How to read the tally, so the paste is not just numbers.** The field after `A` is the
**answerable** column. `answered` there is correct; `refused` is the over-fire being counted.
Ten runs plus the existing three gives thirteen observations.

- **`refused` zero or once in ten** — `D43`'s original was probably noise. §R3.3 stops saying
  "1 of 3" and says so outright.
- **`refused` several times in ten** — a real intermittent mechanism, and the interesting
  question becomes what makes it fire.

**Do not stop early because the first few look boring.** That is the same `n=1` mistake in a new
costume, and this round exists to correct exactly that.

### REPLY 6.1

```
# lab PC, 2026-08-17. Qdrant v1.19.0 healthy; indexed first:

created collection sqlalchemy-upgrade-agent-bge-m3-5617a9f6  dim=1024  distance=COSINE
points in Qdrant: 3284   vectors on disk: 3284
counts match

# ollama: qwen2.5-coder:7b still resident from ASK 5.3. Ten runs, did not stop early.

rag/compare_prompts.py
--- run 1 ---
A        answered  ok   refused  ok
B        answered  ok   refused  ok
C        answered  ok   answered  X
--- run 2 ---
A        answered  ok   refused  ok
B        answered  ok   refused  ok
C        answered  ok   answered  X
--- run 3 ---
A        answered  ok   refused  ok
B        answered  ok   refused  ok
C        answered  ok   answered  X
--- run 4 ---
A        answered  ok   refused  ok
B        answered  ok   refused  ok
C        answered  ok   answered  X
--- run 5 ---
A        answered  ok   refused  ok
B        answered  ok   refused  ok
C        answered  ok   answered  X
--- run 6 ---
A        answered  ok   refused  ok
B        answered  ok   refused  ok
C        answered  ok   answered  X
--- run 7 ---
A        answered  ok   refused  ok
B        answered  ok   refused  ok
C        answered  ok   answered  X
--- run 8 ---
A        answered  ok   refused  ok
B        answered  ok   refused  ok
C        answered  ok   answered  X
--- run 9 ---
A        answered  ok   refused  ok
B        answered  ok   refused  ok
C        answered  ok   answered  X
--- run 10 ---
A        answered  ok   refused  ok
B        answered  ok   refused  ok
C        answered  ok   answered  X

A cell, answerable column:
     10 answered

# Prompt A refused the answerable question 0/10 on this box.
# B was correct in every cell of every run. C always answered the unanswerable
# question (10/10 `answered  X`), which is the known C failure mode, not D43.
```

## What Claude does with it

Rewrites §R3.3's asymmetry table in `study/11-GENERATION.md` and the ⚠️ block in `D43`.
Thirteen observations is still not a benchmark and the write-up will keep saying so — but it is
the difference between "did not reproduce twice" and a proportion.


---

# Round 7 — does raising k fix failures Phase 3 was going to fix?

**Rounds 5 and 6 are closed.** Their replies are on `main` and folded into `D43` (settled at 1
refusal in 13), `D48` (embed 2.8x, and the batch prediction was wrong), `D49` (both models fit on
one card). **The `lab/handoff` branch is deleted** — it predated the whole `rag/` package and
everything is on `main` now. Work from `main`.

**Why this round exists.** Closing the 19 verdicts produced a number nobody was looking for. For
each question the rank of the first chunk actually containing the answer, measured on the Mac:

```
# summary of: rank of the first containing chunk, out of 3284, for the questions that failed
symbol             in corpus   rank   what that means
backref                   80      6   MISSED THE CUT BY ONE PLACE
cascade_backrefs          12      8   just outside
keys()                     7     12   squarely a reranking case
table_names                6     23   and its top-5 scored +0.001 over noise
has_table                  0   none   the ceiling — no k helps
```

**`DEFAULT_K = 5`. One answer sat at rank 6.** Before Phase 3 buys hybrid search and reranking to
fix these, it is worth knowing how many of them a single integer fixes. That is a cheap question
with an embarrassing possible answer, which is exactly the kind worth asking first.

`rag/probe.py` now takes `--k`. **A non-default k prints and does not write `FAILURES.md`** —
overwriting it would replace 19 human verdicts with answers nobody judged.

## ASK 7.1 — sweep k, and count what changes

```bash
cd ~/Documents/Workspace/SqlUpgradeAgent
git fetch origin && git checkout main && git pull
ls rag/compare_prompts.py && grep -c 'limit=k' rag/probe.py     # both must be present

docker compose up -d qdrant && docker compose ps
ollama list | head -3

for k in 5 6 10; do
  echo "===== k=$k ====="
  uv run python -m rag.probe --k $k 2>&1 | tail -25
done
```

**19 generations per value, three values.** At 62.23 tok/s that is a sitting, not an evening —
this is the round that needs the GPU.

### REPLY 7.1

```
# lab PC, 2026-08-17 evening. On main @ fc438f5.
# grep -c 'limit=k' rag/probe.py → 1
# Qdrant healthy, collection sqlalchemy-upgrade-agent-bge-m3-5617a9f6, 3284 points.
# ollama: qwen2.5-coder:7b  4.7 GB

===== k=5 =====
wrote deliverables/FAILURES.md
{
  "refused": 8,
  "uncited": 4,
  "version_mixed": 13,
  "symbol_missing": 6,
  "single_source": 6,
  "retrieval_failure": 5,
  "ceiling": 1,
  "any_duplicate_slot": 2,
  "total_duplicate_slots": 2,
  "questions": 19
}

===== k=6 =====
k=6 (default 5) — report NOT written
{
  "refused": 8,
  "uncited": 2,
  "version_mixed": 17,
  "symbol_missing": 5,
  "single_source": 7,
  "retrieval_failure": 4,
  "ceiling": 1,
  "any_duplicate_slot": 2,
  "total_duplicate_slots": 2,
  "questions": 19
}

===== k=10 =====
k=10 (default 5) — report NOT written
{
  "refused": 8,
  "uncited": 5,
  "version_mixed": 19,
  "symbol_missing": 4,
  "single_source": 2,
  "retrieval_failure": 3,
  "ceiling": 1,
  "any_duplicate_slot": 7,
  "total_duplicate_slots": 8,
  "questions": 19
}

# refused is 8 at k=5, 8 at k=6, 8 at k=10. Unchanged.
# retrieval_failure 5 → 4 → 3 and symbol_missing 6 → 5 → 4 did move.
# ceiling stayed 1.

# Guard: --k 5 IS the default, so it wrote FAILURES.md. --k 6 and --k 10 did not.
# File was restored from a pre-sweep copy; sha256 matches HEAD. verdicts.json untouched.

===== caveat: backref question, --k 10 --retrieval-only =====
# substring 'backref' in hit text/heading, measured, not read off the 180-char snippet:
#   k=5:  NONE of 5
#   k=6:  rank 6
#   k=10: ranks 6, 7, 8
# Rank 6 is glossary.rst "many to one" (2.0.51). Rank 8 is 1.4 One To Many.

===== same question, full generate --k 10 =====
The sources do not answer this.
[qwen2.5-coder:7b  8 tokens  62.7 tok/s  0.4s wall  prompt 3918 tokens]

# The chunk is in the prompt at k=10 and the model still refused.
# Raising k did not fix this refusal. Hybrid search would not have either,
# for this question — the sources reached the model and it declined anyway.
```

## What to look at in the output, so the paste is not just JSON

The summary counts `refused`, `symbol_missing`, `retrieval_failure` and `ceiling`. Compare across
the three runs:

- **`refused` drops from k=5 to k=6** — then one answer was being refused purely because the cut
  fell one place too high, and `DEFAULT_K` is a one-line fix for it.
- **`refused` unchanged at k=6 but lower at k=10** — the cut matters, just not by one; and the
  cost is a prompt twice the size, which is a real trade rather than a free win.
- **`refused` unchanged at k=10** — then these are genuine retrieval failures, Phase 3's hybrid
  search is the answer, and this round has strengthened that argument rather than undermined it.

**All three outcomes are worth having.** The third is the one that makes Phase 3 defensible
instead of assumed, and it is the reason to run this before building anything.

**One caveat that decides whether a null result means anything.** `k` controls what reaches the
**prompt**; these failures are **refusals**, which is a *generation* behaviour. So raising `k`
only helps if handing the model the right chunk stops it refusing. That is plausible — §R3 is
about exactly that clause — but it is not guaranteed.

**So if `refused` does not drop even at k=10, the result is ambiguous**: either retrieval
genuinely failed, or retrieval succeeded and the model refused anyway. Those need opposite fixes.
To tell them apart, add one run that prints the sources rather than the counts:

```bash
uv run python -m rag.ask "why would an object assigned to a many-to-one relationship never be inserted?" --k 10 --retrieval-only
```

**That is the `backref` question, whose answer ranked 6.** At `--k 10` a chunk containing
`backref` must appear in the list. **If it does and the full run still refuses, the problem is the
prompt, not retrieval** — and Phase 3's hybrid search would not have fixed it either.

**Do not commit from that machine** and do not let a `--k` run near `FAILURES.md` — the guard
should prevent it, and if it does not, that is a bug worth reporting in the reply.

---

# Round 8 — is the refusal clause the reason, or the model?

**Round 7 answered its own question and asked a better one.** Raising `k` moved retrieval
(`symbol_missing` 6→4, `retrieval_failure` 5→3) and left **`refused` at 8 for every value of k**.
The `--retrieval-only` check confirmed the `backref` answer was in the prompt at k=10 and the
model refused anyway. **The sources arrive and generation declines** (`09-DECISIONS.md` **D51**).

**So the suspect is the prompt, and there is a specific reason to think so.** `D43` chose the
shipped wording — prompt **B** — by testing three variants against **two** questions. Prompt
**C**, the same model with the refusal clause deleted, answered everything. So the model *can*
answer these; it is being told when not to.

**B has never been measured at this size.** It is now known to refuse 8 of 19 with at least one
answer demonstrably present. This round runs all three wordings over the whole probe set and
counts refusals — the experiment `D43` should have been, at the size that would have caught it.

**Why this before Phase 3 and before any model change.** Hybrid search would surface a chunk that
is already being surfaced. A bigger model invalidates `D43`, `D48`, `D49` and every generation
number in the repo. **This is the cheapest live hypothesis and the only one with evidence behind
it.**

## ASK 8.1 — all three wordings, all 19 questions

```bash
cd ~/Documents/Workspace/SqlUpgradeAgent
git fetch origin
git checkout phase-1/completion && git pull    # NOT main — see the note below
grep -c 'def sweep_all' rag/compare_prompts.py      # must be 1

docker compose up -d qdrant && ollama list | head -3

uv run python -m rag.compare_prompts --all 2>&1 | tail -30
```

> **Which branch, and why it changed.** Everything for the rest of Phase 1 lands on
> **`phase-1/completion`**, not `main`. It is pushed and pulled directly, and merges to `main`
> **once**, when Phase 1 is complete. A PR per change was costing more ceremony than the changes
> were worth.
> **So `main` will go stale during Phase 1, deliberately.** Check out `phase-1/completion` on
> this box and stay on it. This is not the `lab/handoff` mistake repeating: that branch was
> *abandoned* and predated the `rag/` package, whereas this one is the only place work is
> happening and is current by definition.

**57 generations.** Counts only — no answers printed, because 57 answers is not readable and the
question is a rate. `--all` never writes `FAILURES.md`.

### REPLY 8.1

```
# lab PC, 2026-08-17. phase-1/completion @ 915cf0d
# grep -c 'def sweep_all' rag/compare_prompts.py → 1
# Qdrant healthy. qwen2.5-coder:7b. --all does not write FAILURES.md (confirmed).

uv run python -m rag.compare_prompts --all
  symbol    A=ans B=ans C=ans  what replaces Query.from_self() in SQLAlchemy
  symbol    A=ans B=ans C=ans  Query.join with aliased=True stopped working,
  symbol    A=ref B=ref C=ans  engine.table_names() is gone — what replaces i
  symbol    A=ref B=ref C=ans  engine.has_table() no longer exists, what is t
  symbol    A=ref B=ref C=ans  row.keys() raises in 2.0, how do I get the col
  symbol    A=ref B=ref C=ans  orm.relation() is not available any more, what
  skew      A=ans B=ans C=ans  should I pass future=True to create_engine?
  skew      A=ans B=ans C=ans  is Session.autocommit still supported?
  skew      A=ans B=ans C=ans  can I still use session.begin() with subtransa
  skew      A=ans B=ans C=ans  does MetaData still accept a bind argument?
  spanning  A=ans B=ans C=ans  how do I migrate select([col1, col2]) to the 2
  spanning  A=ans B=ans C=ans  what is the full set of steps to migrate a 1.4
  spanning  A=ans B=ans C=ans  how do I get scalar values instead of Row obje
  spanning  A=ans B=ans C=ans  why do I need .unique() when using joinedload
  absent    A=ref B=ref C=ans  what is the exact signature and full argument
  absent    A=ans B=ans C=ans  list every keyword argument accepted by relati
  absent    A=ref B=ref C=ans  what does the SQLAlchemy 2.1 release change?
  silent    A=ref B=ref C=ans  if I write comment.issue = issue instead of is
  silent    A=ref B=ref C=ans  why would an object assigned to a many-to-one

prompt    refused  answered   of 19
A               8        11   strict canned refusal
B               8        11   refusal as last resort (SHIPPED)
C               0        19   no refusal clause

A refusal is CORRECT for the 3 `absent` questions and a failure elsewhere,
so the floor is 3 — a variant refusing 3 is not under-refusing, it is right.

# A and B identical: 8 refused. C refused 0.
# First-row outcome in the ASK table: the clause is the story, the model can answer.
# C also answered all 3 absent questions (0 refusals, below the floor of 3).
# Do not ship C — that is the ASK's own warning, not a finding from this box.
```

## How to read it, and the floor that matters

**Three of the 19 are `absent` questions where refusing is CORRECT.** So the floor is 3: a
variant refusing 3 is not under-refusing, it is exactly right. Anything above 3 is a candidate
over-fire.

| result | what it means | what to do |
|---|---|---|
| **B ≈ 8, C ≈ 0–3** | the clause is the whole story — B over-fires at scale, and `D43`'s "not reproducible" was an artefact of testing two questions | rewrite the wording; the model is fine |
| **B ≈ 8, C ≈ 8** | the refusals are **not** the clause — something else declines | then the model becomes a live question for the first time |
| **B ≈ 3, A ≫ 3** | B is already right and Round 7's 8 came from something else in `probe.py`'s path | look at `probe.py`, not the prompt |

**The second row is the only one that puts the model in scope**, and it is worth saying plainly
that it is the least likely: prompt C already answered everything in `D43`, thirteen times.

**If C refuses far fewer than B, do not conclude "ship C".** C is the variant that invented a
full `Session.execute` signature 13 times out of 13. **The goal is a wording that refuses the 3
`absent` questions and nothing else** — this round measures the gap, it does not pick the winner.

---

# Round 9 — a fourth wording, and the first one that is a different mechanism

**Round 8 settled that the search space was one point, not two.** A and B refused the **same 8
questions, identically** (`09-DECISIONS.md` **D52**). `D43` chose between two options that behave
the same. C refuses 0 and fabricates on all three `absent` questions.

**Scored against this repo's own 19 verdicts, B is wrong in 5 places:**

```
correct refusals  Q4 has_table, Q6 relation, Q15, Q17   corpus genuinely has nothing
over-fires        Q3 table_names, Q5 keys(), Q18, Q19   the answer is present
under-fire        Q16                                    an `absent` question it answered
```

**So the floor is 5, not the 3 Round 8 assumed** — Q4 and Q6 are ceilings too. A correct prompt
refuses 5 of these 19.

**Why D is not a tuned B.** A and B both ask the model to judge **sufficiency** — *"do these
sources contain the answer?"* — a binary gate it applies strictly the moment a question names a
specific symbol. Softening the adverbs would produce a third point on the same line. **D removes
the judgement instead:**

- **Partial answers become the expected output** — *"answer with whatever the sources do support,
  even partially, and state plainly which part they do not cover."*
- **Refusal narrows to subject, not sufficiency** — only when *no source is about the subject at
  all*.
- **A refusal must name what was looked for and not found.** Naming forces a check rather than a
  pattern match, and it makes a wrong refusal visible in the output instead of silent.

Everything else is byte-identical across all four, so the comparison stays controlled — a test
pins that.

## ASK 9.1 — all four wordings, all 19 questions

```bash
cd ~/Documents/Workspace/SqlUpgradeAgent
git fetch origin && git checkout phase-1/completion && git pull
uv run python -c "from rag import compare_prompts as c; print(sorted(c.REFUSAL_CLAUSES))"   # A B C D

docker compose up -d qdrant && ollama list | head -3
uv run python -m rag.compare_prompts --all 2>&1 | tail -32
```

**76 generations** — four wordings now, not three.

### REPLY 9.1

```
# lab PC, 2026-08-17. phase-1/completion @ e9d3e88
# sorted(REFUSAL_CLAUSES) → ['A', 'B', 'C', 'D']
# Qdrant healthy. qwen2.5-coder:7b. FAILURES.md not written.

uv run python -m rag.compare_prompts --all
  symbol    A=ans B=ans C=ans D=ans  what replaces Query.from_self() in SQLAlchemy
  symbol    A=ans B=ans C=ans D=ans  Query.join with aliased=True stopped working,
  symbol    A=ref B=ref C=ans D=ref  engine.table_names() is gone — what replaces i
  symbol    A=ref B=ref C=ans D=ref  engine.has_table() no longer exists, what is t
  symbol    A=ref B=ref C=ans D=ref  row.keys() raises in 2.0, how do I get the col
  symbol    A=ref B=ref C=ans D=ref  orm.relation() is not available any more, what
  skew      A=ans B=ans C=ans D=ans  should I pass future=True to create_engine?
  skew      A=ans B=ans C=ans D=ans  is Session.autocommit still supported?
  skew      A=ans B=ans C=ans D=ans  can I still use session.begin() with subtransa
  skew      A=ans B=ans C=ans D=ans  does MetaData still accept a bind argument?
  spanning  A=ans B=ans C=ans D=ans  how do I migrate select([col1, col2]) to the 2
  spanning  A=ans B=ans C=ans D=ans  what is the full set of steps to migrate a 1.4
  spanning  A=ans B=ans C=ans D=ans  how do I get scalar values instead of Row obje
  spanning  A=ans B=ans C=ans D=ans  why do I need .unique() when using joinedload
  absent    A=ref B=ref C=ans D=ref  what is the exact signature and full argument
  absent    A=ans B=ans C=ans D=ref  list every keyword argument accepted by relati
  absent    A=ref B=ref C=ans D=ref  what does the SQLAlchemy 2.1 release change?
  silent    A=ref B=ref C=ans D=ref  if I write comment.issue = issue instead of is
  silent    A=ref B=ref C=ans D=ref  why would an object assigned to a many-to-one

prompt    refused  answered   of 19
A               8        11   strict canned refusal
B               8        11   refusal as last resort (SHIPPED)
C               0        19   no refusal clause
D               9        10   answer partially, refuse only on subject

# D refused 9. Target is Q4, Q6, Q15, Q16, Q17 (five).
# D's nine: Q3 table_names, Q4 has_table, Q5 keys(), Q6 relation,
#           Q15 Session.execute, Q16 relationship(), Q17 2.1,
#           Q18 cascade_backrefs, Q19 backref.
# Right five: all present. Extra four: Q3, Q5, Q18, Q19 — the same over-fires as B.
# D also refused Q16, which A and B answered (B's under-fire).
# Not row 1 (count is 9 not 5). Not row 3 (D is not identical to A/B). Not C.
```

## How to read it

**Target: 5 refusals, and the RIGHT five** — Q4, Q6, Q15, Q16, Q17. The count alone is not
enough; a prompt refusing five of the wrong five is no better than B.

| result | means |
|---|---|
| **D refuses ~5 and they are the right ones** | the mechanism was the problem — ship D, update `D43`/`D52` |
| **D refuses ~5 but the wrong ones** | the count is a coincidence; look at *which* before believing it |
| **D ≈ 8 like A and B** | three wordings now behave identically, and the instruction is not the lever — **then the model is finally in scope** |
| **D ≈ 0 like C** | D collapsed into C; the narrowed refusal was too narrow |

**The third row is the one that would change the project's direction**, and it is why this is
worth running before anything else. Three genuinely different wordings all landing on 8 would
mean the refusals are not coming from the instruction at all.

**Paste the per-question lines, not just the totals.** Which five is the whole question.

---

# Round 10 — the run that separates the prompt from retrieval

**Round 9's result, and the confound in it.** D refused the **right five** plus the same four A
and B refuse. It is wrong in **4** where B is wrong in **5** — it fixed the under-fire, Q16, the
only `absent` question that had been getting a confident answer.

**But Rounds 8 and 9 both ran at `DEFAULT_K = 5`, and the four D did not fix have their answers at
ranks 23, 12, 8 and 6 — all outside the top-5.** In those runs the model was refusing questions
whose answers **were not in its prompt**. That is correct behaviour, not an over-fire, and no
wording could have fixed it.

**Round 7 already showed the other half**: at k=10, the `backref` chunk *is* in the prompt and the
model refuses anyway. So Q18 and Q19 are genuine over-fires at k=10 and correct refusals at k=5,
and no round so far has tested a wording under the condition that makes the difference visible
(`09-DECISIONS.md` **D53**).

**This round is that test.** `--all` now takes `--k`.

## ASK 10.1 — all four wordings at k=5 and k=10

```bash
cd ~/Documents/Workspace/SqlUpgradeAgent
git fetch origin && git checkout phase-1/completion && git pull

for k in 5 10; do
  echo "########## k=$k ##########"
  uv run python -m rag.compare_prompts --all --k $k 2>&1 | tail -30
done
```

**152 generations** — four wordings, 19 questions, two values of k. The longest round yet, and
the only one that can answer the question.

### REPLY 10.1

```
# lab PC, 2026-08-17. phase-1/completion @ 64480e4
# 152 generations. FAILURES.md not written.

########## k=5 ##########
top-k = 5
  symbol    A=ans B=ans C=ans D=ans  what replaces Query.from_self() in SQLAlchemy
  symbol    A=ans B=ans C=ans D=ans  Query.join with aliased=True stopped working,
  symbol    A=ref B=ref C=ans D=ref  engine.table_names() is gone — what replaces i
  symbol    A=ref B=ref C=ans D=ref  engine.has_table() no longer exists, what is t
  symbol    A=ref B=ref C=ans D=ref  row.keys() raises in 2.0, how do I get the col
  symbol    A=ref B=ref C=ans D=ref  orm.relation() is not available any more, what
  skew      A=ans B=ans C=ans D=ans  should I pass future=True to create_engine?
  skew      A=ans B=ans C=ans D=ans  is Session.autocommit still supported?
  skew      A=ans B=ans C=ans D=ans  can I still use session.begin() with subtransa
  skew      A=ans B=ans C=ans D=ans  does MetaData still accept a bind argument?
  spanning  A=ans B=ans C=ans D=ans  how do I migrate select([col1, col2]) to the 2
  spanning  A=ans B=ans C=ans D=ans  what is the full set of steps to migrate a 1.4
  spanning  A=ans B=ans C=ans D=ans  how do I get scalar values instead of Row obje
  spanning  A=ans B=ans C=ans D=ans  why do I need .unique() when using joinedload
  absent    A=ref B=ref C=ans D=ref  what is the exact signature and full argument
  absent    A=ans B=ans C=ans D=ref  list every keyword argument accepted by relati
  absent    A=ref B=ref C=ans D=ref  what does the SQLAlchemy 2.1 release change?
  silent    A=ref B=ref C=ans D=ref  if I write comment.issue = issue instead of is
  silent    A=ref B=ref C=ans D=ref  why would an object assigned to a many-to-one

prompt    refused  answered   of 19
A               8        11   strict canned refusal
B               8        11   refusal as last resort (SHIPPED)
C               0        19   no refusal clause
D               9        10   answer partially, refuse only on subject

########## k=10 ##########
top-k = 10
  symbol    A=ans B=ans C=ans D=ans  what replaces Query.from_self() in SQLAlchemy
  symbol    A=ans B=ans C=ans D=ans  Query.join with aliased=True stopped working,
  symbol    A=ref B=ref C=ans D=ref  engine.table_names() is gone — what replaces i
  symbol    A=ref B=ref C=ans D=ref  engine.has_table() no longer exists, what is t
  symbol    A=ans B=ans C=ans D=ans  row.keys() raises in 2.0, how do I get the col
  symbol    A=ref B=ref C=ans D=ref  orm.relation() is not available any more, what
  skew      A=ans B=ans C=ans D=ans  should I pass future=True to create_engine?
  skew      A=ans B=ans C=ans D=ans  is Session.autocommit still supported?
  skew      A=ans B=ans C=ans D=ans  can I still use session.begin() with subtransa
  skew      A=ans B=ans C=ans D=ans  does MetaData still accept a bind argument?
  spanning  A=ans B=ans C=ans D=ans  how do I migrate select([col1, col2]) to the 2
  spanning  A=ans B=ans C=ans D=ans  what is the full set of steps to migrate a 1.4
  spanning  A=ans B=ans C=ans D=ans  how do I get scalar values instead of Row obje
  spanning  A=ans B=ans C=ans D=ans  why do I need .unique() when using joinedload
  absent    A=ref B=ref C=ans D=ref  what is the exact signature and full argument
  absent    A=ref B=ref C=ans D=ref  list every keyword argument accepted by relati
  absent    A=ref B=ref C=ans D=ref  what does the SQLAlchemy 2.1 release change?
  silent    A=ref B=ref C=ans D=ref  if I write comment.issue = issue instead of is
  silent    A=ref B=ref C=ans D=ref  why would an object assigned to a many-to-one

prompt    refused  answered   of 19
A               8        11   strict canned refusal
B               8        11   refusal as last resort (SHIPPED)
C               0        19   no refusal clause
D               8        11   answer partially, refuse only on subject

# Totals: A 8→8, B 8→8, C 0→0, D 9→8.
# Q18 and Q19 (the ones that enter the prompt at k=10): A, B, D refused at BOTH k.
#   No prompt answered them at k=10 having refused at k=5.
# Q3 table_names (control, rank 23): A/B/D refused at both k. Held.
# Q5 keys() (control, rank 12, should stay refused at k=10): A/B/D refused at k=5
#   and ANSWERED at k=10. C answered both. Per the ASK, that is fabricating.
# Q16: A/B answered at k=5, refused at k=10. D refused both.
```

## How to read it — compare each prompt against ITSELF across the two k values

The comparison that matters is **not** between prompts. It is each prompt at k=5 versus k=10.

| what happens to a prompt's refusals as k goes 5 → 10 | means |
|---|---|
| **drops toward 5** | the refusals were honest — the answer had not been retrieved. **Retrieval is the problem, Phase 3 is the fix, and the prompt is fine.** |
| **stays flat** | the answer arrived and it refused anyway. **The instruction is the problem for that prompt.** |
| **D drops and B stays flat** | D is the fix and it is measurable — ship D, and `D43`/`D52`/`D53` all resolve |

**Q18 and Q19 are the two to watch**, because ranks 8 and 6 mean they enter the prompt at k=10
and not at k=5. **If any prompt answers them at k=10 having refused at k=5, that prompt is
working and the earlier rounds were measuring retrieval all along.**

Q3 (rank 23) and Q5 (rank 12) stay outside the prompt even at k=10 — **they should still be
refused, by every wording, and a prompt that answers them is fabricating.** They are the control.

**Paste both blocks in full.** The per-question lines are the finding; the totals hide it.


---

# Round 11 — run it to a conclusion, not to another round

**Why this one is different.** Rounds 8–10 each ran **one pass per configuration**, and D's whole
advantage over B is **one question, observed once**. That is the `n=1` standard `D43` shipped on
and `D52` had to correct — so `D54` is marked **provisional** until this round.

**`--repeat N` aggregates internally**, so this settles the question in one sitting instead of
five exchanges through this file. It prints per-question refusal counts and stars any cell that
was **not unanimous** across runs — an unstable cell is the finding, because a prompt whose
behaviour flips between identical runs is not a prompt you can reason about.

## ASK 11.1

```bash
cd ~/Documents/Workspace/SqlUpgradeAgent
git fetch origin && git checkout phase-1/completion && git pull

uv run python -m rag.compare_prompts --all --repeat 5 2>&1 | tail -35
```

**380 generations** (4 wordings × 19 questions × 5 runs) at `k=5`. Long, and it ends the argument
rather than extending it. **Do not stop early** — a partial run is another `n=1`.

### REPLY 11.1

```
(paste here)
```

## How to read it

**Look at the starred rows first.** Any question where a prompt refused on some runs and not
others is non-deterministic, and no conclusion drawn from a single pass on that question was ever
valid — including conclusions in `D52`, `D53` and `D54`.

| result | means |
|---|---|
| **no stars, D=5 and B=8** | the margin is real and reproducible — `D54` drops "provisional" |
| **no stars, D and B identical** | D bought nothing; A, B and D are all one option, and `D52` extends to three |
| **Q16 starred** | the single question D's advantage rests on is a coin-flip — **revert to B**, since D would then be churn |
| **many stars** | prompt comparison at this scale is noise-dominated, and every prompt conclusion today needs re-deriving with `--repeat` |

**The last row is the one to hope against and the most useful if true.** It would mean the method
was wrong, not just the answer — and it would be better to learn that now than after Phase 3 is
built on it.
