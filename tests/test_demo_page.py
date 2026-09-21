"""The demo page's hardcoded numbers must match what the repo actually holds.

WHY THIS EXISTS

`space/static/index.html` is a static file. It states how many passages the
corpus holds, how many files they were cut from, and how many golden questions
grade the system. Nothing recomputes those at render time, so without this test
they are four numbers someone typed once -- exactly the failure the measurement
rule in CLAUDE.md exists to stop, and exactly how `seed.py 1013` survived weeks
of green CI after the real figure became 0.

Each number below is derived from a COMMITTED artifact, so this runs in CI where
`corpus/chunks.jsonl` (gitignored, D11) is absent.

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
