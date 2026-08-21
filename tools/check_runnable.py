"""
Check that every `# runnable` block in the docs actually reproduces.

    uv run python -m tools.check_runnable            # run the checkable ones
    uv run python -m tools.check_runnable --list     # classify, run nothing
    uv run python -m tools.check_runnable --file study/07-TESTS.md

`CLAUDE.md`'s measurement rule says: *"If a doc shows output, a `# runnable`
command must reproduce it verbatim."* There are 139 such blocks across 18 files
and, until this script existed, **that rule was enforced by remembering to check**
— which is not enforcement.

It was already broken. `PHASE-1.md` quoted `p90=1738` from a run taken before
`LEAD_IN_MAX` was added; the real value is 1740. One stale digit, inside the
block whose entire purpose is being verbatim, sitting there through four
commits.

WHAT IT CAN AND CANNOT CHECK, STATED HONESTLY

Not every block is machine-checkable, and pretending otherwise would produce a
green run that means nothing. Each block is classified:

    RUN        a plain command against this repo — executed and compared
    ENV        needs something not present here: the lab PC, a GPU, sudo,
               a container that is not running, network to a third party
    MUTATION   "change X, then run Y" — describes output AFTER an edit that
               is deliberately not in the repo
    PROSE      the "command" is an English description, not a shell command
    HISTORY    explicitly labelled as a past state, e.g. "(before the config
               existed)"

Only `RUN` blocks are pass/fail. **The rest are reported and counted**, so the
number of unverifiable blocks is itself visible rather than quietly growing.

KNOWN COVERAGE GAP

Fenced blocks nested inside a blockquote (`> ```` `) are not scanned — the
parser only recognises a fence at the start of a line. `study/09-DECISIONS.md`
puts its evidence inside `>` quotes, so those blocks are unchecked. Stated here
rather than left to be discovered, because an unknown gap in a checker is worse
than a known one.

THE ONE NORMALISATION, AND WHY IT IS NOT A LOOPHOLE

pytest prints `114 passed, 1 warning in 1.04s`. The duration is genuinely
nondeterministic, so an exact match would fail forever and the check would be
turned off — which is worse than a narrow, declared exception. Timings of the
form `in <number>s` are normalised on both sides. **Nothing else is.** Counts,
paths, error strings and every other digit must match exactly.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import textwrap

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# Substrings that make a command not runnable *here*. Kept as an explicit list
# with a reason each, so "unverifiable" is a stated category rather than a
# convenient escape.
ENV_MARKERS = {
    "docker compose exec": "needs a running container",
    "docker inspect": "needs a running container",
    "docker run": "builds or runs an image; slow and stateful",
    "docker build": "builds an image",
    "docker history": "needs a built image",
    "docker image": "needs a built image",
    "docker ps": "needs running containers",
    "docker volume": "needs a volume created by a previous compose run",
    "/var/lib/docker": "the Docker VM's filesystem, not the host's",
    "docker compose up": "starts containers; slow and stateful",
    "docker compose -f": "starts containers with an override file",
    "nvidia-smi": "lab PC only",
    "ollama": "needs the model server and is nondeterministic",
    "systemctl": "lab PC only",
    "sudo": "needs a password",
    "tailscale": "lab PC only",
    "ssh": "no route to the lab PC",
    "nc -z": "no route to the lab PC",
    "ip -4": "lab PC only",
    "lsb_release": "lab PC only",
    "free -h": "lab PC only",
    "uname -a": "machine-specific",
    "sysctl": "machine-specific",
    "gh ": "hits the GitHub API",
    "git log": "changes with every commit",
    "github.com/sqlalchemy": "downloads ~9MB from GitHub",
    "git config": "reads this machine's git identity",
    "git check-ignore": "environment-specific",
    "rag.embed": "loads a 2.2GB model",
    "embeddings.npy": "reads the embedding run's output; CI cannot produce it without the 2.2GB model",
    "rag.ask": "nondeterministic model output",
    "rag.probe": "nondeterministic model output; minutes to run",
    "rag.index": "needs Qdrant running",
    "rag.score": "reads corpus/chunks.jsonl, which is generated and gitignored (D11), and the live path also needs Qdrant",
    "rag.golden": "reads corpus/chunks.jsonl, which is generated and gitignored (D11)",
    "psql": "needs a running database",
}

# An output that is true of THIS machine and no other — a platform-specific
# filename, a CPU architecture. The command is fine; the output cannot be
# universal, so the doc says so where a reader sees it rather than the tool
# silently exempting it.
MACHINE_MARKER = "machine-specific"

MUTATION_MARKERS = (", then ", "then uv run", "then, ")
HISTORY_MARKERS = ("before ", "first draft", "event only", "old ", "previously")

TIMING = re.compile(r"\bin \d+\.\d+s\b")


class Block:
    def __init__(self, path: pathlib.Path, line_no: int, command: str, expected: str,
                 note: str = ""):
        self.path = path
        self.line_no = line_no
        self.command = command
        self.expected = expected
        self.note = note
        self.mode = "exact"
        self.kind, self.reason = self._classify()
        self.actual: str | None = None

    def _classify(self) -> tuple[str, str]:
        c = self.command + " " + self.note
        # HISTORY is decided on the ANNOTATION only. "(before the config
        # existed)" describes when the output was true; the same words inside a
        # command would mean nothing of the kind.
        if MACHINE_MARKER in self.note.lower():
            return "ENV", f"machine-specific output: {self.note}"
        if any(m in self.note.lower() for m in HISTORY_MARKERS):
            return "HISTORY", f"labelled as a past state: {self.note}"
        if self.command.strip().startswith("the same"):
            return "REFERENCE", "points at another block's command rather than restating it"
        if any(m in c for m in HISTORY_MARKERS):
            return "HISTORY", "labelled as a past state"
        if any(m in c for m in MUTATION_MARKERS):
            return "MUTATION", "describes output after an edit not in the repo"
        for marker, why in ENV_MARKERS.items():
            if marker in c:
                return "ENV", why
        # A "command" with no shell-ish token is an English description.
        if not re.search(r"(^|\s)(uv|python|grep|find|for|cat|wc|ls|awk|sed|printf|curl|test|git|docker|tar|head|tail|diff)\b", c):
            return "PROSE", "an English description rather than a command"
        return "RUN", ""

    @property
    def where(self) -> str:
        return f"{self.path.relative_to(REPO_ROOT)}:{self.line_no}"


def parse(path: pathlib.Path) -> list[Block]:
    """Extract runnable blocks. The command may span several `#` lines."""
    blocks: list[Block] = []
    lines = path.read_text().split("\n")
    inside = False
    n = 0
    while n < len(lines):
        line = lines[n]
        if line.startswith("```"):
            inside = not inside
            if inside:
                # look ahead for a runnable marker at the top of this block
                start = n + 1
                if start < len(lines) and lines[start].strip().startswith("# runnable"):
                    raw = []
                    m = start
                    while m < len(lines) and lines[m].strip().startswith("#"):
                        raw.append(re.sub(r"^\s*#", "", lines[m]))
                        m += 1
                    end = m
                    while end < len(lines) and not lines[end].startswith("```"):
                        end += 1
                    # The first line carries `runnable:`; continuation lines are
                    # indented to align under it, purely for reading. That
                    # decoration must be removed as a BLOCK (textwrap.dedent
                    # semantics) rather than per line — a `python -c` body has
                    # real indentation of its own, and lstrip()ing each line
                    # would flatten a for-loop into a syntax error.
                    head = re.sub(r"^\s*runnable:?\s*", "", raw[0])
                    head = re.sub(r"^\s*(→|->)\s*", "", head)
                    tail = textwrap.dedent("\n".join(raw[1:])) if len(raw) > 1 else ""
                    command = (head + ("\n" + tail if tail else "")).strip()
                    # A trailing "(note)" on the FIRST line is an annotation for
                    # the reader, not shell. `(before the config existed)` and
                    # `(DATABASE_URL comes from .env)` are both this shape.
                    annotation = re.search(r"\s{2,}\(([^)]*)\)\s*$", command.split("\n")[0])
                    if annotation:
                        first = command.split("\n")[0][:annotation.start()].rstrip()
                        rest = command.split("\n")[1:]
                        command = "\n".join([first] + rest)
                        note = annotation.group(1)
                    else:
                        note = ""
                    expected = "\n".join(lines[m:end])
                    blocks.append(Block(path, start + 1, command, expected, note))
                    n = end
                    inside = False
        n += 1
    return blocks


def normalise(text: str) -> str:
    """
    Trailing whitespace and blank edges only.

    Leading INDENTATION is preserved deliberately: section-mode compares the
    expected text as a substring of the real output, and an excerpt that starts
    two spaces in has to keep those two spaces or it will not be found.
    """
    text = TIMING.sub("in <t>s", text)
    lines = [l.rstrip() for l in text.split("\n")]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def execute(block: Block) -> bool:
    """
    Exact match, except for one declared case.

    A block annotated `(§N)` shows ONE labelled section of a script that prints
    several. The block is still verbatim — for that section — so it is checked
    as a **contiguous substring** of the real output rather than the whole of
    it. Demanding the whole output would fail every such block and the check
    would be abandoned, which is how measurement rules die.

    Substring is still a real check: it catches any drift inside the section.
    """
    result = subprocess.run(
        block.command, shell=True, cwd=REPO_ROOT,
        capture_output=True, text=True, timeout=300,
    )
    block.actual = (result.stdout + result.stderr)
    actual, expected = normalise(block.actual), normalise(block.expected)
    if "§" in block.note:
        block.mode = "section"
        return expected in actual
    return actual == expected


def main() -> None:
    argv = sys.argv[1:]
    only_file = argv[argv.index("--file") + 1] if "--file" in argv else None

    paths = sorted(
        p for p in REPO_ROOT.rglob("*.md")
        if not any(part in p.parts for part in (".git", "node_modules", ".venv"))
        and (only_file is None or str(p.relative_to(REPO_ROOT)) == only_file)
    )
    blocks = [b for p in paths for b in parse(p)]

    if "--list" in argv:
        for b in blocks:
            note = f"  ({b.reason})" if b.reason else ""
            print(f"{b.kind:9} {b.where:32} {b.command.splitlines()[0][:60]}{note}")

    counts: dict[str, int] = {}
    for b in blocks:
        counts[b.kind] = counts.get(b.kind, 0) + 1

    print(f"\n{len(blocks)} runnable blocks in {len(paths)} files")
    for kind in ("RUN", "ENV", "MUTATION", "PROSE", "HISTORY", "REFERENCE"):
        if counts.get(kind):
            print(f"  {kind:9} {counts[kind]:>3}")

    if "--list" in argv:
        return

    failures = []
    runnable = [b for b in blocks if b.kind == "RUN"]
    for n, b in enumerate(runnable, 1):
        print(f"\r  checking {n}/{len(runnable)}", end="", file=sys.stderr, flush=True)
        try:
            if not execute(b):
                failures.append(b)
        except subprocess.TimeoutExpired:
            b.actual = "<timed out>"
            failures.append(b)
    print(file=sys.stderr)

    print(f"\n  {len(runnable) - len(failures)}/{len(runnable)} RUN blocks reproduce")
    for b in failures:
        print(f"\n{'=' * 78}\nMISMATCH  {b.where}\n$ {b.command}")
        print(f"--- expected ---\n{normalise(b.expected)[:600]}")
        print(f"--- actual ---\n{normalise(b.actual or '')[:600]}")

    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
