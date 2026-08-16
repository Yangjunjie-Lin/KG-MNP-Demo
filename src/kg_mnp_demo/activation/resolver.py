"""Fail-closed, read-only resolution of the selected immutable publication."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from typing import Any

from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes

from .errors import ActivationError, ActivationErrorCode
from .execution import TargetReverifier
from .persistence import ActivationStateStore
from .registry import (
    ActivationRegistry,
    resolve_authority_target,
    target_descriptor,
)


def _pointer_target(pointer: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "publication_id": pointer["active_publication_id"],
        "publication_semantic_hash": pointer["active_publication_semantic_hash"],
        "repository_id": pointer["active_repository_id"],
        "repository_semantic_hash": pointer["active_repository_semantic_hash"],
        "publication_attestation_sha256": pointer[
            "active_publication_attestation_sha256"
        ],
        "lineage_source_type": pointer["lineage_source_type"],
        "lineage_source_attestation_sha256": pointer[
            "lineage_source_attestation_sha256"
        ],
    }


def _anchor(value: str | Callable[[], str] | None) -> str | None:
    return value() if callable(value) else value


def _effective_anchor(
    configured: str | Callable[[], str] | None,
    supplied: str | None,
    *,
    label: str,
) -> str | None:
    """Keep a separately configured trust anchor non-overridable."""

    trusted = _anchor(configured)
    if trusted is not None:
        if supplied is not None and supplied != trusted:
            raise ActivationError(
                ActivationErrorCode.REGISTRY_TAMPERED,
                f"{label} differs from the configured trusted anchor",
            )
        return trusted
    return supplied


class ActivePublicationResolver:
    """Resolve exactly the governed head; no fallback or repair path exists."""

    def __init__(
        self,
        store: ActivationStateStore,
        verifier: TargetReverifier,
        *,
        trusted_registry_hash: str | Callable[[], str] | None = None,
        trusted_head_event_hash: str | Callable[[], str] | None = None,
    ):
        self.store = store
        self.verifier = verifier
        self.trusted_registry_hash = trusted_registry_hash
        self.trusted_head_event_hash = trusted_head_event_hash

    def resolve_current(
        self,
        *,
        expected_registry_hash: str | None = None,
        expected_head_event_hash: str | None = None,
    ) -> dict[str, Any]:
        registry_anchor = _effective_anchor(
            self.trusted_registry_hash,
            expected_registry_hash,
            label="registry hash",
        )
        head_anchor = _effective_anchor(
            self.trusted_head_event_hash,
            expected_head_event_hash,
            label="head event hash",
        )

        def resolve(
            registry: ActivationRegistry, state: Mapping[str, Any]
        ) -> dict[str, Any]:
            pointer = state["current_pointer"]
            try:
                target = resolve_authority_target(
                    registry.authority, pointer["active_publication_id"]
                )
                descriptor = target_descriptor(target)
                if canonical_json_bytes(descriptor) != canonical_json_bytes(
                    _pointer_target(pointer)
                ):
                    raise ActivationError(ActivationErrorCode.POINTER_TAMPERED)
                evidence = dict(self.verifier.verify(target))
            except ActivationError as exc:
                if exc.code == ActivationErrorCode.TARGET_REPOSITORY_HASH_MISMATCH:
                    raise ActivationError(
                        ActivationErrorCode.ACTIVE_REPOSITORY_MISMATCH,
                        "active repository semantic hash no longer matches",
                    ) from exc
                if exc.code in {
                    ActivationErrorCode.TARGET_REPOSITORY_UNAVAILABLE,
                    ActivationErrorCode.TARGET_PUBLICATION_UNAVAILABLE,
                    ActivationErrorCode.TARGET_PUBLICATION_TAMPERED,
                    ActivationErrorCode.UNVERIFIED_ACTIVATION_TARGET,
                }:
                    raise ActivationError(
                        ActivationErrorCode.ACTIVE_PUBLICATION_NOT_READY,
                        "active publication is unavailable or tampered; no fallback was selected",
                    ) from exc
                raise
            if (
                evidence.get("publication_attestation_sha256")
                != descriptor["publication_attestation_sha256"]
                or evidence.get("expected_repository_semantic_hash")
                != descriptor["repository_semantic_hash"]
                or evidence.get("live_repository_semantic_hash")
                != descriptor["repository_semantic_hash"]
            ):
                raise ActivationError(ActivationErrorCode.ACTIVE_REPOSITORY_MISMATCH)
            return {
                "contract_version": "1.0",
                "pointer_id": pointer["pointer_id"],
                "pointer_hash": pointer["pointer_hash"],
                "generation": pointer["generation"],
                "active_publication_id": descriptor["publication_id"],
                "active_publication_semantic_hash": descriptor[
                    "publication_semantic_hash"
                ],
                "active_repository_id": descriptor["repository_id"],
                "active_repository_semantic_hash": descriptor[
                    "repository_semantic_hash"
                ],
                "active_publication_attestation_sha256": descriptor[
                    "publication_attestation_sha256"
                ],
                "verification_evidence_hashes": deepcopy(evidence),
                "registry_hash": state["registry_hash"],
                "head_event_hash": state["head_event_hash"],
                "semantic_authority": False,
                "deployment_selection_metadata": True,
                "status": "ACTIVE_PUBLICATION_READY",
            }

        return self.store.inspect(
            resolve,
            expected_registry_hash=registry_anchor,
            expected_head_event_hash=head_anchor,
        )
