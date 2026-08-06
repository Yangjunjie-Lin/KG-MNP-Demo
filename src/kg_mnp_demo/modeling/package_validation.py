"""Term-type indexing and confirmed-package structural helpers."""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from .canonical_json import semantic_hash
from .dependencies import ROOT, TERM_INVENTORY_PATH, DependencyError
from .identifiers import candidate_id, candidate_semantic_content
from .review_actions import validate_candidate_term_types, validate_instance_iri
from .review_identifiers import confirmed_item_id
from .semantic_validation import SemanticValidationError


@lru_cache(maxsize=1)
def load_term_type_index(path: Path | None = None) -> dict[str, str]:
    inventory = path or TERM_INVENTORY_PATH
    try:
        with inventory.open("r", encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
    except (OSError, UnicodeError, csv.Error) as exc:
        raise DependencyError(f"cannot read term inventory {inventory}: {exc}") from exc
    index: dict[str, str] = {}
    for row in rows:
        iri = (row.get("term_iri") or "").strip()
        term_type = (row.get("term_type") or "").strip()
        if not iri or term_type == "Ontology":
            continue
        if iri in index:
            raise DependencyError(f"duplicate term_iri in inventory: {iri}")
        index[iri] = term_type
    return index


@lru_cache(maxsize=1)
def load_functional_property_iris(path: Path | None = None) -> frozenset[str]:
    inventory = path or TERM_INVENTORY_PATH
    try:
        with inventory.open("r", encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
    except (OSError, UnicodeError, csv.Error) as exc:
        raise DependencyError(f"cannot read term inventory {inventory}: {exc}") from exc
    functional: set[str] = set()
    for row in rows:
        iri = (row.get("term_iri") or "").strip()
        characteristics = row.get("characteristics") or ""
        if iri and "FunctionalProperty" in characteristics:
            functional.add(iri)
    return frozenset(functional)


def proposal_candidates_by_id(proposal: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        item["candidate_id"]: dict(item)
        for item in [
            *proposal.get("candidate_entities", []),
            *proposal.get("candidate_assertions", []),
        ]
    }


def build_confirmed_envelope(
    *,
    decision: Mapping[str, Any],
    source_candidate: Mapping[str, Any],
    term_types: Mapping[str, str],
) -> dict[str, Any]:
    mode = decision.get("decision")
    if mode == "CONFIRM":
        effective = dict(source_candidate)
        confirmation_mode = "ORIGINAL"
    elif mode == "MODIFY_AND_CONFIRM":
        from .review_actions import validate_modified_candidate

        effective = dict(decision["modified_candidate"])
        confirmation_mode = "MODIFIED"
        validate_modified_candidate(
            source_candidate,
            effective,
            term_types=term_types,
        )
        if effective.get("candidate_kind", "ENTITY") != source_candidate.get(
            "candidate_kind", "ENTITY"
        ):
            raise SemanticValidationError(["modified candidate kind drift"])
    else:
        raise SemanticValidationError([f"cannot confirm with decision {mode!r}"])

    if effective.get("publication_scope") != "ABOX":
        raise SemanticValidationError(["confirmed candidate must remain ABOX"])
    if "proposed_iri" in effective:
        iri_errors = validate_instance_iri(str(effective["proposed_iri"]))
        if iri_errors:
            raise SemanticValidationError(iri_errors)
    type_errors = validate_candidate_term_types(effective, term_types)
    if type_errors:
        raise SemanticValidationError(type_errors)
    expected_id = candidate_id(effective)
    if effective.get("candidate_id") != expected_id:
        raise SemanticValidationError(
            ["effective candidate_id does not match semantic content"]
        )
    semantic_content = candidate_semantic_content(effective)
    semantic_hash_value = semantic_hash(semantic_content)
    item_id = confirmed_item_id(
        source_candidate_id=str(source_candidate["candidate_id"]),
        effective_candidate_id=str(effective["candidate_id"]),
        confirmation_mode=confirmation_mode,
        semantic_content=semantic_content,
    )
    return {
        "decision_id": decision["decision_id"],
        "candidate_id": source_candidate["candidate_id"],
        "decision": mode,
        "publication_scope": "ABOX",
        "confirmed_candidate": {
            "source_candidate_id": source_candidate["candidate_id"],
            "effective_candidate_id": effective["candidate_id"],
            "confirmation_mode": confirmation_mode,
            "semantic_content": semantic_content,
            "semantic_hash": semantic_hash_value,
            "confirmed_item_id": item_id,
        },
    }


def validate_confirmed_candidate_envelope(
    item: Mapping[str, Any],
    *,
    source_candidate: Mapping[str, Any],
    decision: Mapping[str, Any],
    term_types: Mapping[str, str],
) -> None:
    """Re-validate a confirmed envelope against the authoritative source decision."""

    expected = build_confirmed_envelope(
        decision=decision,
        source_candidate=source_candidate,
        term_types=term_types,
    )
    errors: list[str] = []
    if item.get("decision_id") != expected["decision_id"]:
        errors.append("confirmed item decision_id mismatch")
    if item.get("candidate_id") != expected["candidate_id"]:
        errors.append("confirmed item candidate_id mismatch")
    if item.get("decision") != expected["decision"]:
        errors.append("confirmed item decision mismatch")
    if item.get("publication_scope") != "ABOX":
        errors.append("confirmed item publication_scope must remain ABOX")
    confirmed = item.get("confirmed_candidate")
    expected_confirmed = expected["confirmed_candidate"]
    if not isinstance(confirmed, Mapping):
        raise SemanticValidationError(["confirmed item lacks confirmed_candidate envelope"])
    for field in (
        "source_candidate_id",
        "effective_candidate_id",
        "confirmation_mode",
        "semantic_content",
        "semantic_hash",
        "confirmed_item_id",
    ):
        if confirmed.get(field) != expected_confirmed.get(field):
            errors.append(f"confirmed_candidate.{field} does not match authoritative derivation")
    if decision.get("decision") == "CONFIRM":
        if confirmed.get("confirmation_mode") != "ORIGINAL":
            errors.append("CONFIRM must use ORIGINAL confirmation mode")
        if confirmed.get("effective_candidate_id") != source_candidate.get("candidate_id"):
            errors.append("CONFIRM effective_candidate_id must equal source candidate_id")
    if decision.get("decision") == "MODIFY_AND_CONFIRM":
        if confirmed.get("confirmation_mode") != "MODIFIED":
            errors.append("MODIFY_AND_CONFIRM must use MODIFIED confirmation mode")
        modified = decision.get("modified_candidate") or {}
        if confirmed.get("effective_candidate_id") != modified.get("candidate_id"):
            errors.append("MODIFY_AND_CONFIRM effective_candidate_id mismatch")
    if errors:
        raise SemanticValidationError(errors)


def assertion_subject_id(candidate: Mapping[str, Any]) -> str | None:
    subject = candidate.get("subject_ref")
    if isinstance(subject, str) and subject.startswith("urn:kg-mnp:candidate:"):
        return subject
    return None


def assertion_object_candidate_id(candidate: Mapping[str, Any]) -> str | None:
    obj = candidate.get("object")
    if isinstance(obj, str) and obj.startswith("urn:kg-mnp:candidate:"):
        return obj
    return None


def project_root() -> Path:
    return ROOT
