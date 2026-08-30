from __future__ import annotations

from tests.refactor._historical_freeze import assert_prompt01_semantic_snapshot

PHASE04_INPUT_HEAD = "3254656ffcd1c42b601d30b6ea313c6f81642bef"


def test_foundation_and_phases01_to04_are_frozen() -> None:
    assert_prompt01_semantic_snapshot(PHASE04_INPUT_HEAD)
