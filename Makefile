.PHONY: help setup dev install lint type-check test test-cov check clean

VENV := .
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

help:
	@echo "Term-Timer Development Commands"
	@echo "================================"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make setup          Create virtual environment and install deps"
	@echo "  make install        Install package in development mode"
	@echo "  make install-dev    Install with development dependencies"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint           Check code style with Ruff"
	@echo "  make type-check     Check types with MyPy"
	@echo "  make check          Run all quality checks (lint, type, test)"
	@echo ""
	@echo "Testing:"
	@echo "  make test           Run test suite"
	@echo "  make test-cov       Run tests with coverage report"
	@echo "  make test-short     Run tests without coverage and short traceback"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean          Remove cache, builds, and temp files"
	@echo "  make clean-cov      Remove coverage reports"
	@echo ""

setup: $(VENV)
	$(PIP) install --upgrade pip setuptools wheel
	$(PIP) install -e .[dev]
	@echo ""
	@echo "Setup complete! Activate with: source $(VENV)/bin/activate"

$(VENV):
	python3.12 -m venv $(VENV)

install: $(VENV)
	$(PIP) install -e .

install-dev: $(VENV)
	$(PIP) install -e .[dev]

lint:
	ruff check term_timer
	@echo "✓ Linting passed!"

type-check:
	mypy term_timer --strict
	@echo "✓ Type checking passed!"

test:
	pytest term_timer -q

test-short:
	pytest term_timer -q --tb=short

test-cov:
	pytest term_timer --cov=term_timer --cov-report=html --cov-report=term-missing
	@echo ""
	@echo "Coverage report generated in htmlcov/index.html"

check: lint type-check test
	@echo ""
	@echo "✓ All quality checks passed!"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache build dist *.egg-info
	rm -rf htmlcov .coverage
	@echo "✓ Cleaned up!"

clean-cov:
	rm -rf htmlcov .coverage
	@echo "✓ Coverage reports removed!"

.DEFAULT_GOAL := help
