from __future__ import annotations

from typing import Any

IMPORT_STEPS = (
    "verify source compilation",
    "verify GraphDB runtime",
    "assert repository does not exist",
    "create fresh repository",
    "assert repository empty",
    "import canonical N-Quads",
    "wait for transaction completion",
    "verify named graph counts",
    "run invariant query suite",
    "export explicit N-Quads",
    "compare exported semantic hash",
    "produce runtime attestation",
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
