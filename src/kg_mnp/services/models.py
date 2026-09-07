"""Small explicit cross-process service contracts.

These are deliberately stdlib dataclasses.  The API layer exports the same
field definitions and does not accept arbitrary kwargs, import paths or
command strings.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4


@dataclass(frozen=True)
class ServiceConfiguration:
    workspace_root: str
    host: str = "127.0.0.1"
    port: int = 8765
    tls_termination: bool = False
    allowed_origins: tuple[str, ...] = ()
    token_store_path: str | None = None
    jobs_db_path: str | None = None
    max_upload_bytes: int = 16 * 1024 * 1024
    domain_packs_root: str | None = None
    review_profile: str = "PRODUCTION_MULTI_ROLE"
    reasoner_jar: str | None = None
    allow_insecure_loopback_session: bool = False
    workbench_root: str | None = None

    def validate(self) -> None:
        import ipaddress

        loopback = self.host in {"127.0.0.1", "localhost", "::1"}
        try:
            loopback = loopback or ipaddress.ip_address(self.host).is_loopback
        except ValueError:
            pass
        if not loopback and (not self.tls_termination or not self.allowed_origins):
            raise ValueError("non-loopback service requires TLS termination and an origin allowlist")
        if not 1 <= self.port <= 65535:
            raise ValueError("port is out of range")
        if self.review_profile not in {"PRODUCTION_MULTI_ROLE", "DEVELOPMENT_SINGLE_REVIEWER"}:
            raise ValueError("unknown review profile")
        if self.review_profile == "DEVELOPMENT_SINGLE_REVIEWER" and not loopback:
            raise ValueError("development review profile is restricted to explicit loopback service")
        if self.allow_insecure_loopback_session and not loopback:
            raise ValueError("insecure session exception is loopback only")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PrincipalReference:
    principal_id: str
    principal_type: Literal["HUMAN", "SERVICE"] = "HUMAN"
    permissions: frozenset[str] = frozenset()
    project_ids: frozenset[str] = frozenset()
    token_id: str | None = None

    def can(self, permission: str) -> bool:
        return permission in self.permissions or "*" in self.permissions

    def to_dict(self) -> dict[str, Any]:
        return {
            "principal_id": self.principal_id,
            "principal_type": self.principal_type,
            "permissions": sorted(self.permissions),
            "project_ids": sorted(self.project_ids),
            "token_id": self.token_id,
        }


@dataclass(frozen=True)
class ProjectHandle:
    project_id: str
    project_name: str
    root: str
    status: str = "OPEN"
    owner_id: str | None = None
    manifest_project_id: str | None = None
    domain_pack: str | None = None
    domain_pack_version: str | None = None
    migration_status: str | None = None
    authority_revision: int = 0

    def public_dict(self) -> dict[str, Any]:
        """A filesystem handle is never a network resource representation."""
        return {key: value for key, value in asdict(self).items() if key != "root"}

    @property
    def registry_root(self) -> Path:
        return Path(self.root) / "registry" / "lifecycle"


@dataclass(frozen=True)
class OperationDefinition:
    operation_id: str
    request_contract: str
    response_contract: str
    required_permissions: tuple[str, ...] = ()
    project_scope_required: bool = True
    execution_mode: Literal["INLINE", "JOB"] = "INLINE"
    side_effect_class: Literal["READ", "WRITE", "EXTERNAL"] = "READ"
    idempotency_policy: Literal["NONE", "OPTIONAL", "REQUIRED"] = "NONE"
    precondition_policy: str = "STATE"
    audit_policy: str = "REQUIRED"
    blocked_reason: str | None = None


@dataclass(frozen=True)
class OperationRequest:
    operation_id: str
    project_id: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    idempotency_key: str | None = None
    request_id: str = field(default_factory=lambda: uuid4().hex)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OperationResult:
    operation_id: str
    status: Literal["SUCCEEDED", "ACCEPTED", "BLOCKED"]
    payload: dict[str, Any]
    request_id: str
    job_id: str | None = None
    audit_id: str | None = None


@dataclass(frozen=True)
class ServiceError:
    code: str
    message: str
    retryable: bool = False
    details: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "message": self.message, "retryable": self.retryable, "details": list(self.details)}}


def path_for(config: ServiceConfiguration, name: str, default: str) -> Path:
    return Path(getattr(config, name) or (Path(config.workspace_root) / default))
