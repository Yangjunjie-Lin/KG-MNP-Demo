"""Load ontology, shapes, reference data, and case graphs."""

from __future__ import annotations

from pathlib import Path

from rdflib import Graph

from kg_mnp_demo.namespaces import CASE_FILES

ROOT = Path(__file__).resolve().parents[2]


def project_root() -> Path:
    return ROOT


def load_graph(paths: list[Path]) -> Graph:
    g = Graph()
    for path in paths:
        g.parse(path, format="turtle")
    return g


def ontology_paths(*, include_alignments: bool = False) -> list[Path]:
    paths = [
        ROOT / "ontology" / "mnp-core.ttl",
        ROOT / "ontology" / "mnp-compliance.ttl",
    ]
    if include_alignments:
        paths.append(ROOT / "ontology" / "mnp-alignments.ttl")
    return paths


def shapes_path() -> Path:
    return ROOT / "shapes" / "mnp-shapes.ttl"


def reference_paths() -> list[Path]:
    return [
        ROOT / "data" / "regulations.ttl",
        ROOT / "data" / "reference_systems.ttl",
    ]


def case_path(case_id: str) -> Path:
    if case_id not in CASE_FILES:
        raise KeyError(f"Unknown case id: {case_id}. Known: {sorted(CASE_FILES)}")
    return ROOT / "data" / CASE_FILES[case_id]


def load_case_graph(
    case_id: str,
    *,
    include_alignments: bool = False,
    include_shapes: bool = False,
) -> Graph:
    paths = ontology_paths(include_alignments=include_alignments)
    paths.extend(reference_paths())
    paths.append(case_path(case_id))
    if include_shapes:
        paths.append(shapes_path())
    return load_graph(paths)


def load_ontology_graph(*, include_alignments: bool = False) -> Graph:
    return load_graph(ontology_paths(include_alignments=include_alignments))


def rules_path() -> Path:
    return ROOT / "rules" / "eligibility_rules.yaml"


def mappings_path() -> Path:
    return ROOT / "mappings" / "tmf_to_mnp.yaml"


def source_manifest_path() -> Path:
    return ROOT / "references" / "source_manifest.yaml"


def query_path(name: str) -> Path:
    return ROOT / "queries" / name
