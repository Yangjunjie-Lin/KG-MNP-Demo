"""Security and boundary validators for Phase 05."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .authority_binding import ProductionPhase05Authority, require_production_authority
from .errors import AmendmentError, AmendmentErrorCode
from .intake import validate_intake
from .republication import assert_abox_only_invariants


def validate_production_authority(
    authority: ProductionPhase05Authority,
    *,
    expected_commit_sha: str | None = None,
) -> ProductionPhase05Authority:
    value = require_production_authority(authority)
    if expected_commit_sha is not None and value.commit_sha != expected_commit_sha:
        raise AmendmentError(AmendmentErrorCode.AUTHORITY_MISMATCH)
    return value


def validate_phase05_request(
    *,
    authority: ProductionPhase05Authority,
    amendment_request: Mapping[str, Any],
    intake_manifest: Mapping[str, Any],
    base_publication_id: str,
    base_publication_semantic_hash: str,
) -> dict[str, Any]:
    request = authority.require_request(
        str(intake_manifest.get("approved_amendment_request_id"))
    )
    if dict(request) != dict(amendment_request):
        raise AmendmentError(AmendmentErrorCode.AUTHORITY_MISMATCH)
    if request.get("authority_type") != "PRODUCTION_EXACT_PHASE03":
        raise AmendmentError(
            AmendmentErrorCode.TEST_FIXTURE_NOT_ALLOWED_AS_PRODUCTION_AUTHORITY
        )
    if (
        request.get("publication_id") != base_publication_id
        or request.get("publication_semantic_hash") != base_publication_semantic_hash
    ):
        raise AmendmentError(AmendmentErrorCode.STALE_AMENDMENT_BASE)
    validate_intake(
        intake_manifest,
        approved_request=request,
        base_publication_id=base_publication_id,
        base_publication_semantic_hash=base_publication_semantic_hash,
    )
    return request


def validate_no_direct_mutation(operation: str) -> None:
    marker = str(operation).casefold()
    if any(
        token in marker
        for token in ("insert", "delete", "update", "patch", "graph store")
    ):
        raise AmendmentError(AmendmentErrorCode.DIRECT_RDF_MUTATION_BLOCKED)


def validate_new_repository_identity(
    *, old_repository_id: str, new_repository_id: str, new_publication_hash: str
) -> None:
    if old_repository_id == new_repository_id:
        raise AmendmentError(AmendmentErrorCode.GRAPHDB_INPLACE_MUTATION_BLOCKED)
    if not new_repository_id.endswith(new_publication_hash):
        raise AmendmentError(AmendmentErrorCode.AUTHORITY_MISMATCH)


def validate_republication_invariants(**kwargs: Any) -> None:
    assert_abox_only_invariants(**kwargs)
