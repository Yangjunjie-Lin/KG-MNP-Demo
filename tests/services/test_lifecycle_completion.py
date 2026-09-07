"""Version comparison/regression and explicit historical environment rollback."""
from __future__ import annotations

import pytest

from kg_mnp.services.errors import ServiceBoundaryError
from kg_mnp.services.facade import ApplicationService
from kg_mnp.services.models import OperationRequest, ServiceConfiguration
from kg_mnp.services.projects import get_project
from tests.services.test_modeling_workflow import call, modeling_case  # noqa: F401
from tests.services.test_modeling_workflow import (
    run_confirmed_initial_chain as _initial_chain,
)


def test_environment_cannot_execute_with_invented_approval(tmp_path):
    service=ApplicationService(ServiceConfiguration(str(tmp_path)))
    _,principal=service.tokens.create(principal_id="human",principal_type="HUMAN",permissions={"*"},project_ids=set(),created_by="test")
    project=service.execute(OperationRequest("project.create",parameters={"name":"environment","domain_pack":"minimal","domain_pack_version":"0.1.0"}),principal).payload
    env=call(service,principal,project["project_id"],"environment.create",{"name":"development"},"environment")
    assert env["status"]=="ACTIVE"
    with pytest.raises(ServiceBoundaryError):
        call(service,principal,project["project_id"],"environment.activate",{"proposal_id":"urn:kg-mnp:activation-proposal:"+"a"*64,
             "decision_id":"urn:kg-mnp:activation-review-decision:"+"b"*64,"expected_generation":0,
             "expected_pointer_hash":"0"*64,"expected_registry_head_hash":"0"*64},"invented")


def test_cq_regression_reexecutes_packaged_query_oracle(prompt05_case, tmp_path):
    from kg_mnp.lifecycle.registry.import_package import import_package
    from kg_mnp.lifecycle.registry.manifest import init_registry
    from kg_mnp.lifecycle.regression import plan_regression, run_regression
    root=tmp_path/"registry"
    init_registry(root,project_id="regression-test",created_by="human")
    package=prompt05_case["result"].package_directory
    imported=import_package(root,package,source_project_lock=prompt05_case["workspace"]/"project.lock.json")
    plan=plan_regression(root,base_package_id=imported["package_id"],candidate_package_id=imported["package_id"],tests=[{
        "test_category":"CANDIDATE_CQ","expected_result":{"assertion_type":"BOOLEAN_EQUALS","boolean_value":True,
        "integer_value":None,"string_values":[],"semantic_hash":None}}])
    result=run_regression(root,plan)
    assert result["status"]=="PASSED"
    assert result["required_passed"] is True
    wrong=plan_regression(root,base_package_id=imported["package_id"],candidate_package_id=imported["package_id"],tests=[{
        "test_category":"CANDIDATE_CQ","expected_result":{"assertion_type":"BOOLEAN_EQUALS","boolean_value":False,
        "integer_value":None,"string_values":[],"semantic_hash":None}}])
    assert run_regression(root,wrong)["required_passed"] is False


def test_two_compiled_versions_release_and_specified_rollback(modeling_case):  # noqa: F811 - imported pytest fixture
    case=_initial_chain(modeling_case)
    service,principal,project_id=case["service"],case["principal"],case["project_id"]
    base=case["package"]["package_id"]
    plan=call(service,principal,project_id,"compile.plan",{"confirmed_package_id":case["confirmed_id"],"package_name":"synthetic-minimal",
        "package_version":"0.1.1","ontology_iri":"urn:synthetic:ontology","version_iri":"urn:synthetic:ontology:0.1.1",
        "oracles":[{"question_id":case["question_id"],"query_asset_id":"minimal-query-list-entities","min_rows":1,"required_bindings":["entity","label"]}]},"version-two-plan")["plan"]
    built=call(service,principal,project_id,"compile.build",{"plan_id":plan["plan_id"]},"version-two-build")
    candidate=built["package_id"]
    call(service,principal,project_id,"registry.import",{"package_id":candidate},"import-two")
    diff=call(service,principal,project_id,"change.diff",{"base_package_id":base,"candidate_package_id":candidate},"diff-two")
    assert diff["diff"]["overall_classification"]!="UNKNOWN_REQUIRES_REVIEW",diff["diff"]["unknown_constructs"]
    impact=call(service,principal,project_id,"change.impact",{"diff_id":diff["diff"]["diff_id"]},"impact-two")
    regression=call(service,principal,project_id,"change.regression",{"diff_id":diff["diff"]["diff_id"],"impact_id":impact["impact_id"]},"regression-two")
    assert regression["report"]["required_passed"] is True
    evaluated=call(service,principal,project_id,"change.evaluate",{"diff_id":diff["diff"]["diff_id"],"impact_id":impact["impact_id"],
        "regression_report_id":regression["report"]["report_id"],"rationale":"Versioned reproducible successor"},"evaluate-two")
    release_candidate=call(service,principal,project_id,"release.candidate",{"package_id":candidate,"change_evaluation_id":evaluated["evaluation_id"]},"candidate-two")
    reviewed=call(service,principal,project_id,"release.review",{"candidate_id":release_candidate["release_candidate_id"],"decision":"APPROVE","rationale":"Explicit successor approval"},"review-two")
    from kg_mnp.lifecycle.registry.head import read_head
    head=lambda:read_head(get_project(service.root,project_id).registry_root)["head_hash"]
    released=call(service,principal,project_id,"release.publish",{"candidate_id":release_candidate["release_candidate_id"],"review_id":reviewed["review_id"],
        "expected_registry_head_hash":head()},"publish-two")["release"]
    env=call(service,principal,project_id,"environment.create",{"name":"development"},"environment")
    import hashlib
    root=get_project(service.root,project_id).registry_root
    release_bytes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/"records/releases").glob("*.json")}
    for index,(kind,target) in enumerate([("ACTIVATE",case["release"]["release_id"]),("ACTIVATE",released["release_id"]),("ROLLBACK",case["release"]["release_id"])]):
        proposed=call(service,principal,project_id,"environment.propose",{"environment_id":env["environment_id"],"release_id":target,"kind":kind,"rationale":"Explicit selected historical target"},f"environment-proposal-{index}")
        review=call(service,principal,project_id,"environment.review",{"proposal_id":proposed["activation_proposal_id"],"decision":"APPROVE","rationale":"Human target review","breaking_change_acknowledged":True},f"environment-review-{index}")
        pointer=call(service,principal,project_id,"environment.inspect",{"environment_id":env["environment_id"]},"pointer")
        request={"proposal_id":proposed["activation_proposal_id"],"decision_id":review["decision_id"],"expected_generation":pointer["generation"],"expected_pointer_hash":pointer["pointer_hash"],"expected_registry_head_hash":head()}
        applied=call(service,principal,project_id,"environment.rollback" if kind=="ROLLBACK" else "environment.activate",request,f"execute-{index}")
        assert applied["receipt"]["target_release_id"]==target
    pointer=call(service,principal,project_id,"environment.inspect",{"environment_id":env["environment_id"]},"final-pointer")
    assert pointer["active_release_id"]==case["release"]["release_id"]
    root=get_project(service.root,project_id).registry_root
    assert release_bytes=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/"records/releases").glob("*.json")}
