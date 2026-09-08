PYTHON ?= python

.PHONY: install quality contracts backend frontend browser build verify-release-candidate

install:
	$(PYTHON) -m pip install -c requirements-dev.lock -e ".[dev,webvowl]"
	npm ci --prefix workbench

quality:
	$(PYTHON) -m ruff check .
	$(PYTHON) tools/check_types.py
	npm --prefix workbench run lint
	npm --prefix workbench run typecheck

contracts:
	$(PYTHON) scripts/generate_contract_catalog.py --check
	$(PYTHON) tools/generate_compiler_contracts.py --check

backend:
	$(PYTHON) tools/run_backend_tests.py

frontend:
	npm --prefix workbench test
	npm --prefix workbench run build

browser:
	$(PYTHON) tools/run_browser_verification.py

build:
	$(PYTHON) tools/build_distribution.py

verify-release-candidate:
	$(PYTHON) tools/verify_candidate.py --include-browser
