from __future__ import annotations

import pytest
from prompt05_support import candidate

from kg_mnp.semantic_kernel.validation import validate_confirmed_candidates


def test_unsupported_candidate_and_action_partition_mismatch_fail_closed() -> None:
    unsupported = candidate("FUTURE_TYPE", candidate_kind="TBOX", candidate_action="CREATE_NEW", subject_iri="urn:test:new")
    with pytest.raises(ValueError, match="unsupported"):
        validate_confirmed_candidates({"TBOX": [unsupported]}, supported_types={"CLASS"})
    mismatched = candidate("CLASS", candidate_kind="TBOX", candidate_action="ASSERT", subject_iri="urn:test:new")
    with pytest.raises(ValueError, match="invalid"):
        validate_confirmed_candidates({"TBOX": [mismatched]}, supported_types={"CLASS"})

