"""Host the demo on Modal (FastAPI ASGI over the space/dist bundle).

Why Modal: Hugging Face Gradio Spaces returned HTTP 402 on the free plan
(PHASE-6.md Step 4). Modal's Starter credits fit the ~4 GB RAM the page needs
(BGE-M3 + seat-5 reranker + torch) and scale to zero when idle.

    # once: token + secret (secret name must be `nvidia`, key NVIDIA_API_KEY)
    uv run python space/build.py
    uv run --with modal modal deploy space/modal_app.py

The page is the same `web.py` + `rag/demo.py` path gated in D102. Generator is
NVIDIA (nemotron); the page's notice quotes that model's own measured numbers
(0.58 end to end, D104; 91% supported, D107) and names the 0.42 as qwen's.

Keep DEPS in sync with space/requirements.txt (minus torch — see below). Do not
`Path.read_text()` that file at import time: Modal re-imports this module inside
the container, where only this file is mounted, and a missing requirements.txt
crash-loops the web endpoint.
"""

from __future__ import annotations

from pathlib import Path

import modal

HERE = Path(__file__).resolve().parent
DIST = HERE / "dist"

# Same pins as space/requirements.txt, except torch. Torch is installed first from
# the CPU wheel index so sentence-transformers does not pull the multi-GB CUDA
# build (the page never uses a GPU on Modal).
DEPS = (
    "fastapi==0.141.1",
    "langfuse==4.15.2",     # tracing; active only when the `langfuse` secret supplies keys
    "uvicorn==0.52.4",
    "sentence-transformers==5.7.0",
    "transformers==5.15.0",
    "numpy==2.4.6",
    "huggingface-hub==1.27.0",
)

# HF weights are multi-GB; keep them on a volume so cold starts after the first
# do not re-download BGE-M3 and the reranker every time the container dies.
hf_cache = modal.Volume.from_name("sqlalchemy-upgrade-hf-cache", create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("torch==2.13.0", extra_options="--index-url https://download.pytorch.org/whl/cpu")
    .pip_install(*DEPS)
    .env(
        {
            "RAG_DENSE": "memory",
            "DEMO_GENERATOR": "nvidia",
            "HF_HOME": "/cache/huggingface",
            "TRANSFORMERS_CACHE": "/cache/huggingface",
            "HF_HUB_CACHE": "/cache/huggingface",
        }
    )
    # Mount at container start (default): rebuilds of the image stay cheap while
    # `space/build.py` refreshes the 18 MiB bundle. copy=True would bake it in.
    .add_local_dir(DIST, remote_path="/app")
)

app = modal.App("sqlalchemy-upgrade-agent")


@app.function(
    image=image,
    # `langfuse`: LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY / LANGFUSE_BASE_URL (US region).
    secrets=[modal.Secret.from_name("nvidia"), modal.Secret.from_name("langfuse")],
    volumes={"/cache/huggingface": hf_cache},
    # ~4 GB for the two models + embeddings; headroom so the first load does not OOM.
    memory=8192,
    cpu=2.0,
    timeout=600,          # NVIDIA answer can take ~1 min; first HF download longer
    startup_timeout=600,  # first container may still be pulling HF weights into the volume
    scaledown_window=300, # keep warm a few minutes between questions
    # Modal imports this file as `modal_app` from a mount of space/; leave
    # include_source at its default True. Setting False crash-looped cold starts.
)
@modal.asgi_app(label="sqlalchemy-upgrade-agent")
def fastapi_app():
    import os
    import sys

    # web.py setdefaults RAG_DENSE before importing rag; force it here so a
    # caller who unset the image env cannot accidentally hit Qdrant.
    os.environ["RAG_DENSE"] = "memory"
    os.environ.setdefault("DEMO_GENERATOR", "nvidia")
    os.chdir("/app")
    if "/app" not in sys.path:
        sys.path.insert(0, "/app")
    from web import app as web_app  # after chdir + env so rag sees /app/corpus

    return web_app
