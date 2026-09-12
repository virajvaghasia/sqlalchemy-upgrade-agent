# Handoff — Mac ⇄ lab PC

Claude runs on the **Mac** and cannot reach the lab PC: that machine has no inbound
route until `sshd` and a tunnel exist, which is the very thing being set up. AnyDesk is
a GUI, not something Claude can type into.

So this file is the wire. Claude writes **ASK** blocks; Viraj runs them on the PC and
pastes the output into the matching **REPLY** block; Claude reads it on the next pull.

## The lab may edit and commit files — added 2026-09-11

**It is doing the heavy, reproducible work** (`D84`: this box reproduces and the Mac drifts), so it
is not restricted to pasting output. **It edits and commits directly on the working branch, same as
the Mac.** No file is off limits.

**There is no concurrency to manage.** One person, one machine at a time — work happens on the lab
or on the Mac, never both, so two edits cannot race. *(An earlier version of this note carried an
append-don't-restructure rule for the register and the teaching files. That was solving a problem
this setup does not have, and it is withdrawn.)*

**The one rule that is real, because it has already cost this project twice: push before you leave
a machine, pull when you arrive.** Not for merges — for *divergence*. The lab clone once sat many
commits behind on a stale branch, and Round 15 wrote over the Mac's faithfulness rows because the
Mac's copy existed only locally; git had to bring them back (`D83`).

```bash
git pull --ff-only          # arriving
git push                    # leaving — before you walk away, not tomorrow
```

**Artifacts stay machine-suffixed** (`deliverables/*.Linux-x86_64.json`) and the tools refuse to
overwrite another machine's file. That guard is about **not destroying evidence**, not about
merges, and it stays.

**If a lab measurement contradicts a decision, write the correction as a correction.** Round 16
killed the Mac's own hypothesis and that is on the record precisely because it was written up
rather than quietly edited away (`D84`).

## Where things stand — read this first (updated 2026-09-11, lab)

**ROUND 17 CLOSED on the lab.** Tip `6fec996`, branch `phase-5/agent`, Ollama **0.32.9**
(Mac was 0.34.0), generator **100% GPU**. Artifact:
`deliverables/agent-sweep-phase5.Linux-x86_64.json`.

| round | state |
|---|---|
| **18** | **OPEN** — E1 on the lab: does the must-call prompt reproduce? ~25 min |
| **17** | **CLOSED** — Step 0 holds on channel/`--g065`; agent end-to-end **0.02** vs lab baseline **0.42** |
| 1, 12, 13, 14, 15, 16 | **CLOSED** — replies pasted, results folded into `D83` and `D84` |
| 2 / 3 (the Tailscale tunnel) | **OPEN but blocked on Shaili sharing the node.** Nothing currently needs it — AnyDesk is enough |

**Mac gate closed 2026-09-11 (`D86`):** `JUDGE-AGREEMENT.md` filled — **7 of 10 = 70%** agreement
with the local judge. Three DISAGREE: `g080` (too harsh), both `g056` arms (too soft). Nothing
left for the lab.

---

# Round 18 — does the must-call prompt reproduce? (OPEN, ~25 minutes)

**Why.** Round 17.4 found the agent calling **no tool on 96 of 100** questions. The suspect was the
system prompt, and on the Mac the fix works: obligation instead of permission takes no-tool-call
from **9/20 to 2/20**, and out-of-range citations from **3 to 0** — because an agent that retrieves
has real sources to point at.

**Then the same data found something that puts that result behind a rule.** Same 20 items, **same
shipped prompt**, temperature 0:

| | no tool call |
|---|---|
| Mac | 9/20 |
| **lab** | **19/20** |

**Ten of the twenty flip.** Whether a tool gets called **does not reproduce across these machines**
(`D89`). So the Mac's verdict on this candidate is worth exactly what the Mac's verdict on prompt
`H` was — which is why `H` is still held.

## Pass / fail, written before the data

| result on the lab | meaning | next |
|---|---|---|
| candidate takes no-tool-call from ~19/20 down to ~2/20 | the fix reproduces | ship `SYSTEM_MUSTCALL`, re-run 17.4 with it, report both numbers |
| candidate barely moves it | the fix is a **Mac** effect | **do not ship** — `D83`/`D84` applied to my own candidate rather than only to someone else's |
| tool calls rise but `two+` stays 0 | expected; no wording has reached chaining on either box | structural forcing (E2) is next, not more prompting |
| `bad cites` stays above 0 once tools are called | retrieval did **not** fix citation integrity | a bigger finding than the prompt |

## ASK 18.0 — sync

```bash
cd ~/Documents/Workspace/SqlUpgradeAgent
git pull --ff-only && git log -1 --oneline
docker compose up -d qdrant
ollama ps                                  # qwen2.5-coder:7b should be 100% GPU
```

## ASK 18.1 — E1, both arms, one sitting

**The arms alternate within each item**, so a slow drift over the hour lands on both equally. The
Mac's run did not do that and is the weaker design of the two; this is the better one.

```bash
nohup uv run python -u -m rag.agent --e1 --n 20 > /tmp/round18-e1.log 2>&1 &
disown
tail -f /tmp/round18-e1.log
```

Paste the final table in full, then commit the rows:

```bash
git add deliverables/e1-phase5.Linux-x86_64.json
git commit -m "lab: Round 18 — E1 both arms on the 3060" && git push
```

**If it dies partway, just re-run it** — E1 is 40 short runs and has no checkpoint, deliberately:
a half-interleaved comparison is worse than none.

### REPLY 18.0

```
(paste git log -1, ollama ps)
```

### REPLY 18.1

```
(paste the E1 table and the last 10 log lines)
```

### LAB RESULT — Round 17 (Mac: read this)

Measured on the **lab PC** (`kj-XPS-8950`, RTX 3060, tip `6fec996`), qwen at **100% GPU**.

| control | Mac | **Lab Round 17** |
|---|---|---|
| `rag.tools --g065` | exit 0, create_view=False | **same, exit=0** |
| toolcall synth usable | 20/20, content JSON | **20/20, content JSON, tool_calls 0** |
| toolcall golden usable | 100/100, content JSON | **100/100, content JSON, tool_calls 0** |
| gemma `tool_calls` channel | True | **True** (`check_api` / `Query.from_self`) |
| Ollama | 0.34.0 | **0.32.9** — channel result still matches Mac, so **`D87` is a model fact, not a version fact** |

| agent golden (17.4) | lab shipped baseline (D/Round 16) | **Lab Round 17 agent** |
|---|---|---|
| end to end | 38/91 = **0.42** | **2/91 = 0.02** |
| no tool call | — | **96** |
| one tool | — | **4** (`search_docs`×3, `check_api`×1) |
| two or more | — | **0** |
| over-refused / fabricated / failed | — | **0 / 5 / 0** |
| stopped | — | all 100 `answered` |

**Read against the pre-written pass/fail table:** end to end is **materially below 0.42**, and
**`no tool call` is the story** — the model answers from memory despite tools. The two delivered
items (`g002`, `g024`) are exactly the ones that called `search_docs`. That is the phase's finding
for this sitting; do not tune it away on the lab.

---

# Round 17 — does Phase 5's Step 0 hold on the lab? (CLOSED, lab 2026-09-11)

**Why this round exists.** Phase 5 opened on a single measurement: `qwen2.5-coder:7b` emits a
usable tool call **100% of the time** (20/20 synthetic, 100/100 golden), always as JSON in
`message.content` and **never** on the `tool_calls` channel (`D87`). Everything Step 2 will build
stands on that.

**It was taken on the Mac.** `D83` and `D84` say generation does not reproduce across these two
boxes, and that the Mac is the one that drifts. **So the number Phase 5 is standing on is the one
taken on the less reliable machine** — exactly the position that made prompt `H`'s `9↑ 0↓` untrustworthy.

**And there is a second reason, which is not about drift at all.** The Mac runs **Ollama 0.34.0**;
this repo last recorded the lab at **0.32.9** (`study/08-LAB.md`, Day 10). The `tool_calls` channel
is served by the **server's** template handling, not only by the model. **If the lab's older Ollama
lifts the call into `tool_calls`, then `D87`'s constraint is a version fact and not a model fact**,
and Step 2's design changes.

## Pass / fail, written before the data — as in Rounds 14 and 16

| result on the lab | what it means | what happens next |
|---|---|---|
| usable calls **20/20 and 100/100**, all `content_json` | `D87` reproduces, channel is a **model** fact | Step 2 proceeds as planned; `D87` gains a second machine |
| usable calls high, but some/all on **`tool_calls`** | the channel is an **Ollama version** fact | `D87` is narrowed the way `D83` was; Step 2 targets the native channel and the Mac upgrades |
| usable calls **materially below 100%** | `D87` does **not** reproduce | **Step 2 stops.** The agent cannot be built on a rate that holds on one box only |
| `--g065` disagrees with the Mac | a *deterministic* tool disagreed across machines | stop and paste it — that would be a much bigger finding than this round |

**`--g065` is the control.** It runs no model at all — it resolves two symbols in a pinned
interpreter. It **must** match the Mac exactly. If it does not, the problem is the environment and
every other number in this round is suspect.

## ASK 17.0 — sync (note the NEW branch)

```bash
cd ~/Documents/Workspace/SqlUpgradeAgent

git fetch origin
git checkout phase-5/agent          # NEW — Phase 5 branched off phase-2/measure
git pull --ff-only
git log -1 --oneline                # expect 70703aa or newer

uv sync --frozen --extra embed
docker compose up -d qdrant         # only ASK 17.2 needs it
ollama --version                    # RECORD THIS — the Mac is 0.34.0
```

## ASK 17.1 — the deterministic control first

Run this **before** anything that involves the model. It downloads a wheel and resolves two
symbols; no GPU, no Ollama.

```bash
uv run python -m rag.tools --g065; echo "exit=$?"
```

**Expected, exactly:**

```
g065 — the fabricated Alembic script, checked against real alembic (D77)
  OK alembic.operations.Operations.create_table       exists=True  (expected True)
  OK alembic.operations.Operations.create_view        exists=False (expected False)
  Two invented calls beside two working ones — and the tool separates them.
exit=0
```

**If this differs, stop and paste it.** Do not run 17.2 or 17.3 — a deterministic check that
disagrees across machines makes everything after it unreadable.

## ASK 17.2 — the tool-call probe, both sets

```bash
ollama ps                           # after the first call: expect 100% GPU
uv run python -m rag.toolcall            # 20 synthetic, labelled
uv run python -m rag.toolcall --golden   # the 100 real questions, ~5 min
```

**Paste both reports in full**, including the `...on tool_calls` / `...on message.content` lines.
Those two lines are the round.

## ASK 17.3 — the control that says model-or-server

One call, a different model, the identical code path. On the Mac `gemma4:e4b` returns its call on
`tool_calls` first attempt, which is what proved the missing channel belongs to
`qwen2.5-coder:7b` and not to the harness.

```bash
uv run python -c "
from rag import toolcall
r = toolcall.ask('Does Query.from_self still exist in SQLAlchemy 2.0?', model='gemma4:e4b')
print('has tool_calls:', bool((r.get(\"message\") or {}).get(\"tool_calls\")))
print('classify     :', toolcall.classify(r))
"
```

**Expected on the Mac:** `has tool_calls: True`, outcome `tool_calls`.

## ASK 17.4 — the one that needs the lab rather than merely preferring it (~40-60 min)

Everything above is a control. **This is the measurement**, and it is on the lab because `D84`
says this box reproduces and the Mac does not — and because it is 100 agent runs of up to four
generations each, which is an evening on the Mac and a sitting here.

**The question, and it is the one most likely to have an unwelcome answer:** does routing the
same 100 golden questions through the tool-using agent make single-answer quality **worse** than
the one-shot pipeline Phase 4 measured?

It needs **no new labels**. The golden set already exists, `answer_in_prompt` is computed with
`score.rank_of_first_hit` — the same function `--refusals` and the prompt sweep use — and the
generation columns come from `judge._sweep_generation`, not a second copy (`D85`'s lesson).

```bash
ollama ps                         # expect qwen2.5-coder:7b at 100% GPU

nohup uv run python -u -m rag.agent --golden > /tmp/round17-agent.log 2>&1 &
disown

tail -f /tmp/round17-agent.log    # checkpoints every 5 items; --resume if it dies
```

When it finishes:

```bash
uv run python -m rag.agent --report
ls -la deliverables/agent-sweep-phase5.*.json
git add deliverables/agent-sweep-phase5.Linux-x86_64.json && git commit -m "lab: Round 17.4 agent sweep" && git push
```

**The file is machine-suffixed and the sweep REFUSES to overwrite another machine's rows** — that
guard exists because the lab's Round 15 silently destroyed the Mac's faithfulness file and it was
recovered from git (`D83`).

### Pass / fail for 17.4, written before the data

| result | meaning | next |
|---|---|---|
| end to end **≥ 0.43** | the agent is not worse than the shipped pipeline | Step 3's task set is worth building |
| end to end **materially below 0.43** | tools cost more than they buy at this model size | **that is the phase's finding**, and it is a real one — report it, do not tune it away |
| **`no tool call` is large** | the model answers from memory despite having tools | the defect is the prompt, not the loop |
| **`one tool` ≫ `two or more`** | it stops after one call | the compounding `PHASE-5.md` predicted, now with a denominator |

**Do not compare this against the Mac's 0.43 as though they were the same machine.** `D83`: the
lab's shipped-pipeline baseline is **38/91 = 0.42**. That is the number to put beside it.

### REPLY 17.0

```
6fec996 feat(phase-5): Step 3's instrument, and the lab may now edit files
ollama version is 0.32.9
uv sync --frozen --extra embed: Checked 77 packages
qdrant: Running
nvidia-smi: RTX 3060, then warm → qwen2.5-coder:7b 100% GPU
```

### REPLY 17.1

```
g065 — the fabricated Alembic script, checked against real alembic (D77)
  OK alembic.operations.Operations.create_table       exists=True  (expected True)
  OK alembic.operations.Operations.create_view        exists=False (expected False)
  Two invented calls beside two working ones — and the tool separates them.
exit=0
```

### REPLY 17.2

```
NAME                ID              SIZE      PROCESSOR    CONTEXT    UNTIL
qwen2.5-coder:7b    dae161e27b0e    4.7 GB    100% GPU     4096       4 minutes from now

TOOL CALLS — 20 synthetic questions, labelled by construction, qwen2.5-coder:7b, temperature 0.0
  usable call      20/20 = 100%
  right tool       20/20 = 100%  (labelled by construction)
  ...on `tool_calls` (the MCP channel)   0
  ...on `message.content` as JSON text   20
  NOTE: every call arrived as content text. An agent built on this model parses
        JSON itself; it cannot assume the MCP tool-call channel (D87).

TOOL CALLS — the 100 golden questions, real developer phrasing, qwen2.5-coder:7b, temperature 0.0
  usable call      100/100 = 100%
  ...on `tool_calls` (the MCP channel)   0
  ...on `message.content` as JSON text   100
  NOTE: every call arrived as content text. An agent built on this model parses
        JSON itself; it cannot assume the MCP tool-call channel (D87).
```

### REPLY 17.3

```
has tool_calls: True
classify     : {'outcome': 'tool_calls', 'tool': 'check_api', 'arg': 'Query.from_self'}
```

### REPLY 17.4

```
AGENT — the golden set through the tool-using loop  [Linux-x86_64]
  end to end     2/91 = 0.02   (D72's shipped pipeline: 39/91 = 0.43 on Darwin-arm64)
  over-refused   0      fabricated 5      failed 0
  no tool call   96      one tool 4      two or more 0
  stopped        {'answered': 100, 'budget': 0, 'repeated_call': 0}
  Compare item by item, not by the averages (D61) — and only against a run
  from THIS machine (D83).

# last lines of /tmp/round17-agent.log
  [98/100] g120  steps=1 stopped=answered tools=[]
  [99/100] g119  steps=1 stopped=answered tools=[]
  [100/100] g121  steps=1 stopped=answered tools=[]

saved 100 rows to agent-sweep-phase5.Linux-x86_64.json
  end to end 2/91 = 0.02
```


### LAB RESULT — Round 16 (Mac: read this, not the OPEN asks)

Measured on the **lab PC** (`kj-XPS-8950`, RTX 3060, tip `16064dc`), generator **`100% GPU`**
the whole sitting. These are **lab** numbers — do not mix them with Mac `prompt-sweep-phase4.json`
or Mac faithfulness without naming the machine (`D83`).

| | Mac (all-GPU Metal) | Lab Round 14 (52/48 CPU/GPU) | **Lab Round 16 (100% GPU)** |
|---|---|---|---|
| D end/end | 39/91 = 0.43 | 38/91 = 0.42 | **38/91 = 0.42** |
| H end/end | 47/91 = 0.52 | 42/91 = 0.46 | **42/91 = 0.46** |
| paired | 9↑ 0↓, p=0.0039 | 6↑ 2↓, p=0.289 | **6↑ 2↓, p=0.289** (same IDs) |
| H ship? | candidate | hold | **hold** — compute-path confound **not** confirmed |

**Mac read of that table (`D84`), added 2026-09-10.** The two lab runs are **five days apart and
agree to the item** — same six fixed, same two broken, same p. `D54` says refusal behaviour drifts
across days, but that was measured on the **Mac**, where two of seven items flipped overnight.
**The lab did not drift at all**, so the drift is a property of that machine rather than of the
system. What did move between the lab runs is the *citation* counts (D `19/46 → 18/45`, H
`3/55 → 5/57`): **the decision to answer or refuse was bit-stable; the wording was not.**

**Consequence for the ship call:** the Mac's `9↑ 0↓` was measured **once, on the box whose
generator drifts**;
the lab's `6↑ 2↓` **twice, agreeing**. The honest estimate of H is about **six fixes and two
regressions**, so the hold is the weight of evidence rather than a technicality.

**Lab artifacts (machine-stamped — pull these on the Mac):**

- [`../deliverables/prompt-sweep-round16.Linux-x86_64.json`](../deliverables/prompt-sweep-round16.Linux-x86_64.json) — lab D vs H generations
- [`../deliverables/faithfulness-phase4.Linux-x86_64.json`](../deliverables/faithfulness-phase4.Linux-x86_64.json) — lab judge rows (D **77%** / H **92%**)

Broken on lab both Round 14 and 16: `g030`, `g032`. Fixed both times: `g008`, `g021`, `g049`,
`g050`, `g099`, `g106`.

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
# lab PC, 2026-08-17. phase-1/completion @ 0cd03ab
# 380 generations, did not stop early. k=5, repeat=5. FAILURES.md not written.

top-k = 5
repeat = 5
  run 1/5 done
  run 2/5 done
  run 3/5 done
  run 4/5 done
  run 5/5 done

per-question refusals out of 5 runs (A B C D — * = not unanimous)
   1 symbol    A=0 B=0 C=0 D=0   what replaces Query.from_self() in SQLAlch
   2 symbol    A=0 B=0 C=0 D=0   Query.join with aliased=True stopped worki
   3 symbol    A=5 B=5 C=0 D=5   engine.table_names() is gone — what replac
   4 symbol    A=5 B=5 C=0 D=5   engine.has_table() no longer exists, what
   5 symbol    A=5 B=5 C=0 D=5   row.keys() raises in 2.0, how do I get the
   6 symbol    A=5 B=5 C=0 D=5   orm.relation() is not available any more,
   7 skew      A=0 B=0 C=0 D=0   should I pass future=True to create_engine
   8 skew      A=0 B=0 C=0 D=0   is Session.autocommit still supported?
   9 skew      A=0 B=0 C=0 D=0   can I still use session.begin() with subtr
  10 skew      A=0 B=0 C=0 D=0   does MetaData still accept a bind argument
  11 spanning  A=0 B=0 C=0 D=0   how do I migrate select([col1, col2]) to t
  12 spanning  A=0 B=0 C=0 D=0   what is the full set of steps to migrate a
  13 spanning  A=0 B=0 C=0 D=0   how do I get scalar values instead of Row
  14 spanning  A=0 B=0 C=0 D=0   why do I need .unique() when using joinedl
  15 absent    A=5 B=5 C=0 D=5   what is the exact signature and full argum
  16 absent    A=0 B=0 C=0 D=5   list every keyword argument accepted by re
  17 absent    A=5 B=5 C=0 D=5   what does the SQLAlchemy 2.1 release chang
  18 silent    A=5 B=5 C=0 D=5   if I write comment.issue = issue instead o
  19 silent    A=5 B=5 C=0 D=5   why would an object assigned to a many-to-

prompt    refused  answered   of 19
A             8.0      11.0   strict canned refusal
B             8.0      11.0   refusal as last resort (was shipped to 2026-08-17)
C             0.0      19.0   no refusal clause
D             9.0      10.0   answer partially, refuse only on subject (SHIPPED)

# Zero starred rows. Every cell is 0/5 or 5/5.
# Q16 is D=5 B=0 on all five runs — not a coin-flip.
# A and B identical at 8.0. D is 9.0, the extra one is Q16 only.
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

---

# Round 12 — Phase 2 lab confirmation (before more Phase 3)

**Status: CLOSED 2026-08-21.** Lab @ `f502a9d` matched Mac: recall@5 **0.63 ±0.097**,
**6↑ 0↓** vs baseline, refusals **g056/g065 FABRICATED** (same IDs). One scorecard — not two.
Phase 2 lab confirmation done; Phase 3 may continue (reranker next).

**Branch: `phase-2/measure`.** Not `lab/handoff` (deleted). Not `main`.
Pushed tip already included twin-collapse + hybrid (`D66`/`D67`); lab measured that, not the
pre-hybrid ~0.49 tip the ASK originally described.

## ASK 12.1 — sync + stack + retrieval score

Paste every block’s raw output into REPLY 12.1.

```bash
cd ~/Documents/Workspace/SqlUpgradeAgent   # or wherever the clone lives
git fetch origin
git checkout phase-2/measure
git pull --ff-only
git log -1 --oneline
git status -sb

uv sync --frozen --extra embed
docker compose up -d qdrant
# if collection empty / missing after pull:
#   uv run python -m rag.corpus    # only if corpus/raw missing
#   uv run python -m rag.chunk && uv run python -m rag.embed && uv run python -m rag.index

uv run pytest -q
uv run python -m rag.golden --status
uv run python -m rag.score
uv run python -m rag.score --baseline deliverables/baseline-phase1.json
```

**What “pass” looks like (Mac Phase 2, pre-hybrid):**
- `golden --status`: 100 verified, 9 unanswerable
- `rag.score` on 100: recall@5 around **0.49 ±0.101**, not-in-top-20 around **22**,
  duplicate seats in top-5 around **31** (this tip is *before* twin-collapse/`D66`)
- `--baseline`: **0 fixed, 0 broken**, p = 1.000

If your tip already includes later commits, paste `git log -1` anyway — the REPLY is the truth.

### REPLY 12.1

```
# lab PC, 2026-08-21. phase-2/measure @ f502a9d
# tip already includes twin-collapse + hybrid BM25 (not the pre-hybrid ~0.49 tip)

git log -1 --oneline
f502a9d feat(phase-2/3): close golden signature; twin collapse + hybrid BM25
git status -sb
## phase-2/measure...origin/phase-2/measure

uv sync --frozen --extra embed
Checked 77 packages in 1.03s

docker compose up -d qdrant
Container sqlalchemy-upgrade-agent-qdrant-1 Running
qdrant: healthy
collection sqlalchemy-upgrade-agent-bge-m3-5617a9f6 points 3284

uv run pytest -q
........................................................................ [ 38%]
........................................................................ [ 77%]
..........................................                               [100%]
# 186 passed, 1 warning (MovedIn20Warning on models.py — expected)

uv run python -m rag.golden --status
golden set: 100 items, 100 verified by a human, target 50 (D61)
  unanswerable: 9  (at least 3 wanted — they are the only way to measure whether the system declines when it should)
  provenance: breakages=34, github=25, migration_guide=16, stackoverflow=25

uv run python -m rag.score
ALL ITEMS  —  100 items, 91 answerable
  recall@k   @1=0.31  @3=0.48  @5=0.63  @10=0.71  @20=0.81
  strict     @1=0.31  @3=0.48  @5=0.63  @10=0.71  @20=0.81
  MRR        0.436
  recall@5    0.63  ±0.097  (95%, Wilson)
  median rank when found  2.0   not in top-20: 17
  slots lost to duplicates in top-5: 0

EXCLUDING provenance=breakages  —  66 items, 59 answerable
  recall@5    0.69  ±0.114  (95%, Wilson)
  not in top-20: 10
  slots lost to duplicates in top-5: 0

provenance=breakages       recall@5 0.50  ±0.164   not-in-top-20: 7
provenance=github          recall@5 0.74  ±0.170   not-in-top-20: 2
provenance=migration_guide recall@5 0.93  ±0.143   not-in-top-20: 0
provenance=stackoverflow   recall@5 0.48  ±0.196   not-in-top-20: 8

uv run python -m rag.score --baseline deliverables/baseline-phase1.json
PAIRED against baseline  (recall@5)
  fixed    6  g024, g038, g044, g046, g047, g050
  broken   0  —
  exact McNemar p = 0.031  — significant

# Matches Mac hybrid (~0.63), not the ASK's pre-hybrid ~0.49 checklist.
# Duplicate seats in top-5: 0 (twin collapse live). Baseline: 6 fixed / 0 broken.
```

## ASK 12.2 — optional: `--refusals` on the 3060 (generation)

Only after 12.1 looks sane. ~100 Ollama calls; on the 3060 this is a sitting, not a day.
Needs `ollama` up with `qwen2.5-coder:7b`.

```bash
nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader
ollama list | grep qwen
uv run python -m rag.score --refusals 2>&1 | tee /tmp/phase2-refusals-lab.txt
tail -80 /tmp/phase2-refusals-lab.txt
```

**Compare to Mac 2026-08-21 (100-item):** unanswerable **7/9** refused, **2 FABRICATED**
(`g056`, `g065`); **13** answerable refused with the answer in the prompt; end-to-end ~**0.35**.
Expect small drift (`D54` narrowed) — paste the full refusal section, do not summarise away flips.

### REPLY 12.2

```
# lab PC, 2026-08-21. same tip f502a9d. After 12.1.

nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader
NVIDIA GeForce RTX 3060, 597 MiB, 12288 MiB

ollama list | grep qwen
qwen2.5-coder:7b    dae161e27b0e    4.7 GB    8 days ago

uv run python -m rag.score --refusals
REFUSALS  —  generation, at k=5 (D62; not averaged into recall)
  unanswerable items                9
    refused — correct               7/9  (78%)
    answered — FABRICATED           2/9  (22%)   g056, g065
  answerable items                  91
    refused — over-refusal          46/91  (51%)
      with the answer IN the prompt  20   generation defect (the Q18/Q19 class)   g006, g008, g013, g021, g029, g044, g048, g049, g050, g051, g064, g084, g087, g090, g095, g099, g100, g103, g106, g116
      with the answer absent         26   honest — retrieval never supplied it

ALL ITEMS recall@5    0.63  ±0.097  (same as 12.1; retrieval half unchanged)

# vs Mac 2026-08-21 (100-item): unanswerable 7/9 refused + g056/g065 FABRICATED — identical IDs.
# answerable-in-prompt over-refusals: Mac 13, lab 20. Same defect class, more IDs here.
# Do not summarise the list away — full ID list is above.
```

---

# Round 13 — Phase 4 start: refusal baseline on the 3060 (after D68)

**Status: CLOSED 2026-09-05.** REPLY 13.1 and 13.2 are below. Retrieval matched the Mac exactly
(recall@5 **0.64**, **17** absents, ceiling **58/91**); end to end **38/91 = 0.42** against the
Mac's 0.43; unanswerable **7/9 refused, 2 FABRICATED** (`g056`, `g065`), identical. Folded into
`D83`.

**Original framing, kept because it is what the round was written to do.** Phase 3 retrieval is closed
(`D66`–`D68` shipped; `D69` strip and `D70` boundary re-chunking both rejected with numbers).
Read [`study/15-IMPROVE.md`](../study/15-IMPROVE.md) §R7 on the Mac first. This round is
**generation**, not another embed experiment.

> **The baseline this round was written to produce already exists.** The lab was unreachable,
> so `--refusals` ran on the **Mac** on 2026-08-22 in one sitting (`D54`): **end to end
> 39/91 = 0.43** against a retrieval ceiling of **0.64**, **19** over-refusals with the answer
> in the prompt, unanswerable **7/9 refused, 2 FABRICATED**. Full result: `D72`,
> [`../phases/PHASE-4.md`](../phases/PHASE-4.md) Step 1.
>
> **So this round is now a CONFIRMATION, not a first measurement.** What the 3060 buys is
> speed — ~100 calls at 62 tok/s instead of 18 — which is what makes a *same-sitting*
> before/after affordable once prompt changes start. Run the same command; if any cell
> disagrees with the Mac's, that is `D54` drift across machines and is itself a finding worth
> having before any prompt work is judged.
>
> **`rag.score --refusals` now prints end-to-end itself** (`D72`) — it used to be hand-derived
> in the docs. Paste the whole section, not a summary.

**Why the lab.** Full `--refusals` is ~100 Ollama calls. Mac ~18 tok/s; 3060 ~62 tok/s.
`D54`: re-baseline refusals **in the same sitting** as any prompt change — do not compare
cells across days.

**Branch: `phase-2/measure`.** Pull tip that includes `D68`/`D69` (at least `857797e` or later).

## ASK 13.1 — sync + confirm retrieval still 0.64

Paste raw output into REPLY 13.1.

```bash
cd ~/Documents/Workspace/SqlUpgradeAgent   # or wherever the clone lives
git fetch origin
git checkout phase-2/measure
git pull --ff-only
git log -1 --oneline
git status -sb

uv sync --frozen --extra embed
docker compose up -d qdrant
# Collection should already exist. If score fails on missing collection:
#   uv run python -m rag.embed && uv run python -m rag.index --recreate
# Do NOT re-embed with textnorm — D69 rejected; vectors stay raw.

uv run pytest -q
uv run python -m rag.score
uv run python -m rag.score --baseline deliverables/baseline-phase1.json
```

**What “pass” looks like (Mac after D68):**
- `git log -1` at or after `857797e` (or a later tip that still has D66–D69)
- recall@5 ≈ **0.64 ±0.097**, not-in-top-20 **17**, duplicate seats **0**
- `--baseline`: **7 fixed, 0 broken**, McNemar p ≈ **0.016**
  (fixed set includes `g017` plus the six hybrid fixes)

### REPLY 13.1

```
# lab PC, 2026-09-01. tip addca71.

git log -1 --oneline
addca71 feat(phase-4): the faithfulness judge, pinned and proven (D78) — and a subscript is not a citation (D79)

git status -sb
## phase-2/measure...origin/phase-2/measure

uv sync --frozen --extra embed
Checked 77 packages in 945ms

docker compose up -d qdrant
Container sqlalchemy-upgrade-agent-qdrant-1 Started
NAME                                IMAGE                   COMMAND             SERVICE   CREATED       STATUS                    PORTS
sqlalchemy-upgrade-agent-qdrant-1   qdrant/qdrant:v1.19.0   "./entrypoint.sh"   qdrant    2 weeks ago   Up (healthy)              127.0.0.1:6333->6333/tcp, 6334/tcp

uv run pytest -q
282 passed, 1 warning

uv run python -m rag.golden --status
golden set: 100 items, 100 verified by a human, target 50 (D61)
  unanswerable: 9  (at least 3 wanted — they are the only way to measure whether the system declines when it should)
  provenance: breakages=34, github=25, migration_guide=16, stackoverflow=25

uv run python -m rag.score

ALL ITEMS  —  100 items, 91 answerable
  recall@k   @1=0.31  @3=0.48  @5=0.64  @10=0.71  @20=0.81
  strict     @1=0.31  @3=0.48  @5=0.64  @10=0.71  @20=0.81
  MRR        0.436
  recall@5    0.64  ±0.097  (95%, Wilson)
  median rank when found  2.0   not in top-20: 17
  slots lost to duplicates in top-5: 0

EXCLUDING provenance=breakages  —  66 items, 59 answerable
  recall@k   @1=0.34  @3=0.49  @5=0.69  @10=0.75  @20=0.83
  strict     @1=0.34  @3=0.49  @5=0.69  @10=0.75  @20=0.83
  MRR        0.473
  recall@5    0.69  ±0.114  (95%, Wilson)
  median rank when found  2   not in top-20: 10
  slots lost to duplicates in top-5: 0

provenance=breakages  —  34 items, 32 answerable
  recall@k   @1=0.25  @3=0.47  @5=0.53  @10=0.66  @20=0.78
  strict     @1=0.25  @3=0.47  @5=0.53  @10=0.66  @20=0.78
  MRR        0.369
  recall@5    0.53  ±0.163  (95%, Wilson)
  median rank when found  3   not in top-20: 7
  slots lost to duplicates in top-5: 0

provenance=github  —  25 items, 23 answerable
  recall@k   @1=0.26  @3=0.48  @5=0.74  @10=0.74  @20=0.91
  strict     @1=0.26  @3=0.48  @5=0.74  @10=0.74  @20=0.91
  MRR        0.434
  recall@5    0.74  ±0.170  (95%, Wilson)
  median rank when found  3   not in top-20: 2
  slots lost to duplicates in top-5: 0

provenance=migration_guide  —  16 items, 15 answerable
  recall@k   @1=0.67  @3=0.73  @5=0.93  @10=1.00  @20=1.00
  strict     @1=0.67  @3=0.73  @5=0.93  @10=1.00  @20=1.00
  MRR        0.758
  recall@5    0.93  ±0.143  (95%, Wilson)
  median rank when found  1   not in top-20: 0
  slots lost to duplicates in top-5: 0

provenance=stackoverflow  —  25 items, 21 answerable
  recall@k   @1=0.19  @3=0.33  @5=0.48  @10=0.57  @20=0.62
  strict     @1=0.19  @3=0.33  @5=0.48  @10=0.57  @20=0.62
  MRR        0.311
  recall@5    0.48  ±0.196  (95%, Wilson)
  median rank when found  2   not in top-20: 8
  slots lost to duplicates in top-5: 0

uv run python -m rag.score --baseline deliverables/baseline-phase1.json

(same ALL ITEMS block as above — recall@5 0.64 ±0.097, not-in-top-20 17, dup seats 0)

PAIRED against baseline  (recall@5)
  fixed    7  g017, g024, g038, g044, g046, g047, g050
  broken   0  —
  exact McNemar p = 0.016  — significant

# PASS — matches Mac after D68 on every cell checked.
```

## ASK 13.2 — `--refusals` baseline for Phase 4 (same sitting as 13.1)

Only after 13.1 matches. Needs `ollama` + `qwen2.5-coder:7b` on GPU. ~30–40 min on the 3060.

```bash
nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader
ollama list | grep qwen
uv run python -m rag.score --refusals 2>&1 | tee /tmp/phase4-refusals-baseline.txt
tail -100 /tmp/phase4-refusals-baseline.txt
```

**Compare to Round 12.2 (pre-D68 tip, recall 0.63):** unanswerable **7/9** refused,
**2 FABRICATED** (`g056`, `g065`); answerable-in-prompt over-refusals were **20** on lab
(Mac had listed **13** — same defect class, count drifts under `D54`).

**What Phase 4 will use this for:** a same-sitting before/after when the prompt changes.
Paste the full ID lists — do not summarise them away.

### REPLY 13.2

```
# lab PC, 2026-09-05. tip 169e94c. GPU restored (kernel 7.0.0-30 + nvidia modules).
# Same sitting as Round 14.1 (D54).

nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader
NVIDIA GeForce RTX 3060, 689 MiB, 12288 MiB

ollama list | grep qwen
qwen2.5-coder:7b    dae161e27b0e    4.7 GB    3 weeks ago

uv run python -m rag.score --refusals

REFUSALS  —  generation, at k=5 (D62; not averaged into recall)
  unanswerable items                9
    refused — correct               7/9  (78%)
    answered — FABRICATED           2/9  (22%)   g056, g065
  answerable items                  91
    refused — over-refusal          45/91  (49%)
      with the answer IN the prompt  20   generation defect (the Q18/Q19 class)   g006, g008, g013, g021, g029, g044, g048, g049, g050, g051, g064, g084, g087, g090, g095, g099, g100, g103, g106, g116
      with the answer absent         25   honest — retrieval never supplied it

  answer reached the prompt          58/91   <- retrieval's ceiling, at k=5
  ...and was answered, not refused   38/91   = 0.42   END TO END
  generation loses                   20/91   = 0.22 of the ceiling, invisible to every recall figure

ALL ITEMS recall@5    0.64  ±0.097  (same as 13.1; retrieval half unchanged)
  not in top-20: 17   slots lost to duplicates in top-5: 0

# vs Mac D72 (2026-08-22): end to end 39/91=0.43, over-refused-in-prompt 19, fabr g056/g065.
# Lab today: 38/91=0.42, over-refused-in-prompt 20, same fabr IDs. D54 drift of ±1 cell.
# vs Round 12.2 lab (pre-D68 tip): over-refused-in-prompt was also 20 — same ID list shape.
```

## After Round 13

Mac reads the REPLY, then Phase 4 prompt work starts (over-refusal / fabrication) with the
3060 doing before/after in one sitting.

**Retrieval is closed — do not reopen it here.** No Sphinx strip (`D69`, measured, reverted) and
no boundary re-chunking (`D70`): the condition this file used to carry, *"until a named absent
shows a severed answer"*, was **checked on 2026-08-22 and is not met**. Of the 17 absents' 30
answer chunks, zero are `D56` shapes and the single severed-listing flag does not survive
reading. `uv run python -m rag.score --absents` reproduces it in one command.

---

# Round 14 — the D vs H confirmation, one sitting (the ship decision)

**Status: CLOSED 2026-09-05 — and it decided the ship question against H.** REPLY 14.1 below:
**6↑ 2↓, p = 0.289**, regressions `g030` and `g032`, against the Mac's 9↑ 0↓ p = 0.0039. The
pre-written rule (one regression = hold) applies, so **H does not ship** (`D83`). **Caveat found
2026-09-10:** the generator ran **52%/48% CPU/GPU** on this run against **100% GPU** on the Mac, so
the comparison carries a compute-path confound — **Round 16** tests it.

**Original framing.** Written 2026-09-01. This was the highest-value use of the 3060 at the time, and
unlike Round 13 it is not a confirmation of something already known — it is the run that decides
whether the shipped prompt changes.

> **Mac ready 2026-09-05.** Gates green on Mac (`pytest` pass, `58/58` runnable). Faithfulness
> sweep artifact + agreement sheet are on this branch. Lab: `git pull --ff-only` on
> `phase-2/measure`, then start at ASK 14.1 (or 13.1 if you want the quick recall confirm first).
> Human reading still open on the Mac: `JUDGE-AGREEMENT.md` (10 blanks). **The ship-H call is no
> longer open** — Round 14.1's 6↑ 2↓ with two regressions triggers the pre-written hold (`D83`).

> **Read first on the Mac:** [`../phases/PHASE-4.md`](../phases/PHASE-4.md) Step 4 and `D74`.

**Branch: `phase-2/measure`.** Tip must include `rag/faithful.py` and the `D79` citation fix.
If `ls rag/faithful.py` fails after the pull, the Mac has not pushed and **stop here** — every
number below would be measured against the wrong code.

## Why this round exists

Prompt **H** — D's wording, moved into the **user turn** beside `ANSWER:` — measured on the Mac
on 2026-08-23: **end to end 0.43 → 0.52**, **9 fixed 0 broken**, exact McNemar **p = 0.0039**,
uncited **67% → 10%**. Bigger than everything Phase 3's retrieval work bought (0.35 → 0.43).

**It has not shipped**, and `D54` is why this needs re-running rather than trusting: refusal
cells drift across days, and two of seven items flipped between 08-20 and 08-21 with the prompt,
temperature and index all unchanged. **A before/after must be one sitting.** The Mac run *was*
one sitting, so it is valid — this round asks whether it **reproduces on a second machine**,
which is a stronger claim and one nothing in this repo has yet tested.

**What the 3060 buys.** ~200 generations for D + H. Mac ~18 tok/s took about 2.5 hours; the
3060 at ~62 tok/s should do it in roughly 45 minutes. That is the difference between "an
overnight run" and "a sitting", which is exactly what `D54` demands of every future prompt change.

## ASK 14.1 — D vs H, both arms, one sitting

Run **after** 13.1 confirms retrieval is 0.64. Do not split this across two days.

```bash
cd ~/Documents/Workspace/SqlUpgradeAgent
git fetch origin && git checkout phase-2/measure && git pull --ff-only
git log -1 --oneline
ls -la rag/faithful.py            # must exist, or the Mac has not pushed

uv sync --frozen --extra embed
docker compose up -d qdrant
nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader

uv run python -m rag.compare_prompts --golden D H \
    --save /tmp/round14-DH.json 2>&1 | tee /tmp/round14-DH.txt
tail -120 /tmp/round14-DH.txt
```

**What the Mac got (the rows to compare against):**

| | end to end | over-refused | uncited | code w/o source | fabricated |
|---|---|---|---|---|---|
| **D** shipped | 39/91 = **0.43** | 19 | 31/46 = **67%** | 25/26 = 96% | 2 |
| **H** | **47/91 = 0.52** | **10** | **6/60 = 10%** | 19/36 = 53% | 2 |

H's nine fixed items were `g008`, `g021`, `g049`, `g050`, `g064`, `g095`, `g099`, `g103`,
`g106`.

**Paste the full ID lists, not a summary.** The ids are the finding; the averages are not.

### REPLY 14.1

```
# lab PC, 2026-09-05. tip 169e94c. Same sitting as REPLY 13.2 (D54).
# First attempt died mid-D at 25/100 when the IDE wait was interrupted; restarted with
# nohup from scratch (no --resume on compare_prompts). Full log: /tmp/round14-DH.log

git log -1 --oneline
169e94c feat(phase-4): local prose judge measured (D80–D82) and Phase 4 tracks documented

ls -la rag/faithful.py
-rw-rw-r-- 1 shaili shaili 60982 Sep  5 11:18 rag/faithful.py

nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader
NVIDIA GeForce RTX 3060, 3058 MiB, 12288 MiB

# ollama ps during the run reported qwen2.5-coder:7b at 52%/48% CPU/GPU (not 100% GPU).
# Recorded — sizes the sitting (~25–30 min per arm).

uv run python -u -m rag.compare_prompts --golden D H --save /tmp/round14-DH.json

golden sweep — 100 items x 2 variants, k=5
variants: D, H
retrieved 100 items once; generating
  D: done (0 failed)
  H: done (0 failed)

==============================================================================
GOLDEN SWEEP — both Phase 4 defects, one sitting (D54)
==============================================================================

        end/end  ceiling   over  uncited   code  unc.code  fabr
D         38/91       58     20    19/46     30     27/30     2
H         42/91       58     16     3/55     32     19/32     2

PAIRED against D, item by item — the evidence D61 asks for, not the averages

  H: answers now that D refused    6  g008, g021, g049, g050, g099, g106
     refuses now that D answered    2  g030, g032
     exact McNemar p = 0.289

saved 200 rows to /tmp/round14-DH.json

# vs Mac (D74): D 39/91=0.43 over=19 uncited=31/46; H 47/91=0.52 over=10 uncited=6/60;
#   Mac fixed 9 (g008,g021,g049,g050,g064,g095,g099,g103,g106) broken 0 p=0.0039
# Lab:   D 38/91=0.42 over=20 uncited=19/46; H 42/91=0.46 over=16 uncited=3/55;
#   Lab fixed 6 broken 2 (g030,g032) p=0.289
# Pre-decided rule: "H breaks anything (≥1 regression) → do not ship on this evidence."
# That is the reading. Direction still favors H on end/end and citations; the 2 regressions
# are the blocker under the rule written before the data.
```

## How to read the result — decided in advance, so the answer cannot be fitted to the data

- **H reproduces (≥6 fixed, 0 broken, p < 0.05).** Two machines, two sittings, same direction.
  Ship H. `D61`'s bar was ~6 clean fixes with no regressions and this clears it twice.
- **H wins but by less (3–5 fixed, 0 broken).** Real but smaller than the Mac said. Ship it and
  **quote the lab's number**, not the Mac's — the smaller of two honest measurements is the one
  that survives a follow-up question.
- **H breaks anything (≥1 regression).** Do not ship on this evidence. A regression that the Mac
  did not see is `D54` drift or a machine difference, and either one has to be named before a
  prompt ships on top of it.
- **The cells disagree wildly.** That is the more interesting outcome: it means `D72`/`D73`/`D74`
  are machine-dependent, which nothing in this repo currently claims. Record it and stop —
  a finding, not a failure.

# Round 15 — the prose judge on the 3060

**Status: CLOSED 2026-09-05.** REPLY 15.1/15.2 below: judge `gemma4:e4b` at **100% GPU**,
**D 77% / H 92%** supported, paired **8↑ 2↓ p = 0.109**. H's 92% matches the Mac exactly; D drifted
**85% → 77%**. It also struck `D82`'s "coarser scale" claim — the lab used `PARTIAL` **5 times in
47** where the Mac used it twice. Folded into `D83`.

**Read first on the Mac:** [`../study/09-DECISIONS.md`](../study/09-DECISIONS.md) `D80` and
`D81`, and [`../study/16-JUDGE.md`](../study/16-JUDGE.md) §R8.6.

**This round exists because the advice that used to sit at the bottom of this file was wrong.**
It said faithfulness *"calls the Gemini API, so it is network-bound, not GPU-bound — the 3060
buys nothing. Run it on the Mac."* Both halves died on 2026-09-03:

- **The hosted judge cannot do the run at all.** The 429 body names the ceiling:
  `GenerateRequestsPerDayPerProjectPerModel-FreeTier`, **`quotaValue: 20`**. Twenty requests a
  day, per model. D + H over the saved answers is **~110 calls**. And `D78`'s binding property is
  *same judge, both arms, **one sitting*** — so spreading 110 calls across six days does not
  squeeze under the quota, it destroys the comparison.
- **So the judge is local**, `gemma4:e4b` on Ollama — which makes this run **exactly** the kind
  of work the 3060 exists for. On the Mac it measured **~3.4 minutes per item over 64 items,
  about 3.5 hours.** This is now the slowest thing in the project and the box was built for it.

**It is not self-grading**, which is the objection `ROADMAP.md` raises: the generator is
`qwen2.5-coder:7b` and the judge is a different family and size. Nothing marks its own homework.

**Branch: `phase-2/measure`.** The tip must contain `rag/faithful.py` with a `--sweep` flag and
`rag/judge.py` with `--report`. If `uv run python -m rag.faithful --sweep --help` is not
recognised after the pull, **stop** — the Mac has not pushed, and every number below would be
measured against the wrong code.

## ASK 15.1 — pull, and check the judge model is here

```bash
cd ~/Documents/Workspace/SqlUpgradeAgent
git fetch origin && git checkout phase-2/measure && git pull --ff-only
git log -1 --oneline
ls -la rag/faithful.py rag/judge.py

uv sync --frozen --extra embed
docker compose up -d qdrant

ollama list                       # is gemma4:e4b here? if not, next line pulls it (~9.6 GB)
ollama pull gemma4:e4b
nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader
```

**Why the VRAM line matters here specifically.** VRAM is this box's tight budget, not RAM
(31 GiB system, **12288 MiB** card). On the Mac `ollama ps` reported `gemma4:e4b` at **3.2 GB,
100% GPU, context 8192**. `qwen2.5-coder:7b` is not needed for this round — nothing generates,
only judges — so the card should be holding the embedder plus one judge, not two models.
**If `ollama ps` shows anything less than `100% GPU`, say so in the REPLY**: a judge that spilled
to CPU is the difference between a 40-minute round and a five-hour one, and it is not a failure,
it is a number worth having.

### REPLY 15.1

```
# lab PC, 2026-09-05. tip 169e94c. After Round 14.1 in the same day sitting.

git log -1 --oneline
169e94c feat(phase-4): local prose judge measured (D80–D82) and Phase 4 tracks documented

ls -la rag/faithful.py rag/judge.py
-rw-rw-r-- 1 shaili shaili 60982 Sep  5 11:18 rag/faithful.py
-rw-rw-r-- 1 shaili shaili 34448 Sep  5 11:18 rag/judge.py

uv sync --frozen --extra embed
Checked 77 packages in 845ms

docker compose up -d qdrant
(healthy)

ollama list
gemma4:e4b          c6eb396dbd59    9.6 GB    (pulled this sitting)
qwen2.5-coder:7b    dae161e27b0e    4.7 GB

nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader
NVIDIA GeForce RTX 3060, 508 MiB, 12288 MiB   # after unloading qwen for the judge

# qwen unloaded via keep_alive=0 before the judge sweep so the card holds
# embedder + gemma only, not two generators.
```

## ASK 15.2 — judge D and H, one sitting

Run it detached. It survives the terminal closing and writes rows as it goes — `D75` is the
reason both of those are true (a 300-generation sweep once died at 150 with **zero** rows saved).

```bash
nohup uv run python -u -m rag.faithful --sweep --local --variants D,H \
      > /tmp/round15-faith.log 2>&1 &
disown

# check on it whenever; the file is written every 10 items
grep -c '^  \[' /tmp/round15-faith.log
ollama ps

# when it prints "saved N rows":
tail -60 /tmp/round15-faith.log
```

**Paste the whole FAITHFULNESS block and the per-item lines, not a summary.** The ids are the
finding; the percentages are not.

**What the Mac measured on 2026-09-03, for comparison (`D82`):**

```
variant   answers  judged   SUPP  PART  UNSUP  UNPARSED  NO_PROSE  supported
D              48      47     40     2      5         0         1       85%
H              62      61     56     3      2         0         1       92%
```

**Do not read that as "H is more faithful", and do not let the lab run be read that way either.**
Paired on the 46 items both arms answered it is **5↑ 1↓, exact McNemar p = 0.2188** — clears
neither half of `D61`'s bar. The rate gap is the **16 items only H answered**, 13 of them
`SUPPORTED`.

**The known weakness of this judge, so you can look for it in the lab's rows.** A second model
(`gemini-3.5-flash`) agreed with it on **4 of 10** of the review sheet, and **every disagreement
was the second model choosing `PARTIAL`** where ours chose an extreme. Ours used `PARTIAL` twice
in 47. **If the lab's run also shows almost no `PARTIAL`, that is the model, not the corpus** —
and it is the most useful thing this round can confirm.

**Timing, so you can size the sitting.** On the Mac a single judge call is **46s** with nothing
else running, and the full 64-item run took about **90 minutes**. It is resumable:
`--resume` picks up the checkpoint, refuses if the saved rows carry a different judge model, and
finishes half-judged items rather than skipping them.

**Do NOT pass `--model` or drop `--local`.** Two model ids in one run makes it two judges wearing
one name, and the report prints `!! TWO JUDGES IN ONE RUN` rather than a comparison (`D78`).

### REPLY 15.2

```
# lab PC, 2026-09-05. tip 169e94c. Same day as 13.2/14.1.
# Sweep ran detached (nohup). /tmp/round15-faith.log was cleared by a later tmp wipe;
# numbers below are reconstructed from deliverables/faithfulness-phase4.json via
# rag.faithful.report() — same code path the sweep prints at the end.

# During the run (measured earlier): ollama ps showed gemma4:e4b at 3.2 GB, 100% GPU, context 8192.
# VRAM ~8738 MiB with embedder + judge. No CPU spill.

nohup uv run python -u -m rag.faithful --sweep --local --variants D,H

FAITHFULNESS  —  prose only; code is judge.py's half (D77)
  judge: gemma4:e4b, one sitting, both arms, identical passages

  variant     answers  judged   SUPP   PART  UNSUP  UNPARSED  NO_PROSE  supported
  -------------------------------------------------------------------------------
  D                48      47     36      5      6         0         1       77%
  H                62      61     56      4      1         0         1       92%

  D: 11 answers not fully supported by their own sources
    g014   PARTIAL      Passage [3] directly answers the necessity of using `scalars`, contradicting the claim's asserti
    g019   PARTIAL      Passages [1], [2], [3], and [4] describe both the replacement context manager and the preferred 
    g045   UNSUPPORTED  Passage [3] explicitly states that the patterns described, including using `engine.execute(t.sel
    g065   UNSUPPORTED  None of the passages describe creating both a table and a view in the same migration, nor do the
    g078   PARTIAL      Passages [1] and [3] support the need to set `SQLALCHEMY_WARN_20=1` and the best practices of us
    g079   UNSUPPORTED  None of the passages demonstrate passing advanced loading options like `joinedload` directly to 
    g080   UNSUPPORTED  Passages [2] and [3] show exactly how to use `load_only()` with related objects and collections,
    g083   PARTIAL      Passage [1] confirms the deprecation of "connectionless" and "implicit" execution and recommends
    g117   UNSUPPORTED  None of the passages discuss how to define or access relationships specifically within an asynch
    g120   PARTIAL      The passages confirm that `with_polymorphic` works on joined table inheritance and accepts a bas
    g119   UNSUPPORTED  None of the passages compare or define the specific behavior difference between `session.scalar(

  H: 5 answers not fully supported by their own sources
    g016   UNSUPPORTED  None of the passages state that `row.keys()` is deprecated from result rows and replaced by usin
    g031   PARTIAL      Passage [1] confirms the shift of the function to `_orm.registry.map_imperatively` but does not 
    g062   PARTIAL      The passages demonstrate using `typing.Literal` for enums in `mapped_column` (Passages [2] and [
    g064   PARTIAL      Passage [5] supports the general concept of using union types within `type_annotation_map` but d
    g065   PARTIAL      Passages [2] and [3] state that while SQLAlchemy can emit some DDL statements, general support f

# paired on items both arms answered with a prose verdict (lab, binary SUPPORTED vs not):
#   H gained SUPPORTED  8  g014, g019, g045, g078, g080, g083, g119, g120
#   H lost SUPPORTED    2  g031, g062
#   exact McNemar p = 0.109  (via rag.score.mcnemar_exact) — clears neither half of D61's bar
# Mac D82 was 5↑ 1↓ p=0.2188 on rates D 85% / H 92%.
# Lab rates: D 77% / H 92%. H supported% matches Mac; D drifted 85→77 (more PARTIAL: Mac 2, lab 5).
# PARTIAL is not "almost zero" here the way Mac warned — lab D used PARTIAL 5 times in 47.

per-item (64 unique answered ids):
  [1/64] g002  D=SUPPORTED  H=SUPPORTED
  [2/64] g004  D=SUPPORTED  H=SUPPORTED
  [3/64] g008  D=-  H=SUPPORTED
  [4/64] g014  D=PARTIAL  H=SUPPORTED
  [5/64] g015  D=SUPPORTED  H=SUPPORTED
  [6/64] g016  D=-  H=UNSUPPORTED
  [7/64] g017  D=SUPPORTED  H=SUPPORTED
  [8/64] g018  D=SUPPORTED  H=SUPPORTED
  [9/64] g019  D=PARTIAL  H=SUPPORTED
  [10/64] g021  D=-  H=SUPPORTED
  [11/64] g024  D=NO_PROSE  H=SUPPORTED
  [12/64] g025  D=SUPPORTED  H=SUPPORTED
  [13/64] g026  D=SUPPORTED  H=SUPPORTED
  [14/64] g027  D=SUPPORTED  H=SUPPORTED
  [15/64] g028  D=-  H=NO_PROSE
  [16/64] g029  D=SUPPORTED  H=SUPPORTED
  [17/64] g030  D=SUPPORTED  H=SUPPORTED
  [18/64] g031  D=SUPPORTED  H=PARTIAL
  [19/64] g032  D=SUPPORTED  H=SUPPORTED
  [20/64] g033  D=SUPPORTED  H=SUPPORTED
  [21/64] g034  D=SUPPORTED  H=SUPPORTED
  [22/64] g035  D=SUPPORTED  H=SUPPORTED
  [23/64] g036  D=-  H=SUPPORTED
  [24/64] g038  D=SUPPORTED  H=SUPPORTED
  [25/64] g039  D=-  H=SUPPORTED
  [26/64] g040  D=-  H=SUPPORTED
  [27/64] g041  D=SUPPORTED  H=SUPPORTED
  [28/64] g043  D=SUPPORTED  H=SUPPORTED
  [29/64] g045  D=UNSUPPORTED  H=SUPPORTED
  [30/64] g046  D=SUPPORTED  H=SUPPORTED
  [31/64] g047  D=SUPPORTED  H=SUPPORTED
  [32/64] g049  D=-  H=SUPPORTED
  [33/64] g050  D=-  H=SUPPORTED
  [34/64] g053  D=SUPPORTED  H=SUPPORTED
  [35/64] g055  D=SUPPORTED  H=SUPPORTED
  [36/64] g056  D=SUPPORTED  H=SUPPORTED
  [37/64] g058  D=-  H=SUPPORTED
  [38/64] g060  D=SUPPORTED  H=SUPPORTED
  [39/64] g062  D=SUPPORTED  H=PARTIAL
  [40/64] g064  D=-  H=PARTIAL
  [41/64] g065  D=UNSUPPORTED  H=PARTIAL
  [42/64] g074  D=SUPPORTED  H=SUPPORTED
  [43/64] g078  D=PARTIAL  H=SUPPORTED
  [44/64] g079  D=UNSUPPORTED  H=-
  [45/64] g080  D=UNSUPPORTED  H=SUPPORTED
  [46/64] g081  D=SUPPORTED  H=SUPPORTED
  [47/64] g083  D=PARTIAL  H=SUPPORTED
  [48/64] g085  D=-  H=SUPPORTED
  [49/64] g088  D=SUPPORTED  H=SUPPORTED
  [50/64] g095  D=-  H=SUPPORTED
  [51/64] g098  D=SUPPORTED  H=SUPPORTED
  [52/64] g099  D=-  H=SUPPORTED
  [53/64] g103  D=-  H=SUPPORTED
  [54/64] g106  D=-  H=SUPPORTED
  [55/64] g109  D=SUPPORTED  H=SUPPORTED
  [56/64] g110  D=SUPPORTED  H=SUPPORTED
  [57/64] g111  D=SUPPORTED  H=SUPPORTED
  [58/64] g112  D=SUPPORTED  H=SUPPORTED
  [59/64] g115  D=SUPPORTED  H=SUPPORTED
  [60/64] g117  D=UNSUPPORTED  H=-
  [61/64] g118  D=SUPPORTED  H=SUPPORTED
  [62/64] g119  D=UNSUPPORTED  H=SUPPORTED
  [63/64] g120  D=PARTIAL  H=SUPPORTED
  [64/64] g121  D=SUPPORTED  H=SUPPORTED
```

## ASK 15.3 — the gate, end to end

```bash
uv run python -m rag.judge --report 2>&1 | tee /tmp/round15-report.txt
```

**What "pass" looks like**, and every one of these is checkable against a number already in the
repo rather than against a feeling:

| section | expected |
|---|---|
| 1 retrieval | recall@5 ≈ **0.64 ±0.097**, absent from top 20 **17**, duplicate seats **0** |
| 2 generation | D **39/91 = 0.43**, over-refused **19**, fabricated **2**; H **47/91 = 0.52**, **10**, **2** |
| 3 citations | D uncited **31/48 = 65%**; the stale-row line names **`g016`** under H and nothing under D |
| 4 faithfulness | the Mac got D **40/2/5 = 85%** supported, H **56/3/2 = 92%**; the header must name **`gemma4:e4b`** |
| 5 agreement | *"0 answered — a human has not read them yet"* until the sheet is filled |

**Section 2 is the load-bearing check.** Those cells are re-derived from the saved answers, so if
this box prints anything else, the saved sweep or the code moved — not the model. **That is a
finding, and it stops the round.**

### REPLY 15.3

```
# lab PC, 2026-09-05. after 15.2. tip 169e94c.

uv run python -m rag.judge --report

PHASE 4 SCORECARD  —  the whole system, one command
  golden set: 100 items, 91 answerable, 9 not — all human-verified (D06)

1  RETRIEVAL — did the right page reach the prompt?   [measured live]
     recall@5  0.64 ±0.097     absent from top 20  17     duplicate seats  0
     This is a CEILING, not a score: it says the page arrived, not that the user got it (D72).

2  GENERATION — did the user get an answer?           [read: prompt-sweep-phase4.json]
     prompt              end to end   over-refused   fabricated   failed
     D (ships)          39/91 = 0.43             19            2        0
     H                  47/91 = 0.52             10            2        1
     THE GAP: retrieval 0.64 → delivered 0.43 = 0.21 lost after the right page was already in the prompt.

3  CITATIONS — can the answer be checked?             [read: prompt-sweep-phase4.json, re-scored with today's rules (D79)]
     prompt          answered         uncited    code w/o source  out of range  coverage
     D                     48       31 =  65%         26/28 =  93%             0      0.07
     H                     62        6 =  10%         20/37 =  54%             0      0.32
       (stored fields disagree with today's rules on 1: g016)

4  FAITHFULNESS — is the prose supported by those pages?
     [read: faithfulness-phase4.json, judge gemma4:e4b]
     prompt          judged  SUPPORTED  PARTIAL  UNSUPPORTED  supported
     D                   47         36        5            6       77%
     H                   61         56        4            1       92%

5  THE JUDGE'S OWN CEILING — does it agree with a human?
     10 verdicts in JUDGE-AGREEMENT.md, 0 answered — a human has not read them yet (D06).
     An unmeasured judge is a precise instrument of unknown accuracy. This line is the assumption the gate refuses.

# Section-by-section vs expected:
# 1 retrieval  PASS — 0.64 ±0.097, absent 17, dup seats 0
# 2 generation PASS — reads Mac prompt-sweep-phase4.json: D 0.43 / H 0.52 (load-bearing)
#   NOTE: lab Round 14.1 same-sitting D/H was 38/91=0.42 and 42/91=0.46 with 6↑2↓ —
#   that lives in REPLY 14.1; --report deliberately re-derives from the saved Mac sweep.
# 3 citations  PASS — D uncited 31/48=65%; stale-row names g016 under H
# 4 faithfulness — header names gemma4:e4b; LAB numbers D 36/5/6=77%, H 56/4/1=92%
#   (Mac was D 40/2/5=85%, H 56/3/2=92%). H matches; D drifted. Finding per Round 15 rule.
# 5 agreement  PASS as written — 0 answered, human has not read them yet
```

## How to read Round 15's result — decided now, before the data

- **The verdict counts land close to the Mac's.** The prose judge is machine-independent, which
  is a claim nothing in this repo has been able to make about any generation number (`D54` says
  the opposite about refusals). Record it and quote the lab's numbers.
- **They differ.** Then faithfulness drifts across machines the way refusals do, and **every
  faithfulness figure has to carry its machine** the way rows already carry their judge model.
  That is a real finding and it costs one sentence in `D80`.
- **The judge spilled to CPU and the run took hours.** Not a failure — write the timing into
  REPLY 15.1. It sizes every future judge run and it is the number that decides whether the
  agreement-of-ten should be sampled larger.
- **`--report`'s section 2 disagrees with the table above.** Stop. Do not run anything else. The
  saved sweep or the derivation moved, and every Phase 4 number rests on those cells.

# Round 16 — was it the machine, or was it the CPU?

**Status: CLOSED on lab 2026-09-10.** Written as OPEN the same day; replies 16.0–16.3 are filled.
**Mac: the LAB RESULT block at the top of this file is the summary.** Raw replies below.

Original brief (kept so the asks stay readable): one environment variable, one re-run — cheap,
and it could flip a product decision. **It did not flip:** lab at 100% GPU matched Round 14.

**Read first:** [`../study/09-DECISIONS.md`](../study/09-DECISIONS.md) `D83`, including the
**NARROWED** block at the top of it.

**This round exists because of one line in your own REPLY 14.1, which I read wrong.** You wrote:

```
# ollama ps during the run reported qwen2.5-coder:7b at 52%/48% CPU/GPU (not 100% GPU).
# Recorded — sizes the sitting (~25–30 min per arm).
```

You logged it as a **timing** note. I took it as one and wrote `D83` as *"generation does not
reproduce across machines."* **Measured on the Mac 2026-09-10, the same model under the same
Ollama runs `100% GPU`.** So Round 14 did not compare two machines running the same computation —
it compared **all-GPU Metal against roughly half CPU**, and `TEMPERATURE = 0.0` does not make
output identical across backends. Floating point accumulates differently; one flipped token turns
an answer into a refusal, which is precisely the cell that moved.

**So the honest state is: the drift has a named suspect and nobody has tested it.** This round
tests it, and it is the cheapest experiment in the project — it changes one environment variable.

## ASK 16.0 — sync and bring the stack up (5 minutes)

Nothing here is new; it is written out so the round is self-contained and you are not hunting
through Round 13 for the setup.

```bash
cd ~/Documents/Workspace/SqlUpgradeAgent

git fetch origin
git checkout phase-2/measure
git pull --ff-only
git log -1 --oneline                 # must be NEWER than a380920

# the code this round needs must exist, or you are running the wrong tip
ls rag/faithful.py rag/judge.py
grep -c "faithfulness-phase4\.{machine()}" rag/faithful.py    # expect 1

uv sync --frozen --extra embed
docker compose up -d qdrant
docker compose ps                    # qdrant must be (healthy)
```

**If `grep` returns 0, stop.** The Mac has not pushed the machine-stamping work and every path
below is wrong.

**Why Qdrant:** `compare_prompts --golden` retrieves before it generates. No Qdrant, no run.

### REPLY 16.0

```
# lab PC, 2026-09-10. tip 1091d7b.

git log -1 --oneline
1091d7b feat(phase-4): narrow D83 to a compute-path confound, stamp machines, open Round 16

ls rag/faithful.py rag/judge.py
rag/faithful.py
rag/judge.py

grep -c "faithfulness-phase4\.{machine()}" rag/faithful.py
1

uv sync --frozen --extra embed
Checked 77 packages in 919ms

docker compose up -d qdrant
Container sqlalchemy-upgrade-agent-qdrant-1 Running
NAME                                IMAGE                   COMMAND             SERVICE   CREATED       STATUS                PORTS
sqlalchemy-upgrade-agent-qdrant-1   qdrant/qdrant:v1.19.0   "./entrypoint.sh"   qdrant    3 weeks ago   Up 4 days (healthy)   127.0.0.1:6333->6333/tcp, 6334/tcp

# PASS — tip newer than a380920; machine-stamp grep = 1; qdrant healthy.
```

## ASK 16.1 — put the generator fully on the GPU, and PROVE it before running anything long

The 3060 has 12288 MiB and `qwen2.5-coder:7b` needs roughly 5 GB. It went half-CPU last time
anyway, which usually means Ollama left headroom for a context it was not going to use, or
another process was holding the card.

```bash
# 1. what is on the card right now — anything big here is the likely cause
nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv

# 2. load the model with one throwaway generation
ollama run qwen2.5-coder:7b "say OK" >/dev/null

# 3. THE LINE THIS ROUND IS ABOUT
ollama ps
```

**Read the `PROCESSOR` column. It must say `100% GPU`.**

**If it says anything else, do NOT run the sweep** — a second half-CPU run measures the same
confound twice and the round produces nothing. Try these **one at a time**, running `ollama ps`
after each, so the REPLY records which one worked:

```bash
# a) free the card, then reload
#    (kill whatever nvidia-smi listed above, if it is yours to kill)
ollama stop qwen2.5-coder:7b && ollama run qwen2.5-coder:7b "say OK" >/dev/null && ollama ps

# b) restart the Ollama service and reload
sudo systemctl restart ollama && sleep 5 && ollama run qwen2.5-coder:7b "say OK" >/dev/null && ollama ps

# c) force every layer onto the GPU for the service, then reload
sudo systemctl set-environment OLLAMA_NUM_GPU=999
sudo systemctl restart ollama && sleep 5 && ollama run qwen2.5-coder:7b "say OK" >/dev/null && ollama ps
```

**Paste the `ollama ps` line from each attempt you make**, including the failures. Which lever
moved it is part of the answer, and "it worked eventually" is not.

**If none of them reach 100% GPU, that is a complete and useful REPLY.** It means the 3060 cannot
run this model fully resident under this configuration, `D83`'s confound is not removable on this
box, and the Mac-vs-lab comparison is permanently confounded — worth knowing, and it stops us
planning further cross-machine rounds that cannot answer anything.

### REPLY 16.1

```
# lab PC, 2026-09-10. same sitting as 16.0.

# 1. what is on the card
nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader
NVIDIA GeForce RTX 3060, 589 MiB, 12288 MiB

nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv
pid, process_name, used_gpu_memory [MiB]
4480, /usr/libexec/gnome-remote-desktop-daemon, 106 MiB
697560, /usr/share/rustdesk/rustdesk, 142 MiB

ollama ps
(empty — nothing loaded)

# Unloaded leftover bake-off models (gemma4:e4b, qwen2.5:14b-instruct, llama3.1:8b)
# then loaded the generator. Did NOT need sudo / OLLAMA_NUM_GPU — first load was clean.

# 2+3. throwaway generation + THE LINE
ollama run qwen2.5-coder:7b "say OK"
OK

ollama ps
NAME                ID              SIZE      PROCESSOR    CONTEXT    UNTIL
qwen2.5-coder:7b    dae161e27b0e    4.7 GB    100% GPU     4096       4 minutes from now

nvidia-smi memory after load: 5248 MiB

# PASS — PROCESSOR = 100% GPU. Round 14's 52%/48% was not reproduced on a clean card.
# Levers a/b/c not needed. Proceeding to 16.2.
```

## ASK 16.2 — re-run D vs H with the generator fully on the GPU

**Only after 16.1 shows `100% GPU`.** Roughly 25–30 minutes per arm, so ~1 hour. Run it detached
so an interrupted terminal cannot kill it — Round 14's first attempt died at 25/100 exactly that
way, and `compare_prompts` has **no `--resume`**, so a death means starting over.

```bash
nohup uv run python -u -m rag.compare_prompts --golden D H \
      --save /tmp/round16-DH.json > /tmp/round16-DH.log 2>&1 &
disown

# check on it whenever
tail -5 /tmp/round16-DH.log
ollama ps                       # confirm it is STILL 100% GPU mid-run

# when it finishes
tail -40 /tmp/round16-DH.log
ollama ps                       # and once more after
```

**Paste the whole `GOLDEN SWEEP` block and the `PAIRED against D` list — the ids, not a summary —
plus `ollama ps` from before, during and after.** The ids are the finding; the percentages are
not, and the `ollama ps` lines are what the round exists to pin down.

**Copy the JSON back into the repo so the Mac can re-score it without regenerating:**

```bash
cp /tmp/round16-DH.json deliverables/prompt-sweep-round16.Linux-x86_64.json
git add deliverables/prompt-sweep-round16.Linux-x86_64.json logs/HANDOFF.md
git commit -m "docs(handoff): Round 16 reply — D vs H with the generator fully on GPU"
git push
```

**Do not overwrite `deliverables/prompt-sweep-phase4.json`.** That is the Mac's 300 saved
generations and every published Phase 4 citation figure is derived from it. The machine-suffixed
name above is deliberate — this is the exact mistake that cost us the Mac's judge rows in Round 15
(`D83`).

### REPLY 16.2

```
# lab PC, 2026-09-10. tip 1091d7b. After 16.1 proved 100% GPU.
# Generator stayed 100% GPU before, during (mid-run check at H:50/100), and after.

# BEFORE (from 16.1, immediately before nohup):
ollama ps
NAME                ID              SIZE      PROCESSOR    CONTEXT    UNTIL
qwen2.5-coder:7b    dae161e27b0e    4.7 GB    100% GPU     4096       4 minutes from now

nohup uv run python -u -m rag.compare_prompts --golden D H \
      --save /tmp/round16-DH.json > /tmp/round16-DH.log 2>&1 &

# DURING (at H:50/100):
ollama ps
NAME                ID              SIZE      PROCESSOR    CONTEXT    UNTIL
qwen2.5-coder:7b    dae161e27b0e    4.7 GB    100% GPU     4096       4 minutes from now
# nvidia-smi: 9128 MiB used, 95% util — embedder+reranker+qwen coexist; qwen still 100% GPU

retrieved 100 items once; generating
  D: 25/100
  D: 50/100
  D: 75/100
  D: 100/100
  D: done (0 failed)
  H: 25/100
  H: 50/100
    generation timed out at 300s; retrying once
  H: 75/100
  H: 100/100
  H: done (0 failed)
  H: answers now that D refused    6  g008, g021, g049, g050, g099, g106

==============================================================================
GOLDEN SWEEP — both Phase 4 defects, one sitting (D54)
==============================================================================

        end/end  ceiling   over  uncited   code  unc.code  fabr
D         38/91       58     20    18/45     29     24/29     2
H         42/91       58     16     5/57     31     19/31     2

  end/end   answer in the prompt AND not refused — what a user gets
  ceiling   answer in the prompt at all — identical across variants by design
  over      refused WITH the page in hand (D72's defect)
  uncited   answered items citing nothing (D73's defect)
  unc.code  answers whose code carries no source, of those containing code
  fabr      answered an unanswerable item — the worst cell in the table

PAIRED against D, item by item — the evidence D61 asks for, not the averages

  H: answers now that D refused    6  g008, g021, g049, g050, g099, g106
     refuses now that D answered    2  g030, g032
     exact McNemar p = 0.289

saved 200 rows to /tmp/round16-DH.json

# AFTER:
ollama ps
NAME                ID              SIZE      PROCESSOR    CONTEXT    UNTIL
qwen2.5-coder:7b    dae161e27b0e    4.7 GB    100% GPU     4096       About a minute from now

cp /tmp/round16-DH.json deliverables/prompt-sweep-round16.Linux-x86_64.json
# did NOT touch deliverables/prompt-sweep-phase4.json

# vs Round 14 lab (52%/48% CPU/GPU): D 38/91 H 42/91 6↑2↓ p=0.289 — IDENTICAL cells and IDs
# vs Mac all-GPU: D 39/91 H 47/91 9↑0↓ p=0.0039
# Pre-decided reading: cells stay where Round 14 put them → compute-path confound NOT confirmed.
# H stays held. Generation does not reproduce across machines even at matched 100% GPU backends.
```

## ASK 16.3 — optional, only if 16.2 finished and you still have the sitting

The prose judge again, now that the generator's backend is known. ~90 minutes, resumable, and it
writes to a machine-suffixed path so it **cannot** clobber the Mac's rows the way Round 15 did.

```bash
nohup uv run python -u -m rag.faithful --sweep --local --variants D,H \
      > /tmp/round16-faith.log 2>&1 &
disown

grep -c '^  \[' /tmp/round16-faith.log     # progress
ollama ps                                  # gemma4:e4b should be 100% GPU

# when it prints "saved N rows":
tail -40 /tmp/round16-faith.log
ls -la deliverables/faithfulness-phase4.*.json
```

**It writes `deliverables/faithfulness-phase4.Linux-x86_64.json`** and refuses to overwrite a file
from a different machine. `--resume` picks up the checkpoint if it dies.

**Do not pass `--model` and do not drop `--local`** — two model ids in one run is two judges
wearing one name, and the report prints `!! TWO JUDGES IN ONE RUN` rather than a comparison
(`D78`).

### REPLY 16.3

```
# lab PC, 2026-09-10. same sitting as 16.2. tip ba8c1c2 base; judge on 100% GPU.

# Before: unloaded qwen2.5-coder:7b so the card holds gemma only.
ollama ps (during run)
NAME          ID              SIZE      PROCESSOR    CONTEXT    UNTIL
gemma4:e4b    c6eb396dbd59    3.2 GB    100% GPU     8192       4 minutes from now

nohup uv run python -u -m rag.faithful --sweep --local --variants D,H \
      > /tmp/round16-faith.log 2>&1 &

# progress: 64/64 lines printed
# source: prompt-sweep-phase4.json (Mac saved answers — does not regenerate)

FAITHFULNESS  —  prose only; code is judge.py's half (D77)
  judge: gemma4:e4b on ?, one sitting, both arms, identical passages

  variant     answers  judged   SUPP   PART  UNSUP  UNPARSED  NO_PROSE  supported
  -------------------------------------------------------------------------------
  D                48      47     36      5      6         0         1       77%
  H                62      61     56      4      1         0         1       92%

  D: 11 answers not fully supported by their own sources
    g014   PARTIAL      Passage [3] directly answers the necessity of using `scalars`, contradicting the claim's asserti
    g019   PARTIAL      Passages [1], [2], [3], and [4] describe both the replacement context manager and the preferred 
    g045   UNSUPPORTED  Passage [3] explicitly states that the patterns described, including using `engine.execute(t.sel
    g065   UNSUPPORTED  None of the passages describe creating both a table and a view in the same migration, nor do the
    g078   PARTIAL      Passages [1] and [3] support the need to set `SQLALCHEMY_WARN_20=1` and the best practices of us
    g079   UNSUPPORTED  None of the passages demonstrate passing advanced loading options like `joinedload` directly to 
    g080   UNSUPPORTED  Passages [2] and [3] show exactly how to use `load_only()` with related objects and collections,
    g083   PARTIAL      Passage [1] confirms the deprecation of "connectionless" and "implicit" execution and recommends
    g117   UNSUPPORTED  None of the passages discuss how to define or access relationships specifically within an asynch
    g120   PARTIAL      The passages confirm that `with_polymorphic` works on joined table inheritance and accepts a bas
    g119   UNSUPPORTED  None of the passages compare or define the specific behavior difference between `session.scalar(

  H: 5 answers not fully supported by their own sources
    g016   UNSUPPORTED  None of the passages state that `row.keys()` is deprecated from result rows and replaced by usin
    g031   PARTIAL      Passage [1] confirms the shift of the function to `_orm.registry.map_imperatively` but does not 
    g062   PARTIAL      The passages demonstrate using `typing.Literal` for enums in `mapped_column` (Passages [2] and [
    g064   PARTIAL      Passage [5] supports the general concept of using union types within `type_annotation_map` but d
    g065   PARTIAL      Passages [2] and [3] state that while SQLAlchemy can emit some DDL statements, general support f

saved 110 rows to deliverables/faithfulness-phase4.Linux-x86_64.json

ls -la deliverables/faithfulness-phase4.*.json
-rw-rw-r-- ... deliverables/faithfulness-phase4.Linux-x86_64.json

# AFTER:
ollama ps
NAME          ID              SIZE      PROCESSOR    CONTEXT    UNTIL
gemma4:e4b    c6eb396dbd59    3.2 GB    100% GPU     8192       ...

# vs Round 15 lab (same box, same judge, wrote legacy faithfulness-phase4.json):
#   D 36/5/6 = 77%, H 56/4/1 = 92% — IDENTICAL rates.
# vs Mac D82: D 40/2/5 = 85%, H 56/3/2 = 92%. H matches; D still 85→77 on Linux.
# Machine-stamped path used — Mac rows not overwritten (D83).
```

## How to read it — decided now, before the data

Round 14 on the lab (half-CPU) gave **D 38/91, H 42/91, 6↑ 2↓, p = 0.289**.
The Mac (all-GPU) gave **D 39/91, H 47/91, 9↑ 0↓, p = 0.0039**.

- **The lab's cells move toward the Mac's** (H back up near 47, regressions `g030`/`g032` gone).
  Then **the variable was the compute path, not the machine.** `D83` narrows again — to a sentence
  about backends — and **H becomes shippable on two clean runs.** This is the outcome that would
  change a product decision, which is why the round is worth a sitting.
- **The cells stay where Round 14 put them.** Then the broad claim is earned: generation really
  does not reproduce across machines even at matched backends, and `D54` grows a paragraph. H stays
  held, now for a reason that survived its best challenge.
- **Something in between.** Report it as in between. Do not round it toward whichever story is
  tidier — the honest version of this finding is worth more than a clean one.

**Whatever happens, `ollama ps` output before AND after the run is part of the answer**, not
housekeeping. That one line is what this whole round exists to pin down, and it is the line that
was recorded as a timing note last time.

## What NOT to run on the lab PC

- **The hosted Gemini judge, expecting it to finish.** The free tier is **20 requests per day per
  model** (measured 2026-09-03) against a ~110-call run. The quota is per Google Cloud **project**,
  so a second key is a second 20 — still not 110, and mixing keys mid-run is the same
  disqualifying error as mixing models. `uv run python -m rag.faithful --check` is one call and is
  worth running once to see whether the pinned id is answering here at all; anything past that is
  spending a quota that cannot reach the finish line.

  **And if you do put a key on this box:** `.env` is gitignored so the key does NOT travel with a
  pull, it has to be pasted by hand, and **this is a shared machine** — the other user can read
  it. Remove the line before you leave. Never `git add -f` it.

  ```bash
  echo 'GEMINI_API_KEY=paste-the-key' >> .env    # gitignored; delete it before you leave
  uv run python -m rag.faithful --check          # ONE call
  ```

  **`--check` is the authority, not `--models`.** Measured 2026-08-31: `--models` listed
  `gemini-2.5-flash` and calling it returned **404 — "no longer available to new users"**. And on
  2026-09-03 the pinned `gemini-3.6-flash` returned **503** while three siblings answered in the
  same minute. The catalog is what the API advertises; a call is what happens.

- **`--cross-check` against a hosted model, expecting all ten.** It is ten calls against the same
  **20/day/model** ceiling, and the Mac's second attempt got **7 of 10** before the cap. The tool
  now fails fast on a per-day 429 rather than retrying it (a per-minute 429 is still retried), so
  it will tell you plainly instead of hanging. Worth running once if a key is on the box; not
  worth planning the round around.
- **The agreement-of-ten** (`deliverables/JUDGE-AGREEMENT.md`). That is a human reading the judge's
  verdicts against the passages (`D06`), and it needs no machine at all. **Do it on whatever you
  are comfortable reading on** — the rate is parsed back out of the file, so the only thing that
  matters is that the AGREE/DISAGREE lines get filled in.
- **The open-cell read** (`deliverables/OPEN-CELL-REVIEW.md`). That is a human reading answers
  against real 2.0.51 (`D06`), and it needs no machine at all.
- **Anything retrieval.** Closed by `D66`–`D70`. Do not reopen it here.

## Housekeeping on that box, unchanged

- Clone lives at `~/Documents/Workspace/SqlUpgradeAgent`, shared box (`kj` + `shaili`).
- **Do not touch `~/.claude`** — it is the other user's. No `claude`, no `/login`, no `/logout`.
- Tailscale is already `shaili.gandhi@`; do not re-login. The Day 3 tunnel is still blocked on
  Shaili sharing the node and nothing in this round needs it — AnyDesk is enough.
