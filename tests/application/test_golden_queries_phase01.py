from __future__ import annotations

import json

import pytest

from kg_mnp_demo.application.errors import ApplicationError
from kg_mnp_demo.application.query_registry import QueryRegistry
from kg_mnp_demo.application.service import ApplicationService

from ._phase01_helpers import ROOT, DatasetClient, synthetic_binding


def _json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _service(scenario):
    return ApplicationService(binding=synthetic_binding(scenario), registry=QueryRegistry.load(), client=DatasetClient(scenario))


def test_all_ten_golden_case_directories_are_present_and_deterministic():
    root = ROOT / "examples/application"
    cases = sorted(path for path in root.iterdir() if path.is_dir())
    assert len(cases) == 10
    for case in cases:
        assert (case / "request.json").is_file()
        assert (case / "expected.json").is_file()
        request = _json(case / "request.json")
        expected = _json(case / "expected.json")
        if case.name == "invalid-iri":
            with pytest.raises(ApplicationError) as caught:
                _service(request["scenario"]).run(request["query_id"], request["parameters"])
            assert caught.value.code.value == expected["error_code"]
            continue
        if case.name == "rejected-candidate-not-visible-as-business-fact":
            service = _service(request["scenario"])
            for plane in ("business", "review"):
                item = request[f"{plane}_query"]
                result = service.run(item["query_id"], item["parameters"])
                assert result["result_count"] == expected[plane]["result_count"]
                assert result["publication_id"] == service.binding.publication_id
                assert result["result_semantic_hash"] == expected[plane]["result_semantic_hash"]
            continue
        service = _service(request["scenario"])
        result = service.run(request["query_id"], request["parameters"])
        assert result["result_count"] == expected["result_count"]
        assert result["publication_id"] == service.binding.publication_id
        assert result["result_semantic_hash"] == expected["result_semantic_hash"]
        assert result["truncated"] is expected["truncated"]
