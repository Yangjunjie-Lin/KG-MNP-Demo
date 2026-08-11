"""Versioned mappings for classifications, severities and templates."""

from __future__ import annotations

from enum import Enum
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import yaml

from kg_mnp_demo.modeling.canonical_json import semantic_hash
from kg_mnp_demo.modeling.dependencies import ROOT, _UniqueKeyLoader

from .contracts import validate_diagnostic_contract


POLICY_VERSION = "1.0.0"
POLICY_PATH = ROOT / "config" / "diagnostics" / "diagnostic-policy-1.0.0.yaml"


class DiagnosticClassification(str, Enum):
    REQUIRED_VALUE_MISSING = "REQUIRED_VALUE_MISSING"
    OPTIONAL_VALUE_ABSENT = "OPTIONAL_VALUE_ABSENT"
    VALUE_UNKNOWN = "VALUE_UNKNOWN"
    VALUE_UNCERTAIN = "VALUE_UNCERTAIN"
    VALUE_NOT_APPLICABLE = "VALUE_NOT_APPLICABLE"
    FORMAL_CONSTRAINT_VIOLATION = "FORMAL_CONSTRAINT_VIOLATION"
    FORMAL_CONSTRAINT_WARNING = "FORMAL_CONSTRAINT_WARNING"
    FORMAL_CONSTRAINT_INFO = "FORMAL_CONSTRAINT_INFO"
    CONFIRMED_VALUE_CONFLICT = "CONFIRMED_VALUE_CONFLICT"
    HISTORICAL_REVIEW_CONFLICT = "HISTORICAL_REVIEW_CONFLICT"
    EVIDENCE_REQUIRED_MISSING = "EVIDENCE_REQUIRED_MISSING"
    SOURCE_REQUIRED_MISSING = "SOURCE_REQUIRED_MISSING"
    REJECTED_CANDIDATE_HISTORY = "REJECTED_CANDIDATE_HISTORY"
    DEFERRED_CANDIDATE_HISTORY = "DEFERRED_CANDIDATE_HISTORY"


class DiagnosticSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    VIOLATION = "VIOLATION"


class DiagnosticScope(str, Enum):
    CURRENT_DIAGNOSTIC = "CURRENT_DIAGNOSTIC"
    HISTORICAL_REVIEW_CONTEXT = "HISTORICAL_REVIEW_CONTEXT"


@lru_cache(maxsize=1)
def _load_diagnostic_policy_cached(path: Path = POLICY_PATH) -> dict[str, Any]:
    try:
        value = yaml.load(
            Path(path).read_text(encoding="utf-8"),
            Loader=_UniqueKeyLoader,
        )
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ValueError("cannot load diagnostic policy") from exc
    if not isinstance(value, dict):
        raise ValueError("diagnostic policy root must be an object")
    validate_diagnostic_contract("diagnostic-policy", value)
    if set(value["classifications"]) != {
        classification.value for classification in DiagnosticClassification
    }:
        raise ValueError("diagnostic policy classification set mismatch")
    return value


def load_diagnostic_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    return deepcopy(_load_diagnostic_policy_cached(path))


def diagnostic_policy_hash(policy: Mapping[str, Any] | None = None) -> str:
    return semantic_hash(dict(policy or load_diagnostic_policy()))


def classification_mapping(
    classification: DiagnosticClassification | str,
    policy: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    value = (
        classification.value
        if isinstance(classification, DiagnosticClassification)
        else DiagnosticClassification(classification).value
    )
    document = policy or load_diagnostic_policy()
    return dict(document["classifications"][value])


def shacl_classification(
    severity: str,
    policy: Mapping[str, Any] | None = None,
) -> DiagnosticClassification:
    normalized = severity.rsplit("#", 1)[-1]
    document = policy or load_diagnostic_policy()
    try:
        return DiagnosticClassification(document["shacl_severity_mapping"][normalized])
    except (KeyError, ValueError) as exc:
        raise ValueError(f"unsupported formal constraint severity: {severity}") from exc
