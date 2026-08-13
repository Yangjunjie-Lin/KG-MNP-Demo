"""Governance operations and atomic local JSON persistence."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes, semantic_hash

from .amendment_request import build_approved_amendment_request
from .authority_binding import (
    GovernanceAuthority,
    _require_verified_production_authority,
)
from .contracts import strict_json_file, validate_governance_contract
from .errors import GovernanceError, GovernanceErrorCode
from .event_log import build_event
from .identity import governance_urn
from .proposal import create_resolution_proposal
from .review import build_review_decision
from .state_machine import require_transition
from .validator import (
    validate_governance_workspace_against_authorities,
    workspace_semantic_content,
)


def _finalize(value: dict[str, Any]) -> dict[str, Any]:
    value["workspace_revision"] = len(value["events"])
    value["head_event_hash"] = (
        value["events"][-1]["event_id"] if value["events"] else "GENESIS"
    )
    value["workspace_hash"] = semantic_hash(workspace_semantic_content(value))
    validate_governance_contract("governance-workspace", value)
    return value


def _workspace_value(authority: GovernanceAuthority) -> dict[str, Any]:
    binding = authority.binding
    value = {
        "contract_version": "1.0",
        "workspace_id": governance_urn(
            "governance-workspace", binding, authority.authority_type
        ),
        "authority_binding": binding,
        "events": [],
        "workspace_revision": 0,
        "head_event_hash": "GENESIS",
        "workspace_hash": "0" * 64,
        "status": "GOVERNANCE_WORKSPACE_ACTIVE",
    }
    return _finalize(value)


def new_workspace(authority: GovernanceAuthority) -> dict[str, Any]:
    authority = _require_verified_production_authority(authority)
    return _workspace_value(authority)


@dataclass
class GovernanceWorkspace:
    value: dict[str, Any]
    current_authority: Callable[[], GovernanceAuthority]

    @classmethod
    def initialize(
        cls,
        authority: GovernanceAuthority,
        current_authority: Callable[[], GovernanceAuthority] | None = None,
    ) -> GovernanceWorkspace:
        authority = _require_verified_production_authority(authority)
        supplied_current = current_authority or (lambda: authority)
        return cls(
            _workspace_value(authority),
            lambda: _require_verified_production_authority(supplied_current()),
        )

    def reconstruct(self) -> dict[str, Any]:
        authority = self._require_current_authority_mode()
        return validate_governance_workspace_against_authorities(
            self.value, authority
        )

    def _require_current_authority_mode(self) -> GovernanceAuthority:
        authority = _require_verified_production_authority(self.current_authority())
        mode = self.value.get("authority_binding", {}).get("authority_type")
        if mode != "PRODUCTION_EXACT_PHASE03":
            raise GovernanceError(GovernanceErrorCode.AUTHORITY_MISMATCH)
        return authority

    def _current(
        self, expected_workspace_revision: int, expected_head_hash: str | None
    ) -> GovernanceAuthority:
        if expected_workspace_revision != self.value["workspace_revision"]:
            raise GovernanceError(GovernanceErrorCode.CONCURRENCY_CONFLICT)
        if (
            expected_head_hash is not None
            and expected_head_hash != self.value["head_event_hash"]
        ):
            raise GovernanceError(GovernanceErrorCode.CONCURRENCY_CONFLICT)
        authority = self._require_current_authority_mode()
        authority.assert_same_current_authority(self.value["authority_binding"])
        self.reconstruct()
        return authority

    def _append(
        self,
        event_type: str,
        payload: Mapping[str, Any],
        observed_at: str | None = None,
    ) -> dict[str, Any]:
        event = build_event(
            sequence=len(self.value["events"]) + 1,
            previous_event_hash=self.value["head_event_hash"],
            event_type=event_type,
            payload=payload,
            observed_at=observed_at,
        )
        self.value["events"].append(event)
        _finalize(self.value)
        return event

    def create_proposal(
        self,
        *,
        expected_workspace_revision: int,
        expected_head_hash: str | None = None,
        observed_at: str | None = None,
        **arguments: Any,
    ) -> dict[str, Any]:
        authority = self._current(expected_workspace_revision, expected_head_hash)
        proposal = create_resolution_proposal(
            authority=authority,
            workspace_id=self.value["workspace_id"],
            sequence=len(self.value["events"]) + 1,
            previous_event_hash=self.value["head_event_hash"],
            **arguments,
        )
        self._append("ProposalCreated", proposal, observed_at)
        self.reconstruct()
        return deepcopy(proposal)

    def submit_proposal(
        self,
        proposal_id: str,
        *,
        expected_workspace_revision: int,
        expected_head_hash: str | None = None,
        observed_at: str | None = None,
    ) -> dict[str, Any]:
        self._current(expected_workspace_revision, expected_head_hash)
        state = self.reconstruct()
        proposal = next(
            (p for p in state["proposals"] if p["proposal_id"] == proposal_id), None
        )
        if proposal is None:
            raise GovernanceError(
                GovernanceErrorCode.INVALID_REQUEST, "unknown proposal"
            )
        if proposal["status"] == "SUBMITTED":
            raise GovernanceError(GovernanceErrorCode.REPLAY_DETECTED)
        require_transition(proposal["status"], "SUBMITTED")
        self._append(
            "ProposalSubmitted",
            {
                "proposal_id": proposal_id,
                "proposal_revision": proposal["proposal_revision"],
                "resulting_status": "SUBMITTED",
            },
            observed_at,
        )
        return next(
            p
            for p in self.reconstruct()["proposals"]
            if p["proposal_id"] == proposal_id
        )

    def review_proposal(
        self,
        proposal_id: str,
        *,
        decision: str,
        review_note: str,
        reviewed_by_label: str,
        explicit_human_action: bool,
        expected_workspace_revision: int,
        expected_head_hash: str | None = None,
        observed_at: str | None = None,
    ) -> dict[str, Any]:
        self._current(expected_workspace_revision, expected_head_hash)
        state = self.reconstruct()
        proposal = next(
            (p for p in state["proposals"] if p["proposal_id"] == proposal_id), None
        )
        if proposal is None:
            raise GovernanceError(
                GovernanceErrorCode.INVALID_REQUEST, "unknown proposal"
            )
        if any(
            item["proposal_id"] == proposal_id for item in state["review_decisions"]
        ):
            raise GovernanceError(GovernanceErrorCode.REPLAY_DETECTED)
        review, target, event_type = build_review_decision(
            workspace_id=self.value["workspace_id"],
            sequence=len(self.value["events"]) + 1,
            previous_event_hash=self.value["head_event_hash"],
            proposal=proposal,
            decision=decision,
            review_note=review_note,
            reviewed_by_label=reviewed_by_label,
            explicit_human_action=explicit_human_action,
        )
        require_transition(proposal["status"], target)
        review_event = self._append(event_type, review, observed_at)
        result: dict[str, Any] = {"review_decision": review, "amendment_request": None}
        if decision == "APPROVE_FOR_AMENDMENT":
            amendment = build_approved_amendment_request(
                proposal={**proposal, "status": target},
                decision=review,
                review_event_id=review_event["event_id"],
            )
            self._append("AmendmentRequestProduced", amendment, observed_at)
            result["amendment_request"] = amendment
        self.reconstruct()
        return result


class GovernanceWorkspaceStore:
    """Startup-frozen workspace file with atomic replacement and in-process lock."""

    def __init__(
        self,
        path: Path,
        current_authority: Callable[[], GovernanceAuthority],
    ):
        absolute = Path(path).absolute()
        if absolute.name != "governance-workspace.json":
            raise GovernanceError(GovernanceErrorCode.PATH_REJECTED)
        for candidate in (absolute.parent, *absolute.parent.parents):
            is_junction = getattr(candidate, "is_junction", lambda: False)
            if candidate.is_symlink() or is_junction():
                raise GovernanceError(GovernanceErrorCode.PATH_REJECTED)
        self.path = absolute
        self._parent = absolute.parent.resolve(strict=False)
        self.current_authority = current_authority
        import threading

        self._lock = threading.RLock()

    def initialize(self, authority: GovernanceAuthority) -> GovernanceWorkspace:
        with self._lock:
            authority = self._validate_authority(authority)
            if self.path.exists():
                raise GovernanceError(
                    GovernanceErrorCode.REPLAY_DETECTED, "workspace already exists"
                )
            workspace = GovernanceWorkspace.initialize(
                authority, lambda: self._validate_authority(self.current_authority())
            )
            self._persist(workspace.value)
            return workspace

    def load(self) -> GovernanceWorkspace:
        with self._lock:
            authority = self._validate_authority(self.current_authority())
            self._assert_safe_path(for_write=False)
            value = strict_json_file(self.path)
            workspace = GovernanceWorkspace(value, lambda: authority)
            workspace.reconstruct()
            return workspace

    def _validate_authority(
        self, authority: GovernanceAuthority
    ) -> GovernanceAuthority:
        return _require_verified_production_authority(authority)

    def mutate(self, operation: Callable[[GovernanceWorkspace], Any]) -> Any:
        with self._lock:
            workspace = self.load()
            result = operation(workspace)
            self._persist(workspace.value)
            return result

    def _persist(self, value: Mapping[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._assert_safe_path(for_write=True)
        parent = self._parent
        data = canonical_json_bytes(value) + b"\n"
        descriptor, temporary = tempfile.mkstemp(
            prefix=".governance-", suffix=".tmp", dir=parent
        )
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            Path(temporary).replace(self.path)
            try:
                directory_fd = os.open(parent, os.O_RDONLY)
            except OSError:
                directory_fd = None
            if directory_fd is not None:
                try:
                    os.fsync(directory_fd)
                except OSError:
                    pass
                finally:
                    os.close(directory_fd)
        finally:
            try:
                Path(temporary).unlink(missing_ok=True)
            except OSError:
                pass

    def _assert_safe_path(self, *, for_write: bool) -> None:
        try:
            for candidate in (self.path.parent, *self.path.parent.parents):
                is_junction = getattr(candidate, "is_junction", lambda: False)
                if candidate.is_symlink() or is_junction():
                    raise GovernanceError(GovernanceErrorCode.PATH_REJECTED)
            if self.path.parent.resolve(strict=True) != self._parent:
                raise GovernanceError(GovernanceErrorCode.PATH_REJECTED)
            if self.path.is_symlink():
                raise GovernanceError(GovernanceErrorCode.PATH_REJECTED)
            if not for_write and self.path.resolve(strict=True) != self.path:
                raise GovernanceError(GovernanceErrorCode.PATH_REJECTED)
        except GovernanceError:
            raise
        except OSError as exc:
            if not for_write:
                raise GovernanceError(GovernanceErrorCode.PATH_REJECTED) from exc
