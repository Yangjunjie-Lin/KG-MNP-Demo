from __future__ import annotations

import pytest

from kg_mnp.modeling.control_plane.errors import (
    ModelingControlError,
    ModelingProviderError,
)
from kg_mnp.modeling.control_plane.security import assert_safe_json


@pytest.mark.parametrize(
    "payload,match",
    [
        ({"confirmed": True}, "authority field"),
        ({"review_decision": "ACCEPT"}, "authority field"),
        ({"project_lock_id": "forged"}, "authority field"),
        ({"domain_pack_lock_ids": []}, "authority field"),
        ({"body": "@prefix evil:"}, "RDF syntax"),
        ({"body": "```python run()"}, "executable"),
    ],
)
def test_provider_authority_and_executable_injection_is_rejected(payload: dict, match: str) -> None:
    with pytest.raises((ModelingProviderError, ModelingControlError), match=match):
        assert_safe_json(payload, provider_output=True)


def test_provider_path_secret_unicode_and_json_depth_are_rejected() -> None:
    with pytest.raises(ModelingControlError, match="filesystem"):
        assert_safe_json({"value": "C:\\private\\file"}, provider_output=True)
    with pytest.raises(ModelingControlError, match="secret"):
        assert_safe_json({"value": "sk-abcdefghijklmnop"}, provider_output=True)
    with pytest.raises(ModelingControlError, match="control"):
        assert_safe_json({"value": "safe\u202eevil"}, provider_output=True)
    with pytest.raises(ModelingControlError, match="nesting"):
        assert_safe_json({"a": {"b": {"c": 1}}}, provider_output=True, max_depth=2)
