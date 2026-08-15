"""TEST-ONLY deterministic Phase 05 controlled fixture.

The fixture is intentionally not accepted by the production authority loader.
It exists to exercise re-entry and attack cases without fabricating production
attestation or publication identity.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from kg_mnp_demo.modeling.canonical_json import semantic_hash

from .diff import compute_cleaned_input_diff
from .errors import AmendmentError, AmendmentErrorCode

FIXTURE_NAMESPACE = "urn:kg-mnp:test-fixture:phase05:"
FIXTURE_TYPE = "PHASE05_CONTROLLED_AMENDMENT_FIXTURE"
FIXTURE_STATUS = "CONTROLLED_AMENDMENT_FIXTURE"


@dataclass(frozen=True, slots=True)
class ControlledAmendmentFixture:
    base_cleaned_data: dict[str, Any]
    revised_cleaned_data: dict[str, Any]
    approved_amendment_request: dict[str, Any]
    declared_changed_json_pointers: tuple[str, ...]
    controlled_fixture_hash: str

    @property
    def fixture_type(self) -> str:
        return FIXTURE_TYPE

    @property
    def status(self) -> str:
        return FIXTURE_STATUS

    @property
    def test_only(self) -> bool:
        return True

    @property
    def production_authority(self) -> bool:
        return False

    @classmethod
    def create(
        cls,
        *,
        base_publication_id: str | None = None,
        base_publication_semantic_hash: str | None = None,
        repository_semantic_hash: str | None = None,
        target_diagnostic_id: str | None = None,
    ) -> ControlledAmendmentFixture:
        base = {
            "contract_version": "1.0",
            "document_id": "phase05-controlled-missing",
            "dataset_id": "phase05-controlled",
            "data": {
                "subscriber": {"id": "SUBSCRIBER-PHASE05"},
                "subscription": {"subscription_id": "SUBSCRIPTION-PHASE05"},
            },
            "sources": [
                {
                    "source_id": "phase05-source",
                    "source_type": "SYNTHETIC_FIXTURE",
                    "source_locator": "fixture:phase05",
                    "source_version": "1.0",
                }
            ],
            "field_metadata": [
                {
                    "path": "/subscriber/id",
                    "source_refs": ["phase05-source"],
                    "presence": "PRESENT",
                    "confidence": {
                        "level": "HIGH",
                        "score": 0.9,
                        "basis": "SOURCE_DECLARED",
                    },
                },
                {
                    "path": "/subscription/subscription_id",
                    "source_refs": ["phase05-source"],
                    "presence": "PRESENT",
                    "confidence": {
                        "level": "HIGH",
                        "score": 0.9,
                        "basis": "SOURCE_DECLARED",
                    },
                },
            ],
            "declared_missing_items": [],
            "declared_conflicts": [],
            "input_context": {"test_only": True},
        }
        revised = deepcopy(base)
        revised["data"]["subscription"]["status"] = "active"
        revised["field_metadata"].append(
            {
                "path": "/subscription/status",
                "source_refs": ["phase05-source"],
                "presence": "PRESENT",
                "confidence": {
                    "level": "HIGH",
                    "score": 0.9,
                    "basis": "SOURCE_DECLARED",
                },
            }
        )
        pointers = tuple(compute_cleaned_input_diff(base, revised))
        payload = {
            "rdf_term": {
                "term_type": "LITERAL",
                "iri": None,
                "lexical_form": "ACTIVE",
                "datatype_iri": "http://www.w3.org/2001/XMLSchema#string",
                "language": None,
            },
            "evidence_refs": ["phase05-source"],
            "source_refs": ["phase05-source"],
            "candidate_refs": [],
            "constraint_refs": [],
            "review_reopen_reason": None,
        }
        semantic = {
            "base_publication_id": base_publication_id
            or f"{FIXTURE_NAMESPACE}publication:base",
            "base_publication_semantic_hash": base_publication_semantic_hash
            or semantic_hash(base),
            "target_diagnostic_id": target_diagnostic_id
            or f"{FIXTURE_NAMESPACE}diagnostic:{semantic_hash({'target': 'missing-status'})}",
            "amendment_type": "PROPOSE_VALUE_CANDIDATE",
            "structured_proposed_payload": payload,
        }
        request_hash = semantic_hash(semantic)
        request = {
            "contract_version": "1.0",
            "amendment_request_id": f"{FIXTURE_NAMESPACE}approved-amendment-request:{request_hash}",
            "proposal_id": f"{FIXTURE_NAMESPACE}resolution-proposal:{semantic_hash({'proposal': request_hash})}",
            "review_decision_id": f"{FIXTURE_NAMESPACE}resolution-review-decision:{semantic_hash({'review': request_hash})}",
            "target_diagnostic_id": semantic["target_diagnostic_id"],
            "authority_type": "CONTROLLED_TEST_HARNESS",
            "publication_id": semantic["base_publication_id"],
            "publication_semantic_hash": semantic["base_publication_semantic_hash"],
            "repository_semantic_hash": repository_semantic_hash
            or semantic_hash({"repository": "base"}),
            "upstream_phase03_attestation_sha256": semantic_hash(
                {"phase03": "fixture"}
            ),
            "upstream_phase03_diagnostic_package_hash": semantic_hash(
                {"diagnostics": "fixture"}
            ),
            "amendment_type": semantic["amendment_type"],
            "structured_proposed_payload": payload,
            "provenance_chain": [
                semantic["target_diagnostic_id"],
                f"{FIXTURE_NAMESPACE}resolution-proposal:{request_hash}",
                f"{FIXTURE_NAMESPACE}resolution-review-decision:{request_hash}",
            ],
            "governance_status": "APPROVED_FOR_FUTURE_AMENDMENT",
            "status": "APPROVED_FOR_FUTURE_MODELING_AMENDMENT",
        }
        fixture_hash = semantic_hash(
            {
                "namespace": FIXTURE_NAMESPACE,
                "base": base,
                "revised": revised,
                "request": request,
            }
        )
        return cls(base, revised, request, pointers, fixture_hash)

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_type": FIXTURE_TYPE,
            "status": FIXTURE_STATUS,
            "test_only": True,
            "production_authority": False,
            "controlled_fixture_hash": self.controlled_fixture_hash,
            "base_cleaned_data": deepcopy(self.base_cleaned_data),
            "revised_cleaned_data": deepcopy(self.revised_cleaned_data),
            "approved_amendment_request": deepcopy(self.approved_amendment_request),
            "declared_changed_json_pointers": list(self.declared_changed_json_pointers),
        }

    def require_test_only(self) -> None:
        return None

    def as_production_authority(self) -> None:
        raise AmendmentError(
            AmendmentErrorCode.TEST_FIXTURE_NOT_ALLOWED_AS_PRODUCTION_AUTHORITY
        )

    def evidence(self) -> dict[str, Any]:
        """Return deterministic controlled hash evidence for offline/CI closure."""

        old_abox = semantic_hash(self.base_cleaned_data)
        new_abox = semantic_hash(self.revised_cleaned_data)
        old_publication = semantic_hash(
            {"fixture": self.controlled_fixture_hash, "version": "P0"}
        )
        new_publication = semantic_hash(
            {"fixture": self.controlled_fixture_hash, "version": "P1"}
        )
        tbox = semantic_hash({"fixture": "phase05", "plane": "TBOX"})
        shacl = semantic_hash({"fixture": "phase05", "plane": "SHACL"})
        webvowl = semantic_hash({"fixture": "phase05", "plane": "WEBVOWL"})
        repository = semantic_hash({"publication": old_publication, "repository": "P0"})
        new_repository = semantic_hash(
            {"publication": new_publication, "repository": "P1"}
        )
        return {
            "old_tbox_hash": tbox,
            "new_tbox_hash": tbox,
            "old_shacl_hash": shacl,
            "new_shacl_hash": shacl,
            "old_abox_hash": old_abox,
            "new_abox_hash": new_abox,
            "old_publication_hash": old_publication,
            "new_publication_hash": new_publication,
            "old_webvowl_hash": webvowl,
            "new_webvowl_hash": webvowl,
            "old_repository_before_hash": repository,
            "old_repository_after_hash": repository,
            "new_repository_expected_hash": new_repository,
            "new_repository_actual_hash": new_repository,
            "base_cleaned_data_hash": old_abox,
            "revised_cleaned_data_hash": new_abox,
        }
