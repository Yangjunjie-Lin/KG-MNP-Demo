"""Strict Draft 2020-12 contracts for Phase 06 activation governance."""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from kg_mnp_demo.modeling.canonical_json import semantic_hash
from kg_mnp_demo.modeling.dependencies import ROOT

DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
CONTRACT_VERSION = "1.0"

ACTIVATION_KINDS = (
    "ACTIVATE_NEW_VERIFIED_PUBLICATION",
    "ROLLBACK_TO_PRIOR_VERIFIED_PUBLICATION",
)
ACTIVATION_PROPOSAL_STATUSES = (
    "DRAFT",
    "SUBMITTED",
    "APPROVED_FOR_ACTIVATION",
    "REJECTED",
    "DEFERRED",
)
TERMINAL_ACTIVATION_PROPOSAL_STATUSES = frozenset(
    {"APPROVED_FOR_ACTIVATION", "REJECTED", "DEFERRED"}
)
ACTIVATION_REVIEW_DECISIONS = (
    "APPROVE_FOR_ACTIVATION",
    "REJECT",
    "DEFER",
)
ACTIVATION_EVENT_TYPES = (
    "RegistryBootstrapped",
    "ActivationProposalCreated",
    "ActivationProposalSubmitted",
    "ActivationReviewApproved",
    "ActivationReviewRejected",
    "ActivationReviewDeferred",
    "ActivationApplied",
    "RollbackApplied",
)
ACTIVATION_EXECUTION_STATUSES = ("ACTIVATION_APPLIED", "ROLLBACK_APPLIED")
ACTIVE_POINTER_STATUS = "ACTIVE_VERIFIED_PUBLICATION"
ACTIVATION_REGISTRY_STATUS = "ACTIVATION_REGISTRY_ACTIVE"
APPLICATION_PHASE06_STATUS = "APPLICATION_PUBLICATION_ACTIVATION_VERIFIED"

SCHEMAS: dict[str, tuple[str, str]] = {
    "activation-proposal": (
        "activation_proposal.schema.json",
        "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/activation/activation-proposal/1.0",
    ),
    "activation-review-decision": (
        "activation_review_decision.schema.json",
        "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/activation/activation-review-decision/1.0",
    ),
    "activation-event": (
        "activation_event.schema.json",
        "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/activation/activation-event/1.0",
    ),
    "current-publication-pointer": (
        "current_publication_pointer.schema.json",
        "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/activation/current-publication-pointer/1.0",
    ),
    "activation-registry": (
        "activation_registry.schema.json",
        "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/activation/activation-registry/1.0",
    ),
    "activation-execution-receipt": (
        "activation_execution_receipt.schema.json",
        "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/activation/activation-execution-receipt/1.0",
    ),
    "application-phase06-attestation": (
        "application_phase06_attestation.schema.json",
        "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/activation/application-phase06-attestation/1.0",
    ),
}


class ActivationContractError(ValueError):
    """Contract parsing or validation failed."""


def unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build an object while rejecting duplicate keys case-insensitively."""

    result: dict[str, Any] = {}
    folded: set[str] = set()
    for key, value in pairs:
        marker = key.casefold()
        if marker in folded:
            raise ActivationContractError(f"duplicate JSON key: {key}")
        folded.add(marker)
        result[key] = value
    return result


def strict_json_bytes(raw: bytes) -> Any:
    """Parse UTF-8 JSON without duplicate keys or non-finite numbers."""

    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=unique_json_object,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"non-finite JSON number: {value}")
            ),
        )
    except (
        UnicodeError,
        json.JSONDecodeError,
        ValueError,
        ActivationContractError,
    ) as exc:
        raise ActivationContractError("invalid strict JSON") from exc


def strict_json_file(path: Path) -> dict[str, Any]:
    value = strict_json_bytes(Path(path).read_bytes())
    if not isinstance(value, dict):
        raise ActivationContractError("JSON root must be an object")
    return value


@lru_cache(maxsize=len(SCHEMAS))
def _schema(name: str, root: Path = ROOT) -> dict[str, Any]:
    if name not in SCHEMAS:
        raise ActivationContractError(f"unknown activation contract: {name}")
    filename, identifier = SCHEMAS[name]
    value = strict_json_file(Path(root) / "schemas" / "activation" / filename)
    if (
        value.get("$schema") != DRAFT_2020_12
        or value.get("$id") != identifier
        or value.get("additionalProperties") is not False
    ):
        raise ActivationContractError(f"invalid activation schema identity: {name}")
    try:
        Draft202012Validator.check_schema(value)
    except Exception as exc:
        raise ActivationContractError(f"invalid activation schema: {name}") from exc
    return value


def load_activation_schema(name: str, root: Path = ROOT) -> dict[str, Any]:
    """Return an isolated copy of a verified Phase 06 schema."""

    return deepcopy(_schema(name, root))


def validate_activation_contract(
    name: str,
    value: Any,
    root: Path = ROOT,
) -> None:
    """Validate a value against a named Phase 06 contract."""

    try:
        errors = sorted(
            Draft202012Validator(
                load_activation_schema(name, root),
                format_checker=FormatChecker(),
            ).iter_errors(value),
            key=lambda error: [str(part) for part in error.absolute_path],
        )
    except ActivationContractError:
        raise
    except Exception as exc:
        raise ActivationContractError(str(exc)) from exc
    if errors:
        location = "/".join(str(part) for part in errors[0].absolute_path)
        raise ActivationContractError(
            f"{name} at {location or '<root>'}: {errors[0].message}"
        )


def activation_contract_hash(root: Path = ROOT) -> str:
    """Hash the complete verified Phase 06 schema set deterministically."""

    return semantic_hash(
        {name: load_activation_schema(name, root) for name in sorted(SCHEMAS)}
    )
