from __future__ import annotations

from pathlib import Path
from typing import Any
import time

from .client import GraphDBClient
from ._io import read_json
from .identifiers import validate_repository_id, repository_id_for_publication


class GraphDBImportError(RuntimeError):
    pass


def _assert_empty_ruleset(repository_info: dict[str, Any]) -> None:
    ruleset = repository_info.get("params", {}).get("ruleset")
    if isinstance(ruleset, dict):
        ruleset = ruleset.get("value")
    if ruleset != "empty":
        raise GraphDBImportError("created repository did not report ruleset=empty")


def _wait_for_import_count(
    client: GraphDBClient, repository_id: str, expected: int, *, timeout: float = 90.0
) -> int:
    deadline = time.monotonic() + timeout
    last = -1
    while True:
        last = client.count_repository_statements(repository_id)
        if last == expected:
            return last
        if time.monotonic() >= deadline:
            raise GraphDBImportError(
                f"GraphDB import did not reach expected count {expected}; observed {last}"
            )
        time.sleep(0.5)


def import_package(client: GraphDBClient, package_directory: Path, *, cleanup_failed_generated_repository: bool = False) -> dict[str, Any]:
    package_directory = Path(package_directory)
    manifest = read_json(package_directory / "graphdb-import-manifest.json")
    repository_id = manifest["repository_id"]
    validate_repository_id(repository_id)
    if repository_id != repository_id_for_publication(manifest["publication_semantic_hash"]):
        raise GraphDBImportError("repository id is not bound to publication hash")
    repositories = client.list_repositories()
    if repository_id in repositories:
        raise GraphDBImportError("refusing to overwrite an existing repository")
    config = (package_directory / "repository" / "repository-config.ttl").read_bytes()
    data = (package_directory / "import" / "knowledge-graph.nq").read_bytes()
    created = False
    started = time.monotonic()
    try:
        create_status = client.create_repository(config)
        created = True
        repository_info = client.inspect_repository(repository_id)
        _assert_empty_ruleset(repository_info)
        initial_count = client.count_repository_statements(repository_id)
        if initial_count != 0:
            raise GraphDBImportError("fresh GraphDB repository is not empty")
        import_status = client.import_nquads(repository_id, data)
        final_count = _wait_for_import_count(
            client, repository_id, int(manifest["assembled_quad_count"])
        )
        return {"repository_id": repository_id, "create_status": create_status, "initial_count": initial_count, "repository_ruleset": "empty", "import_status": import_status, "final_count": final_count, "duration_seconds": round(time.monotonic() - started, 6)}
    except Exception:
        if created and cleanup_failed_generated_repository:
            try:
                client.delete_generated_repository(repository_id)
            except Exception:
                pass
        raise
