from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from ..modeling.dependencies import ROOT

SCHEMA = (
    "end_to_end_publication_manifest.schema.json",
    "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/publication/end-to-end-publication-manifest/1.0",
)
ATTESTATION = (
    "publication_attestation.schema.json",
    "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/publication/publication-attestation/1.0",
)


class PublicationContractError(ValueError):
    pass


def _unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise PublicationContractError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def load_publication_schema(name: str, root: Path = ROOT) -> dict[str, Any]:
    spec = (
        SCHEMA
        if name == "end-to-end-publication-manifest"
        else ATTESTATION
        if name == "publication-attestation"
        else None
    )
    if spec is None:
        raise PublicationContractError(f"unknown publication contract: {name}")
    filename, identifier = spec
    document = json.loads(
        (Path(root) / "schemas/publication" / filename).read_text(encoding="utf-8"),
        object_pairs_hook=_unique,
    )
    if (
        document.get("$schema") != "https://json-schema.org/draft/2020-12/schema"
        or document.get("$id") != identifier
    ):
        raise PublicationContractError(f"invalid publication schema: {name}")
    Draft202012Validator.check_schema(document)
    return document


def validate_publication_contract(
    name: str, payload: Mapping[str, Any], root: Path = ROOT
) -> None:
    errors = sorted(
        Draft202012Validator(
            load_publication_schema(name, root), format_checker=FormatChecker()
        ).iter_errors(payload),
        key=lambda e: list(e.absolute_path),
    )
    if errors:
        raise PublicationContractError(f"{name}: {errors[0].message}")
    if name == "end-to-end-publication-manifest":
        _validate_manifest_semantics(payload)
    if name == "publication-attestation":
        _validate_attestation_semantics(payload)


def _validate_manifest_semantics(payload: Mapping[str, Any]) -> None:
    from ..modeling.canonical_json import semantic_hash
    from .identifiers import publication_id, publication_semantic_hash

    digest = publication_semantic_hash(payload)
    if (
        payload.get("publication_semantic_hash") != digest
        or payload.get("publication_id") != publication_id(digest)
        or payload.get("publication_status") != "READY_FOR_PRESENTATION"
    ):
        raise PublicationContractError("publication manifest identity/status mismatch")
    paths: set[str] = set()
    artifact_ids: set[str] = set()
    for record in payload["artifact_manifest"]:
        relative = str(record["relative_path"])
        posix = PurePosixPath(relative)
        windows = PureWindowsPath(relative)
        if (
            "\\" in relative
            or posix.is_absolute()
            or windows.is_absolute()
            or windows.drive
            or ".." in posix.parts
            or relative != posix.as_posix()
        ):
            raise PublicationContractError(
                f"unsafe publication artifact path: {relative}"
            )
        expected_id = "urn:kg-mnp:publication-artifact:" + semantic_hash(
            {
                key: record[key]
                for key in (
                    "relative_path",
                    "role",
                    "byte_sha256",
                    "semantic_sha256",
                )
            }
        )
        if record["artifact_id"] != expected_id:
            raise PublicationContractError("publication artifact identity mismatch")
        if relative in paths or record["artifact_id"] in artifact_ids:
            raise PublicationContractError(
                "publication artifact paths and IDs must be unique"
            )
        paths.add(relative)
        artifact_ids.add(record["artifact_id"])


def _validate_attestation_semantics(payload: Mapping[str, Any]) -> None:
    if payload.get("status") != "PUBLICATION_VERIFIED":
        return
    if payload.get("coverage_status") != "PASS":
        raise PublicationContractError(
            "PUBLICATION_VERIFIED requires coverage_status=PASS"
        )
    if payload.get("browser_status") != "PASS":
        raise PublicationContractError(
            "PUBLICATION_VERIFIED requires browser_status=PASS"
        )
    if payload.get("graphdb_tbox_semantic_hash") != payload.get(
        "stage03_tbox_semantic_hash"
    ):
        raise PublicationContractError(
            "PUBLICATION_VERIFIED requires equal GraphDB/Stage 03 TBox hashes"
        )
    from ..webvowl.policy import (
        AUDITED_NORMALIZED_SHA256,
        AUDITED_RAW_SHA256,
        OWL2VOWL_SHA,
        WEBVOWL_SHA,
    )

    publication_id = str(payload.get("publication_id", ""))
    publication_hash = publication_id.rsplit(":", 1)[-1]
    if payload.get("publication_semantic_hash") != publication_hash:
        raise PublicationContractError(
            "PUBLICATION_VERIFIED publication ID/hash mismatch"
        )
    visualization_hash = str(payload.get("visualization_semantic_hash", ""))
    visualization_id = str(payload.get("visualization_id", ""))
    if visualization_id != f"urn:kg-mnp:visualization:{visualization_hash}":
        raise PublicationContractError(
            "PUBLICATION_VERIFIED visualization ID/hash mismatch"
        )
    if payload.get("webvowl_upstream_commit") != WEBVOWL_SHA:
        raise PublicationContractError("PUBLICATION_VERIFIED WebVOWL lock mismatch")
    if payload.get("owl2vowl_upstream_commit") != OWL2VOWL_SHA:
        raise PublicationContractError("PUBLICATION_VERIFIED OWL2VOWL lock mismatch")
    if payload.get("raw_vowl_hash") != AUDITED_RAW_SHA256:
        raise PublicationContractError("PUBLICATION_VERIFIED raw VOWL hash mismatch")
    if payload.get("normalized_vowl_hash") != AUDITED_NORMALIZED_SHA256:
        raise PublicationContractError(
            "PUBLICATION_VERIFIED normalized VOWL hash mismatch"
        )


def validate_publication_attestation_evidence(
    attestation: Mapping[str, Any],
    *,
    publication_manifest: Mapping[str, Any],
    visualization_manifest: Mapping[str, Any],
    coverage: Mapping[str, Any],
    representation_loss: Mapping[str, Any],
    tbox_equivalence: Mapping[str, Any],
    upstream_lock: Mapping[str, Any],
    browser_smoke: Mapping[str, Any],
    webvowl_runtime: Mapping[str, Any],
) -> None:
    """Bind a runtime attestation to the co-located authority artifacts."""
    validate_publication_contract("publication-attestation", attestation)
    validate_publication_contract(
        "end-to-end-publication-manifest", publication_manifest
    )
    from ..compilation.manifest import json_bytes
    from ..modeling.canonical_json import semantic_hash
    from ..webvowl.contracts import validate_webvowl_contract

    validate_webvowl_contract("visualization-manifest", visualization_manifest)
    validate_webvowl_contract("coverage-report", coverage)
    validate_webvowl_contract("representation-loss", representation_loss)
    if attestation.get("publication_id") != publication_manifest.get("publication_id"):
        raise PublicationContractError("attestation publication is not authoritative")
    if attestation.get("publication_semantic_hash") != publication_manifest.get(
        "publication_semantic_hash"
    ):
        raise PublicationContractError(
            "attestation publication hash is not authoritative"
        )
    if attestation.get("visualization_id") != visualization_manifest.get(
        "visualization_id"
    ) or attestation.get("visualization_semantic_hash") != visualization_manifest.get(
        "visualization_semantic_hash"
    ):
        raise PublicationContractError(
            "attestation visualization identity is not authoritative"
        )
    for field in (
        "visualization_id",
        "visualization_semantic_hash",
        "ontology_baseline_id",
        "ontology_version",
        "ontology_release_source_hash",
        "webvowl_upstream_commit",
        "owl2vowl_upstream_commit",
    ):
        if publication_manifest.get(field) != visualization_manifest.get(field):
            raise PublicationContractError(
                f"publication/visualization authority mismatch: {field}"
            )
    for field in ("webvowl_upstream_commit", "owl2vowl_upstream_commit"):
        if attestation.get(field) != visualization_manifest.get(field):
            raise PublicationContractError(
                f"attestation visualization lock mismatch: {field}"
            )
    if attestation.get("raw_vowl_hash") != visualization_manifest.get(
        "raw_converter_sha256"
    ) or attestation.get("normalized_vowl_hash") != visualization_manifest.get(
        "normalized_vowl_sha256"
    ):
        raise PublicationContractError("attestation VOWL hashes are not authoritative")
    if attestation.get("coverage_status") != coverage.get("status"):
        raise PublicationContractError("attestation coverage is not authoritative")
    if visualization_manifest.get("missing_required_term_count") != len(
        coverage.get("missing_required_terms", [])
    ) or visualization_manifest.get("unexpected_project_term_count") != len(
        coverage.get("unexpected_project_terms", [])
    ):
        raise PublicationContractError(
            "visualization manifest coverage counts are not authoritative"
        )
    if visualization_manifest.get("representation_loss_report_hash") != semantic_hash(
        representation_loss
    ):
        raise PublicationContractError(
            "visualization representation-loss hash is not authoritative"
        )
    if (
        attestation.get("graphdb_tbox_semantic_hash")
        != tbox_equivalence.get("graphdb_tbox_semantic_hash")
        or attestation.get("stage03_tbox_semantic_hash")
        != tbox_equivalence.get("stage03_tbox_semantic_hash")
        or tbox_equivalence.get("status") != "PASS"
        or tbox_equivalence.get("equal") is not True
    ):
        raise PublicationContractError("attestation TBox evidence is not authoritative")
    if visualization_manifest.get("tbox_source_semantic_hash") != attestation.get(
        "stage03_tbox_semantic_hash"
    ):
        raise PublicationContractError(
            "visualization source TBox is not the attested GraphDB TBox"
        )

    artifacts = {
        str(record.get("relative_path")): record
        for record in publication_manifest.get("artifact_manifest", [])
        if isinstance(record, Mapping)
    }
    for relative, document in (
        ("visualization/visualization-manifest.json", visualization_manifest),
        ("verification/ontology-visualization-coverage.json", coverage),
        ("verification/representation-loss.json", representation_loss),
        ("source/upstream-lock.json", upstream_lock),
    ):
        record = artifacts.get(relative)
        data = json_bytes(document)
        if (
            record is None
            or record.get("byte_sha256")
            != __import__("hashlib").sha256(data).hexdigest()
            or record.get("semantic_sha256") != semantic_hash(document)
        ):
            raise PublicationContractError(
                f"runtime report is not the published artifact: {relative}"
            )

    if (
        browser_smoke.get("status") != "PASS"
        or browser_smoke.get("canonical_vowl_loaded") is not True
        or int(browser_smoke.get("class_nodes", 0)) <= 0
        or int(browser_smoke.get("property_nodes", 0)) <= 0
        or int(browser_smoke.get("svg_count", 0)) <= 0
        or browser_smoke.get("javascript_errors") != []
        or browser_smoke.get("console_errors") != []
        or browser_smoke.get("external_requests") != []
        or browser_smoke.get("browser_http_egress_probe_blocked") is not True
        or browser_smoke.get("browser_websocket_egress_probe_blocked") is not True
        or browser_smoke.get("loopback_proxy_egress_probe", {}).get("status") != "PASS"
    ):
        raise PublicationContractError("browser smoke evidence is not verified")
    for field in (
        "browser_name",
        "browser_version",
        "browser_revision",
        "playwright_version",
    ):
        if browser_smoke.get(field) != attestation.get(field):
            raise PublicationContractError(f"browser attestation mismatch: {field}")
    security = browser_smoke.get("security_probe")
    if (
        not isinstance(security, Mapping)
        or security.get("status") != "PASS"
        or int(security.get("security_label_count", 0)) < 3
        or int(security.get("encoded_iri_count", 0)) < 1
        or security.get("security_labels_rendered_as_text") is not True
        or security.get("encoded_iris_loaded") is not True
        or security.get("script_executed") is not False
        or int(security.get("injected_html_nodes", -1)) != 0
        or security.get("external_requests") != []
        or security.get("javascript_errors") != []
        or security.get("console_errors") != []
    ):
        raise PublicationContractError("browser security evidence is not verified")

    smoke = webvowl_runtime.get("smoke")
    if (
        webvowl_runtime.get("bind_host") != "127.0.0.1"
        or webvowl_runtime.get("port") != 8080
        or webvowl_runtime.get("external_exposure") != "FORBIDDEN"
        or webvowl_runtime.get("runtime_internet_access") != "FORBIDDEN"
        or webvowl_runtime.get("image_digest")
        != attestation.get("runtime_image_digest")
        or not isinstance(smoke, Mapping)
        or smoke.get("status") != "PASS"
        or smoke.get("errors") != []
        or smoke.get("egress_probe", {}).get("status") != "PASS"
        or smoke.get("egress_probe", {}).get("connection_blocked") is not True
    ):
        raise PublicationContractError("WebVOWL runtime evidence is not verified")
