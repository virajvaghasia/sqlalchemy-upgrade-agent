"""
Phase 1, Step 2 — cut the corpus into chunks, without cutting anything that
has to stay whole.

    uv run python -m rag.chunk              # chunk, write jsonl + stats, report
    uv run python -m rag.chunk --sample 10  # print N random chunks to eyeball

A chunk is **one retrievable idea**. Too large and the embedding averages
several ideas into mush; too small and it loses the context that made it an
answer. Nothing below is a copied default — the numbers came from measuring
this corpus first.

WHY 1800 CHARACTERS

Measured across all 270 files (the `--stats` numbers this module prints):

    sections         n=2351   median=1274   p75=2569   p90=3816   p99=7149
    literal blocks   n=3811   median=275    p75=489    p90=782    p99=1723

Two facts decide the target, and they point at the same number:

  - **The median reStructuredText section is 1274 characters.** A section is
    already "one idea with a heading on it" — the unit the author chose. A
    target above 1274 means most sections survive as a single chunk instead of
    being cut in half for no reason.
  - **The 99th-percentile code block is 1723 characters.** A budget below that
    guarantees splitting code blocks, and half a `before`/`after` pair is worse
    than neither.

1800 clears both. HARD_MAX is 2400 so a chunk that is already near target can
still absorb one more block rather than emitting a 200-character orphan.

In tokens, 1800 characters of English prose is roughly 450-500, and of code
roughly 600 — comfortably inside BGE-M3's window, and in the range where a hit
is specific enough to be worth returning.

WHAT MUST NOT BE SPLIT, AND WHAT THAT COSTS

  - **Literal blocks.** In RST these are a line ending `::` followed by an
    indented run, or an explicit `.. code-block::`. Never split, even when a
    single one exceeds HARD_MAX — it is emitted alone and counted in the stats
    as an oversized chunk. An honest oversized chunk beats a silently truncated
    example.
  - **Glossary entries.** `glossary.rst` is a single `.. glossary::` directive
    holding every term — 69236 bytes in one indented block at 2.0. Chunked
    naively it is one useless chunk. Split per term instead, since a glossary
    term with its definition is precisely one retrievable idea.

WHAT IS DELIBERATELY NOT DONE

RST markup is left **raw**. `:class:`_orm.Session`` is not rewritten to
`Session`, even though the role syntax is noise to an embedding model and the
rewrite would probably help. Phase 1 is the deliberately naive baseline
(`study/09-DECISIONS.md` D04): a fix applied before its problem has been
measured is a best practice copied from a blog post, not a number earned. If
Step 5 shows markup hurting retrieval, that is a Phase 3 change with a
before/after.
"""

from __future__ import annotations

import json
import pathlib
import random
import re
import statistics
import sys

from rag import corpus

CHUNKS_PATH = corpus.CORPUS_DIR / "chunks.jsonl"
STATS_PATH = corpus.CORPUS_DIR / "CHUNK_STATS.json"

# Derived above. Characters, not tokens: tokenisation is model-specific and
# these have to be stable across whatever embedder Step 3 settles on.
TARGET = 1800
HARD_MAX = 2400

# Overlap is measured in WHOLE BLOCKS, not characters, and this was a
# correction rather than a design. The first version carried `tail[-200:]`
# forward, and the ten-sample review found what that produces: one chunk opened
# with `"sed on"` — a word cut in half — and another opened with an orphaned
# fragment of the previous glossary term, which read as the definition of the
# term that followed it.
#
# The reasoning behind character overlap does not apply here anyway. Overlap
# exists so an answer straddling a boundary is not lost, which matters when the
# boundary is arbitrary. This packer only ever splits between paragraphs and
# code blocks — boundaries the author chose. So the last complete PROSE block
# is carried forward when it is small enough, and nothing is ever truncated.
# Code is never carried: a duplicated half-example is the exact failure this
# module is arranged to avoid.
OVERLAP_MAX = 400

# How much introducing prose a code atom may absorb. In RST the line ending
# `::` is the LAST LINE of the paragraph that introduces the example, so the
# paragraph and the code are one idea. Merging them keeps a chunk that shows
# code from ever being wordless. Capped so a 2000-character essay is not
# duplicated into an example; above the cap only the lead-in line comes along.
LEAD_IN_MAX = 900

# A floor, added after measuring the first run: 415 of 3860 chunks (10.8%) came
# out under 150 characters, and inspection showed they were almost all markup
# rather than short answers — bare `===============` adornment rows, `.. _anchor:`
# link targets, `.. toctree::` blocks. A chunk that carries no prose cannot
# answer anything, but it can still win a short query, so it is worse than
# absent. Anything below this is merged into its neighbour, or dropped.
MIN_CHARS = 120

# Directives that instruct Sphinx rather than say anything. `autoclass` and
# friends are the API-reference generators (D07): at build time they read a
# Python docstring, so in SOURCE they are an empty promise. Deliberately NOT
# listed: note, warning, versionadded, deprecated, seealso, code-block — those
# are content, and often the most quotable content in the file.
NON_CONTENT_DIRECTIVES = frozenset({
    "toctree", "currentmodule", "module", "index", "contents", "include",
    "autoclass", "autofunction", "automethod", "autoattribute", "automodule",
    "autodata", "autoexception", "highlight", "rst-class", "container",
})

# An RST section adornment: a run of one punctuation character. Which character
# means which level is not fixed by the spec — it is decided per document, by
# order of first appearance. See _heading_levels.
ADORNMENT = re.compile(r'^([=\-`:\'"~^_*+#<>!$%&(),./;?@\[\]\\{|}])\1{1,}\s*$')
DIRECTIVE = re.compile(r'^\s*\.\.\s+([a-z-]+)::')
LITERAL_INTRO = re.compile(r'::\s*$')


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------

def split_sections(lines: list[str]) -> list[tuple[list[str], int, int]]:
    """
    Return (heading_path, start_line, end_line) for every section in a file.

    `heading_path` is the full ancestry — ["Working with Data", "Using SELECT
    Statements"] — because headings ARE context. A chunk reading "this was
    removed in 2.0" is useless without the heading naming what "this" is, and
    the path is what gets prepended to the chunk text.
    """
    heads: list[tuple[int, str]] = []          # (line index of title, title text)
    order: list[tuple[str, bool]] = []          # (char, overlined) styles, in order of first use
    levels: list[int] = []

    i = 0
    while i < len(lines):
        line = lines[i]
        if ADORNMENT.match(line) and i > 0:
            title = lines[i - 1].strip()
            # An adornment must be at least as long as the title it underlines.
            # This is what keeps a table's `-----` row from reading as a heading.
            if title and len(line.rstrip()) >= len(title) and not ADORNMENT.match(lines[i - 1]):
                char = line.strip()[0]
                # An OVERLINED title is `===` / title / `===`. Two things hang
                # on detecting it. Without it the overline becomes a chunk of
                # its own — that is how a bare `===============` reached the
                # index on the first run. And per the RST spec **overline+
                # underline is a DIFFERENT level from underline-only with the
                # same character**, which SQLAlchemy relies on: the page title
                # is overlined `===` and its sections are underlined `===`.
                # Keying the level on the character alone collapsed the two,
                # and every section silently lost its parent heading.
                title_line = i - 1
                overlined = (
                    title_line >= 1
                    and ADORNMENT.match(lines[title_line - 1])
                    and lines[title_line - 1].strip()[0] == char
                )
                if overlined:
                    title_line -= 1
                style = (char, bool(overlined))
                if style not in order:
                    order.append(style)
                heads.append((title_line, title))
                levels.append(order.index(style))
        i += 1

    if not heads:
        return [([], 0, len(lines))]

    sections = []
    if heads[0][0] > 0:
        sections.append(([], 0, heads[0][0]))   # preamble before the first heading

    for n, (line_no, title) in enumerate(heads):
        end = heads[n + 1][0] if n + 1 < len(heads) else len(lines)
        path = []
        for m in range(n + 1):
            if levels[m] < levels[n]:
                path = path[:levels[m]] + [heads[m][1]]
            elif m == n:
                path = path[:levels[n]] + [title]
        sections.append((path, line_no, end))
    return sections


def split_blocks(lines: list[str]) -> list[tuple[str, str]]:
    """
    Break a section body into atoms: ("code", text) or ("prose", text).

    A "code" atom is never split by the packer. Everything else is a paragraph,
    which is small enough that splitting between paragraphs loses nothing.
    """
    blocks: list[tuple[str, str]] = []
    buf: list[str] = []
    i = 0

    def flush():
        text = "\n".join(buf).strip("\n")
        if text.strip():
            blocks.append(("prose", text))
        buf.clear()

    while i < len(lines):
        line = lines[i]
        directive = DIRECTIVE.match(line)

        # A glossary directive holds every term in one indented block. Handled
        # by the caller; here it just must not become a single atom.
        if directive and directive.group(1) == "glossary":
            flush()
            i += 1
            continue

        is_code_intro = (
            (directive and directive.group(1) in ("code-block", "sourcecode", "code"))
            or (LITERAL_INTRO.search(line) and line.strip() != "::" or line.strip() == "::")
        )
        if is_code_intro:
            # In RST the line introducing a literal block is the LAST LINE OF
            # THE PARAGRAPH — "...the SQL return type based on the argument
            # given::". Flushing prose here and starting the code atom at the
            # `::` line severs a sentence from its own example: the ten-sample
            # review showed "...based on the" ending one block and "argument
            # given::" starting the next. So the paragraph is pulled INTO the
            # code atom, keeping the sentence and the code it introduces
            # inseparable — which is the point of not splitting code blocks in
            # the first place. Capped, so a long paragraph is not dragged along.
            prefix: list[str] = []
            if buf:
                if len("\n".join(buf)) <= LEAD_IN_MAX:
                    prefix = list(buf)
                    buf.clear()
                else:
                    # Paragraph too long to duplicate wholesale. Keep only its
                    # last line, which is the one ending in `::` and therefore
                    # the one that says what the example demonstrates, and let
                    # the rest stand as its own chunk. Without this the code
                    # atom opens on a fragment like "statement executions::".
                    prefix = [buf.pop()]
                    flush()
            start = i
            i += 1
            # Consume the indented run, blank lines included — a blank line
            # inside a code block does not end it.
            while i < len(lines) and (not lines[i].strip() or lines[i].startswith((" ", "\t"))):
                i += 1
            blocks.append(("code", "\n".join(prefix + lines[start:i]).strip("\n")))
            continue

        if not line.strip():
            flush()
        else:
            buf.append(line)
        i += 1

    flush()
    return blocks


def is_content(text: str) -> bool:
    """
    Does this atom say anything, or is it scaffolding?

    Strip the lines that exist to instruct Sphinx — adornment rows, `.. _anchor:`
    link targets, non-content directives and their `:option:` lines, and the
    indented body of such a directive — and see whether prose remains.

    Kept as a positive test on what survives, rather than a blocklist of shapes,
    so an unfamiliar directive fails safe: unknown markup is treated as content
    and kept, and only the named structural ones are removed.
    """
    kept, skip_indent = [], False
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            skip_indent = False
            continue
        if skip_indent and line.startswith((" ", "\t")):
            continue
        skip_indent = False
        if ADORNMENT.match(line):
            continue
        if re.match(r'^\s*\.\.\s+_[^:]+:\s*$', line):      # .. _anchor:
            continue
        directive = DIRECTIVE.match(line)
        if directive and directive.group(1) in NON_CONTENT_DIRECTIVES:
            skip_indent = True
            continue
        if re.match(r'^\s*:[\w-]+:\s*\S*\s*$', line):      # :maxdepth: 2
            continue
        kept.append(stripped)
    return len(" ".join(kept)) >= 40


def merge_small(chunks: list[str], floor: int) -> list[str]:
    """
    Fold anything under `floor` into its neighbour rather than emitting it.

    Merging beats dropping here because a short chunk is usually a real
    paragraph that simply landed at a section boundary; attaching it to the
    adjacent chunk keeps the sentence in the index. Only a chunk with no
    neighbour at all — a whole section shorter than the floor — is dropped, and
    `is_content` has already removed the markup-only ones by this point.
    """
    out: list[str] = []
    for text in chunks:
        if out and len(text) < floor:
            out[-1] = out[-1] + "\n\n" + text
        elif out and len(out[-1]) < floor:
            out[-1] = out[-1] + "\n\n" + text
        else:
            out.append(text)
    return [c for c in out if len(c) >= floor]


def glossary_entries(lines: list[str]) -> list[tuple[str, str]]:
    """
    One atom per glossary term.

    Terms sit at the directive's base indent; definitions are indented further.
    Consecutive term lines share a definition, which RST allows and SQLAlchemy
    uses ("1.x style / 2.0 style / 1.x-style" are one entry).
    """
    entries: list[tuple[str, str]] = []
    inside = False
    base: int | None = None
    current: list[str] = []

    def flush():
        text = "\n".join(current).strip("\n")
        if text.strip():
            entries.append(("prose", text))
        current.clear()

    for line in lines:
        directive = DIRECTIVE.match(line)
        if directive and directive.group(1) == "glossary":
            inside, base = True, None
            continue
        if not inside:
            continue
        if not line.strip():
            current.append(line)
            continue
        indent = len(line) - len(line.lstrip())
        if base is None and not line.strip().startswith(":"):
            base = indent
        if base is not None and indent == base:
            # A new term starts here — unless the previous line was also a term
            # with no definition yet, in which case they share one.
            if current and any(l.strip() and (len(l) - len(l.lstrip())) > base for l in current):
                flush()
        current.append(line)
    flush()
    return entries


# ---------------------------------------------------------------------------
# Packing
# ---------------------------------------------------------------------------

def pack(blocks: list[tuple[str, str]], target: int, hard_max: int, overlap_max: int):
    """
    Greedily fill chunks up to `target`, never splitting a block.

    Packing runs per section, so overlap never bleeds the end of one section
    into the start of the next — that would attach text to a heading which does
    not describe it, and the heading is the whole point of carrying a path.
    """
    chunks: list[str] = []
    current: list[tuple[str, str]] = []
    size = 0

    def emit():
        text = "\n\n".join(t for _, t in current)
        if text.strip():
            chunks.append(text)

    for kind, text in blocks:
        n = len(text)
        if current and size + n + 2 > target:
            emit()
            # Carry the previous block only if it is a whole prose block and
            # small enough to be worth duplicating. Never a partial slice.
            last_kind, last_text = current[-1]
            current = (
                [(last_kind, last_text)]
                if last_kind == "prose" and len(last_text) <= overlap_max
                else []
            )
            size = sum(len(t) + 2 for _, t in current)
        current.append((kind, text))
        size += n + 2
        if size >= hard_max:
            emit()
            current, size = [], 0

    if current:
        emit()
    return chunks


def chunk_file(path: pathlib.Path, version: str, source_path: str) -> list[dict]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.split("\n")
    out: list[dict] = []

    is_glossary = path.name == "glossary.rst"

    for heading_path, start, end in split_sections(lines):
        body = lines[start:end]
        if is_glossary and any(DIRECTIVE.match(l) and DIRECTIVE.match(l).group(1) == "glossary" for l in body):
            blocks = glossary_entries(body)
        else:
            blocks = split_blocks(body)
        blocks = [(kind, text) for kind, text in blocks if is_content(text)]
        if not blocks:
            continue

        for text_chunk in merge_small(pack(blocks, TARGET, HARD_MAX, OVERLAP_MAX), MIN_CHARS):
            out.append({
                "sqlalchemy_version": version,
                "source_path": source_path,
                "heading_path": heading_path,
                "text": text_chunk,
                "n_chars": len(text_chunk),
                "has_code": "::" in text_chunk or ".. code-block::" in text_chunk,
            })
    return out


# ---------------------------------------------------------------------------
# Drive
# ---------------------------------------------------------------------------

def build() -> list[dict]:
    manifest = json.loads(corpus.MANIFEST_PATH.read_text())
    chunks: list[dict] = []
    for entry in manifest["files"]:
        path = corpus.REPO_ROOT / entry["path"]
        if not path.exists():
            sys.exit(
                f"missing {entry['path']} — run `uv run python -m rag.corpus` first "
                "(corpus/raw/ is fetched, not committed)"
            )
        chunks.extend(chunk_file(path, entry["sqlalchemy_version"], entry["source_path"]))
    for n, chunk in enumerate(chunks):
        chunk["id"] = f"c{n:05d}"
    return chunks


def stats(chunks: list[dict]) -> dict:
    sizes = sorted(c["n_chars"] for c in chunks)
    q = lambda p: sizes[min(len(sizes) - 1, int(len(sizes) * p))]
    by_version: dict[str, int] = {}
    for c in chunks:
        by_version[c["sqlalchemy_version"]] = by_version.get(c["sqlalchemy_version"], 0) + 1
    return {
        "generated_by": "rag/chunk.py",
        "parameters": {"target": TARGET, "hard_max": HARD_MAX, "overlap_max": OVERLAP_MAX},
        "n_chunks": len(chunks),
        "n_chars": sum(sizes),
        "by_version": dict(sorted(by_version.items())),
        "with_code": sum(1 for c in chunks if c["has_code"]),
        "oversized": sum(1 for c in chunks if c["n_chars"] > HARD_MAX),
        "size": {
            "min": sizes[0], "median": int(statistics.median(sizes)),
            "p75": q(0.75), "p90": q(0.90), "p99": q(0.99), "max": sizes[-1],
        },
    }


def report(s: dict) -> None:
    p = s["parameters"]
    print(f"chunks: {CHUNKS_PATH.relative_to(corpus.REPO_ROOT)}")
    print(f"  target={p['target']}  hard_max={p['hard_max']}  overlap_max={p['overlap_max']}")
    print(f"  {s['n_chunks']} chunks   {s['n_chars']} chars")
    for version, n in s["by_version"].items():
        print(f"    {version:<8} {n:>5} chunks")
    print(f"  with a code block: {s['with_code']}   over hard_max: {s['oversized']}")
    z = s["size"]
    print(f"  size  min={z['min']}  median={z['median']}  p75={z['p75']}  "
          f"p90={z['p90']}  p99={z['p99']}  max={z['max']}")


def main() -> None:
    sample = 0
    if "--sample" in sys.argv:
        sample = int(sys.argv[sys.argv.index("--sample") + 1])

    chunks = build()
    CHUNKS_PATH.write_text("".join(json.dumps(c) + "\n" for c in chunks))
    s = stats(chunks)
    STATS_PATH.write_text(json.dumps(s, indent=2) + "\n")
    report(s)

    if sample:
        # Fixed seed: "ten at random" has to mean the same ten every time, or a
        # review of them is not repeatable and cannot be cited.
        rng = random.Random(20260814)
        print(f"\n{'=' * 78}\n{sample} chunks at random (seed 20260814)\n{'=' * 78}")
        for c in rng.sample(chunks, sample):
            print(f"\n--- {c['id']}  {c['sqlalchemy_version']}  {c['source_path']}")
            print(f"    heading: {' > '.join(c['heading_path']) or '(none)'}")
            print(f"    {c['n_chars']} chars, code={c['has_code']}\n")
            print(c["text"])


if __name__ == "__main__":
    main()
