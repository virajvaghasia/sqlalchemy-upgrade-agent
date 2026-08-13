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
(paste her answer, or note when asked)
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
