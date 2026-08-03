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


def ontology_module_files(*, include_alignments: bool = False) -> list[str]:
    """Ordered local ontology modules loaded explicitly (offline; no remote owl:imports)."""
    files = [
        "mnp-core.ttl",
        "mnp-compliance.ttl",
        "mnp-identity.ttl",
        "mnp-account-billing.ttl",
        "mnp-service-contract.ttl",
        "mnp-process.ttl",
        "mnp-evidence-time.ttl",
        "mnp-code-list.ttl",
    ]
    if include_alignments:
        files.append("mnp-alignments.ttl")
    return files


def ontology_paths(*, include_alignments: bool = False) -> list[Path]:
    return [ROOT / "ontology" / name for name in ontology_module_files(include_alignments=include_alignments)]


def ontology_modules_config_path() -> Path:
    return ROOT / "config" / "ontology_modules.yaml"


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


def merge_reference_graph(instance: Graph) -> Graph:
    """Merge ontology + reference systems/regulations into a working graph."""
    base = load_graph(ontology_paths() + reference_paths())
    for triple in instance:
        base.add(triple)
    return base


def rules_path() -> Path:
    return ROOT / "rules" / "eligibility_rules.yaml"


def mappings_path() -> Path:
    return ROOT / "mappings" / "tmf_to_mnp.yaml"


def source_manifest_path() -> Path:
    return ROOT / "references" / "source_manifest.yaml"


def query_path(name: str) -> Path:
    return ROOT / "queries" / name
