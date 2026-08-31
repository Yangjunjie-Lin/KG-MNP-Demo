"""Prompt 4 `kg-mnp model` offline control-plane CLI."""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Any

import yaml

from kg_mnp.contracts.document_io import deterministic_json_bytes
from kg_mnp.domain_packs.registry import DomainPackRegistry
from kg_mnp.plugins.conformance import run_conformance
from kg_mnp.plugins.registry import PluginRegistry
from kg_mnp.plugins.snapshot import build_snapshot

from .alignment import align_terms
from .baseline import build_baseline_snapshot, verify_baseline_snapshot
from .candidates import normalize_candidate_drafts
from .competency import build_question_set, structural_coverage, verify_question_set
from .errors import (
    ModelingControlError,
    ModelingProposalError,
    ModelingProviderError,
    PrevalidationError,
    ScopeInvalidError,
    ScopeNotApprovedError,
    StaleModelingArtifactError,
)
from .input_bundle import build_input_bundle, verify_input_bundle
from .limits import ModelingLimits
from .mappings import build_field_mapping_candidates
from .prevalidation import prevalidate, verify_prevalidation
from .proposal import build_proposal, verify_proposal
from .providers.execution import execute_provider
from .providers.models import (
    ImmutableModelingProviderRequest,
    build_provider_request,
    build_provider_response,
)
from .providers.recorded_model import import_recorded_model_output
from .review.policy import build_review_policy
from .run import advance_modeling_run, build_modeling_run
from .scope import build_scope, verify_scope
from .scope_approval import approve_scope, verify_scope_approval
from .service import ModelingWorkspaceService
from .terminology import build_terminology_catalog, verify_terminology_catalog

SUCCESS = 0
SCOPE_INVALID = 17
SCOPE_NOT_APPROVED = 18
COMPETENCY_QUESTION_INVALID = 19
BASELINE_INVALID = 20
MODELING_PROVIDER_INVALID = 21
MODELING_PROPOSAL_INVALID = 22
PREVALIDATION_FAILED = 23
STALE_MODELING_ARTIFACT = 27


def _emit(value: Any, *, error: bool = False) -> None:
    stream = sys.stderr if error else sys.stdout
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True), file=stream)


def _common_flags(argv: list[str] | None) -> tuple[list[str], bool, bool]:
    values = list(argv or [])
    use_json = "--json" in values
    debug = "--debug" in values
    return [value for value in values if value not in {"--json", "--debug"}], use_json, debug


def _read_mapping(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    value = yaml.safe_load(raw) if path.suffix.casefold() in {".yaml", ".yml"} else json.loads(raw)
    if not isinstance(value, dict):
        raise ModelingControlError("input document root must be an object")
    return value


def _registry_roots(service: ModelingWorkspaceService) -> list[Path]:
    registry = DomainPackRegistry()
    return [
        registry.resolve(item["pack_id"], item["pack_version"]).root
        for item in service.project_lock["resolved_domain_packs"]
    ]


def _scope_run(service: ModelingWorkspaceService) -> tuple[dict[str, Any], str]:
    scope = service.latest_artifact("KG_MNP_ONTOLOGY_SCOPE")
    return scope, scope["scope_id"]


def _dataset_closure(datasets: list[dict[str, Any]]) -> tuple[set[str], set[str]]:
    evidence = {
        record["evidence_id"] for dataset in datasets for record in dataset["evidence_records"]
    }
    items = {item["item_id"] for dataset in datasets for item in dataset["items"]}
    return evidence, items


def _domain_questions(pack_id: str, service: ModelingWorkspaceService) -> list[dict[str, Any]]:
    registry = DomainPackRegistry()
    match = next(
        item
        for item in service.project_lock["resolved_domain_packs"]
        if item["pack_id"] == pack_id
    )
    resolved = registry.resolve(pack_id, match["pack_version"])
    manifest = resolved.manifest.document
    asset_id = manifest["entrypoints"]["competency-questions"]
    asset = next(item for item in manifest["assets"] if item["asset_id"] == asset_id)
    source = yaml.safe_load((resolved.root / asset["path"]).read_text(encoding="utf-8"))
    rows = source.get("questions") or source.get("competency_questions") or []
    return [
        {
            "question_text": row.get("question") or row.get("question_text"),
            "purpose": row.get("purpose") or row.get("description") or "structural retrieval and traceability",
            "priority": row.get("priority", "MEDIUM"),
            "expected_answer_shape": row.get("expected_answer_shape", "ENTITY_LIST"),
            "required_concepts": row.get("required_concepts", []),
            "required_relations": row.get("required_relations", []),
            "required_constraints": row.get("required_constraints", []),
            "evidence_refs": row.get("evidence_refs", []),
            "source_domain_asset_refs": [asset_id],
            "validation_intent": row.get("validation_intent", "RETRIEVAL"),
            "status": "APPROVED",
        }
        for row in rows
    ]


def _domain_terms(service: ModelingWorkspaceService) -> list[dict[str, Any]]:
    registry = DomainPackRegistry()
    result: list[dict[str, Any]] = []
    for lock in service.project_lock["resolved_domain_packs"]:
        resolved = registry.resolve(lock["pack_id"], lock["pack_version"])
        manifest = resolved.manifest.document
        asset_id = manifest.get("entrypoints", {}).get("terminology")
        if not asset_id:
            continue
        asset = next(item for item in manifest["assets"] if item["asset_id"] == asset_id)
        source = yaml.safe_load((resolved.root / asset["path"]).read_text(encoding="utf-8"))
        rows = source.get("terms") or source.get("entries") or []
        for row in rows:
            labels = row.get("preferred_labels", {})
            lexical = row.get("label") or row.get("lexical_form")
            if lexical is None and isinstance(labels, dict):
                lexical = labels.get(row.get("language")) or labels.get("en") or next(
                    iter(labels.values()), None
                )
            if not lexical:
                continue
            iri_value = row.get("iri") or row.get("term_iri")
            result.append(
                {
                    "lexical_form": lexical,
                    "language": row.get("language"),
                    "source_ref": asset_id,
                    "candidate_iris": [iri_value] if iri_value else [],
                    "definition": row.get("definition"),
                    "aliases": row.get("aliases", []),
                }
            )
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kg-mnp model")
    commands = parser.add_subparsers(dest="command", required=True)

    scope = commands.add_parser("scope")
    scope_commands = scope.add_subparsers(dest="operation", required=True)
    scope_init = scope_commands.add_parser("init")
    scope_init.add_argument("workspace", type=Path)
    scope_init.add_argument("--dataset", required=True)
    for operation in ("validate", "inspect", "status"):
        command = scope_commands.add_parser(operation)
        command.add_argument("workspace", type=Path)
        command.add_argument("scope_id")
    scope_approve = scope_commands.add_parser("approve")
    scope_approve.add_argument("workspace", type=Path)
    scope_approve.add_argument("scope_id")
    scope_approve.add_argument("--reviewer-id", required=True)
    scope_approve.add_argument("--reviewer-role", required=True)
    scope_approve.add_argument("--rationale", required=True)

    cq = commands.add_parser("cq")
    cq_commands = cq.add_subparsers(dest="operation", required=True)
    cq_import = cq_commands.add_parser("import")
    cq_import.add_argument("workspace", type=Path)
    cq_import.add_argument("--domain-pack", required=True)
    cq_add = cq_commands.add_parser("add")
    cq_add.add_argument("workspace", type=Path)
    cq_add.add_argument("--file", required=True, type=Path)
    for operation in ("validate", "inspect"):
        command = cq_commands.add_parser(operation)
        command.add_argument("workspace", type=Path)
        command.add_argument("question_set_id")
    cq_coverage = cq_commands.add_parser("coverage")
    cq_coverage.add_argument("workspace", type=Path)
    cq_coverage.add_argument("artifact_id")

    baseline = commands.add_parser("baseline")
    baseline_commands = baseline.add_subparsers(dest="operation", required=True)
    baseline_snapshot = baseline_commands.add_parser("snapshot")
    baseline_snapshot.add_argument("workspace", type=Path)
    for operation in ("validate", "inspect"):
        command = baseline_commands.add_parser(operation)
        command.add_argument("workspace", type=Path)
        command.add_argument("snapshot_id")

    terminology = commands.add_parser("terminology")
    terminology_commands = terminology.add_subparsers(dest="operation", required=True)
    terminology_build = terminology_commands.add_parser("build")
    terminology_build.add_argument("workspace", type=Path)
    terminology_build.add_argument("--dataset", required=True)
    terminology_build.add_argument("--baseline", required=True)
    terminology_inspect = terminology_commands.add_parser("inspect")
    terminology_inspect.add_argument("workspace", type=Path)
    terminology_inspect.add_argument("catalog_id")
    terminology_align = terminology_commands.add_parser("align")
    terminology_align.add_argument("workspace", type=Path)
    terminology_align.add_argument("catalog_id")
    terminology_align.add_argument("--baseline", required=True)

    provider = commands.add_parser("provider")
    provider_commands = provider.add_subparsers(dest="operation", required=True)
    provider_commands.add_parser("list")
    for operation in ("inspect", "conformance"):
        command = provider_commands.add_parser(operation)
        command.add_argument("provider_id")

    request = commands.add_parser("provider-request")
    request_commands = request.add_subparsers(dest="operation", required=True)
    request_export = request_commands.add_parser("export")
    request_export.add_argument("workspace", type=Path)
    request_export.add_argument("--input-bundle", required=True)
    request_export.add_argument("--capability", required=True)
    request_export.add_argument("--output", type=Path)

    response = commands.add_parser("provider-response")
    response_commands = response.add_subparsers(dest="operation", required=True)
    response_import = response_commands.add_parser("import")
    response_import.add_argument("workspace", type=Path)
    response_import.add_argument("response_file", type=Path)
    response_import.add_argument("--provider", required=True)

    input_command = commands.add_parser("input")
    input_commands = input_command.add_subparsers(dest="operation", required=True)
    input_build = input_commands.add_parser("build")
    input_build.add_argument("workspace", type=Path)
    input_build.add_argument("--scope", required=True)
    input_build.add_argument("--dataset", required=True)
    input_build.add_argument("--baseline", required=True)
    input_build.add_argument("--terminology", required=True)

    propose = commands.add_parser("propose")
    propose.add_argument("workspace", type=Path)
    propose.add_argument("--input-bundle", required=True)
    propose.add_argument("--provider", action="append", required=True)

    prevalidation = commands.add_parser("prevalidate")
    prevalidation.add_argument("workspace", type=Path)
    prevalidation.add_argument("proposal_id")
    for name in ("inspect", "status"):
        command = commands.add_parser(name)
        command.add_argument("workspace", type=Path)
        command.add_argument("proposal_id")
    trace = commands.add_parser("trace")
    trace.add_argument("workspace", type=Path)
    trace.add_argument("candidate_id")
    return parser


def _provider_payload(descriptor: Any) -> dict[str, Any]:
    return {
        "plugin_id": descriptor.plugin_id,
        "plugin_api_version": descriptor.manifest["plugin_api_version"],
        "capabilities": descriptor.manifest["capabilities"],
        "authority_level": descriptor.manifest.get("authority_level"),
        "network_policy": descriptor.manifest.get("network_policy"),
        "determinism": descriptor.manifest["determinism"],
        "side_effects": descriptor.manifest["side_effects"],
        "enabled": descriptor.enabled,
        "builtin": descriptor.builtin,
    }


def _dispatch_scope(args: argparse.Namespace) -> Any:
    service = ModelingWorkspaceService(args.workspace)
    if args.operation == "init":
        dataset = service.find_artifact(args.dataset)
        lock_ids = [item["pack_lock_id"] for item in service.project_lock["resolved_domain_packs"]]
        scope = build_scope(
            project_id=service.project["project_id"],
            project_lock_id=service.project_lock["lock_id"],
            domain_pack_lock_ids=lock_ids,
            kg_ir_dataset_ids=[dataset["dataset_id"]],
            modeling_intent="MIXED_MODELING",
            domain_description="Evidence-grounded, non-production ontology modeling scope.",
            target_object_families=["Entity"],
            in_scope=["evidence-bound entity labels and mappings"],
            out_of_scope=["authoritative RDF publication", "GraphDB writes"],
            target_artifacts=["TBOX", "MAPPING", "ABOX", "SHACL", "TERMINOLOGY"],
            default_namespace=f"urn:kg-mnp:project:{service.project['project_id']}:",
        )
        service.write_build(scope["scope_id"], {"ontology-scope.json": scope})
        return scope
    scope = service.find_artifact(args.scope_id)
    if args.operation == "approve":
        approval = approve_scope(
            scope,
            reviewer_id=args.reviewer_id,
            reviewer_role=args.reviewer_role,
            rationale=args.rationale,
        )
        service.update_build(scope["scope_id"], {"scope-approval.json": approval})
        return approval
    verify_scope(scope, project_lock_id=service.project_lock["lock_id"])
    if args.operation == "status":
        try:
            approval = service.latest_artifact("KG_MNP_ONTOLOGY_SCOPE_APPROVAL")
            verify_scope_approval(scope, approval)
            return {"scope_id": scope["scope_id"], "status": "APPROVED", "approval_id": approval["approval_id"]}
        except ModelingControlError:
            return {"scope_id": scope["scope_id"], "status": "NOT_APPROVED"}
    return scope if args.operation == "inspect" else {"scope_id": scope["scope_id"], "valid": True}


def _dispatch_cq(args: argparse.Namespace) -> Any:
    service = ModelingWorkspaceService(args.workspace)
    if args.operation in {"import", "add"}:
        scope, run_id = _scope_run(service)
        if args.operation == "import":
            questions = _domain_questions(args.domain_pack, service)
        else:
            value = _read_mapping(args.file)
            questions = value.get("questions", [])
        question_set = build_question_set(
            project_lock_id=service.project_lock["lock_id"],
            scope_id=scope["scope_id"],
            questions=questions,
        )
        service.update_build(run_id, {"competency-question-set.json": question_set})
        return question_set
    artifact = service.find_artifact(
        args.question_set_id if args.operation != "coverage" else args.artifact_id
    )
    if args.operation == "coverage":
        question_set = service.latest_artifact("KG_MNP_COMPETENCY_QUESTION_SET")
        if artifact.get("manifest_kind") == "KG_MNP_ONTOLOGY_CONFIRMED_MODELING_PACKAGE":
            artifact = service.find_artifact(artifact["source_proposal_id"])
        if artifact.get("manifest_kind") != "KG_MNP_ONTOLOGY_MODELING_PROPOSAL":
            raise ModelingControlError(
                "CQ coverage target must be a Modeling Proposal or Confirmed Modeling Package"
            )
        report = structural_coverage(question_set, artifact)
        return report
    verify_question_set(artifact)
    return artifact if args.operation == "inspect" else {"question_set_id": artifact["question_set_id"], "valid": True}


def _dispatch_baseline(args: argparse.Namespace) -> Any:
    service = ModelingWorkspaceService(args.workspace)
    if args.operation == "snapshot":
        _scope, run_id = _scope_run(service)
        baseline = build_baseline_snapshot(
            project_lock_id=service.project_lock["lock_id"],
            pack_roots=_registry_roots(service),
        )
        service.update_build(run_id, {"baseline-snapshot.json": baseline})
        return baseline
    baseline = service.find_artifact(args.snapshot_id)
    verify_baseline_snapshot(baseline)
    return baseline if args.operation == "inspect" else {"baseline_snapshot_id": baseline["baseline_snapshot_id"], "valid": True}


def _dispatch_terminology(args: argparse.Namespace) -> Any:
    service = ModelingWorkspaceService(args.workspace)
    if args.operation == "build":
        scope, run_id = _scope_run(service)
        dataset = service.find_artifact(args.dataset)
        baseline = service.find_artifact(args.baseline)
        terminology = build_terminology_catalog(
            scope=scope,
            baseline=baseline,
            kg_ir_datasets=[dataset],
            domain_terms=_domain_terms(service),
        )
        service.update_build(run_id, {"terminology-catalog.json": terminology})
        return terminology
    if args.operation == "align":
        terminology = service.find_artifact(args.catalog_id)
        baseline = service.find_artifact(args.baseline)
        alignments = align_terms(terminology, baseline)
        scope, run_id = _scope_run(service)
        service.update_build(run_id, {"term-alignment-set.json": alignments})
        return alignments
    terminology = service.find_artifact(args.catalog_id)
    verify_terminology_catalog(terminology)
    return terminology


def _dispatch_provider(args: argparse.Namespace) -> Any:
    registry = PluginRegistry()
    if args.operation == "list":
        return [
            _provider_payload(item)
            for item in registry.list()
            if "modeling-provider" in item.manifest["plugin_kinds"]
        ]
    descriptor = registry.get(args.provider_id)
    if args.operation == "inspect":
        return _provider_payload(descriptor)
    result = run_conformance(registry, args.provider_id)
    if result.status != "PASS":
        raise ModelingProviderError("; ".join(result.errors))
    return {
        "provider_id": result.plugin_id,
        "status": result.status,
        "checks": [{"check": name, "status": status} for name, status in result.checks],
    }


def _request_context(service: ModelingWorkspaceService) -> dict[str, Any]:
    baseline = service.latest_artifact("KG_MNP_ONTOLOGY_BASELINE_SNAPSHOT")
    alignments = service.latest_artifact("KG_MNP_TERM_ALIGNMENT_SET")
    mappings = service.latest_artifact("KG_MNP_FIELD_MAPPING_CANDIDATE_SET")
    bundle = service.latest_artifact("KG_MNP_MODELING_INPUT_BUNDLE")
    datasets = [service.find_artifact(value) for value in bundle["kg_ir_dataset_ids"]]
    return {
        "baseline_elements": baseline["elements"],
        "alignments": alignments["alignments"],
        "field_mappings": mappings["mappings"],
        "kg_ir_items": [item for dataset in datasets for item in dataset["items"]],
        "default_namespace": service.latest_artifact("KG_MNP_ONTOLOGY_SCOPE")[
            "namespace_policy"
        ]["default_namespace"],
        "competency_question_ids": [
            item["question_id"]
            for item in service.latest_artifact(
                "KG_MNP_COMPETENCY_QUESTION_SET"
            )["questions"]
        ],
    }


def _new_request(
    service: ModelingWorkspaceService,
    bundle: dict[str, Any],
    provider_id: str,
    capability: str,
) -> tuple[ImmutableModelingProviderRequest, dict[str, Any]]:
    registry = PluginRegistry()
    snapshot = build_snapshot(registry.get(provider_id))
    request = build_provider_request(
        modeling_input_bundle_id=bundle["modeling_input_bundle_id"],
        provider_snapshot_id=snapshot["snapshot_id"],
        capability=capability,
        scope_id=bundle["approved_scope_id"],
        baseline_snapshot_id=bundle["baseline_snapshot_id"],
        terminology_catalog_id=bundle["terminology_catalog_id"],
        term_alignment_set_id=bundle["term_alignment_set_id"],
        kg_ir_dataset_ids=bundle["kg_ir_dataset_ids"],
        evidence_record_ids=bundle["evidence_record_ids"],
        context=_request_context(service),
    )
    return request, snapshot


def _dispatch_provider_artifacts(args: argparse.Namespace) -> Any:
    service = ModelingWorkspaceService(args.workspace)
    _scope, run_id = _scope_run(service)
    if args.command == "provider-request":
        bundle = service.find_artifact(args.input_bundle)
        request, snapshot = _new_request(
            service, bundle, "recorded-model-output-provider", args.capability
        )
        artifact = request.artifact
        service.update_build(
            run_id,
            {
                "modeling-provider-request.json": artifact,
                "recorded-provider-snapshot.json": snapshot,
            },
        )
        if args.output:
            args.output.write_bytes(deterministic_json_bytes(artifact))
        return artifact
    if args.provider != "recorded-model-output-provider":
        raise ModelingProviderError("only recorded-model-output-provider accepts imports")
    request_artifact = service.latest_artifact("KG_MNP_MODELING_PROVIDER_REQUEST")
    request = ImmutableModelingProviderRequest(
        artifact_bytes=deterministic_json_bytes(request_artifact),
        context_bytes=b"{}",
    )
    raw = args.response_file.read_bytes()
    drafts, invocation = import_recorded_model_output(
        raw,
        provider_name="recorded-model-output-provider",
        model_id="recorded-external-model",
        model_revision="recorded-bytes",
        request_artifact_ref="modeling-provider-request.json",
        request_bytes=request.artifact_bytes,
        response_artifact_ref="recorded-provider-response.json",
        prompt_template_id="kg-mnp-recorded-provider-v1",
        prompt_template_sha256="0" * 64,
        sampling_parameters={},
    )
    response = build_provider_response(request, candidate_drafts=drafts)
    service.update_build(
        run_id,
        {
            "recorded-provider-response.json": response,
            "model-invocation-record.json": invocation,
        },
    )
    return {"provider_response": response, "model_invocation_record": invocation}


def _dispatch_input(args: argparse.Namespace) -> Any:
    service = ModelingWorkspaceService(args.workspace)
    scope = service.find_artifact(args.scope)
    approval = service.latest_artifact("KG_MNP_ONTOLOGY_SCOPE_APPROVAL")
    question_set = service.latest_artifact("KG_MNP_COMPETENCY_QUESTION_SET")
    baseline = service.find_artifact(args.baseline)
    terminology = service.find_artifact(args.terminology)
    alignments = service.latest_artifact("KG_MNP_TERM_ALIGNMENT_SET")
    dataset = service.find_artifact(args.dataset)
    field_mappings = build_field_mapping_candidates(
        kg_ir_datasets=[dataset],
        alignments=alignments,
        terminology=terminology,
        baseline=baseline,
    )
    policy = build_review_policy(
        project_lock_id=service.project_lock["lock_id"],
        profile="DEVELOPMENT_SINGLE_REVIEWER",
    )
    bundle = build_input_bundle(
        project_lock=service.project_lock,
        scope=scope,
        approval=approval,
        question_set=question_set,
        baseline=baseline,
        terminology=terminology,
        alignments=alignments,
        kg_ir_datasets=[dataset],
        review_policy_id=policy["policy_id"],
        allowed_provider_ids=[
            "manual-candidate-provider",
            "baseline-reuse-provider",
            "rule-mapping-provider",
            "recorded-model-output-provider",
        ],
    )
    modeling_run = build_modeling_run(
        project_lock_id=service.project_lock["lock_id"],
        modeling_input_bundle_id=bundle["modeling_input_bundle_id"],
        limits=ModelingLimits(),
    )
    service.update_build(
        scope["scope_id"],
        {
            "field-mapping-candidate-set.json": field_mappings,
            "modeling-input-bundle.json": bundle,
            "review-policy.json": policy,
            "modeling-run.json": modeling_run,
        },
    )
    return bundle


def _dispatch_propose(args: argparse.Namespace) -> Any:
    service = ModelingWorkspaceService(args.workspace)
    bundle = service.find_artifact(args.input_bundle)
    verify_input_bundle(bundle)
    scope = service.find_artifact(bundle["approved_scope_id"])
    question_set = service.find_artifact(bundle["competency_question_set_id"])
    baseline = service.find_artifact(bundle["baseline_snapshot_id"])
    terminology = service.find_artifact(bundle["terminology_catalog_id"])
    alignments = service.find_artifact(bundle["term_alignment_set_id"])
    field_mappings = service.latest_artifact("KG_MNP_FIELD_MAPPING_CANDIDATE_SET")
    datasets = [service.find_artifact(value) for value in bundle["kg_ir_dataset_ids"]]
    evidence_ids, kg_ir_item_ids = _dataset_closure(datasets)
    baseline_ids = {item["element_id"] for item in baseline["elements"]}
    registry = PluginRegistry()
    responses: list[dict[str, Any]] = []
    snapshots: list[dict[str, Any]] = []
    invocation_records: list[dict[str, Any]] = []
    invocation_map: dict[str, tuple[str, ...]] = {}
    capability_by_provider = {
        "baseline-reuse-provider": "baseline-reuse",
        "rule-mapping-provider": "field-mapping-proposal",
        "manual-candidate-provider": "tbox-proposal",
        "recorded-model-output-provider": "tbox-proposal",
    }
    for provider_id in args.provider:
        if provider_id not in bundle["provider_policy"]["allowed_provider_ids"]:
            raise ModelingProviderError("provider is not authorized by Modeling Input Bundle")
        if provider_id == "recorded-model-output-provider":
            response = service.latest_artifact("KG_MNP_MODELING_PROVIDER_RESPONSE")
            invocation = service.latest_artifact("KG_MNP_MODEL_INVOCATION_RECORD")
            snapshot = build_snapshot(registry.get(provider_id))
            invocation_records.append(invocation)
            invocation_map[response["response_id"]] = (invocation["invocation_id"],)
        else:
            request, snapshot = _new_request(
                service, bundle, provider_id, capability_by_provider[provider_id]
            )
            response = execute_provider(registry, provider_id, request)
        responses.append(response)
        snapshots.append(snapshot)
    candidate_set = normalize_candidate_drafts(
        responses,
        scope=scope,
        evidence_ids=evidence_ids,
        kg_ir_item_ids=kg_ir_item_ids,
        baseline_element_ids=baseline_ids,
        model_invocation_refs_by_response=invocation_map,
    )
    proposal = build_proposal(
        project_lock_id=service.project_lock["lock_id"],
        input_bundle=bundle,
        scope=scope,
        question_set=question_set,
        baseline=baseline,
        terminology=terminology,
        alignments=alignments,
        field_mappings=field_mappings,
        candidate_set=candidate_set,
        provider_snapshot_ids=[item["snapshot_id"] for item in snapshots],
        model_invocation_ids=[item["invocation_id"] for item in invocation_records],
    )
    service.write_proposal(
        proposal["proposal_id"],
        {
            "ontology-modeling-proposal.json": proposal,
            "provider-responses.json": responses,
            "provider-snapshots.json": snapshots,
            "model-invocation-records.json": invocation_records,
        },
    )
    run = service.latest_artifact("KG_MNP_ONTOLOGY_MODELING_RUN")
    service.update_modeling_run(
        advance_modeling_run(
            run,
            status="PROPOSED",
            proposal_id=proposal["proposal_id"],
        )
    )
    return proposal


def _dispatch_prevalidate(args: argparse.Namespace) -> Any:
    service = ModelingWorkspaceService(args.workspace)
    proposal = service.find_artifact(args.proposal_id)
    scope = service.find_artifact(proposal["scope_id"])
    baseline = service.find_artifact(proposal["baseline_snapshot_id"])
    bundle = service.find_artifact(proposal["modeling_input_bundle_id"])
    datasets = [service.find_artifact(value) for value in bundle["kg_ir_dataset_ids"]]
    evidence_ids, kg_ir_item_ids = _dataset_closure(datasets)
    report = prevalidate(
        proposal,
        current_project_lock_id=service.project_lock["lock_id"],
        evidence_ids=evidence_ids,
        kg_ir_item_ids=kg_ir_item_ids,
        baseline_element_ids={item["element_id"] for item in baseline["elements"]},
        provider_snapshot_ids=set(proposal["provider_snapshots"]),
        model_invocation_ids=set(proposal["model_invocation_records"]),
        allowed_namespaces=tuple(scope["namespace_policy"]["allowed_new_namespaces"]),
        input_bundle=bundle,
        scope=scope,
        scope_approval=service.latest_artifact("KG_MNP_ONTOLOGY_SCOPE_APPROVAL"),
    )
    service.update_proposal(
        proposal["proposal_id"], {"formal-prevalidation-report.json": report}
    )
    run = service.latest_artifact("KG_MNP_ONTOLOGY_MODELING_RUN")
    service.update_modeling_run(advance_modeling_run(run, status="PREVALIDATED"))
    if report["status"] == "FAIL":
        raise PrevalidationError(json.dumps(report, sort_keys=True))
    return report


def _dispatch_inspect(args: argparse.Namespace) -> Any:
    service = ModelingWorkspaceService(args.workspace)
    proposal = service.find_artifact(args.proposal_id)
    verify_proposal(proposal)
    if args.command == "inspect":
        return proposal
    try:
        report = service.latest_artifact("KG_MNP_FORMAL_PREVALIDATION_REPORT")
        verify_prevalidation(report, proposal=proposal)
        status = report["status"]
    except ModelingControlError:
        status = "NOT_PREVALIDATED"
    return {"proposal_id": proposal["proposal_id"], "status": status}


def _dispatch(args: argparse.Namespace) -> Any:
    if args.command == "scope":
        return _dispatch_scope(args)
    if args.command == "cq":
        return _dispatch_cq(args)
    if args.command == "baseline":
        return _dispatch_baseline(args)
    if args.command == "terminology":
        return _dispatch_terminology(args)
    if args.command == "provider":
        return _dispatch_provider(args)
    if args.command in {"provider-request", "provider-response"}:
        return _dispatch_provider_artifacts(args)
    if args.command == "input":
        return _dispatch_input(args)
    if args.command == "propose":
        return _dispatch_propose(args)
    if args.command == "prevalidate":
        return _dispatch_prevalidate(args)
    if args.command in {"inspect", "status"}:
        return _dispatch_inspect(args)
    if args.command == "trace":
        return ModelingWorkspaceService(args.workspace).trace_candidate(args.candidate_id)
    raise ModelingControlError("unknown model command")


def _error_code(exc: BaseException) -> int:
    if isinstance(exc, ScopeNotApprovedError):
        return SCOPE_NOT_APPROVED
    if isinstance(exc, ScopeInvalidError):
        return SCOPE_INVALID
    if isinstance(exc, ModelingProviderError):
        return MODELING_PROVIDER_INVALID
    if isinstance(exc, PrevalidationError):
        return PREVALIDATION_FAILED
    if isinstance(exc, StaleModelingArtifactError):
        return STALE_MODELING_ARTIFACT
    if isinstance(exc, ModelingProposalError):
        return MODELING_PROPOSAL_INVALID
    return MODELING_PROPOSAL_INVALID


def main(argv: list[str] | None = None) -> int:
    values, _use_json, debug = _common_flags(argv)
    args = _parser().parse_args(values)
    try:
        _emit(_dispatch(args))
        return SUCCESS
    except (
        KeyError,
        OSError,
        TypeError,
        ValueError,
        ModelingControlError,
    ) as exc:
        if debug:
            traceback.print_exc()
        else:
            _emit({"error": type(exc).__name__, "message": str(exc)}, error=True)
        return _error_code(exc)
