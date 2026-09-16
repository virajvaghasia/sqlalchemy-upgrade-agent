"""
A token ledger for hosted calls, because nobody else keeps one.

WHY THIS EXISTS

NVIDIA's free Build tier has **no credit balance and no remaining-tokens meter**,
and measured 2026-09-16, its responses carry **no rate-limit headers** either:

    rate-limit-ish headers: NONE
    usage block: {'prompt_tokens': 6, 'completion_tokens': 5, 'total_tokens': 11, ...}

So the only place consumption is ever visible is the `usage` block of each
reply, which exists for exactly as long as the process that received it. This
module writes it down.

WHAT IT RECORDS, INCLUDING THE FAILURES

Every call: model, caller, the three token counts, and the HTTP status. **A
refused call is recorded too**, and that is the point rather than tidiness:
with no headers, a **429** is the only signal that a rate limit was reached, and
a **404 "not found for account"** is how an entitlement disappears (`PHASE-6.md`,
2026-09-16 — the demo's model stopped being callable while still being listed).
A ledger that only logged successes would show silence for both.

WHAT IT IS NOT

Not a bill: NVIDIA Build is free and these tokens cost nothing. It answers
"how much have we used, on which model, and did anything start failing" — the
question the console does not answer.

Not the demo's record either. The page runs in an ephemeral Modal container, so
its ledger dies with the container; Langfuse keeps the page's per-question token
counts (`D108`). This file is for runs on a machine you own.

    uv run python -m rag.usage --report
"""

from __future__ import annotations

import datetime as _dt
import json
import pathlib
import sys

LEDGER = pathlib.Path(__file__).resolve().parent.parent / "logs" / "nvidia-usage.jsonl"


def record(model: str, usage: dict | None, caller: str, status: int = 200,
           path: pathlib.Path | None = None) -> dict:
    """Append one call. Never raises: a broken ledger must not break a run."""
    usage = usage or {}
    row = {
        "ts": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "model": model,
        "caller": caller,
        "status": status,
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
    }
    target = path or LEDGER
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a") as fh:
            fh.write(json.dumps(row) + "\n")
    except OSError:  # pragma: no cover - a read-only container is not a failure
        pass
    return row


def load(path: pathlib.Path | None = None) -> list[dict]:
    target = path or LEDGER
    if not target.exists():
        return []
    return [json.loads(line) for line in target.read_text().splitlines() if line.strip()]


def report(rows: list[dict]) -> str:
    """Counts first: calls, then tokens, then anything that failed."""
    if not rows:
        return ("NVIDIA TOKEN LEDGER — empty\n"
                "  no hosted calls recorded yet (this file only sees runs on this machine)")
    ok = [r for r in rows if r["status"] == 200]
    bad = [r for r in rows if r["status"] != 200]
    lines = ["NVIDIA TOKEN LEDGER",
             f"  calls {len(rows)}   ok {len(ok)}   failed {len(bad)}",
             f"  tokens in {sum(r['prompt_tokens'] for r in ok)}   "
             f"out {sum(r['completion_tokens'] for r in ok)}   "
             f"total {sum(r['total_tokens'] for r in ok)}",
             f"  first {rows[0]['ts']}   last {rows[-1]['ts']}",
             "",
             f"  {'model':46} {'calls':>5} {'tokens':>9}"]
    models: dict[str, list[dict]] = {}
    for r in ok:
        models.setdefault(r["model"], []).append(r)
    for model, rs in sorted(models.items(), key=lambda kv: -sum(x["total_tokens"] for x in kv[1])):
        lines.append(f"  {model:46} {len(rs):>5} {sum(x['total_tokens'] for x in rs):>9}")

    days: dict[str, list[dict]] = {}
    for r in ok:
        days.setdefault(r["ts"][:10], []).append(r)
    lines += ["", f"  {'day':46} {'calls':>5} {'tokens':>9}"]
    for day, rs in sorted(days.items()):
        lines.append(f"  {day:46} {len(rs):>5} {sum(x['total_tokens'] for x in rs):>9}")

    if bad:
        codes: dict[int, int] = {}
        for r in bad:
            codes[r["status"]] = codes.get(r["status"], 0) + 1
        lines += ["", "  failures by status: " + ", ".join(f"{c}x{n}" for c, n in sorted(codes.items()))]
        if 429 in codes:
            lines.append("  429 = the rate limit was reached. NVIDIA sends no rate-limit headers,")
            lines.append("        so this ledger is the only place that shows it.")
        if 404 in codes:
            lines.append("  404 = 'not found for account' — an entitlement, not an outage")
            lines.append("        (PHASE-6.md, 2026-09-16: a listed model stopped being callable).")
    return "\n".join(lines)


def main() -> None:
    if "--report" not in sys.argv[1:]:
        sys.exit("usage: rag.usage --report [PATH]")
    argv = sys.argv[1:]
    i = argv.index("--report")
    path = pathlib.Path(argv[i + 1]) if len(argv) > i + 1 else None
    print(report(load(path)))


if __name__ == "__main__":
    main()
