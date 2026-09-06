"""Deterministic, offline semantic diff engine for KG-MNP ontology packages."""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from rdflib import Graph, URIRef

from kg_mnp.contracts.canonical import semantic_hash, stable_urn

from ..contracts import canonicalize
from ..store import bind_identity
from .classification import classify_abox, classify_shacl, classify_tbox, worst


def _read_nt(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, (set, list, tuple)):
        return {str(x).strip() for x in value if str(x).strip()}
    path = Path(value)
    if path.is_dir():
        for candidate in (path / "ontology" / "effective-tbox.nt", path / "effective-tbox.nt"):
            if candidate.is_file():
                path = candidate
                break
    if path.is_file():
        return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.lstrip().startswith("#")}
    return {str(value)}


def _triples(lines: Iterable[str]) -> set[tuple[str, str, str]]:
    graph = Graph()
    for line in lines:
        try:
            graph.parse(data=line + ("\n" if not line.endswith("\n") else ""), format="nt")
        except (ValueError, TypeError):
            parts = line.rstrip(" .").split(None, 2)
            if len(parts) == 3:
                yield tuple(parts)
    if len(graph):
        for s, p, o in graph:
            yield str(s), str(p), str(o)


def _package_parts(value: Any) -> dict[str, set[str]]:
    if isinstance(value, dict):
        return {k: _read_nt(v) for k, v in value.items() if k in {"tbox", "abox", "shacl", "mapping", "cq", "dependency", "annotation", "provenance", "metadata"}}
    root = Path(value)
    if root.is_file():
        return {"tbox": _read_nt(root), "abox": set(), "shacl": set(), "mapping": set(), "cq": set(), "dependency": set(), "annotation": set(), "provenance": set(), "metadata": set()}
    return {
        "tbox": _read_nt(root / "ontology" / "effective-tbox.nt"),
        "abox": _read_nt(root / "data" / "abox.nt"),
        "shacl": _read_nt(root / "shapes" / "effective-shapes.nt"),
        "mapping": _read_nt(root / "mappings" / "mapping-plan.json"),
        "cq": _read_nt(root / "validation" / "competency-question-test-plan.json"),
        "dependency": _read_nt(root / "manifest.json"),
        "annotation": set(), "provenance": set(), "metadata": set(),
    }


def _change(component: str, operation: str, subject: str, old: str | None, new: str | None, classification: str, rule: str, base: str, candidate: str) -> dict[str, Any]:
    return {
        "change_id": stable_urn("semantic-change", {"component": component, "operation": operation, "subject": subject, "old_value": old, "new_value": new, "base_artifact_digest": base, "candidate_artifact_digest": candidate}),
        "component": component, "operation": operation, "semantic_subject": subject,
        "semantic_predicate": None, "old_value": old, "new_value": new,
        "affected_iris": sorted([subject] if subject.startswith(("http://", "https://", "urn:")) else []),
        "classification": classification, "classification_rule_id": rule,
        "rationale": rule, "base_artifact_digest": base, "candidate_artifact_digest": candidate,
    }


def _classify(component: str, old: str | None, new: str | None) -> tuple[str, str]:
    if component == "TBOX":
        parts = (new or old or "").split()
        p = URIRef(parts[1].strip("<>") if len(parts) > 1 else "urn:unknown")
        return classify_tbox(None, p, old, new)
    if component == "ABOX":
        parts = (new or old or "").split()
        p = URIRef(parts[1].strip("<>") if len(parts) > 1 else "urn:unknown")
        return classify_abox(None, p, old, new)
    if component == "SHACL":
        parts = (new or old or "").split()
        p = URIRef(parts[1].strip("<>") if len(parts) > 1 else "urn:unknown")
        return classify_shacl(None, p, old, new)
    if old is None:
        return "ADDITIVE", "ARTIFACT_ADDED"
    if new is None:
        return "BREAKING", "ARTIFACT_REMOVED"
    return "POTENTIALLY_BREAKING", "ARTIFACT_CHANGED"


def create_diff(base: Any, candidate: Any, *, policy_id: str | None = None, registry_id: str | None = None, base_package_id: str | None = None, candidate_package_id: str | None = None, base_version: str = "0.0.0", candidate_version: str = "0.0.0") -> dict[str, Any]:
    left, right = _package_parts(base), _package_parts(candidate)
    groups = {"tbox": "TBOX", "abox": "ABOX", "shacl": "SHACL", "mapping": "MAPPING", "cq": "CQ", "dependency": "DEPENDENCY", "annotation": "ANNOTATION", "provenance": "PROVENANCE", "metadata": "METADATA"}
    changes: dict[str, list[dict[str, Any]]] = {"IDENTITY": [], **{v: [] for v in groups.values()}}
    for key, component in groups.items():
        a, b = left.get(key, set()), right.get(key, set())
        da, db = sorted(a - b), sorted(b - a)
        for line in da:
            c, rule = _classify(component, line, None)
            changes[component].append(_change(component, "REMOVE", line, line, None, c, rule, semantic_hash(sorted(a)), semantic_hash(sorted(b))))
        for line in db:
            c, rule = _classify(component, None, line)
            changes[component].append(_change(component, "ADD", line, None, line, c, rule, semantic_hash(sorted(a)), semantic_hash(sorted(b))))
    all_changes = [c for vals in changes.values() for c in vals]
    counts = [{"classification": name, "count": sum(1 for c in all_changes if c["classification"] == name)} for name in sorted({c["classification"] for c in all_changes})]
    overall = worst([c["classification"] for c in all_changes])
    base_digest, cand_digest = semantic_hash({k: sorted(v) for k, v in left.items()}), semantic_hash({k: sorted(v) for k, v in right.items()})
    report_core = {"base_package_id": base_package_id or stable_urn("ontology-package", {"digest": base_digest}), "candidate_package_id": candidate_package_id or stable_urn("ontology-package", {"digest": cand_digest}), "base_package_version": base_version, "candidate_package_version": candidate_version, "ontology_iri": "urn:kg-mnp:ontology", "base_semantic_dataset_digest": base_digest, "candidate_semantic_dataset_digest": cand_digest, "identity_changes": changes["IDENTITY"], "tbox_changes": changes["TBOX"], "abox_changes": changes["ABOX"], "shacl_changes": changes["SHACL"], "mapping_changes": changes["MAPPING"], "cq_changes": changes["CQ"], "dependency_changes": changes["DEPENDENCY"], "annotation_changes": changes["ANNOTATION"], "provenance_changes": changes["PROVENANCE"], "metadata_changes": changes["METADATA"], "raw_statement_delta": {"added": sorted(set().union(*(right.get(k, set()) - left.get(k, set()) for k in groups))), "removed": sorted(set().union(*(left.get(k, set()) - right.get(k, set()) for k in groups)))}, "classification_summary": counts, "affected_iris": sorted({i for c in all_changes for i in c["affected_iris"]}), "unknown_constructs": [], "overall_classification": overall}
    core = {"manifest_kind": "KG_MNP_SEMANTIC_DIFF_REPORT", "schema_version": "1.0.0", "registry_id": registry_id or stable_urn("registry", {"local": "lifecycle"}), "policy_id": policy_id or stable_urn("semantic-diff-policy", {"version": "1.0.0"}), **report_core}
    core = canonicalize(core)
    bind_identity(core, "diff_id", "semantic-diff-report")
    return core


def verify_diff(report: dict[str, Any]) -> dict[str, Any]:
    from ..contracts import verify
    verify(report, contract="semantic-diff-report")
    return {"status": "VALID", "diff_id": report["diff_id"], "overall_classification": report.get("overall_classification", "UNKNOWN_REQUIRES_REVIEW"), "change_count": sum(len(report.get(k, [])) for k in ("identity_changes", "tbox_changes", "abox_changes", "shacl_changes", "mapping_changes", "cq_changes", "dependency_changes", "annotation_changes", "provenance_changes", "metadata_changes"))}
