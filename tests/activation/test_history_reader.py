"""A reader reproduces original persisted history without running a controller."""
# ruff: noqa: F811 -- imported shared pytest fixture uses injection by name
from copy import deepcopy

import pytest

from kg_mnp.activation.errors import ActivationError
from kg_mnp.activation.history_reader import reconstruct_controlled_history
from tests.activation.test_artifact_verifier_phase06 import (
    corpus,  # noqa: F401 - shared authentic event construction
)


def read(corpus, registry=None, **anchors):
    workflow = corpus["workflow"]
    return reconstruct_controlled_history(registry or workflow["final_registry"], workflow["final_pointer"],
        authority=corpus["fixture"]["authority"], expected_registry_hash=anchors.get("registry_hash", workflow["final_state"]["registry_hash"]),
        expected_head_event_hash=anchors.get("head_hash", workflow["final_state"]["head_event_hash"]))


def test_reader_matches_original_controller_transcript_exactly(corpus):
    assert read(corpus) == corpus["workflow"]


def test_reader_cannot_infer_trusted_anchors(corpus):
    with pytest.raises(ActivationError, match="trusted history anchors"):
        read(corpus, registry_hash="", head_hash="")


@pytest.mark.parametrize("anchor", ["registry_hash", "head_hash"])
def test_reader_rejects_wrong_external_anchor(corpus, anchor):
    with pytest.raises(ActivationError):
        read(corpus, **{anchor: "f" * 64})


def test_historical_reader_has_no_network_or_control_side_effects():
    import inspect

    from kg_mnp.activation import history_reader

    source = inspect.getsource(history_reader)
    for forbidden in ("ReadOnlyGraphDBClient", "ActivationController", "ActivationStateStore", "http.client", "subprocess", "write_bytes", "write_text"):
        assert forbidden not in source


@pytest.mark.parametrize("mutation", ["append", "delete", "modify", "reorder"])
def test_reader_rejects_tampered_history(corpus, mutation):
    registry = deepcopy(corpus["workflow"]["final_registry"])
    if mutation == "append": registry["events"].append(deepcopy(registry["events"][-1]))
    elif mutation == "delete": registry["events"].pop()
    elif mutation == "reorder": registry["events"].reverse()
    else: registry["events"][-1]["payload"]["status"] = "ACTIVATION_APPLIED"
    with pytest.raises(ActivationError):
        read(corpus, registry)
