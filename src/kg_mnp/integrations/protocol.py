from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal
from uuid import uuid4


@dataclass(frozen=True)
class AdapterManifest:
    adapter_id: str
    adapter_version: str
    kind: str
    capabilities: tuple[str, ...]
    network_policy: str = "DENY"
    side_effect_policy: str = "READ_ONLY"


@dataclass(frozen=True)
class AdapterSnapshot:
    adapter_id: str
    adapter_version: str
    config_digest: str
    capability_digest: str


@dataclass(frozen=True)
class IntegrationTarget:
    target_id: str
    target_type: str
    target_revision: str
    scheme: str = "local"
    host: str = ""
    port: int | None = None
    base_path: str = ""
    tls_policy: str = "LOCAL_ONLY"
    credential_ref: str | None = None


@dataclass(frozen=True)
class IntegrationPlan:
    plan_id: str
    project_id: str
    release_id: str
    package_id: str
    target_id: str
    target_revision: str
    adapter_snapshot: AdapterSnapshot
    payload_digest: str
    allowed_effect: str
    environment_pointer_generation: int | None
    expiry: str | None
    preconditions: tuple[str, ...] = ()


@dataclass(frozen=True)
class IntegrationApproval:
    approval_id: str
    plan_id: str
    project_id: str
    principal_id: str
    approved_effect: str
    payload_digest: str
    target_revision: str
    expires_at: str | None


@dataclass(frozen=True)
class IntegrationReceipt:
    receipt_id: str = field(default_factory=lambda: "receipt_" + uuid4().hex)
    plan_id: str = ""
    status: Literal["PLANNED", "APPROVED", "EXECUTING", "DEPLOYMENT_VERIFIED", "FAILED", "RECONCILIATION_REQUIRED", "REQUEST_ENQUEUED", "EXTERNAL_EXECUTION_NOT_CONFIGURED"] = "PLANNED"
    desired_release_id: str | None = None
    observed_deployed_release_id: str | None = None
    observed_dataset_digest: str | None = None
    last_verification_status: str = "NOT_VERIFIED"
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)
