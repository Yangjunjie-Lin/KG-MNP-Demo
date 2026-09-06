from __future__ import annotations

import json
from pathlib import Path

import pytest

from kg_mnp.lifecycle.cli import main
from kg_mnp.lifecycle.environment import activate, init_environment
from kg_mnp.lifecycle.errors import LifecycleError
from kg_mnp.lifecycle.policy import load_policy
from kg_mnp.lifecycle.registry.manifest import init_registry
from kg_mnp.lifecycle.registry.replay import verify_registry


def test_bundled_policies_are_digest_bound() -> None:
    for name in ("registry-policy-1.0.0.yaml", "semantic-diff-policy-1.0.0.yaml", "regression-policy-1.0.0.yaml", "release-policy-1.0.0.yaml", "activation-policy-1.0.0.yaml"):
        assert load_policy(name)["content_digest"]


def test_cli_rejects_bypass_flags(tmp_path: Path) -> None:
    assert main(["registry", "status", str(tmp_path), "--force", "--json"]) == 42


def test_registry_head_tamper_is_detected(tmp_path: Path) -> None:
    root = tmp_path / "registry"
    init_registry(root)
    head = root / "state" / "registry-head.json"
    value = json.loads(head.read_bytes())
    value["head_hash"] = "0" * 64
    head.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(LifecycleError) as error:
        verify_registry(root)
    assert error.value.exit_code == 56


def test_environment_cas_rejects_stale_pointer(tmp_path: Path) -> None:
    root = tmp_path / "registry"
    init_registry(root)
    environment = init_environment(root, environment_name="dev")
    pointer = json.loads(next((root / "state").glob("environment-pointer-*.json")).read_bytes())
    activate(root, environment_id=environment["environment_id"], release_id="urn:kg-mnp:release:" + "1" * 64, reviewer_id="human", breaking_change_acknowledged=True, expected_generation=pointer["generation"], expected_pointer_hash=pointer["pointer_hash"])
    with pytest.raises(LifecycleError) as error:
        activate(root, environment_id=environment["environment_id"], release_id="urn:kg-mnp:release:" + "2" * 64, reviewer_id="human", breaking_change_acknowledged=True, expected_generation=pointer["generation"], expected_pointer_hash=pointer["pointer_hash"])
    assert error.value.exit_code == 54
