.PHONY: lint reformat test-local test-integration docs locales

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests
	uv run ty check src

reformat:
	uv run ruff format src tests
	uv run ruff check --fix src tests

locales: ## Compile the .po catalogues to .mo
	uv run pybabel compile -d locales

test-local: locales
	uv run pytest tests -m "not integration"

test-integration:
	# Exit code 5 is pytest's "no tests collected" — expected while no test
	# carries the `integration` marker yet. Anything else still fails the
	# target.
	uv run pytest tests -m integration; status=$$?; \
	if [ $$status -eq 5 ]; then \
		echo "no tests marked 'integration' — nothing to run"; \
		exit 0; \
	fi; \
	exit $$status
