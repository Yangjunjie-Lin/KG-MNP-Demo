"""Zero business baseline: explicit source-bound drafts through real five-stage services."""
from pathlib import Path

from tests.services.test_modeling_workflow import call
from zhigou_toolchain.modeling.control_plane.providers.models import (
    candidate_body,
    candidate_draft,
)
from zhigou_toolchain.services.facade import ApplicationService
from zhigou_toolchain.services.models import OperationRequest, ServiceConfiguration
from zhigou_toolchain.services.projects import get_project
from zhigou_toolchain.services.sources import verified_run


def test_new_ontology_without_business_baseline(tmp_path):
    run_new_ontology(tmp_path)


def run_new_ontology(tmp_path, *, live_repair=False):
    root = Path(__file__).resolve().parents[2]
    app = ApplicationService(ServiceConfiguration(str(tmp_path), review_profile="DEVELOPMENT_SINGLE_REVIEWER", reasoner_jar=str(root / "third_party/downloads/robot-1.9.7.jar")))
    _, human = app.tokens.create(principal_id="synthetic-new-ontology", principal_type="HUMAN", permissions={"*"}, project_ids=set(), created_by="test")
    project = app.execute(OperationRequest("project.create", parameters={"name": "new-ontology", "domain_pack": "empty", "domain_pack_version": "0.1.0"}), human).payload["project_id"]
    def run(operation, parameters, key):
        return call(app, human, project, operation, parameters, key)
    source = run("source.sample.load", {}, "sample")
    expected = {"schema_version": "1.0.0", "query_type": "SELECT", "comparison": "MULTISET", "variables": ["entity", "value"], "rows": [{
        "entity": {"kind": "IRI", "value": "urn:new:entity:001"}, "value": {"kind": "LITERAL", "value": "Alpha", "datatype": "http://www.w3.org/2001/XMLSchema#string"}}]}
    acceptance = [{"query_asset_id": "empty-query-values", "expected": expected}]
    run("modeling.session.open", {"run_id": source["run"]["run_id"], "business_rules": ["Entity instances must be identified by IRIs"], "acceptance": acceptance, "expected_revision": None}, "session")
    scope = run("modeling.scope", {"run_id": source["run"]["run_id"], "description": "Create an Entity vocabulary from explicit human design and real source values", "object_families": ["Entity"], "in_scope": ["one synthetic Entity"], "namespace": "urn:new:"}, "scope")["scope"]
    approval = run("modeling.scope.approve", {"scope_id": scope["scope_id"], "rationale": "Synthetic new ontology scope"}, "scope-approval")["approval"]
    prepared = run("modeling.prepare", {"scope_id": scope["scope_id"], "approval_id": approval["approval_id"], "questions": [{"question_text": "What value belongs to Entity 001?", "purpose": "Exact source-bound answer", "required_concepts": ["Entity"], "expected_answer_shape": "ENTITY_LIST"}]}, "prepare")
    assert prepared["baseline"]["elements"] == []
    dataset = verified_run(get_project(app.root, project).root, source["run"]["run_id"]).dataset
    item = next(i for i in dataset["items"] if i["item_kind"] == "table-cell" and i["payload"]["row"] == 2 and i["payload"]["column"] == 2)
    question = prepared["questions"]["questions"][0]["question_id"]
    def draft(ref, kind, action, body, dependencies=()):
        return candidate_draft(draft_ref=ref, draft_kind=kind, candidate_action=action, body=candidate_body(**body),
            rationale="Explicit synthetic human draft bound to original source and scope; not LIVE inference", kg_ir_item_refs=[item["item_id"]], evidence_refs=item["evidence_refs"], competency_question_refs=[question], dependency_draft_refs=dependencies)
    drafts = [draft("class", "TBOX", "CREATE_NEW", {"candidate_type": "CLASS", "target_iri": "urn:new:Entity", "label": "Entity"}),
        draft("property", "TBOX", "CREATE_NEW", {"candidate_type": "DATA_PROPERTY", "target_iri": "urn:new:label", "label": "label"}),
        draft("individual", "ABOX", "ASSERT", {"candidate_type": "INDIVIDUAL", "subject_iri": "urn:new:entity:001"}),
        draft("type", "ABOX", "ASSERT", {"candidate_type": "CLASS_ASSERTION", "subject_iri": "urn:new:entity:001", "object_iri": "urn:new:Entity"}, ["class", "individual"]),
        draft("value", "ABOX", "ASSERT", {"candidate_type": "DATA_PROPERTY_ASSERTION", "subject_iri": "urn:new:entity:001", "predicate_iri": "urn:new:label", "literal": {"lexical_value": item["payload"]["value"]["normalized_lexical_value"], "datatype_iri": "http://www.w3.org/2001/XMLSchema#string", "language": None}}, ["property", "individual"]),
        draft("shape", "SHACL", "CONSTRAIN", {"candidate_type": "NODE_SHAPE", "subject_iri": "urn:new:EntityShape", "target_iri": "urn:new:Entity"}, ["class"]),
        draft("node-kind", "SHACL", "CONSTRAIN", {"candidate_type": "NODE_KIND", "subject_iri": "urn:new:EntityShape", "object_iri": "http://www.w3.org/ns/shacl#IRI"}, ["shape"])]
    if live_repair:
        # Explicit fault injection, not a research comparison baseline.
        drafts[4]["body"]["literal"]["lexical_value"] = "FaultInjectedValue"
    proposal = run("modeling.proposal", {"bundle_id": prepared["bundle"]["modeling_input_bundle_id"], "providers": ["manual-candidate-provider"], "manual_drafts": drafts}, "drafts")
    if live_repair:
        from zhigou_toolchain.services.modeling_sessions import read
        old_proposal, old_review = proposal["proposal"]["proposal_id"], proposal["queue"]["review_queue_id"]
        proposal = run("modeling.proposal", {"bundle_id": prepared["bundle"]["modeling_input_bundle_id"], "providers": ["manual-candidate-provider"],
            "model_assistance": {"execution_mode": "LIVE", "action": "REPAIR", "parent_proposal_id": old_proposal,
                "expected_session_revision": read(get_project(app.root, project).root)["revision"]}}, "repair")
        assert proposal["proposal"]["proposal_id"] != old_proposal
        assert proposal["queue"]["review_queue_id"] != old_review
        assert proposal["model_assistance"]["changes"]
        assert all(c["status"] == "PASS" for c in read(get_project(app.root, project).root)["checks"])
    # New vocabulary requires human review even when the closed draft schema
    # is valid. Structural validity must not become automatic approval.
    assert proposal["prevalidation"]["status"] == "REVIEW_REQUIRED"
    candidates = [c for key in ("tbox_candidates", "abox_candidates", "mapping_candidates", "shacl_candidates") for c in proposal["proposal"][key]]
    queue = proposal["queue"]["review_queue_id"]
    checks = run("modeling.semantic.check", {"review_id": queue, "candidate_ids": [c["candidate_id"] for c in candidates]}, "semantic")
    assert all(c["validation_status"] == "PASS" for c in checks["five_stage"]["step_runs"])
    head = None
    for index, candidate in enumerate(candidates):
        result = run("review.action", {"review_id": queue, "candidate_id": candidate["candidate_id"], "decision": "ACCEPT", "rationale": "Synthetic explicit per-item design review", "expected_head": head}, f"review-{index}")
        head = result["action"]["action_hash"]
    confirmed = run("review.finalize", {"review_id": queue}, "finalize")["confirmed_package"]
    plan = run("compile.plan.exact", {"confirmed_package_id": confirmed["package_id"], "package_name": "new-ontology", "package_version": "0.1.0", "ontology_iri": "urn:new:ontology", "version_iri": "urn:new:ontology:0.1.0", "oracles": [{"question_id": question, **acceptance[0]}]}, "plan")["plan"]
    built = run("compile.build", {"plan_id": plan["plan_id"]}, "build")
    assert built["reports"]["competency-question-test-report.json"]["required_passed"] is True
    return {"project_id": project, "package_id": built["package_id"], "proposal": proposal, "reports": built["reports"]}
