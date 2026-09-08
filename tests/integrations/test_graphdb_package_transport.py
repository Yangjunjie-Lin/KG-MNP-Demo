"""GraphDB protocol checks operate on actual current package bytes, offline."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from kg_mnp.integrations.graphdb import GraphDBAdapter
from kg_mnp.integrations.protocol import IntegrationApproval, IntegrationTarget
from tests.package_archive.test_snapshot_export import package


class Transport:
    retries = 0
    def __init__(self, fault=None):
        self.fault, self.calls, self.data = fault, [], b""
    def list_repositories(self):
        self.calls.append("list")
        return [self.repository_id] if self.fault == "existing" else []
    def create_repository(self, config):
        assert b'graphdb:ruleset "empty"' in config
        self.calls.append("create")
        if self.fault == "timeout": raise TimeoutError("unknown external result")
        return 201
    def inspect_repository(self, identifier):
        assert identifier == self.repository_id
        return {"id": identifier, "params": {"ruleset": {"value": "rdfs" if self.fault == "inference" else "empty"}}}
    def count_repository_statements(self, identifier):
        return 1 if self.fault == "nonempty" else 0
    def import_nquads(self, identifier, data):
        self.calls.append("import"); self.data = data
        return 204
    def export_nquads(self, identifier, *, include_inferred=False):
        self.calls.append("complete-export" if include_inferred else "explicit-export")
        if self.fault == "missing": return b""
        if self.fault == "changed" or (self.fault == "inferred" and include_inferred):
            return self.data + b'<urn:injected> <urn:p> "x" <urn:g> .\n'
        return self.data
    def get_default_graph(self, identifier):
        return SimpleNamespace(statement_count=1 if self.fault == "default-graph" else 0)


@pytest.fixture
def planned(tmp_path):
    root = package(tmp_path)
    import json
    identifier = json.loads((root / "ontology-package.json").read_bytes())["package_id"]
    adapter = GraphDBAdapter()
    target = IntegrationTarget("isolated", "GRAPHDB", "1")
    plan = adapter.plan_import(project_id="project", release_id="release", package_id=identifier, target=target, package_root=root)
    approval = IntegrationApproval("approval", plan.plan_id, plan.project_id, "human", plan.allowed_effect, plan.payload_digest, target.target_revision, None)
    return adapter, target, plan, approval, root


def client(plan, fault=None):
    from kg_mnp.contracts.canonical import semantic_hash
    transport = Transport(fault)
    transport.repository_id = "kg-mnp-" + semantic_hash({"plan_id": plan.plan_id, "package_id": plan.package_id})[:20]
    return transport


def test_current_package_deployment_requires_actual_explicit_complete_and_default_exports(planned):
    adapter, target, plan, approval, root = planned
    transport = client(plan)
    result = adapter.execute(plan, approval, target=target, package_root=root, transport=transport)
    assert result.status == "DEPLOYMENT_VERIFIED"
    assert result.observed_dataset_digest
    assert result.observed_deployed_release_id == plan.release_id
    assert transport.data == (root / "dataset/dataset.nq").read_bytes()
    assert "explicit-export" in transport.calls and "complete-export" in transport.calls


@pytest.mark.parametrize("fault", ["existing", "nonempty", "inference", "missing", "changed", "inferred", "default-graph", "timeout"])
def test_external_fault_never_claims_verified_or_deletes_a_repository(planned, fault):
    adapter, target, plan, approval, root = planned
    transport = client(plan, fault)
    result = adapter.execute(plan, approval, target=target, package_root=root, transport=transport)
    assert result.status in {"FAILED", "RECONCILIATION_REQUIRED"}
    assert result.observed_deployed_release_id is None
    if fault == "existing": assert transport.calls == ["list"]
    if fault in {"existing", "nonempty", "inference", "timeout"}: assert "import" not in transport.calls


@pytest.mark.parametrize("field", ["project_id", "approved_effect", "target_revision", "payload_digest"])
def test_approval_scope_cannot_be_changed_before_network(planned, field):
    adapter, target, plan, approval, root = planned
    transport = client(plan)
    with pytest.raises(ValueError):
        adapter.execute(plan, replace(approval, **{field: "forged"}), target=target, package_root=root, transport=transport)
    assert transport.calls == []


def test_unconfigured_transport_is_not_a_deployment(planned):
    adapter, target, plan, approval, root = planned
    result = adapter.execute(plan, approval, target=target, package_root=root)
    assert result.status == "RECONCILIATION_REQUIRED"
    assert result.observed_deployed_release_id is None


def test_adapter_never_materializes_environment_license_or_cleans_user_files(planned, tmp_path, monkeypatch):
    adapter, target, plan, approval, root = planned
    supplied = tmp_path / "user-license.txt"
    supplied.write_bytes(b"synthetic-user-owned-license")
    monkeypatch.setenv("GRAPHDB_LICENSE_FILE", str(supplied))
    monkeypatch.setenv("GRAPHDB_LICENSE_CONTENT", "must-not-be-read")
    monkeypatch.setenv("GRAPHDB_LICENSE_B64", "not-even-base64!")
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    result = adapter.execute(plan, approval, target=target, package_root=root, transport=client(plan, "timeout"))
    assert result.status == "RECONCILIATION_REQUIRED"
    assert before == {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}


@pytest.mark.parametrize("fault", ["endpoint", "retry", "protocol", "expired", "target-change"])
def test_invalid_transport_or_plan_is_rejected_before_effects(planned, fault):
    adapter, target, plan, approval, root = planned
    transport = client(plan)
    if fault == "endpoint": transport.base_url = "http://unapproved.invalid:7200"
    elif fault == "retry": transport.retries = 2
    elif fault == "protocol": transport.export_nquads = None
    elif fault == "expired": approval = replace(approval, expires_at="2000-01-01T00:00:00Z")
    else: target = replace(target, host="unapproved.invalid")
    with pytest.raises(TypeError if fault == "protocol" else ValueError):
        adapter.execute(plan, approval, target=target, package_root=root, transport=transport)
    assert transport.calls == []
