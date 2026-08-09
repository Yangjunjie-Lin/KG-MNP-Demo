from __future__ import annotations

from fastapi.testclient import TestClient

from kg_mnp_demo.application.http import create_app
from kg_mnp_demo.application.query_registry import QueryRegistry
from kg_mnp_demo.application.service import ApplicationService

from ._phase01_helpers import DatasetClient, ROOT, synthetic_binding


def test_phase01_has_no_stage09_agent_llm_or_graph_rag_runtime_dependency():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8").lower()
    for dependency in ("openai", "langchain", "llamaindex", "chromadb", "pinecone", "qdrant"):
        assert dependency not in pyproject
    assert not (ROOT / "ontology/stage-09").exists()
    assert not (ROOT / "src/kg_mnp_demo/agent").exists()


def test_http_openapi_contains_only_get_and_head_application_operations():
    service = ApplicationService(binding=synthetic_binding(), registry=QueryRegistry.load(), client=DatasetClient())
    with TestClient(create_app(service)) as http:
        paths = http.get("/openapi.json").json()["paths"]
    assert paths
    assert all(set(operations) <= {"get", "head"} for operations in paths.values())
    assert all("sparql" not in path.lower() for path in paths)
