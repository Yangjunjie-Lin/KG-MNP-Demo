.PHONY: install test check-refs verify-repo-hygiene verify-python-core \
	verify-stage-01 verify-semantic-governance verify-stage-02

PYTHON_CORE_TESTS = \
	tests/test_ontology.py \
	tests/test_shacl.py \
	tests/test_inference.py \
	tests/test_mappings.py \
	tests/test_input_adapter.py \
	tests/test_rdf_builder.py \
	tests/ontology \
	tests/scripts/test_repo_hygiene.py

install:
	python -m pip install -e ".[dev]"

test:
	python -m pytest

check-refs:
	python scripts/check_references.py

verify-repo-hygiene:
	python scripts/check_repo_hygiene.py

verify-python-core: verify-repo-hygiene check-refs
	python -m pytest $(PYTHON_CORE_TESTS)

verify-stage-01: verify-python-core
	python -m pytest -q tests/governance/test_stage_01_closure.py

verify-semantic-governance:
	python -m pytest -q tests/governance

verify-stage-02: verify-stage-01 verify-semantic-governance
