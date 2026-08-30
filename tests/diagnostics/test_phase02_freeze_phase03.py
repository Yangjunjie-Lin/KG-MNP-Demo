from __future__ import annotations

from pathlib import Path

from tests.refactor._historical_freeze import assert_prompt01_semantic_snapshot

ROOT = Path(__file__).resolve().parents[2]
STAGE08 = "4dc09d9cfb15da3746f108755593ceb9fe805cd7"
PHASE01 = "79b7d34125b0c5cb2d5fe8546e1f4e6a95ca8106"
PHASE02 = "3ef40b9cfbd657b55d8c5f446cfc247335db87f0"


def test_all_lower_authority_and_presentation_layers_are_frozen() -> None:
    for commit in (STAGE08, PHASE01, PHASE02):
        assert_prompt01_semantic_snapshot(commit)


def test_phase01_query_registry_hash_remains_frozen() -> None:
    from kg_mnp.application.query_registry import QueryRegistry

    registry = QueryRegistry.load(
        ROOT / "domain_packs/mnp/queries/query-registry-1.0.0.yaml"
    )
    assert registry.document_hash == "8971d445a26bf97b855bb0174edd446f4dd9204fd7dc4c48e734a0f9fce5c0e6"
