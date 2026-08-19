"""
Phase 2, Steps 2-3 — the bench for building the golden set by hand.

    uv run python -m rag.golden --status                  # how many verified, what is left
    uv run python -m rag.golden --add "question text"     # append a draft item
    uv run python -m rag.golden --candidates "question"   # top-10 chunks to choose from  [needs Qdrant]
    uv run python -m rag.golden --show c01542             # one chunk in full, and where it lives

WHY THIS EXISTS

`D06` says the golden set is hand-verified, never auto-generated, and
`rag/score.py` enforces it: nothing without `verified_by: "human"` is scored.
That makes ~50 items x ~15 minutes the largest single block of human time in
the project.

**Nothing here verifies anything.** It removes the parts of that 15 minutes
that are clerical rather than judgement: finding candidate chunks, reading one
in full, learning exactly which line of which .rst to open, and getting the
JSON shape right. The reading and the decision stay where D06 puts them.

WHAT --candidates DOES NOT DO

It ranks by the same dense search the system under test uses. So the top hit is
*what the system found*, not *what is correct* -- and on a question phrased the
way a developer would type it, the right chunk may not be in the list at all.
That is not a bug in this tool, it is the measured behaviour the golden set
exists to capture (D60: one question's answer chunk ranks 1 under corpus
vocabulary and outside the top 20 under developer phrasing).

**If the answer is not in the candidates, that is a finding, not a dead end.**
Record the chunk you find by reading, and the item becomes one of the ones that
proves retrieval is failing.
"""

from __future__ import annotations

import json
import pathlib
import sys

from rag import corpus, score


def _load() -> dict:
    return json.loads(score.GOLDEN_PATH.read_text())


def _save(data: dict) -> None:
    score.GOLDEN_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def _next_id(items: list[dict]) -> str:
    used = {int(i["id"][1:]) for i in items if i.get("id", "").startswith("g")}
    return f"g{max(used, default=0) + 1:03d}"


def status() -> None:
    """Progress against D61's target of 50, and what each item still needs."""
    items = _load()["items"]
    verified = [i for i in items if i.get("verified_by") == "human"]
    unanswerable = [i for i in items if not i.get("answerable")]
    print(f"golden set: {len(items)} items, {len(verified)} verified by a human, "
          f"target 50 (D61)")
    print(f"  unanswerable: {len(unanswerable)}  (at least 3 wanted — they are the only way to "
          f"measure whether the system declines when it should)")
    by_prov: dict[str, int] = {}
    for i in items:
        by_prov[i.get("provenance", "?")] = by_prov.get(i.get("provenance", "?"), 0) + 1
    print("  provenance:", ", ".join(f"{k}={v}" for k, v in sorted(by_prov.items())) or "—")
    todo = [i for i in items if i.get("verified_by") != "human"]
    if todo:
        print(f"\nnot yet verified ({len(todo)}):")
        for i in todo:
            need = []
            if i.get("answerable") and not i.get("answer_chunks"):
                need.append("answer_chunks")
            if not (i.get("answer_note") or "").strip():
                need.append("answer_note")
            print(f"  {i['id']}  {i['question'][:62]}")
            if need:
                print(f"        still needs: {', '.join(need)}")


def add(question: str, provenance: str, url: str | None, answerable: bool) -> None:
    """Append a draft item. verified_by stays null — only a person sets that."""
    if provenance not in score.PROVENANCE:
        sys.exit(f"provenance must be one of {sorted(score.PROVENANCE)}")
    data = _load()
    item = {
        "id": _next_id(data["items"]),
        "question": question,
        "provenance": provenance,
        "source_url": url,
        "answerable": answerable,
        "answer_note": "",
        "verified_by": None,
        "verified_on": None,
    }
    if answerable:
        item["answer_chunks"] = []
    data["items"].append(item)
    _save(data)
    print(f"added {item['id']} as a DRAFT. Next:")
    print(f"  uv run python -m rag.golden --candidates {question!r}")
    print(f"  then set answer_chunks, write answer_note, and set verified_by to \"human\".")


def candidates(question: str, limit: int = 10) -> None:
    """Top-`limit` chunks for a question, with the two fields --search omits.

    `rag/index.py --search` prints score, path and heading. It does NOT print
    the chunk id (which is what goes in answer_chunks) or the character offsets
    (which are how you open the .rst at the right spot), so verifying an item
    with it means going back to chunks.jsonl by hand every time.
    """
    from rag import index

    chunks = score.load_chunks()
    hits = index.retrieve(question, limit=limit)
    print(f"\n=== {question}\n")
    for rank, h in enumerate(hits, 1):
        p = h.payload
        cid = p["chunk_id"]
        c = chunks.get(cid, {})
        head = " > ".join(p["heading_path"]) or "(none)"
        print(f"{rank:>2}. {h.score:.3f}  {cid}  {p['sqlalchemy_version']}")
        print(f"    {p['source_path']}  chars {c.get('char_start')}–{c.get('char_end')}")
        print(f"    {head[:96]}")
        print(f"    {p['text'][:180].strip().replace(chr(10), ' ')}…\n")
    print("Read before choosing. If none of these contains the answer, find it by reading and")
    print("record that chunk anyway — a question the system cannot retrieve is the point (D60).")


def show(chunk_id: str) -> None:
    """One chunk in full, plus the exact place in the source it came from."""
    chunks = score.load_chunks()
    c = chunks.get(chunk_id)
    if not c:
        sys.exit(f"no chunk {chunk_id!r} in {score.CHUNKS_PATH.name}")
    raw = corpus.CORPUS_DIR / "raw" / c["sqlalchemy_version"] / c["source_path"].removeprefix("doc/build/")
    print(f"{chunk_id}  {c['sqlalchemy_version']}  {c['n_chars']} chars, code={c['has_code']}")
    print(f"heading: {' > '.join(c['heading_path']) or '(none)'}")
    print(f"source : {c['source_path']}  chars {c['char_start']}–{c['char_end']}")
    if raw.exists():
        # The line number is what a person actually needs to open the file.
        line = raw.read_text(errors="replace")[: c["char_start"]].count("\n") + 1
        print(f"open   : {raw.relative_to(corpus.REPO_ROOT)}  +{line}")
    print("-" * 78)
    print(c["text"])


def main() -> None:
    argv = sys.argv[1:]

    def val(flag: str, default=None):
        return argv[argv.index(flag) + 1] if flag in argv else default

    if "--status" in argv or not argv:
        status()
    elif "--add" in argv:
        add(val("--add"), val("--provenance", "github"), val("--url"),
            answerable="--unanswerable" not in argv)
    elif "--candidates" in argv:
        candidates(val("--candidates"), int(val("--limit", "10")))
    elif "--show" in argv:
        show(val("--show"))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
