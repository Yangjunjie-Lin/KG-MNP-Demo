from __future__ import annotations

import copy

import run_reasoner as reasoner
import verify_reasoner_report as verifier


def test_current_json_attestation_and_markdown_are_consistent():
    attestation = reasoner.read_json(reasoner.ATTESTATION_PATH)
    markdown = reasoner.MARKDOWN_REPORT_PATH.read_text(encoding="utf-8")
    assert markdown == reasoner.render_reasoner_markdown(attestation)


def test_current_attestation_matches_current_successful_runtime():
    attestation = reasoner.read_json(reasoner.ATTESTATION_PATH)
    runtime = reasoner.read_json(reasoner.RUNTIME_REPORT_PATH)
    assert verifier.validate_runtime_report(runtime) == []
    assert verifier.validate_attestation(attestation, runtime) == []


def test_not_run_attestation_cannot_pass():
    attestation = reasoner.read_json(reasoner.ATTESTATION_PATH)
    runtime = reasoner.read_json(reasoner.RUNTIME_REPORT_PATH)
    invalid = copy.deepcopy(attestation)
    invalid["status"] = reasoner.STATUS_NOT_RUN
    errors = verifier.validate_attestation(invalid, runtime)
    assert any("status" in error and "NOT_RUN" in error for error in errors)


def test_unknown_consistency_cannot_pass():
    attestation = reasoner.read_json(reasoner.ATTESTATION_PATH)
    runtime = reasoner.read_json(reasoner.RUNTIME_REPORT_PATH)
    invalid = copy.deepcopy(attestation)
    invalid["consistency"] = reasoner.UNKNOWN
    errors = verifier.validate_attestation(invalid, runtime)
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


def test_runtime_verifier_rejects_tampered_input_hash():
    runtime = reasoner.read_json(reasoner.RUNTIME_REPORT_PATH)
    invalid = copy.deepcopy(runtime)
    invalid["reasoner_input_semantic_hash"] = "0" * 64
    errors = reasoner.validate_runtime_report(invalid)
    assert any("reasoner_input_semantic_hash" in error for error in errors)


def test_runtime_verifier_recomputes_equivalences_from_reasoned_graph():
    runtime = reasoner.read_json(reasoner.RUNTIME_REPORT_PATH)
    invalid = copy.deepcopy(runtime)
    invalid["inferred_equivalent_classes"] = [
        ["https://example.test/A", "https://example.test/B"]
    ]
    errors = reasoner.validate_runtime_report(invalid)
    assert any("inferred_equivalent_classes" in error for error in errors)
