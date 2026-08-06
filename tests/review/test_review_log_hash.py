from __future__ import annotations

import copy

from kg_mnp_demo.modeling.review_identifiers import decision_log_hash

from ._helpers import load_expected_log


def test_log_hash_covers_decisions_and_excludes_itself():
    log = load_expected_log("full-confirmation")
    assert log["log_hash"] == decision_log_hash(log)
    tampered = copy.deepcopy(log)
    tampered["decisions"][0]["rationale"] = "changed"
    assert decision_log_hash(tampered) != log["log_hash"]
