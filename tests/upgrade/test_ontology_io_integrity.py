"""Offline protocol/budget/inventory tests; never live model measurements."""
from copy import deepcopy
from types import SimpleNamespace

import pytest
from jsonschema import ValidationError

from tests.upgrade.test_ontology_io import empty_report
from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.ontology_io.adapters import adapt_llms4ol, additions_only
from zhigou_toolchain.ontology_io.cli import verify_sample_inventory
from zhigou_toolchain.ontology_io.contracts import Protocol
from zhigou_toolchain.ontology_io.engine import generate_sample
from zhigou_toolchain.ontology_io.reports import inspect_report
from zhigou_toolchain.ontology_io.statistics import holm_adjust


def sample():
    return adapt_llms4ol({"id": "s1", "context": "Oak is a tree."}, task="flagship")


def protocol(**extra):
    return Protocol(model_id="fixture-not-live", declared_revision="fixture-v1", protocol_id="offline-boundary",
        systems=["DirectGeneralLLM", "TwoAgentV3", "DirectBudgetControl"], **extra)


class RecordedClient:
    lock = SimpleNamespace(model_id="fixture-not-live")
    last_public_response = None

    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.inputs = []

    def propose(self, instruction, content, schema):
        from jsonschema import validate
        self.inputs.append(deepcopy(content))
        value = next(self.outputs)
        if isinstance(value, Exception):
            raise value
        validate(value, schema)
        return {"proposal": value, "execution_source": "RECORDED", "usage": {"total_tokens": None},
            "model": {"observed_model_id": "fixture-not-live"}}


def test_unknown_usage_is_retained_as_null_not_zero_or_failed_output(tmp_path):
    client = RecordedClient([{"triples": []}])
    result = generate_sample(sample(), protocol(), "DirectGeneralLLM", tmp_path / "case", client=client)
    assert result["status"] == "GENERATED"
    assert result["resources"]["reported_total_tokens"] is None
    assert result["resources"]["cost"] is None
    assert result["prediction"]["triples"] == []
    assert result["approval"] == "UNREVIEWED_EVAL_DRAFT" and result["release_status"] == "NOT_RELEASED"


def test_actual_five_stage_pilot_records_role_sequence_without_fake_semantic_pass(tmp_path):
    client = RecordedClient([{"plan": "Use only the supplied text.", "unresolved": []}, {"triples": [["Oak", "is-a", "Tree"]]}])
    result = generate_sample(sample(), protocol(), "TwoAgentV3", tmp_path / "case", client=client)
    assert result["status"] == "GENERATED"
    assert [r["stage_id"] for r in result["agent_execution"]["records"]] == [1, 2, 3, 4, 5]
    assert result["validation"]["owl"] == "NOT_RUN"
    assert "NO_VALIDATION_FEEDBACK_REPAIR_IMPLEMENTED_IN_THIS_PROFILE" in result["limitations"]


def test_api_timeout_counts_attempt_and_preserves_public_failure_not_secret(tmp_path):
    client = RecordedClient([TimeoutError("private token and endpoint must not be copied")])
    result = generate_sample(sample(), protocol(), "DirectGeneralLLM", tmp_path / "case", client=client)
    assert result["status"] == "FAILED" and result["failure_type"] == "TimeoutError"
    assert result["resources"]["model_calls"] == 1
    assert result["resources"]["reported_total_tokens"] is None
    assert "private token" not in str(result)
    assert (tmp_path / "case/model-call-01.json").is_file()


def test_alphanumeric_provider_secrets_are_not_mistaken_for_public_error_codes(tmp_path):
    client = RecordedClient([RuntimeError("SENSITIVESECRET123")])
    result = generate_sample(sample(), protocol(), "DirectGeneralLLM", tmp_path / "case", client=client)
    assert result["failure_code"] == "EXECUTION_FAILED"
    assert "SENSITIVESECRET123" not in str(result)


def test_context_token_budget_rejects_before_transport_for_every_variant(tmp_path):
    configured = protocol(budget={"context_window_tokens": 512})
    for system in configured.systems:
        client = RecordedClient([])
        result = generate_sample(sample(), configured, system, tmp_path / system, client=client)
        assert result["status"] == "FAILED" and result["failure_code"] == "CONTEXT_TOKEN_UPPER_BOUND_EXCEEDED"
        assert client.inputs == [] and result["resources"]["model_calls"] == 0


def test_reuse_subtraction_uses_pinned_lowercase_whitespace_not_casefold():
    initial = [["Oak", "is-a", "Tree"]]
    extra = ["Tree", "is-a", "Oak"]
    assert additions_only([["  OAK ", " is-a ", " tree "], extra], initial) == [extra]
    # Upstream lower() must not be silently replaced by casefold().
    assert additions_only([["straße", "p", "x"]], [["STRASSE", "p", "x"]]) == [["straße", "p", "x"]]


def test_holm_correction_keeps_original_family_and_monotonic_adjustment():
    assert holm_adjust({"a": .01, "b": .04, "c": .03}) == {"a": .03, "c": .06, "b": .06}
    with pytest.raises(ValueError):
        holm_adjust({"a": float("nan")})


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "path", "group", "protocol"])
def test_frozen_inventory_cannot_drop_failures_or_change_file_targets(mutation):
    config = protocol(replicates=2)
    inputs = {"s1": sample()}
    manifest = {"protocol_sha256": semantic_hash(config.model_dump(mode="json")), "samples": [
        {"sample_id": "s1", "replicate_id": r, "path": f"s1-{r}", "group_id": sample().group_id} for r in range(2)]}
    verify_sample_inventory(manifest, inputs, config)
    if mutation == "missing":
        manifest["samples"].pop()
    elif mutation == "duplicate":
        manifest["samples"].append(manifest["samples"][0])
    elif mutation == "protocol":
        manifest["protocol_sha256"] = "0" * 64
    else:
        manifest["samples"][0]["path" if mutation == "path" else "group_id"] = "../../scoring/gold.json"
    with pytest.raises(ValueError):
        verify_sample_inventory(manifest, inputs, config)


@pytest.mark.parametrize("field,value", [("metrics", {}), ("sample_count", -1), ("sample_count", "1"),
    ("observed_model_ids", "model"), ("source_commit", "main"), ("comparison", []), ("input_manifest_sha256", "not-a-hash")])
def test_report_schema_rejects_wrong_top_level_types(field, value):
    report = empty_report()
    report[field] = value
    with pytest.raises(ValidationError):
        inspect_report(report)
