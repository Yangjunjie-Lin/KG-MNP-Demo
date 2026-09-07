import copy

import pytest

from kg_mnp.services.errors import ServiceBoundaryError
from tests.services.test_modeling_workflow import call, modeling_case  # noqa: F401


def test_candidate_edit_creates_new_id_and_rejects_unsafe_iri(modeling_case):  # noqa: F811
    service,principal,project,proposed=modeling_case
    candidate=proposed["proposal"]["tbox_candidates"][0];before=copy.deepcopy(candidate)
    request={"review_id":proposed["queue"]["review_queue_id"],"candidate_id":candidate["candidate_id"],"decision":"MODIFY_AND_ACCEPT","rationale":"Explicit reviewed candidate label correction","expected_head":None,"body_edits":{"label":"Reviewed candidate label"}}
    result=call(service,principal,project,"review.action",request,"edit")
    assert result["action"]["modified_candidate"]["candidate_id"]!=candidate["candidate_id"]
    assert candidate==before
    request.update(expected_head=result["action"]["action_hash"],body_edits={"subject_iri":"javascript:alert(1)"})
    with pytest.raises(ServiceBoundaryError):call(service,principal,project,"review.action",request,"unsafe-edit")
