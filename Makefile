.PHONY: install test check-refs verify-repo-hygiene verify-python-core \
	verify-stage-01 verify-semantic-governance verify-stage-02 \
	verify-ontology-audit verify-ontology-release verify-shacl-profiles \
	verify-legacy-eligibility verify-stage-03-core reasoner-check \
	verify-robot-checksum verify-reasoner-run verify-reasoner-report \
	verify-no-runtime-legacy-terms verify-schema-identifiers verify-stage-03 \
	verify-modeling-contracts verify-modeling-dependencies \
	verify-modeling-proposal verify-modeling-determinism \
	verify-modeling-cli verify-stage-04 \
	verify-review-contracts verify-review-policy verify-review-workflow \
	verify-review-determinism verify-confirmed-package verify-package-readiness \
 verify-review-security verify-review-cli verify-stage-05 \
 verify-compiler-contracts verify-compiler-policy verify-compiler-mapping \
 verify-compiler-provenance verify-compiler-rdf verify-compiler-shacl \
 verify-compiler-reasoner verify-compiler-determinism verify-compiler-security \
 verify-compiler-cli verify-stage-06

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

verify-schema-identifiers:
	python scripts/check_schema_identifiers.py
	python -m pytest -q tests/schema_governance

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
	$(MAKE) verify-schema-identifiers
	$(MAKE) verify-robot-checksum
	$(MAKE) reasoner-check
	$(MAKE) verify-reasoner-run
	$(MAKE) verify-reasoner-report
	$(MAKE) verify-no-runtime-legacy-terms

verify-modeling-contracts:
	python scripts/check_schema_identifiers.py
	python -m pytest -q \
		tests/modeling/test_contract_registry.py \
		tests/modeling/test_cleaned_partial_data_contract.py \
		tests/modeling/test_modeling_proposal_contract.py \
		tests/modeling/test_review_decision_log_contract.py \
		tests/modeling/test_confirmed_package_contract.py

verify-modeling-dependencies:
	python scripts/verify_ontology_baseline_manifest.py
	python -m pytest -q \
		tests/modeling/test_ontology_baseline_manifest.py \
		tests/modeling/test_mapping_rules.py \
		tests/modeling/test_terminology_profile.py

verify-modeling-proposal:
	python -m pytest -q \
		tests/modeling/test_proposal_generation.py \
		tests/modeling/test_missing_semantics.py \
		tests/modeling/test_null_semantics.py \
		tests/modeling/test_conflict_semantics.py \
		tests/modeling/test_unmapped_fields.py \
		tests/modeling/test_confidence_semantics.py \
		tests/modeling/test_no_tbox_generation.py

verify-modeling-determinism:
	python -m pytest -q \
		tests/modeling/test_canonical_json.py \
		tests/modeling/test_stable_identifiers.py \
		tests/modeling/test_transformations.py \
		tests/modeling/test_determinism.py

verify-modeling-cli:
	python -m pytest -q tests/modeling/test_modeling_cli.py

verify-stage-04:
	$(MAKE) verify-stage-03
	$(MAKE) verify-modeling-contracts
	$(MAKE) verify-modeling-dependencies
	$(MAKE) verify-modeling-proposal
	$(MAKE) verify-modeling-determinism
	$(MAKE) verify-modeling-cli
	python -m pytest -q tests/modeling/test_stage04_boundaries.py

verify-review-contracts:
	python scripts/check_schema_identifiers.py
	python -m pytest -q \
		tests/review/test_review_action_contract.py \
		tests/review/test_review_policy.py

verify-review-policy:
	python -m pytest -q tests/review/test_review_policy.py

verify-review-workflow:
	python -m pytest -q \
		tests/review/test_review_init.py \
		tests/review/test_review_record.py \
		tests/review/test_review_status.py \
		tests/review/test_review_finalize.py \
		tests/review/test_review_coverage.py \
		tests/review/test_candidate_decisions.py \
		tests/review/test_issue_decisions.py \
		tests/review/test_modified_candidate.py

verify-review-determinism:
	python -m pytest -q \
		tests/review/test_review_identifiers.py \
		tests/review/test_review_log_hash.py \
		tests/review/test_review_log_determinism.py

verify-confirmed-package:
	python -m pytest -q \
		tests/review/test_confirmation_builder.py \
		tests/review/test_confirmed_item_identity.py \
		tests/review/test_reference_closure.py \
		tests/review/test_term_type_validation.py \
		tests/review/test_package_hash.py \
		tests/review/test_package_determinism.py \
		tests/review/test_malicious_cases.py

verify-package-readiness:
	python -m pytest -q tests/review/test_package_readiness.py

verify-review-security:
	python -m pytest -q \
		tests/review/test_review_finalization_fail_closed.py \
		tests/review/test_package_reconstruction_validation.py \
		tests/review/test_full_dependency_binding.py \
		tests/review/test_review_policy_fail_closed.py \
		tests/review/test_package_validation_cli_security.py \
		tests/review/test_review_finalize_cli_security.py

verify-review-cli:
	python -m pytest -q \
		tests/review/test_review_cli.py \
		tests/review/test_confirmation_cli.py

verify-stage-05:
	$(MAKE) verify-stage-04
	$(MAKE) verify-review-contracts
	$(MAKE) verify-review-policy
	$(MAKE) verify-review-workflow
	$(MAKE) verify-review-determinism
	$(MAKE) verify-confirmed-package
	$(MAKE) verify-package-readiness
	$(MAKE) verify-review-security
	$(MAKE) verify-review-cli
	python -m pytest -q tests/review/test_stage05_boundaries.py

verify-compiler-contracts:
	python scripts/check_schema_identifiers.py
	python -m pytest -q tests/compilation/test_compilation_contracts.py tests/compilation/test_compiler_policy.py

verify-compiler-policy:
	python -m pytest -q tests/compilation/test_compiler_policy.py

verify-compiler-mapping:
	python -m pytest -q tests/compilation/test_candidate_resolution.py tests/compilation/test_entity_compilation.py tests/compilation/test_class_assertion_compilation.py tests/compilation/test_object_property_compilation.py tests/compilation/test_data_property_compilation.py tests/compilation/test_mapping_assertion_rejected.py tests/compilation/test_tbox_leakage.py

verify-compiler-provenance:
	python -m pytest -q tests/compilation/test_graph_separation.py tests/compilation/test_provenance_coverage.py tests/compilation/test_review_audit.py

verify-compiler-rdf:
	python -m pytest -q tests/compilation/test_no_blank_nodes.py tests/compilation/test_canonical_ntriples.py tests/compilation/test_canonical_nquads.py tests/compilation/test_deterministic_turtle.py tests/compilation/test_deterministic_trig.py

verify-compiler-shacl:
	python -m pytest -q tests/compilation/test_shacl_profile.py tests/compilation/test_shacl_validation.py tests/compilation/test_shacl_report_determinism.py

verify-compiler-reasoner:
	python -m pytest -q tests/compilation/test_owl_consistency.py

verify-compiler-determinism:
	python -m pytest -q tests/compilation/test_compilation_manifest.py tests/compilation/test_artifact_hashes.py tests/compilation/test_compilation_determinism.py tests/compilation/test_compilation_reconstruction.py

verify-compiler-security:
	python -m pytest -q tests/compilation/test_compilation_security.py

verify-compiler-cli:
	python -m pytest -q tests/compilation/test_compilation_cli.py

verify-stage-06:
	$(MAKE) verify-stage-05
	$(MAKE) verify-compiler-contracts
	$(MAKE) verify-compiler-policy
	$(MAKE) verify-compiler-mapping
	$(MAKE) verify-compiler-provenance
	$(MAKE) verify-compiler-rdf
	$(MAKE) verify-compiler-shacl
	$(MAKE) verify-compiler-reasoner
	$(MAKE) verify-compiler-determinism
	$(MAKE) verify-compiler-security
	$(MAKE) verify-compiler-cli
	python -m pytest -q tests/compilation/test_stage06_boundaries.py
