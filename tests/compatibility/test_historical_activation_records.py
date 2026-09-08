"""Replay genuine pre-retirement controlled records, never regenerate goldens."""
import hashlib
import json
from pathlib import Path

from kg_mnp.activation.artifact_verifier import _controlled_reconstruction
from scripts.activation_controlled_fixture import build_controlled_history


def test_original_persisted_activation_records_replay_without_state_store(tmp_path):
    directory = Path(__file__).with_name("fixtures") / "activation-1.0"
    registry_bytes = (directory / "activation-registry.json").read_bytes()
    pointer_bytes = (directory / "current-publication-pointer.json").read_bytes()
    registry, pointer = json.loads(registry_bytes), json.loads(pointer_bytes)
    # Digests are pinned to records written at c77, not current reconstruction.
    expected = json.loads((directory / "provenance.json").read_bytes())
    assert hashlib.sha256(registry_bytes).hexdigest() == expected["registry_byte_sha256"]
    assert hashlib.sha256(pointer_bytes).hexdigest() == expected["pointer_byte_sha256"]
    with _controlled_reconstruction(registry, pointer, expected["registry_hash"], expected["head_event_hash"]) as (fixture, workflow):
        assert workflow["final_registry"] == registry
        assert workflow["final_pointer"] == pointer
        assert workflow["final_state"]["activation_cycles"] == workflow["final_state"]["rollback_cycles"] == 1
        assert [p["generation"] for p in workflow["final_state"]["pointer_history"]] == [0, 1, 2]
        assert build_controlled_history(fixture=fixture) == workflow
        assert not list(Path(fixture["p0_attestation_path"]).parent.parent.rglob("activation.lock"))
    assert not list(tmp_path.iterdir())
