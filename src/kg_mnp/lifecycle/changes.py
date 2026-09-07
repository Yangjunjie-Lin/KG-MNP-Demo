from __future__ import annotations

from pathlib import Path
from typing import Any

from .errors import LifecycleError
from .registry.events import append_event, read_events
from .registry.manifest import load_manifest
from .security import inert_intent
from .store import bind_identity, list_records, save

FOLDER="records/changes"

def create_change_proposal(workspace: Path | str, *, base_package_id: str | None = None, base_release_id: str | None = None, change_type: str = "CORRECTIVE", change_scope: str = "TBOX", affected_iris: list[str] | None = None, requested_outcomes: list[str] | None = None, submitted_by: str = "operator", feedback_refs: list[str] | None = None, **extra: Any) -> dict[str, Any]:
    root=Path(workspace); m=load_manifest(root); affected_iris=affected_iris or []; requested_outcomes=requested_outcomes or []
    inert_intent(requested_outcomes)
    if base_package_id is None and base_release_id is None:
        raise LifecycleError("LIFECYCLE_CONTRACT_INVALID", "a base package or base release is required")
    value={"manifest_kind":"KG_MNP_CHANGE_PROPOSAL","schema_version":"1.0.0","registry_id":m["registry_id"],"base_package_id":base_package_id,"base_release_id":base_release_id,"feedback_refs":feedback_refs or [],"change_type":change_type,"change_scope":change_scope,"affected_iris":sorted(set(affected_iris)),"requested_outcomes":sorted(set(requested_outcomes)),"required_competency_questions":extra.pop("required_competency_questions",[]),"risk_class":extra.pop("risk_class","UNKNOWN"),"constraints":extra.pop("constraints",[]),"submitted_by":submitted_by,"proposal_status":"DRAFT",**extra}
    bind_identity(value, "change_proposal_id", "change-proposal"); save(root,f"{FOLDER}/{value['change_proposal_id'].rsplit(':',1)[1]}.json",value); append_event(root,"ChangeProposalCreated",{"subject_id":value["change_proposal_id"],"base_package_id":base_package_id}); return value

def submit_change_proposal(workspace: Path | str, proposal_id: str) -> dict[str, Any]:
    root=Path(workspace); rows=list_records(root,FOLDER)
    for row in rows:
        if row.get("change_proposal_id")==proposal_id:
            append_event(root,"ChangeProposalSubmitted",{"subject_id":proposal_id,"transition":"SUBMITTED"}); return {**row,"proposal_status":"SUBMITTED"}
    raise LifecycleError("LIFECYCLE_ARTIFACT_MISSING","change proposal not found")

def list_change_proposals(workspace: Path | str) -> list[dict[str, Any]]: return list_records(workspace,FOLDER)


def attach_candidate_package(workspace: Path | str, proposal_id: str, candidate_package_id: str) -> dict[str, Any]:
    """Record a candidate association without mutating either package or proposal."""
    root=Path(workspace); proposal=next((x for x in list_change_proposals(root) if x.get("change_proposal_id")==proposal_id),None)
    if proposal is None: raise LifecycleError("LIFECYCLE_ARTIFACT_MISSING","change proposal not found")
    package=next((x for x in list_records(root,"records/packages") if x.get("package_id")==candidate_package_id),None)
    if package is None or package.get("import_status")!="IMPORTED_VERIFIED": raise LifecycleError("PACKAGE_IMPORT_INVALID","candidate package is not imported and verified")
    if package.get("package_status")!="VALIDATED_UNPUBLISHED": raise LifecycleError("PACKAGE_IMPORT_INVALID","candidate package state is not VALIDATED_UNPUBLISHED")
    base=proposal.get("base_package_id")
    if base and base==candidate_package_id: raise LifecycleError("PACKAGE_VERSION_CONFLICT","candidate cannot equal base package")
    event=append_event(root,"CandidatePackageAttached",{"subject_id":proposal_id,"related_ids":[candidate_package_id],"transition":"CANDIDATE_ATTACHED"})
    return {"status":"CANDIDATE_ATTACHED","change_proposal_id":proposal_id,"candidate_package_id":candidate_package_id,"event_id":event["event_id"]}


def evaluate_change(workspace: Path | str, proposal_id: str, *, candidate_package_id: str | None = None, semantic_diff_id: str | None = None, version_compatibility_report_id: str | None = None, impact_analysis_id: str | None = None, regression_test_report_id: str | None = None) -> dict[str, Any]:
    root = Path(workspace)
    proposal = next((x for x in list_change_proposals(root) if x.get("change_proposal_id") == proposal_id), None)
    if proposal is None:
        raise LifecycleError("LIFECYCLE_ARTIFACT_MISSING", "change proposal not found")
    from .guards import package_record, record_by_id

    # Candidate attachment is an event-backed relationship.  A caller may
    # narrow it, but cannot create the relationship merely by supplying an ID.
    attached = None
    for event in read_events(root):
        if event.get("event_type") == "CandidatePackageAttached" and event.get("payload", {}).get("subject_id") == proposal_id:
            related = event.get("payload", {}).get("related_ids", [])
            if related:
                attached = related[-1]
    candidate_package_id = candidate_package_id or attached
    reasons: list[str] = []
    if not candidate_package_id:
        reasons.append("candidate-package-missing")
    elif candidate_package_id == proposal.get("base_package_id"):
        reasons.append("candidate-equals-base")
    else:
        try:
            package_record(root, candidate_package_id)
        except LifecycleError as exc:
            reasons.append(exc.code)
    if not proposal.get("base_package_id"):
        reasons.append("base-package-missing")
    else:
        try:
            package_record(root, proposal["base_package_id"])
        except LifecycleError as exc:
            reasons.append(exc.code)
    references = {
        "semantic_diff_id": ("records/diffs", "diff_id", semantic_diff_id),
        "version_compatibility_report_id": ("records/version-compatibility", "report_id", version_compatibility_report_id),
        "impact_analysis_id": ("records/impacts", "impact_id", impact_analysis_id),
        "regression_test_report_id": ("records/regressions", "report_id", regression_test_report_id),
    }
    for field, (folder, id_field, identifier) in references.items():
        if not identifier:
            reasons.append(f"{field}-missing")
            continue
        try:
            row = record_by_id(root, folder, id_field, identifier)
            if field == "regression_test_report_id" and (row.get("status") != "PASSED" or not row.get("required_passed")):
                reasons.append("regression-not-passed")
            if field == "impact_analysis_id" and row.get("status") not in {"COMPLETE", "VALID"}:
                reasons.append("impact-not-complete")
        except LifecycleError as exc:
            reasons.append(exc.code)
    status = "COMPLETE" if not reasons else "BLOCKED"
    value = {
        "manifest_kind": "KG_MNP_CHANGE_EVALUATION", "schema_version": "1.0.0", "registry_id": proposal["registry_id"],
        "change_proposal_id": proposal_id, "base_package_id": proposal.get("base_package_id"), "candidate_package_id": candidate_package_id,
        "semantic_diff_id": semantic_diff_id, "version_compatibility_report_id": version_compatibility_report_id,
        "impact_analysis_id": impact_analysis_id, "regression_test_report_id": regression_test_report_id,
        "evaluation_status": status, "blocking_reasons": sorted(set(reasons)), "review_requirements": ["REVALIDATE_INPUT_CLOSURE"] if reasons else [],
    }
    bind_identity(value, "evaluation_id", "change-evaluation")
    save(root, f"records/change-evaluations/{value['evaluation_id'].rsplit(':', 1)[1]}.json", value)
    event = append_event(root, "ChangeEvaluated", {"subject_id": value["evaluation_id"], "related_ids":[proposal_id], "transition":"EVALUATED"})
    return {**value, "event_id": event["event_id"]}
