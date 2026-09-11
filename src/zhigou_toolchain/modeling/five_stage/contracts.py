"""Versioned internal adapters; do not replace frozen Domain Contract IDs."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from zhigou_toolchain.contracts.canonical import semantic_hash, stable_urn

ExecutionStatus = Literal["NOT_RUN", "READY", "RUNNING", "BLOCKED", "SUCCEEDED", "FAILED", "CANCELLED", "STALE"]
ValidationStatus = Literal["PASS", "FAIL", "NOT_RUN", "NOT_APPLICABLE", "ERROR", "TIMEOUT"]
ReviewStatus = Literal["PENDING", "APPROVED", "REJECTED", "CHANGES_REQUESTED"]
ExecutionSource = Literal["LIVE", "DETERMINISTIC", "RECORDED_MODEL_OUTPUT", "TUTORIAL_FIXTURE"]


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class ArtifactRef(DTO):
    artifact_id: str
    schema_version: Literal["1.0.0"] = "1.0.0"
    project_id: str
    session_id: str
    stage_id: int = Field(ge=0, le=5)
    step_id: str
    artifact_version: str
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    storage_ref: str = Field(pattern=r"^urn:kg-mnp:stage-artifact:[a-f0-9]{64}$")
    media_type: Literal["application/json"] = "application/json"
    data_kind: Literal["KG_IR", "MODELING_CANDIDATE", "SEMANTIC_DELIVERY", "REPORT", "CONFIGURATION"]
    record_count: int = Field(ge=0)
    produced_by: str
    hash_profile: Literal["KG-MNP Canonical JSON v1"] = "KG-MNP Canonical JSON v1"


class StepRun(DTO):
    schema_version: Literal["1.0.0"] = "1.0.0"
    step_id: str = Field(pattern=r"^[1-5]\.[1-6]$")
    run_id: str
    input_artifact_refs: list[ArtifactRef]
    output_artifact_refs: list[ArtifactRef]
    execution_kind: ExecutionSource
    job_id: str | None = None
    configuration_hash: str
    tool_versions: dict[str, str]
    model_revision: str | None = None
    status: ExecutionStatus
    validation_status: ValidationStatus = "NOT_RUN"
    review_status: ReviewStatus = "PENDING"
    validation_refs: list[str] = Field(default_factory=list)
    review_refs: list[str] = Field(default_factory=list)
    created_at: str
    scope: str


class StageRun(DTO):
    schema_version: Literal["1.0.0"] = "1.0.0"
    bundle_id: str
    stage_id: int = Field(ge=0, le=5)
    session_id: str
    parent_bundle_refs: list[str]
    inherited_artifact_refs: list[ArtifactRef]
    new_artifact_refs: list[ArtifactRef]
    status: ExecutionStatus = "NOT_RUN"
    authority: Literal["OBSERVATION_ONLY"] = "OBSERVATION_ONLY"


class ModelingSession(DTO):
    schema_version: Literal["1.0.0"] = "1.0.0"
    session_id: str
    project_id: str
    source_run_id: str
    stages: list[StageRun]
    step_runs: list[StepRun]
    delivery_status: Literal["NOT_DELIVERED", "VALIDATED_UNPUBLISHED"] = "NOT_DELIVERED"


def artifact(value: Any, *, project_id: str, session_id: str, step_id: str,
             produced_by: str, data_kind="REPORT") -> dict:
    digest = semantic_hash(value)
    identifier = stable_urn("stage-artifact", {"project_id": project_id, "session_id": session_id,
                            "step_id": step_id, "hash": digest, "data_kind": data_kind,
                            "produced_by": produced_by})
    ref = ArtifactRef(artifact_id=identifier, project_id=project_id, session_id=session_id,
                      stage_id=int(step_id.split(".")[0]), step_id=step_id,
                      artifact_version=digest, content_hash=digest, storage_ref=identifier,
                      data_kind=data_kind, record_count=len(value) if isinstance(value, list) else 1,
                      produced_by=produced_by)
    return {"ref": ref.model_dump(), "content": value}


def receipt(step_id: str, inputs: list[dict], outputs: list[dict], *, configuration: dict,
            tools: dict[str, str], scope: str, execution_kind="DETERMINISTIC", model_revision=None) -> dict:
    input_refs, output_refs = [a["ref"] for a in inputs], [a["ref"] for a in outputs]
    return StepRun(step_id=step_id, run_id=stable_urn("step-run", {"step": step_id, "inputs": input_refs,
                   "outputs": output_refs, "config": configuration, "tools": tools}),
                   input_artifact_refs=input_refs, output_artifact_refs=output_refs,
                   execution_kind=execution_kind, configuration_hash=semantic_hash(configuration),
                   tool_versions=tools, model_revision=model_revision, status="SUCCEEDED",
                   created_at=datetime.now(UTC).isoformat(), scope=scope).model_dump()


def verify_handoff(previous: list[dict], following: list[dict]) -> None:
    """A matching label/count is insufficient: compare the entire immutable ref."""
    index = {a["artifact_id"]: ArtifactRef.model_validate(a).model_dump() for a in previous}
    for raw in following:
        ref = ArtifactRef.model_validate(raw).model_dump()
        if index.get(ref["artifact_id"]) != ref:
            raise ValueError("ARTIFACT_HANDOFF_MISMATCH")


def bind_job(receipts: list[dict], job_id: str | None) -> list[dict]:
    """Execution identity differs from immutable output content identity."""
    if not job_id or not job_id.startswith("job_"):
        raise ValueError("SERVER_JOB_REFERENCE_REQUIRED")
    return [StepRun.model_validate({**row, "job_id": job_id,
            "run_id": stable_urn("step-run", {"computation_ref": row["run_id"], "job_id": job_id})}).model_dump()
            for row in receipts]
