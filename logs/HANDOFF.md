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

**Status: OPEN.** Everything below is on the **lab PC**.

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
(paste here)
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
(paste here)
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
(paste here)
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
