import pytest

from kg_mnp.services.errors import ServiceBoundaryError
from tests.services.test_modeling_workflow import call, modeling_case  # noqa: F401


def test_scope_decisions_require_observed_revision_and_rejection_invalidates_bundle(modeling_case):  # noqa: F811
    service, principal, project, proposed = modeling_case
    from kg_mnp.modeling.control_plane.service import ModelingWorkspaceService
    from kg_mnp.services.projects import get_project
    modeling = ModelingWorkspaceService(get_project(service.root, project).root)
    scope_id = proposed["proposal"]["scope_id"]
    from kg_mnp.contracts.document_io import read_document
    approval = read_document(modeling.build_directory(scope_id) / "scope-approval.json")
    with pytest.raises(ServiceBoundaryError, match="reload"):
        call(service, principal, project, "modeling.scope.approve", {"scope_id":scope_id,
            "decision":"REJECT", "rationale":"Stale reader must not overwrite approval"}, "stale-review")
    rejected = call(service, principal, project, "modeling.scope.approve", {"scope_id":scope_id,
        "expected_approval_id":approval["approval_id"], "decision":"REJECT", "rationale":"Explicit withdrawal of scope approval"}, "current-review")
    assert rejected["approval"]["decision"] == "REJECT"
    with pytest.raises(ServiceBoundaryError):
        call(service, principal, project, "modeling.proposal", {"bundle_id": proposed["proposal"]["modeling_input_bundle_id"],
            "providers":["baseline-reuse-provider","rule-mapping-provider"]}, "stale-bundle")
