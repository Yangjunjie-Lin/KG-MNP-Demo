from __future__ import annotations

from tests.refactor._historical_freeze import assert_prompt01_semantic_snapshot

STAGE08 = "4dc09d9cfb15da3746f108755593ceb9fe805cd7"
PHASE01 = "79b7d34125b0c5cb2d5fe8546e1f4e6a95ca8106"
PHASE02 = "3ef40b9cfbd657b55d8c5f446cfc247335db87f0"
PHASE03 = "06898e8ef3fbe93bd7e7a030f4361c0bef7a76c9"


def test_all_lower_layers_are_frozen() -> None:
    for commit in (STAGE08, PHASE01, PHASE02, PHASE03):
        assert_prompt01_semantic_snapshot(commit)
