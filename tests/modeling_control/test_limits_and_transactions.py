from __future__ import annotations

from pathlib import Path

import pytest

from kg_mnp.modeling.control_plane.artifacts import transactional_write_directory
from kg_mnp.modeling.control_plane.errors import ModelingControlError
from kg_mnp.modeling.control_plane.limits import ModelingLimits


def test_limits_are_positive_bounded_and_serializable() -> None:
    limits = ModelingLimits()
    assert all(0 < value <= 1_000_000_000 for value in limits.to_dict().values())
    with pytest.raises(ValueError, match="positive finite"):
        ModelingLimits(max_total_candidates=0)


def test_transaction_reuses_identical_bytes_and_rejects_mutation(prompt03_workspace: Path) -> None:
    documents = {"value.json": {"safe": True}}
    first = transactional_write_directory(
        prompt03_workspace,
        operation="scope-write",
        relative_destination="artifacts/builds/modeling/test-value",
        documents=documents,
    )
    assert transactional_write_directory(
        prompt03_workspace,
        operation="scope-write",
        relative_destination="artifacts/builds/modeling/test-value",
        documents=documents,
    ) == first
    with pytest.raises(ModelingControlError, match="different bytes"):
        transactional_write_directory(
            prompt03_workspace,
            operation="scope-write",
            relative_destination="artifacts/builds/modeling/test-value",
            documents={"value.json": {"safe": False}},
        )


@pytest.mark.parametrize("destination", ["artifacts/packages/blocked", "registry/blocked"])
def test_transaction_cannot_write_authority_directories(
    prompt03_workspace: Path, destination: str
) -> None:
    with pytest.raises(ModelingControlError, match="cannot write packages or registry"):
        transactional_write_directory(
            prompt03_workspace,
            operation="confirmation-write",
            relative_destination=destination,
            documents={"value.json": {"safe": True}},
        )
