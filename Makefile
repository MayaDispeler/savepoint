.PHONY: test lint up bench report export console api
test:
	uv run pytest -q
lint:
	uv run ruff check .
up:
	docker compose -f docker/ledger.compose.yml up -d
bench:
	uv run python -m savepoint.bench.cli run
report:
	uv run python -m savepoint.bench.cli report
export:
	uv run python -c "from savepoint.ledger.db import Ledger; from savepoint.export.bundle import export; print(export(Ledger('sqlite:///ledger.db')))"
console:
	cd console/public && python -m http.server 8080
api:
	uv run uvicorn savepoint.api.main:app --port 8787
