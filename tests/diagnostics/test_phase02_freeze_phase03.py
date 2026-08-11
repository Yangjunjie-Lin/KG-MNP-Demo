from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STAGE08 = "4dc09d9cfb15da3746f108755593ceb9fe805cd7"
PHASE01 = "79b7d34125b0c5cb2d5fe8546e1f4e6a95ca8106"
PHASE02 = "3ef40b9cfbd657b55d8c5f446cfc247335db87f0"
FOUNDATION_PATHS = (
    "ontology",
    "shapes",
    "schemas/modeling",
    "schemas/compilation",
    "schemas/graphdb",
    "schemas/webvowl",
    "schemas/publication",
    "config/modeling",
    "config/compilation",
    "config/graphdb",
    "config/webvowl",
    "src/kg_mnp_demo/modeling",
    "src/kg_mnp_demo/review",
    "src/kg_mnp_demo/compilation",
    "src/kg_mnp_demo/graphdb",
    "src/kg_mnp_demo/webvowl",
    "src/kg_mnp_demo/publication",
)
PHASE01_PATHS = (
    "config/application",
    "queries/application",
    "schemas/application",
    "src/kg_mnp_demo/application",
    "examples/application",
    "tests/application",
    "scripts/application_integration.py",
    "scripts/verify_application_phase01_artifact.py",
)
PHASE02_PATHS = (
    "config/workbench",
    "schemas/workbench",
    "src/kg_mnp_demo/workbench",
    "web/workbench",
    "tests/workbench",
    "scripts/workbench_integration.py",
    "scripts/verify_application_phase02_artifact.py",
)


def changed_since(baseline: str, paths: tuple[str, ...]) -> list[str]:
    completed = subprocess.run(
        ["git", "diff", "--name-only", baseline, "--", *paths],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    status = subprocess.run(
        ["git", "status", "--porcelain", "--", *paths],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [*completed.stdout.splitlines(), *status.stdout.splitlines()]


def test_all_lower_authority_and_presentation_layers_are_frozen() -> None:
    assert changed_since(STAGE08, FOUNDATION_PATHS) == []
    assert changed_since(PHASE01, PHASE01_PATHS) == []
    assert changed_since(PHASE02, PHASE02_PATHS) == []


def test_phase01_query_registry_hash_remains_frozen() -> None:
    from kg_mnp_demo.application.query_registry import QueryRegistry

    registry = QueryRegistry.load(ROOT / "config/application/query-registry-1.0.0.yaml")
    assert registry.document_hash == "d45644a041621263ba86a9e7b3ea01b8c648b9569b465609c464010507682908"
