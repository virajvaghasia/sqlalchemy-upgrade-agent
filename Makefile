# Short names for the commands CI runs. Each target is the same command a CI job
# runs, so `make lint` passing locally means the lint job will pass too.
#
#   make test     the test suite (5 tests skip without Qdrant)
#   make lint     ruff lint, ruff format check, mypy
#   make format   apply the formatter and the linter's safe fixes
#   make demo     the demo page in a container on http://127.0.0.1:7860
#   make gate     the retrieval quality gate against the committed baseline
#
# `demo` and `gate` need the corpus built first (rag.corpus, rag.chunk, rag.embed);
# `gate` also needs Qdrant, which it starts.

.PHONY: test lint format demo gate

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy

format:
	uv run ruff check --fix .
	uv run ruff format .

demo:
	docker compose --profile demo up --build demo

# The same three steps as .github/workflows/gate.yml, minus the caching. Rows go
# to a temporary file: they are this run's output, not a deliverable.
gate:
	docker compose up -d --wait qdrant
	uv run python -m rag.index --recreate
	uv run python -m rag.score --save "$${TMPDIR:-/tmp}/gate-rows.json"
	uv run python -m rag.gate --baseline deliverables/gate-baseline.json --rows "$${TMPDIR:-/tmp}/gate-rows.json"
