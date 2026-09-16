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
    import urllib.error
    import urllib.request

    from rag import usage as usage_mod

    request = urllib.request.Request(
        faithful.NVIDIA_URL, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        usage_mod.record(body.get("model", "?"), None, "escalate.nvidia_chat", status=exc.code)
        raise
    usage_mod.record(body.get("model", "?"), data.get("usage"), "escalate.nvidia_chat")
    return data


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
        except (TimeoutError, urllib.error.URLError) as exc:
            # D75's gap: retrying() gives up and re-raises, which would end a
            # 100-call run at one slow question. Leave it unasked; a resume asks it.
            log(f"  [{n}/{len(items)}] {it['id']} SKIPPED ({type(exc).__name__}); re-run to ask it")
            continue
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


# --- Step 4d: the demo's hosted generator on ALL 100 --------------------------
#
# The escalation sets above are the questions qwen declined. The hosted demo
# would answer every question with this model, so its end-to-end score needs
# every question asked. Rules and the prediction are in PHASE-6.md Step 4d,
# written before the first call; the constants below are those rules.

ROWS_ALL = judge.DELIVERABLES / "nemotron-all-phase6.json"
ROWS_REPEAT = judge.DELIVERABLES / "nemotron-all-repeat-phase6.json"
QWEN_LAB = route.OUTCOMES                                          # the rule's baseline (D95)
QWEN_MAC = judge.DELIVERABLES / "prompt-sweep-phase4.json"         # context only
MAX_MISSING = 5          # more EMPTY or unasked rows than this -> the run is not quoted
AHEAD_FIXED, AHEAD_BROKEN, ALPHA = 6, 1, 0.05                      # D61's bar
FABRICATION_BAR = 2      # qwen's count (g056, g065)
REPEAT_N, STABLE_AT = 20, 19


def all_ids(golden: dict) -> list[str]:
    """Every human-verified item, sorted. Unverified items are never scored (D06)."""
    return sorted(i for i, it in golden.items() if it.get("verified_by") == "human")


def repeat_ids(golden: dict) -> list[str]:
    """The first 20 by id: chosen by position, before any result existed."""
    return all_ids(golden)[:REPEAT_N]


def outcome_rows(rows: list[dict], golden: dict, chunks: dict) -> list[dict]:
    """Generated rows in `score.report_refusals`' shape, with the repo's own
    definitions: `ask.refused`, and `score.rank_of_first_hit` for whether the
    verified answer page was among the five. EMPTY rows are left out: no answer
    text is neither an answer nor a refusal."""
    out = []
    for r in rows:
        if r.get("empty"):
            continue
        it = golden[r["id"]]
        out.append({"id": r["id"], "answerable": bool(it.get("answerable")),
                    "answer": r["answer"], "refused": ask.refused(r["answer"]),
                    "answer_in_prompt": (score.rank_of_first_hit(r["hits"], it, chunks) is not None
                                         if it.get("answerable") else False)})
    return out


def paired(new: list[dict], old: list[dict]) -> dict:
    """By id on `route.delivered`, over answerable items present on BOTH sides,
    so a question missing from either run is dropped from both (D61)."""
    a = {r["id"]: r for r in new if r["answerable"]}
    b = {r["id"]: r for r in old if r["answerable"]}
    common = sorted(a.keys() & b.keys())
    fixed = [i for i in common if route.delivered(a[i]) and not route.delivered(b[i])]
    broken = [i for i in common if route.delivered(b[i]) and not route.delivered(a[i])]
    return {"n": len(common), "fixed": fixed, "broken": broken,
            "delivered_new": sum(route.delivered(a[i]) for i in common),
            "delivered_old": sum(route.delivered(b[i]) for i in common),
            "p": score.mcnemar_exact(len(fixed), len(broken)),
            # Retrieval reproduces across machines (D83); if a page-present flag
            # differs, the pairing is not comparing the same five pages.
            "flag_differs": [i for i in common if a[i]["answer_in_prompt"] != b[i]["answer_in_prompt"]]}


DELIVERED_IDS = judge.DELIVERABLES / "nemotron-all-delivered.json"   # Step 4f's input


def delivered_ids(rows: list[dict], golden: dict, chunks: dict) -> list[str]:
    """The answers that count toward end to end: answerable, page in the prompt, answered."""
    return sorted(r["id"] for r in outcome_rows(rows, golden, chunks)
                  if r["answerable"] and route.delivered(r))


def verdict(p: dict) -> str:
    f, b = len(p["fixed"]), len(p["broken"])
    if f >= AHEAD_FIXED and b <= AHEAD_BROKEN and p["p"] < ALPHA:
        return "AHEAD"
    if b > f and p["p"] < ALPHA:
        return "BEHIND"
    return "LEVEL"


def stability(first: list[dict], second: list[dict]) -> dict:
    """The same question asked twice: does the answer/decline decision hold, and
    is the text identical? Two different facts, counted apart."""
    a = {r["id"]: r for r in first if not r.get("empty")}
    b = {r["id"]: r for r in second if not r.get("empty")}
    common = sorted(a.keys() & b.keys())
    same = [i for i in common if ask.refused(a[i]["answer"]) == ask.refused(b[i]["answer"])]
    return {"n": len(common), "same_decision": len(same),
            "same_text": sum(a[i]["answer"] == b[i]["answer"] for i in common),
            "flipped": [i for i in common if i not in same]}


def needs_judging(row: dict) -> bool:
    """An answered row without a READABLE verdict. UNPARSED is asked again:
    Step 4d's g025 got an empty reply from the judge, and the old skip test
    (`r.get("verdict_nvidia")`) treated that as done forever."""
    return (not row["refused"] and not row.get("empty")
            and row.get("verdict_nvidia") not in faithful.VERDICTS)


# --- Step 4e: the same judge on both models ----------------------------------

ROWS_QWEN_JUDGED = judge.DELIVERABLES / "qwen-lab-judged-phase6.json"


def qwen_judge_rows(qwen: list[dict], nemotron: list[dict]) -> list[dict]:
    """The lab qwen's answers, each paired with the five page ids from nemotron's
    row for the same question. qwen's rows never stored page ids; retrieval
    reproduces across machines (D83), and the report re-checks that per question."""
    hits = {r["id"]: r["hits"] for r in nemotron}
    return [{"id": r["id"], "answer": r["answer"], "hits": list(hits[r["id"]]),
             "refused": False, "empty": False, "generator": "qwen2.5-coder:7b (lab, Round 16)"}
            for r in qwen if "answer" in r and not ask.refused(r["answer"])]


def paired_support(nem: dict, qwen: dict, drop: set = frozenset()) -> dict:
    """SUPPORTED yes/no by id over questions both models answered and the judge
    read on both sides. Unreadable verdicts and page-flag mismatches are dropped
    from BOTH sides and named."""
    common = sorted(nem.keys() & qwen.keys())
    dropped = [i for i in common if i in drop
               or nem[i] not in faithful.VERDICTS or qwen[i] not in faithful.VERDICTS]
    kept = [i for i in common if i not in dropped]
    fixed = [i for i in kept if nem[i] == "SUPPORTED" and qwen[i] != "SUPPORTED"]
    broken = [i for i in kept if qwen[i] == "SUPPORTED" and nem[i] != "SUPPORTED"]
    return {"n": len(kept), "fixed": fixed, "broken": broken, "dropped": dropped,
            "p": score.mcnemar_exact(len(fixed), len(broken))}


def faith_verdict(p: dict) -> str:
    return {"AHEAD": "MORE faithful", "BEHIND": "LESS faithful", "LEVEL": "LEVEL"}[verdict(p)]


def report_same_judge(nem_rows: list[dict], qwen_judged: list[dict], nem_outs: list[dict],
                      qwen_outs: list[dict]) -> dict:
    nem = {r["id"]: r["verdict_nvidia"] for r in nem_rows
           if not r.get("empty") and not ask.refused(r["answer"]) and r.get("verdict_nvidia")}
    qwen = {r["id"]: r.get("verdict_nvidia") for r in qwen_judged}
    flag_n = {r["id"]: r["answer_in_prompt"] for r in nem_outs}
    flag_q = {r["id"]: r["answer_in_prompt"] for r in qwen_outs}
    differ = {i for i in flag_n.keys() & flag_q.keys() if flag_n[i] != flag_q[i]}
    print(f"\n  SAME JUDGE, BOTH MODELS ({faithful.NVIDIA_JUDGE}, each answer against its five pages)")
    for name, v in (("qwen2.5-coder:7b (lab)", qwen), ("nemotron", nem)):
        judged = [x for x in v.values() if x in faithful.VERDICTS]
        sup = sum(x == "SUPPORTED" for x in judged)
        rate = f"{sup / len(judged):.0%}" if judged else "-"
        print(f"    {name:<24} judged {len(judged):>2} of {len(v):>2} answered   SUPPORTED {sup:>2} = {rate}"
              f"   PARTIAL {sum(x == 'PARTIAL' for x in judged)}   UNSUPPORTED {sum(x == 'UNSUPPORTED' for x in judged)}")
    missing = [i for i, x in qwen.items() if x not in faithful.VERDICTS]
    p = paired_support(nem, qwen, drop=differ)
    done = not missing
    tail = f"-> {faith_verdict(p)}" if done else f"no verdict: {len(missing)} qwen answers not judged yet"
    print(f"    paired over {p['n']} answered by both   nemotron-only SUPPORTED {len(p['fixed'])}  "
          f"qwen-only SUPPORTED {len(p['broken'])}  exact McNemar p = {p['p']:.4f}   {tail}")
    print(f"      nemotron-only  {' '.join(p['fixed']) or '-'}")
    print(f"      qwen-only      {' '.join(p['broken']) or '-'}")
    if p["dropped"]:
        print(f"      dropped (unreadable verdict or page flag differs)  {' '.join(p['dropped'])}")
    return p


# --- Step 4g: the judge given what the model was given ---------------------------

NOISE_N, NOISE_MAX = 20, 2    # PHASE-6.md Step 4g


# One definition, shared with the Phase 4 judge (Round 22).
passage_as_shown = faithful.passage_as_shown


def judge_into(rows: list[dict], chunks: dict, judge, *, field: str, headings: bool,
               log=print, save=None, only: set | None = None) -> None:
    """Judge answered rows into `field` (reason into `reason` + the suffix). Rows with a
    readable verdict in that field are skipped, so a resume never asks twice and an
    UNPARSED one is asked again. `judge(answer, passages)` returns {"verdict", "reason"}."""
    reason_field = field.replace("verdict", "reason")
    for r in rows:
        if r.get("empty") or ask.refused(r["answer"]) or r.get(field) in faithful.VERDICTS:
            continue
        if only is not None and r["id"] not in only:
            continue
        passages = [passage_as_shown(chunks[c]) if headings else chunks[c]["text"] for c in r["hits"]]
        try:
            v = judge(r["answer"], passages)
        except (TimeoutError, urllib.error.URLError) as exc:
            log(f"  {r['id']} SKIPPED ({type(exc).__name__}); re-run to judge it")
            continue
        r[field], r[reason_field] = v["verdict"], v.get("reason", "")
        log(f"  {r['id']} {field} {r[field]}")
        if save:
            save()


def noise_ids(rows: list[dict]) -> list[str]:
    """The noise control: the first 20 answered rows by id, chosen by position."""
    return sorted(r["id"] for r in rows if not r.get("empty") and not ask.refused(r["answer"]))[:NOISE_N]


def flips(rows: list[dict], a: str, b: str) -> dict:
    """SUPPORTED yes/no from field a to field b, over rows readable in both."""
    both = [r for r in rows if r.get(a) in faithful.VERDICTS and r.get(b) in faithful.VERDICTS]
    up = sorted(r["id"] for r in both if r[a] != "SUPPORTED" and r[b] == "SUPPORTED")
    down = sorted(r["id"] for r in both if r[a] == "SUPPORTED" and r[b] != "SUPPORTED")
    return {"n": len(both), "up": up, "down": down, "p": score.mcnemar_exact(len(up), len(down))}


def headings_matter(per_model: list[dict], noise_flips: int) -> str:
    if noise_flips > NOISE_MAX:
        return "judge too noisy to attribute"
    if any(len(f["up"]) >= 3 and len(f["up"]) > len(f["down"]) and f["p"] < ALPHA for f in per_model):
        return "headings MATTER"
    return "headings do NOT matter"


def report_headings(nem_rows: list[dict], qwen_rows: list[dict], nem_outs: list[dict],
                    qwen_outs: list[dict]) -> dict:
    print("\n  STEP 4g — THE JUDGE GIVEN THE HEADINGS THE MODEL SAW")
    noise_rows = [r for r in nem_rows if r.get("verdict_nvidia_t2")]
    nz = flips(noise_rows, "verdict_nvidia", "verdict_nvidia_t2")
    noise = len(nz["up"]) + len(nz["down"])
    print(f"    noise control  {nz['n']} nemotron answers judged text-only twice: flips {noise}"
          f"  (up {' '.join(nz['up']) or '-'}; down {' '.join(nz['down']) or '-'})   rule <= {NOISE_MAX}")
    per = []
    for name, rows in (("nemotron", nem_rows), ("qwen2.5-coder:7b (lab)", qwen_rows)):
        answered = [r for r in rows if not r.get("empty") and not ask.refused(r["answer"])]
        f = flips(answered, "verdict_nvidia", "verdict_nvidia_h")
        per.append(f)
        judged = [r for r in answered if r.get("verdict_nvidia_h") in faithful.VERDICTS]
        sup = sum(r["verdict_nvidia_h"] == "SUPPORTED" for r in judged)
        rate = f"{sup / len(judged):.0%}" if judged else "-"
        print(f"    {name:<24} with headings judged {len(judged):>2} of {len(answered):>2}   SUPPORTED {sup:>2} = {rate}"
              f"   text-only -> headings: up {len(f['up'])}  down {len(f['down'])}  p = {f['p']:.4f}")
        print(f"      up    {' '.join(f['up']) or '-'}")
        print(f"      down  {' '.join(f['down']) or '-'}")
    complete = all(r.get("verdict_nvidia_h") in faithful.VERDICTS for rows in (nem_rows, qwen_rows)
                   for r in rows if not r.get("empty") and not ask.refused(r["answer"]))
    complete = complete and nz["n"] == NOISE_N
    verdict = headings_matter(per, noise) if complete else "no verdict until every answer and the noise control are judged"
    print(f"    Q1  -> {verdict}")
    nem = {r["id"]: r.get("verdict_nvidia_h") for r in nem_rows
           if not r.get("empty") and not ask.refused(r["answer"])}
    qwen = {r["id"]: r.get("verdict_nvidia_h") for r in qwen_rows}
    flag_n = {r["id"]: r["answer_in_prompt"] for r in nem_outs}
    flag_q = {r["id"]: r["answer_in_prompt"] for r in qwen_outs}
    differ = {i for i in flag_n.keys() & flag_q.keys() if flag_n[i] != flag_q[i]}
    p = paired_support(nem, qwen, drop=differ)
    print(f"    Q2  paired over {p['n']}: nemotron-only SUPPORTED {len(p['fixed'])}  qwen-only {len(p['broken'])}"
          f"  p = {p['p']:.4f}   -> {faith_verdict(p) if complete else 'no verdict yet'}")
    g = next((r for r in nem_rows if r["id"] == "g044"), {})
    print(f"    g044 (nemotron)  text-only {g.get('verdict_nvidia')}  ->  with headings {g.get('verdict_nvidia_h')}")
    return {"noise": noise, "per_model": per, "verdict": verdict, "paired": p}


def report_all(rows: list[dict], repeat: list[dict], golden: dict, chunks: dict, *,
               qwen_lab: list[dict], qwen_mac: list[dict], prices: dict | None,
               qwen_judged: list[dict] | None = None) -> dict:
    expected = len(all_ids(golden))
    empty = [r["id"] for r in rows if r.get("empty")]
    missing = expected - (len(rows) - len(empty))
    quoted = missing <= MAX_MISSING
    print(f"ALL {expected} — {MODEL}, shipped prompt, k={ask.DEFAULT_K}  "
          f"(asked {len(rows)}, EMPTY {len(empty)}{': ' + ' '.join(empty) if empty else ''})")
    if not quoted:
        print(f"  NOT QUOTED — {missing} of {expected} have no answer text or were not asked "
              f"(rule: at most {MAX_MISSING})")
    outs = outcome_rows(rows, golden, chunks)
    score.report_refusals(outs)

    print()
    result = {"quoted": quoted}
    for label, old, rules in (("lab qwen2.5-coder:7b, Round 16 (the rule)", qwen_lab, True),
                              ("Mac qwen2.5-coder:7b, 2026-08-23 (context)", qwen_mac, False)):
        if not old:
            continue
        p = paired(outs, old)
        tail = f"  -> {verdict(p)}" if rules and quoted else ""
        print(f"  vs {label}")
        print(f"    delivered {p['delivered_new']} vs {p['delivered_old']} over {p['n']} paired   "
              f"fixed {len(p['fixed'])}  broken {len(p['broken'])}  exact McNemar p = {p['p']:.4f}{tail}")
        print(f"    fixed   {' '.join(p['fixed']) or '-'}")
        print(f"    broken  {' '.join(p['broken']) or '-'}")
        if p["flag_differs"]:
            print(f"    !! page-present flag differs from that run on {' '.join(p['flag_differs'])}")
        if rules:
            result["paired"] = p

    fab = [r["id"] for r in outs if not r["answerable"] and not r["refused"]]
    if quoted:
        print(f"\n  fabrications  {len(fab)}   rule <= {FABRICATION_BAR}  -> "
              f"{'no worse' if len(fab) <= FABRICATION_BAR else 'WORSE'}   {' '.join(fab) or '-'}")

    answered = [r for r in rows if not r.get("empty") and not ask.refused(r["answer"])]
    judged = [r for r in answered if r.get("verdict_nvidia") in faithful.VERDICTS]
    unparsed = [r["id"] for r in answered if r.get("verdict_nvidia") == "UNPARSED"]
    sup = [r for r in judged if r["verdict_nvidia"] == "SUPPORTED"]
    print(f"\n  FAITHFULNESS ({faithful.NVIDIA_JUDGE}, against the five pages given; SUPPORTED is not 'correct')")
    if not judged:
        print("    not judged yet")
    else:
        share = len(sup) / len(judged)
        done = len(judged) == len(answered) and quoted
        rule = (f"-> {'PASS' if share >= PASS_SUPPORTED else 'FAIL'}" if done
                else "no verdict until every answer is judged")
        print(f"    judged {len(judged)} of {len(answered)} answered   SUPPORTED {len(sup)} = {share:.0%}"
              f"   rule >= {PASS_SUPPORTED:.0%} {rule}")
        others = {r["id"]: r["verdict_nvidia"] for r in judged if r["verdict_nvidia"] != "SUPPORTED"}
        print(f"    not SUPPORTED  {' '.join(f'{i}={v}' for i, v in sorted(others.items())) or '-'}")
        if unparsed:
            print(f"    UNPARSED {' '.join(unparsed)}  (not a verdict; re-run --judge-nvidia to ask again)")
        result["supported"] = (len(sup), len(judged))

    if qwen_judged:
        qwen_outs = [dict(r, refused=ask.refused(r["answer"])) for r in qwen_lab]
        result["same_judge"] = report_same_judge(rows, qwen_judged, outs, qwen_outs)
        if any(r.get("verdict_nvidia_h") for r in rows + qwen_judged):
            result["headings"] = report_headings(rows, qwen_judged, outs, qwen_outs)

    if repeat:
        s = stability([r for r in rows if r["id"] in {x["id"] for x in repeat}], repeat)
        rule = (f"-> {'stable' if s['same_decision'] >= STABLE_AT else 'NOT stable'}"
                if s["n"] == REPEAT_N else f"no verdict on {s['n']} of {REPEAT_N}")
        print(f"\n  REPEAT  {s['n']} asked twice   same decision {s['same_decision']}   "
              f"rule >= {STABLE_AT} {rule}   identical text {s['same_text']}"
              f"   flipped {' '.join(s['flipped']) or '-'}")
        result["repeat"] = s

    every = rows + list(repeat)
    print(f"\n  tokens, as returned by the API: prompt {sum(r['prompt_tokens'] or 0 for r in every)}, "
          f"output {sum(r['output_tokens'] or 0 for r in every)}  (over {len(every)} generation calls)")
    if prices:
        c = shadow_cost(rows, prices)
        print(f"  shadow cost of the 100: ${c:.4f}, ${c / max(len(rows), 1) * 1000:.2f} per 1000 queries"
              f"  (price snapshot; calls were free credits)")
    return result


SHEET = judge.DELIVERABLES / "ESCALATE-PARTIAL-REVIEW.md"


def write_sheet(rows: list[dict], golden: dict) -> None:
    """The answers the scored judge called PARTIAL, laid out for a human (D06).

    Claude drafts this sheet and never fills the verdict column. Each entry has
    the question, the verified answer chunk ids, the escalated answer in full,
    and the judge's reason, so the reader decides without opening anything else.
    """
    from rag import score as score_mod
    # Never regenerate over a human's verdicts (D06): the file is where they live.
    if SHEET.exists() and any("______" not in line for line in SHEET.read_text().splitlines()
                              if line.startswith("**Human verdict:**")):
        sys.exit(f"{SHEET.name} already holds human verdicts; not overwriting it")
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
            # The heading line is part of what ask.build_prompt gave the model. The first sheet
            # left it out, and a human reason for g044 was written without it (PHASE-6.md).
            heading = " > ".join(chunks[c].get("heading_path") or []) or "(no heading)"
            out += [f"<details><summary>[{n}] {c} — {heading}</summary>", "", "````", chunks[c]["text"],
                    "````", "", "</details>", ""]
        out += ["**Human verdict:** ______  **Reason:** ______", ""]
    SHEET.write_text("\n".join(out) + "\n")
    print(f"sheet written: {SHEET.name} ({len(partial)} items)")


def main() -> None:
    global ROWS
    argv = sys.argv[1:]
    golden = {i["id"]: i for i in score.load_golden()}
    which = "rest" if "--rest" in argv else "present"
    all_mode = "--all" in argv
    if all_mode:
        # Step 4d. --repeat asks the first 20 again into their own file.
        # Step 4e. --judge-qwen judges the lab qwen's answers with the same judge.
        ids, ROWS = ((repeat_ids(golden), ROWS_REPEAT) if "--repeat" in argv
                     else (all_ids(golden), ROWS_ALL))
        if "--write-delivered" in argv:
            ids_ = delivered_ids(json.loads(ROWS_ALL.read_text())["rows"], golden, score.load_chunks())
            DELIVERED_IDS.write_text(json.dumps({"source": ROWS_ALL.name, "ids": ids_}, indent=1) + "\n")
            print(f"wrote {DELIVERED_IDS.name}: {len(ids_)} ids")
            return
        if "--judge-headings" in argv:
            # Step 4g: noise control first (20 text-only), then both models with headings.
            key = faithful.env_key(faithful.NVIDIA_KEY_VAR)
            if not key:
                sys.exit(f"no {faithful.NVIDIA_KEY_VAR} in the environment or .env; nothing called")
            chunks = score.load_chunks()
            post = faithful.retrying(faithful.nvidia_post)
            judge_fn = lambda answer, passages: faithful.judge_answer(
                answer, passages, key=key, model=faithful.NVIDIA_JUDGE, post=post)
            for path, field, headings, only in (
                    (ROWS_ALL, "verdict_nvidia_t2", False, "noise"),
                    (ROWS_ALL, "verdict_nvidia_h", True, None),
                    (ROWS_QWEN_JUDGED, "verdict_nvidia_h", True, None)):
                data = json.loads(path.read_text())
                ids_only = set(noise_ids(data["rows"])) if only == "noise" else None
                save = lambda d=data, pth=path: pth.write_text(json.dumps(d, indent=1) + "\n")
                print(f"== {path.name} {field} {'(noise control)' if ids_only else ''}", flush=True)
                judge_into(data["rows"], chunks, judge_fn, field=field, headings=headings,
                           log=lambda *a: print(*a, flush=True), save=save, only=ids_only)
                save()
            return
        if "--judge-qwen" in argv:
            if not ROWS_QWEN_JUDGED.exists():
                built = qwen_judge_rows(json.loads(QWEN_LAB.read_text())["D"],
                                        json.loads(ROWS_ALL.read_text())["rows"])
                ROWS_QWEN_JUDGED.write_text(json.dumps({"rows": built}, indent=1) + "\n")
            ROWS = ROWS_QWEN_JUDGED
            argv = argv + ["--judge-nvidia"]
    else:
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
            if not needs_judging(r):
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
    prices = json.loads(PRICES.read_text()) if PRICES.exists() else None
    if all_mode:
        load = lambda p: json.loads(p.read_text())["rows"] if p.exists() else []
        report_all(load(ROWS_ALL), load(ROWS_REPEAT), golden, score.load_chunks(),
                   qwen_lab=json.loads(QWEN_LAB.read_text())["D"],
                   qwen_mac=json.loads(QWEN_MAC.read_text())["D"], prices=prices,
                   qwen_judged=load(ROWS_QWEN_JUDGED))
        return
    rows = json.loads(ROWS.read_text())["rows"]
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
