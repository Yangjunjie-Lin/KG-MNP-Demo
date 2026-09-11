"""Read-only baseline snapshots from locked local Domain Pack assets."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from jsonschema import ValidationError
from rdflib import OWL, RDF, RDFS, Graph, URIRef
from rdflib.namespace import SH

from zhigou_toolchain.contracts.canonical import bytes_sha256, stable_urn
from zhigou_toolchain.contracts.errors import ContractError
from zhigou_toolchain.contracts.registry import validate_contract
from zhigou_toolchain.domain_packs.locking import verify_pack_lock
from zhigou_toolchain.domain_packs.validation import load_domain_pack_manifest

from .artifacts import finalize_document, verify_document
from .errors import ModelingControlError
from .limits import ModelingLimits
from .security import validate_safe_relative_path

KIND_TYPES = {
    OWL.Class: "CLASS", OWL.ObjectProperty: "OBJECT_PROPERTY",
    OWL.DatatypeProperty: "DATA_PROPERTY", OWL.AnnotationProperty: "ANNOTATION_PROPERTY",
    OWL.NamedIndividual: "INDIVIDUAL", SH.NodeShape: "SHAPE", SH.PropertyShape: "SHAPE",
}


def _load_pack(pack_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest_path = pack_root / "pack.yaml"
    lock_path = pack_root / "pack.lock.json"
    if manifest_path.is_symlink() or lock_path.is_symlink():
        raise ModelingControlError("Domain Pack metadata cannot be a symlink")
    try:
        manifest_model = load_domain_pack_manifest(pack_root)
        lock_model = verify_pack_lock(manifest_model)
    except (ContractError, OSError, UnicodeError, ValueError, ValidationError) as exc:
        raise ModelingControlError(
            f"Domain Pack differs from pack lock or lock is invalid: {exc}"
        ) from exc
    manifest = manifest_model.document
    lock = lock_model.document
    for asset in lock["assets"]:
        validate_safe_relative_path(asset["path"])
        path = (pack_root / asset["path"]).resolve(strict=True)
        if pack_root.resolve(strict=True) not in path.parents or path.is_symlink():
            raise ModelingControlError("Domain Pack asset escapes its root")
        raw = path.read_bytes()
        if bytes_sha256(raw) != asset["sha256"] or len(raw) != asset["size_bytes"]:
            raise ModelingControlError("Domain Pack asset differs from pack lock")
    return manifest, lock


def _element(
    iri_value: str,
    kind: str,
    *,
    graph: Graph,
    asset_id: str,
    source_sha256: str,
) -> dict[str, Any]:
    node = URIRef(iri_value)
    labels = sorted(
        ({"value": str(value), "language": value.language} for value in graph.objects(node, RDFS.label)),
        key=lambda item: (item["value"], item["language"] or ""),
    )
    definitions = sorted(str(value) for value in graph.objects(node, RDFS.comment))
    domains = sorted(str(value) for value in graph.objects(node, RDFS.domain) if isinstance(value, URIRef))
    ranges = sorted(str(value) for value in graph.objects(node, RDFS.range) if isinstance(value, URIRef))
    parents = sorted(str(value) for value in graph.objects(node, RDFS.subClassOf) if isinstance(value, URIRef))
    semantic = {"iri": iri_value, "element_kind": kind, "source_asset_id": asset_id, "source_sha256": source_sha256}
    return {
        "element_id": stable_urn("baseline-element", semantic), "element_kind": kind, "iri": iri_value,
        "source_asset_id": asset_id, "source_sha256": source_sha256, "labels": labels,
        "definition": definitions[0] if definitions else None, "domain_refs": domains,
        "range_refs": ranges, "parent_refs": parents,
    }


def _index_rows(mapping: dict[str, set[str]]) -> list[dict[str, Any]]:
    return [{"key": key, "element_ids": sorted(values)} for key, values in sorted(mapping.items())]


def build_baseline_snapshot(
    *,
    project_lock_id: str,
    pack_roots: list[Path] | tuple[Path, ...],
    limits: ModelingLimits | None = None,
) -> dict[str, Any]:
    effective_limits = limits or ModelingLimits()
    graph = Graph()
    ontology_assets: list[dict[str, Any]] = []
    ontology_iris: set[str] = set()
    version_iris: set[str] = set()
    imports: list[dict[str, Any]] = []
    elements_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    domain_pack_lock_ids: list[str] = []
    triple_count = 0
    for pack_root_value in sorted(pack_roots, key=lambda item: item.as_posix()):
        pack_root = pack_root_value.resolve(strict=True)
        manifest, lock = _load_pack(pack_root)
        domain_pack_lock_ids.append(lock["lock_id"])
        locked = {asset["asset_id"]: asset for asset in lock["assets"]}
        semantic_assets = [asset for asset in manifest["assets"] if asset["kind"] in {"ontology-root", "ontology-module", "shacl-shapes"}]
        for asset in sorted(semantic_assets, key=lambda item: item["asset_id"]):
            locked_asset = locked[asset["asset_id"]]
            path = pack_root / asset["path"]
            local_graph = Graph()
            local_graph.parse(path, format="turtle")
            triple_count += len(local_graph)
            if triple_count > effective_limits.max_baseline_triples:
                raise ModelingControlError("baseline triple limit exceeded")
            graph += local_graph
            ontology_assets.append({"asset_id": asset["asset_id"], "relative_path": f"{manifest['pack_id']}/{asset['path']}", "sha256": locked_asset["sha256"]})
            for ontology in local_graph.subjects(RDF.type, OWL.Ontology):
                if isinstance(ontology, URIRef):
                    ontology_iris.add(str(ontology))
                    version_iris.update(str(value) for value in local_graph.objects(ontology, OWL.versionIRI) if isinstance(value, URIRef))
                    for imported in local_graph.objects(ontology, OWL.imports):
                        if not isinstance(imported, URIRef):
                            raise ModelingControlError("blank-node owl:imports is rejected")
                        target = next((item for item in semantic_assets if item.get("ontology_iri") == str(imported)), None)
                        if target is None:
                            raise ModelingControlError("remote or unlocked owl:imports is rejected")
                        imports.append({"source_iri": str(ontology), "import_iri": str(imported), "local_asset_id": target["asset_id"], "remote_fetch": False})
            for rdf_type, kind in KIND_TYPES.items():
                for subject in local_graph.subjects(RDF.type, rdf_type):
                    if not isinstance(subject, URIRef):
                        continue
                    key = (str(subject), kind)
                    if key in elements_by_key or any(existing[0] == str(subject) and existing[1] != kind for existing in elements_by_key):
                        raise ModelingControlError(f"duplicate or conflicting baseline IRI declaration: {subject}")
                    elements_by_key[key] = _element(str(subject), kind, graph=local_graph, asset_id=asset["asset_id"], source_sha256=locked_asset["sha256"])
    elements = sorted(elements_by_key.values(), key=lambda item: (item["iri"], item["element_kind"], item["element_id"]))
    iri_index: dict[str, set[str]] = defaultdict(set)
    label_index: dict[str, set[str]] = defaultdict(set)
    normalized_index: dict[str, set[str]] = defaultdict(set)
    language_index: dict[str, set[str]] = defaultdict(set)
    property_index: dict[str, set[str]] = defaultdict(set)
    domain_range_index: dict[str, set[str]] = defaultdict(set)
    hierarchy_index: dict[str, set[str]] = defaultdict(set)
    source_index: dict[str, set[str]] = defaultdict(set)
    for item in elements:
        iri_index[item["iri"]].add(item["element_id"])
        property_index[item["element_kind"]].add(item["element_id"])
        source_index[item["source_asset_id"]].add(item["element_id"])
        for label in item["labels"]:
            label_index[label["value"]].add(item["element_id"])
            normalized_index[" ".join(label["value"].casefold().split())].add(item["element_id"])
            if label["language"]:
                language_index[label["language"]].add(item["element_id"])
        for target in [*item["domain_refs"], *item["range_refs"]]:
            domain_range_index[target].add(item["element_id"])
        for parent in item["parent_refs"]:
            hierarchy_index[parent].add(item["element_id"])
    by_kind = lambda kind: sorted(item["element_id"] for item in elements if item["element_kind"] == kind)
    core = {
        "manifest_kind": "KG_MNP_ONTOLOGY_BASELINE_SNAPSHOT", "schema_version": "1.0.0",
        "project_lock_id": project_lock_id, "domain_pack_lock_ids": sorted(domain_pack_lock_ids),
        "ontology_assets": sorted(ontology_assets, key=lambda item: item["asset_id"]),
        "ontology_iris": sorted(ontology_iris), "version_iris": sorted(version_iris),
        "imports": sorted(imports, key=lambda item: (item["source_iri"], item["import_iri"])),
        "elements": elements, "classes": by_kind("CLASS"), "object_properties": by_kind("OBJECT_PROPERTY"),
        "data_properties": by_kind("DATA_PROPERTY"), "annotation_properties": by_kind("ANNOTATION_PROPERTY"),
        "individuals": by_kind("INDIVIDUAL"), "shapes": by_kind("SHAPE"),
        "labels": sorted(item["element_id"] for item in elements if item["labels"]),
        "definitions": sorted(item["element_id"] for item in elements if item["definition"] is not None),
        "domain_axioms": sorted(item["element_id"] for item in elements if item["domain_refs"]),
        "range_axioms": sorted(item["element_id"] for item in elements if item["range_refs"]),
        "subclass_axioms": sorted(item["element_id"] for item in elements if item["parent_refs"]),
        "indexes": {
            "iri_index": _index_rows(iri_index), "label_index": _index_rows(label_index),
            "normalized_label_index": _index_rows(normalized_index), "language_index": _index_rows(language_index),
            "property_type_index": _index_rows(property_index), "domain_range_index": _index_rows(domain_range_index),
            "hierarchy_index": _index_rows(hierarchy_index), "source_asset_index": _index_rows(source_index),
        },
    }
    snapshot = finalize_document(core, id_field="baseline_snapshot_id", urn_kind="ontology-baseline-snapshot")
    validate_contract("ontology-baseline-snapshot", snapshot)
    return snapshot


def verify_baseline_snapshot(value: dict[str, Any]) -> None:
    validate_contract("ontology-baseline-snapshot", value)
    verify_document(value, id_field="baseline_snapshot_id", urn_kind="ontology-baseline-snapshot")
    iris = [item["iri"] for item in value["elements"]]
    if len(iris) != len(set(iris)):
        raise ModelingControlError("duplicate baseline IRI")
