from __future__ import annotations

from copy import deepcopy

from kg_mnp_demo.modeling.identifiers import candidate_id, issue_id
from kg_mnp_demo.modeling.issues import make_issue


def test_candidate_identifier_is_content_derived_and_stable() -> None:
    candidate = {"review_status": "PROPOSED", "value": "A"}
    first = candidate_id(candidate)
    assert first == candidate_id(deepcopy(candidate))
    assert first.startswith("urn:kg-mnp:candidate:")
    changed = {**candidate, "value": "B"}
    assert candidate_id(changed) != first


def test_issue_identifier_matches_issue_content() -> None:
    issue = make_issue("UNSUPPORTED", "WARNING", "Needs review", source_paths=["/x"])
    assert issue["issue_id"] == issue_id(issue)
    assert len(issue["issue_id"].rsplit(":", 1)[-1]) == 64

