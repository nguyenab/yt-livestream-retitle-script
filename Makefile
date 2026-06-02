.PHONY: test lint fmt check

VENV ?= .venv
PY := $(VENV)/bin/python

test:
	$(PY) -m pytest

lint:
	$(PY) -m ruff check .

fmt:
	$(PY) -m ruff check --fix .

check: lint test
