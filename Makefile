.PHONY: install test check-refs verify-repo-hygiene verify-python-core \
	verify-stage-01 verify-semantic-governance verify-stage-02 \
	verify-ontology-audit verify-ontology-release verify-shacl-profiles \
	verify-legacy-eligibility verify-stage-03-core reasoner-check \
	verify-robot-checksum verify-reasoner-run verify-reasoner-report \
	verify-no-runtime-legacy-terms verify-stage-03

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

verify-ontology-audit:
	python scripts/audit_ontology.py
	python scripts/check_catalog.py
	python -m pytest -q tests/ontology_release/test_stage03_core.py -k "inventory or ownership or catalog or module_config"

verify-ontology-release:
	python scripts/check_ontology_release.py
	python -m pytest -q tests/ontology_release/test_stage03_core.py -k "namespace or bilingual or domain_range or deprecated or mapping_record or example_org or determinism or module_has_ontology"

verify-shacl-profiles:
	python -m pytest -q tests/ontology_release/test_stage03_core.py -k "shape_profiles or foundation or eligibility or case_03"

verify-legacy-eligibility:
	python -m pytest -q tests/test_cli.py tests/cases
	python -m pytest -q tests/ontology_release/test_stage03_core.py -k "competency"

verify-stage-03-core: verify-stage-02 verify-ontology-audit verify-ontology-release \
	verify-shacl-profiles verify-legacy-eligibility

reasoner-check:
	python scripts/run_reasoner.py

verify-robot-checksum:
	python scripts/run_reasoner.py --verify-robot-checksum
	python -m pytest -q tests/reasoner/test_robot_checksum.py

verify-reasoner-run:
	python scripts/verify_reasoner_run.py
	python -m pytest -q \
		tests/reasoner/test_reasoner_input_hash.py \
		tests/reasoner/test_unsatisfiable_parser.py \
		tests/reasoner/test_equivalence_detection.py \
		tests/reasoner/test_reasoner_statuses.py

verify-reasoner-report:
	python scripts/verify_reasoner_report.py
	python -m pytest -q \
		tests/reasoner/test_reasoner_report.py \
		tests/reasoner/test_portable_report.py

verify-no-runtime-legacy-terms:
	python scripts/check_runtime_legacy_terms.py
	python -m pytest -q tests/ontology_release/test_no_runtime_legacy_terms.py

verify-stage-03:
	$(MAKE) verify-stage-03-core
	$(MAKE) verify-robot-checksum
	$(MAKE) reasoner-check
	$(MAKE) verify-reasoner-run
	$(MAKE) verify-reasoner-report
	$(MAKE) verify-no-runtime-legacy-terms
