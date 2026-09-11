from __future__ import annotations

from typing import Any

IMPORT_STEPS = (
    "verify Stage 03 authority",
    "reconstruct and verify Stage 06 package",
    "reconstruct and verify GraphDBImportPackage",
    "start pinned GraphDB",
    "verify product version",
    "verify license accepted",
    "verify repository does not exist",
    "create repository",
    "verify ruleset=empty",
    "verify repository initially empty",
    "import canonical N-Quads",
    "verify named graph exact set",
    "verify exact per-graph counts",
    "verify physical default graph empty",
    "verify forbidden assertion set absent",
    "verify business/TBox separation",
    "verify provenance coverage",
    "verify review audit structure",
    "verify exact ontology/version pairs",
    "export explicit repository N-Quads",
    "compare semantic hash",
    "export with inference",
    "prove no inferred statements",
    "produce IMPORT_VERIFIED Attestation",
    "delete generated repository",
    "docker compose down -v",
)


def build_import_plan(*, publication_id: str, repository_id: str, query_suite_id: str, dataset_path: str = "import/knowledge-graph.nq") -> dict[str, Any]:
    return {
        "contract_version": "1.0",
        "plan_id": f"urn:kg-mnp:graphdb-import-plan:{publication_id.rsplit(':', 1)[-1]}",
        "publication_id": publication_id,
        "repository_id": repository_id,
        "query_suite_id": query_suite_id,
        "authoritative_import": {"path": dataset_path, "format": "NQUADS", "preserve_named_graphs": True},
        "steps": [{"step": index, "action": action} for index, action in enumerate(IMPORT_STEPS, start=1)],
        "failure_policy": {"continue_after_failure": False, "mark_partial_success": False, "overwrite_repository": False, "delete_failed_repository": False},
    }
