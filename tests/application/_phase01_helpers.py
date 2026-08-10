from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from rdflib import Dataset

from kg_mnp_demo.application.publication_binding import PublicationBinding

ROOT = Path(__file__).resolve().parents[2]
_BINDING_TEMPORARY_DIRECTORIES: list[TemporaryDirectory[str]] = []


def json_document(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


@lru_cache(maxsize=4)
def synthetic_binding(scenario: str = "full-confirmation") -> PublicationBinding:
    temporary = TemporaryDirectory(prefix=f"kg-mnp-phase01-{scenario}-")
    _BINDING_TEMPORARY_DIRECTORIES.append(temporary)
    attestation = publication_attestation_report(Path(temporary.name), scenario)
    return PublicationBinding.verify(
        ROOT / f"examples/publication/expected/{scenario}",
        attestation,
        publication_scenario=scenario,
    )


def publication_attestation_report(directory: Path, scenario: str) -> Path:
    """Create deterministic, contract-valid offline runtime evidence."""

    package = ROOT / f"examples/publication/expected/{scenario}"
    manifest = json_document(package / "publication-manifest.json")
    visualization = json_document(
        package / "visualization/visualization-manifest.json"
    )
    coverage = json_document(
        package / "verification/ontology-visualization-coverage.json"
    )
    representation_loss = json_document(
        package / "verification/representation-loss.json"
    )
    tbox = json_document(package / "verification/tbox-equivalence.json")
    attestation = {
        "contract_version": "1.0",
        "status": "PUBLICATION_VERIFIED",
        "publication_id": manifest["publication_id"],
        "publication_semantic_hash": manifest["publication_semantic_hash"],
        "visualization_id": visualization["visualization_id"],
        "visualization_semantic_hash": visualization[
            "visualization_semantic_hash"
        ],
        "graphdb_tbox_semantic_hash": tbox["graphdb_tbox_semantic_hash"],
        "stage03_tbox_semantic_hash": tbox["stage03_tbox_semantic_hash"],
        "raw_vowl_hash": visualization["raw_converter_sha256"],
        "normalized_vowl_hash": visualization["normalized_vowl_sha256"],
        "coverage_status": coverage["status"],
        "browser_status": "PASS",
        "graphdb_version": "11.4.2",
        "graphdb_license_state": "ACCEPTED",
        "graphdb_oci_image_digest": "sha256:" + "0" * 64,
        "webvowl_upstream_commit": visualization["webvowl_upstream_commit"],
        "owl2vowl_upstream_commit": visualization["owl2vowl_upstream_commit"],
        "runtime_image_digest": "sha256:" + "1" * 64,
        "browser_name": "chromium",
        "browser_version": "131.0.6778.33",
        "browser_revision": "1148",
        "playwright_version": "1.49.1",
    }
    documents: dict[str, Any] = {
        "publication-manifest.json": manifest,
        "visualization-manifest.json": visualization,
        "ontology-visualization-coverage.json": coverage,
        "representation-loss.json": representation_loss,
        "tbox-equivalence.json": tbox,
        "upstream-lock.json": json_document(package / "source/upstream-lock.json"),
        "browser-smoke.json": {
            "status": "PASS",
            "browser_name": "chromium",
            "browser_version": "131.0.6778.33",
            "browser_revision": "1148",
            "playwright_version": "1.49.1",
            "canonical_vowl_loaded": True,
            "class_nodes": visualization["class_count"],
            "property_nodes": visualization["object_property_count"]
            + visualization["datatype_property_count"],
            "svg_count": 1,
            "javascript_errors": [],
            "console_errors": [],
            "external_requests": [],
            "browser_http_egress_probe_blocked": True,
            "browser_websocket_egress_probe_blocked": True,
            "loopback_proxy_egress_probe": {"status": "PASS"},
            "security_probe": {
                "status": "PASS",
                "security_label_count": 3,
                "encoded_iri_count": 1,
                "security_labels_rendered_as_text": True,
                "encoded_iris_loaded": True,
                "script_executed": False,
                "injected_html_nodes": 0,
                "external_requests": [],
                "javascript_errors": [],
                "console_errors": [],
            },
        },
        "webvowl-runtime.json": {
            "contract_version": "1.0",
            "runtime_id": "kg-mnp-webvowl-runtime",
            "bind_host": "127.0.0.1",
            "port": 8080,
            "external_exposure": "FORBIDDEN",
            "runtime_internet_access": "FORBIDDEN",
            "image_digest": "sha256:" + "1" * 64,
            "smoke": {
                "status": "PASS",
                "errors": [],
                "egress_probe": {
                    "status": "PASS",
                    "connection_blocked": True,
                },
            },
        },
        "publication-attestation.json": attestation,
    }
    directory.mkdir(parents=True, exist_ok=True)
    for name, value in documents.items():
        (directory / name).write_text(
            json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n",
            encoding="utf-8",
        )
    return directory / "publication-attestation.json"


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

    def export_explicit_nquads(self, repository_id):
        assert repository_id.startswith("kg-mnp-")
        value = self.dataset.serialize(format="nquads")
        return value if isinstance(value, bytes) else value.encode("utf-8")

    def select(self, repository_id, query, *, timeout=5.0):
        assert repository_id.startswith("kg-mnp-")
        assert timeout <= 10
        result = self.dataset.query(query)
        return json.loads(result.serialize(format="json").decode("utf-8"))
