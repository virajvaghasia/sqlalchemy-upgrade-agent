"""Phase 6, Step 3b — the cascade escalates 20 page-present refusals. Does a stronger model fix them?

    uv run python -m rag.escalate --generate       # 20 NVIDIA free-credit calls; needs Qdrant + NVIDIA_API_KEY
    uv run python -m rag.escalate --judge-nvidia   # mistral-large-2 judges (the scored verdicts)
    uv run python -m rag.escalate --judge          # local gemma4:e4b, agreement only
    uv run python -m rag.escalate --report     # no model, no network: reads the saved rows

WHAT IS HELD FIXED, SO A DIFFERENCE MEANS THE MODEL

The same 20 questions `rag.route` lists as the cascade's page-present escalations.
The same five pages (`index.retrieve`, which `route.join_check` proved matches the
lab's). The same prompt, unchanged: `ask.SYSTEM` as the system instruction and
`ask.build_prompt` as the user turn, temperature 0. **The only thing that changes
is the model reading it.**

WHAT IS COUNTED RATHER THAN ESTIMATED

Tokens. The API returns `usage` with every response; each row keeps
`prompt_tokens` and `completion_tokens` exactly as returned. A shadow cost
multiplies those by a published rate, so the rate is the only input anyone has
to look up.

Rules and prediction were written into phases/PHASE-6.md before the first call.

WHO JUDGES, AND WHY THAT ONE

The first run used gemini-3.7-flash and judged it with gemma4:e4b -- a Google
model grading a Google model, caught on Viraj's question. Now the escalation
model is Nemotron (Llama-based) and the scored judge is Mistral Large 2, which
shares a lab with neither. gemma stays as a second opinion for agreement.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error

from rag import ask, faithful, judge, route, score

# Switched from gemini-3.7-flash on 2026-09-12 before any answer from this model
# (PHASE-6.md Step 3b): the Gemini free tier stopped the run at 7 of 20.
# nemotron-70b was listed but returned 404 on this key; this is the largest model
# that answered a content-free probe (PHASE-6.md Step 3b, second switch).
MODEL = "nvidia/nemotron-3-ultra-550b-a55b"
ROWS = judge.DELIVERABLES / "escalate-phase6.json"
# Step 3c: the escalations a real cascade cannot tell apart from the 20.
ROWS_REST = judge.DELIVERABLES / "escalate-rest-phase6.json"
PRICES = judge.DELIVERABLES / "prices-phase6.json"
PASS_ANSWERED = 15
PASS_SUPPORTED = 0.80


def escalation_ids(which: str = "present") -> list[str]:
    """The cascade's escalations, derived -- never typed.

    present  the 20 page-present refusals (Step 3b)
    rest     the other 33: page-absent refusals + unanswerable ones (Step 3c)
    """
    signals = {r["id"]: r for r in json.loads(
        (judge.DELIVERABLES / "route-signals-phase6.Darwin-arm64.json").read_text())}
    outcomes = {r["id"]: r for r in json.loads(route.OUTCOMES.read_text())["D"]}
    b = route.evaluate(signals, outcomes)["B"]
    return sorted(b["present"] if which == "present" else b["absent"] + b["unanswerable"])


def shadow_cost(rows: list[dict], prices: dict) -> float:
    """USD these calls WOULD have cost at the snapshot's list price. The calls
    were free credits; this is the counterfactual the ROADMAP sentence needs."""
    p = prices["models"][MODEL]["pricing"]
    return sum((r["prompt_tokens"] or 0) * float(p["prompt"]) +
               (r["output_tokens"] or 0) * float(p["completion"]) for r in rows)


def request_body(question: str, hits) -> dict:
    """The shipped prompt as an OpenAI-style chat. Pure, so a test can hold it
    to `ask.SYSTEM` and `ask.build_prompt` byte for byte."""
    return {
        "model": MODEL, "temperature": ask.TEMPERATURE,
        # A reasoning model spends budget before it answers; a small cap returns
        # an empty answer, which would read as neither answer nor refusal.
        "max_tokens": 8192,
        "messages": [{"role": "system", "content": ask.SYSTEM},
                     {"role": "user", "content": ask.build_prompt(question, hits)}],
    }


def parse(data: dict) -> dict:
    """Tokens are the API's own `usage` counts, never estimated."""
    usage = data.get("usage", {})
    return {"answer": (data["choices"][0]["message"].get("content") or "").strip(),
            "prompt_tokens": usage.get("prompt_tokens"),
            "output_tokens": usage.get("completion_tokens")}


def nvidia_chat(path: str, body: dict, key: str, timeout: int = 180) -> dict:
    """Raw OpenAI-compatible call; `path` is ignored so `faithful.retrying`
    can wrap it with the same (path, body, key, timeout) signature."""
    import urllib.request
    request = urllib.request.Request(
        faithful.NVIDIA_URL, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def empty(row: dict) -> bool:
    """No answer text at all (reasoning ran out of budget). Neither an answer nor
    a refusal, so it must not be scored as either."""
    return not row["answer"]


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
            data = post("chat/completions", request_body(it["question"], hits), key)
        except urllib.error.HTTPError as exc:
            # Reaching here means retries were exhausted or the quota is per-day.
            log(f"  [{n}/{len(items)}] {it['id']} HTTP {exc.code} after retries -- stopping, rows so far kept")
            break
        row = {"id": it["id"], "model": MODEL,
               "hits": [h.payload["chunk_id"] for h in hits], **parse(data)}
        row["empty"] = empty(row)
        row["refused"] = (not row["empty"]) and ask.refused(row["answer"])
        rows.append(row)
        state = "EMPTY" if row["empty"] else ("REFUSED" if row["refused"] else "answered")
        log(f"  [{n}/{len(items)}] {it['id']} {state}"
            f"  tokens {row['prompt_tokens']}+{row['output_tokens']}")
        if save:
            save(rows)
        sleep(2)
    return rows


def summarise(rows: list[dict], expected: int) -> dict:
    answered = [r for r in rows if not r["refused"] and not r.get("empty")]
    # PHASE-6.md Step 3b: the non-Google judge's verdicts are the ones scored;
    # gemma's are kept for agreement. Before the NVIDIA judge runs, gemma's show.
    field = "verdict_nvidia" if any(r.get("verdict_nvidia") for r in answered) else "verdict"
    judged = [dict(r, verdict=r[field]) for r in answered if r.get(field)]
    supported = [r for r in judged if r["verdict"] == "SUPPORTED"]
    both = [r for r in answered if r.get("verdict") and r.get("verdict_nvidia")]
    return {
        "expected": expected, "run": len(rows), "answered": [r["id"] for r in answered],
        "refused": [r["id"] for r in rows if r["refused"]],
        "empty": [r["id"] for r in rows if r.get("empty")],
        "judged": len(judged), "supported": [r["id"] for r in supported],
        "verdicts": {r["id"]: r["verdict"] for r in judged},
        "judge": faithful.NVIDIA_JUDGE if field == "verdict_nvidia" else faithful.LOCAL_MODEL,
        "agree": sum(r["verdict"] == r["verdict_nvidia"] for r in both), "both": len(both),
        "prompt_tokens": sum(r["prompt_tokens"] or 0 for r in rows),
        "output_tokens": sum(r["output_tokens"] or 0 for r in rows),
    }


UNANSWERABLE_BAR = 2   # Step 3c: >= 2 of 7 unanswerable answered = escalation buys fabrications


def report_rest(rows: list[dict], golden: dict, prices: dict | None) -> dict:
    """Step 3c's own rules. It must not reuse 3b's: those were written for
    page-present refusals, and printing "answered >= 15 -> MIXED" over a set
    that is mostly page-absent and unanswerable reads a rule that was never
    written for it. The first report did exactly that."""
    un = [r for r in rows if not golden[r["id"]].get("answerable")]
    ab = [r for r in rows if golden[r["id"]].get("answerable")]
    fab = [r["id"] for r in un if not r["refused"] and not r.get("empty")]
    ans = [r for r in ab if not r["refused"] and not r.get("empty")]
    judged = [r for r in ans if r.get("verdict_nvidia")]
    sup = [r["id"] for r in judged if r["verdict_nvidia"] == "SUPPORTED"]
    print(f"ESCALATION REST — {MODEL} on the {len(rows)} escalations a cascade cannot tell apart")
    print()
    verdict = "escalation BUYS fabrications" if len(fab) >= UNANSWERABLE_BAR else "refusals stay honest"
    print(f"  unanswerable, answered   {len(fab)} of {len(un)}   rule >= {UNANSWERABLE_BAR}  -> {verdict}"
          f"   {' '.join(fab)}")
    print(f"  page absent, answered    {len(ans)} of {len(ab)}   {' '.join(r['id'] for r in ans) or '-'}")
    if judged:
        others = {r["id"]: r["verdict_nvidia"] for r in judged if r["verdict_nvidia"] != "SUPPORTED"}
        print(f"  page absent, SUPPORTED   {len(sup)} of {len(judged)} judged  (by those pages, NOT the verified one)")
        print(f"  not SUPPORTED            {' '.join(f'{i}={v}' for i, v in sorted(others.items())) or '-'}")
    s = summarise(rows, len(rows))
    print()
    print(f"  tokens, as returned by the API: prompt {s['prompt_tokens']}, output {s['output_tokens']}"
          f"  (over {s['run']} calls)")
    if prices:
        c = shadow_cost(rows, prices)
        print(f"  shadow cost at the price snapshot: ${c:.4f} total, ${c / max(len(rows), 1):.5f} per escalation")
    return {"fabricated": fab, "absent_answered": [r["id"] for r in ans], "absent_supported": sup}


CALIBRATION = {"g016": "not SUPPORTED", "g007": "SUPPORTED or PARTIAL"}   # executed on 2.0.51, D100


def calibration_ok(rows: list[dict]) -> bool:
    by = {r["id"]: r.get("verdict_ref") for r in rows}
    return by.get("g016") not in (None, "SUPPORTED") and by.get("g007") in ("SUPPORTED", "PARTIAL")


def report_reference(present: list[dict], rest: list[dict], delivered: int, answerable: int) -> dict:
    """Step 3d: the judge against the VERIFIED answer chunks. Refuses to print a
    correctness count if the two executed calibration items fail."""
    rows = present + rest
    print("REFERENCE JUDGE — escalated answers against the verified answer chunks (D06)")
    print()
    by = {r["id"]: r.get("verdict_ref") for r in rows}
    print(f"  calibration  g016 (wrong on 2.0.51) -> {by.get('g016')}   "
          f"g007 (right on 2.0.51) -> {by.get('g007')}")
    if not calibration_ok(rows):
        print("  CALIBRATION FAILED -- no correctness count is printed")
        return {}
    print("  calibration passed (a smoke test on two items, not a validation)")
    out = {}
    for name, set_rows in (("3b page present", present), ("3c page absent", rest)):
        judged = [r for r in set_rows if r.get("verdict_ref")]
        count = {v: sorted(r["id"] for r in judged if r["verdict_ref"] == v)
                 for v in ("SUPPORTED", "PARTIAL", "UNSUPPORTED")}
        out[name] = count
        print(f"  {name:<15} judged {len(judged):>2}   SUPPORTED {len(count['SUPPORTED']):>2}   "
              f"PARTIAL {len(count['PARTIAL']):>2}   UNSUPPORTED {len(count['UNSUPPORTED']):>2}")
        print(f"      SUPPORTED  {' '.join(count['SUPPORTED']) or '-'}")
    page = {r["id"] for r in present if r.get("verdict_nvidia") == "SUPPORTED"}
    ref = set(out["3b page present"]["SUPPORTED"])
    print(f"  3b: page judge and reference judge both SUPPORTED {len(page & ref)}; "
          f"page only {' '.join(sorted(page - ref)) or '-'}; reference only {' '.join(sorted(ref - page)) or '-'}")
    k = len(ref)
    print()
    print(f"  pre-registered quote: {delivered} + {k} = {delivered + k}/{answerable} = "
          f"{(delivered + k) / answerable:.2f} end to end (upper bound; lab delivered {delivered})")
    extra = len(out["3c page absent"]["SUPPORTED"])
    print(f"  NOT pre-registered, exploration: + {extra} page-absent -> "
          f"{delivered + k + extra}/{answerable} = {(delivered + k + extra) / answerable:.2f}")
    return out


def report_cascade(present: list[dict], rest: list[dict], n_queries: int, prices: dict) -> None:
    """The whole cascade on the golden set: every refusal escalated, priced."""
    rows = present + rest
    cost = shadow_cost(rows, prices)
    print(f"CASCADE — escalate every local refusal to {MODEL}")
    print()
    print(f"  queries {n_queries}, escalated {len(rows)} ({len(rows) / n_queries:.0%})")
    print(f"  shadow cost ${cost:.4f} for these {n_queries} queries  ->  "
          f"${cost / n_queries * 1000:.2f} per 1000 queries  (price snapshot; calls were free)")


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
    if s["empty"]:
        print(f"  EMPTY      {len(s['empty']):>2}   {' '.join(s['empty'])}  (no answer text; neither answer nor refusal)")
    if s["judged"]:
        share = len(s["supported"]) / s["judged"]
        verdict = ("PASS" if share >= PASS_SUPPORTED else "FAIL") if complete \
            else "no verdict on an incomplete run"
        print(f"  SUPPORTED  {len(s['supported']):>2} of {s['judged']} judged = {share:.0%}"
              f"   rule >= {PASS_SUPPORTED:.0%}  -> {verdict}")
        print(f"  judge      {s.get('judge')}")
        if s.get("both"):
            print(f"  judges agree on {s['agree']} of {s['both']} (gemma4:e4b vs {faithful.NVIDIA_JUDGE})")
        others = {i: v for i, v in s["verdicts"].items() if v != "SUPPORTED"}
        print(f"  not SUPPORTED  {' '.join(f'{i}={v}' for i, v in sorted(others.items())) or '-'}")
    else:
        print("  not judged yet")
    print()
    print(f"  tokens, as returned by the API: prompt {s['prompt_tokens']}, output {s['output_tokens']}"
          f"  (over {s['run']} calls)")
    if s.get("shadow_usd") is not None:
        print(f"  shadow cost at the price snapshot: ${s['shadow_usd']:.4f} total, "
              f"${s['shadow_usd'] / max(s['run'], 1):.5f} per escalation  (calls were free credits)")


SHEET = judge.DELIVERABLES / "ESCALATE-PARTIAL-REVIEW.md"


def write_sheet(rows: list[dict], golden: dict) -> None:
    """The answers the scored judge called PARTIAL, laid out for a human (D06).

    Claude drafts this sheet and never fills the verdict column. Each entry has
    the question, the verified answer chunk ids, the escalated answer in full,
    and the judge's reason, so the reader decides without opening anything else.
    """
    from rag import score as score_mod
    chunks = score_mod.load_chunks()
    partial = [r for r in rows if r.get("verdict_nvidia") == "PARTIAL"]
    out = ["# Escalated answers the judge called PARTIAL — for a human read",
           "",
           f"Generated by `uv run python -m rag.escalate --report --sheet`. Model `{MODEL}`, judge "
           f"`{faithful.NVIDIA_JUDGE}`. **{len(partial)} items.** Fill the last line of each entry "
           "with `SUPPORTED`, `PARTIAL` or `UNSUPPORTED` against the passages the model was given, "
           "and a one-line reason. Claude does not fill these (`D06`).", ""]
    for r in partial:
        g = golden[r["id"]]
        out += [f"## {r['id']} — {g['question']}", "",
                f"**Verified answer chunks:** {', '.join(g.get('answer_chunks') or []) or '—'}  ",
                f"**Pages given to the model:** {', '.join(r['hits'])}  ",
                f"**Judge's reason:** {r.get('reason_nvidia', '').strip()}", "",
                "**Answer:**", "", "````", r["answer"], "````", ""]
        for n, c in enumerate(r["hits"], 1):
            text = chunks[c]["text"]
            out += [f"<details><summary>[{n}] {c}</summary>", "", "````", text, "````", "", "</details>", ""]
        out += ["**Human verdict:** ______  **Reason:** ______", ""]
    SHEET.write_text("\n".join(out) + "\n")
    print(f"sheet written: {SHEET.name} ({len(partial)} items)")


def main() -> None:
    global ROWS
    argv = sys.argv[1:]
    golden = {i["id"]: i for i in score.load_golden()}
    which = "rest" if "--rest" in argv else "present"
    ids = escalation_ids(which)
    if which == "rest":
        ROWS = ROWS_REST

    if "--generate" in argv:
        key = faithful.env_key(faithful.NVIDIA_KEY_VAR)
        if not key:
            sys.exit(f"no {faithful.NVIDIA_KEY_VAR} in the environment or .env; nothing called")
        # Resume, never restart: rows already saved are not asked again, so a
        # stopped run spends no quota twice on the same question.
        done = json.loads(ROWS.read_text())["rows"] if ROWS.exists() else []
        from rag import index
        save = lambda rows: ROWS.write_text(json.dumps({"rows": rows}, indent=1) + "\n")
        rows = generate_rows([golden[i] for i in ids], key=key,
                             post=faithful.retrying(nvidia_chat),
                             retrieve=lambda q: index.retrieve(q, limit=ask.DEFAULT_K),
                             save=save, done=done)
        save(rows)
    elif "--reference" in argv:
        # Step 3d: the same judge, reading each answer against the golden set's
        # VERIFIED answer chunks rather than the five retrieved pages. Only the
        # items named with --only are judged, so calibration can run first.
        key = faithful.env_key(faithful.NVIDIA_KEY_VAR)
        if not key:
            sys.exit(f"no {faithful.NVIDIA_KEY_VAR} in the environment or .env; nothing called")
        only = set(argv[argv.index("--only") + 1].split(",")) if "--only" in argv else None
        chunks = score.load_chunks()
        post = faithful.retrying(faithful.nvidia_post)
        for path in (judge.DELIVERABLES / "escalate-phase6.json", ROWS_REST):
            data = json.loads(path.read_text())
            for r in data["rows"]:
                if r["refused"] or r.get("empty") or r.get("verdict_ref"):
                    continue
                if only is not None and r["id"] not in only:
                    continue
                refs = golden[r["id"]].get("answer_chunks") or []
                if not refs:
                    continue
                try:
                    v = faithful.judge_answer(r["answer"], [chunks[c]["text"] for c in refs],
                                              key=key, model=faithful.NVIDIA_JUDGE, post=post)
                except (TimeoutError, urllib.error.URLError) as exc:
                    print(f"  {r['id']} SKIPPED ({type(exc).__name__})", flush=True)
                    continue
                r["verdict_ref"], r["reason_ref"] = v["verdict"], v.get("reason", "")
                print(f"  {r['id']} {r['verdict_ref']}   {r['reason_ref'][:120]}", flush=True)
                path.write_text(json.dumps(data, indent=1) + "\n")
                time.sleep(2)
        return
    elif "--judge-nvidia" in argv:
        key = faithful.env_key(faithful.NVIDIA_KEY_VAR)
        if not key:
            sys.exit(f"no {faithful.NVIDIA_KEY_VAR} in the environment or .env; nothing called")
        chunks = score.load_chunks()
        data = json.loads(ROWS.read_text())
        post = faithful.retrying(faithful.nvidia_post)
        for r in data["rows"]:
            if r["refused"] or r.get("empty") or r.get("verdict_nvidia"):
                continue
            passages = [chunks[c]["text"] for c in r["hits"]]
            try:
                v = faithful.judge_answer(r["answer"], passages, key=key,
                                          model=faithful.NVIDIA_JUDGE, post=post)
            except (TimeoutError, urllib.error.URLError) as exc:
                # D75, and the gap the 09-10 notes named: retrying() gives up and
                # re-raises, which used to kill the whole run. Skip the item and
                # leave it unjudged, so a resume asks it again.
                print(f"  {r['id']} SKIPPED ({type(exc).__name__}); re-run to judge it", flush=True)
                continue
            r["verdict_nvidia"], r["reason_nvidia"] = v["verdict"], v.get("reason", "")
            print(f"  {r['id']} {r['verdict_nvidia']}", flush=True)
            ROWS.write_text(json.dumps(data, indent=1) + "\n")
            time.sleep(2)
    elif "--judge" in argv:
        chunks = score.load_chunks()
        data = json.loads(ROWS.read_text())
        post = faithful.retrying(faithful.local_post)
        for r in data["rows"]:
            if r["refused"] or r.get("empty") or r.get("verdict"):
                continue
            passages = [chunks[c]["text"] for c in r["hits"]]
            try:
                v = faithful.judge_answer(r["answer"], passages, key="",
                                          model=faithful.LOCAL_MODEL, post=post)
            except (TimeoutError, urllib.error.URLError) as exc:
                print(f"  {r['id']} SKIPPED ({type(exc).__name__}); re-run to judge it", flush=True)
                continue
            r["verdict"], r["reason"], r["judge"] = v["verdict"], v.get("reason", ""), faithful.LOCAL_MODEL
            print(f"  {r['id']} {r['verdict']}", flush=True)
            ROWS.write_text(json.dumps(data, indent=1) + "\n")
    rows = json.loads(ROWS.read_text())["rows"]
    prices = json.loads(PRICES.read_text()) if PRICES.exists() else None
    if "--reference-report" in argv:
        present = json.loads((judge.DELIVERABLES / "escalate-phase6.json").read_text())["rows"]
        rest = [r for r in json.loads(ROWS_REST.read_text())["rows"] if golden[r["id"]].get("answerable")]
        outcomes = json.loads(route.OUTCOMES.read_text())["D"]
        answerable = [r for r in outcomes if r["answerable"]]
        report_reference(present, rest, sum(route.delivered(r) for r in answerable), len(answerable))
        return
    if "--cascade" in argv:
        present = json.loads((judge.DELIVERABLES / "escalate-phase6.json").read_text())["rows"]
        rest = json.loads(ROWS_REST.read_text())["rows"]
        outcomes = json.loads(route.OUTCOMES.read_text())["D"]
        report_cascade(present, rest, len(outcomes), prices)
        return
    if which == "rest":
        report_rest(rows, golden, prices)
        return
    s = summarise(rows, len(ids))
    s["shadow_usd"] = shadow_cost(rows, prices) if prices else None
    report(s)
    if "--sheet" in argv:
        write_sheet(rows, golden)


if __name__ == "__main__":
    main()
