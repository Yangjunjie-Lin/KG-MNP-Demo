from __future__ import annotations

from tests.refactor._historical_freeze import assert_prompt01_semantic_snapshot

STAGE08 = "4dc09d9cfb15da3746f108755593ceb9fe805cd7"
PHASE01 = "79b7d34125b0c5cb2d5fe8546e1f4e6a95ca8106"


def test_foundation_authority_is_unchanged_from_stage08_closure() -> None:
    assert_prompt01_semantic_snapshot(STAGE08)


def test_phase01_semantic_and_security_layer_is_unchanged() -> None:
    assert_prompt01_semantic_snapshot(PHASE01)
