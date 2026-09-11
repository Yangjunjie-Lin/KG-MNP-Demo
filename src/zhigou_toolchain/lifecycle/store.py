"""Small deterministic record store used by lifecycle services and CLI."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from zhigou_toolchain.contracts.canonical import semantic_hash, stable_urn
from zhigou_toolchain.contracts.document_io import atomic_write_json

from .contracts import canonicalize
from .errors import LifecycleError
from .registry._common import read


def load(workspace: Path | str, filename: str) -> dict[str, Any]:
    return read(Path(workspace), filename)


def bind_identity(value: dict[str, Any], identity: str, kind: str) -> dict[str, Any]:
    """Bind an artifact identity to its canonical content digest before save."""
    try:
        from .contracts import _core, contract_for
        core = _core(contract_for(value), value)
    except Exception:  # noqa: BLE001 - useful for non-contract index records
        core = {k: v for k, v in value.items() if k not in {identity, "content_digest"}}
    digest = semantic_hash(canonicalize(core))
    value["content_digest"] = digest
    value[identity] = stable_urn(kind, {"content_digest": digest})
    return value

def save(workspace: Path | str, filename: str, value: dict[str, Any]) -> dict[str, Any]:
    root = Path(workspace); path = root / filename; path.parent.mkdir(parents=True, exist_ok=True)
    # Only the artifact's own identity field is excluded.  Reference fields
    # such as ``change_proposal_id`` on a release candidate are semantic input
    # and must remain bound by the digest.
    try:
        from .contracts import _core, contract_for, identity_field
        contract = contract_for(value)
        identity = identity_field(contract)
        core = _core(contract, value)
    except Exception:  # noqa: BLE001 - the store also accepts non-contract indexes
        identity = next((key for key in value if key.endswith("_id") and key not in {"registry_id", "package_id"}), None)
        core = {k: v for k, v in value.items() if k not in {"content_digest", identity}}
    value["content_digest"] = semantic_hash(canonicalize(core))
    atomic_write_json(path, value)
    return value

def next_id(kind: str, value: Any) -> str:
    return stable_urn(kind, value if isinstance(value, dict) else {"value": value})

def list_records(workspace: Path | str, folder: str) -> list[dict[str, Any]]:
    root = Path(workspace) / folder
    if not root.is_dir(): return []
    rows=[]
    for path in sorted(root.glob("*.json")):
        try: rows.append(json.loads(path.read_bytes()))
        except (OSError, json.JSONDecodeError) as exc: raise LifecycleError("LIFECYCLE_ARTIFACT_TAMPERED", f"invalid record: {path.name}") from exc
    return rows
