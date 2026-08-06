import copy
import pytest

from kg_mnp_demo.compilation.abox_compiler import ABoxCompilationError, compile_abox
from ._helpers import authorities


def test_mapping_assertion_is_explicitly_forbidden():
    values = list(authorities())
    package = copy.deepcopy(values[3])
    item = package["confirmed_abox_decisions"][2]
    candidate_id = item["candidate_id"]
    proposal = copy.deepcopy(values[1])
    candidate = next(c for c in proposal["candidate_assertions"] if c["candidate_id"] == candidate_id)
    candidate["candidate_kind"] = "MAPPING_ASSERTION"
    with pytest.raises((ABoxCompilationError, ValueError)):
        compile_abox(package, proposal, values[4])


def test_unknown_candidate_kind_is_rejected():
    values = list(authorities())
    proposal = copy.deepcopy(values[1])
    candidate_id = values[3]["confirmed_abox_decisions"][0]["candidate_id"]
    candidate = next(item for item in proposal["candidate_entities"] if item["candidate_id"] == candidate_id)
    candidate["candidate_kind"] = "UNKNOWN_CANDIDATE_KIND"
    with pytest.raises(ABoxCompilationError, match="unsupported candidate kind"):
        compile_abox(values[3], proposal, values[4])
