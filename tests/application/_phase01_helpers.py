from __future__ import annotations

import json
from pathlib import Path

from rdflib import Dataset

from kg_mnp_demo.application.policy import GraphRole, graph_role_for_iri
from kg_mnp_demo.application.publication_binding import PublicationBinding

ROOT = Path(__file__).resolve().parents[2]
PUBLICATION_HASH = "0e43e22adccec950dc6b638ffec5c3fdc2f0f43911704f9648e6171ae35161d3"


def json_document(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def synthetic_binding(scenario: str = "full-confirmation") -> PublicationBinding:
    graphdb = json_document(ROOT / f"examples/graphdb/expected/{scenario}/graphdb-import-manifest.json")
    compilation = json_document(ROOT / f"examples/compilation/expected/{scenario}/compilation-manifest.json")
    graphs = {role: [] for role in GraphRole}
    for iri in graphdb["named_graphs"]:
        role = graph_role_for_iri(iri)
        assert role is not None
        graphs[role].append(iri)
    return PublicationBinding(
        package_directory=ROOT / f"examples/publication/expected/{scenario}",
        attestation_directory=ROOT,
        manifest={
            "publication_id": "urn:kg-mnp:e2e-publication:" + PUBLICATION_HASH,
            "publication_semantic_hash": PUBLICATION_HASH,
            "compilation_id": graphdb["source_compilation_id"],
        },
        attestation={"status": "PUBLICATION_VERIFIED"},
        graphdb_manifest=graphdb,
        compilation_manifest=compilation,
        graphs={role: tuple(sorted(values)) for role, values in graphs.items()},
    )


class DatasetClient:
    def __init__(self, scenario: str = "full-confirmation"):
        self.dataset = Dataset()
        data = (
            ROOT / f"examples/graphdb/expected/{scenario}/import/knowledge-graph.nq"
        ).read_text(encoding="utf-8")
        self.dataset.parse(data=data, format="nquads")

    def health(self):
        return {"healthy": True, "repository_count": 1}

    def repository_info(self, repository_id):
        return {"id": repository_id, "params": {"ruleset": {"value": "empty"}}}

    def select(self, repository_id, query, *, timeout=5.0):
        assert repository_id.startswith("kg-mnp-")
        assert timeout <= 10
        result = self.dataset.query(query)
        return json.loads(result.serialize(format="json").decode("utf-8"))
