from __future__ import annotations

from pathlib import Path

import pytest

from kg_mnp.workspace.service import initialize_workspace

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def prompt03_workspace(tmp_path: Path) -> Path:
    target = tmp_path / "workspace"
    initialize_workspace(
        target,
        project_id="prompt03-test-project",
        project_version="0.3.0",
        display_name="Prompt 3 Test Project",
        domain_pack="minimal",
        domain_pack_version="0.1.0",
        domain_packs_root=ROOT / "domain_packs",
    )
    return target


@pytest.fixture(scope="session")
def prompt04_case(tmp_path_factory: pytest.TempPathFactory) -> dict:
    """Build one real Minimal ingestion→confirmation chain for Prompt 4 tests."""

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
    from kg_mnp.modeling.control_plane.providers.models import build_provider_request
    from kg_mnp.modeling.control_plane.review.actions import build_review_action
    from kg_mnp.modeling.control_plane.review.finalization import finalize_review
    from kg_mnp.modeling.control_plane.review.policy import build_review_policy
    from kg_mnp.modeling.control_plane.review.queue import build_review_queue
    from kg_mnp.modeling.control_plane.scope import build_scope
    from kg_mnp.modeling.control_plane.scope_approval import approve_scope
    from kg_mnp.modeling.control_plane.terminology import build_terminology_catalog
    from kg_mnp.plugins.registry import PluginRegistry
    from kg_mnp.plugins.snapshot import build_snapshot

    root = tmp_path_factory.mktemp("prompt04-case")
    workspace = root / "workspace"
    opened = initialize_workspace(
        workspace,
        project_id="prompt04-test-project",
        project_version="0.4.0",
        display_name="Prompt 4 Test Project",
        domain_pack="minimal",
        domain_pack_version="0.1.0",
        domain_packs_root=ROOT / "domain_packs",
    )
    store = SourceStore(workspace)
    source = store.add_file(ROOT / "examples/ingestion/minimal-project/sample.csv").source
    batch = store.create_batch([source["source_id"]])
    plan = create_ingestion_plan(workspace, batch_id=batch["batch_id"])
    ingestion = execute_ingestion_plan(workspace, plan.plan["plan_id"])
    dataset = ingestion.dataset
    project_lock = opened.lock.document
    scope = build_scope(
        project_id=opened.manifest.project_id,
        project_lock_id=project_lock["lock_id"],
        domain_pack_lock_ids=[
            item["pack_lock_id"] for item in project_lock["resolved_domain_packs"]
        ],
        kg_ir_dataset_ids=[dataset["dataset_id"]],
        modeling_intent="MIXED_MODELING",
        domain_description="Minimal non-production ontology modeling test.",
        target_object_families=["Entity"],
        in_scope=["entity labels"],
        out_of_scope=["publication"],
        target_artifacts=["TBOX", "MAPPING", "ABOX", "SHACL", "TERMINOLOGY"],
        default_namespace="urn:kg-mnp:project:prompt04-test-project:",
    )
    approval = approve_scope(
        scope,
        reviewer_id="reviewer-1",
        reviewer_role="Development Reviewer",
        rationale="bounded test scope approved by a human fixture",
    )
    question_set = build_question_set(
        project_lock_id=project_lock["lock_id"],
        scope_id=scope["scope_id"],
        questions=[
            {
                "question_text": "Which entities and labels are present?",
                "purpose": "structural retrieval and traceability",
                "required_concepts": ["Entity"],
                "expected_answer_shape": "ENTITY_LIST",
            }
        ],
    )
    baseline = build_baseline_snapshot(
        project_lock_id=project_lock["lock_id"],
        pack_roots=[ROOT / "domain_packs/minimal"],
    )
    terminology = build_terminology_catalog(
        scope=scope,
        baseline=baseline,
        kg_ir_datasets=[dataset],
        domain_terms=[
            {
                "lexical_form": "Entity",
                "source_ref": "minimal-terminology",
                "candidate_iris": [
                    "https://yangjunjie-lin.github.io/KG-MNP-Demo/domain-packs/minimal/terms#Entity"
                ],
            }
        ],
    )
    alignments = align_terms(terminology, baseline)
    field_mappings = build_field_mapping_candidates(
        kg_ir_datasets=[dataset],
        alignments=alignments,
        terminology=terminology,
        baseline=baseline,
    )
    policy = build_review_policy(
        project_lock_id=project_lock["lock_id"],
        profile="DEVELOPMENT_SINGLE_REVIEWER",
    )
    provider_ids = ["baseline-reuse-provider", "rule-mapping-provider"]
    input_bundle = build_input_bundle(
        project_lock=project_lock,
        scope=scope,
        approval=approval,
        question_set=question_set,
        baseline=baseline,
        terminology=terminology,
        alignments=alignments,
        kg_ir_datasets=[dataset],
        review_policy_id=policy["policy_id"],
        allowed_provider_ids=provider_ids,
    )
    context = {
        "baseline_elements": baseline["elements"],
        "alignments": alignments["alignments"],
        "field_mappings": field_mappings["mappings"],
        "kg_ir_items": dataset["items"],
        "default_namespace": scope["namespace_policy"]["default_namespace"],
        "competency_question_ids": [
            item["question_id"] for item in question_set["questions"]
        ],
    }
    registry = PluginRegistry()
    responses = []
    snapshots = []
    for provider_id, capability in (
        ("baseline-reuse-provider", "baseline-reuse"),
        ("rule-mapping-provider", "field-mapping-proposal"),
    ):
        snapshot = build_snapshot(registry.get(provider_id))
        request = build_provider_request(
            modeling_input_bundle_id=input_bundle["modeling_input_bundle_id"],
            provider_snapshot_id=snapshot["snapshot_id"],
            capability=capability,
            scope_id=scope["scope_id"],
            baseline_snapshot_id=baseline["baseline_snapshot_id"],
            terminology_catalog_id=terminology["terminology_catalog_id"],
            term_alignment_set_id=alignments["term_alignment_set_id"],
            kg_ir_dataset_ids=[dataset["dataset_id"]],
            evidence_record_ids=input_bundle["evidence_record_ids"],
            context=context,
        )
        responses.append(execute_provider(registry, provider_id, request))
        snapshots.append(snapshot)
    candidate_set = normalize_candidate_drafts(
        responses,
        scope=scope,
        evidence_ids=set(input_bundle["evidence_record_ids"]),
        kg_ir_item_ids={item["item_id"] for item in dataset["items"]},
        baseline_element_ids={item["element_id"] for item in baseline["elements"]},
    )
    proposal = build_proposal(
        project_lock_id=project_lock["lock_id"],
        input_bundle=input_bundle,
        scope=scope,
        question_set=question_set,
        baseline=baseline,
        terminology=terminology,
        alignments=alignments,
        field_mappings=field_mappings,
        candidate_set=candidate_set,
        provider_snapshot_ids=[item["snapshot_id"] for item in snapshots],
    )
    prevalidation = prevalidate(
        proposal,
        current_project_lock_id=project_lock["lock_id"],
        evidence_ids=set(input_bundle["evidence_record_ids"]),
        kg_ir_item_ids={item["item_id"] for item in dataset["items"]},
        baseline_element_ids={item["element_id"] for item in baseline["elements"]},
        provider_snapshot_ids=set(proposal["provider_snapshots"]),
        allowed_namespaces=tuple(scope["namespace_policy"]["allowed_new_namespaces"]),
        input_bundle=input_bundle,
        scope=scope,
        scope_approval=approval,
    )
    coverage = structural_coverage(question_set, proposal)
    queue = build_review_queue(proposal, prevalidation, policy)
    actions = []
    for item in queue["items"]:
        if item["candidate_id"] is None:
            continue
        actions.append(
            build_review_action(
                queue=queue,
                proposal=proposal,
                policy=policy,
                existing_actions=actions,
                decision="ACCEPT",
                reviewer_id="reviewer-1",
                reviewer_role="Development Reviewer",
                rationale="explicit human test-fixture decision",
                candidate_id=item["candidate_id"],
            )
        )
    finalization = finalize_review(
        queue=queue,
        proposal=proposal,
        prevalidation=prevalidation,
        policy=policy,
        actions=actions,
        coverage_report=coverage,
        scope=scope,
        scope_approval=approval,
        current_project_lock_id=project_lock["lock_id"],
    )
    package = build_confirmed_package(
        project_lock=project_lock,
        input_bundle=input_bundle,
        scope=scope,
        scope_approval=approval,
        question_set=question_set,
        coverage_report=coverage,
        baseline=baseline,
        terminology=terminology,
        alignments=alignments,
        field_mappings=field_mappings,
        proposal=proposal,
        prevalidation=prevalidation,
        review_policy=policy,
        finalization=finalization,
        actions=actions,
        review_queue=queue,
    )
    return locals()
