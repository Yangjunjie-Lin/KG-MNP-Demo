"""Semantic version compatibility derived from diff classifications."""
from __future__ import annotations

import re
from typing import Any

from kg_mnp.contracts.canonical import stable_urn

from ..store import bind_identity

_SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

def _v(value: str) -> tuple[int, int, int]:
    match = _SEMVER.fullmatch(value or "")
    if not match:
        raise ValueError(f"invalid semantic version: {value}")
    return tuple(map(int, match.groups()))

def check_version(base_version: str, candidate_version: str, classification: str | dict[str, Any], *, registry_id: str | None = None, semantic_diff_id: str | None = None, pre_one_policy: str = "BREAKING_REQUIRES_MAJOR") -> dict[str, Any]:
    old, new = _v(base_version), _v(candidate_version)
    level = classification.get("overall_classification", "UNKNOWN_REQUIRES_REVIEW") if isinstance(classification, dict) else classification
    relation = "UNCHANGED" if old == new else ("PATCH" if old[:2] == new[:2] else "MINOR" if old[0] == new[0] else "MAJOR")
    compatible = level in {"NO_CHANGE", "ANNOTATION_ONLY", "PATCH_COMPATIBLE", "RELAXING", "ADDITIVE"} and relation in {"UNCHANGED", "PATCH", "MINOR"}
    issues: list[str] = []
    if level in {"BREAKING", "POTENTIALLY_BREAKING", "UNKNOWN_REQUIRES_REVIEW"} and relation != "MAJOR":
        compatible = False; issues.append("breaking-or-unknown-change-requires-major-version")
    if old[0] == 0 and level in {"BREAKING", "POTENTIALLY_BREAKING"} and new[0] == 0:
        compatible = False; issues.append(pre_one_policy.lower().replace("_", "-"))
    if new < old:
        compatible = False; issues.append("version-must-not-decrease")
    report = {"manifest_kind": "KG_MNP_VERSION_COMPATIBILITY_REPORT", "schema_version": "1.0.0", "registry_id": registry_id or stable_urn("registry", {"local": "lifecycle"}), "semantic_diff_id": semantic_diff_id or stable_urn("semantic-diff-report", {"base": base_version, "candidate": candidate_version}), "base_version": base_version, "candidate_version": candidate_version, "version_relation": relation, "semantic_classification": level, "required_version_change": "MAJOR" if level in {"BREAKING", "POTENTIALLY_BREAKING"} else "MINOR" if level == "ADDITIVE" else "PATCH", "actual_version_change": relation, "pre_one_policy": pre_one_policy, "compatible": compatible, "issues": sorted(issues)}
    bind_identity(report, "report_id", "version-compatibility-report")
    return report
