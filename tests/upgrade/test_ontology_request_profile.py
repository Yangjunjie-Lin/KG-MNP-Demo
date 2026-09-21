"""Wire-shape and bounded formal-plan tests; no real model inference."""
import json
from pathlib import Path

import httpx
import pytest

from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.modeling.five_stage.compatible import CompatibleClient
from zhigou_toolchain.modeling.five_stage.tools import ModelLock
from zhigou_toolchain.ontology_io.adapters import adapt_llms4ol
from zhigou_toolchain.ontology_io.cli import load, save
from zhigou_toolchain.ontology_io.contracts import Protocol, RequestProfile
from zhigou_toolchain.ontology_io.cq4oe import adapt_cq4oe
from zhigou_toolchain.ontology_io.engine import generate_sample
from zhigou_toolchain.ontology_io.formal_calls import (
    ALL_SYSTEMS,
    TASKS,
    call_cap,
    prepare_call_pack,
    task_protocol,
)


def sample():
    return adapt_llms4ol({"id": "sample", "context": "Oak is a tree."}, task="flagship")


def test_formal_profile_is_actually_sent_without_guessing_sampling_parameters(tmp_path):
    captured = []

    def respond(request):
        value = json.loads(request.content)
        captured.append(value)
        assert value["max_completion_tokens"] == 8192 and "max_tokens" not in value
        assert value["n"] == 1 and value["stream"] is False and value["store"] is False
        assert value["response_format"] == {"type": "json_object"}
        assert not {"reasoning_effort", "temperature", "top_p", "seed"} & value.keys()
        return httpx.Response(200, json={"model": "fixture", "system_fingerprint": "fp_test", "choices": [{"finish_reason": "stop", "message": {"content": '{"triples":[]}'}}]})

    client = CompatibleClient(ModelLock("fixture", "revision-1", "http://localhost:1/v1"), transport=httpx.MockTransport(respond))
    p = task_protocol("llms4ol_2026--flagship", model_id="fixture", declared_revision="revision-1", reasoning_effort=None)
    try:
        result = generate_sample(sample(), p, "DirectGeneralLLM", tmp_path / "run", client=client)
        assert result["status"] == "GENERATED", result
        assert client.client.timeout.read == 120 and len(captured) == 1
        assert result["calls"][0]["model"]["observed_system_fingerprint"] == "fp_test"
    finally:
        client.close()


def test_legacy_service_default_request_shape_remains_unchanged():
    def respond(request):
        payload = json.loads(request.content)
        assert "max_tokens" in payload and "max_completion_tokens" not in payload
        assert not {"n", "store", "stream"} & payload.keys()
        return httpx.Response(200, json={"model": "fixture", "choices": [{"finish_reason": "stop", "message": {"content": '{"ok":true}'}}]})
    client = CompatibleClient(ModelLock("fixture", "r1", "http://localhost:1/v1"), transport=httpx.MockTransport(respond))
    try:
        client.propose("Return JSON", {}, {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]})
    finally:
        client.close()


@pytest.mark.parametrize("failure", ["json", "schema", "length", "refusal", "model"])
def test_rejected_model_output_keeps_billing_without_private_reasoning(tmp_path, failure):
    message = {"content": '{"triples":[]}', "reasoning_content": "PRIVATE_REASONING_CANARY"}
    response = {"model": "fixture", "choices": [{"finish_reason": "stop", "message": message}],
        "usage": {"prompt_tokens": 11, "completion_tokens": 23, "total_tokens": 34,
            "completion_tokens_details": {"private": "PRIVATE_REASONING_CANARY"}}}
    if failure == "json":
        message["content"] = "not json"
    elif failure == "schema":
        message["content"] = '{"triples": "invalid"}'
    elif failure == "length":
        response["choices"][0]["finish_reason"] = "length"
    elif failure == "refusal":
        message["refusal"] = "cannot comply"
    else:
        response["model"] = "wrong-model"
    client = CompatibleClient(ModelLock("fixture", "r1", "http://localhost:1/v1"),
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=response)))
    protocol = task_protocol("llms4ol_2026--flagship", model_id="fixture", declared_revision="r1", reasoning_effort=None)
    try:
        result = generate_sample(sample(), protocol, "DirectGeneralLLM", tmp_path / "run", client=client)
        assert result["status"] == "FAILED"
        assert result["resources"]["model_calls"] == 1
        assert result["resources"]["reported_total_tokens"] == 34
        assert result["resources"]["model_seconds"] >= 0
        assert "PRIVATE_REASONING_CANARY" not in json.dumps(result)
    finally:
        client.close()


@pytest.mark.parametrize("usage", [None, {}, {"total_tokens": True}, {"total_tokens": -1}, {"total_tokens": "34"}])
def test_unknown_or_invalid_usage_is_not_a_zero_or_fabricated_count(tmp_path, usage):
    response = {"model": "fixture", "choices": [{"finish_reason": "stop", "message": {"content": "invalid-json"}}], "usage": usage}
    client = CompatibleClient(ModelLock("fixture", "r1", "http://localhost:1/v1"),
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=response)))
    protocol = task_protocol("llms4ol_2026--flagship", model_id="fixture", declared_revision="r1", reasoning_effort=None)
    try:
        result = generate_sample(sample(), protocol, "DirectGeneralLLM", tmp_path / "run", client=client)
        assert result["resources"]["reported_total_tokens"] is None
    finally:
        client.close()


def test_declared_revision_mismatch_stops_before_network(tmp_path):
    client = CompatibleClient(ModelLock("fixture", "actual", "http://localhost:1/v1"), transport=httpx.MockTransport(lambda _: pytest.fail("no network")))
    p = Protocol(protocol_id="revision-check", model_id="fixture", declared_revision="not-actual", systems=["DirectGeneralLLM"])
    try:
        result = generate_sample(sample(), p, "DirectGeneralLLM", tmp_path / "run", client=client)
        assert result["failure_code"] == "CONFIGURED_REVISION_DIFFERS_FROM_PROTOCOL"
        assert result["resources"]["model_calls"] == 0
    finally:
        client.close()


@pytest.mark.parametrize("values", [{"n": 2}, {"store": True}, {"stream": True}, {"temperature": 0}, {"seed": 17}])
def test_request_profile_forbids_unfrozen_or_unsupported_fields(values):
    with pytest.raises(ValueError):
        RequestProfile(**values)


def test_call_caps_match_current_stage_structure_and_na_components():
    a = sample()
    b = adapt_llms4ol({"id": "r", "context": "Oak is a tree.", "initial-primitive-ontology-triples": [["Oak", "is-a", "Tree"]]}, task="reuse")
    c = adapt_cq4oe([{"id": "CQ1", "value": "Which plants?"}], sample_id="plants", task="cq2onto")
    for key, source, kernel, no_feedback in [("llms4ol_2026--flagship", a, 4, 2), ("llms4ol_2026--reuse", b, 5, 3),
        ("cq4oe_0_0_1--cq2onto", c, 2, 1)]:
        p = task_protocol(key, model_id="fixture", declared_revision="r1", reasoning_effort=None)
        assert call_cap(source, p, "TwoAgentKernelV1") == kernel
        assert call_cap(source, p, "NoValidationFeedback") == no_feedback
        assert call_cap(source, p, "DirectGeneralLLM") == 1
        assert call_cap(source, p, "DirectBudgetControl") == p.budget.max_calls
        assert p.total_run_authorization is None
    with pytest.raises(ValueError, match="ABLATION_COMPONENT"):
        call_cap(a, task_protocol("llms4ol_2026--flagship", model_id="fixture", declared_revision="r1", reasoning_effort=None), "NoRetrieval")


@pytest.mark.parametrize("task", ["flagship", "reuse", "cq2onto"])
def test_call_caps_cover_actual_longest_structural_repair_path(task, tmp_path, monkeypatch):
    from tests.upgrade.test_ontology_io_kernel import (
        REUSE,
        TBOX,
        VOCAB,
        Boundary,
        extracted,
    )
    s = sample() if task == "flagship" else adapt_llms4ol({"id": "r", "context": "Oak is a tree.",
        "initial-primitive-ontology-triples": [["Oak", "is-a", "Tree"]]}, task="reuse") if task == "reuse" else \
        adapt_cq4oe([{"id": "CQ1", "value": "Which animals?"}], sample_id="animals", task="cq2onto")
    key = s.benchmark_id + "--" + s.task_id
    p = task_protocol(key, model_id="fixture", declared_revision="fixture-v1", reasoning_effort=None).model_copy(update={"request_profile": None})
    count = []

    def forced_issue(**kwargs):
        count.append(1)
        return {"owl_consistency": {"status": "INCONSISTENT" if len(count) == 1 else "CONSISTENT"},
            "shacl": {"status": "NOT_APPLICABLE_NO_LEGAL_SHAPES"}, "scope": "SCRIPTED_ROUTE_FOR_CALL_BOUND_TEST_ONLY"}

    monkeypatch.setattr("zhigou_toolchain.modeling.five_stage.semantic_check.check_research_graphs", forced_issue)
    replies = [{"turtle": TBOX}, {"turtle": TBOX}] if task == "cq2onto" else [VOCAB, extracted(), VOCAB, extracted()]
    if task == "reuse":
        replies.insert(0, REUSE)
    result = generate_sample(s, p, "TwoAgentKernelV1", tmp_path / "run", client=Boundary(replies))
    assert result["status"] == "GENERATED", result
    assert result["resources"]["model_calls"] == call_cap(s, p, "TwoAgentKernelV1")


def test_pack_covers_all_tasks_systems_repeats_and_never_opens_gold(tmp_path):
    prepared = tmp_path / "prepared"
    for key in TASKS:
        task = key.split("--")[1]
        if task == "flagship":
            s = sample()
        elif task == "reuse":
            s = adapt_llms4ol({"id": "r", "context": "Oak is a tree.", "initial-primitive-ontology-triples": [["Oak", "is-a", "Tree"]]}, task=task)
        else:
            s = adapt_cq4oe([{"id": "CQ1", "value": "Which plants?"}], sample_id="plants", task=task)
        raw = [s.model_dump(mode="json")]
        save(prepared / key / "generation/inputs.json", raw)
        save(prepared / key / "prepared-lock.json", {"input_sha256": semantic_hash(raw), "sample_count": 1, "dataset_version": s.dataset_version})
        # An invalid JSON scoring file would crash any accidental gold loader.
        folder = prepared / key / "scoring"
        folder.mkdir()
        (folder / "gold.json").write_text("FORBIDDEN_NOT_JSON", encoding="utf-8")
    output = tmp_path / "pack"
    report = prepare_call_pack(prepared, output, observed_configuration={"model_id": "fixture", "declared_revision": "r1", "reasoning_effort": None})
    jobs = [json.loads(line) for line in (output / "jobs.jsonl").read_text().splitlines()]
    assert len(jobs) == len(TASKS) * len(ALL_SYSTEMS) * 3
    assert report["totals"]["core_calls"] == 3 * (9 + 11 + 5 + 5)
    assert report["totals"]["all_calls"] == 3 * (15 + 25 + 6 + 6)
    assert not list(output.rglob("gold.json"))
    assert load(output / "call-pack.json")["proposal_not_authorization"]["user_approval"] is None
    assert not any("FORBIDDEN_NOT_JSON" in p.read_text(encoding="utf-8-sig") for p in Path(output).rglob("*.json"))
