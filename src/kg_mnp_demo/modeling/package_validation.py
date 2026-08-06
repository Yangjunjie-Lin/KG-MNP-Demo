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
        effective = dict(decision["modified_candidate"])
        confirmation_mode = "MODIFIED"
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
