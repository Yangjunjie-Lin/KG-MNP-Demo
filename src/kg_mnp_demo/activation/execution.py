"""Human-approved activation execution with read-only target reverification."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any, Protocol

from kg_mnp_demo.application.readonly_client import ReadOnlyGraphDBClient
from kg_mnp_demo.graphdb.rdf_semantics import graphdb_semantic_hash_nquads
from kg_mnp_demo.modeling.canonical_json import semantic_hash

from .attestation import verify_controlled_publication, verify_production_publication
from .contracts import validate_activation_contract
from .errors import ActivationError, ActivationErrorCode
from .persistence import ActivationStateStore
from .pointer import build_current_publication_pointer
from .registry import ActivationRegistry, target_descriptor


class TargetReverifier(Protocol):
    """Read-only boundary used immediately before a pointer switch."""

    def verify(self, target: object) -> Mapping[str, str]: ...


def _target_path(target: object, *names: str) -> Path:
    for name in names:
        value = getattr(target, name, None)
        if value is not None:
            return Path(value)
    raise ActivationError(
        ActivationErrorCode.TARGET_PUBLICATION_UNAVAILABLE,
        "verified authority did not retain a physical target publication path",
    )


class ReadOnlyGraphDBTargetVerifier:
    """Concrete package plus live-GraphDB verifier with no write capability."""

    def __init__(
        self,
        client: ReadOnlyGraphDBClient | None = None,
        *,
        publication_scenario: str = "full-confirmation",
    ):
        self.client = client or ReadOnlyGraphDBClient()
        self.publication_scenario = publication_scenario

    def verify(self, target: object) -> dict[str, str]:
        descriptor = target_descriptor(target)
        try:
            package = _target_path(
                target,
                "package_directory",
                "publication_package_directory",
                "_package_directory",
            )
            attestation = _target_path(
                target,
                "attestation_path",
                "publication_attestation_path",
                "_attestation_path",
            )
            if not package.is_dir() or not attestation.is_file():
                raise FileNotFoundError("target publication is unavailable")
            expected_tree = str(
                target.publication_tree_sha256  # type: ignore[attr-defined]
            )
            controlled_fixture_hash = getattr(target, "controlled_fixture_hash", None)
            if getattr(target, "test_only", False) is True:
                if not isinstance(controlled_fixture_hash, str):
                    raise ValueError("controlled fixture lineage is unavailable")
                publication_evidence = verify_controlled_publication(
                    package_directory=package,
                    attestation_path=attestation,
                    expected_publication_tree_sha256=expected_tree,
                    expected_publication_id=descriptor["publication_id"],
                    expected_publication_semantic_hash=descriptor[
                        "publication_semantic_hash"
                    ],
                    expected_repository_id=descriptor["repository_id"],
                    expected_repository_semantic_hash=descriptor[
                        "repository_semantic_hash"
                    ],
                    expected_attestation_sha256=descriptor[
                        "publication_attestation_sha256"
                    ],
                    expected_controlled_fixture_hash=controlled_fixture_hash,
                )
            else:
                publication_evidence = verify_production_publication(
                    package_directory=package,
                    publication_attestation_path=attestation,
                    publication_scenario=str(
                        getattr(
                            target, "publication_scenario", self.publication_scenario
                        )
                    ),
                    expected_publication_tree_sha256=expected_tree,
                    expected_publication_id=descriptor["publication_id"],
                    expected_publication_semantic_hash=descriptor[
                        "publication_semantic_hash"
                    ],
                    expected_repository_id=descriptor["repository_id"],
                    expected_repository_semantic_hash=descriptor[
                        "repository_semantic_hash"
                    ],
                    expected_attestation_sha256=descriptor[
                        "publication_attestation_sha256"
                    ],
                )
            tree_hash = publication_evidence["publication_tree_sha256"]
            attestation_hash = publication_evidence["publication_attestation_sha256"]
        except ActivationError:
            raise
        except (FileNotFoundError, NotADirectoryError) as exc:
            raise ActivationError(
                ActivationErrorCode.TARGET_PUBLICATION_UNAVAILABLE
            ) from exc
        except OSError as exc:
            if not package.exists() or not attestation.exists():
                raise ActivationError(
                    ActivationErrorCode.TARGET_PUBLICATION_UNAVAILABLE
                ) from exc
            raise ActivationError(
                ActivationErrorCode.TARGET_PUBLICATION_TAMPERED
            ) from exc
        except Exception as exc:
            raise ActivationError(
                ActivationErrorCode.TARGET_PUBLICATION_TAMPERED
            ) from exc

        if (
            attestation_hash != descriptor["publication_attestation_sha256"]
            or tree_hash != expected_tree
        ):
            raise ActivationError(ActivationErrorCode.TARGET_PUBLICATION_TAMPERED)

        try:
            repository_info = self.client.repository_info(descriptor["repository_id"])
            if isinstance(repository_info, Mapping):
                observed_id = repository_info.get("id") or repository_info.get(
                    "repositoryID"
                )
                if (
                    observed_id is not None
                    and observed_id != descriptor["repository_id"]
                ):
                    raise ValueError("live repository identity mismatch")
            data = self.client.export_explicit_nquads(descriptor["repository_id"])
            live_hash = graphdb_semantic_hash_nquads(data)
        except ActivationError:
            raise
        except Exception as exc:
            raise ActivationError(
                ActivationErrorCode.TARGET_REPOSITORY_UNAVAILABLE
            ) from exc
        if live_hash != descriptor["repository_semantic_hash"]:
            raise ActivationError(ActivationErrorCode.TARGET_REPOSITORY_HASH_MISMATCH)
        return {
            "publication_tree_sha256": tree_hash,
            "publication_attestation_sha256": attestation_hash,
            "expected_repository_semantic_hash": descriptor["repository_semantic_hash"],
            "live_repository_semantic_hash": live_hash,
        }


def execution_identity_content(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(value) for key, value in payload.items() if key != "execution_id"
    }


def build_execution_payload(
    *,
    proposal: Mapping[str, Any],
    decision: Mapping[str, Any],
    old_pointer: Mapping[str, Any],
    new_pointer: Mapping[str, Any],
    verification_evidence_hashes: Mapping[str, str],
    test_only: bool,
) -> dict[str, Any]:
    status = (
        "ACTIVATION_APPLIED"
        if proposal["activation_kind"] == "ACTIVATE_NEW_VERIFIED_PUBLICATION"
        else "ROLLBACK_APPLIED"
    )
    payload: dict[str, Any] = {
        "proposal_id": proposal["activation_proposal_id"],
        "review_decision_id": decision["activation_review_decision_id"],
        "old_pointer": deepcopy(dict(old_pointer)),
        "new_pointer": deepcopy(dict(new_pointer)),
        "verification_evidence_hashes": dict(verification_evidence_hashes),
        "status": status,
    }
    payload["execution_id"] = (
        "urn:kg-mnp:test-fixture:phase06:activation-execution:"
        if test_only
        else "urn:kg-mnp:activation-execution:"
    ) + semantic_hash(payload)
    return payload


def build_execution_receipt(
    *,
    execution_payload: Mapping[str, Any],
    proposal: Mapping[str, Any],
    event_id: str,
) -> dict[str, Any]:
    old_pointer = execution_payload["old_pointer"]
    new_pointer = execution_payload["new_pointer"]
    value = {
        "contract_version": "1.0",
        "execution_id": execution_payload["execution_id"],
        "proposal_id": execution_payload["proposal_id"],
        "review_decision_id": execution_payload["review_decision_id"],
        "old_pointer_hash": old_pointer["pointer_hash"],
        "new_pointer_hash": new_pointer["pointer_hash"],
        "old_generation": old_pointer["generation"],
        "new_generation": new_pointer["generation"],
        "target_publication_id": proposal["target_publication_id"],
        "target_publication_semantic_hash": proposal[
            "target_publication_semantic_hash"
        ],
        "target_repository_id": proposal["target_repository_id"],
        "target_repository_semantic_hash": proposal["target_repository_semantic_hash"],
        "target_publication_attestation_sha256": proposal[
            "target_publication_attestation_sha256"
        ],
        "verification_evidence_hashes": deepcopy(
            dict(execution_payload["verification_evidence_hashes"])
        ),
        "event_id": event_id,
        "semantic_authority": False,
        "deployment_governance_only": True,
        "test_only": proposal["test_only"],
        "production_authority": proposal["production_authority"],
        "status": execution_payload["status"],
    }
    validate_activation_contract("activation-execution-receipt", value)
    return value


class ActivationController:
    """Explicit CLI-oriented control plane; it exposes no graph write operation."""

    def __init__(self, store: ActivationStateStore, verifier: TargetReverifier):
        self.store = store
        self.verifier = verifier

    def initialize(self, *, observed_at: str | None = None):
        return self.store.initialize(observed_at=observed_at)

    def status(
        self,
        *,
        expected_registry_hash: str | None = None,
        expected_head_event_hash: str | None = None,
    ) -> dict[str, Any]:
        _registry, _pointer, state = self.store.load(
            expected_registry_hash=expected_registry_hash,
            expected_head_event_hash=expected_head_event_hash,
        )
        return state

    def create_proposal(self, **arguments: Any) -> dict[str, Any]:
        return self.store.mutate(lambda registry: registry.create_proposal(**arguments))

    def propose_rollback(self, **arguments: Any) -> dict[str, Any]:
        return self.create_proposal(
            activation_kind="ROLLBACK_TO_PRIOR_VERIFIED_PUBLICATION", **arguments
        )

    def submit_proposal(self, proposal_id: str, **arguments: Any) -> dict[str, Any]:
        return self.store.mutate(
            lambda registry: registry.submit_proposal(proposal_id, **arguments)
        )

    def record_review(self, proposal_id: str, **arguments: Any) -> dict[str, Any]:
        return self.store.mutate(
            lambda registry: registry.record_review(proposal_id, **arguments)
        )

    def execute(
        self,
        proposal_id: str,
        review_decision_id: str,
        *,
        expected_generation: int,
        expected_pointer_hash: str,
        observed_at: str | None = None,
    ) -> dict[str, Any]:
        """Reverify, then perform one CAS-protected pointer generation switch."""

        def operation(registry: ActivationRegistry) -> dict[str, Any]:
            pointer = registry.current_pointer
            # CAS precedes replay classification so the loser of a same-base race
            # is always the required ACTIVATION_CONCURRENCY_CONFLICT.
            if (
                pointer["generation"] != expected_generation
                or pointer["pointer_hash"] != expected_pointer_hash
            ):
                raise ActivationError(
                    ActivationErrorCode.ACTIVATION_CONCURRENCY_CONFLICT
                )
            state = registry.reconstruct()
            proposal = next(
                (
                    item
                    for item in state["proposals"]
                    if item["activation_proposal_id"] == proposal_id
                ),
                None,
            )
            decision = next(
                (
                    item
                    for item in state["review_decisions"]
                    if item["activation_review_decision_id"] == review_decision_id
                ),
                None,
            )
            if any(item["proposal_id"] == proposal_id for item in state["executions"]):
                raise ActivationError(ActivationErrorCode.REPLAY_DETECTED)
            if (
                proposal is None
                or decision is None
                or proposal["status"] != "APPROVED_FOR_ACTIVATION"
                or decision["activation_proposal_id"] != proposal_id
                or decision["decision"] != "APPROVE_FOR_ACTIVATION"
                or decision["explicit_human_action"] is not True
            ):
                raise ActivationError(
                    ActivationErrorCode.HUMAN_ACTIVATION_APPROVAL_REQUIRED
                )
            if (
                proposal["base_generation"] != pointer["generation"]
                or proposal["base_pointer_hash"] != pointer["pointer_hash"]
            ):
                raise ActivationError(
                    ActivationErrorCode.ACTIVATION_CONCURRENCY_CONFLICT
                )
            target = registry._require_fresh_target(proposal)
            evidence = dict(self.verifier.verify(target))
            required_evidence = {
                "publication_tree_sha256",
                "publication_attestation_sha256",
                "expected_repository_semantic_hash",
                "live_repository_semantic_hash",
            }
            if set(evidence) != required_evidence:
                raise ActivationError(ActivationErrorCode.INVALID_ACTIVATION_REQUEST)
            descriptor = target_descriptor(target)
            if (
                evidence["publication_attestation_sha256"]
                != descriptor["publication_attestation_sha256"]
                or evidence["expected_repository_semantic_hash"]
                != descriptor["repository_semantic_hash"]
                or evidence["live_repository_semantic_hash"]
                != descriptor["repository_semantic_hash"]
            ):
                raise ActivationError(
                    ActivationErrorCode.TARGET_REPOSITORY_HASH_MISMATCH
                )
            # The live repository export may be slow.  Re-snapshot the physical
            # publication after that read so a target changed during
            # reverification can never be selected by the pointer commit.
            registry._require_fresh_target(proposal)
            new_pointer = build_current_publication_pointer(
                registry_id=registry.value["registry_id"],
                generation=pointer["generation"] + 1,
                target=descriptor,
                previous_pointer_hash=pointer["pointer_hash"],
                test_only=registry.value["test_only"],
            )
            payload = build_execution_payload(
                proposal=proposal,
                decision=decision,
                old_pointer=pointer,
                new_pointer=new_pointer,
                verification_evidence_hashes=evidence,
                test_only=registry.value["test_only"],
            )
            event_type = (
                "ActivationApplied"
                if proposal["activation_kind"] == "ACTIVATE_NEW_VERIFIED_PUBLICATION"
                else "RollbackApplied"
            )
            event = registry.append_execution(
                event_type=event_type,
                execution_payload=payload,
                new_pointer=new_pointer,
                observed_at=observed_at,
            )
            return build_execution_receipt(
                execution_payload=payload,
                proposal=proposal,
                event_id=event["event_id"],
            )

        return self.store.mutate(operation)
