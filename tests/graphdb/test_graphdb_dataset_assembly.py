from kg_mnp_demo.graphdb.dataset_assembler import assemble_stage06_dataset
from ._helpers import compilation


def test_stage06_graph_iris_are_preserved_exactly():
    result = assemble_stage06_dataset(compilation())
    assert set(result["named_graphs"]) == set(result["manifest"]["graph_iris"].values())
    assert result["quad_count"] == result["manifest"]["artifact_manifest"][2]["quad_count"]
    assert b"_:" not in result["data"]
