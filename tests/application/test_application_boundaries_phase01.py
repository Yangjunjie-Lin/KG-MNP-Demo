from __future__ import annotations

from ._phase01_helpers import ROOT


def test_phase01_has_no_stage09_agent_llm_or_graph_rag_runtime_dependency():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8").lower()
    for dependency in ("openai", "langchain", "llamaindex", "chromadb", "pinecone", "qdrant"):
        assert dependency not in pyproject
    assert not (ROOT / "ontology/stage-09").exists()
    assert not (ROOT / "src/zhigou_toolchain/agent").exists()
