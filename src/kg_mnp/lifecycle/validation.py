"""Public validation helpers for lifecycle artifacts."""
from __future__ import annotations

from typing import Any

from .contracts import contract_for, validate, verify


def validate_artifact(value: dict[str, Any], contract: str | None = None) -> None:
    validate(contract or contract_for(value), value)


def verify_artifact(value: dict[str, Any], contract: str | None = None, registry_id: str | None = None) -> dict[str, Any]:
    return verify(value, contract=contract, registry_id=registry_id)


__all__ = ["contract_for", "validate_artifact", "verify_artifact"]
