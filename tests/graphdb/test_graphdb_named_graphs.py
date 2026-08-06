import json

from rdflib import BNode, Dataset

from ._helpers import ROOT


def test_golden_dataset_has_exact_closed_named_graph_set():
    package = ROOT / "examples" / "graphdb" / "expected" / "full-confirmation"
    manifest = json.loads((package / "graphdb-import-manifest.json").read_text(encoding="utf-8"))
    expected_counts = json.loads((package / "verification" / "expected" / "named-graph-counts.json").read_text(encoding="utf-8"))
    dataset = Dataset().parse((package / "import" / "knowledge-graph.nq").as_posix(), format="nquads")
    quads = list(dataset.quads((None, None, None, None)))
    assert not any(isinstance(term, BNode) for quad in quads for term in quad)
    actual_counts = {}
    for _, _, _, graph in quads:
        actual_counts[str(graph)] = actual_counts.get(str(graph), 0) + 1
    assert set(actual_counts) == set(manifest["named_graphs"]) == set(expected_counts)
    assert actual_counts == expected_counts
