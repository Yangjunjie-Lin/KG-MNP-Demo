"""Deterministic validation checks and ValidationReport construction."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from jsonschema import ValidationError

from .canonical import file_sha256, stable_urn
from .errors import PathSecurityError
from .identifiers import resolve_within
from .registry import validate_contract

_ABSOLUTE = re.compile(r"(?:[A-Za-z]:[\\/]|/Users/|/home/|\\\\)", re.IGNORECASE)


@dataclass(frozen=True, order=True)
class ValidationCheck:
    code: str
    severity: str
    path: str
    message: str
    contract_name: str
    context: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        if self.context is None:
            value.pop("context")
        return value


def safe_subject(value: Path | str) -> str:
    """Return a report subject without leaking an absolute filesystem path."""

    text = str(value)
    return Path(text).name if Path(text).is_absolute() or _ABSOLUTE.search(text) else text


def sorted_checks(checks: Iterable[ValidationCheck]) -> tuple[ValidationCheck, ...]:
    return tuple(
        sorted(
            checks,
            key=lambda item: (
                {"ERROR": 0, "WARNING": 1, "INFO": 2}.get(item.severity, 9),
                item.code,
                item.path,
                item.message,
                item.contract_name,
            ),
        )
    )


def validation_report(
    *,
    validator: str,
    subject: Path | str,
    contract_name: str,
    checks: Iterable[ValidationCheck],
) -> dict[str, Any]:
    ordered = sorted_checks(checks)
    counts = {
        severity: sum(item.severity == severity for item in ordered)
        for severity in ("ERROR", "WARNING", "INFO")
    }
    return {
        "manifest_kind": "KG_MNP_VALIDATION_REPORT",
        "schema_version": "1.0.0",
        "validator": validator,
        "validator_version": "1.0.0",
        "subject": safe_subject(subject),
        "status": "INVALID" if counts["ERROR"] else "VALID",
        "checks": [item.to_dict() for item in ordered],
        "summary": {
            "error_count": counts["ERROR"],
            "warning_count": counts["WARNING"],
            "info_count": counts["INFO"],
        },
    }


def structural_validation_report(
    contract_name: str,
    payload: Any,
    *,
    subject: Path | str,
) -> dict[str, Any]:
    checks: list[ValidationCheck] = []
    try:
        validate_contract(contract_name, payload)
    except ValidationError as exc:
        path = "$" + "".join(f"/{item}" for item in exc.absolute_path)
        checks.append(
            ValidationCheck(
                code="CONTRACT_INVALID",
                severity="ERROR",
                path=path,
                message=exc.message,
                contract_name=contract_name,
            )
        )
    return validation_report(
        validator="kg-mnp-contracts",
        subject=subject,
        contract_name=contract_name,
        checks=checks,
    )


def artifact_manifest_checks(
    payload: dict[str, Any],
    *,
    artifact_root: Path | None = None,
) -> tuple[ValidationCheck, ...]:
    """Apply closed-set, dependency, authority and optional file-binding rules."""

    checks: list[ValidationCheck] = []
    artifacts = payload.get("artifacts", [])
    identifiers = [item.get("artifact_id") for item in artifacts if isinstance(item, dict)]
    known = set(identifiers)
    if identifiers != sorted(identifiers):
        checks.append(
            ValidationCheck("NONDETERMINISTIC_ORDER", "ERROR", "$/artifacts", "artifacts must be sorted by artifact_id", "artifact-manifest")
        )
    if len(identifiers) != len(known):
        checks.append(
            ValidationCheck("DUPLICATE_ARTIFACT_ID", "ERROR", "$/artifacts", "artifact_id values must be unique", "artifact-manifest")
        )
    graph: dict[str, set[str]] = {}
    for item in artifacts:
        artifact_id = item.get("artifact_id", "")
        dependencies = item.get("dependencies", [])
        if dependencies != sorted(dependencies):
            checks.append(ValidationCheck("NONDETERMINISTIC_ORDER", "ERROR", f"$/artifacts/{artifact_id}/dependencies", "dependencies must be sorted", "artifact-manifest"))
        if item.get("provenance_refs", []) != sorted(item.get("provenance_refs", [])):
            checks.append(ValidationCheck("NONDETERMINISTIC_ORDER", "ERROR", f"$/artifacts/{artifact_id}/provenance_refs", "provenance_refs must be sorted", "artifact-manifest"))
        dangling = sorted(set(dependencies) - known)
        if dangling:
            checks.append(ValidationCheck("DANGLING_ARTIFACT_DEPENDENCY", "ERROR", f"$/artifacts/{artifact_id}/dependencies", f"unknown artifacts: {', '.join(dangling)}", "artifact-manifest"))
        graph[artifact_id] = set(dependencies) & known
        if "confirmed" in str(item.get("artifact_type", "")).casefold():
            checks.append(ValidationCheck("UNSUPPORTED_AUTHORITY_CLAIM", "ERROR", f"$/artifacts/{artifact_id}/artifact_type", "ArtifactManifest cannot claim confirmed authority", "artifact-manifest"))
        if artifact_root is not None:
            try:
                path = resolve_within(artifact_root, item["path"])
                if path.stat().st_size != item["size_bytes"] or file_sha256(path) != item["sha256"]:
                    checks.append(ValidationCheck("ARTIFACT_FILE_MISMATCH", "ERROR", item["path"], "artifact size or SHA-256 does not match", "artifact-manifest"))
            except (OSError, KeyError, PathSecurityError) as exc:
                checks.append(ValidationCheck("ARTIFACT_PATH_INVALID", "ERROR", str(item.get("path", "$")), str(exc), "artifact-manifest"))
    for root_id in payload.get("root_artifacts", []):
        if root_id not in known:
            checks.append(ValidationCheck("DANGLING_ROOT_ARTIFACT", "ERROR", "$/root_artifacts", f"unknown artifact: {root_id}", "artifact-manifest"))
    visited: set[str] = set()
    active: list[str] = []

    def visit(node: str) -> None:
        if node in active:
            checks.append(ValidationCheck("ARTIFACT_DEPENDENCY_CYCLE", "ERROR", "$/artifacts", "artifact dependency cycle detected", "artifact-manifest"))
            return
        if node in visited:
            return
        active.append(node)
        for target in sorted(graph.get(node, set())):
            visit(target)
        active.pop()
        visited.add(node)

    for node in sorted(graph):
        visit(node)
    expected_id = stable_urn(
        "artifact-set",
        {key: value for key, value in payload.items() if key != "artifact_set_id"},
    )
    if payload.get("artifact_set_id") != expected_id:
        checks.append(ValidationCheck("ARTIFACT_SET_ID_MISMATCH", "ERROR", "$/artifact_set_id", "artifact_set_id is not derived from the canonical manifest preimage", "artifact-manifest"))
    return sorted_checks(checks)
