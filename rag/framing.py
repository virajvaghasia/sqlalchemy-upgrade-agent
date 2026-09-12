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


def report(out: dict) -> None:
    print("\n" + "=" * 62)
    print("SOURCE FRAMING — does the shape of the prompt move the refusals?")
    print("=" * 62)
    print(f"{'':<16}{'page present':>14}{'answered':>10}{'over-refused':>14}")
    for arm, rows in out.items():
        present = [r for r in rows if r["answerable"] and r["answer_in_prompt"]]
        over = [r for r in present if ask.refused(r["answer"])]
        print(f"{arm:<16}{len(present):>14}{len(present) - len(over):>10}"
              f"{len(over):>14}")
    print("\nover-refused = the answer page WAS in the prompt and it declined")
    print("(D72's defect: 19 of 58 on the shipped path over the full 100)")


def main() -> None:
    """`--n` items, both arms, one sitting. Rows saved machine-suffixed (`D83`)."""
    import json as _json
    import sys

    from rag import judge, score

    argv = sys.argv[1:]
    n = int(argv[argv.index("--n") + 1]) if "--n" in argv else 25
    items = [i for i in score.load_golden() if i.get("answerable")][:n]
    out = run(items)
    report(out)
    path = judge.DELIVERABLES / f"framing-phase6.{_machine()}.json"
    path.write_text(_json.dumps({"machine": _machine(), "n": len(items),
                                 "arms": out}, indent=1) + "\n")
    print(f"\nsaved to {path.name}")


def _machine() -> str:
    from rag import faithful
    return faithful.machine()


if __name__ == "__main__":
    main()
