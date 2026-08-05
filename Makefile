.PHONY: install test check-refs verify-repo-hygiene verify-python-core

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
