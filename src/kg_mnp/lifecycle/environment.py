from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from kg_mnp.contracts.canonical import semantic_hash

from .errors import LifecycleError
from .registry.events import append_event
from .registry.manifest import load_manifest
from .security import human
from .store import bind_identity, list_records, next_id, save


def init_environment(workspace: Path | str, *, environment_name: str, environment_class: str = "DEVELOPMENT", allowed_package_names: list[str] | None = None, allowed_ontology_iris: list[str] | None = None, activation_roles: list[str] | None = None, activation_quorum: int = 1, rollback_roles: list[str] | None = None, rollback_quorum: int = 1, **extra) -> dict:
    root=Path(workspace); m=load_manifest(root)
    value={"manifest_kind":"KG_MNP_ENVIRONMENT_MANIFEST","schema_version":"1.0.0","registry_id":m["registry_id"],"environment_name":environment_name,"environment_class":environment_class,"allowed_package_names":sorted(allowed_package_names or []),"allowed_ontology_iris":sorted(allowed_ontology_iris or []),"allowed_release_types":sorted(extra.pop("allowed_release_types",["INITIAL_RELEASE","PATCH_COMPATIBLE","MINOR","MAJOR"])),"activation_roles":sorted(activation_roles or ["RELEASE_MANAGER"]),"activation_quorum":activation_quorum,"rollback_roles":sorted(rollback_roles or ["RELEASE_MANAGER"]),"rollback_quorum":rollback_quorum,"breaking_release_policy":extra.pop("breaking_release_policy","REQUIRE_EXPLICIT_ACK"),"pointer_policy":extra.pop("pointer_policy","CAS_GENERATION"),"status":"ACTIVE",**extra}
    bind_identity(value, "environment_id", "environment-manifest"); save(root,f"records/environments/{value['environment_id'].rsplit(':',1)[1]}.json",value); pointer={"manifest_kind":"KG_MNP_ENVIRONMENT_POINTER","schema_version":"1.0.0","registry_id":m["registry_id"],"environment_id":value["environment_id"],"generation":0,"active_release_id":None,"active_package_id":None,"active_package_version":None,"active_release_attestation_id":None,"previous_pointer_hash":None,"selection_status":"NO_RELEASE_SELECTED"}; bind_identity(pointer, "pointer_id", "environment-pointer"); pointer["pointer_hash"]=pointer["content_digest"]; save(root,f"state/environment-pointer-{value['environment_id'].rsplit(':',1)[1]}.json",pointer); append_event(root,"EnvironmentCreated",{"subject_id":value["environment_id"]}); return value


def _pointer(root: Path, environment_id: str) -> tuple[Path, dict]:
    path=root/"state"/f"environment-pointer-{environment_id.rsplit(':',1)[1]}.json"
    if not path.is_file(): raise LifecycleError("ENVIRONMENT_INVALID", "environment pointer not found")
    return path, json.loads(path.read_bytes())


def propose_activation(workspace: Path | str, *, environment_id: str, release_id: str, rationale: str, requested_by: str = "operator", activation_kind: str = "ACTIVATE") -> dict:
    root=Path(workspace); env=next((x for x in list_environments(root) if x.get("environment_id")==environment_id),None)
    if env is None: raise LifecycleError("ENVIRONMENT_INVALID", "environment not found")
    _, pointer=_pointer(root, environment_id)
    value={"manifest_kind":"KG_MNP_ACTIVATION_PROPOSAL","schema_version":"1.0.0","registry_id":env["registry_id"],"environment_id":environment_id,"activation_kind":activation_kind,"base_pointer_generation":pointer["generation"],"base_pointer_hash":pointer["pointer_hash"],"target_release_id":release_id,"target_package_id":None,"release_attestation_id":None,"rationale":rationale,"requested_by":requested_by,"proposal_status":"PROPOSED"}
    bind_identity(value,"activation_proposal_id","activation-proposal"); save(root,f"records/activation-proposals/{value['activation_proposal_id'].rsplit(':',1)[1]}.json",value); append_event(root,"ActivationProposed",{"subject_id":value["activation_proposal_id"],"target_environment_id":environment_id,"target_release_id":release_id}); return value


def review_activation(workspace: Path | str, *, proposal_id: str, decision: str, reviewer_id: str, reviewer_roles: list[str] | None = None, rationale: str = "", breaking_change_acknowledged: bool = False) -> dict:
    root=Path(workspace); proposals=list_records(root,"records/activation-proposals"); proposal=next((x for x in proposals if x.get("activation_proposal_id")==proposal_id),None)
    if proposal is None: raise LifecycleError("LIFECYCLE_ARTIFACT_MISSING", "activation proposal not found")
    human(reviewer_id,"HUMAN",True)
    value={"manifest_kind":"KG_MNP_ACTIVATION_REVIEW_DECISION","schema_version":"1.0.0","registry_id":proposal["registry_id"],"activation_proposal_id":proposal_id,"environment_id":proposal["environment_id"],"decision":decision,"reviewer_id":reviewer_id,"reviewer_roles":sorted(set(reviewer_roles or ["RELEASE_MANAGER"])),"reviewer_type":"HUMAN","rationale":rationale,"explicit_human_action":True,"breaking_change_acknowledged":breaking_change_acknowledged,"semantic_decision_hash":semantic_hash({"proposal":proposal_id,"decision":decision,"reviewer":reviewer_id,"rationale":rationale}),"observed_at":datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00","Z")}
    bind_identity(value,"decision_id","activation-review-decision"); value["semantic_decision_hash"]=value["content_digest"]; save(root,f"records/activation-reviews/{value['decision_id'].rsplit(':',1)[1]}.json",value); append_event(root,"ActivationReviewed",{"subject_id":value["decision_id"],"activation_proposal_id":proposal_id}); return value


def execute_activation(workspace: Path | str, *, proposal_id: str, decision_id: str, expected_generation: int | None = None, expected_pointer_hash: str | None = None, reviewer_id: str = "operator", breaking_change_acknowledged: bool = False) -> dict:
    root=Path(workspace); proposal=next((x for x in list_records(root,"records/activation-proposals") if x.get("activation_proposal_id")==proposal_id),None)
    decision=next((x for x in list_records(root,"records/activation-reviews") if x.get("decision_id")==decision_id),None)
    if proposal is None or decision is None: raise LifecycleError("ACTIVATION_BLOCKED", "activation proposal or review is missing")
    if decision.get("decision") not in {"APPROVE_ACTIVATION", "APPROVE_ROLLBACK", "APPROVE"} or not decision.get("explicit_human_action"):
        raise LifecycleError("ACTIVATION_BLOCKED", "activation review did not approve")
    if proposal.get("activation_kind") == "ROLLBACK":
        return rollback(root, environment_id=proposal["environment_id"], reviewer_id=reviewer_id, rationale=proposal.get("rationale", ""), expected_generation=expected_generation if expected_generation is not None else proposal.get("base_pointer_generation"), expected_pointer_hash=expected_pointer_hash if expected_pointer_hash is not None else proposal.get("base_pointer_hash"))
    return activate(root, environment_id=proposal["environment_id"], release_id=proposal["target_release_id"], reviewer_id=reviewer_id, breaking_change_acknowledged=breaking_change_acknowledged or decision.get("breaking_change_acknowledged",False), expected_generation=expected_generation if expected_generation is not None else proposal.get("base_pointer_generation"), expected_pointer_hash=expected_pointer_hash if expected_pointer_hash is not None else proposal.get("base_pointer_hash"))
def list_environments(workspace): return list_records(workspace,"records/environments")
def activate(workspace: Path | str, *, environment_id: str, release_id: str, reviewer_id: str, reviewer_roles: list[str] | None = None, rationale: str = "", breaking_change_acknowledged: bool = False, expected_generation: int | None = None, expected_pointer_hash: str | None = None) -> dict:
    root=Path(workspace); env=next((x for x in list_environments(root) if x.get("environment_id")==environment_id),None)
    if not env: raise LifecycleError("LIFECYCLE_ARTIFACT_MISSING","environment not found")
    human(reviewer_id, "HUMAN", True)
    if env.get("breaking_release_policy")=="REQUIRE_EXPLICIT_ACK" and not breaking_change_acknowledged: raise LifecycleError("LIFECYCLE_ACTIVATION_NOT_AUTHORIZED","explicit activation acknowledgement required")
    path=next((p for p in (root/"state").glob(f"environment-pointer-{environment_id.rsplit(':',1)[1]}.json")),None); pointer=__import__("json").loads(path.read_bytes()) if path else {}
    if expected_generation is not None and pointer.get("generation") != expected_generation:
        raise LifecycleError("LIFECYCLE_CONCURRENCY_CONFLICT", "environment generation changed")
    if expected_pointer_hash is not None and pointer.get("pointer_hash") != expected_pointer_hash:
        raise LifecycleError("LIFECYCLE_CONCURRENCY_CONFLICT", "environment pointer changed")
    old_hash=pointer.get("pointer_hash"); new={**pointer,"generation":pointer.get("generation",0)+1,"active_release_id":release_id,"selection_status":"CONTROL_PLANE_SELECTED","previous_pointer_hash":old_hash}; bind_identity(new, "pointer_id", "environment-pointer"); new["pointer_hash"]=new["content_digest"]
    save(root,path.relative_to(root).as_posix(),new); receipt={"manifest_kind":"KG_MNP_ACTIVATION_EXECUTION_RECEIPT","schema_version":"1.0.0","registry_id":env["registry_id"],"activation_proposal_id":next_id("activation-proposal",{"environment":environment_id,"release":release_id}),"activation_review_decision_id":next_id("activation-review-decision",{"environment":environment_id,"reviewer":reviewer_id}),"environment_id":environment_id,"old_pointer_hash":old_hash,"new_pointer_hash":new["pointer_hash"],"old_generation":pointer.get("generation",0),"new_generation":new["generation"],"target_release_id":release_id,"target_package_id":None,"verification_evidence":["pointer-cas-verified"],"registry_event_id":None,"execution_status":"APPLIED","observed_at":datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00","Z")}; bind_identity(receipt, "execution_id", "activation-execution-receipt"); event=append_event(root,"ActivationApplied",{"subject_id":receipt["execution_id"],"target_release_id":release_id,"target_environment_id":environment_id}); receipt["registry_event_id"]=event["event_id"]; bind_identity(receipt, "execution_id", "activation-execution-receipt"); save(root,f"records/activation-receipts/{receipt['execution_id'].rsplit(':',1)[1]}.json",receipt); return receipt
def rollback(workspace: Path | str, *, environment_id: str, reviewer_id: str, rationale: str = "", expected_generation: int | None = None, expected_pointer_hash: str | None = None) -> dict:
    root=Path(workspace); path=next((p for p in (root/"state").glob(f"environment-pointer-{environment_id.rsplit(':',1)[1]}.json")),None)
    if not path: raise LifecycleError("LIFECYCLE_ARTIFACT_MISSING","environment pointer not found")
    human(reviewer_id, "HUMAN", True)
    pointer=json.loads(path.read_bytes())
    if expected_generation is not None and pointer.get("generation") != expected_generation:
        raise LifecycleError("LIFECYCLE_CONCURRENCY_CONFLICT", "environment generation changed")
    if expected_pointer_hash is not None and pointer.get("pointer_hash") != expected_pointer_hash:
        raise LifecycleError("LIFECYCLE_CONCURRENCY_CONFLICT", "environment pointer changed")
    old=pointer.get("active_release_id"); pointer={**pointer,"generation":pointer.get("generation",0)+1,"active_release_id":None,"active_package_id":None,"active_package_version":None,"selection_status":"NO_RELEASE_SELECTED","previous_pointer_hash":pointer.get("pointer_hash")}; bind_identity(pointer, "pointer_id", "environment-pointer"); pointer["pointer_hash"]=pointer["content_digest"]; save(root,path.relative_to(root).as_posix(),pointer); result={"status":"ROLLED_BACK","environment_id":environment_id,"previous_release_id":old,"pointer_hash":pointer["pointer_hash"],"reviewer_id":reviewer_id}; append_event(root,"RollbackApplied",{"subject_id":next_id("rollback",result),"target_environment_id":environment_id}); return result
