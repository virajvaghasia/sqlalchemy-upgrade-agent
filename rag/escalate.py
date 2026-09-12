"""Phase 6, Step 3b — the cascade escalates 20 page-present refusals. Does a stronger model fix them?

    uv run python -m rag.escalate --generate   # 20 hosted free-tier calls; needs Qdrant + GEMINI_API_KEY
    uv run python -m rag.escalate --judge      # local gemma4:e4b reads each answer against its pages
    uv run python -m rag.escalate --report     # no model, no network: reads the saved rows

WHAT IS HELD FIXED, SO A DIFFERENCE MEANS THE MODEL

The same 20 questions `rag.route` lists as the cascade's page-present escalations.
The same five pages (`index.retrieve`, which `route.join_check` proved matches the
lab's). The same prompt, unchanged: `ask.SYSTEM` as the system instruction and
`ask.build_prompt` as the user turn, temperature 0. **The only thing that changes
is the model reading it.**

WHAT IS COUNTED RATHER THAN ESTIMATED

Tokens. The Gemini API returns `usageMetadata` with every response; each row keeps
`promptTokenCount` and `candidatesTokenCount` exactly as returned. A shadow cost
multiplies those by a published rate, so the rate is the only input anyone has
to look up.

Rules and prediction were written into phases/PHASE-6.md before the first call.

THE JUDGE IS NOT INDEPENDENT OF THIS GENERATOR, AND SAYS SO

`--judge` uses local `gemma4:e4b`, which is independent of the SHIPPED generator
(qwen) and is what Phase 4 used. Against `gemini-3.7-flash` it is not clean:
both are Google models. Different weights, same lab -- a weaker form of the
self-grading problem D78 was written to avoid. Settle that before the full 20
are judged (PHASE-6.md Step 3b).
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error

from rag import ask, faithful, judge, route, score

MODEL = faithful.MODEL                     # gemini-3.7-flash, the id D80 measured answering
ROWS = judge.DELIVERABLES / "escalate-phase6.json"
PASS_ANSWERED = 15
PASS_SUPPORTED = 0.80


def escalation_ids() -> list[str]:
    """Exactly the cascade's page-present escalations, derived -- never typed."""
    signals = {r["id"]: r for r in json.loads(
        (judge.DELIVERABLES / "route-signals-phase6.Darwin-arm64.json").read_text())}
    outcomes = {r["id"]: r for r in json.loads(route.OUTCOMES.read_text())["D"]}
    return sorted(route.evaluate(signals, outcomes)["B"]["present"])


def request_body(question: str, hits) -> dict:
    """The shipped prompt in Gemini's shape. Pure, so a test can hold it to
    `ask.SYSTEM` and `ask.build_prompt` byte for byte."""
    return {
        "systemInstruction": {"parts": [{"text": ask.SYSTEM}]},
        "contents": [{"role": "user", "parts": [{"text": ask.build_prompt(question, hits)}]}],
        "generationConfig": {"temperature": ask.TEMPERATURE},
    }


def parse(data: dict) -> dict:
    usage = data.get("usageMetadata", {})
    return {"answer": data["candidates"][0]["content"]["parts"][0]["text"].strip(),
            "prompt_tokens": usage.get("promptTokenCount"),
            "output_tokens": usage.get("candidatesTokenCount")}


def generate_rows(items: list[dict], *, key: str, post, retrieve, log=print,
                  save=None, sleep=time.sleep, done: list[dict] | None = None) -> list[dict]:
    """`post` should be `faithful.retrying(...)`: it retries 503 and per-minute
    429s and raises at once on a per-day quota. The first run passed the raw
    transport, stopped on a transient 503 at item 2, and printed a verdict on
    one row -- both fixed, both tested."""
    rows = list(done or [])
    have = {r["id"] for r in rows}
    for n, it in enumerate(items, 1):
        if it["id"] in have:
            continue
        hits = retrieve(it["question"])
        try:
            data = post(f"models/{MODEL}:generateContent",
                        request_body(it["question"], hits), key)
        except urllib.error.HTTPError as exc:
            # Reaching here means retries were exhausted or the quota is per-day.
            log(f"  [{n}/{len(items)}] {it['id']} HTTP {exc.code} after retries -- stopping, rows so far kept")
            break
        row = {"id": it["id"], "model": MODEL,
               "hits": [h.payload["chunk_id"] for h in hits], **parse(data)}
        row["refused"] = ask.refused(row["answer"])
        rows.append(row)
        log(f"  [{n}/{len(items)}] {it['id']} {'REFUSED' if row['refused'] else 'answered'}"
            f"  tokens {row['prompt_tokens']}+{row['output_tokens']}")
        if save:
            save(rows)
        sleep(faithful.PACE_SECONDS)
    return rows


def summarise(rows: list[dict], expected: int) -> dict:
    answered = [r for r in rows if not r["refused"]]
    judged = [r for r in answered if r.get("verdict")]
    supported = [r for r in judged if r["verdict"] == "SUPPORTED"]
    return {
        "expected": expected, "run": len(rows), "answered": [r["id"] for r in answered],
        "refused": [r["id"] for r in rows if r["refused"]],
        "judged": len(judged), "supported": [r["id"] for r in supported],
        "verdicts": {r["id"]: r["verdict"] for r in judged},
        "prompt_tokens": sum(r["prompt_tokens"] or 0 for r in rows),
        "output_tokens": sum(r["output_tokens"] or 0 for r in rows),
    }


def report(s: dict) -> None:
    head = (f"INCOMPLETE — {s['run']} of {s['expected']}" if s["run"] < s["expected"]
            else f"{s['run']} of {s['expected']}")
    print(f"ESCALATION — {MODEL} on the cascade's page-present refusals ({head})")
    print()
    a = len(s["answered"])
    complete = s["run"] >= s["expected"]
    band = ("PASS" if a >= PASS_ANSWERED else ("MIXED" if a >= 11 else "FAIL")) if complete \
        else "no verdict on an incomplete run"
    print(f"  answered   {a:>2} of {s['run']}   rule >= {PASS_ANSWERED}  -> {band}")
    print(f"  refused    {len(s['refused']):>2}   {' '.join(s['refused']) or '-'}")
    if s["judged"]:
        share = len(s["supported"]) / s["judged"]
        verdict = ("PASS" if share >= PASS_SUPPORTED else "FAIL") if complete \
            else "no verdict on an incomplete run"
        print(f"  SUPPORTED  {len(s['supported']):>2} of {s['judged']} judged = {share:.0%}"
              f"   rule >= {PASS_SUPPORTED:.0%}  -> {verdict}   (local judge, Mac screen)")
        others = {i: v for i, v in s["verdicts"].items() if v != "SUPPORTED"}
        print(f"  not SUPPORTED  {' '.join(f'{i}={v}' for i, v in sorted(others.items())) or '-'}")
    else:
        print("  not judged yet")
    print()
    print(f"  tokens, as returned by the API: prompt {s['prompt_tokens']}, output {s['output_tokens']}"
          f"  (over {s['run']} calls)")


def main() -> None:
    argv = sys.argv[1:]
    golden = {i["id"]: i for i in score.load_golden()}
    ids = escalation_ids()

    if "--generate" in argv:
        key = faithful.api_key()
        if not key:
            sys.exit(f"no {faithful.KEY_VAR}; nothing called")
        # Resume, never restart: rows already saved are not asked again, so a
        # stopped run spends no quota twice on the same question.
        done = json.loads(ROWS.read_text())["rows"] if ROWS.exists() else []
        from rag import index
        save = lambda rows: ROWS.write_text(json.dumps({"rows": rows}, indent=1) + "\n")
        rows = generate_rows([golden[i] for i in ids], key=key,
                             post=faithful.retrying(faithful._post),
                             retrieve=lambda q: index.retrieve(q, limit=ask.DEFAULT_K),
                             save=save, done=done)
        save(rows)
    elif "--judge" in argv:
        chunks = score.load_chunks()
        data = json.loads(ROWS.read_text())
        post = faithful.retrying(faithful.local_post)
        for r in data["rows"]:
            if r["refused"] or r.get("verdict"):
                continue
            passages = [chunks[c]["text"] for c in r["hits"]]
            v = faithful.judge_answer(r["answer"], passages, key="",
                                      model=faithful.LOCAL_MODEL, post=post)
            r["verdict"], r["reason"], r["judge"] = v["verdict"], v.get("reason", ""), faithful.LOCAL_MODEL
            print(f"  {r['id']} {r['verdict']}", flush=True)
            ROWS.write_text(json.dumps(data, indent=1) + "\n")
    report(summarise(json.loads(ROWS.read_text())["rows"], len(ids)))


if __name__ == "__main__":
    main()
