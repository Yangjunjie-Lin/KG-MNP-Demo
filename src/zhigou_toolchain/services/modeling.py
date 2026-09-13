"""Application orchestration of the existing modeling/review control plane.

Explicit IDs select each authority. No lexical 'latest', CLI/stdout dispatch,
client reviewer roles, auto-approval, or direct RDF writing is used.
"""
from __future__ import annotations

import re

from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.contracts.document_io import (
    deterministic_json_bytes,
    read_document,
)
from zhigou_toolchain.domain_packs.registry import DomainPackRegistry
from zhigou_toolchain.ingestion.source_store import SourceStore
from zhigou_toolchain.modeling.control_plane.alignment import align_terms
from zhigou_toolchain.modeling.control_plane.baseline import build_baseline_snapshot
from zhigou_toolchain.modeling.control_plane.candidates import (
    normalize_candidate_drafts,
)
from zhigou_toolchain.modeling.control_plane.competency import (
    build_question_set,
    structural_coverage,
)
from zhigou_toolchain.modeling.control_plane.confirmation import build_confirmed_package
from zhigou_toolchain.modeling.control_plane.errors import ModelingControlError
from zhigou_toolchain.modeling.control_plane.input_bundle import (
    build_input_bundle,
    verify_input_bundle,
)
from zhigou_toolchain.modeling.control_plane.mappings import (
    build_field_mapping_candidates,
)
from zhigou_toolchain.modeling.control_plane.prevalidation import prevalidate
from zhigou_toolchain.modeling.control_plane.proposal import build_proposal
from zhigou_toolchain.modeling.control_plane.providers.execution import execute_provider
from zhigou_toolchain.modeling.control_plane.providers.mixed_mapping import (
    input_inventory,
    mixed_mapping_drafts,
)
from zhigou_toolchain.modeling.control_plane.providers.models import (
    build_provider_request,
    build_provider_response,
)
from zhigou_toolchain.modeling.control_plane.providers.record_mapping import (
    record_mapping_drafts,
)
from zhigou_toolchain.modeling.control_plane.providers.record_profile import (
    MixedRecordMapping,
)
from zhigou_toolchain.modeling.control_plane.providers.recorded_model import (
    import_recorded_model_output,
)
from zhigou_toolchain.modeling.control_plane.review.actions import (
    build_review_action,
    rebuild_candidate_revision,
)
from zhigou_toolchain.modeling.control_plane.review.finalization import finalize_review
from zhigou_toolchain.modeling.control_plane.review.policy import build_review_policy
from zhigou_toolchain.modeling.control_plane.review.queue import (
    build_review_queue,
    verify_review_queue,
)
from zhigou_toolchain.modeling.control_plane.review.replay import review_status
from zhigou_toolchain.modeling.control_plane.scope import build_scope
from zhigou_toolchain.modeling.control_plane.scope_approval import (
    approve_scope,
    verify_scope_approval,
)
from zhigou_toolchain.modeling.control_plane.service import ModelingWorkspaceService
from zhigou_toolchain.modeling.control_plane.terminology import (
    build_terminology_catalog,
)
from zhigou_toolchain.modeling.five_stage.agents import invoke
from zhigou_toolchain.plugins.registry import PluginRegistry
from zhigou_toolchain.plugins.snapshot import build_snapshot, verify_snapshot

from .errors import ServiceBoundaryError
from .sources import verified_run

PREPARE_OPERATIONS = {"modeling.prepare", "modeling.cq", "modeling.baseline", "modeling.alignment"}
OPERATIONS = frozenset({"modeling.scope", "modeling.scope.approve", *PREPARE_OPERATIONS,
                        "modeling.session.open", "modeling.session.revise", "source.sample.load",
                        "modeling.profile", "modeling.scope.draft", "modeling.tutorial.seed", "modeling.semantic.check",
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


def _record_rules(packs):
    matches=[]
    for pack in packs:
        identifier=pack.manifest.document["entrypoints"].get("mappings")
        asset=next((a for a in pack.manifest.document["assets"] if a["asset_id"]==identifier),None)
        if asset:
            document=read_document(pack.root/asset["path"])
            if isinstance(document,dict) and document.get("profile") in {"evidence-record-mapping-v1", "evidence-record-mapping-v2"}:matches.append((identifier,document))
    if len(matches)>1:raise ModelingControlError("ambiguous record mapping profiles")
    return matches[0] if matches else None


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
                                review_policy_id=policy["policy_id"], allowed_provider_ids=["baseline-reuse-provider", "rule-mapping-provider","manual-candidate-provider","recorded-model-output-provider"])
    modeling.write_build(bundle["modeling_input_bundle_id"], {
        "competency-question-set.json": question_set, "baseline-snapshot.json": baseline, "terminology-catalog.json": terminology,
        "term-alignment-set.json": alignments, "field-mapping-candidate-set.json": mappings,
        "review-policy.json": policy, "modeling-input-bundle.json": bundle,
    })
    return {"bundle": bundle, "questions": question_set, "baseline": baseline, "terminology": terminology,
            "alignments": alignments, "mappings": mappings, "policy": policy,
            "input_inventory": input_inventory(datasets),
            "record_mapping":(_record_rules(packs) or (None,None))[1]}


def _propose(app,modeling, params):
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
                        "evidence_records": [e for d in datasets for e in d["evidence_records"]],
                        "default_namespace": scope["namespace_policy"]["default_namespace"],
                        "competency_question_ids": [q["question_id"] for q in context["question_set"]["questions"]]}
    registry, responses, snapshots, requests = PluginRegistry(), [], [], []
    invocations=[];invocation_refs={}
    declared=_record_rules(_packs(app,modeling))
    if (params.get("model_assistance") or {}).get("action") == "REPAIR":
        from .modeling_sessions import current, read
        active = read(modeling.root)
        previous = current(active, "modeling.proposal") if active else None
        if not previous or previous["identifier"] != params["model_assistance"].get("parent_proposal_id"):
            raise ServiceBoundaryError("REPAIR_PARENT_STALE", "Repair only the current proposal", status_code=409)
        old_mapping = read_document(modeling.proposal_directory(previous["identifier"]) / "record-mapping-proposal.json")
        declared = (old_mapping["source_asset_id"], old_mapping["mapping"]) if old_mapping["mapping"] else None
        if params.get("record_mapping") is not None or params.get("manual_drafts") is not None:
            raise ServiceBoundaryError("REPAIR_INPUT_IMMUTABLE", "Repair cannot replace parent mappings or draft input", status_code=422)
    if params.get("record_mapping") is not None:
        declared=(None,params["record_mapping"])
    if params.get("manual_drafts") is not None:
        if declared or params["providers"] != ["manual-candidate-provider"]:
            raise ServiceBoundaryError("MANUAL_DRAFT_PROVIDER_CONFLICT", "Explicit manual drafts require only the manual provider and no record mapping", status_code=422)
        provider_context["manual_drafts"] = params["manual_drafts"]
    extraction, record_builder = None, None
    if declared:
        if "manual-candidate-provider" not in params["providers"] or "rule-mapping-provider" in params["providers"]:
            raise ServiceBoundaryError("MAPPING_PROVIDER_CONFLICT", "Explicit mappings require the manual provider and exclude default row identities", status_code=422)
        source_store=SourceStore(modeling.root)
        source_ids={source for data in datasets for source in source_store.load_batch(data["source_batch_id"])["sources"]}
        if declared[1]["profile"] == "evidence-record-mapping-v2":
            declared = (declared[0], MixedRecordMapping.model_validate(declared[1]).model_dump())
        def build_records():
            if declared[1]["profile"] == "evidence-record-mapping-v2":
                drafts, report = mixed_mapping_drafts(rules=declared[1], datasets=datasets,
                    namespace=scope["namespace_policy"]["default_namespace"], baseline=baseline,
                    question_ids=provider_context["competency_question_ids"], asset_id=declared[0])
                return {"drafts": drafts, "report": report}
            drafts = record_mapping_drafts(rules=declared[1], datasets=datasets,
                source_names={identifier: source_store.verify_source(identifier)["original_name"] for identifier in source_ids},
                namespace=scope["namespace_policy"]["default_namespace"], baseline=baseline,
                question_ids=provider_context["competency_question_ids"], asset_id=declared[0])
            return {"drafts": drafts, "report": None}
        record_builder = build_records
        provider_context["planned_record_mapping"] = declared[1]
        if not params.get("model_assistance"):
            mapped = invoke(3, "records.map", record_builder, inputs={"mapping": declared[1], "source_ids": sorted(source_ids)})
            provider_context["manual_drafts"], extraction = mapped["drafts"], mapped["report"]
            record_builder = None
    elif "rule-mapping-provider" in params["providers"] and len([e for e in baseline["elements"] if e["element_kind"] == "CLASS"]) > 1:
        raise ServiceBoundaryError("MAPPING_CLASS_REQUIRED", "Multiple baseline classes require explicit record mappings", status_code=422)
    assistance = None
    if params.get("model_assistance"):
        from .modeling_assistance import assist
        provider_context["manual_drafts"], assistance = assist(app, modeling, bundle, scope, provider_context, params, record_builder=record_builder)
        extraction = assistance.get("record_mapping", extraction)
    for provider in sorted(set(params["providers"])):
        if provider not in bundle["provider_policy"]["allowed_provider_ids"]:
            raise ServiceBoundaryError("PROVIDER_FORBIDDEN", "provider not allowed by input bundle", status_code=403)
        configuration = {"record_mapping": declared[1]} if declared and declared[1]["profile"] == "evidence-record-mapping-v2" and provider == "manual-candidate-provider" else None
        if params.get("manual_drafts") is not None:
            configuration = {"manual_drafts": params["manual_drafts"]}
        if assistance and provider == "manual-candidate-provider":
            configuration = {"model_assistance_digest": semantic_hash(assistance), "drafts": sorted(provider_context["manual_drafts"], key=lambda d: d["draft_ref"])}
        snapshot = build_snapshot(registry.get(provider), configuration=configuration)
        request = build_provider_request(modeling_input_bundle_id=bundle["modeling_input_bundle_id"],
            provider_snapshot_id=snapshot["snapshot_id"], capability={"baseline-reuse-provider": "baseline-reuse", "rule-mapping-provider": "field-mapping-proposal","manual-candidate-provider":"tbox-proposal","recorded-model-output-provider":"tbox-proposal"}[provider],
            scope_id=scope["scope_id"], baseline_snapshot_id=baseline["baseline_snapshot_id"],
            terminology_catalog_id=context["terminology"]["terminology_catalog_id"], term_alignment_set_id=context["alignments"]["term_alignment_set_id"],
            kg_ir_dataset_ids=bundle["kg_ir_dataset_ids"], evidence_record_ids=sorted(evidence_ids), context=provider_context)
        if provider=="recorded-model-output-provider":
            if not all(params.get(field) for field in ["recorded_response_source_id","recorded_prompt_source_id","recorded_model_id","recorded_model_revision"]):
                raise ServiceBoundaryError("RECORDED_INPUTS_REQUIRED","recorded response, prompt and model labels are required",status_code=422)
            store=SourceStore(modeling.root)
            response_source=store.verify_source(params["recorded_response_source_id"])
            prompt_source=store.verify_source(params["recorded_prompt_source_id"])
            request_name="provider-request-"+request.artifact["request_id"].rsplit(":",1)[-1]+".json"
            modeling.update_build(bundle["modeling_input_bundle_id"],{request_name:request.artifact})
            drafts,invocation=import_recorded_model_output(store.blob_for(response_source).read_bytes(),provider_name=provider,
                model_id=params["recorded_model_id"],model_revision=params["recorded_model_revision"],
                request_artifact_ref=(directory/request_name).relative_to(modeling.root).as_posix(),request_bytes=request.artifact_bytes,
                response_artifact_ref=response_source["blob_path"],prompt_template_id=prompt_source["source_id"],prompt_template_sha256=prompt_source["content_sha256"],sampling_parameters={})
            response=build_provider_response(request,candidate_drafts=drafts)
            invocations.append(invocation);invocation_refs[response["response_id"]]=(invocation["invocation_id"],)
        elif assistance and provider == "manual-candidate-provider":
            # Record the actual generated bytes through the existing invocation
            # contract. This records a LIVE result; it does not label inference
            # as human-authored. The separate LIVE receipt retains raw requests.
            recorded_bytes = deterministic_json_bytes({"candidate_drafts": provider_context["manual_drafts"]})
            suffix = semantic_hash(assistance)
            request_name, response_name = f"live-request-{suffix}.json", f"live-drafts-{suffix}.json"
            modeling.update_build(bundle["modeling_input_bundle_id"], {request_name: request.artifact,
                response_name: {"candidate_drafts": provider_context["manual_drafts"]}, f"live-receipt-{suffix}.json": assistance})
            call = assistance["calls"][-1]
            drafts, invocation = import_recorded_model_output(recorded_bytes, provider_name="live-model-recording-adapter",
                model_id=call["model"]["model_id"], model_revision=call["model"]["configured_revision"],
                request_artifact_ref=(directory / request_name).relative_to(modeling.root).as_posix(), request_bytes=request.artifact_bytes,
                response_artifact_ref=(directory / response_name).relative_to(modeling.root).as_posix(),
                prompt_template_id="live-assisted-modeling-v1", prompt_template_sha256=call["prompt_hash"], sampling_parameters={},
                determinism_class="NONDETERMINISTIC")
            response = build_provider_response(request, candidate_drafts=drafts)
            invocations.append(invocation)
            invocation_refs[response["response_id"]] = (invocation["invocation_id"],)
        else:response=execute_provider(registry,provider,request)
        responses.append(response)
        snapshots.append(snapshot)
        requests.append(request.artifact)
    item_ids, baseline_ids = {item["item_id"] for item in items}, {item["element_id"] for item in baseline["elements"]}
    candidates = invoke(3, "facts.normalize", lambda: normalize_candidate_drafts(responses, scope=scope, evidence_ids=evidence_ids,
        kg_ir_item_ids=item_ids, baseline_element_ids=baseline_ids, model_invocation_refs_by_response=invocation_refs), inputs={"responses": responses})
    proposal = build_proposal(project_lock_id=modeling.project_lock["lock_id"], input_bundle=bundle,
        field_mappings=mappings, candidate_set=candidates, provider_snapshot_ids=[s["snapshot_id"] for s in snapshots],model_invocation_ids=[i["invocation_id"] for i in invocations], **context)
    report = invoke(4, "integrity.check", lambda: prevalidate(proposal, current_project_lock_id=modeling.project_lock["lock_id"], evidence_ids=evidence_ids,
        kg_ir_item_ids=item_ids, baseline_element_ids=baseline_ids, provider_snapshot_ids=set(proposal["provider_snapshots"]),
        allowed_namespaces=tuple(scope["namespace_policy"]["allowed_new_namespaces"]), input_bundle=bundle, scope=scope, scope_approval=approval,
        model_invocation_ids={i["invocation_id"] for i in invocations}), inputs={"proposal": proposal["proposal_id"]})
    coverage = structural_coverage(context["question_set"], proposal)
    queue = build_review_queue(proposal, report, policy)
    modeling.write_proposal(proposal["proposal_id"], {"ontology-modeling-proposal.json": proposal,
        **({"live-model-assistance.json": assistance} if assistance else {}),
        **({"manual-draft-proposal.json": {"drafts": params["manual_drafts"], "authority": "PROPOSAL_ONLY"}} if params.get("manual_drafts") is not None else {}),
        "record-mapping-proposal.json":{"mapping":declared[1] if declared else None,"source_asset_id":declared[0] if declared else None},
        "source-extraction-report.json": extraction or {},
        "provider-requests.json": requests, "provider-responses.json": responses, "provider-snapshots.json": snapshots,
        "model-invocation-records.json":invocations,
        "ontology-candidate-set.json": candidates, "formal-prevalidation-report.json": report})
    modeling.write_review(queue["review_queue_id"], {"review-queue.json": queue, "review-policy.json": policy,
        "competency-question-coverage-report.json": coverage})
    return {"proposal": proposal, "prevalidation": report, "queue": queue, "coverage": coverage,
            "extraction": extraction, **({"model_assistance": assistance} if assistance else {})}


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
        candidate_id=params.get("candidate_id");issue_id=params.get("issue_id")
        if bool(candidate_id)==bool(issue_id):raise ServiceBoundaryError("REVIEW_TARGET_INVALID","select exactly one candidate or issue",status_code=422)
        item = next((row for row in queue["items"] if row["candidate_id"] == candidate_id and row["issue_id"]==issue_id), None)
        if item is None:
            raise ServiceBoundaryError("REVIEW_TARGET_INVALID", "candidate not in current review", status_code=422)
        used = {row["reviewer_role"] for row in actions if row["candidate_id"] == candidate_id and row["decision"] == "ACCEPT"}
        roles = [role for role in item["required_roles"] if principal.can("review:role:" + role)]
        if not roles:
            raise ServiceBoundaryError("REVIEW_ROLE_FORBIDDEN", "current identity has no required reviewer role", status_code=403)
        role = next((role for role in roles if role not in used), roles[0])
        modified=None
        if params["decision"]=="MODIFY_AND_ACCEPT":
            if not candidate_id or not params.get("body_edits"):raise ServiceBoundaryError("REVISION_REQUIRED","candidate body edits required",status_code=422)
            original,_=modeling.find_candidate(candidate_id)
            updated_body={**original["body"],**params["body_edits"]}
            if any(original["body"].get(field) and not updated_body.get(field) for field in ["subject_iri","predicate_iri","object_iri","target_iri","source_field"]):
                raise ServiceBoundaryError("REVISION_INVALID","required semantic fields cannot be erased",status_code=422)
            if original["body"]["candidate_type"]=="DATA_PROPERTY_ASSERTION":
                from zhigou_toolchain.modeling.control_plane.prevalidation import (
                    _literal_is_valid,
                )
                if not _literal_is_valid(updated_body["literal"]):raise ServiceBoundaryError("REVISION_INVALID","literal failed formal prevalidation",status_code=422)
            scope=modeling.find_artifact(proposal["scope_id"]);datasets=_datasets(modeling,scope)
            baseline=modeling.find_artifact(proposal["baseline_snapshot_id"])
            candidates=[c for key in ["tbox_candidates","mapping_candidates","abox_candidates","shacl_candidates"] for c in proposal[key]]
            modified=rebuild_candidate_revision(original,{"body":updated_body},scope=scope,
                evidence_ids={e["evidence_id"] for d in datasets for e in d["evidence_records"]},baseline_element_ids={e["element_id"] for e in baseline["elements"]},candidate_ids={c["candidate_id"] for c in candidates})
        elif params.get("body_edits") is not None:raise ServiceBoundaryError("REVISION_DECISION_REQUIRED","edits require MODIFY_AND_ACCEPT",status_code=422)
        action = build_review_action(queue=queue, proposal=proposal, policy=policy, existing_actions=actions,
            decision=params["decision"], reviewer_id=principal.principal_id, reviewer_role=role,
            rationale=params["rationale"], candidate_id=candidate_id,issue_id=issue_id,modified_candidate=modified)
        modeling.append_action(params["review_id"], action)
        status=review_status(queue,[*actions,action])
        return {"action":action,"status":{"complete":status["complete"]}}
    bundle = modeling.find_artifact(proposal["modeling_input_bundle_id"])
    live_path = modeling.proposal_directory(proposal["proposal_id"]) / "live-model-assistance.json"
    if live_path.exists():
        live_receipt = read_document(live_path)
        if live_receipt.get("unresolved") or any(row.get("unresolved") for row in live_receipt.get("extraction", [])):
            raise ServiceBoundaryError("MODEL_UNRESOLVED_REVIEW_REQUIRED", "Resolve model ambiguities in a new proposal before freezing", status_code=409)
    context = _bundle_context(modeling, bundle)
    scope = context["scope"]
    datasets = _datasets(modeling, scope)
    # The mapping digest lives in the core-hashed candidate rationales. A
    # mutable sidecar alone must never authorize identity/exclusion decisions.
    proposed_candidates = [c for key in ["tbox_candidates", "mapping_candidates", "abox_candidates", "shacl_candidates"] for c in proposal[key]]
    bound_digests = {r["rationale"].rsplit("mapping-sha256:", 1)[-1]
                     for c in proposed_candidates for r in c["provider_rationales"] if "mapping-sha256:" in r["rationale"]}
    if bound_digests:
        mapping_record = read_document(modeling.proposal_directory(proposal["proposal_id"]) / "record-mapping-proposal.json")
        rules = MixedRecordMapping.model_validate(mapping_record["mapping"]).model_dump()
        if bound_digests != {semantic_hash(rules)}:
            raise ServiceBoundaryError("MAPPING_INTEGRITY_FAILED", "Mapping no longer matches reviewed candidate provenance", status_code=409)
        snapshots = read_document(modeling.proposal_directory(proposal["proposal_id"]) / "provider-snapshots.json")
        selected_snapshots = [s for s in snapshots if s["plugin_id"] == "manual-candidate-provider"]
        if len(selected_snapshots) != 1 or selected_snapshots[0]["snapshot_id"] not in proposal["provider_snapshots"]:
            raise ServiceBoundaryError("MAPPING_INTEGRITY_FAILED", "Mapping provider snapshot is not bound to this proposal", status_code=409)
        live_path = modeling.proposal_directory(proposal["proposal_id"]) / "live-model-assistance.json"
        if live_path.exists():
            live_receipt = read_document(live_path)
            provider_responses = read_document(modeling.proposal_directory(proposal["proposal_id"]) / "provider-responses.json")
            live_drafts = next(r["candidate_drafts"] for r in provider_responses if r["provider_snapshot_id"] == selected_snapshots[0]["snapshot_id"])
            live_configuration = {"model_assistance_digest": semantic_hash(live_receipt), "drafts": sorted(live_drafts, key=lambda d: d["draft_ref"])}
            verify_snapshot(PluginRegistry().get("manual-candidate-provider"), selected_snapshots[0], configuration=live_configuration)
        else:
            verify_snapshot(PluginRegistry().get("manual-candidate-provider"), selected_snapshots[0], configuration={"record_mapping": rules})
        _, extraction = mixed_mapping_drafts(rules=rules, datasets=datasets,
            namespace=scope["namespace_policy"]["default_namespace"], baseline=context["baseline"],
            question_ids=[q["question_id"] for q in context["question_set"]["questions"]], asset_id=mapping_record["source_asset_id"])
        if extraction["unmapped_item_ids"]:
            raise ServiceBoundaryError("MAPPING_COVERAGE_INCOMPLETE", "Unmapped input items require mapping or explicit reasoned exclusion in a new proposal", status_code=422)
    approval = _approval(modeling, scope)
    coverage = structural_coverage(context["question_set"], proposal)
    final = finalize_review(queue=queue, proposal=proposal, prevalidation=report, policy=policy, actions=actions,
        coverage_report=coverage, scope=scope, scope_approval=approval, current_project_lock_id=modeling.project_lock["lock_id"])
    from .modeling_sessions import require_checks
    require_checks(modeling.root, [*final.accepted_tbox, *final.accepted_mapping, *final.accepted_abox, *final.accepted_shacl], params["review_id"])
    package = build_confirmed_package(project_lock=modeling.project_lock, input_bundle=bundle, scope_approval=approval,
        coverage_report=coverage, field_mappings=modeling.find_artifact(proposal["field_mapping_candidate_set_id"]),
        proposal=proposal, prevalidation=report, review_policy=policy, finalization=final, actions=actions, review_queue=queue, **context)
    modeling.write_review_final(params["review_id"], decision_log=final.decision_log, coverage_report=coverage)
    modeling.write_confirmed(package["package_id"], package)
    return {"confirmed_package": package, "decision_log": final.decision_log}


def execute(app, project, request, principal):
    if request.operation_id in {"modeling.candidate", "modeling.proposal"} and request.parameters.get("model_assistance") and not principal.can("source:read"):
        raise ServiceBoundaryError("SOURCE_READ_REQUIRED", "LIVE modeling requires source-read permission before sending source content to a provider", status_code=403)
    if request.operation_id == "source.sample.load":
        from .sample_batch import execute as execute_sample
        return execute_sample(app, project, request, principal)
    if request.operation_id in {"modeling.session.open", "modeling.session.revise"}:
        from .modeling_sessions import execute as execute_session
        return execute_session(app, project, request, principal)
    if request.operation_id == "modeling.semantic.check":
        from .modeling_semantic import execute as execute_semantic
        return execute_semantic(app, project, request, principal)
    if request.operation_id in {"modeling.profile", "modeling.scope.draft", "modeling.tutorial.seed"}:
        from .modeling_five_stage import execute as execute_five_stage
        return execute_five_stage(app, project, request, principal)
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
            current_path = modeling.build_directory(scope["scope_id"]) / "scope-approval.json"
            current = read_document(current_path) if current_path.exists() else None
            if params.get("expected_approval_id") != (current["approval_id"] if current else None):
                raise ServiceBoundaryError("SCOPE_APPROVAL_CONFLICT", "scope review changed; reload before deciding", status_code=409)
            approval = approve_scope(scope, reviewer_id=principal.principal_id, reviewer_role="Scope Reviewer",
                                     rationale=params["rationale"], decision=params.get("decision", "APPROVE"))
            modeling.write_build(approval["approval_id"], {"scope-approval.json": approval})
            modeling.update_build(scope["scope_id"], {"scope-approval.json": approval})
            return {"approval": approval}
        if name in PREPARE_OPERATIONS:
            return _prepare(app, modeling, params)
        if name in {"modeling.candidate", "modeling.proposal"}:
            result = _propose(app,modeling, params)
            if params.get("model_assistance"):
                from .modeling_assistance import recheck
                result["automatic_validation"] = recheck(app, project, request, principal, result)
            return result
        return _review(modeling, request, principal)
    except ModelingControlError as exc:
        code, separator, message = str(exc).partition(": ")
        if separator and re.fullmatch(r"(?:MAPPING|TEXT_TEMPLATE)_[A-Z_]+", code):
            raise ServiceBoundaryError(code, message, status_code=422) from exc
        raise ServiceBoundaryError("MODELING_BLOCKED", "modeling authority or review precondition failed", status_code=422) from exc
