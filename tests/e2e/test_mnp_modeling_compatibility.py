from __future__ import annotations

import hashlib
import json
from pathlib import Path

from kg_mnp.ingestion.executor import execute_ingestion_plan
from kg_mnp.ingestion.planner import create_ingestion_plan
from kg_mnp.ingestion.source_store import SourceStore
from kg_mnp.modeling.control_plane.alignment import align_terms
from kg_mnp.modeling.control_plane.baseline import build_baseline_snapshot
from kg_mnp.modeling.control_plane.candidates import normalize_candidate_drafts
from kg_mnp.modeling.control_plane.competency import build_question_set
from kg_mnp.modeling.control_plane.input_bundle import build_input_bundle
from kg_mnp.modeling.control_plane.mappings import build_field_mapping_candidates
from kg_mnp.modeling.control_plane.proposal import build_proposal
from kg_mnp.modeling.control_plane.providers.execution import execute_provider
from kg_mnp.modeling.control_plane.providers.models import (
    build_provider_request,
    candidate_body,
    candidate_draft,
)
from kg_mnp.modeling.control_plane.review.policy import build_review_policy
from kg_mnp.modeling.control_plane.scope import build_scope
from kg_mnp.modeling.control_plane.scope_approval import approve_scope
from kg_mnp.modeling.control_plane.terminology import build_terminology_catalog
from kg_mnp.plugins.registry import PluginRegistry
from kg_mnp.plugins.snapshot import build_snapshot
from kg_mnp.workspace.service import initialize_workspace

ROOT = Path(__file__).resolve().parents[2]


def test_mnp_readonly_baseline_terminology_and_candidate_smoke(tmp_path: Path) -> None:
    pack_root = ROOT / "domain_packs/mnp"
    lock_path = pack_root / "pack.lock.json"
    lock_before = lock_path.read_bytes()
    opened = initialize_workspace(
        tmp_path / "workspace",
        project_id="prompt04-mnp-compatibility",
        project_version="0.4.0",
        display_name="Prompt 4 MNP Compatibility",
        domain_pack="mnp",
        domain_pack_version="1.0.0",
        domain_packs_root=ROOT / "domain_packs",
    )
    store = SourceStore(opened.root)
    source = store.add_file(ROOT / "examples/ingestion/minimal-project/sample.csv").source
    batch = store.create_batch([source["source_id"]])
    plan = create_ingestion_plan(opened.root, batch_id=batch["batch_id"])
    dataset = execute_ingestion_plan(opened.root, plan.plan["plan_id"]).dataset
    project_lock = opened.lock.document
    scope = build_scope(
        project_id=opened.manifest.project_id,
        project_lock_id=project_lock["lock_id"],
        domain_pack_lock_ids=[
            item["pack_lock_id"] for item in project_lock["resolved_domain_packs"]
        ],
        kg_ir_dataset_ids=[dataset["dataset_id"]],
        modeling_intent="ALIGN_TO_BASELINE",
        domain_description="Read-only MNP compatibility smoke over non-sensitive test KG-IR.",
        target_object_families=["Subscriber"],
        in_scope=["baseline reuse compatibility"],
        out_of_scope=["MNP ontology modification", "publication"],
        target_artifacts=["TBOX", "MAPPING", "TERMINOLOGY"],
        default_namespace="urn:kg-mnp:project:prompt04-mnp-compatibility:",
    )
    approval = approve_scope(
        scope,
        reviewer_id="mnp-compatibility-reviewer",
        reviewer_role="Development Reviewer",
        rationale="read-only compatibility fixture approval",
    )
    questions = build_question_set(
        project_lock_id=project_lock["lock_id"],
        scope_id=scope["scope_id"],
        questions=[
            {
                "question_text": "Can the locked MNP baseline be reused explicitly?",
                "purpose": "read-only baseline reuse traceability",
                "expected_answer_shape": "BOOLEAN",
                "required_concepts": ["Subscriber"],
            }
        ],
    )
    baseline = build_baseline_snapshot(
        project_lock_id=project_lock["lock_id"],
        pack_roots=[pack_root],
    )
    assert baseline["classes"]
    assert len(baseline["elements"]) == 214
    class_element = next(
        item for item in baseline["elements"] if item["element_kind"] == "CLASS"
    )
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
    policy = build_review_policy(
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
        review_policy_id=policy["policy_id"],
        allowed_provider_ids=["manual-candidate-provider"],
    )
    evidence_id = bundle["evidence_record_ids"][0]
    kg_ir_item_id = dataset["items"][0]["item_id"]
    draft = candidate_draft(
        draft_ref="mnp-baseline-reuse",
        draft_kind="TBOX",
        candidate_action="REUSE_EXISTING",
        body=candidate_body(
            candidate_type="CLASS",
            target_iri=class_element["iri"],
            label=(class_element["labels"][0]["value"] if class_element["labels"] else None),
        ),
        rationale="explicit read-only reuse of a locked MNP class",
        kg_ir_item_refs=[kg_ir_item_id],
        evidence_refs=[evidence_id],
        domain_asset_refs=[class_element["source_asset_id"]],
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
    assert len(proposal["tbox_candidates"]) == 1
    assert proposal["tbox_candidates"][0]["candidate_action"] == "REUSE_EXISTING"
    assert lock_path.read_bytes() == lock_before

    golden = json.loads(
        (ROOT / "tests/golden/domain-packs/mnp-prompt01-content.json").read_text(
            encoding="utf-8"
        )
    )
    assert len(golden["assets"]) == 84
    for item in golden["assets"]:
        content = (ROOT / item["path"]).read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(content).hexdigest() == item["sha256"]
