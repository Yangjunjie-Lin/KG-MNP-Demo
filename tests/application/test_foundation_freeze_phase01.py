from __future__ import annotations

from tests.refactor._historical_freeze import assert_prompt01_semantic_snapshot

STAGE_08_COMMIT = "4dc09d9cfb15da3746f108755593ceb9fe805cd7"


def test_phase01_preserves_stage08_foundation_authority_bytes() -> None:
    assert_prompt01_semantic_snapshot(STAGE_08_COMMIT)
