from __future__ import annotations

import pytest

from kg_mnp.integrations.protocol import AdapterManifest, IntegrationTarget
from kg_mnp.integrations.registry import AdapterRegistry
from kg_mnp.integrations.targets import validate_endpoint
from kg_mnp.integrations.workflow import LocalWorkflowOutbox


def test_adapter_registry_uses_target_ids_not_request_urls():
    registry = AdapterRegistry()
    registry.register_manifest(AdapterManifest("local", "1.0.0", "LOCAL", ("read",)))
    target = IntegrationTarget("target-local", "LOCAL", "r1")
    registry.register_target(target)
    assert registry.target("target-local") == target
    with pytest.raises(ValueError):
        registry.register_target(IntegrationTarget("https://attacker.invalid", "LOCAL", "r1"))


def test_ssrf_policy_rejects_private_and_userinfo():
    with pytest.raises(ValueError):
        validate_endpoint("https://user:pass@example.com", allowed_hosts={"example.com"})
    with pytest.raises(ValueError):
        validate_endpoint("http://127.0.0.1:7200", allow_local_graphdb=False)


def test_workflow_outbox_is_explicitly_enqueued_not_completed(tmp_path):
    outbox = LocalWorkflowOutbox(tmp_path)
    receipt = outbox.enqueue(action_definition={"action_id": "a1", "input_contract": "Input", "released_ontology_context": "release-1"}, project_id="project-1", release_id="release-1", payload={"iri": "urn:item:1"}, idempotency_key="k1")
    assert receipt.status == "REQUEST_ENQUEUED"
    assert receipt.details["execution_status"] == "EXTERNAL_EXECUTION_NOT_CONFIGURED"
    assert outbox.inspect(receipt.details["invocation_id"])["status"] == "REQUEST_ENQUEUED"
