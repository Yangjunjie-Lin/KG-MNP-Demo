"""Application orchestration of the existing modeling/review control plane.

Explicit IDs select each authority. No lexical 'latest', CLI/stdout dispatch,
client reviewer roles, auto-approval, or direct RDF writing is used.
"""
from __future__ import annotations

from kg_mnp.contracts.document_io import read_document
from kg_mnp.domain_packs.registry import DomainPackRegistry
from kg_mnp.modeling.control_plane.alignment import align_terms
from kg_mnp.modeling.control_plane.baseline import build_baseline_snapshot
from kg_mnp.modeling.control_plane.candidates import normalize_candidate_drafts
from kg_mnp.modeling.control_plane.competency import (
    build_question_set,
    structural_coverage,
)
from kg_mnp.modeling.control_plane.confirmation import build_confirmed_package
from kg_mnp.modeling.control_plane.errors import ModelingControlError
from kg_mnp.modeling.control_plane.input_bundle import (
    build_input_bundle,
    verify_input_bundle,
)
from kg_mnp.modeling.control_plane.mappings import build_field_mapping_candidates
from kg_mnp.modeling.control_plane.prevalidation import prevalidate
from kg_mnp.modeling.control_plane.proposal import build_proposal
from kg_mnp.modeling.control_plane.providers.execution import execute_provider
from kg_mnp.modeling.control_plane.providers.models import build_provider_request
from kg_mnp.modeling.control_plane.review.actions import build_review_action
from kg_mnp.modeling.control_plane.review.finalization import finalize_review
from kg_mnp.modeling.control_plane.review.policy import build_review_policy
from kg_mnp.modeling.control_plane.review.queue import (
    build_review_queue,
    verify_review_queue,
)
from kg_mnp.modeling.control_plane.review.replay import review_status
from kg_mnp.modeling.control_plane.scope import build_scope
from kg_mnp.modeling.control_plane.scope_approval import (
    approve_scope,
    verify_scope_approval,
)
from kg_mnp.modeling.control_plane.service import ModelingWorkspaceService
from kg_mnp.modeling.control_plane.terminology import build_terminology_catalog
from kg_mnp.plugins.registry import PluginRegistry
from kg_mnp.plugins.snapshot import build_snapshot

from .errors import ServiceBoundaryError
from .sources import verified_run

PREPARE_OPERATIONS = {"modeling.prepare", "modeling.cq", "modeling.baseline", "modeling.alignment"}
OPERATIONS = frozenset({"modeling.scope", "modeling.scope.approve", *PREPARE_OPERATIONS,
                        "modeling.candidate", "modeling.proposal", "review.action", "review.replay", "review.finalize"})


def _packs(app, modeling):
    registry = DomainPackRegistry(app.configuration.domain_packs_root)
    return [registry.resolve(item["pack_id"], item["pack_version"]) for item in modeling.project_lock["resolved_domain_packs"]]


def _terms(packs):
    terms = []
    for pack in packs:
        manifest = pack.manifest.document
        identifier = manifest["entrypoints"].get("terminology")
        asset = next((row for row in manifest["assets"] if row["asset_id"] == identifier), None)
        if not asset:
            continue
        document = read_document(pack.root / asset["path"])
        for row in document.get("terms", document.get("entries", [])):
            labels = row.get("preferred_labels", {})
            lexical = row.get("label") or row.get("lexical_form") or labels.get("en") or next(iter(labels.values()), None)
            if lexical:
                iri = row.get("iri") or row.get("term_iri")
                terms.append({"lexical_form": lexical, "language": row.get("language"), "source_ref": identifier,
                              "candidate_iris": [iri] if iri else [], "definition": row.get("definition"), "aliases": row.get("aliases", [])})
    return terms


def _bundle_context(modeling, bundle):
    return {key: modeling.find_artifact(bundle[reference]) for key, reference in {
        "scope": "approved_scope_id", "baseline": "baseline_snapshot_id", "terminology": "terminology_catalog_id",
        "alignments": "term_alignment_set_id", "question_set": "competency_question_set_id"}.items()}


def _datasets(modeling, scope):
    # A source -> run binding written by scope creation avoids unverified IR.
    binding = read_document(modeling.build_directory(scope["scope_id"]) / "ingestion-binding.json")
    dataset = verified_run(modeling.root, binding["run_id"]).dataset
    if scope["kg_ir_dataset_ids"] != [dataset["dataset_id"]]:
        raise ServiceBoundaryError("DATASET_BINDING_INVALID", "scope dataset binding changed", status_code=409)
    return [dataset]


def _approval(modeling, scope):
    return read_document(modeling.build_directory(scope["scope_id"]) / "scope-approval.json")


def _prepare(app, modeling, params):
    scope = modeling.find_artifact(params["scope_id"])
    approval = modeling.find_artifact(params["approval_id"])
    verify_scope_approval(scope, approval)
    datasets, packs = _datasets(modeling, scope), _packs(app, modeling)
    question_set = build_question_set(project_lock_id=modeling.project_lock["lock_id"], scope_id=scope["scope_id"], questions=params["questions"])
    baseline = build_baseline_snapshot(project_lock_id=modeling.project_lock["lock_id"], pack_roots=[p.root for p in packs])
    terminology = build_terminology_catalog(scope=scope, baseline=baseline, kg_ir_datasets=datasets, domain_terms=_terms(packs))
    alignments = align_terms(terminology, baseline)
    mappings = build_field_mapping_candidates(kg_ir_datasets=datasets, alignments=alignments, terminology=terminology, baseline=baseline)
    policy = build_review_policy(project_lock_id=modeling.project_lock["lock_id"], profile=app.configuration.review_profile)
    bundle = build_input_bundle(project_lock=modeling.project_lock, scope=scope, approval=approval, question_set=question_set,
                                baseline=baseline, terminology=terminology, alignments=alignments, kg_ir_datasets=datasets,
                                review_policy_id=policy["policy_id"], allowed_provider_ids=["baseline-reuse-provider", "rule-mapping-provider"])
    modeling.write_build(bundle["modeling_input_bundle_id"], {
        "competency-question-set.json": question_set, "baseline-snapshot.json": baseline, "terminology-catalog.json": terminology,
        "term-alignment-set.json": alignments, "field-mapping-candidate-set.json": mappings,
        "review-policy.json": policy, "modeling-input-bundle.json": bundle,
    })
    return {"bundle": bundle, "questions": question_set, "baseline": baseline, "terminology": terminology,
            "alignments": alignments, "mappings": mappings, "policy": policy}


def _propose(modeling, params):
    bundle = modeling.find_artifact(params["bundle_id"])
    verify_input_bundle(bundle)
    context = _bundle_context(modeling, bundle)
    scope, baseline = context["scope"], context["baseline"]
    approval, datasets = _approval(modeling, scope), _datasets(modeling, scope)
    verify_scope_approval(scope, approval)
    directory = modeling.build_directory(bundle["modeling_input_bundle_id"])
    mappings, policy = (read_document(directory / name) for name in ("field-mapping-candidate-set.json", "review-policy.json"))
    items = [item for dataset in datasets for item in dataset["items"]]
    evidence_ids = {record["evidence_id"] for dataset in datasets for record in dataset["evidence_records"]}
    provider_context = {"baseline_elements": baseline["elements"], "alignments": context["alignments"]["alignments"],
                        "field_mappings": mappings["mappings"], "kg_ir_items": items,
                        "default_namespace": scope["namespace_policy"]["default_namespace"],
                        "competency_question_ids": [q["question_id"] for q in context["question_set"]["questions"]]}
    registry, responses, snapshots, requests = PluginRegistry(), [], [], []
    for provider in sorted(set(params["providers"])):
        if provider not in bundle["provider_policy"]["allowed_provider_ids"]:
            raise ServiceBoundaryError("PROVIDER_FORBIDDEN", "provider not allowed by input bundle", status_code=403)
        snapshot = build_snapshot(registry.get(provider))
        request = build_provider_request(modeling_input_bundle_id=bundle["modeling_input_bundle_id"],
            provider_snapshot_id=snapshot["snapshot_id"], capability={"baseline-reuse-provider": "baseline-reuse", "rule-mapping-provider": "field-mapping-proposal"}[provider],
            scope_id=scope["scope_id"], baseline_snapshot_id=baseline["baseline_snapshot_id"],
            terminology_catalog_id=context["terminology"]["terminology_catalog_id"], term_alignment_set_id=context["alignments"]["term_alignment_set_id"],
            kg_ir_dataset_ids=bundle["kg_ir_dataset_ids"], evidence_record_ids=sorted(evidence_ids), context=provider_context)
        responses.append(execute_provider(registry, provider, request))
        snapshots.append(snapshot)
        requests.append(request.artifact)
    item_ids, baseline_ids = {item["item_id"] for item in items}, {item["element_id"] for item in baseline["elements"]}
    candidates = normalize_candidate_drafts(responses, scope=scope, evidence_ids=evidence_ids, kg_ir_item_ids=item_ids, baseline_element_ids=baseline_ids)
    proposal = build_proposal(project_lock_id=modeling.project_lock["lock_id"], input_bundle=bundle,
        field_mappings=mappings, candidate_set=candidates, provider_snapshot_ids=[s["snapshot_id"] for s in snapshots], **context)
    report = prevalidate(proposal, current_project_lock_id=modeling.project_lock["lock_id"], evidence_ids=evidence_ids,
        kg_ir_item_ids=item_ids, baseline_element_ids=baseline_ids, provider_snapshot_ids=set(proposal["provider_snapshots"]),
        allowed_namespaces=tuple(scope["namespace_policy"]["allowed_new_namespaces"]), input_bundle=bundle, scope=scope, scope_approval=approval)
    coverage = structural_coverage(context["question_set"], proposal)
    queue = build_review_queue(proposal, report, policy)
    modeling.write_proposal(proposal["proposal_id"], {"ontology-modeling-proposal.json": proposal,
        "provider-requests.json": requests, "provider-responses.json": responses, "provider-snapshots.json": snapshots,
        "ontology-candidate-set.json": candidates, "formal-prevalidation-report.json": report})
    modeling.write_review(queue["review_queue_id"], {"review-queue.json": queue, "review-policy.json": policy,
        "competency-question-coverage-report.json": coverage})
    return {"proposal": proposal, "prevalidation": report, "queue": queue, "coverage": coverage}


def _review(modeling, request, principal):
    params = request.parameters
    queue = modeling.find_artifact(params["review_id"])
    proposal = modeling.find_artifact(queue["proposal_id"])
    report = modeling.find_artifact(queue["formal_prevalidation_report_id"])
    policy = modeling.find_artifact(queue["review_policy_id"])
    verify_review_queue(queue, proposal=proposal, prevalidation=report, policy=policy)
    actions = modeling.load_actions(params["review_id"])
    if request.operation_id == "review.replay":
        return {"queue": queue, "actions": actions, "status": review_status(queue, actions)}
    if request.operation_id == "review.action":
        head = actions[-1]["action_hash"] if actions else None
        if params["expected_head"] != head:
            raise ServiceBoundaryError("REVIEW_HEAD_CONFLICT", "review changed; reload before deciding", status_code=409)
        item = next((row for row in queue["items"] if row["candidate_id"] == params["candidate_id"]), None)
        if item is None:
            raise ServiceBoundaryError("REVIEW_TARGET_INVALID", "candidate not in current review", status_code=422)
        used = {row["reviewer_role"] for row in actions if row["candidate_id"] == params["candidate_id"] and row["decision"] == "ACCEPT"}
        roles = [role for role in item["required_roles"] if principal.can("review:role:" + role)]
        if not roles:
            raise ServiceBoundaryError("REVIEW_ROLE_FORBIDDEN", "current identity has no required reviewer role", status_code=403)
        role = next((role for role in roles if role not in used), roles[0])
        action = build_review_action(queue=queue, proposal=proposal, policy=policy, existing_actions=actions,
            decision=params["decision"], reviewer_id=principal.principal_id, reviewer_role=role,
            rationale=params["rationale"], candidate_id=params["candidate_id"])
        modeling.append_action(params["review_id"], action)
        return {"action": action, "status": review_status(queue, [*actions, action])}
    bundle = modeling.find_artifact(proposal["modeling_input_bundle_id"])
    context = _bundle_context(modeling, bundle)
    scope = context["scope"]
    _datasets(modeling, scope)
    approval = _approval(modeling, scope)
    coverage = structural_coverage(context["question_set"], proposal)
    final = finalize_review(queue=queue, proposal=proposal, prevalidation=report, policy=policy, actions=actions,
        coverage_report=coverage, scope=scope, scope_approval=approval, current_project_lock_id=modeling.project_lock["lock_id"])
    package = build_confirmed_package(project_lock=modeling.project_lock, input_bundle=bundle, scope_approval=approval,
        coverage_report=coverage, field_mappings=modeling.find_artifact(proposal["field_mapping_candidate_set_id"]),
        proposal=proposal, prevalidation=report, review_policy=policy, finalization=final, actions=actions, review_queue=queue, **context)
    modeling.write_review_final(params["review_id"], decision_log=final.decision_log, coverage_report=coverage)
    modeling.write_confirmed(package["package_id"], package)
    return {"confirmed_package": package, "decision_log": final.decision_log}


def execute(app, project, request, principal):
    modeling, params, name = ModelingWorkspaceService(project.root), request.parameters, request.operation_id
    try:
        if name == "modeling.scope":
            dataset = verified_run(modeling.root, params["run_id"]).dataset
            scope = build_scope(project_id=modeling.project["project_id"], project_lock_id=modeling.project_lock["lock_id"],
                domain_pack_lock_ids=[p["pack_lock_id"] for p in modeling.project_lock["resolved_domain_packs"]],
                kg_ir_dataset_ids=[dataset["dataset_id"]], modeling_intent=params.get("intent", "MIXED_MODELING"),
                domain_description=params["description"], target_object_families=params["object_families"],
                in_scope=params["in_scope"], out_of_scope=params.get("out_of_scope", []),
                target_artifacts=["TBOX", "ABOX", "MAPPING", "SHACL", "TERMINOLOGY"], default_namespace=params["namespace"])
            modeling.write_build(scope["scope_id"], {"ontology-scope.json": scope, "ingestion-binding.json": {"run_id": params["run_id"]}})
            return {"scope": scope}
        if name == "modeling.scope.approve":
            scope = modeling.find_artifact(params["scope_id"])
            approval = approve_scope(scope, reviewer_id=principal.principal_id, reviewer_role="Scope Reviewer",
                                     rationale=params["rationale"], decision=params.get("decision", "APPROVE"))
            modeling.update_build(scope["scope_id"], {"scope-approval.json": approval})
            return {"approval": approval}
        if name in PREPARE_OPERATIONS:
            return _prepare(app, modeling, params)
        if name in {"modeling.candidate", "modeling.proposal"}:
            return _propose(modeling, params)
        return _review(modeling, request, principal)
    except ModelingControlError as exc:
        raise ServiceBoundaryError("MODELING_BLOCKED", "modeling authority or review precondition failed", status_code=422) from exc
