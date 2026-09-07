import pytest

from kg_mnp.lifecycle.environment import (
    execute_activation,
    init_environment,
    review_activation,
)
from kg_mnp.lifecycle.errors import LifecycleError
from kg_mnp.lifecycle.registry.head import read_head
from kg_mnp.lifecycle.registry.manifest import init_registry
from kg_mnp.lifecycle.store import bind_identity, save


@pytest.mark.parametrize("fault", ["withdrawn", "quorum"])
def test_environment_gate_rejects_current_review_before_resolving_target(tmp_path, fault):
    # Deliberately missing target: rejecting the review must happen before any
    # target resolution. This is a negative boundary test, not a release fixture.
    registry = init_registry(tmp_path)
    env = init_environment(tmp_path, environment_name="dev", activation_quorum=2 if fault=="quorum" else 1)
    pointer = __import__('json').loads(next((tmp_path / "state").glob("environment-pointer-*.json")).read_bytes())
    proposal = {"manifest_kind":"KG_MNP_ACTIVATION_PROPOSAL","schema_version":"1.0.0",
        "registry_id":registry["registry_id"],"environment_id":env["environment_id"],"activation_kind":"ACTIVATE",
        "base_pointer_generation":pointer["generation"],"base_pointer_hash":pointer["pointer_hash"],
        "target_release_id":"urn:kg-mnp:release:"+"a"*64,"target_package_id":None,"release_attestation_id":None,
        "rationale":"Synthetic missing target boundary", "requested_by":"alice", "proposal_status":"PROPOSED"}
    bind_identity(proposal,"activation_proposal_id","activation-proposal")
    save(tmp_path,"records/activation-proposals/test.json",proposal)
    approved = review_activation(tmp_path,proposal_id=proposal["activation_proposal_id"],decision="APPROVE",
        reviewer_id="alice",reviewer_roles=["RELEASE_MANAGER"],rationale="Initial decision",breaking_change_acknowledged=True)
    if fault=="withdrawn":
        review_activation(tmp_path,proposal_id=proposal["activation_proposal_id"],decision="REJECT",
            reviewer_id="alice",reviewer_roles=["RELEASE_MANAGER"],rationale="Withdrawal")
    with pytest.raises(LifecycleError) as caught:
        execute_activation(tmp_path,proposal_id=proposal["activation_proposal_id"],decision_id=approved["decision_id"],
            expected_generation=pointer["generation"],expected_pointer_hash=pointer["pointer_hash"],
            expected_registry_head_hash=read_head(tmp_path)["head_hash"])
    assert caught.value.code == "ACTIVATION_BLOCKED"
    assert "current review" in str(caught.value)
