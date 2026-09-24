"""The demo page's hardcoded numbers must match what the repo actually holds.

WHY THIS EXISTS

`space/static/index.html` is a static file. It states how many passages the
corpus holds, how many files they were cut from, and how many golden questions
grade the system. Nothing recomputes those at render time, so without this test
they are four numbers someone typed once -- exactly the failure the measurement
rule exists to stop, and exactly how `seed.py 1013` survived weeks
of green CI after the real figure became 0.

Each number below is derived from a COMMITTED artifact, so this runs in CI where
`corpus/chunks.jsonl` (gitignored) is absent.

It deliberately does NOT pin the measured rates (64%, 0.42). Those live in
`deliverables/` and in the register; re-deriving them here would need Qdrant and
a model, and `tools/check_page.py` plus `rag.score` already own them.
"""

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAGE = ROOT / "space" / "static" / "index.html"


def page_text() -> str:
    return PAGE.read_text(encoding="utf-8")


def test_passage_count_matches_the_committed_chunk_stats():
    n = json.loads((ROOT / "corpus" / "CHUNK_STATS.json").read_text())["n_chunks"]
    # the page writes it with a thousands separator
    assert f"{n:,}" in page_text(), f"page should say {n:,} passages"


def test_corpus_file_count_matches_the_manifest():
    n = len(json.loads((ROOT / "corpus" / "MANIFEST.json").read_text())["files"])
    assert re.search(rf"\b{n} files\b", page_text()), f"page should say {n} files"


def test_golden_counts_match_the_golden_set():
    items = json.loads((ROOT / "deliverables" / "golden.json").read_text())["items"]
    unanswerable = sum(1 for i in items if i.get("answerable") is False)
    text = page_text()
    assert re.search(rf"\b{len(items)} questions\b", text), f"page should say {len(items)} questions"
    assert f"<dt>{len(items)}</dt>" in text, "the figure block should show the golden set size"
    assert f"<dt>{unanswerable}</dt>" in text, f"the figure block should show {unanswerable} unanswerable"


def test_real_question_split_matches_the_golden_set():
    items = json.loads((ROOT / "deliverables" / "golden.json").read_text())["items"]
    so = sum(1 for i in items if i.get("provenance") == "stackoverflow")
    gh = sum(1 for i in items if i.get("provenance") == "github")
    text = page_text()
    assert f"{so} come from Stack Overflow" in text, f"page should say {so} from Stack Overflow"
    assert f"{gh} from GitHub" in text, f"page should say {gh} from GitHub"
    assert f"other {len(items) - so - gh} were written here" in text


def test_the_page_states_the_number_of_sources_the_prompt_gets():
    from rag import ask
    # sentence-initial capital, so the count is what is asserted, not the spelling
    assert re.search(rf"\b{'five' if ask.DEFAULT_K == 5 else ask.DEFAULT_K} pages go into one prompt",
                     page_text(), re.IGNORECASE), f"page should match DEFAULT_K = {ask.DEFAULT_K}"


def parse_breakages() -> list[dict]:
    """The 23 entries of deliverables/BREAKAGES.md, reduced to what the page shows: number,
    group, the 1.4 call, the exception 2.0.51 raised (None for the silent #23) and its message.
    The page's "What breaks in 2.0" index is generated from this and must stay equal to it."""
    lines = (ROOT / "deliverables" / "BREAKAGES.md").read_text(encoding="utf-8").splitlines()
    out, group = [], None
    for i, ln in enumerate(lines):
        m = re.match(r"## Group ([A-H]) — (.+?)(?: \(#[\d–-]+\))?$", ln)
        if m:
            group = (m.group(1), re.sub(r"^#\d+ ", "", m.group(2)))
            continue
        m = re.match(r"### (\d+)\. (.+)$", ln)
        if not m:
            continue
        j = next(k for k in range(i, len(lines)) if lines[k].startswith("**2.0 error**"))
        cls = re.search(r"`([^`]+)`", lines[j])
        k = next(k for k in range(j + 1, len(lines)) if lines[k].startswith("```"))
        block = []
        for b in lines[k + 1:]:
            if b.startswith("```"):
                break
            block.append(b.strip())
        # an error message wrapped over several lines is one message; the silent #23 shows
        # its measurement instead, and the line that matters is the row that never arrived
        msg = " ".join(block) if cls else block[-1]
        out.append({"n": int(m.group(1)), "group": group[0], "gname": group[1], "title": m.group(2),
                    "error": cls.group(1) if cls else None, "msg": re.sub(r"\s+", " ", msg)})
    return out


def test_breakage_index_matches_breakages_md():
    page = page_text()
    m = re.search(r"const BREAKAGES = (\[.*?\]);\n", page, re.S)
    assert m, "page should embed the BREAKAGES index"
    assert json.loads(m.group(1)) == parse_breakages(), \
        "the page's breakage index drifted from deliverables/BREAKAGES.md; regenerate it"


def test_breakage_count_in_prose_matches():
    n = len(parse_breakages())
    assert re.search(rf"\b{n} changes that break", page_text()), f"page should say {n} changes that break"
