from __future__ import annotations

from pathlib import Path

import pytest

from kg_mnp.lifecycle.changes import create_change_proposal, submit_change_proposal
from kg_mnp.lifecycle.diff import create_diff, verify_diff
from kg_mnp.lifecycle.environment import activate, init_environment
from kg_mnp.lifecycle.errors import LifecycleError
from kg_mnp.lifecycle.feedback import add_feedback
from kg_mnp.lifecycle.registry.manifest import init_registry
from kg_mnp.lifecycle.registry.replay import verify_registry


def test_registry_event_chain_and_states_are_replayable(tmp_path: Path) -> None:
    root = tmp_path / "registry"
    manifest = init_registry(root, project_id="urn:kg-mnp:project:" + "1" * 64)
    feedback = add_feedback(root, feedback_type="DEFECT", target_package_id="urn:kg-mnp:ontology-package:" + "2" * 64)
    proposal = create_change_proposal(root, base_package_id="urn:kg-mnp:ontology-package:" + "2" * 64)
    submit_change_proposal(root, proposal["change_proposal_id"])
    result = verify_registry(root)
    assert result["status"] == "VALID"
    assert result["event_count"] == 3
    assert feedback["registry_id"] == manifest["registry_id"]


def test_semantic_diff_is_deterministic_and_verifiable(tmp_path: Path) -> None:
    left = tmp_path / "left.nt"
    right = tmp_path / "right.nt"
    left.write_text("<urn:s> <urn:p> <urn:o> .\n", encoding="utf-8")
    right.write_text("<urn:s> <urn:p> <urn:o2> .\n", encoding="utf-8")
    one = create_diff(left, right)
    two = create_diff(left, right)
    assert one == two
    assert verify_diff(one)["status"] == "VALID"


def test_activation_requires_explicit_human_breaking_ack(tmp_path: Path) -> None:
    root = tmp_path / "registry"
    init_registry(root, project_id="urn:kg-mnp:project:" + "3" * 64)
    env = init_environment(root, environment_name="dev")
    with pytest.raises(LifecycleError):
        activate(root, environment_id=env["environment_id"], release_id="urn:kg-mnp:release:" + "4" * 64, reviewer_id="operator")
    receipt = activate(root, environment_id=env["environment_id"], release_id="urn:kg-mnp:release:" + "4" * 64, reviewer_id="human-owner", breaking_change_acknowledged=True)
    assert receipt["execution_status"] == "APPLIED"
