"""Phase 6, Step 1 — does HOW the sources arrive change whether the model answers?

**The measurement this exists for, from Phase 5.** Same model, same corpus, same
retrieved pages:

    one-shot pipeline   refuses 19 times with the answer page in the prompt
    the agent           refuses 6 (Mac) and 0 (lab)

`D72` named those 19 as generation's defect and Phase 4 could not move them:
`D74` tried five wordings and the refusal count barely shifted. **The agent, not
built for that problem at all, has most of it gone.**

The only structural difference is HOW THE PAGES ARRIVE:

    shipped   one SOURCES block, five passages at once, in a prompt the model
              never asked for, followed by QUESTION and ANSWER.

    agent     the question; then an assistant turn asking for a lookup; then a
              user turn carrying the numbered passages as the RESULT of that
              request; then the model answers.

**No tools are involved in testing this.** The agent's *tool loop* is not the
suspect -- its *conversation shape* is. So arm B replays that shape with no
tools, no loop and no extra model call: the assistant turn is written by us, not
generated. **If the refusals fall anyway, the fix is a prompt change to the
shipped path** and the whole agent apparatus is beside the point.

`D95`: this runs on the Mac first as a SCREEN. Any number that gets quoted is
the lab's, or names both machines.
"""

import json
import urllib.request

from rag import ask

HOST = "http://127.0.0.1:11434"


def sources_block(hits) -> str:
    """Arm A: exactly what ships. `ask.build_prompt` is called, not copied."""
    return ask.build_prompt("", hits).split("\n\n---\n\nQUESTION:")[0]


def as_block(question: str, hits) -> list[dict]:
    """Arm A — one user turn, the shipped prompt verbatim."""
    return [{"role": "system", "content": ask.SYSTEM},
            {"role": "user", "content": ask.build_prompt(question, hits)}]


def as_conversation(question: str, hits) -> list[dict]:
    """Arm B — the agent's shape, with the assistant turn WRITTEN not generated.

    Three changes and no others, so a difference is attributable:
      1. the question arrives FIRST, alone;
      2. an assistant turn asks for the pages;
      3. the pages arrive as the RESULT of that request, then `ANSWER:`.

    **The system prompt, the passages and their numbering are identical to arm
    A.** `ask.SYSTEM` carries the refusal clause every Phase 4 instrument keys
    on, so `ask.refused()` reads both arms the same way (`D76`).
    """
    return [
        {"role": "system", "content": ask.SYSTEM},
        {"role": "user", "content": f"QUESTION: {question}"},
        {"role": "assistant",
         "content": "Let me look that up in the SQLAlchemy documentation."},
        {"role": "user", "content": f"{sources_block(hits)}\n\n---\n\n"
                                    f"QUESTION: {question}\n\nANSWER:"},
    ]


ARMS = {"A_block": as_block, "B_conversation": as_conversation}


def generate(messages: list[dict], model: str = ask.MODEL, post=None) -> str:
    """One call. Temperature and context pinned for the reason `D80` records:
    Ollama truncates at `num_ctx` in silence, and these prompts are ~1600
    tokens before the answer."""
    body = {"model": model, "messages": messages, "stream": False,
            "options": {"temperature": 0.0, "num_ctx": 8192}}
    if post:
        return post(body)
    request = urllib.request.Request(
        f"{HOST}/api/chat", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=300) as response:
        return json.loads(response.read())["message"]["content"]


def run(items, chunks=None, k=None, retrieve=None, gen=None, log=print) -> dict:
    """Both arms over the same items, arms alternating WITHIN each item.

    Retrieval happens ONCE per item and both arms get the identical hits --
    two lookups of one query is how a framing difference becomes a retrieval
    difference (`D78`'s rule, and `faithful.sweep_rows` follows it too).
    """
    from rag import index, score

    chunks = chunks if chunks is not None else score.load_chunks()
    retrieve = retrieve or (lambda q: index.retrieve(q, limit=k or ask.DEFAULT_K))
    out = {arm: [] for arm in ARMS}
    for n, item in enumerate(items, 1):
        hits = retrieve(item["question"])
        ids = [h.payload["chunk_id"] for h in hits]
        in_prompt = score.rank_of_first_hit(ids, item, chunks) is not None
        for arm, build in ARMS.items():
            answer = (gen or generate)(build(item["question"], hits))
            out[arm].append({"id": item["id"], "answer": answer,
                             "answerable": bool(item.get("answerable")),
                             "answer_in_prompt": bool(in_prompt),
                             "n_sources": len(hits)})
            log(f"  {arm} [{n}/{len(items)}] {item['id']} "
                f"{'REFUSED' if ask.refused(answer) else 'answered'}")
    return out


def cells(rows: list[dict]) -> dict:
    """Three rows, because one refusal count hides two opposite things.

    page present  refusing is generation's defect (`D72`) -- fewer is better
    page absent   refusing is the HONEST outcome -- more answers here is a
                  prompt answering without its evidence, not an improvement
    unanswerable  answering is a fabrication, by the same definition
                  `score.report_refusals` uses

    Added 2026-09-12 after the Mac's run: B's six page-present fixes came with
    six page-ABSENT answers A had declined, which is what a more WILLING prompt
    looks like rather than one that reads its pages better. The page-present
    row alone could not tell those apart.
    """
    answerable = [r for r in rows if r["answerable"]]
    present = [r for r in answerable if r["answer_in_prompt"]]
    absent = [r for r in answerable if not r["answer_in_prompt"]]
    unanswerable = [r for r in rows if not r["answerable"]]
    ids = lambda rs: [r["id"] for r in rs]
    return {
        "present": len(present),
        "over_refused": ids(r for r in present if ask.refused(r["answer"])),
        "absent": len(absent),
        "absent_answered": ids(r for r in absent if not ask.refused(r["answer"])),
        "unanswerable": len(unanswerable),
        "fabricated": ids(r for r in unanswerable if not ask.refused(r["answer"])),
    }


def flips(control: list[dict], variant: list[dict]) -> dict:
    """Paired, by item id, per row. `fixed` always means the variant moved in
    the row's GOOD direction, so a willingness shift shows up as fixes in one
    row and breaks in the other rather than cancelling inside one number.

    Items present in only one arm are not paired (`D61`: a paired comparison
    over two different item sets is two averages).
    """
    a = {r["id"]: r for r in control}
    b = {r["id"]: r for r in variant}
    out = {"present": ([], []), "absent": ([], []), "unanswerable": ([], [])}
    for i in sorted(a.keys() & b.keys()):
        ra, rb = a[i], b[i]
        ref_a, ref_b = ask.refused(ra["answer"]), ask.refused(rb["answer"])
        if ref_a == ref_b:
            continue
        if not ra["answerable"]:
            row, good = "unanswerable", ref_b          # refusing is right
        elif ra["answer_in_prompt"]:
            row, good = "present", not ref_b           # answering is right
        else:
            row, good = "absent", ref_b                # declining is honest
        (out[row][0] if good else out[row][1]).append(i)
    return out


def report(out: dict) -> None:
    from rag import score

    print("\n" + "=" * 70)
    print("SOURCE FRAMING — does the shape of the prompt move the refusals?")
    print("=" * 70)
    print(f"{'':<16}{'page present':>13}{'over-refused':>13}"
          f"{'page absent':>12}{'answered':>9}{'unans.':>7}{'fabr':>5}")
    for arm, rows in out.items():
        c = cells(rows)
        print(f"{arm:<16}{c['present']:>13}{len(c['over_refused']):>13}"
              f"{c['absent']:>12}{len(c['absent_answered']):>9}"
              f"{c['unanswerable']:>7}{len(c['fabricated']):>5}")
    print("\nover-refused = the answer page WAS in the prompt and it declined")
    print("(D72's defect: 19 of 58 on the shipped path over the full 100)")
    print("answered (page absent) = answered WITHOUT the verified page; declining")
    print("there is honest, so a rise is willingness, not reading")
    if any(cells(rows)["unanswerable"] == 0 for rows in out.values()):
        print("!! an arm has no unanswerable items -- fabrication NOT measured")

    arms = list(out)
    if len(arms) == 2:
        f = flips(out[arms[0]], out[arms[1]])
        print(f"\npaired, {arms[1]} against {arms[0]}"
              f" (fixed = moved in that row's good direction):")
        for row, (fixed, broken) in f.items():
            print(f"  {row:<13} fixed {len(fixed):>2}  broken {len(broken):>2}"
                  f"  p = {score.mcnemar_exact(len(fixed), len(broken)):.4f}")
            if fixed:
                print(f"    fixed   {' '.join(fixed)}")
            if broken:
                print(f"    broken  {' '.join(broken)}")


def select_items(golden: list[dict], n: int) -> list[dict]:
    """The first `n` answerable items, THEN every unanswerable one.

    The answerable slice is exactly what the first runs took, so the
    page-present row stays comparable with them; the unanswerable items are
    appended rather than interleaved so `--n` keeps meaning what it meant.
    """
    answerable = [i for i in golden if i.get("answerable")][:n]
    return answerable + [i for i in golden if not i.get("answerable")]


def main() -> None:
    """Both arms, one sitting. Rows saved machine-suffixed (`D83`).

    --n N              first N answerable items, plus all unanswerable ones
    --report           re-print the saved file for this machine, no model
    --unanswerable     generate ONLY the unanswerable items and merge them into
                       this machine's saved file -- for a run that predates
                       them, so its answerable rows are not regenerated (`D54`)
    """
    import json as _json
    import sys

    from rag import judge, score

    argv = sys.argv[1:]
    path = judge.DELIVERABLES / f"framing-phase6.{_machine()}.json"
    if "--report" in argv:
        report(_json.loads(path.read_text())["arms"])
        return
    golden = score.load_golden()
    if "--unanswerable" in argv:
        saved = _json.loads(path.read_text())
        have = {r["id"] for r in saved["arms"]["A_block"]}
        items = [i for i in golden if not i.get("answerable") and i["id"] not in have]
        for arm, rows in run(items).items():
            saved["arms"][arm].extend(rows)
        saved["unanswerable_added"] = [i["id"] for i in items]
        out = saved
    else:
        n = int(argv[argv.index("--n") + 1]) if "--n" in argv else 25
        items = select_items(golden, n)
        out = {"machine": _machine(), "n": len(items), "arms": run(items)}
    report(out["arms"])
    path.write_text(_json.dumps(out, indent=1) + "\n")
    print(f"\nsaved to {path.name}")


def _machine() -> str:
    from rag import faithful
    return faithful.machine()


if __name__ == "__main__":
    main()
