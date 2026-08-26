.PHONY: lint reformat test-local test-integration docs

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests
	uv run ty check src

reformat:
	uv run ruff format src tests
	uv run ruff check --fix src tests

test-local:
	uv run pytest tests -m "not integration"

test-integration:
	uv run pytest tests -m integration
