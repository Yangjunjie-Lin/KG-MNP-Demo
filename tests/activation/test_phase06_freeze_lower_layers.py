from __future__ import annotations

from tests.refactor._historical_freeze import assert_prompt01_semantic_snapshot

PHASE06_INPUT_HEAD = "9e7684bb9b988cec796e86ed9a6c51c59fa3a741"


def test_foundation_and_application_phases01_to05_are_frozen() -> None:
    assert_prompt01_semantic_snapshot(PHASE06_INPUT_HEAD)
