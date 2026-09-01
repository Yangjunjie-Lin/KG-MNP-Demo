"""Build the read-only MNP Prompt 4→5 compatibility fixture."""

from __future__ import annotations

import hashlib
from pathlib import Path

from kg_mnp.contracts.document_io import atomic_write_json
from kg_mnp.ingestion.executor import execute_ingestion_plan
from kg_mnp.ingestion.planner import create_ingestion_plan
from kg_mnp.ingestion.source_store import SourceStore
from kg_mnp.modeling.control_plane.alignment import align_terms
from kg_mnp.modeling.control_plane.baseline import build_baseline_snapshot
from kg_mnp.modeling.control_plane.candidates import normalize_candidate_drafts
from kg_mnp.modeling.control_plane.competency import (
    build_question_set,
    structural_coverage,
)
from kg_mnp.modeling.control_plane.confirmation import build_confirmed_package
from kg_mnp.modeling.control_plane.input_bundle import build_input_bundle
from kg_mnp.modeling.control_plane.mappings import build_field_mapping_candidates
from kg_mnp.modeling.control_plane.prevalidation import prevalidate
from kg_mnp.modeling.control_plane.proposal import build_proposal
from kg_mnp.modeling.control_plane.providers.execution import execute_provider
from kg_mnp.modeling.control_plane.providers.models import (
    build_provider_request,
    candidate_body,
    candidate_draft,
)
from kg_mnp.modeling.control_plane.review.actions import build_review_action
from kg_mnp.modeling.control_plane.review.finalization import finalize_review
from kg_mnp.modeling.control_plane.review.policy import build_review_policy
from kg_mnp.modeling.control_plane.review.queue import build_review_queue
from kg_mnp.modeling.control_plane.scope import build_scope
from kg_mnp.modeling.control_plane.scope_approval import approve_scope
from kg_mnp.modeling.control_plane.terminology import build_terminology_catalog
from kg_mnp.plugins.registry import PluginRegistry
from kg_mnp.plugins.snapshot import build_snapshot
from kg_mnp.semantic_kernel.baseline import load_baseline_closure
from kg_mnp.semantic_kernel.compiler import SemanticCompiler
from kg_mnp.semantic_kernel.snapshot import ROBOT_SHA256
from kg_mnp.semantic_kernel.validators.competency_questions import build_cq_test_plan
from kg_mnp.workspace.service import initialize_workspace

ROOT = Path(__file__).resolve().parents[1]


def build_mnp_prompt05(root: Path) -> dict:
    pack_root = ROOT / "domain_packs" / "mnp"
    lock_path = pack_root / "pack.lock.json"
    lock_before = lock_path.read_bytes()
    opened = initialize_workspace(
        root / "workspace",
        project_id="prompt05-mnp-compatibility",
        project_version="0.5.0",
        display_name="Prompt 5 MNP Compatibility",
        domain_pack="mnp",
        domain_pack_version="1.0.0",
        domain_packs_root=ROOT / "domain_packs",
    )
    store = SourceStore(opened.root)
    source = store.add_file(ROOT / "examples/ingestion/minimal-project/sample.csv").source
    batch = store.create_batch([source["source_id"]])
    ingestion_plan = create_ingestion_plan(opened.root, batch_id=batch["batch_id"])
    dataset = execute_ingestion_plan(opened.root, ingestion_plan.plan["plan_id"]).dataset
    project_lock = opened.lock.document
    scope = build_scope(
        project_id=opened.manifest.project_id,
        project_lock_id=project_lock["lock_id"],
        domain_pack_lock_ids=[item["pack_lock_id"] for item in project_lock["resolved_domain_packs"]],
        kg_ir_dataset_ids=[dataset["dataset_id"]],
        modeling_intent="ALIGN_TO_BASELINE",
        domain_description="Read-only MNP semantic-kernel compatibility over non-sensitive test KG-IR.",
        target_object_families=["Subscriber"],
        in_scope=["locked baseline class reuse"],
        out_of_scope=["MNP mutation", "production eligibility validation", "publication"],
        target_artifacts=["TBOX", "TERMINOLOGY"],
        default_namespace="urn:kg-mnp:project:prompt05-mnp-compatibility:",
    )
    approval = approve_scope(
        scope,
        reviewer_id="mnp-compatibility-reviewer",
        reviewer_role="Development Reviewer",
        rationale="explicit read-only compatibility fixture approval",
    )
    questions = build_question_set(
        project_lock_id=project_lock["lock_id"],
        scope_id=scope["scope_id"],
        questions=[
            {
                "question_text": "Which MNP eligibility cases appear in this empty compatibility data graph?",
                "purpose": "compatibility-only execution of an existing locked query asset",
                "expected_answer_shape": "ENTITY_LIST",
                "required_concepts": ["Subscriber"],
            }
        ],
    )
    question_id = questions["questions"][0]["question_id"]
    baseline = build_baseline_snapshot(project_lock_id=project_lock["lock_id"], pack_roots=[pack_root])
    class_element = next(item for item in baseline["elements"] if item["element_kind"] == "CLASS")
    terminology = build_terminology_catalog(
        scope=scope,
        baseline=baseline,
        kg_ir_datasets=[dataset],
        domain_terms=[
            {
                "lexical_form": "Subscriber",
                "language": "en",
                "source_ref": "mnp-terminology-terminology-profile-1-0-0",
                "candidate_iris": [class_element["iri"]],
            }
        ],
    )
    alignments = align_terms(terminology, baseline)
    mappings = build_field_mapping_candidates(
        kg_ir_datasets=[dataset],
        alignments=alignments,
        terminology=terminology,
        baseline=baseline,
    )
    review_policy = build_review_policy(
        project_lock_id=project_lock["lock_id"],
        profile="DEVELOPMENT_SINGLE_REVIEWER",
    )
    bundle = build_input_bundle(
        project_lock=project_lock,
        scope=scope,
        approval=approval,
        question_set=questions,
        baseline=baseline,
        terminology=terminology,
        alignments=alignments,
        kg_ir_datasets=[dataset],
        review_policy_id=review_policy["policy_id"],
        allowed_provider_ids=["manual-candidate-provider"],
    )
    draft = candidate_draft(
        draft_ref="mnp-baseline-reuse",
        draft_kind="TBOX",
        candidate_action="REUSE_EXISTING",
        body=candidate_body(
            candidate_type="CLASS",
            target_iri=class_element["iri"],
            label=class_element["labels"][0]["value"] if class_element["labels"] else None,
        ),
        rationale="explicit read-only reuse of a locked MNP class",
        kg_ir_item_refs=[dataset["items"][0]["item_id"]],
        evidence_refs=[bundle["evidence_record_ids"][0]],
        domain_asset_refs=[class_element["source_asset_id"]],
        competency_question_refs=[question_id],
        baseline_element_refs=[class_element["element_id"]],
    )
    registry = PluginRegistry()
    snapshot = build_snapshot(registry.get("manual-candidate-provider"))
    request = build_provider_request(
        modeling_input_bundle_id=bundle["modeling_input_bundle_id"],
        provider_snapshot_id=snapshot["snapshot_id"],
        capability="tbox-proposal",
        scope_id=scope["scope_id"],
        baseline_snapshot_id=baseline["baseline_snapshot_id"],
        terminology_catalog_id=terminology["terminology_catalog_id"],
        term_alignment_set_id=alignments["term_alignment_set_id"],
        kg_ir_dataset_ids=[dataset["dataset_id"]],
        evidence_record_ids=bundle["evidence_record_ids"],
        context={"manual_drafts": [draft]},
    )
    response = execute_provider(registry, "manual-candidate-provider", request)
    candidate_set = normalize_candidate_drafts(
        [response],
        scope=scope,
        evidence_ids=set(bundle["evidence_record_ids"]),
        kg_ir_item_ids={item["item_id"] for item in dataset["items"]},
        baseline_element_ids={item["element_id"] for item in baseline["elements"]},
    )
    proposal = build_proposal(
        project_lock_id=project_lock["lock_id"],
        input_bundle=bundle,
        scope=scope,
        question_set=questions,
        baseline=baseline,
        terminology=terminology,
        alignments=alignments,
        field_mappings=mappings,
        candidate_set=candidate_set,
        provider_snapshot_ids=[snapshot["snapshot_id"]],
    )
    prevalidation = prevalidate(
        proposal,
        current_project_lock_id=project_lock["lock_id"],
        evidence_ids=set(bundle["evidence_record_ids"]),
        kg_ir_item_ids={item["item_id"] for item in dataset["items"]},
        baseline_element_ids={item["element_id"] for item in baseline["elements"]},
        provider_snapshot_ids={snapshot["snapshot_id"]},
        allowed_namespaces=tuple(scope["namespace_policy"]["allowed_new_namespaces"]),
        input_bundle=bundle,
        scope=scope,
        scope_approval=approval,
    )
    coverage = structural_coverage(questions, proposal)
    queue = build_review_queue(proposal, prevalidation, review_policy)
    actions = [
        build_review_action(
            queue=queue,
            proposal=proposal,
            policy=review_policy,
            existing_actions=[],
            decision="ACCEPT",
            reviewer_id="mnp-compatibility-reviewer",
            reviewer_role="Development Reviewer",
            rationale="explicit compatibility-fixture human decision",
            candidate_id=proposal["tbox_candidates"][0]["candidate_id"],
        )
    ]
    finalization = finalize_review(
        queue=queue,
        proposal=proposal,
        prevalidation=prevalidation,
        policy=review_policy,
        actions=actions,
        coverage_report=coverage,
        scope=scope,
        scope_approval=approval,
        current_project_lock_id=project_lock["lock_id"],
    )
    confirmed = build_confirmed_package(
        project_lock=project_lock,
        input_bundle=bundle,
        scope=scope,
        scope_approval=approval,
        question_set=questions,
        coverage_report=coverage,
        baseline=baseline,
        terminology=terminology,
        alignments=alignments,
        field_mappings=mappings,
        proposal=proposal,
        prevalidation=prevalidation,
        review_policy=review_policy,
        finalization=finalization,
        actions=actions,
        review_queue=queue,
    )
    authority_dir = opened.root / "artifacts" / "confirmed" / "prompt05-current"
    authority_dir.mkdir(parents=True, exist_ok=False)
    documents = {
        "confirmed-package.json": confirmed,
        "scope.json": scope,
        "scope-approval.json": approval,
        "question-set.json": questions,
        "coverage-report.json": coverage,
        "baseline-snapshot.json": baseline,
        "terminology-catalog.json": terminology,
        "term-alignment-set.json": alignments,
        "field-mapping-candidate-set.json": mappings,
        "proposal.json": proposal,
        "prevalidation.json": prevalidation,
        "review-policy.json": review_policy,
        "review-decision-log.json": finalization.decision_log,
        "provider-snapshot.json": snapshot,
    }
    for name, document in documents.items():
        atomic_write_json(authority_dir / name, document)
    baseline_closure = load_baseline_closure(project_lock, domain_packs_root=ROOT / "domain_packs")
    query_ref = "mnp-competency-questions-queries-cq01-current-eligibility"

    def query_loader(reference: str) -> bytes:
        return baseline_closure.query_assets[reference]

    cq_plan = build_cq_test_plan(
        [
            {
                "question_id": question_id,
                "requirement": "REQUIRED",
                "query_artifact_ref": query_ref,
                "query_type": "SELECT",
                "target_graph_roles": ["abox"],
                "expected_answer_shape": "COMPATIBILITY_EMPTY_RESULT",
                "assertions": [
                    {
                        "assertion_type": "MAX_ROW_COUNT",
                        "boolean_value": None,
                        "integer_value": 0,
                        "string_values": [],
                        "semantic_hash": None,
                    }
                ],
                "resource_limits": [
                    {"name": "max_query_characters", "value": 100000},
                    {"name": "max_query_results", "value": 1000},
                    {"name": "max_query_seconds", "value": 30},
                    {"name": "max_query_path_depth", "value": 8},
                ],
            }
        ],
        query_loader=query_loader,
    )
    atomic_write_json(authority_dir / "cq-test-plan.json", cq_plan)
    jar = ROOT / "third_party" / "downloads" / "robot-1.9.7.jar"
    assert hashlib.sha256(jar.read_bytes()).hexdigest() == ROBOT_SHA256
    registry_before = {
        path.relative_to(opened.root / "registry").as_posix(): path.read_bytes()
        for path in (opened.root / "registry").rglob("*")
        if path.is_file()
    }
    compiler = SemanticCompiler(opened.root, domain_packs_root=ROOT / "domain_packs", reasoner_jar=jar)
    plan, attestation = compiler.create_plan(
        package_id=confirmed["package_id"],
        package_name="mnp-semantic-kernel-compatibility",
        package_version="0.1.0",
        ontology_iri="https://yangjunjie-lin.github.io/KG-MNP-Demo/examples/mnp-compatibility",
        version_iri="https://yangjunjie-lin.github.io/KG-MNP-Demo/examples/mnp-compatibility/0.1.0",
        cq_test_plan=cq_plan,
    )
    result = compiler.build(plan["plan_id"])
    registry_after = {
        path.relative_to(opened.root / "registry").as_posix(): path.read_bytes()
        for path in (opened.root / "registry").rglob("*")
        if path.is_file()
    }
    return locals()
