"""Local bearer credential store.

Only SHA-256 token digests are persisted.  Token creation and revocation are
local administrator operations; there is intentionally no HTTP enrollment
endpoint.
"""
from __future__ import annotations

import hashlib
import json
import secrets
from pathlib import Path
from typing import Any

from .errors import ServiceBoundaryError
from .models import PrincipalReference


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class TokenStore:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({"tokens": {}})

    def _read(self) -> dict[str, Any]:
        try:
            return json.loads(self.path.read_bytes())
        except (OSError, json.JSONDecodeError) as exc:
            raise ServiceBoundaryError("AUTH_STORE_INVALID", "credential store is invalid", status_code=503) from exc

    def _write(self, value: dict[str, Any]) -> None:
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        temporary.replace(self.path)

    def create(self, *, principal_id: str, principal_type: str, permissions: set[str], project_ids: set[str], created_by: str) -> tuple[str, PrincipalReference]:
        if not principal_id or principal_type not in {"HUMAN", "SERVICE"} or not created_by:
            raise ServiceBoundaryError("AUTH_CONFIGURATION_INVALID", "principal metadata is invalid")
        token = "kgmnp_" + secrets.token_urlsafe(32)
        token_id = secrets.token_hex(16)
        records = self._read()
        records["tokens"][token_id] = {"token_digest": _digest(token), "principal_id": principal_id, "principal_type": principal_type, "permissions": sorted(permissions), "project_ids": sorted(project_ids), "revoked": False, "created_by": created_by}
        self._write(records)
        return token, PrincipalReference(principal_id, principal_type, frozenset(permissions), frozenset(project_ids), token_id)

    def revoke(self, token_id: str) -> None:
        records = self._read()
        record = records.get("tokens", {}).get(token_id)
        if not record:
            raise ServiceBoundaryError("AUTH_TOKEN_NOT_FOUND", "credential not found", status_code=404)
        record["revoked"] = True
        self._write(records)

    def authenticate(self, token: str) -> PrincipalReference:
        if not token or not token.startswith("kgmnp_"):
            raise ServiceBoundaryError("AUTH_REQUIRED", "Bearer credential required", status_code=401)
        digest = _digest(token)
        for token_id, record in self._read().get("tokens", {}).items():
            if secrets.compare_digest(record.get("token_digest", ""), digest):
                if record.get("revoked"):
                    raise ServiceBoundaryError("AUTH_TOKEN_REVOKED", "credential has been revoked", status_code=401)
                return PrincipalReference(record["principal_id"], record["principal_type"], frozenset(record.get("permissions", [])), frozenset(record.get("project_ids", [])), token_id)
        raise ServiceBoundaryError("AUTH_INVALID", "credential is invalid", status_code=401)
