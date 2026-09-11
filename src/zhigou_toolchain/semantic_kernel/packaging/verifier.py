"""Strict closed-set directory verifier for portable ontology packages."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from rdflib import Dataset, Graph

from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.modeling.control_plane.confirmation import (
    verify_confirmed_package,
)

from ..artifacts import semantic_sha256
from ..contracts import verify_artifact
from ..errors import PackageError
from ..identifiers import graph_iri
from ..rdf.canonical import graph_semantic_digest
from ..security import scan_prohibited_text, validate_relative_path
from .manifest import semantic_payload_identity_digest, verify_package_manifest


def verify_package(package_directory: Path | str) -> dict[str, Any]:
    root = Path(package_directory).resolve(strict=True)
    if not root.is_dir() or root.is_symlink():
        raise PackageError("package root is not a safe directory")
    manifest_path = root / "ontology-package.json"
    lock_path = root / "ontology-package.lock.json"
    if any(path.is_symlink() or not path.is_file() for path in (manifest_path, lock_path)):
        raise PackageError("package manifest or lock is missing/unsafe")
    try:
        manifest = json.loads(manifest_path.read_bytes())
        lock = json.loads(lock_path.read_bytes())
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PackageError(f"package authority JSON is invalid: {exc}") from exc
    try:
        verify_package_manifest(manifest)
    except Exception as exc:
        raise PackageError(str(exc)) from exc
    try:
        verify_artifact(lock, id_field="lock_id", urn_kind="ontology-package-lock", contract="ontology-package-lock")
    except Exception as exc:
        raise PackageError(str(exc)) from exc
    if manifest["package_status"] != "VALIDATED_UNPUBLISHED" or lock["package_id"] != manifest["package_id"]:
        raise PackageError("package authority identity/status mismatch")
    if hashlib.sha256(manifest_path.read_bytes()).hexdigest() != lock["manifest_file_sha256"] or semantic_hash(manifest) != lock["manifest_semantic_sha256"]:
        raise PackageError("package manifest digest mismatch")
    declared = {"ontology-package.json", "ontology-package.lock.json"}
    fields = ("path", "role", "byte_sha256", "semantic_sha256", "size_bytes")
    manifest_artifacts = {
        row["path"]: {field: row[field] for field in fields}
        for row in manifest["artifacts"]
    }
    lock_artifacts = {
        row["path"]: {field: row[field] for field in fields}
        for row in lock["payload_files"]
    }
    if manifest_artifacts != lock_artifacts:
        raise PackageError("manifest and package lock artifact closures differ")
    for row in lock["payload_files"]:
        relative = validate_relative_path(row["path"])
        try:
            path = (root / relative).resolve(strict=True)
        except OSError as exc:
            raise PackageError(f"package payload is missing: {relative}") from exc
        if root not in path.parents or path.is_symlink() or not path.is_file():
            raise PackageError("package payload path is missing or unsafe")
        data = path.read_bytes()
        if len(data) != row["size_bytes"] or hashlib.sha256(data).hexdigest() != row["byte_sha256"] or semantic_sha256(relative, data) != row["semantic_sha256"]:
            raise PackageError(f"package payload integrity failed: {relative}")
        if scan_prohibited_text(data):
            raise PackageError(f"package payload contains prohibited content: {relative}")
        declared.add(relative)
    actual = set()
    for path in root.rglob("*"):
        if path.is_symlink() or (not path.is_file() and not path.is_dir()):
            raise PackageError("package contains a symlink or non-regular entry")
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
    if actual != declared:
        raise PackageError(f"package closed set differs: missing={sorted(declared-actual)}, extra={sorted(actual-declared)}")
    try:
        plan = json.loads((root / "source" / "semantic-compilation-plan.json").read_bytes())
        verify_artifact(plan, id_field="plan_id", urn_kind="semantic-compilation-plan", contract="semantic-compilation-plan")
        verify_package_manifest(manifest, plan=plan)
        confirmed = json.loads((root / "source" / "confirmed-modeling-package.json").read_bytes())
        verify_confirmed_package(confirmed)
        snapshot = json.loads((root / "source" / "semantic-compiler-snapshot.json").read_bytes())
        verify_artifact(snapshot, id_field="snapshot_id", urn_kind="semantic-compiler-snapshot", contract="semantic-compiler-snapshot")
        attestation = json.loads((root / "source" / "compiler-input-attestation.json").read_bytes())
        verify_artifact(attestation, id_field="attestation_id", urn_kind="compiler-input-attestation", contract="compiler-input-attestation")
        if (
            manifest["source_confirmed_package"] != confirmed["package_id"]
            or manifest["compiler_snapshot"] != snapshot["snapshot_id"]
            or plan["confirmed_package_id"] != confirmed["package_id"]
            or plan["compiler_snapshot_id"] != snapshot["snapshot_id"]
            or plan["compiler_input_attestation_id"] != attestation["attestation_id"]
        ):
            raise ValueError("package source authorities are not mutually bound")
        dataset = json.loads((root / "dataset" / "rdf-dataset-manifest.json").read_bytes())
        verify_artifact(dataset, id_field="dataset_id", urn_kind="rdf-dataset-manifest", contract="rdf-dataset-manifest")
        if dataset["graphs"] != manifest["graphs"] or dataset["dataset_semantic_digest"] != manifest["semantic_summary"]["semantic_dataset_digest"]:
            raise ValueError("package dataset manifest differs from package semantic summary")
        parsed_dataset = Dataset()
        parsed_dataset.parse(
            data=(root / "dataset" / "dataset.nq").read_text(encoding="utf-8"),
            format="nquads",
        )
        graphs_by_iri: dict[str, Graph] = {}
        for subject, predicate, obj, context in parsed_dataset.quads(
            (None, None, None, None)
        ):
            graph_ref = context.identifier if hasattr(context, "identifier") else context
            graph = graphs_by_iri.setdefault(str(graph_ref), Graph())
            graph.add((subject, predicate, obj))
        declared_graph_iris = {row["graph_iri"] for row in dataset["graphs"]}
        serialized_graph_iris = {
            row["graph_iri"] for row in dataset["graphs"] if row["triple_count"] > 0
        }
        # N-Quads has no representation for an empty named graph. Such graph
        # roles remain authoritative manifest entries, but correctly contribute
        # no serialized quads.
        if set(graphs_by_iri) != serialized_graph_iris:
            raise ValueError("dataset named-graph closure differs from its manifest")
        for graph_iri_value in declared_graph_iris:
            graphs_by_iri.setdefault(graph_iri_value, Graph())
        graph_digests: dict[str, str] = {}
        for row in dataset["graphs"]:
            expected_graph = graph_iri(
                manifest["package_id"], row["role"], row["graph_semantic_digest"]
            )
            if row["graph_iri"] != expected_graph:
                raise ValueError("named graph IRI is not bound to the final Package ID")
            actual_graph = graphs_by_iri[row["graph_iri"]]
            actual_digest = graph_semantic_digest(actual_graph)
            if (
                len(actual_graph) != row["triple_count"]
                or actual_digest != row["graph_semantic_digest"]
            ):
                raise ValueError("dataset graph content differs from its graph record")
            graph_digests[row["role"]] = actual_digest
        mapping_plan = json.loads((root / "mappings" / "mapping-plan.json").read_bytes())
        verify_artifact(
            mapping_plan,
            id_field="mapping_plan_id",
            urn_kind="mapping-plan",
            contract="mapping-plan",
        )
        cq_plan = json.loads(
            (root / "validation" / "competency-question-test-plan.json").read_bytes()
        )
        verify_artifact(
            cq_plan,
            id_field="test_plan_id",
            urn_kind="competency-question-test-plan",
            contract="competency-question-test-plan",
        )
        identity_payload_digest = semantic_payload_identity_digest(
            graph_digests=graph_digests,
            mapping_plan_digest=mapping_plan["content_digest"],
            cq_test_plan_digest=cq_plan["content_digest"],
            attestation_digest=attestation["content_digest"],
            baseline_assets=manifest["baseline_dependencies"],
        )
        if identity_payload_digest != manifest["semantic_summary"]["identity_payload_digest"]:
            raise ValueError("normalized semantic payload identity digest mismatch")
        validation_specs = {
            "rdf-syntax-report.json": ("report_id", "rdf-syntax-validation-report", "rdf-syntax-validation-report"),
            "owl-profile-report.json": ("report_id", "owl-profile-report", "owl-profile-report"),
            "owl-consistency-report.json": ("report_id", "semantic-owl-consistency-report", "semantic-owl-consistency-report"),
            "shacl-validation-report.json": ("report_id", "semantic-shacl-validation-report", "semantic-shacl-validation-report"),
            "competency-question-test-report.json": ("report_id", "competency-question-test-report", "competency-question-test-report"),
            "provenance-closure-report.json": ("report_id", "provenance-closure-report", "provenance-closure-report"),
            "build-reproduction-report.json": ("report_id", "build-reproduction-report", "build-reproduction-report"),
            "ontology-package-validation-report.json": ("report_id", "ontology-package-validation-report", "ontology-package-validation-report"),
        }
        validated_reports = {}
        for name, (id_field, urn_kind, contract) in validation_specs.items():
            report = json.loads((root / "validation" / name).read_bytes())
            verify_artifact(report, id_field=id_field, urn_kind=urn_kind, contract=contract)
            validated_reports[report[id_field]] = report
        declared_reports = {row["report_id"]: row for row in manifest["validation_reports"]}
        if set(declared_reports) != set(validated_reports):
            raise ValueError("package validation report closure differs from the manifest")
        for report_id, report in validated_reports.items():
            if declared_reports[report_id]["content_digest"] != report["content_digest"]:
                raise ValueError("package validation report digest mismatch")
        required_statuses = {
            "KG_MNP_RDF_SYNTAX_VALIDATION_REPORT": "PASSED",
            "KG_MNP_OWL_PROFILE_REPORT": "PASSED",
            "KG_MNP_SEMANTIC_OWL_CONSISTENCY_REPORT": "CONSISTENT",
            "KG_MNP_SEMANTIC_SHACL_VALIDATION_REPORT": "CONFORMS",
            "KG_MNP_PROVENANCE_CLOSURE_REPORT": "PASSED",
            "KG_MNP_BUILD_REPRODUCTION_REPORT": "PASSED",
            "KG_MNP_ONTOLOGY_PACKAGE_VALIDATION_REPORT": "VALID",
        }
        for report in validated_reports.values():
            expected_status = required_statuses.get(report["manifest_kind"])
            if expected_status is not None and report.get("status") != expected_status:
                raise ValueError("a required package validation gate did not pass")
            if report["manifest_kind"] == "KG_MNP_COMPETENCY_QUESTION_TEST_REPORT" and report.get("required_passed") is not True:
                raise ValueError("required competency questions did not pass")
            if report["manifest_kind"] == "KG_MNP_PROVENANCE_CLOSURE_REPORT" and report.get("coverage_basis_points") != 10000:
                raise ValueError("package provenance closure is incomplete")
            if report["manifest_kind"] == "KG_MNP_BUILD_REPRODUCTION_REPORT" and report["archive_sha256_first"] != report["archive_sha256_second"]:
                raise ValueError("package reproduction hashes differ")
    except (KeyError, TypeError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise PackageError(f"package identity closure failed: {exc}") from exc
    return {"package_id": manifest["package_id"], "lock_id": lock["lock_id"], "status": "VALID", "file_count": len(actual)}
