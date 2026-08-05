"""Load ontology, shapes, reference data, and case graphs from config."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from rdflib import Graph

from kg_mnp_demo.namespaces import CASE_FILES

ROOT = Path(__file__).resolve().parents[2]

SHAPE_PROFILES = {
    "foundation": [
        "shapes/foundation-instance-shapes.ttl",
    ],
    "eligibility": [
        "shapes/foundation-instance-shapes.ttl",
        "examples/eligibility-use-case/shapes/eligibility-instance-shapes.ttl",
    ],
    "ontology_schema": [
        "shapes/ontology-schema-shapes.ttl",
    ],
}


def project_root() -> Path:
    return ROOT


def load_graph(paths: list[Path]) -> Graph:
    g = Graph()
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(f"RDF file not found: {path}")
        g.parse(path, format="turtle")
    return g


def ontology_modules_config_path() -> Path:
    return ROOT / "config" / "ontology_modules.yaml"


def load_ontology_modules_config() -> dict[str, Any]:
    path = ontology_modules_config_path()
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict) or "modules" not in data:
        raise ValueError(f"Invalid ontology modules config: {path}")
    return data


def ontology_module_entries(*, include_alignments: bool = False) -> list[dict[str, Any]]:
    """Ordered module entries from config (deterministic catalog order)."""
    cfg = load_ontology_modules_config()
    modules = list(cfg["modules"])
    seen: set[str] = set()
    ordered: list[dict[str, Any]] = []
    for entry in modules:
        code = entry["code"]
        if code in seen:
            raise ValueError(f"Duplicate ontology module code in config: {code}")
        seen.add(code)
        is_runtime = bool(entry.get("runtime", False))
        is_optional = bool(entry.get("optional", False))
        if is_runtime:
            ordered.append(entry)
        elif include_alignments and (is_optional or code == "ALIGNMENTS"):
            ordered.append(entry)
    return ordered


def ontology_module_files(*, include_alignments: bool = False) -> list[str]:
    return [e["file"] for e in ontology_module_entries(include_alignments=include_alignments)]


def ontology_paths(*, include_alignments: bool = False) -> list[Path]:
    paths = []
    for entry in ontology_module_entries(include_alignments=include_alignments):
        path = ROOT / "ontology" / entry["file"]
        if not path.is_file():
            raise FileNotFoundError(f"Missing ontology module file for {entry['code']}: {path}")
        paths.append(path)
    return paths


def shapes_path() -> Path:
    """Default legacy convenience path — foundation + eligibility combined profile entry."""
    return ROOT / "examples" / "eligibility-use-case" / "shapes" / "eligibility-instance-shapes.ttl"


def shape_paths(profile: str = "eligibility") -> list[Path]:
    if profile not in SHAPE_PROFILES:
        raise KeyError(f"Unknown shape profile: {profile}. Known: {sorted(SHAPE_PROFILES)}")
    paths = [ROOT / rel for rel in SHAPE_PROFILES[profile]]
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(f"Missing shapes file for profile {profile}: {path}")
    return paths


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
    shape_profile: str = "eligibility",
) -> Graph:
    paths = ontology_paths(include_alignments=include_alignments)
    paths.extend(reference_paths())
    paths.append(case_path(case_id))
    if include_shapes:
        paths.extend(shape_paths(shape_profile))
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
