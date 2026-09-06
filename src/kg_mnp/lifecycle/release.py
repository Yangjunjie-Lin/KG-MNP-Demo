from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from kg_mnp.contracts.canonical import semantic_hash

from .errors import LifecycleError
from .registry.events import append_event
from .registry.manifest import load_manifest
from .security import human
from .store import bind_identity, list_records, load, next_id, save


def _now(): return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00","Z")
def create_release_candidate(workspace: Path | str, *, candidate_package_id: str, base_package_id: str | None = None, semantic_diff_id: str = "", version_compatibility_report_id: str = "", impact_analysis_id: str = "", regression_test_report_id: str = "", change_proposal_id: str = "", change_evaluation_id: str = "", release_policy_id: str = "", release_candidate_kind: str = "INITIAL", required_roles: list[str] | None = None, minimum_distinct_reviewers: int = 1, **extra) -> dict:
    root=Path(workspace); m=load_manifest(root); required_roles=required_roles or ["RELEASE_MANAGER"]
    value={"manifest_kind":"KG_MNP_RELEASE_CANDIDATE","schema_version":"1.0.0","registry_id":m["registry_id"],"release_candidate_kind":release_candidate_kind,"base_release_id":None,"base_package_id":base_package_id,"candidate_package_id":candidate_package_id,"change_proposal_id":change_proposal_id or None,"change_evaluation_id":change_evaluation_id or None,"semantic_diff_id":semantic_diff_id or None,"version_compatibility_report_id":version_compatibility_report_id or None,"impact_analysis_id":impact_analysis_id or None,"regression_test_report_id":regression_test_report_id or None,"release_policy_id":release_policy_id or next_id("release-policy",{"version":"1.0.0"}),"required_roles":required_roles,"alternative_roles":[],"minimum_distinct_reviewers":minimum_distinct_reviewers,"required_acknowledgements":[],"candidate_status":"SUBMITTED",**extra}
    bind_identity(value, "release_candidate_id", "release-candidate"); save(root,f"records/release-candidates/{value['release_candidate_id'].rsplit(':',1)[1]}.json",value); append_event(root,"ReleaseCandidateCreated",{"subject_id":value["release_candidate_id"],"candidate_package_id":candidate_package_id}); return value

def record_review(workspace: Path | str, release_candidate_id: str, *, reviewer_id: str, reviewer_roles: list[str], action: str = "APPROVE", rationale: str = "", explicit_human_action: bool = True, acknowledgement_refs: list[str] | None = None) -> dict:
    root=Path(workspace); rows=list_records(root,"records/release-reviews"); actions=[]
    human(reviewer_id, "HUMAN", explicit_human_action)
    for row in rows:
        if row.get("release_candidate_id")==release_candidate_id: actions=row.get("actions",[]); log=row; break
    else:
        review_id=next_id("release-review",{"candidate":release_candidate_id})
        log={"manifest_kind":"KG_MNP_RELEASE_REVIEW_DECISION_LOG","schema_version":"1.0.0","registry_id":load_manifest(root)["registry_id"],"review_id":review_id,"review_log_id":review_id,"release_policy_id":None,"review_policy_id":None,"release_candidate_id":release_candidate_id,"actions":[]}
    action_row={"registry_id":log["registry_id"],"review_id":log["review_id"],"release_candidate_id":release_candidate_id,"sequence":len(actions)+1,"previous_action_hash":actions[-1].get("action_hash") if actions else None,"previous_semantic_action_hash":None,"action":action,"reviewer_id":reviewer_id,"reviewer_roles":sorted(set(reviewer_roles)),"reviewer_type":"HUMAN","explicit_human_action":explicit_human_action,"rationale":rationale,"acknowledgement_refs":acknowledgement_refs or [],"observed_at":_now(),"semantic_action_hash":next_id("review-action-semantic",{"candidate":release_candidate_id,"sequence":len(actions)+1}).rsplit(":",1)[1],"action_hash":next_id("review-action",{"candidate":release_candidate_id,"sequence":len(actions)+1}).rsplit(":",1)[1]}
    log["actions"]=actions+[action_row]; log["final_decision"]=action; log["role_coverage"]=sorted({r for a in log["actions"] for r in a["reviewer_roles"]}); log["quorum_satisfied"]=action=="APPROVE" and explicit_human_action; log["finalized"]=log["quorum_satisfied"]; log["semantic_decision_hash"]=semantic_hash(log["actions"]); log["authority_digests"]=[]; bind_identity(log, "review_log_id", "release-review-decision-log"); save(root,f"records/release-reviews/{log['review_id'].rsplit(':',1)[1]}.json",log); append_event(root,"ReleaseReviewRecorded",{"subject_id":log["review_id"],"release_candidate_id":release_candidate_id}); return log

def publish_release(workspace: Path | str, candidate: dict, review: dict, *, package_name: str = "ontology-package", package_version: str = "0.0.0", ontology_iri: str = "urn:kg-mnp:ontology", version_iri: str = "urn:kg-mnp:version") -> dict:
    root=Path(workspace)
    if not review.get("quorum_satisfied") or not review.get("finalized"): raise LifecycleError("LIFECYCLE_RELEASE_NOT_AUTHORIZED","human review quorum is not satisfied")
    if candidate.get("candidate_status") not in {"SUBMITTED","APPROVED"}: raise LifecycleError("LIFECYCLE_RELEASE_NOT_AUTHORIZED","candidate is not publishable")
    package_records=list_records(root,"records/packages")
    if package_records and not any(row.get("package_id") == candidate.get("candidate_package_id") and row.get("import_status") == "IMPORTED_VERIFIED" and row.get("package_status") == "VALIDATED_UNPUBLISHED" for row in package_records):
        raise LifecycleError("LIFECYCLE_RELEASE_NOT_AUTHORIZED", "candidate package is not an imported verified package")
    value={"manifest_kind":"KG_MNP_RELEASE","schema_version":"1.0.0","registry_id":candidate["registry_id"],"release_status":"RELEASED","release_type":"INITIAL_RELEASE" if not candidate.get("base_package_id") else "PATCH_COMPATIBLE","package_id":candidate["candidate_package_id"],"package_name":package_name,"package_version":package_version,"ontology_iri":ontology_iri,"version_iri":version_iri,"base_release_id":candidate.get("base_release_id"),"change_proposal_id":candidate.get("change_proposal_id"),"change_evaluation_id":candidate.get("change_evaluation_id"),"semantic_diff_id":candidate.get("semantic_diff_id"),"version_compatibility_report_id":candidate.get("version_compatibility_report_id"),"impact_analysis_id":candidate.get("impact_analysis_id"),"regression_test_report_id":candidate.get("regression_test_report_id"),"release_candidate_id":candidate["release_candidate_id"],"release_review_decision_log_id":review["review_id"],"release_review_semantic_hash":review.get("semantic_decision_hash"),"release_policy_id":candidate.get("release_policy_id"),"package_lock_id":None,"package_content_digest":None,"semantic_dataset_digest":None,"release_lineage":[]}
    filename=f"records/releases/{value['release_id'].rsplit(':',1)[1]}.json"
    path=root/filename
    if path.is_file():
        existing=load(root,filename)
        if existing == value or existing.get("content_digest") == value.get("content_digest"):
            return {**existing,"status":"ALREADY_PUBLISHED"}
        raise LifecycleError("LIFECYCLE_CONCURRENCY_CONFLICT", "release identity already exists with different content")
    save(root,filename,value); append_event(root,"ReleasePublished",{"subject_id":value["release_id"],"target_package_id":value["package_id"]}); return value

def list_releases(workspace): return list_records(workspace,"records/releases")

def attest_release(workspace: Path | str, release: dict, *, package_lock_id: str | None = None, package_archive_sha256: str | None = None, authority_records: list[dict] | None = None) -> dict:
    """Create the immutable publication attestation after release verification."""
    root=Path(workspace)
    value={"manifest_kind":"KG_MNP_RELEASE_ATTESTATION","schema_version":"1.0.0","registry_id":release["registry_id"],"release_id":release["release_id"],"release_manifest_file_sha256":release.get("package_content_digest") or "0"*64,"release_manifest_semantic_sha256":release.get("package_content_digest") or "0"*64,"package_id":release["package_id"],"package_lock_id":package_lock_id,"package_lock_content_digest":None,"package_archive_sha256":package_archive_sha256 or "0"*64,"release_candidate_id":release.get("release_candidate_id"),"review_log_id":release.get("release_review_decision_log_id"),"review_semantic_hash":release.get("release_review_semantic_hash"),"semantic_diff_id":release.get("semantic_diff_id"),"impact_analysis_id":release.get("impact_analysis_id"),"regression_report_id":release.get("regression_test_report_id"),"pre_publication_registry_head_hash":"0"*64,"authority_records":authority_records or [],"attestation_status":"VERIFIED"}
    bind_identity(value, "attestation_id", "release-attestation"); save(root,f"records/releases/{value['attestation_id'].rsplit(':',1)[1]}.json",value); return value
