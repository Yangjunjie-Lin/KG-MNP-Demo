from rdflib import Graph, Literal, URIRef

from ._helpers import authorities, build


def test_named_graphs_are_stable_and_separated(tmp_path):
    directory, manifest, _ = build(tmp_path)
    graphs = manifest["graph_iris"]
    assert len(set(graphs.values())) == 3
    assert directory.joinpath("rdf/abox.nt").is_file()
    assert "decision_id" not in directory.joinpath("rdf/abox.nt").read_text(encoding="utf-8")


def test_business_abox_excludes_review_and_provenance_payloads(tmp_path):
    directory, _, _ = build(tmp_path, "rejection")
    values = authorities("rejection")
    decision_log, package = values[2], values[3]
    graph = Graph()
    graph.parse(directory / "rdf" / "abox.nt", format="nt")

    literals = {str(value) for value in graph.all_nodes() if isinstance(value, Literal)}
    forbidden_literals = {
        str(decision_log["reviewer"]["reviewer_id"]),
        *(str(item["rationale"]) for item in decision_log["decisions"]),
    }
    for section in ("candidate_entities", "candidate_assertions"):
        for candidate in values[1].get(section, []):
            forbidden_literals.update(map(str, candidate.get("source_paths", [])))
            forbidden_literals.update(map(str, candidate.get("mapping_rule_ids", [])))
    assert literals.isdisjoint(forbidden_literals)

    rejected_targets = {
        URIRef(str(item["candidate_id"]))
        for item in package["rejected_items"]
        if item.get("candidate_id")
    }
    assert all(target not in graph.all_nodes() for target in rejected_targets)
