.PHONY: help install dev lint format test test-cov smoke docker-build docker-run clean

PYTHON ?= python
VENV ?= .venv
BIN := $(VENV)/bin
ifeq ($(OS),Windows_NT)
	BIN := $(VENV)/Scripts
endif

help:
	@echo "SRM PYQ API - common tasks"
	@echo "  make install       Create venv and install dev dependencies"
	@echo "  make dev           Run the API with reload on http://127.0.0.1:8000"
	@echo "  make lint          Run Ruff checks"
	@echo "  make format        Auto-fix and format Python code"
	@echo "  make test          Run the test suite"
	@echo "  make test-cov      Run tests with a coverage report"
	@echo "  make smoke         Smoke test a running API (BASE_URL=...)"
	@echo "  make docker-build  Build the production image"
	@echo "  make docker-run    Run the production image on port 8000"
	@echo "  make clean         Remove caches and build artifacts"

install:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/python -m pip install --upgrade pip
	$(BIN)/python -m pip install -r requirements-dev.txt

dev:
	$(BIN)/python -m uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload

lint:
	$(BIN)/python -m ruff check .
	$(BIN)/python -m ruff format --check .

format:
	$(BIN)/python -m ruff check --fix .
	$(BIN)/python -m ruff format .

test:
	$(BIN)/python -m pytest

test-cov:
	$(BIN)/python -m pytest --cov=api_server --cov-report=term-missing

smoke:
	$(BIN)/python api_smoke_test.py --base-url $(or $(BASE_URL),http://127.0.0.1:8000)

docker-build:
	docker build -t srm-pyq-api:local .

docker-run:
	docker run --rm -p 8000:8000 --env-file .env srm-pyq-api:local

clean:
	rm -rf .pytest_cache .ruff_cache .coverage htmlcov
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
