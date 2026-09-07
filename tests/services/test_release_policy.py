import pytest

from kg_mnp.services.errors import ServiceBoundaryError
from kg_mnp.services.release_policy import release_policy, require_release_policy


def test_production_policy_requires_multiple_humans_and_all_policy_roles():
    policy = release_policy("PRODUCTION_MULTI_ROLE")
    assert policy["minimum_distinct_reviewers"] == 2
    assert set(policy["required_roles"]) == {
        "RELEASE_MANAGER", "ONTOLOGY_ENGINEER", "DOMAIN_REVIEWER", "SECURITY_REVIEWER", "DATA_STEWARD",
    }
    require_release_policy(policy, "PRODUCTION_MULTI_ROLE")


def test_development_policy_cannot_be_reused_as_production_approval():
    development = release_policy("DEVELOPMENT_SINGLE_REVIEWER")
    assert development["minimum_distinct_reviewers"] == 1
    assert development["release_policy_id"] != release_policy("PRODUCTION_MULTI_ROLE")["release_policy_id"]
    with pytest.raises(ServiceBoundaryError, match="current server review policy"):
        require_release_policy(development, "PRODUCTION_MULTI_ROLE")


def test_production_service_requires_two_authenticated_reviewers(prompt05_case, tmp_path):
    from kg_mnp.lifecycle.registry.head import read_head
    from kg_mnp.lifecycle.registry.import_package import import_package
    from kg_mnp.services.facade import ApplicationService
    from kg_mnp.services.models import OperationRequest, ServiceConfiguration
    from kg_mnp.services.projects import get_project
    from tests.services.test_modeling_workflow import call

    service = ApplicationService(ServiceConfiguration(str(tmp_path)))
    _, alice = service.tokens.create(principal_id="alice", principal_type="HUMAN", permissions={"*"}, project_ids=set(), created_by="synthetic-test")
    project = service.execute(OperationRequest("project.create", parameters={
        "name": "production-policy", "domain_pack": "minimal", "domain_pack_version": "0.1.0"}), alice).payload
    identifier = project["project_id"]
    # Fixture package is normally compiled/reviewed, not a constructed success.
    imported = import_package(get_project(service.root, identifier).registry_root,
        prompt05_case["result"].package_directory, source_project_lock=prompt05_case["workspace"] / "project.lock.json")
    candidate = call(service, alice, identifier, "release.candidate", {"package_id": imported["package_id"]}, "candidate")
    assert candidate["minimum_distinct_reviewers"] == 2
    review = call(service, alice, identifier, "release.review", {"candidate_id": candidate["release_candidate_id"],
        "decision": "APPROVE", "rationale": "First authenticated human decision"}, "alice")
    assert review["quorum_satisfied"] is False
    def publish(key):
        return call(service, alice, identifier, "release.publish", {"candidate_id": candidate["release_candidate_id"],
            "review_id": review["review_id"], "expected_registry_head_hash": read_head(get_project(service.root, identifier).registry_root)["head_hash"]}, key)
    with pytest.raises(ServiceBoundaryError, match="quorum"):
        publish("insufficient")
    _, bob = service.tokens.create(principal_id="bob", principal_type="HUMAN",
        permissions={"release:review", "review:role:ONTOLOGY_ENGINEER"}, project_ids={identifier}, created_by="synthetic-test")
    review = call(service, bob, identifier, "release.review", {"candidate_id": candidate["release_candidate_id"],
        "decision": "APPROVE", "rationale": "Independent second human review"}, "bob")
    assert review["actions"][-1]["reviewer_roles"] == ["ONTOLOGY_ENGINEER"]
    assert review["quorum_satisfied"] is True
    assert publish("complete")["release"]["release_status"] == "RELEASED"
