import hashlib
import json
import zipfile
from io import BytesIO
from pathlib import Path

from rdflib import Graph

from zhigou_toolchain.modeling.delivery.native import GRAPH_PATHS, diagnostic_bytes
from zhigou_toolchain.ontology_io.contracts import REPORT_SCHEMA

ROOT = Path(__file__).resolve().parents[2]


def test_native_archive_diagnostic_preserves_graph_bytes_and_reports_missing_v3_inputs():
    original = ROOT / "docs/upgrade/evidence/hr-delivery.kgop"
    before = hashlib.sha256(original.read_bytes()).hexdigest()
    raw = diagnostic_bytes(original)
    with zipfile.ZipFile(BytesIO(raw)) as diagnostic, zipfile.ZipFile(original) as native:
        report = json.loads(diagnostic.read("diagnostic.json"))
        assert report["status"] == "BLOCKED_REQUIRED_BOUND_INPUTS" and report["v3_export_created"] is False
        assert report["native_verified"] == "VALID" and report["native_archive_sha256"] == before
        assert report["business_fact_count"] == 18 and report["auxiliary_named_individual_declarations"] == 5
        assert len(report["missing_bound_inputs"]) == 5
        assert set(diagnostic.namelist()) == {"diagnostic.json", "model/ontology.ttl", "model/instances.ttl", "model/shapes.ttl"}
        for role, name in GRAPH_PATHS.items():
            assert diagnostic.read("model/" + role + ".ttl") == native.read(name)
            assert len(Graph().parse(data=diagnostic.read("model/" + role + ".ttl"), format="turtle")) == report["graphs"][role]["triples"]
    assert hashlib.sha256(original.read_bytes()).hexdigest() == before


def test_report_schema_artifact_matches_runtime_contract():
    assert json.loads((ROOT / "config/ontology_io/ontology_io_report.schema.json").read_bytes()) == REPORT_SCHEMA
