"""Formal structural prevalidation; never an OWL/SHACL/CQ final validator."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from kg_mnp.contracts.catalog import ContractCatalog
from kg_mnp.contracts.registry import validate_contract

from .artifacts import finalize_document, verify_document
from .conflicts import issue
from .errors import ModelingControlError, ModelingProposalError
from .input_bundle import verify_input_bundle
from .limits import ModelingLimits
from .proposal import verify_proposal
from .scope_approval import verify_scope_approval
from .security import validate_iri

CHECKS = (
    "CONTRACT_VALIDITY", "PROJECT_LOCK_VALIDITY", "CATALOG_BINDING", "DOMAIN_PACK_LOCK_BINDING",
    "SCOPE_APPROVAL", "KG_IR_VALIDITY", "EVIDENCE_CLOSURE", "CANDIDATE_ID_RECALCULATION",
    "SEMANTIC_SIGNATURE", "IRI_SCHEME", "NAMESPACE_AUTHORIZATION", "RESERVED_NAMESPACE_PROTECTION",
    "BASELINE_IRI_COLLISION", "LABEL_COLLISION", "CANDIDATE_DEPENDENCY_CLOSURE",
    "CANDIDATE_DEPENDENCY_CYCLE", "TBOX_ABOX_SCOPE_SEPARATION", "CLASS_PROPERTY_TYPE_CORRECTNESS",
    "DOMAIN_RANGE_REFERENCE_VALIDITY", "DATATYPE_LEXICAL_VALIDITY", "OBJECT_REFERENCE_VALIDITY",
    "MAPPING_SOURCE_TARGET_VALIDITY", "SHACL_CANDIDATE_STRUCTURE", "COMPETENCY_QUESTION_STRUCTURAL_COVERAGE",
    "PROVIDER_SNAPSHOT_CLOSURE", "MODEL_INVOCATION_CLOSURE", "CONFLICT_CLASSIFICATION",
    "UNSUPPORTED_CANDIDATE_BLOCKING", "RESOURCE_LIMITS", "ARTIFACT_MANIFEST_CLOSURE",
)

ISSUE_CHECKS = {
    "PROJECT_LOCK_STALE": "PROJECT_LOCK_VALIDITY",
    "CATALOG_STALE": "CATALOG_BINDING",
    "DOMAIN_PACK_LOCK_STALE": "DOMAIN_PACK_LOCK_BINDING",
    "SCOPE_APPROVAL_STALE": "SCOPE_APPROVAL",
    "KG_IR_CLOSURE": "KG_IR_VALIDITY",
    "EVIDENCE_CLOSURE": "EVIDENCE_CLOSURE",
    "CONTRACT_OR_ID_INVALID": "CANDIDATE_ID_RECALCULATION",
    "UNAUTHORIZED_NAMESPACE": "NAMESPACE_AUTHORIZATION",
    "IRI_COLLISION": "BASELINE_IRI_COLLISION",
    "DUPLICATE_LABEL": "LABEL_COLLISION",
    "CANDIDATE_DEPENDENCY_MISSING": "CANDIDATE_DEPENDENCY_CLOSURE",
    "SUBCLASS_CYCLE": "CANDIDATE_DEPENDENCY_CYCLE",
    "TBOX_ABOX_SCOPE_SEPARATION": "TBOX_ABOX_SCOPE_SEPARATION",
    "ELEMENT_TYPE_CONFLICT": "CLASS_PROPERTY_TYPE_CORRECTNESS",
    "DOMAIN_CONFLICT": "DOMAIN_RANGE_REFERENCE_VALIDITY",
    "RANGE_CONFLICT": "DOMAIN_RANGE_REFERENCE_VALIDITY",
    "DATATYPE_CONFLICT": "DATATYPE_LEXICAL_VALIDITY",
    "DATATYPE_LEXICAL_INVALID": "DATATYPE_LEXICAL_VALIDITY",
    "OBJECT_REFERENCE_MISSING": "OBJECT_REFERENCE_VALIDITY",
    "MAPPING_TARGET_CONFLICT": "MAPPING_SOURCE_TARGET_VALIDITY",
    "MAPPING_TARGET_MISSING": "MAPPING_SOURCE_TARGET_VALIDITY",
    "SHACL_STRUCTURE_INVALID": "SHACL_CANDIDATE_STRUCTURE",
    "CQ_COVERAGE_GAP": "COMPETENCY_QUESTION_STRUCTURAL_COVERAGE",
    "PROVIDER_SNAPSHOT_CLOSURE": "PROVIDER_SNAPSHOT_CLOSURE",
    "MODEL_INVOCATION_CLOSURE": "MODEL_INVOCATION_CLOSURE",
    "CONFLICT_CLASSIFICATION": "CONFLICT_CLASSIFICATION",
    "UNSUPPORTED_CANDIDATE": "UNSUPPORTED_CANDIDATE_BLOCKING",
    "OUT_OF_SCOPE_CANDIDATE": "UNSUPPORTED_CANDIDATE_BLOCKING",
    "RESOURCE_LIMIT_EXCEEDED": "RESOURCE_LIMITS",
}


def _literal_is_valid(literal: dict[str, Any] | None) -> bool:
    if literal is None:
        return False
    lexical = literal["lexical_value"]
    datatype = literal["datatype_iri"]
    language = literal["language"]
    if datatype is not None and language is not None:
        return False
    try:
        if datatype == "http://www.w3.org/2001/XMLSchema#integer":
            int(lexical)
        elif datatype in {
            "http://www.w3.org/2001/XMLSchema#decimal",
            "http://www.w3.org/2001/XMLSchema#double",
            "http://www.w3.org/2001/XMLSchema#float",
        }:
            value = Decimal(lexical)
            if not value.is_finite():
                return False
        elif datatype == "http://www.w3.org/2001/XMLSchema#boolean":
            return lexical in {"true", "false", "1", "0"}
    except (ValueError, InvalidOperation):
        return False
    return True


def prevalidate(
    proposal: dict[str, Any],
    *,
    current_project_lock_id: str,
    current_catalog_digest: str | None = None,
    evidence_ids: set[str],
    kg_ir_item_ids: set[str],
    baseline_element_ids: set[str],
    provider_snapshot_ids: set[str],
    model_invocation_ids: set[str] = frozenset(),
    allowed_namespaces: tuple[str, ...] = (),
    input_bundle: dict[str, Any] | None = None,
    scope: dict[str, Any] | None = None,
    scope_approval: dict[str, Any] | None = None,
    limits: ModelingLimits | None = None,
) -> dict[str, Any]:
    effective_limits = limits or ModelingLimits()
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    try:
        verify_proposal(proposal)
    except Exception as exc:  # noqa: BLE001 - all validation errors become report issues
        failures.append(issue("CONTRACT_OR_ID_INVALID", str(exc), []))
    if proposal["project_lock_id"] != current_project_lock_id:
        failures.append(issue("PROJECT_LOCK_STALE", "proposal is bound to another or stale Project Lock", []))
    catalog_digest = current_catalog_digest or ContractCatalog.load().digest
    if not catalog_digest or catalog_digest != ContractCatalog.load().digest:
        failures.append(issue("CATALOG_STALE", "Contract Catalog binding is absent or stale", []))
    if input_bundle is not None:
        try:
            verify_input_bundle(input_bundle, current_catalog_digest=catalog_digest)
        except ModelingControlError as exc:
            failures.append(issue("CATALOG_STALE", str(exc), []))
        if input_bundle["modeling_input_bundle_id"] != proposal["modeling_input_bundle_id"]:
            failures.append(issue("PROJECT_LOCK_STALE", "proposal uses another Modeling Input Bundle", []))
    if scope is not None and scope_approval is not None:
        try:
            verify_scope_approval(scope, scope_approval)
        except ModelingControlError as exc:
            failures.append(issue("SCOPE_APPROVAL_STALE", str(exc), []))
    candidates = [*proposal["tbox_candidates"], *proposal["mapping_candidates"], *proposal["abox_candidates"], *proposal["shacl_candidates"]]
    if len(candidates) > effective_limits.max_total_candidates:
        failures.append(issue("RESOURCE_LIMIT_EXCEEDED", "candidate count exceeds configured limit", []))
    candidate_ids = {item["candidate_id"] for item in candidates}
    for candidate in candidates:
        refs = [candidate["candidate_id"]]
        if not set(candidate["evidence_refs"]).issubset(evidence_ids):
            failures.append(issue("EVIDENCE_CLOSURE", "candidate EvidenceRecord closure failed", refs))
        if not set(candidate["kg_ir_item_refs"]).issubset(kg_ir_item_ids):
            failures.append(issue("KG_IR_CLOSURE", "candidate KG-IR closure failed", refs))
        if not set(candidate["baseline_element_refs"]).issubset(baseline_element_ids):
            failures.append(issue("BASELINE_CLOSURE", "candidate baseline closure failed", refs))
        if not set(candidate["provider_snapshot_refs"]).issubset(provider_snapshot_ids):
            failures.append(issue("PROVIDER_SNAPSHOT_CLOSURE", "candidate provider snapshot closure failed", refs))
        if not set(candidate["model_invocation_refs"]).issubset(model_invocation_ids):
            failures.append(issue("MODEL_INVOCATION_CLOSURE", "candidate model invocation closure failed", refs))
        if not set(candidate["dependency_candidate_refs"]).issubset(candidate_ids):
            failures.append(issue("CANDIDATE_DEPENDENCY_MISSING", "candidate dependency closure failed", refs))
        if candidate["support_status"] == "UNSUPPORTED":
            failures.append(issue("UNSUPPORTED_CANDIDATE", "unsupported candidate is blocking", refs))
        for problem in candidate["issues"]:
            (failures if problem["severity"] == "BLOCKING" else warnings).append(problem)
        body = candidate["body"]
        for field in ("subject_iri", "predicate_iri", "object_iri", "target_iri"):
            if body.get(field):
                try:
                    validate_iri(body[field], allowed_namespaces=allowed_namespaces, creating=candidate["candidate_action"] == "CREATE_NEW" and field in {"subject_iri", "target_iri"})
                except ModelingControlError as exc:
                    failures.append(issue("UNAUTHORIZED_NAMESPACE", str(exc), refs))
        if candidate["candidate_kind"] != candidate["publication_scope"]:
            failures.append(issue("TBOX_ABOX_SCOPE_SEPARATION", "candidate partition and publication scope differ", refs))
        if body["candidate_type"] == "DATA_PROPERTY_ASSERTION" and not _literal_is_valid(body["literal"]):
            failures.append(issue("DATATYPE_LEXICAL_INVALID", "typed literal lexical form is invalid", refs))
        if body["candidate_type"] in {"MIN_COUNT", "MAX_COUNT"} and not isinstance(body["integer_value"], int):
            failures.append(issue("SHACL_STRUCTURE_INVALID", "cardinality candidate lacks an integer value", refs))
        if candidate["review_required"]:
            warnings.append(issue("HUMAN_REVIEW_REQUIRED", "candidate requires an explicit human decision", refs, severity="WARNING"))
    conflicts = proposal["conflicts"]
    failures.extend(item for item in conflicts if item["severity"] == "BLOCKING")
    warnings.extend(item for item in conflicts if item["severity"] != "BLOCKING")
    if proposal["coverage_summary"]["gaps"]:
        warnings.append(
            issue(
                "CQ_COVERAGE_GAP",
                "competency-question structural coverage has unresolved gaps; no CQ execution is claimed",
                [],
                severity="WARNING",
            )
        )
    all_issues = sorted({item["issue_id"]: item for item in [*failures, *warnings]}.values(), key=lambda item: item["issue_id"])
    overall = "FAIL" if failures else ("REVIEW_REQUIRED" if candidates or warnings else "PASS")
    checks = []
    for name in CHECKS:
        related = [item for item in all_issues if ISSUE_CHECKS.get(item["code"]) == name]
        status = "FAIL" if any(item["issue_id"] in {failure["issue_id"] for failure in failures} for item in related) else ("REVIEW_REQUIRED" if related or name == "COMPETENCY_QUESTION_STRUCTURAL_COVERAGE" else "PASS")
        checks.append({"check_id": name, "status": status, "issues": related})
    core = {
        "manifest_kind": "KG_MNP_FORMAL_PREVALIDATION_REPORT", "schema_version": "1.0.0",
        "proposal_id": proposal["proposal_id"], "proposal_digest": proposal["content_digest"],
        "status": overall, "checks": checks, "issues": all_issues,
        "owl_consistency_claimed": False, "shacl_execution_claimed": False, "cq_execution_claimed": False,
    }
    report = finalize_document(core, id_field="formal_prevalidation_report_id", urn_kind="formal-prevalidation-report")
    validate_contract("formal-prevalidation-report", report)
    return report


def verify_prevalidation(value: dict[str, Any], *, proposal: dict[str, Any] | None = None) -> None:
    validate_contract("formal-prevalidation-report", value)
    verify_document(value, id_field="formal_prevalidation_report_id", urn_kind="formal-prevalidation-report")
    if any(value[field] for field in ("owl_consistency_claimed", "shacl_execution_claimed", "cq_execution_claimed")):
        raise ModelingProposalError("prevalidation claimed a Prompt 5 final validation")
    if proposal is not None and (value["proposal_id"] != proposal["proposal_id"] or value["proposal_digest"] != proposal["content_digest"]):
        raise ModelingProposalError("prevalidation report is STALE")
