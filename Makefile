.PHONY: install test check-refs verify-repo-hygiene verify-toolchain-foundation \
	verify-python-core \
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
 verify-compiler-cli verify-compiler-semantic-closure verify-stage-06 \
 verify-graphdb-contracts verify-graphdb-policy verify-graphdb-assembly \
 verify-graphdb-package verify-graphdb-queries verify-graphdb-security \
 verify-graphdb-cli verify-graphdb-live verify-graphdb-offline verify-stage-07 \
 verify-webvowl-contracts verify-webvowl-policy verify-webvowl-upstream-lock \
 verify-webvowl-conversion verify-webvowl-determinism verify-webvowl-coverage \
 verify-webvowl-security verify-publication-package verify-webvowl-live \
 verify-stage-08-components verify-stage-08-offline verify-stage-08 \
 verify-application-contracts verify-application-query-registry \
 verify-application-readonly verify-application-traceability \
 verify-application-security verify-application-http verify-application-live \
 verify-application-authority-binding verify-application-live-binding \
 verify-application-rehash-attacks verify-application-foundation-freeze \
 verify-application-phase-01-offline verify-application-phase-01 \
 verify-workbench-contracts verify-workbench-runtime-policy \
 verify-workbench-phase01-freeze verify-workbench-view-model \
 verify-workbench-security verify-workbench-browser verify-workbench-live \
 verify-application-phase-02-offline verify-application-phase-02 \
 verify-diagnostics-contracts verify-diagnostics-policy \
 verify-diagnostics-authority-binding verify-diagnostics-missingness \
 verify-diagnostics-conflicts verify-diagnostics-evidence \
 verify-diagnostics-determinism verify-diagnostics-security \
 verify-diagnostics-browser verify-diagnostics-live \
	 verify-application-phase-03-offline verify-application-phase-03 \
	 verify-governance-contracts verify-governance-state-machine \
	 verify-governance-authority-binding verify-governance-event-chain \
	 verify-governance-stale-protection verify-governance-security \
	 verify-governance-browser verify-governance-live \
	 verify-application-phase-04-offline verify-application-phase-04

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

verify-toolchain-foundation: verify-repo-hygiene
	python -m pytest -q tests/refactor
	python -c "import kg_mnp; print(kg_mnp.__name__)"
	python -m kg_mnp --help
	kg-mnp --help

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

verify-compiler-semantic-closure:
	python -m pytest -q \
		tests/compilation/test_data_property_compilation.py \
		tests/compilation/test_shacl_validation.py \
		tests/compilation/test_shacl_report_determinism.py \
		tests/compilation/test_review_audit.py \
		tests/compilation/test_compilation_contracts.py \
		tests/compilation/test_compiler_policy.py \
		tests/compilation/test_compilation_security.py

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
	$(MAKE) verify-compiler-semantic-closure
	python -m pytest -q tests/compilation/test_stage06_boundaries.py

verify-graphdb-contracts:
	python scripts/check_schema_identifiers.py
	python -m pytest -q tests/graphdb/test_graphdb_contracts.py

verify-graphdb-policy:
	python -m pytest -q tests/graphdb/test_graphdb_policy.py

verify-graphdb-assembly:
	python -m pytest -q \
		tests/graphdb/test_tbox_assembly.py \
		tests/graphdb/test_graphdb_dataset_assembly.py \
		tests/graphdb/test_graphdb_repository_config.py

verify-graphdb-package:
	python -m pytest -q tests/graphdb/test_graphdb_package_reconstruction.py
	python scripts/verify_graphdb_goldens.py

verify-graphdb-queries:
	python -m pytest -q \
		tests/graphdb/test_graphdb_query_suite.py \
		tests/graphdb/test_graphdb_query_normalization.py \
		tests/graphdb/test_graphdb_default_graph_semantics.py \
		tests/graphdb/test_graphdb_review_audit_semantics.py \
		tests/graphdb/test_graphdb_tbox_version_semantics.py

verify-graphdb-security:
	python -m pytest -q \
		tests/graphdb/test_graphdb_client.py \
		tests/graphdb/test_graphdb_import_security.py \
		tests/graphdb/test_graphdb_forbidden_assertions.py \
		tests/graphdb/test_graphdb_live_import.py \
		-k "not graphdb_live_import_is_fail_closed_without_external_license_or_verifies_with_one"

verify-graphdb-cli:
	python -m pytest -q tests/graphdb/test_graphdb_cli.py

verify-graphdb-live:
	python scripts/graphdb_integration.py

verify-graphdb-offline:
	$(MAKE) verify-graphdb-contracts
	$(MAKE) verify-graphdb-policy
	$(MAKE) verify-graphdb-assembly
	$(MAKE) verify-graphdb-package
	$(MAKE) verify-graphdb-queries
	$(MAKE) verify-graphdb-security
	$(MAKE) verify-graphdb-cli
	python -m pytest -q tests/graphdb -k "not live_import"

verify-stage-07:
	$(MAKE) verify-stage-06
	$(MAKE) verify-graphdb-contracts
	$(MAKE) verify-graphdb-policy
	$(MAKE) verify-graphdb-assembly
	$(MAKE) verify-graphdb-package
	$(MAKE) verify-graphdb-queries
	$(MAKE) verify-graphdb-security
	$(MAKE) verify-graphdb-cli
	$(MAKE) verify-graphdb-live
	python -m pytest -q tests/graphdb/test_stage07_boundaries.py

verify-webvowl-contracts:
	python scripts/check_schema_identifiers.py
	python -m pytest -q tests/webvowl/test_stage08_core.py -k "contracts"

verify-webvowl-policy:
	python -m pytest -q tests/webvowl/test_stage08_core.py -k "policy"

verify-webvowl-upstream-lock:
	python -m pytest -q tests/webvowl/test_stage08_core.py -k "frozen or mutable or forged"

verify-webvowl-conversion:
	python scripts/verify_owl2vowl_conversion.py

verify-webvowl-determinism:
	python -m pytest -q tests/webvowl/test_stage08_core.py -k "deterministic"

verify-webvowl-coverage:
	python -m pytest -q tests/webvowl/test_stage08_core.py -k "complete or abox"

verify-webvowl-security:
	python -m pytest -q tests/webvowl/test_stage08_core.py -k "rejects or must_be_compared or validator"

verify-publication-package:
	python -m pytest -q tests/publication

verify-webvowl-live:
	python scripts/webvowl_integration.py

verify-stage-08-components: verify-webvowl-contracts verify-webvowl-policy \
	verify-webvowl-upstream-lock verify-webvowl-determinism \
	verify-webvowl-coverage verify-webvowl-security verify-publication-package
	python -m pytest -q tests/webvowl/test_stage08_boundaries.py tests/webvowl/test_stage08_hardening.py

verify-stage-08-offline: verify-stage-06 verify-graphdb-offline verify-stage-08-components

verify-stage-08: verify-stage-07 verify-stage-08-components verify-webvowl-conversion verify-webvowl-live
	python -m pytest -q tests/webvowl/test_stage08_core.py tests/publication/test_publication_stage08.py

verify-application-contracts:
	python scripts/check_schema_identifiers.py
	python -m pytest -q tests/application/test_application_phase01_contracts.py

verify-application-query-registry:
	python -m pytest -q tests/application/test_query_registry_phase01.py

verify-application-readonly:
	python -m pytest -q \
		tests/application/test_readonly_client_phase01.py \
		tests/application/test_readonly_transport_defense_phase01.py \
		tests/application/test_rdf_term_projection_phase01.py

verify-application-traceability:
	python -m pytest -q \
		tests/application/test_application_queries_phase01.py \
		tests/application/test_golden_queries_phase01.py

verify-application-security:
	python -m pytest -q \
		tests/application/test_query_validation_phase01.py \
		tests/application/test_publication_binding_phase01.py \
		tests/application/test_application_attestation_phase01.py \
		tests/application/test_application_artifact_verifier_phase01.py \
		tests/application/test_application_boundaries_phase01.py

verify-application-http:
	python -m pytest -q tests/application/test_application_http_phase01.py

verify-application-authority-binding:
	python -m pytest -q tests/application/test_publication_authority_reconstruction_phase01.py

verify-application-live-binding:
	python -m pytest -q tests/application/test_live_repository_binding_phase01.py

verify-application-rehash-attacks:
	python -m pytest -q tests/application/test_rehash_attacks_phase01.py

verify-application-foundation-freeze:
	python -m pytest -q \
		tests/application/test_foundation_freeze_phase01.py \
		tests/application/test_root_cli_phase01.py

verify-application-live:
	python scripts/application_integration.py

verify-application-phase-01-offline: verify-application-contracts \
	verify-application-query-registry verify-application-readonly \
	verify-application-traceability verify-application-security \
	verify-application-http verify-application-authority-binding \
	verify-application-live-binding verify-application-rehash-attacks \
	verify-application-foundation-freeze
	python -m pytest -q tests/application

verify-application-phase-01: verify-stage-08 verify-application-phase-01-offline verify-application-live

verify-workbench-contracts:
	python scripts/check_schema_identifiers.py
	python -m pytest -q \
		tests/workbench/test_workbench_contracts.py \
		tests/workbench/test_workbench_package.py

verify-workbench-runtime-policy:
	python -m pytest -q \
		tests/workbench/test_runtime_policy.py \
		tests/workbench/test_runtime_http.py

verify-workbench-phase01-freeze:
	python -m pytest -q tests/workbench/test_phase01_freeze_phase02.py

verify-workbench-view-model:
	python -m pytest -q tests/workbench/test_view_model_fidelity.py

verify-workbench-security:
	python -m pytest -q \
		tests/workbench/test_publication_binding.py \
		tests/workbench/test_relay_security.py \
		tests/workbench/test_xss_security.py \
		tests/workbench/test_phase02_boundaries.py

verify-workbench-browser:
	python -m pytest -q tests/workbench/test_browser_smoke.py

verify-workbench-live:
	python scripts/workbench_integration.py

verify-application-phase-02-offline: verify-application-phase-01-offline \
	verify-workbench-contracts verify-workbench-runtime-policy \
	verify-workbench-phase01-freeze verify-workbench-view-model \
	verify-workbench-security verify-workbench-browser
	python -m pytest -q tests/workbench

verify-application-phase-02: verify-application-phase-01 \
	verify-application-phase-02-offline verify-workbench-live

verify-diagnostics-contracts:
	python scripts/check_schema_identifiers.py
	python -m pytest -q tests/diagnostics/test_contracts.py

verify-diagnostics-policy: verify-diagnostics-contracts
	python -m pytest -q tests/diagnostics/test_contracts.py -k policy

verify-diagnostics-authority-binding: verify-diagnostics-contracts
	python -m pytest -q tests/diagnostics/test_deterministic_diagnostics.py -k reconstruction

verify-diagnostics-missingness: verify-diagnostics-contracts
	python -m pytest -q tests/diagnostics/test_deterministic_diagnostics.py -k rejection

verify-diagnostics-conflicts: verify-diagnostics-contracts
	python -m pytest -q tests/diagnostics/test_deterministic_diagnostics.py -k conflict

verify-diagnostics-evidence: verify-diagnostics-contracts
	python -m pytest -q tests/diagnostics/test_deterministic_diagnostics.py

verify-diagnostics-determinism: verify-diagnostics-contracts
	python -m pytest -q tests/diagnostics/test_deterministic_diagnostics.py -k permutation

verify-diagnostics-security: verify-diagnostics-contracts
	python -m pytest -q tests/diagnostics/test_deterministic_diagnostics.py -k rehash
	ruff check src/kg_mnp/diagnostics scripts/diagnostics_integration.py scripts/verify_application_phase03_artifact.py

verify-diagnostics-browser: verify-diagnostics-contracts
	python -m pytest -q tests/diagnostics/test_runtime_security.py

verify-diagnostics-live: verify-diagnostics-browser
	python scripts/diagnostics_integration.py

verify-application-phase-03-offline: verify-application-phase-02-offline \
	verify-diagnostics-contracts \
	verify-diagnostics-policy verify-diagnostics-authority-binding \
	verify-diagnostics-missingness verify-diagnostics-conflicts \
	verify-diagnostics-evidence verify-diagnostics-determinism \
	verify-diagnostics-security verify-diagnostics-browser
	python -m pytest -q tests/diagnostics

verify-application-phase-03: verify-application-phase-02 \
	verify-application-phase-03-offline verify-diagnostics-live

verify-governance-contracts:
	python scripts/check_schema_identifiers.py
	python -m pytest -q tests/application_governance/test_contracts.py tests/application_governance/test_cli_boundaries.py

verify-governance-state-machine:
	python -m pytest -q tests/application_governance/test_state_machine.py

verify-governance-authority-binding:
	python -m pytest -q tests/application_governance/test_authority_binding.py \
		tests/application_governance/test_contracts.py -k "current_verified or operator_label or phase03 or rehash or publication"

verify-governance-event-chain:
	python -m pytest -q tests/application_governance/test_event_chain.py -k "event_chain or rehash"

verify-governance-stale-protection:
	python -m pytest -q tests/application_governance/test_event_chain.py -k "stale_replay"

verify-governance-security:
	python -m pytest -q tests/application_governance/test_runtime_security.py
	ruff check src/kg_mnp/governance scripts/governance_integration.py scripts/governance_controlled_fixture.py scripts/verify_application_phase04_artifact.py tests/application_governance

verify-governance-browser:
	python -m pytest -q tests/application_governance/test_runtime_security.py -k "xss or pages"

verify-governance-live: verify-governance-browser
	python scripts/governance_integration.py

verify-application-phase-04-offline: verify-application-phase-03-offline \
	verify-governance-contracts verify-governance-state-machine \
	verify-governance-authority-binding verify-governance-event-chain \
	verify-governance-stale-protection verify-governance-security \
	verify-governance-browser
	python -m pytest -q tests/application_governance

verify-application-phase-04: verify-application-phase-03 \
	verify-application-phase-04-offline verify-governance-live

.PHONY: verify-amendment-contracts verify-amendment-authority-binding verify-amendment-input-diff verify-amendment-scope verify-amendment-reentry verify-amendment-review-boundary verify-amendment-determinism verify-amendment-security verify-amendment-republication verify-application-phase-05-offline verify-application-phase-05

verify-amendment-contracts:
	python scripts/check_schema_identifiers.py
	python -m pytest -q tests/amendment/test_contracts.py

verify-amendment-authority-binding:
	python -m pytest -q tests/amendment/test_artifact_closed_set.py

verify-amendment-input-diff:
	python -m pytest -q tests/amendment/test_diff_and_scope.py -k "diff or undeclared"

verify-amendment-scope:
	python -m pytest -q tests/amendment/test_diff_and_scope.py -k "scope or tbox or reopen"

verify-amendment-reentry:
	python -m pytest -q tests/amendment/test_reentry_boundaries.py

verify-amendment-review-boundary:
	python -m pytest -q tests/amendment/test_review_boundary.py

verify-amendment-determinism:
	python -m pytest -q tests/amendment/test_reentry_boundaries.py -k "identity or invariants"

verify-amendment-security:
	ruff check src/kg_mnp/amendment scripts/amendment_controlled_fixture.py scripts/amendment_integration.py scripts/verify_application_phase05_artifact.py tests/amendment
	python -m pytest -q tests/amendment

verify-amendment-republication:
	python -m pytest -q tests/amendment/test_reentry_boundaries.py tests/amendment/test_review_boundary.py
	python scripts/amendment_controlled_fixture.py

verify-application-phase-05-offline: verify-application-phase-04-offline verify-amendment-contracts verify-amendment-authority-binding verify-amendment-input-diff verify-amendment-scope verify-amendment-reentry verify-amendment-review-boundary verify-amendment-determinism verify-amendment-security verify-amendment-republication
	python -m pytest -q tests/amendment

verify-application-phase-05: verify-application-phase-04 verify-application-phase-05-offline
	python scripts/amendment_integration.py

.PHONY: verify-activation-contracts verify-activation-authority-binding \
	verify-activation-state-machine verify-activation-event-chain \
	verify-activation-pointer verify-activation-concurrency \
	verify-activation-rollback verify-activation-security \
	verify-activation-resolver verify-application-phase-06-offline \
	verify-application-phase-06

verify-activation-contracts:
	python scripts/check_schema_identifiers.py
	python -m pytest -q tests/activation/test_contracts.py

verify-activation-authority-binding:
	python -m pytest -q tests/activation/test_authority_binding.py \
		tests/activation/test_phase06_freeze_lower_layers.py \
		tests/activation/test_phase05_public_surface_freeze.py

verify-activation-state-machine:
	python -m pytest -q tests/activation/test_registry_and_validator.py

verify-activation-event-chain:
	python -m pytest -q tests/activation/test_registry_and_validator.py \
		-k "registry or event or rehash"

verify-activation-pointer:
	python -m pytest -q tests/activation/test_registry_and_validator.py \
		tests/activation/test_persistence_and_concurrency.py \
		-k "pointer or generation or state_files or prepared_pair"

verify-activation-concurrency:
	python -m pytest -q tests/activation/test_persistence_and_concurrency.py \
		tests/activation/test_execution_and_resolver.py \
		-k "multiprocessing or concurrency or stale_cas or replay or prepared_pair"

verify-activation-rollback:
	python -m pytest -q tests/activation/test_registry_and_validator.py \
		-k "rollback"

verify-activation-security:
	ruff check src/kg_mnp/activation scripts/activation_controlled_fixture.py \
		scripts/activation_integration.py \
		scripts/verify_application_phase06_artifact.py tests/activation
	python -m pytest -q tests/activation

verify-activation-resolver:
	python -m pytest -q tests/activation/test_execution_and_resolver.py \
		-k "resolver or read_graphdb"

verify-application-phase-06-offline: verify-application-phase-05-offline \
	verify-activation-contracts verify-activation-authority-binding \
	verify-activation-state-machine verify-activation-event-chain \
	verify-activation-pointer verify-activation-concurrency \
	verify-activation-rollback verify-activation-security \
	verify-activation-resolver
	python -m pytest -q tests/activation

verify-application-phase-06: verify-application-phase-05 \
	verify-application-phase-06-offline
	python scripts/activation_integration.py

.PHONY: verify-contract-catalog verify-domain-packs \
	verify-project-workspace verify-prompt-02-offline

verify-contract-catalog:
	python scripts/generate_contract_catalog.py --check
	python -m pytest -q tests/contracts \
		tests/security/test_contract_document_security.py \
		tests/cli/test_contract_cli.py
	kg-mnp contracts list --json
	kg-mnp contracts verify-catalog

verify-domain-packs:
	python scripts/generate_prompt02_pack_manifests.py --check
	python scripts/generate_mnp_prompt01_content_golden.py --check
	python scripts/normalize_domain_pack_text.py --check
	python -m pytest -q tests/domain_packs \
		tests/security/test_domain_pack_security.py \
		tests/cli/test_domain_pack_cli.py
	kg-mnp domain-pack validate domain_packs/minimal
	kg-mnp domain-pack verify-lock domain_packs/minimal
	kg-mnp domain-pack validate domain_packs/mnp
	kg-mnp domain-pack verify-lock domain_packs/mnp
	kg-mnp domain-pack validate domain_packs/forestry
	kg-mnp domain-pack verify-lock domain_packs/forestry

verify-project-workspace:
	python -m pytest -q tests/workspace \
		tests/security/test_workspace_security.py \
		tests/cli/test_workspace_cli.py

verify-prompt-02-offline: verify-toolchain-foundation \
	verify-contract-catalog verify-domain-packs verify-project-workspace
	python -m pytest -q tests/refactor/test_product_docs.py \
		tests/refactor/test_domain_pack_layout.py
	git diff --exit-code

.PHONY: verify-plugin-sdk verify-source-store verify-ingestion-contracts \
	verify-ingestion-parsers verify-evidence-kgir verify-ingestion-security \
	verify-prompt-03-offline

verify-plugin-sdk:
	python -m pytest -q tests/plugins tests/cli/test_plugin_cli.py \
		tests/security/test_plugin_security.py

verify-source-store:
	python -m pytest -q tests/sources tests/cli/test_source_cli.py \
		tests/security/test_source_security.py

verify-ingestion-contracts:
	python scripts/generate_contract_catalog.py --check
	python -m pytest -q tests/contracts/test_ingestion_contracts.py \
		tests/contracts/test_catalog.py tests/contracts/test_wheel_packaging.py

verify-ingestion-parsers:
	python -m pytest -q tests/ingestion/test_parsers_and_media.py \
		tests/security/test_document_parser_security.py

verify-evidence-kgir:
	python -m pytest -q tests/evidence tests/kgir tests/quality \
		tests/cli/test_ingestion_cli.py tests/cli/test_ir_cli.py

verify-ingestion-security:
	python -m pytest -q tests/security/test_plugin_security.py \
		tests/security/test_source_security.py \
		tests/security/test_ingestion_security.py \
		tests/security/test_document_parser_security.py \
		tests/ingestion/test_planner_executor.py

verify-prompt-03-offline: verify-toolchain-foundation verify-contract-catalog \
	verify-domain-packs verify-project-workspace verify-plugin-sdk \
	verify-source-store verify-ingestion-contracts verify-ingestion-parsers \
	verify-evidence-kgir verify-ingestion-security
	python scripts/generate_contract_catalog.py --check
	python scripts/generate_ingestion_examples.py --check
	git diff --exit-code

.PHONY: verify-modeling-scope verify-modeling-baseline \
	verify-modeling-providers verify-modeling-candidates \
	verify-modeling-prevalidation verify-modeling-review \
	verify-modeling-confirmation verify-modeling-security \
	verify-prompt-04-offline

verify-modeling-scope:
	python -m pytest -q tests/modeling_control tests/modeling_scope \
		tests/competency_questions/test_structural_coverage.py

verify-modeling-baseline:
	python -m pytest -q tests/modeling_baseline tests/modeling_terminology \
		tests/modeling_alignment tests/e2e/test_mnp_modeling_compatibility.py

verify-modeling-providers:
	python -m pytest -q tests/modeling_providers tests/cli/test_model_cli.py

verify-modeling-candidates:
	python -m pytest -q tests/modeling_candidates \
		tests/security/test_modeling_candidate_security.py

verify-modeling-prevalidation:
	python -m pytest -q tests/modeling_prevalidation

verify-modeling-review:
	python -m pytest -q tests/modeling_review tests/cli/test_review_cli.py \
		tests/security/test_modeling_review_security.py

verify-modeling-confirmation:
	python -m pytest -q tests/modeling_confirmation \
		tests/security/test_confirmed_package_security.py \
		tests/e2e/test_minimal_modeling_workflow.py

verify-modeling-security:
	python -m pytest -q tests/security/test_modeling_provider_security.py \
		tests/security/test_modeling_candidate_security.py \
		tests/security/test_modeling_review_security.py \
		tests/security/test_confirmed_package_security.py

verify-prompt-04-offline: verify-toolchain-foundation verify-contract-catalog \
	verify-domain-packs verify-project-workspace verify-prompt-03-offline \
	verify-modeling-scope verify-modeling-baseline verify-modeling-providers \
	verify-modeling-candidates verify-modeling-prevalidation \
	verify-modeling-review verify-modeling-confirmation verify-modeling-security
	python scripts/generate_prompt04_contracts.py --check
	python scripts/generate_contract_catalog.py --check
	git diff --exit-code

.PHONY: verify-semantic-kernel-contracts verify-compiler-input \
	verify-tbox-compilation verify-abox-compilation \
	verify-shacl-compilation verify-mapping-compilation verify-rdf-dataset \
	verify-provenance-closure verify-owl-validation \
	verify-shacl-final-validation verify-cq-execution \
	verify-ontology-package verify-semantic-kernel-security \
	verify-prompt-05-offline

verify-semantic-kernel-contracts:
	python scripts/generate_prompt05_contracts.py --check
	python scripts/generate_contract_catalog.py --check
	python -m pytest -q tests/contracts tests/semantic_kernel/test_prompt05_kernel.py -k "contract or catalog or policy or snapshot"

verify-compiler-input:
	python -m pytest -q tests/compiler_input tests/compilation_plan

verify-tbox-compilation:
	python -m pytest -q tests/tbox_compilation

verify-abox-compilation:
	python -m pytest -q tests/abox_compilation

verify-shacl-compilation:
	python -m pytest -q tests/shacl_compilation

verify-mapping-compilation:
	python -m pytest -q tests/mapping_compilation

verify-rdf-dataset:
	python -m pytest -q tests/rdf_canonicalization tests/rdf_dataset

verify-provenance-closure:
	python -m pytest -q tests/provenance_compilation

verify-owl-validation:
	python -m pytest -q tests/owl_validation tests/security/test_reasoner_security.py

verify-shacl-final-validation:
	python -m pytest -q tests/shacl_final_validation

verify-cq-execution:
	python -m pytest -q tests/competency_question_execution tests/security/test_cq_execution_security.py

verify-ontology-package:
	python -m pytest -q tests/ontology_package tests/package_archive \
		tests/compilation_transactions tests/cli/test_compile_cli.py \
		tests/cli/test_package_cli.py

verify-semantic-kernel-security:
	python -m pytest -q tests/security/test_semantic_compiler_security.py \
		tests/security/test_rdf_compilation_security.py \
		tests/security/test_reasoner_security.py \
		tests/security/test_cq_execution_security.py \
		tests/security/test_ontology_package_security.py

verify-prompt-05-offline: verify-toolchain-foundation verify-contract-catalog \
	verify-domain-packs verify-project-workspace verify-prompt-03-offline \
	verify-prompt-04-offline verify-semantic-kernel-contracts \
	verify-compiler-input verify-tbox-compilation verify-abox-compilation \
	verify-shacl-compilation verify-mapping-compilation verify-rdf-dataset \
	verify-provenance-closure verify-owl-validation \
	verify-shacl-final-validation verify-cq-execution \
	verify-ontology-package verify-semantic-kernel-security
	python -m pytest -q tests/semantic_kernel \
		tests/e2e/test_minimal_ontology_package.py \
		tests/e2e/test_mnp_semantic_kernel_compatibility.py
	python scripts/generate_prompt05_contracts.py --check
	python scripts/generate_contract_catalog.py --check
	git diff --exit-code
