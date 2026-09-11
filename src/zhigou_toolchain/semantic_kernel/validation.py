"""Candidate dispatch and cross-partition invariants."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from zhigou_toolchain.modeling.control_plane.candidates import (
    recalculate_candidate_identity,
)

from .errors import CompilationPlanError

PARTITION_TYPES = {
    "TBOX": {"CLASS", "OBJECT_PROPERTY", "DATA_PROPERTY", "SUBCLASS_AXIOM", "DOMAIN_AXIOM", "RANGE_AXIOM", "DISJOINT_CLASSES_AXIOM"},
    "MAPPING": {"RECORD_TO_CLASS", "FIELD_TO_DATA_PROPERTY", "REFERENCE_TO_OBJECT_PROPERTY", "VALUE_MAPPING", "IRI_TEMPLATE", "NULL_HANDLING_POLICY"},
    "ABOX": {"INDIVIDUAL", "CLASS_ASSERTION", "DATA_PROPERTY_ASSERTION", "OBJECT_PROPERTY_ASSERTION"},
    "SHACL": {"NODE_SHAPE", "PROPERTY_SHAPE", "MIN_COUNT", "MAX_COUNT", "DATATYPE", "CLASS_CONSTRAINT", "NODE_KIND", "IN_VALUES"},
}

ACTION_PARTITIONS = {
    "REUSE_EXISTING": {"TBOX"},
    "ALIGN_TO_EXISTING": {"TBOX", "MAPPING"},
    "CREATE_NEW": {"TBOX"},
    "ASSERT": {"ABOX"},
    "CONSTRAIN": {"SHACL"},
}


def validate_confirmed_candidates(
    partitions: Mapping[str, Iterable[dict[str, Any]]],
    *,
    supported_types: set[str],
) -> tuple[dict[str, Any], ...]:
    values = []
    candidate_ids = set()
    for partition, candidates in partitions.items():
        if partition not in PARTITION_TYPES:
            raise CompilationPlanError(f"unknown confirmed partition: {partition}")
        for candidate in candidates:
            body = candidate.get("body", {})
            candidate_type = body.get("candidate_type")
            candidate_id = candidate.get("candidate_id")
            if candidate_type not in PARTITION_TYPES[partition] or candidate_type not in supported_types:
                raise CompilationPlanError(
                    f"unsupported confirmed candidate type {candidate_type!r}",
                    code="UNSUPPORTED_CONFIRMED_CANDIDATE",
                )
            action = candidate.get("candidate_action")
            if partition not in ACTION_PARTITIONS.get(action, set()):
                raise CompilationPlanError(f"candidate action {action!r} is invalid for {partition}")
            signature, recalculated_id = recalculate_candidate_identity(candidate)
            if signature != candidate.get("semantic_signature") or recalculated_id != candidate_id:
                raise CompilationPlanError("confirmed candidate identity mismatch")
            if candidate_id in candidate_ids:
                raise CompilationPlanError("duplicate confirmed candidate ID")
            candidate_ids.add(candidate_id)
            values.append({"partition": partition, "candidate": candidate})
    rejected = set()
    for value in values:
        candidate = value["candidate"]
        missing = set(candidate["dependency_candidate_refs"]) - candidate_ids
        if missing:
            raise CompilationPlanError("confirmed candidate has a missing or rejected dependency")
        if candidate.get("support_status") == "UNSUPPORTED":
            rejected.add(candidate["candidate_id"])
    if rejected:
        raise CompilationPlanError("unsupported candidates cannot enter compilation")
    return tuple(sorted(values, key=lambda item: item["candidate"]["candidate_id"]))
