from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from rdflib import Dataset

from .._path_security import UnsafePathError, safe_artifact_path, validated_directory
from ..compilation.manifest import json_bytes
from ..compilation.policy import load_compiler_policy
from ..compilation.rdf_canonical import canonical_nquads
from ..graphdb.package_validator import validate_graphdb_import_package
from ..graphdb.tbox_assembler import assemble_runtime_tbox
from ..modeling.canonical_json import semantic_hash
from ..modeling.dependencies import ROOT, load_modeling_dependencies
from ..modeling.package_validation import (
    load_functional_property_iris,
    load_term_type_index,
)
from ..modeling.review_policy import load_review_policy
from ..modeling.semantic_validation import (
    validate_cleaned_partial_data_semantics,
    validate_confirmed_package_against_authorities,
    validate_mapping_rules_semantics,
    validate_modeling_proposal_semantics,
    validate_proposal_policy_semantics,
    validate_review_decision_log_semantics,
    validate_terminology_profile_semantics,
)
from ..webvowl.package_builder import build_webvowl_visualization_package
from .manifest import build_publication_manifest


class PublicationPackageError(ValueError):
    pass


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise PublicationPackageError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _load(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique)
    except Exception as exc:
        raise PublicationPackageError(
            f"cannot read publication authority {path}: {exc}"
        ) from exc


def _authority(value: Mapping[str, Any] | None, path: Path) -> dict[str, Any]:
    return dict(value) if value is not None else _load(path)


def _graphdb_package_tbox_hash(
    package_directory: Path,
    *,
    root: Path,
    baseline: Mapping[str, Any],
    graphdb_manifest: Mapping[str, Any],
) -> str:
    try:
        dataset_path = safe_artifact_path(
            package_directory,
            "import/knowledge-graph.nq",
            label="GraphDB import dataset",
        )
    except UnsafePathError as exc:
        raise PublicationPackageError(str(exc)) from exc
    dataset = Dataset()
    try:
        dataset.parse(data=dataset_path.read_text(encoding="utf-8"), format="nquads")
    except Exception as exc:
        raise PublicationPackageError(
            f"cannot parse GraphDB import dataset: {exc}"
        ) from exc
    tbox = assemble_runtime_tbox(root=root, baseline=baseline)
    graph_iris = {str(value) for value in tbox["named_graphs"]}
    quads = [
        quad
        for quad in dataset.quads((None, None, None, None))
        if str(quad[3]) in graph_iris
    ]
    if len(quads) != int(graphdb_manifest["tbox_triple_count"]):
        raise PublicationPackageError("GraphDB package TBox count mismatch")
    return hashlib.sha256(canonical_nquads(quads)).hexdigest()


def build_end_to_end_publication_package(
    *,
    cleaned_partial_data: Mapping[str, Any] | None = None,
    proposal: Mapping[str, Any] | None = None,
    review_decision_log: Mapping[str, Any] | None = None,
    confirmed_modeling_package: Mapping[str, Any] | None = None,
    compilation_manifest: Mapping[str, Any] | None = None,
    graphdb_manifest: Mapping[str, Any] | None = None,
    compilation_directory: Path | None = None,
    graphdb_package_directory: Path | None = None,
    ontology_baseline: Mapping[str, Any] | None = None,
    visualization_package: Mapping[str, Any] | None = None,
    scenario: str = "full-confirmation",
    output_dir: Path | None = None,
    force: bool = False,
    root: Path = ROOT,
    graphdb_tbox_semantic_hash: str | None = None,
    **_: Any,
) -> dict[str, Any]:
    try:
        root = validated_directory(Path(root), label="publication authority root")
    except UnsafePathError as exc:
        raise PublicationPackageError(str(exc)) from exc
    dependencies = load_modeling_dependencies(root=root)
    baseline = dict(ontology_baseline or dependencies["ontology_baseline"])
    source_name = (
        "conflicting-values" if scenario == "issue-resolution" else "partial-basic"
    )
    cleaned = _authority(
        cleaned_partial_data, root / "examples/modeling/inputs" / f"{source_name}.json"
    )
    proposal_doc = _authority(
        proposal,
        root / "examples/modeling/expected-proposals" / f"{source_name}.proposal.json",
    )
    review = _authority(
        review_decision_log,
        root / "examples/review/expected-logs" / f"{scenario}.log.json",
    )
    confirmed = _authority(
        confirmed_modeling_package,
        root / "examples/review/expected-packages" / f"{scenario}.package.json",
    )
    for supplied, label, required in (
        (
            compilation_manifest,
            "compilation",
            {"compilation_id", "compilation_semantic_hash", "release_status"},
        ),
        (
            graphdb_manifest,
            "GraphDB",
            {"publication_id", "publication_semantic_hash", "release_status"},
        ),
    ):
        if supplied is not None and not required <= set(supplied):
            raise PublicationPackageError(
                f"supplied {label} manifest is not authoritative"
            )
    mapping_rules = dependencies["mapping_rules"]
    terminology_profile = dependencies["terminology_profile"]
    proposal_policy = dependencies["proposal_policy"]
    review_policy = load_review_policy(
        root / "config/modeling/review-policy-1.0.0.yaml"
    )
    compiler_policy = load_compiler_policy(
        root / "config/compilation/compiler-policy-1.0.0.yaml"
    )
    term_inventory = root / "docs/ontology/term-inventory.csv"
    term_types = load_term_type_index(term_inventory)
    functional_properties = load_functional_property_iris(term_inventory)
    try:
        validate_cleaned_partial_data_semantics(cleaned)
        validate_mapping_rules_semantics(
            mapping_rules,
            baseline,
            terminology_profile,
            term_iris=dependencies["term_iris"],
        )
        validate_terminology_profile_semantics(
            terminology_profile,
            baseline,
            term_iris=dependencies["term_iris"],
        )
        validate_proposal_policy_semantics(proposal_policy)
        validate_modeling_proposal_semantics(proposal_doc, cleaned, mapping_rules)
        validate_review_decision_log_semantics(
            review,
            proposal_doc,
            cleaned_partial_data=cleaned,
            ontology_baseline=baseline,
            mapping_rules=mapping_rules,
            review_policy=review_policy,
            require_final=True,
            term_types=term_types,
        )
        validate_confirmed_package_against_authorities(
            confirmed,
            cleaned,
            proposal_doc,
            review,
            baseline,
            mapping_rules,
            terminology_profile,
            proposal_policy,
            review_policy,
            term_types=term_types,
            functional_property_iris=functional_properties,
        )
    except Exception as exc:
        raise PublicationPackageError(
            f"Stage 04/05 authority validation failed: {exc}"
        ) from exc

    try:
        compilation_dir = validated_directory(
            Path(
                compilation_directory
                or root / "examples/compilation/expected" / scenario
            ),
            label="Stage 06 compilation authority package",
        )
        graphdb_dir = validated_directory(
            Path(
                graphdb_package_directory
                or root / "examples/graphdb/expected" / scenario
            ),
            label="Stage 07 GraphDB authority package",
        )
    except UnsafePathError as exc:
        raise PublicationPackageError(str(exc)) from exc
    try:
        graphdb_validation = validate_graphdb_import_package(
            graphdb_dir,
            compilation_directory=compilation_dir,
            cleaned_partial_data=cleaned,
            proposal=proposal_doc,
            final_review_decision_log=review,
            confirmed_modeling_package=confirmed,
            ontology_baseline=baseline,
            mapping_rules=mapping_rules,
            terminology_profile=terminology_profile,
            proposal_policy=proposal_policy,
            review_policy=review_policy,
            compiler_policy=compiler_policy,
            root=root,
        )
    except Exception as exc:
        raise PublicationPackageError(
            f"Stage 06/07 authority validation failed: {exc}"
        ) from exc
    if (
        graphdb_validation.get("source_package_valid") is not True
        or graphdb_validation.get("shacl_status") != "CONFORMS"
        or graphdb_validation.get("owl_consistency_status") != "CONSISTENT"
        or graphdb_validation.get("valid") is not True
        or graphdb_validation.get("release_status") != "FORMALLY_VALIDATED"
    ):
        raise PublicationPackageError("Stage 06/07 authorities are not validated")

    compilation = _load(compilation_dir / "compilation-manifest.json")
    graphdb = _load(graphdb_dir / "graphdb-import-manifest.json")
    if compilation_manifest is not None and dict(compilation_manifest) != compilation:
        raise PublicationPackageError(
            "supplied compilation manifest is not authoritative"
        )
    if graphdb_manifest is not None and dict(graphdb_manifest) != graphdb:
        raise PublicationPackageError("supplied GraphDB manifest is not authoritative")
    package_tbox_hash = _graphdb_package_tbox_hash(
        graphdb_dir,
        root=root,
        baseline=baseline,
        graphdb_manifest=graphdb,
    )
    if (
        graphdb_tbox_semantic_hash is not None
        and graphdb_tbox_semantic_hash != package_tbox_hash
    ):
        raise PublicationPackageError(
            "live GraphDB TBox hash differs from the validated Stage 07 package"
        )
    effective_tbox_hash = graphdb_tbox_semantic_hash or package_tbox_hash
    expected_visualization = build_webvowl_visualization_package(
        root=root,
        ontology_baseline=baseline,
        graphdb_tbox_semantic_hash=effective_tbox_hash,
    )
    if visualization_package is not None:
        supplied_files = visualization_package.get("files")
        if not isinstance(supplied_files, Mapping) or dict(supplied_files) != dict(
            expected_visualization["files"]
        ):
            raise PublicationPackageError(
                "supplied visualization package is not authoritative"
            )
    visualization = expected_visualization
    tbox_report = json.loads(
        visualization["files"]["verification/tbox-equivalence.json"].decode("utf-8")
    )
    if tbox_report.get("status") != "PASS" or tbox_report.get("equal") is not True:
        raise PublicationPackageError(
            "GraphDB/Stage 03 TBox equivalence is not verified"
        )
    visualization_manifest = visualization["manifest"]
    if visualization_manifest.get("release_status") != "VISUALIZATION_VALIDATED":
        raise PublicationPackageError("visualization package is not validated")

    def h(value: Mapping[str, Any]) -> str:
        return semantic_hash(value)

    lineage = {
        "cleaned_partial_data_hash": h(cleaned),
        "modeling_proposal_id": str(proposal_doc["proposal_id"]),
        "modeling_proposal_hash": str(proposal_doc["proposal_semantic_hash"]),
        "review_decision_log_id": str(review["decision_log_id"]),
        "review_decision_log_hash": str(review["log_hash"]),
        "confirmed_modeling_package_id": str(confirmed["package_id"]),
        "confirmed_modeling_package_hash": str(confirmed["package_semantic_hash"]),
        "compilation_id": str(compilation["compilation_id"]),
        "compilation_semantic_hash": str(compilation["compilation_semantic_hash"]),
        "graphdb_publication_id": str(graphdb["publication_id"]),
        "graphdb_publication_semantic_hash": str(graphdb["publication_semantic_hash"]),
        "visualization_id": visualization_manifest["visualization_id"],
        "visualization_semantic_hash": visualization_manifest[
            "visualization_semantic_hash"
        ],
        "ontology_baseline_id": baseline["baseline_id"],
        "ontology_version": baseline["ontology_version"],
        "ontology_release_source_hash": baseline["release_source_hash"],
        "webvowl_upstream_commit": visualization_manifest["webvowl_upstream_commit"],
        "owl2vowl_upstream_commit": visualization_manifest["owl2vowl_upstream_commit"],
    }
    files = {
        "source/cleaned-partial-data.json": json_bytes(cleaned),
        "source/modeling-proposal.json": json_bytes(proposal_doc),
        "source/review-decision-log.json": json_bytes(review),
        "source/confirmed-modeling-package.json": json_bytes(confirmed),
        "source/compilation-manifest.json": json_bytes(compilation),
        "source/graphdb-import-manifest.json": json_bytes(graphdb),
        "source/ontology-baseline.json": visualization["files"][
            "source/ontology-baseline.json"
        ],
        "source/webvowl-runtime-policy.yaml": visualization["files"][
            "source/webvowl-runtime-policy.yaml"
        ],
        "source/upstream-lock.json": visualization["files"][
            "source/upstream-lock.json"
        ],
        "visualization/kg-mnp.webvowl.json": visualization["files"][
            "visualization/kg-mnp.webvowl.json"
        ],
        "visualization/visualization-manifest.json": visualization["files"][
            "visualization/visualization-manifest.json"
        ],
        "verification/ontology-visualization-coverage.json": visualization["files"][
            "verification/ontology-visualization-coverage.json"
        ],
        "verification/representation-loss.json": visualization["files"][
            "verification/representation-loss.json"
        ],
        "verification/tbox-equivalence.json": visualization["files"][
            "verification/tbox-equivalence.json"
        ],
        "verification/abox-leakage-scan.json": visualization["files"][
            "verification/abox-leakage-scan.json"
        ],
        "verification/determinism-report.json": visualization["files"][
            "verification/determinism-report.json"
        ],
        "verification/normalization-exclusions.json": visualization["files"][
            "verification/normalization-exclusions.json"
        ],
    }
    manifest = build_publication_manifest(lineage=lineage, artifact_bytes=files)
    files["publication-manifest.json"] = json_bytes(manifest)
    if output_dir is not None:
        from ..compilation.artifacts import write_artifact_set

        write_artifact_set(Path(output_dir), files, force=force)
    return {
        "manifest": manifest,
        "files": files,
        "visualization": visualization,
        "lineage": lineage,
    }
