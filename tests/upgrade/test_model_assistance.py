"""Network-boundary doubles; never counted as LIVE model inference."""
import json
from copy import deepcopy

import httpx
import pytest

from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.modeling.control_plane.providers.models import (
    candidate_body,
    candidate_draft,
)
from zhigou_toolchain.modeling.five_stage.assistance import (
    character_chunks,
    generate,
    repair,
)
from zhigou_toolchain.modeling.five_stage.compatible import (
    CompatibleClient,
    configured_client,
)
from zhigou_toolchain.modeling.five_stage.exact_answers import ExactAnswer, assertions
from zhigou_toolchain.modeling.five_stage.tools import ModelLock, ToolBlocked
from zhigou_toolchain.semantic_kernel.validators.competency_questions import (
    _assertions,
    _execute,
    build_cq_test_plan,
)

SCHEMA = {"type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"], "additionalProperties": False}


def client_for(value, **extra):
    def handler(request):
        payload = json.loads(request.content)
        assert payload["response_format"]["type"] == "json_object"
        assert "structured_outputs" not in payload
        return httpx.Response(200, json={"id": "synthetic-request", "model": "model-test", "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(value), "reasoning_content": "DO_NOT_STORE"}}], **extra})
    return CompatibleClient(ModelLock("model-test", "configured-alias:model-test", "http://localhost:1/v1"), api_key="synthetic-credential", transport=httpx.MockTransport(handler))


def test_compatible_json_mode_validated_receipt_and_secret_redaction():
    client = client_for({"value": "ok"})
    try:
        result = client.propose("Extract value", {"value": "ok"}, SCHEMA)
        assert result["proposal"] == {"value": "ok"}
        assert result["server_schema_enforced"] is False
        assert result["approval"] == "NOT_GRANTED"
        assert result["input_hash"] == semantic_hash({"value": "ok"})
        assert "synthetic-credential" not in json.dumps(result)
        assert "DO_NOT_STORE" not in json.dumps(result)
    finally:
        client.close()


@pytest.mark.parametrize("value,extra", [({"value": 1}, {}), ({"value": "ok", "approve": True}, {}), ({"value": "ok"}, {"model": "another-model"}),
    ({"value": "ok"}, {"choices": [{"finish_reason": "length", "message": {"content": '{"value":"ok"}'}}]}),
    ({"value": "ok"}, {"choices": [{"finish_reason": "stop", "message": {"content": '{"value":"ok"}', "refusal": "refused"}}]})])
def test_compatible_rejects_invalid_output(value, extra):
    client = client_for(value, **extra)
    try:
        with pytest.raises(ToolBlocked, match="MODEL_OUTPUT_REJECTED"):
            client.propose("test", {}, SCHEMA)
    finally:
        client.close()


def test_incomplete_explicit_qwen_does_not_silently_use_generic_api(monkeypatch):
    monkeypatch.setenv("ZHIGOU_QWEN_MODEL", "configured")
    monkeypatch.setenv("ZHIGOU_QWEN_REVISION", "")
    monkeypatch.setenv("ZHIGOU_QWEN_ENDPOINT", "")
    with pytest.raises(ToolBlocked):
        configured_client()


@pytest.mark.parametrize("payload", [[], {}, {"model": "model-test", "choices": None}, {"model": "model-test", "choices": [None]},
    {"model": "model-test", "choices": [{"finish_reason": "stop", "message": None}]}])
def test_malformed_provider_envelopes_fail_closed_with_sanitized_diagnostics(payload):
    client = CompatibleClient(ModelLock("model-test", "configured-alias:model-test", "http://localhost:1/v1"),
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)))
    try:
        with pytest.raises(ToolBlocked, match="MODEL_OUTPUT_REJECTED"):
            client.propose("Synthetic probe", {}, SCHEMA)
    finally:
        client.close()


def test_live_proposal_requires_source_permission_before_any_project_or_network_access():
    from types import SimpleNamespace

    from zhigou_toolchain.services.errors import ServiceBoundaryError
    from zhigou_toolchain.services.modeling import execute
    from zhigou_toolchain.services.models import OperationRequest
    with pytest.raises(ServiceBoundaryError) as error:
        execute(None, None, OperationRequest("modeling.proposal", parameters={"model_assistance": {"execution_mode": "LIVE"}}), SimpleNamespace(can=lambda _: False))
    assert error.value.status_code == 403


def context_and_drafts():
    item = {"item_id": "text-1", "item_kind": "text-block", "payload": {"text": "Entity A: correct. Entity B: unknown."}, "evidence_refs": ["evidence-1"]}
    context = {"kg_ir_items": [item], "baseline_elements": [{"iri": "urn:base:Entity", "element_kind": "CLASS", "labels": [{"value": "Entity"}]},
        {"iri": "urn:base:label", "element_kind": "DATA_PROPERTY", "labels": [{"value": "label"}]}],
        "object_families": ["Entity"], "business_rules": ["Preserve unknown status"], "default_namespace": "urn:new:"}
    def draft(ref, body, kind="ABOX", action="ASSERT"):
        return candidate_draft(draft_ref=ref, draft_kind=kind, candidate_action=action, body=candidate_body(**body), rationale="Synthetic boundary test",
            kg_ir_item_refs=["text-1"], evidence_refs=["evidence-1"])
    drafts = [draft("individual", {"candidate_type": "INDIVIDUAL", "subject_iri": "urn:new:A"}),
        draft("value", {"candidate_type": "DATA_PROPERTY_ASSERTION", "subject_iri": "urn:new:A", "predicate_iri": "urn:base:label",
            "literal": {"lexical_value": "wrong", "datatype_iri": "http://www.w3.org/2001/XMLSchema#string", "language": None}}),
        draft("hard-rule", {"candidate_type": "MIN_COUNT", "subject_iri": "urn:new:Shape", "integer_value": 1}, "SHACL", "CONSTRAIN")]
    return context, drafts


class RecordedBoundary:
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.contexts = []
    def propose(self, task, context, schema, **kwargs):
        from jsonschema import validate
        from jsonschema.exceptions import ValidationError
        self.contexts.append(deepcopy(context))
        output = next(self.outputs)
        try:
            validate(output, schema)
        except ValidationError:
            raise ToolBlocked("RECORDED_BOUNDARY_SCHEMA_REJECTED") from None
        return {"proposal": output, "execution_source": "RECORDED", "model": {"model_id": "test", "configured_revision": "test-r1"}, "prompt_hash": semantic_hash(task)}


def test_two_round_generation_quote_binding_unknown_and_no_answers():
    context, drafts = context_and_drafts()
    boundary = RecordedBoundary([{"decisions": [{"term": "Entity", "decision": "REUSE", "existing_iri": "urn:base:Entity", "reason": "Exact kind"}], "unresolved": []},
        {"additions": [], "unresolved": []}, {"facts": [{"subject_iri": "urn:new:A", "predicate_iri": "urn:base:label", "object_iri": None,
            "literal_value": "correct", "quote": "Entity A: correct.", "quote_start": 0, "polarity": "ASSERTED", "reason": "Verbatim"},
            {"subject_iri": "urn:new:A", "predicate_iri": "urn:base:label", "object_iri": None, "literal_value": "unknown", "quote": "Entity B: unknown.", "quote_start": 19, "polarity": "UNKNOWN", "reason": "Unresolved; do not assert"}], "unresolved": []}])
    generated, receipt = generate(boundary, context=context, initial_drafts=drafts, configuration={"retrieval": "LLM_SUBSTITUTE", "chunking": "UNICODE_SUBSTITUTE"})
    assert len(generated) == len(drafts) + 1
    assert receipt["extraction"][0]["facts"][1]["polarity"] == "UNKNOWN"
    assert receipt["independent_answers_accessible"] is False
    assert receipt["retrieval"][0]["method"] == "EXACT_PLUS_LLM_RANKING_SUBSTITUTE"
    assert len(boundary.contexts) == 3
    assert not any("acceptance" in c or "expected" in c for c in boundary.contexts)


def test_unicode_chunks_are_lossless_and_explicit_substitution():
    text = "甲😀é\n" * 500
    result = character_chunks(text, text_id="id", text_version="v", window=40, overlap=5)
    covered = set()
    for c in result["chunks"]:
        assert text[c["start"]:c["end"]] == c["text"]
        covered.update(range(c["start"], c["end"]))
    assert covered == set(range(len(text)))
    assert result["method"] == "UNICODE_WINDOW_SUBSTITUTE"


@pytest.mark.parametrize("approved", [True, False])
def test_new_structure_requires_explicit_namespace_gap_and_source_binding(approved):
    context, _ = context_and_drafts()
    context["kg_ir_items"][0].update(item_kind="table-cell", payload={"value": {"normalized_lexical_value": "Alpha"}})
    row = {"kind": "TBOX", "action": "CREATE_NEW", "body": {"candidate_type": "CLASS", "subject_iri": None, "predicate_iri": None,
        "object_iri": None, "target_iri": "urn:new:ApprovedClass", "label": "ApprovedClass", "integer_value": None, "values": []},
        "item_refs": ["S0"], "rule_indexes": [], "rationale": "Explicitly requested class candidate"}
    boundary = RecordedBoundary([{"decisions": [], "unresolved": []}, {"additions": [row], "unresolved": []}])
    configuration = {"retrieval": "LLM_SUBSTITUTE", "chunking": "UNICODE_SUBSTITUTE", "approved_new_iris": ["urn:new:ApprovedClass"] if approved else []}
    if not approved:
        with pytest.raises(ToolBlocked):
            generate(boundary, context=context, initial_drafts=[], configuration=configuration)
    else:
        drafts, receipt = generate(boundary, context=context, initial_drafts=[], configuration=configuration)
        assert drafts[0]["kg_ir_item_refs"] == ["text-1"]
        assert drafts[0]["evidence_refs"] == ["evidence-1"]
        assert receipt["model_added_draft_count"] == 1


def patch(**extra):
    return {"draft_ref": "value", "field": "literal", "value": "correct", "item_id": "S0", "quote": "Entity A: correct.", "quote_start": 0, "reason": "Verbatim correction", **extra}


def test_whitelisted_repair_preserves_original_and_hard_rules():
    context, original = context_and_drafts()
    repaired, result = repair(RecordedBoundary([{"patches": [patch()], "unresolved": []}]), original_drafts=original, context=context, issues={"code": "SYNTHETIC_FAULT"}, configuration={})
    assert original[1]["body"]["literal"]["lexical_value"] == "wrong"
    assert repaired[1]["body"]["literal"]["lexical_value"] == "correct"
    assert repaired[2] == original[2]
    assert "HUMAN_REVIEW" in result["required_next_steps"]


def test_repair_binds_actual_cell_value_not_a_synthetic_text_location():
    context, original = context_and_drafts()
    context["kg_ir_items"][0].update(item_kind="table-cell", payload={"value": {"normalized_lexical_value": "correct"}, "row": 2, "column": 2})
    repaired, result = repair(RecordedBoundary([{"patches": [patch(quote="correct")], "unresolved": []}]), original_drafts=original, context=context, issues={}, configuration={})
    assert repaired[1]["body"]["literal"]["lexical_value"] == "correct"
    assert result["changes"][0]["binding"]["start"] == 0
    assert result["changes"][0]["binding"]["text_id"] == "text-1"


def test_model_assistance_dto_rejects_endpoint_and_client_authority():
    from pydantic import ValidationError

    from zhigou_toolchain.services.requests import ModelAssistance
    for extra in ({"endpoint": "http://evil"}, {"approved": True}, {"expected_answers": []}):
        with pytest.raises(ValidationError):
            ModelAssistance.model_validate({"execution_mode": "LIVE", "expected_session_revision": 1, **extra})


def test_repair_inputs_separate_human_authority_from_actual_defects():
    from zhigou_toolchain.services.modeling_assistance import repair_findings
    required = {"code": "HUMAN_REVIEW_REQUIRED", "severity": "INFO"}
    defect = {"code": "EVIDENCE_MISSING", "severity": "BLOCKING"}
    warning = {"code": "UNKNOWN_STATUS", "severity": "WARNING"}
    original = {"issues": [required, defect, warning]}
    assert repair_findings(original) == [defect, warning]
    assert original["issues"] == [required, defect, warning]


def test_repair_semantic_findings_are_bound_to_server_receipt():
    from types import SimpleNamespace

    from zhigou_toolchain.services.errors import ServiceBoundaryError
    from zhigou_toolchain.services.modeling_assistance import semantic_findings
    value = {"artifacts": [{"ref": {"step_id": "4.2"}, "content": {"status": "FAIL", "shacl": "violation"}}]}
    job = SimpleNamespace(project_id="project", status="SUCCEEDED", result={"five_stage": value})
    app = SimpleNamespace(jobs=SimpleNamespace(get=lambda _: job))
    session = {"outputs": [{"operation": "modeling.semantic.check", "status": "CURRENT", "job_id": "job", "digest": semantic_hash(value)}]}
    assert semantic_findings(app, session, "project") == [{"status": "FAIL", "shacl": "violation"}]
    job.result["five_stage"]["artifacts"][0]["content"]["status"] = "PASS"
    with pytest.raises(ServiceBoundaryError, match="exact committed"):
        semantic_findings(app, session, "project")


@pytest.mark.parametrize("changes", [{"draft_ref": "hard-rule"}, {"value": "fabricated"}, {"item_id": "unrelated"}, {"quote_start": 1}, {"field": "object_iri", "value": "urn:evil:target"}])
def test_repair_rejects_rule_edits_unknown_evidence_and_ungrounded_values(changes):
    context, drafts = context_and_drafts()
    with pytest.raises((ToolBlocked, ValueError)):
        repair(RecordedBoundary([{"patches": [patch(**changes)], "unresolved": []}]), original_drafts=drafts, context=context, issues={}, configuration={})


@pytest.mark.parametrize("comparison", ["SET", "ORDERED", "MULTISET"])
def test_exact_profiles_in_real_query_engine(comparison):
    query = 'PREFIX xsd: <http://www.w3.org/2001/XMLSchema#> SELECT ?x WHERE { VALUES ?x { "b"^^xsd:string "a"^^xsd:string "a"^^xsd:string } } ORDER BY ?x'
    rows = [{"x": {"kind": "LITERAL", "value": v, "datatype": "http://www.w3.org/2001/XMLSchema#string"}} for v in (["a", "b"] if comparison == "SET" else ["a", "a", "b"])]
    answer = ExactAnswer.model_validate({"query_type": "SELECT", "comparison": comparison, "variables": ["x"], "rows": rows})
    status, value = _execute(b'', query, "SELECT", 30, 100, comparison == "ORDERED")
    assert status == "OK"
    assert all(a["passed"] for a in _assertions("SELECT", value, assertions(answer))[0])
    if comparison == "ORDERED":
        value["rows"].reverse()
        assert not _assertions("SELECT", value, assertions(answer))[0][0]["passed"]


def test_ordered_profile_requires_real_top_level_order_clause():
    with pytest.raises(ValueError, match="ORDER BY"):
        build_cq_test_plan([{"query_artifact_ref": "query", "query_type": "SELECT", "assertions": [{"assertion_type": "RESULT_SEMANTIC_HASH", "string_values": ["ORDERED_V1"]}]}],
            query_loader=lambda _: b'SELECT ?x WHERE { VALUES ?x { "ORDER BY" } }')
