"""Deterministic append-only activation registry operations.

The registry is deployment metadata.  It never creates or modifies semantic
facts and every mutation is independently replayable by :mod:`validator`.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes, semantic_hash

from .contracts import validate_activation_contract
from .errors import ActivationError, ActivationErrorCode
from .event_log import build_activation_event
from .pointer import build_current_publication_pointer
from .proposal import create_activation_proposal
from .review import build_activation_review_decision
from .state_machine import require_transition


def authority_flags(authority: object) -> tuple[bool, bool]:
    """Return the explicit production/test separation carried by an authority."""

    test_only = getattr(authority, "test_only", None)
    production = getattr(authority, "production_authority", None)
    if test_only is None and isinstance(authority, Mapping):
        test_only = authority.get("test_only")
    if production is None and isinstance(authority, Mapping):
        production = authority.get("production_authority")
    if type(test_only) is not bool or type(production) is not bool:
        raise ActivationError(
            ActivationErrorCode.AUTHORITY_MISMATCH,
            "activation authority does not declare its production/test mode",
        )
    if test_only == production:
        raise ActivationError(
            ActivationErrorCode.AUTHORITY_MISMATCH,
            "activation authority mode is contradictory",
        )
    return test_only, production


def authority_binding(authority: object) -> dict[str, Any]:
    value = getattr(authority, "binding", None)
    if callable(value):
        value = value()
    if not isinstance(value, Mapping):
        raise ActivationError(
            ActivationErrorCode.AUTHORITY_MISMATCH,
            "activation authority binding is unavailable",
        )
    return deepcopy(dict(value))


def authority_binding_hash(authority: object) -> str:
    """Obtain an authority-provided hash, or hash its verified binding projection."""

    for name in ("binding_hash", "authority_semantic_hash"):
        value = getattr(authority, name, None)
        if callable(value):
            value = value()
        if isinstance(value, str) and len(value) == 64:
            return value
    return semantic_hash(authority_binding(authority))


def target_descriptor(target: object) -> dict[str, Any]:
    """Project an authority-owned target into the exact pointer/proposal shape."""

    value: Any = getattr(target, "descriptor", target)
    if callable(value):
        value = value()
    required = {
        "publication_id",
        "publication_semantic_hash",
        "repository_id",
        "repository_semantic_hash",
        "publication_attestation_sha256",
        "lineage_source_type",
        "lineage_source_attestation_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise ActivationError(
            ActivationErrorCode.AUTHORITY_MISMATCH,
            "verified publication target descriptor is invalid",
        )
    return deepcopy(dict(value))


def base_target(authority: object) -> object:
    for name in ("base_publication", "base_target"):
        value = getattr(authority, name, None)
        if value is not None:
            return value
    raise ActivationError(
        ActivationErrorCode.AUTHORITY_MISMATCH,
        "activation authority has no verified bootstrap publication",
    )


def eligible_targets(authority: object) -> tuple[object, ...]:
    for name in ("activation_candidates", "eligible_new_publications", "candidates"):
        value = getattr(authority, name, None)
        if value is not None:
            return tuple(value)
    return ()


def resolve_authority_target(authority: object, publication_id: str) -> object:
    resolver = getattr(authority, "resolve_target", None)
    if callable(resolver):
        try:
            return resolver(publication_id)
        except ActivationError:
            raise
        except Exception as exc:
            raise ActivationError(
                ActivationErrorCode.UNVERIFIED_ACTIVATION_TARGET,
                f"target is not in verified activation authority: {publication_id}",
            ) from exc
    values = (base_target(authority), *eligible_targets(authority))
    for target in values:
        if target_descriptor(target)["publication_id"] == publication_id:
            return target
    raise ActivationError(
        ActivationErrorCode.UNVERIFIED_ACTIVATION_TARGET,
        f"target is not in verified activation authority: {publication_id}",
    )


def target_binding_hash(authority: object, publication_id: str) -> str:
    builder = getattr(authority, "target_binding_hash", None)
    if callable(builder):
        value = builder(publication_id)
        if isinstance(value, str) and len(value) == 64:
            return value
        raise ActivationError(ActivationErrorCode.AUTHORITY_MISMATCH)
    return semantic_hash(
        {
            "authority_binding_hash": authority_binding_hash(authority),
            "target": target_descriptor(
                resolve_authority_target(authority, publication_id)
            ),
        }
    )


def registry_semantic_content(registry: Mapping[str, Any]) -> dict[str, Any]:
    content = {
        key: deepcopy(value)
        for key, value in registry.items()
        if key != "registry_hash"
    }
    # Timestamps are audit metadata, never control-plane identity inputs.
    content["events"] = [
        {key: deepcopy(value) for key, value in event.items() if key != "observed_at"}
        for event in registry["events"]
    ]
    return content


def _finalize(registry: dict[str, Any], current_pointer: Mapping[str, Any]) -> None:
    events = registry["events"]
    registry["registry_revision"] = len(events)
    registry["head_event_hash"] = events[-1]["event_hash"] if events else "GENESIS"
    registry["current_pointer_hash"] = current_pointer["pointer_hash"]
    registry["registry_hash"] = semantic_hash(registry_semantic_content(registry))
    validate_activation_contract("activation-registry", registry)


def new_activation_registry(
    authority: object, *, observed_at: str | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Bootstrap generation zero from the authority-owned Stage08 P0."""

    test_only, production = authority_flags(authority)
    binding_hash = authority_binding_hash(authority)
    target = target_descriptor(base_target(authority))
    registry_prefix = (
        "urn:kg-mnp:test-fixture:phase06:activation-registry:"
        if test_only
        else "urn:kg-mnp:activation-registry:"
    )
    registry_id = registry_prefix + semantic_hash(
        {"authority_binding_hash": binding_hash, "base_publication": target}
    )
    pointer = build_current_publication_pointer(
        registry_id=registry_id,
        generation=0,
        target=target,
        previous_pointer_hash="GENESIS",
        test_only=test_only,
    )
    event = build_activation_event(
        sequence=1,
        previous_event_hash="GENESIS",
        event_type="RegistryBootstrapped",
        payload={
            "bootstrap_pointer": pointer,
            "bootstrap_authority_binding_hash": binding_hash,
            "bootstrap_status": "BOOTSTRAP_CURRENT_REFERENCE",
        },
        test_only=test_only,
        production_authority=production,
        observed_at=observed_at,
    )
    registry: dict[str, Any] = {
        "contract_version": "1.0",
        "registry_id": registry_id,
        "authority_binding_hash": binding_hash,
        "bootstrap_pointer": deepcopy(pointer),
        "events": [event],
        "registry_revision": 0,
        "head_event_hash": "GENESIS",
        "current_pointer_hash": pointer["pointer_hash"],
        "registry_hash": "0" * 64,
        "semantic_authority": False,
        "deployment_governance_only": True,
        "test_only": test_only,
        "production_authority": production,
        "status": "ACTIVATION_REGISTRY_ACTIVE",
    }
    _finalize(registry, pointer)
    from .validator import validate_activation_registry_against_authorities

    validate_activation_registry_against_authorities(
        registry, authority, current_pointer=pointer
    )
    return registry, pointer


@dataclass
class ActivationRegistry:
    """Mutable façade whose value remains a deterministic append-only document."""

    value: dict[str, Any]
    authority: object
    current_pointer: dict[str, Any]

    @classmethod
    def initialize(
        cls, authority: object, *, observed_at: str | None = None
    ) -> ActivationRegistry:
        value, pointer = new_activation_registry(authority, observed_at=observed_at)
        return cls(value, authority, pointer)

    def reconstruct(
        self,
        *,
        expected_registry_hash: str | None = None,
        expected_head_event_hash: str | None = None,
    ) -> dict[str, Any]:
        from .validator import validate_activation_registry_against_authorities

        return validate_activation_registry_against_authorities(
            self.value,
            self.authority,
            current_pointer=self.current_pointer,
            expected_registry_hash=expected_registry_hash,
            expected_head_event_hash=expected_head_event_hash,
        )

    def _require_registry_cas(
        self, expected_registry_revision: int, expected_head_event_hash: str
    ) -> dict[str, Any]:
        if (
            expected_registry_revision != self.value["registry_revision"]
            or expected_head_event_hash != self.value["head_event_hash"]
        ):
            raise ActivationError(ActivationErrorCode.ACTIVATION_CONCURRENCY_CONFLICT)
        return self.reconstruct()

    def _append(
        self,
        event_type: str,
        payload: Mapping[str, Any],
        *,
        observed_at: str | None = None,
        current_pointer: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = build_activation_event(
            sequence=len(self.value["events"]) + 1,
            previous_event_hash=self.value["head_event_hash"],
            event_type=event_type,
            payload=payload,
            test_only=self.value["test_only"],
            production_authority=self.value["production_authority"],
            observed_at=observed_at,
        )
        self.value["events"].append(event)
        if current_pointer is not None:
            self.current_pointer = deepcopy(dict(current_pointer))
        _finalize(self.value, self.current_pointer)
        return deepcopy(event)

    def create_proposal(
        self,
        *,
        target_publication_id: str,
        activation_kind: str,
        rationale: str,
        created_by_label: str,
        explicit_human_intent: bool,
        expected_registry_revision: int,
        expected_head_event_hash: str,
        observed_at: str | None = None,
    ) -> dict[str, Any]:
        state = self._require_registry_cas(
            expected_registry_revision, expected_head_event_hash
        )
        historical_ids = {
            item["active_publication_id"] for item in state["pointer_history"]
        }
        if (
            activation_kind == "ROLLBACK_TO_PRIOR_VERIFIED_PUBLICATION"
            and target_publication_id not in historical_ids
        ):
            raise ActivationError(ActivationErrorCode.UNKNOWN_ROLLBACK_TARGET)
        target_object = resolve_authority_target(self.authority, target_publication_id)
        target = target_descriptor(target_object)
        if target["publication_id"] == self.current_pointer["active_publication_id"]:
            raise ActivationError(ActivationErrorCode.INVALID_ACTIVATION_REQUEST)
        eligible_ids = {
            target_descriptor(item)["publication_id"]
            for item in eligible_targets(self.authority)
        }
        if (
            activation_kind == "ACTIVATE_NEW_VERIFIED_PUBLICATION"
            and target_publication_id not in eligible_ids
        ):
            raise ActivationError(ActivationErrorCode.UNVERIFIED_ACTIVATION_TARGET)
        proposal = create_activation_proposal(
            activation_kind=activation_kind,
            target=target,
            base_pointer_hash=self.current_pointer["pointer_hash"],
            base_generation=self.current_pointer["generation"],
            target_authority_binding_hash=target_binding_hash(
                self.authority, target_publication_id
            ),
            rationale=rationale,
            created_by_label=created_by_label,
            explicit_human_intent=explicit_human_intent,
            test_only=self.value["test_only"],
            production_authority=self.value["production_authority"],
        )
        if proposal["activation_proposal_id"] in {
            item["activation_proposal_id"] for item in state["proposals"]
        }:
            raise ActivationError(ActivationErrorCode.REPLAY_DETECTED)
        self._append("ActivationProposalCreated", proposal, observed_at=observed_at)
        self.reconstruct()
        return deepcopy(proposal)

    def submit_proposal(
        self,
        proposal_id: str,
        *,
        expected_registry_revision: int,
        expected_head_event_hash: str,
        observed_at: str | None = None,
    ) -> dict[str, Any]:
        state = self._require_registry_cas(
            expected_registry_revision, expected_head_event_hash
        )
        proposal = next(
            (
                item
                for item in state["proposals"]
                if item["activation_proposal_id"] == proposal_id
            ),
            None,
        )
        if proposal is None:
            raise ActivationError(ActivationErrorCode.INVALID_ACTIVATION_REQUEST)
        if proposal["status"] != "DRAFT":
            raise ActivationError(ActivationErrorCode.REPLAY_DETECTED)
        self._require_fresh_target(proposal)
        require_transition(proposal["status"], "SUBMITTED")
        self._append(
            "ActivationProposalSubmitted",
            {"activation_proposal_id": proposal_id, "resulting_status": "SUBMITTED"},
            observed_at=observed_at,
        )
        return next(
            item
            for item in self.reconstruct()["proposals"]
            if item["activation_proposal_id"] == proposal_id
        )

    def record_review(
        self,
        proposal_id: str,
        *,
        decision: str,
        reviewed_by_label: str,
        review_note: str,
        explicit_human_action: bool,
        expected_registry_revision: int,
        expected_head_event_hash: str,
        observed_at: str | None = None,
    ) -> dict[str, Any]:
        state = self._require_registry_cas(
            expected_registry_revision, expected_head_event_hash
        )
        proposal = next(
            (
                item
                for item in state["proposals"]
                if item["activation_proposal_id"] == proposal_id
            ),
            None,
        )
        if proposal is None:
            raise ActivationError(ActivationErrorCode.INVALID_ACTIVATION_REQUEST)
        if proposal["status"] != "SUBMITTED":
            if proposal["status"] in {
                "APPROVED_FOR_ACTIVATION",
                "REJECTED",
                "DEFERRED",
            }:
                raise ActivationError(ActivationErrorCode.REPLAY_DETECTED)
            raise ActivationError(ActivationErrorCode.INVALID_ACTIVATION_REQUEST)
        self._require_fresh_target(proposal)
        review, target_status, event_type = build_activation_review_decision(
            proposal=proposal,
            decision=decision,
            reviewed_by_label=reviewed_by_label,
            review_note=review_note,
            explicit_human_action=explicit_human_action,
        )
        require_transition(proposal["status"], target_status)
        self._append(event_type, review, observed_at=observed_at)
        self.reconstruct()
        return deepcopy(review)

    def _require_fresh_target(self, proposal: Mapping[str, Any]) -> object:
        try:
            target = resolve_authority_target(
                self.authority, str(proposal["target_publication_id"])
            )
            descriptor = target_descriptor(target)
            expected = {
                "publication_id": proposal["target_publication_id"],
                "publication_semantic_hash": proposal[
                    "target_publication_semantic_hash"
                ],
                "repository_id": proposal["target_repository_id"],
                "repository_semantic_hash": proposal["target_repository_semantic_hash"],
                "publication_attestation_sha256": proposal[
                    "target_publication_attestation_sha256"
                ],
                "lineage_source_type": proposal["target_lineage_source_type"],
                "lineage_source_attestation_sha256": proposal[
                    "target_lineage_source_attestation_sha256"
                ],
            }
            if (
                canonical_json_bytes(descriptor) != canonical_json_bytes(expected)
                or target_binding_hash(
                    self.authority, str(proposal["target_publication_id"])
                )
                != proposal["target_authority_binding_hash"]
            ):
                raise ValueError("target binding changed")
            package = getattr(target, "package_directory", None)
            attestation = getattr(target, "attestation_path", None)
            expected_tree = getattr(target, "publication_tree_sha256", None)
            if any(
                value is not None for value in (package, attestation, expected_tree)
            ):
                if any(
                    value is None for value in (package, attestation, expected_tree)
                ):
                    raise ValueError("target physical authority is incomplete")
                from .attestation import file_sha256, publication_tree_sha256

                if (
                    publication_tree_sha256(package) != expected_tree
                    or file_sha256(attestation)
                    != proposal["target_publication_attestation_sha256"]
                ):
                    raise ValueError("target physical authority changed")
        except ActivationError as exc:
            if exc.code in {
                ActivationErrorCode.AUTHORITY_MISMATCH,
                ActivationErrorCode.UNVERIFIED_ACTIVATION_TARGET,
                ActivationErrorCode.TARGET_PUBLICATION_TAMPERED,
                ActivationErrorCode.TARGET_PUBLICATION_UNAVAILABLE,
            }:
                raise ActivationError(
                    ActivationErrorCode.STALE_ACTIVATION_TARGET
                ) from exc
            raise
        except Exception as exc:
            raise ActivationError(ActivationErrorCode.STALE_ACTIVATION_TARGET) from exc
        return target

    def append_execution(
        self,
        *,
        event_type: str,
        execution_payload: Mapping[str, Any],
        new_pointer: Mapping[str, Any],
        observed_at: str | None = None,
    ) -> dict[str, Any]:
        """Append an already reverified execution while the store lock is held."""

        if event_type not in {"ActivationApplied", "RollbackApplied"}:
            raise ActivationError(ActivationErrorCode.INVALID_ACTIVATION_REQUEST)
        event = self._append(
            event_type,
            execution_payload,
            observed_at=observed_at,
            current_pointer=new_pointer,
        )
        self.reconstruct()
        return event
