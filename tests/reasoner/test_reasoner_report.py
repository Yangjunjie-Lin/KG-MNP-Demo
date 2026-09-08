from __future__ import annotations

import copy

import run_reasoner as reasoner
import verify_reasoner_report as verifier


def test_current_json_attestation_and_markdown_are_consistent():
    attestation = reasoner.read_json(reasoner.ATTESTATION_PATH)
    markdown = reasoner.MARKDOWN_REPORT_PATH.read_text(encoding="utf-8")
    assert markdown == reasoner.render_reasoner_markdown(attestation)


def test_current_attestation_matches_current_successful_runtime(actual_reasoner_report):
    attestation = reasoner.read_json(reasoner.ATTESTATION_PATH)
    runtime, options = actual_reasoner_report
    assert verifier.validate_runtime_report(runtime, **options) == []
    assert verifier.validate_attestation(attestation, runtime, root=options["root"]) == []


def test_not_run_attestation_cannot_pass(actual_reasoner_report):
    attestation = reasoner.read_json(reasoner.ATTESTATION_PATH)
    runtime, options = actual_reasoner_report
    invalid = copy.deepcopy(attestation)
    invalid["status"] = reasoner.STATUS_NOT_RUN
    errors = verifier.validate_attestation(invalid, runtime, root=options["root"])
    assert any("status" in error and "NOT_RUN" in error for error in errors)


def test_unknown_consistency_cannot_pass(actual_reasoner_report):
    attestation = reasoner.read_json(reasoner.ATTESTATION_PATH)
    runtime, options = actual_reasoner_report
    invalid = copy.deepcopy(attestation)
    invalid["consistency"] = reasoner.UNKNOWN
    errors = verifier.validate_attestation(invalid, runtime, root=options["root"])
    assert any("consistency" in error and "UNKNOWN" in error for error in errors)


def test_release_hash_and_actual_input_hash_are_separate_fields():
    attestation = reasoner.read_json(reasoner.ATTESTATION_PATH)
    assert len(attestation["release_source_hash"]) == 64
    assert len(attestation["reasoner_input_semantic_hash"]) == 64
    assert len(attestation["reasoner_input_file_hash"]) == 64
    assert "release_source_hash" in attestation
    assert "reasoner_input_semantic_hash" in attestation
    assert "reasoner_input_file_hash" in attestation
    assert attestation["rdflib_version"] == reasoner.EXPECTED_RDFLIB_VERSION


def test_runtime_verifier_rejects_tampered_input_hash(actual_reasoner_report):
    runtime, options = actual_reasoner_report
    invalid = copy.deepcopy(runtime)
    invalid["reasoner_input_semantic_hash"] = "0" * 64
    errors = reasoner.validate_runtime_report(invalid, **options)
    assert any("reasoner_input_semantic_hash" in error for error in errors)


def test_runtime_verifier_recomputes_equivalences_from_reasoned_graph(actual_reasoner_report):
    runtime, options = actual_reasoner_report
    invalid = copy.deepcopy(runtime)
    invalid["inferred_equivalent_classes"] = [
        ["https://example.test/A", "https://example.test/B"]
    ]
    errors = reasoner.validate_runtime_report(invalid, **options)
    assert any("inferred_equivalent_classes" in error for error in errors)
