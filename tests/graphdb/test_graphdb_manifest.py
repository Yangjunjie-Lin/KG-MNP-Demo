import json

import pytest

from kg_mnp_demo.graphdb.contracts import validate_graphdb_contract
from kg_mnp_demo.graphdb.identifiers import repository_id_for_publication

from ._helpers import ROOT


@pytest.mark.parametrize(
    "scenario",
    ("full-confirmation", "modified-confirmation", "rejection", "issue-resolution"),
)
def test_golden_manifest_identity_and_closed_artifact_metadata(scenario):
    package = ROOT / "examples" / "graphdb" / "expected" / scenario
    manifest = json.loads((package / "graphdb-import-manifest.json").read_text(encoding="utf-8"))
    validate_graphdb_contract("graphdb-import-manifest", manifest)
    records = manifest["artifact_manifest"]
    assert len({record["relative_path"] for record in records}) == len(records)
    assert len({record["artifact_id"] for record in records}) == len(records)
    assert manifest["repository_id"] == repository_id_for_publication(manifest["publication_semantic_hash"])
