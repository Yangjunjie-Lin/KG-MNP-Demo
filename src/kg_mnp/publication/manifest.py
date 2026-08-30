from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from ..modeling.canonical_json import semantic_hash
from .contracts import validate_publication_contract
from .identifiers import publication_id, publication_semantic_hash


def _record(relative_path: str, role: str, data: bytes) -> dict[str, str]:
    byte_hash = hashlib.sha256(data).hexdigest()
    semantic = byte_hash
    if relative_path.endswith(".json"):
        import json

        try:
            semantic = semantic_hash(json.loads(data.decode("utf-8")))
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            pass
    identity = semantic_hash(
        {
            "relative_path": relative_path,
            "role": role,
            "byte_sha256": byte_hash,
            "semantic_sha256": semantic,
        }
    )
    return {
        "relative_path": relative_path,
        "role": role,
        "byte_sha256": byte_hash,
        "semantic_sha256": semantic,
        "artifact_id": f"urn:kg-mnp:publication-artifact:{identity}",
    }


def build_publication_manifest(
    *, lineage: Mapping[str, Any], artifact_bytes: Mapping[str, bytes]
) -> dict[str, Any]:
    records = [
        _record(path, "PUBLICATION_ARTIFACT", data)
        for path, data in sorted(artifact_bytes.items())
        if path != "publication-manifest.json"
    ]
    body = {**dict(lineage), "contract_version": "1.0", "artifact_manifest": records}
    digest = publication_semantic_hash({**body, "publication_semantic_hash": ""})
    body.update(
        {
            "publication_semantic_hash": digest,
            "publication_id": publication_id(digest),
            "publication_status": "READY_FOR_PRESENTATION",
        }
    )
    validate_publication_contract("end-to-end-publication-manifest", body)
    return body
