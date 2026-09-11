"""Optional local integration preparation and truthful no-transport observations."""
from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path

from zhigou_toolchain.contracts.canonical import file_sha256, semantic_hash
from zhigou_toolchain.contracts.document_io import atomic_write_json, read_document
from zhigou_toolchain.integrations.graphdb import GraphDBAdapter
from zhigou_toolchain.integrations.protocol import (
    IntegrationApproval,
    IntegrationTarget,
)
from zhigou_toolchain.integrations.webvowl import WebVOWLConverter
from zhigou_toolchain.integrations.workflow import LocalWorkflowOutbox
from zhigou_toolchain.lifecycle.guards import (
    package_files,
    package_record,
    release_record,
)
from zhigou_toolchain.semantic_kernel.packaging.verifier import verify_package
from zhigou_toolchain.workspace.service import load_project_manifest

from .compilation import package_path
from .errors import ServiceBoundaryError

OPERATIONS=frozenset({"visualization.export","integration.plan","integration.review","integration.execute","integration.verify","workflow.enqueue"})


def _read(directory,identifier):
    path=directory/(identifier+".json")
    if not path.is_file() or path.is_symlink():raise ServiceBoundaryError("INTEGRATION_ARTIFACT_MISSING","integration artifact is unavailable",status_code=404)
    value=read_document(path)
    if value.get("content_digest")!=semantic_hash({k:v for k,v in value.items() if k!="content_digest"}):
        raise ServiceBoundaryError("INTEGRATION_ARTIFACT_INVALID","integration artifact digest mismatch",status_code=409)
    return value


def _save(directory,identifier,value):
    value=json.loads(json.dumps(value,allow_nan=False))
    value={**value,"content_digest":semantic_hash(value)}
    atomic_write_json(directory/(identifier+".json"),value)
    return value


def execute(app,project,request,principal):
    name,params=request.operation_id,request.parameters
    directory=Path(project.root)/"artifacts/builds/integrations"
    directory.mkdir(parents=True,exist_ok=True)
    if name=="visualization.export":
        converted=WebVOWLConverter().convert(package_path(project,params["package_id"]))
        identifier="webvowl-"+params["package_id"].rsplit(":",1)[-1]
        _save(directory,identifier,converted)
        return {**converted,"artifact_id":identifier,"sha256":file_sha256(directory/(identifier+".json"))}
    if name in {"integration.plan","workflow.enqueue"}:
        release=release_record(project.registry_root,params["release_id"])
        record=package_record(project.registry_root,release["package_id"])
        package=package_files(project.registry_root,record)[2]
        verify_package(package)
        if name=="workflow.enqueue":
            definition={"action_id":"request-source-review","input_contract":"closed-note-v1",
                        "released_ontology_context":{"release_id":release["release_id"],"package_id":record["package_id"]}}
            receipt=LocalWorkflowOutbox(directory/"outbox").enqueue(action_definition=definition,project_id=project.project_id,
                release_id=release["release_id"],payload={"note":params["note"]},idempotency_key=request.idempotency_key or "fenced-job")
            return receipt.to_dict()
        target=IntegrationTarget("local-graphdb","GRAPHDB","unconfigured-v1")
        adapter=GraphDBAdapter();adapter.validate_target(target)
        plan=adapter.plan_import(project_id=project.project_id,release_id=release["release_id"],package_id=record["package_id"],target=target,package_root=package)
        plan=replace(plan,plan_id="plan_"+semantic_hash(asdict(plan)))
        return _save(directory,plan.plan_id,{"plan":asdict(plan),"target":asdict(target),"availability":"EXTERNAL_TRANSPORT_NOT_CONFIGURED",
            "offline_only":load_project_manifest(project.root).document["settings"]["offline_only"]})
    stored=_read(directory,params["plan_id"])
    plan=stored["plan"]
    if plan["project_id"]!=project.project_id:raise ServiceBoundaryError("PROJECT_FORBIDDEN","integration project differs",status_code=403)
    if name=="integration.review":
        approval=IntegrationApproval("approval_"+semantic_hash({"plan":plan,"principal":principal.principal_id,"rationale":params["rationale"]}),
            plan["plan_id"],project.project_id,principal.principal_id,plan["allowed_effect"],plan["payload_digest"],plan["target_revision"],None)
        _save(directory,approval.approval_id,{"approval":asdict(approval),"rationale":params["rationale"],"grant_reference":principal.token_id})
        return {"approval":asdict(approval),"rationale":params["rationale"]}
    approved=_read(directory,params["approval_id"])
    approval=approved["approval"]
    actor=app.tokens.resolve(approved["grant_reference"])
    if (actor.principal_type!="HUMAN" or actor.principal_id!=approval["principal_id"] or not actor.can("integration:review")
            or approval["plan_id"]!=plan["plan_id"] or approval["payload_digest"]!=plan["payload_digest"]
            or approval["target_revision"]!=plan["target_revision"] or approval["approved_effect"]!=plan["allowed_effect"]):
        raise ServiceBoundaryError("INTEGRATION_REVIEW_INVALID","current human approval does not bind this plan",status_code=403)
    offline=load_project_manifest(project.root).document["settings"]["offline_only"]
    # No transport is provisioned by this local service configuration. Neither
    # executing nor observing invents a request, deployment or unknown outcome.
    return {"plan_id":plan["plan_id"],"status":"BLOCKED_BY_OFFLINE_POLICY" if offline else "EXTERNAL_TRANSPORT_NOT_CONFIGURED",
            "desired_release_id":plan["release_id"],"observed_deployed_release_id":None,"external_request_attempted":False,
            "last_verification_status":"NOT_RUN","reason":"No separately licensed/authorized external target transport is configured"}
