from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Callable

import pytest

from kg_mnp_demo.application.errors import ApplicationError, ErrorCode
from kg_mnp_demo.application.publication_binding import PublicationBinding
from kg_mnp_demo.compilation.manifest import json_bytes
from kg_mnp_demo.graphdb.contracts import validate_graphdb_contract
from kg_mnp_demo.graphdb.identifiers import (
    publication_id as graphdb_publication_id,
)
from kg_mnp_demo.graphdb.identifiers import (
    publication_semantic_hash as graphdb_publication_semantic_hash,
)
from kg_mnp_demo.graphdb.identifiers import repository_id_for_publication
from kg_mnp_demo.modeling.canonical_json import semantic_hash
from kg_mnp_demo.modeling.registry import validate_contract
from kg_mnp_demo.modeling.review_identifiers import (
    confirmed_package_id,
    decision_log_hash,
    package_semantic_hash,
)
from kg_mnp_demo.publication.contracts import (
    validate_publication_attestation_evidence,
    validate_publication_contract,
)
from kg_mnp_demo.publication.manifest import build_publication_manifest

from ._phase01_helpers import ROOT, publication_attestation_report

PACKAGE = ROOT / "examples/publication/expected/full-confirmation"


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _write(path: Path, value: dict) -> None:
    path.write_bytes(json_bytes(value))


def _source_document(package: Path, relative: str) -> dict:
    return _load(package / relative)


def _mutate_cleaned_data(package: Path, manifest: dict) -> None:
    relative = "source/cleaned-partial-data.json"
    document = _source_document(package, relative)
    document["input_context"]["attacker_rehashed"] = True
    validate_contract("cleaned-partial-data", document)
    _write(package / relative, document)
    manifest["cleaned_partial_data_hash"] = semantic_hash(document)


def _mutate_review_log(package: Path, manifest: dict) -> None:
    relative = "source/review-decision-log.json"
    document = _source_document(package, relative)
    document["reviewer"]["display_name"] = "Rehashed Attacker"
    document["log_hash"] = decision_log_hash(document)
    validate_contract("review-decision-log", document)
    assert document["log_hash"] == decision_log_hash(document)
    _write(package / relative, document)
    manifest["review_decision_log_id"] = document["decision_log_id"]
    manifest["review_decision_log_hash"] = document["log_hash"]


def _mutate_confirmed_package(package: Path, manifest: dict) -> None:
    relative = "source/confirmed-modeling-package.json"
    document = _source_document(package, relative)
    document["publication_manifest"]["attacker_rehashed"] = True
    digest = package_semantic_hash(document)
    document["package_semantic_hash"] = digest
    document["package_id"] = confirmed_package_id(digest)
    validate_contract("confirmed-modeling-package", document)
    assert document["package_semantic_hash"] == package_semantic_hash(document)
    assert document["package_id"] == confirmed_package_id(document)
    _write(package / relative, document)
    manifest["confirmed_modeling_package_id"] = document["package_id"]
    manifest["confirmed_modeling_package_hash"] = digest


def _mutate_graphdb_manifest(package: Path, manifest: dict) -> None:
    relative = "source/graphdb-import-manifest.json"
    document = _source_document(package, relative)
    document["assembled_dataset_semantic_hash"] = "0" * 64
    digest = graphdb_publication_semantic_hash(document)
    document["publication_semantic_hash"] = digest
    document["publication_id"] = graphdb_publication_id(digest)
    document["repository_id"] = repository_id_for_publication(digest)
    validate_graphdb_contract("graphdb-import-manifest", document)
    _write(package / relative, document)
    manifest["graphdb_publication_id"] = document["publication_id"]
    manifest["graphdb_publication_semantic_hash"] = digest


def _delete_artifact(package: Path, _manifest: dict) -> None:
    (package / "verification/determinism-report.json").unlink()


def _insert_artifact(package: Path, _manifest: dict) -> None:
    path = package / "attacker/extra.json"
    path.parent.mkdir(parents=True)
    _write(path, {"contract_version": "1.0", "attacker_rehashed": True})


def _rehash_attacker_controlled_evidence(package: Path, report: Path) -> dict:
    previous = _load(package / "publication-manifest.json")
    excluded = {
        "artifact_manifest",
        "contract_version",
        "publication_id",
        "publication_semantic_hash",
        "publication_status",
    }
    lineage = {key: value for key, value in previous.items() if key not in excluded}
    artifacts = {
        path.relative_to(package).as_posix(): path.read_bytes()
        for path in package.rglob("*")
        if path.is_file() and path.name != "publication-manifest.json"
    }
    manifest = build_publication_manifest(lineage=lineage, artifact_bytes=artifacts)
    _write(package / "publication-manifest.json", manifest)
    _write(report / "publication-manifest.json", manifest)
    attestation = _load(report / "publication-attestation.json")
    attestation["publication_id"] = manifest["publication_id"]
    attestation["publication_semantic_hash"] = manifest["publication_semantic_hash"]
    _write(report / "publication-attestation.json", attestation)
    return manifest


def _assert_attacker_package_is_internally_closed(package: Path, report: Path) -> None:
    manifest = _load(package / "publication-manifest.json")
    validate_publication_contract("end-to-end-publication-manifest", manifest)
    expected = {"publication-manifest.json"}
    for record in manifest["artifact_manifest"]:
        relative = record["relative_path"]
        expected.add(relative)
        assert hashlib.sha256((package / relative).read_bytes()).hexdigest() == record[
            "byte_sha256"
        ]
    actual = {
        path.relative_to(package).as_posix()
        for path in package.rglob("*")
        if path.is_file()
    }
    assert actual == expected
    validate_publication_attestation_evidence(
        _load(report / "publication-attestation.json"),
        publication_manifest=_load(report / "publication-manifest.json"),
        visualization_manifest=_load(report / "visualization-manifest.json"),
        coverage=_load(report / "ontology-visualization-coverage.json"),
        representation_loss=_load(report / "representation-loss.json"),
        tbox_equivalence=_load(report / "tbox-equivalence.json"),
        upstream_lock=_load(report / "upstream-lock.json"),
        browser_smoke=_load(report / "browser-smoke.json"),
        webvowl_runtime=_load(report / "webvowl-runtime.json"),
    )


ATTACKS: tuple[tuple[str, Callable[[Path, dict], None]], ...] = (
    ("cleaned-partial-data", _mutate_cleaned_data),
    ("review-decision-log", _mutate_review_log),
    ("confirmed-modeling-package", _mutate_confirmed_package),
    ("graphdb-import-manifest", _mutate_graphdb_manifest),
    ("deleted-artifact", _delete_artifact),
    ("inserted-artifact", _insert_artifact),
)


@pytest.mark.parametrize(("attack_name", "mutate"), ATTACKS, ids=[item[0] for item in ATTACKS])
def test_rehashed_self_consistent_publication_cannot_replace_frozen_authority(
    tmp_path: Path,
    attack_name: str,
    mutate: Callable[[Path, dict], None],
) -> None:
    package = tmp_path / f"package-{attack_name}"
    report = tmp_path / f"report-{attack_name}"
    shutil.copytree(PACKAGE, package)
    publication_attestation_report(report, "full-confirmation")
    manifest = _load(package / "publication-manifest.json")
    mutate(package, manifest)
    _write(package / "publication-manifest.json", manifest)
    _rehash_attacker_controlled_evidence(package, report)
    _assert_attacker_package_is_internally_closed(package, report)

    with pytest.raises(ApplicationError) as caught:
        PublicationBinding.verify(
            package,
            report / "publication-attestation.json",
            publication_scenario="full-confirmation",
        )

    assert caught.value.code == ErrorCode.FOUNDATION_NOT_VERIFIED
