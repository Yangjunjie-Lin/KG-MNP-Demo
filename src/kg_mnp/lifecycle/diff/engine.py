"""Deterministic semantic diff over verified ontology packages."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rdflib import Graph, URIRef

from kg_mnp.contracts.canonical import canonical_json_bytes, semantic_hash, stable_urn
from kg_mnp.semantic_kernel.packaging.verifier import verify_package

from ..contracts import canonicalize
from ..errors import LifecycleError
from ..store import bind_identity
from .classification import classify_abox, classify_shacl, classify_tbox, worst

_COMPONENT_FILES = {
    "tbox": ("ontology/effective-tbox.nt",),
    "abox": ("data/abox.nt",),
    "shacl": ("shapes/effective-shapes.nt",),
    "mapping": ("mappings/mapping-plan.json",),
    "cq": ("validation/competency-question-test-plan.json",),
    "provenance": ("provenance/provenance.json", "provenance.json"),
}


def _parse_rdf(path: Path) -> set[str]:
    if not path.is_file():
        raise LifecycleError("SEMANTIC_DIFF_FAILED", f"component file is missing: {path.name}")
    graph = Graph()
    try:
        graph.parse(path, format="nt")
    except Exception as exc:  # rdflib exposes several parser exception types
        raise LifecycleError("SEMANTIC_DIFF_FAILED", f"RDF component cannot be parsed: {path.name}") from exc
    return {f"{subject.n3()} {predicate.n3()} {obj.n3()} ." for subject, predicate, obj in graph}


def _parse_json(path: Path) -> set[str]:
    if not path.is_file():
        raise LifecycleError("SEMANTIC_DIFF_FAILED", f"component file is missing: {path.name}")
    try:
        value = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as exc:
        raise LifecycleError("SEMANTIC_DIFF_FAILED", f"JSON component cannot be parsed: {path.name}") from exc
    rows = value if isinstance(value, list) else value.get("mappings", value.get("queries", value.get("items", [value]))) if isinstance(value, dict) else [value]
    if not isinstance(rows, list):
        rows = [rows]
    # Stable business keys make reordering invisible while preserving the full
    # structured value for an actual change.
    def key(row: Any) -> str:
        if isinstance(row, dict):
            for name in ("mapping_id", "query_id", "contract_id", "id", "name"):
                if row.get(name) is not None:
                    return str(row[name])
        return semantic_hash(row)
    return {"json:" + key(row) + "=" + semantic_hash(row) + ":" + canonical_json_bytes(row).decode("utf-8") for row in rows}


def _component(root: Path, relative: str, *, required: bool = False) -> set[str]:
    path = root / relative
    if relative.endswith(".json"):
        if not path.is_file() and not required:
            return set()
        return _parse_json(path)
    if not path.is_file() and not required:
        return set()
    return _parse_rdf(path)


def _package_parts(value: Any) -> tuple[dict[str, set[str]], dict[str, Any]]:
    if isinstance(value, dict):
        parts: dict[str, set[str]] = {}
        for component in ("tbox", "abox", "shacl", "mapping", "cq", "dependency", "annotation", "provenance", "metadata"):
            supplied = value.get(component, set())
            if isinstance(supplied, (set, list, tuple)):
                parts[component] = {str(item) for item in supplied}
            elif supplied in (None, ""):
                parts[component] = set()
            else:
                parts[component] = {str(supplied)}
        return parts, {"package_id": value.get("package_id"), "ontology_iri": value.get("ontology_iri", "urn:kg-mnp:ontology"), "version": value.get("version", "0.0.0")}
    path = Path(value)
    if not path.exists():
        raise LifecycleError("SEMANTIC_DIFF_FAILED", f"package entrypoint is missing: {path}")
    if path.is_file():
        # Kept for deterministic low-level RDF utility compatibility.  The
        # lifecycle directory entry point below remains package-only.
        return {"tbox": _parse_rdf(path), "abox": set(), "shacl": set(), "mapping": set(), "cq": set(), "dependency": set(), "annotation": set(), "provenance": set(), "metadata": set()}, {"package_id": None, "ontology_iri": "urn:kg-mnp:ontology", "version": "0.0.0"}
    manifest_path = path / "ontology-package.json"
    lock_path = path / "ontology-package.lock.json"
    if not manifest_path.is_file() or not lock_path.is_file():
        raise LifecycleError("SEMANTIC_DIFF_FAILED", "verified package manifest and lock are required")
    try:
        verify_package(path)
        manifest = json.loads(manifest_path.read_bytes())
    except Exception as exc:
        if isinstance(exc, LifecycleError):
            raise
        raise LifecycleError("SEMANTIC_DIFF_FAILED", "package verification failed") from exc
    parts = {
        "tbox": _component(path, "ontology/effective-tbox.nt", required=True),
        "abox": _component(path, "data/abox.nt"),
        "shacl": _component(path, "shapes/effective-shapes.nt"),
        "mapping": _component(path, "mappings/mapping-plan.json"),
        "cq": _component(path, "validation/competency-question-test-plan.json"),
        # A new output package digest is not a changed semantic dependency.
        # Compare the actual locked domain dependency set, not this build's
        # archive/file checksums (which change on any legitimate version).
        "dependency": {"json:domain-pack-lock=" + value for value in manifest.get("domain_pack_locks", [])},
        "annotation": set(), "provenance": set(),
        "metadata": {"json:package=" + semantic_hash({"package_name": manifest.get("package_name"), "package_version": manifest.get("package_version"), "ontology_identity": manifest.get("ontology_identity")})},
    }
    return parts, {"package_id": manifest.get("package_id"), "ontology_iri": manifest.get("ontology_identity", {}).get("ontology_iri", "urn:kg-mnp:ontology"), "version": manifest.get("package_version", "0.0.0")}


def _rdf_descriptor(value: str) -> tuple[str, str, str] | None:
    if value.startswith("json:"):
        return None
    graph = Graph()
    try:
        graph.parse(data=value + "\n", format="nt")
    except (ValueError, TypeError):
        return None
    triple = next(iter(graph), None)
    return tuple(item.n3() for item in triple) if triple else None


def _change(component: str, operation: str, subject: str, predicate: str | None, old: str | None, new: str | None, classification: str, rule: str, base: str, candidate: str) -> dict[str, Any]:
    affected = []
    for value in (subject, predicate or ""):
        if value.startswith(("<http://", "<https://", "<urn:")):
            affected.append(value[1:-1])
    return {
        "change_id": stable_urn("semantic-change", {"component": component, "operation": operation, "subject": subject, "predicate": predicate, "old_value": old, "new_value": new, "base_artifact_digest": base, "candidate_artifact_digest": candidate}),
        "component": component, "operation": operation, "semantic_subject": subject, "semantic_predicate": predicate,
        "old_value": old, "new_value": new, "affected_iris": sorted(set(affected)), "classification": classification,
        "classification_rule_id": rule, "rationale": rule, "base_artifact_digest": base, "candidate_artifact_digest": candidate,
    }


def _classify(component: str, old: str | None, new: str | None, predicate: str | None) -> tuple[str, str]:
    if component=="METADATA":
        return "PATCH_COMPATIBLE","EXPLICIT_PACKAGE_METADATA_CHANGE"
    if component in {"TBOX", "ABOX", "SHACL"}:
        p = URIRef(predicate.strip("<>") if predicate else "urn:unknown")
        if component == "TBOX":
            return classify_tbox(None, p, old, new)
        if component == "ABOX":
            return classify_abox(None, p, old, new)
        return classify_shacl(None, p, old, new)
    if old is None:
        return "ADDITIVE", "ARTIFACT_ADDED"
    if new is None:
        return "BREAKING", "ARTIFACT_REMOVED"
    return "UNKNOWN_REQUIRES_REVIEW", "STRUCTURED_VALUE_CHANGED"


def create_diff(base: Any, candidate: Any, *, policy_id: str | None = None, registry_id: str | None = None, base_package_id: str | None = None, candidate_package_id: str | None = None, base_version: str = "0.0.0", candidate_version: str = "0.0.0", _allow_unverified_fixture: bool = False) -> dict[str, Any]:
    path_inputs = [item for item in (base, candidate) if not isinstance(item, dict)]
    if not _allow_unverified_fixture and path_inputs and any(Path(item).is_file() for item in path_inputs):
        raise LifecycleError("SEMANTIC_DIFF_FAILED", "formal semantic diff requires verified package directories")
    left, left_meta = _package_parts(base)
    right, right_meta = _package_parts(candidate)
    groups = {"tbox": "TBOX", "abox": "ABOX", "shacl": "SHACL", "mapping": "MAPPING", "cq": "CQ", "dependency": "DEPENDENCY", "annotation": "ANNOTATION", "provenance": "PROVENANCE", "metadata": "METADATA"}
    changes: dict[str, list[dict[str, Any]]] = {"IDENTITY": [], **{value: [] for value in groups.values()}}
    for key, component in groups.items():
        left_values, right_values = left.get(key, set()), right.get(key, set())
        left_digest, right_digest = semantic_hash(sorted(left_values)), semantic_hash(sorted(right_values))
        for descriptor in sorted(left_values - right_values):
            triple = _rdf_descriptor(descriptor)
            subject, predicate, old = triple if triple else (descriptor, None, descriptor)
            classification, rule = _classify(component, old, None, predicate)
            changes[component].append(_change(component, "REMOVE", subject, predicate, old, None, classification, rule, left_digest, right_digest))
        for descriptor in sorted(right_values - left_values):
            triple = _rdf_descriptor(descriptor)
            subject, predicate, new = triple if triple else (descriptor, None, descriptor)
            classification, rule = _classify(component, None, new, predicate)
            changes[component].append(_change(component, "ADD", subject, predicate, None, new, classification, rule, left_digest, right_digest))
    identity_left = {"package_id": left_meta.get("package_id"), "ontology_iri": left_meta.get("ontology_iri"), "version": base_version or left_meta.get("version")}
    identity_right = {"package_id": right_meta.get("package_id"), "ontology_iri": right_meta.get("ontology_iri"), "version": candidate_version or right_meta.get("version")}
    if identity_left != identity_right:
        same_ontology=identity_left["ontology_iri"]==identity_right["ontology_iri"]
        classification="PATCH_COMPATIBLE" if same_ontology else "UNKNOWN_REQUIRES_REVIEW"
        rule="VERSIONED_PACKAGE_IDENTITY" if same_ontology else "ONTOLOGY_IDENTITY_CHANGED"
        changes["IDENTITY"].append(_change("IDENTITY", "MODIFY", "package-identity", None, json.dumps(identity_left, sort_keys=True), json.dumps(identity_right, sort_keys=True), classification, rule, semantic_hash(identity_left), semantic_hash(identity_right)))
    all_changes = [item for values in changes.values() for item in values]
    counts = [{"classification": name, "count": sum(item["classification"] == name for item in all_changes)} for name in sorted({item["classification"] for item in all_changes})]
    business_components = {key: sorted(values) for key, values in left.items() if key not in {"metadata", "dependency"}}
    candidate_business_components = {key: sorted(values) for key, values in right.items() if key not in {"metadata", "dependency"}}
    base_digest, candidate_digest = semantic_hash(business_components), semantic_hash(candidate_business_components)
    report_core = {
        "base_package_id": base_package_id or left_meta.get("package_id") or stable_urn("ontology-package", {"digest": base_digest}),
        "candidate_package_id": candidate_package_id or right_meta.get("package_id") or stable_urn("ontology-package", {"digest": candidate_digest}),
        "base_package_version": base_version or left_meta.get("version", "0.0.0"), "candidate_package_version": candidate_version or right_meta.get("version", "0.0.0"),
        "ontology_iri": right_meta.get("ontology_iri") or left_meta.get("ontology_iri") or "urn:kg-mnp:ontology", "base_semantic_dataset_digest": base_digest, "candidate_semantic_dataset_digest": candidate_digest,
        "identity_changes": changes["IDENTITY"], "tbox_changes": changes["TBOX"], "abox_changes": changes["ABOX"], "shacl_changes": changes["SHACL"], "mapping_changes": changes["MAPPING"], "cq_changes": changes["CQ"], "dependency_changes": changes["DEPENDENCY"], "annotation_changes": changes["ANNOTATION"], "provenance_changes": changes["PROVENANCE"], "metadata_changes": changes["METADATA"],
        "raw_statement_delta": {"added": sorted(set().union(*(right.get(key, set()) - left.get(key, set()) for key in groups))), "removed": sorted(set().union(*(left.get(key, set()) - right.get(key, set()) for key in groups)))},
        "classification_summary": counts, "affected_iris": sorted({iri for item in all_changes for iri in item["affected_iris"]}), "unknown_constructs": sorted({item["semantic_subject"] for item in all_changes if item["classification"] == "UNKNOWN_REQUIRES_REVIEW"}), "overall_classification": worst([item["classification"] for item in all_changes]),
    }
    core = canonicalize({"manifest_kind": "KG_MNP_SEMANTIC_DIFF_REPORT", "schema_version": "1.0.0", "registry_id": registry_id or stable_urn("registry", {"local": "lifecycle"}), "policy_id": policy_id or stable_urn("semantic-diff-policy", {"version": "1.0.0"}), **report_core})
    bind_identity(core, "diff_id", "semantic-diff-report")
    return core


def create_diff_from_rdf_fixture(base: Path | str, candidate: Path | str, **kwargs: Any) -> dict[str, Any]:
    """Test-only low-level RDF comparison; it is not a lifecycle gate."""
    return create_diff(base, candidate, _allow_unverified_fixture=True, **kwargs)


def verify_diff(report: dict[str, Any]) -> dict[str, Any]:
    from ..contracts import verify
    verify(report, contract="semantic-diff-report")
    return {"status": "VALID", "diff_id": report["diff_id"], "overall_classification": report.get("overall_classification", "UNKNOWN_REQUIRES_REVIEW"), "change_count": sum(len(report.get(key, [])) for key in ("identity_changes", "tbox_changes", "abox_changes", "shacl_changes", "mapping_changes", "cq_changes", "dependency_changes", "annotation_changes", "provenance_changes", "metadata_changes"))}
