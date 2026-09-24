"""Assemble the deployable demo in space/dist/ (gitignored). Nothing is pushed.

    uv run python space/build.py

The bundle is the hand-designed page: `web.py` (FastAPI) and `static/index.html`
over `rag/demo.py`. It used to ship the Gradio page `app.py`, for a Hugging Face
Gradio Space; Hugging Face refused that on the free plan (HTTP 402), so the target is now any Python host with ~4 GB RAM, and `app.py` stays
in the repo only. Start the bundle with:

    cd space/dist && pip install -r requirements.txt && python web.py   # HOST=0.0.0.0 PORT=... on a server

The corpus files are generated and gitignored in this repo, so the
bundle is where they travel: a deployment, not a second copy of the source of
truth. Refuses to build if the vectors, ids and
stats disagree -- the same check rag.index makes before loading anything.
"""

import json
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIST = ROOT / "space" / "dist"
CORPUS = ["chunks.jsonl", "embeddings.npy", "embeddings.ids.json", "EMBED_STATS.json", "MANIFEST.json"]


def main() -> None:
    missing = [c for c in CORPUS if not (ROOT / "corpus" / c).exists()]
    if missing:
        sys.exit(f"missing corpus files {missing}: run rag.corpus, rag.chunk, rag.embed first")
    stats = json.loads((ROOT / "corpus" / "EMBED_STATS.json").read_text())
    ids = json.loads((ROOT / "corpus" / "embeddings.ids.json").read_text())
    if stats["n_vectors"] != len(ids):
        sys.exit(f"EMBED_STATS says {stats['n_vectors']} vectors, ids file has {len(ids)}")

    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / "rag").mkdir(parents=True)
    (DIST / "corpus").mkdir()
    for f in ("web.py", "requirements.txt", "README.md"):
        shutil.copy(ROOT / "space" / f, DIST / f)
    shutil.copytree(ROOT / "space" / "static", DIST / "static")
    for f in (ROOT / "rag").glob("*.py"):
        shutil.copy(f, DIST / "rag" / f.name)
    for c in CORPUS:
        shutil.copy(ROOT / "corpus" / c, DIST / "corpus" / c)
    # Only matters if the bundle is pushed to a git host that caps file size (Hugging Face: 10 MB).
    (DIST / ".gitattributes").write_text("*.npy filter=lfs diff=lfs merge=lfs -text\n"
                                         "*.jsonl filter=lfs diff=lfs merge=lfs -text\n")
    size = sum(p.stat().st_size for p in DIST.rglob("*") if p.is_file())
    print(f"built {DIST.relative_to(ROOT)}: {sum(1 for p in DIST.rglob('*') if p.is_file())} files, "
          f"{size / 2**20:.1f} MiB")


if __name__ == "__main__":
    main()
