"""Assemble the Hugging Face Space in space/dist/ (gitignored). Nothing is pushed.

    uv run python space/build.py

The corpus files are generated and gitignored in this repo (D11, D36), so the
Space bundle is where they travel: the Space repository is a deployment, not a
second copy of the source of truth. Refuses to build if the vectors, ids and
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
    for f in ("app.py", "requirements.txt", "README.md"):
        shutil.copy(ROOT / "space" / f, DIST / f)
    for f in (ROOT / "rag").glob("*.py"):
        shutil.copy(f, DIST / "rag" / f.name)
    for c in CORPUS:
        shutil.copy(ROOT / "corpus" / c, DIST / "corpus" / c)
    # Hugging Face rejects files over 10 MB unless they are tracked by Git LFS.
    (DIST / ".gitattributes").write_text("*.npy filter=lfs diff=lfs merge=lfs -text\n"
                                         "*.jsonl filter=lfs diff=lfs merge=lfs -text\n")
    size = sum(p.stat().st_size for p in DIST.rglob("*") if p.is_file())
    print(f"built {DIST.relative_to(ROOT)}: {sum(1 for p in DIST.rglob('*') if p.is_file())} files, "
          f"{size / 2**20:.1f} MiB")


if __name__ == "__main__":
    main()
