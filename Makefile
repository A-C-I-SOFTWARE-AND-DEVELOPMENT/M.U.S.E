# Makefile — common dev commands for M.U.S.E
# Usage: make <target>

PYTHON := python
UV := uv
RUFF := ruff

.PHONY: help install dev-install test test-fast lint format typecheck clean build docker

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install for production (uv)
	$(UV) sync --extra all

dev-install: ## Install with dev dependencies
	$(UV) sync --extra all --extra dev

test: ## Run all tests
	$(PYTHON) -m pytest tests/ -q --ignore=tests/integration --ignore=tests/e2e -n auto --timeout=30

test-fast: ## Run fast tests only (studio + agent)
	$(PYTHON) -m pytest tests/studio/ tests/agent/ -q -n auto --timeout=30

test-studio: ## Run AAA pipeline tests only
	$(PYTHON) -m pytest tests/studio/ -q -n auto --timeout=30

lint: ## Run ruff linter
	$(RUFF) check .

format: ## Run ruff formatter
	$(RUFF) format .

format-check: ## Check formatting without modifying
	$(RUFF) format --check .

typecheck: ## Run ty type checker
	ty check agent/studio/ tools/ gateway/

clean: ## Remove build artifacts and caches
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf *.egg-info build dist
	rm -rf final_pipeline_output final_proof_game toolchain_output

build: ## Build wheel + sdist
	$(UV) build

lock: ## Regenerate uv.lock
	$(UV) lock

lock-check: ## Verify uv.lock is in sync
	$(UV) lock --check

run-game: ## Run the AAA game pipeline
	$(PYTHON) scripts/run_pipeline.py

verify-slice: ## Verify a UE5 vertical slice
	$(PYTHON) scripts/verify_slice.py

docker: ## Build Docker image
	docker build -t hermes-agent:latest .

docker-run: ## Run Docker container
	docker run -it --rm -p 8642:8642 hermes-agent:latest
