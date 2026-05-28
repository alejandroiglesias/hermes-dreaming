PYTHON ?= .venv/bin/python
TESTS ?= tests

.PHONY: test
test:
	@test -x "$(PYTHON)" || (echo "Missing $(PYTHON). Run: python3 -m venv .venv && .venv/bin/python -m pip install -e '.[dev]'"; exit 1)
	$(PYTHON) -m pytest $(TESTS)
