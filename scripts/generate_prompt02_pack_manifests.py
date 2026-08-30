#!/usr/bin/env python3
"""Generate/check the formal MNP manifest from the frozen Prompt 1 asset tree."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import yaml

from kg_mnp.contracts.document_io import atomic_write_bytes

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "domain_packs" / "mnp"
MANIFEST = PACK / "pack.yaml"
INCLUDED_SUFFIXES = {".json", ".md", ".rq", ".ttl", ".xml", ".yaml", ".yml"}


def asset_id(relative: str) -> str:
    stem = relative.casefold()
    if stem.endswith(".schema.json"):
        stem = stem[: -len(".schema.json")]
    else:
        stem = str(Path(stem).with_suffix(""))
    return "mnp-" + re.sub(r"[^a-z0-9]+", "-", stem).strip("-")


def media_type(path: Path) -> str:
    lowered = path.name.casefold()
    if lowered.endswith(".schema.json"):
        return "application/schema+json"
    return {
        ".json": "application/json",
        ".md": "text/markdown",
        ".rq": "application/sparql-query",
        ".ttl": "text/turtle",
        ".xml": "application/xml",
        ".yaml": "application/yaml",
        ".yml": "application/yaml",
    }[path.suffix.casefold()]


def kind(relative: str) -> str:
    path = Path(relative)
    if path.suffix.casefold() == ".md":
        return "documentation"
    if relative == "ontology/kg-mnp.ttl":
        return "ontology-root"
    if relative == "ontology/mnp-alignments.ttl":
        return "ontology-alignment"
    if relative.startswith("ontology/") and path.suffix.casefold() == ".ttl":
        return "ontology-module"
    if relative.startswith("ontology/"):
        return "ontology-catalog"
    if relative.startswith("shapes/"):
        return "shacl-shapes"
    if relative.startswith("terminology/"):
        return "terminology"
    if relative.startswith("mappings/"):
        return "mapping-rules"
    if relative.startswith("rules/"):
        return "domain-rules"
    if relative.startswith("competency_questions/"):
        return "competency-questions"
    if relative.startswith("queries/"):
        return "query"
    if relative.startswith("fixtures/"):
        return "fixture"
    raise ValueError(f"unclassified MNP asset: {relative}")


def ontology_metadata() -> dict[str, dict[str, str]]:
    value = yaml.safe_load((PACK / "ontology" / "modules.yaml").read_text(encoding="utf-8"))
    result = {
        f"ontology/{item['file']}": {
            "ontology_iri": item["ontology_iri"],
            "version_iri": item["version_iri"],
        }
        for item in value["modules"]
    }
    result[f"ontology/{value['root']['file']}"] = {
        "ontology_iri": value["root"]["ontology_iri"],
        "version_iri": value["root"]["version_iri"],
    }
    return result


def manifest_document() -> dict[str, Any]:
    metadata = ontology_metadata()
    paths = [
        path
        for path in sorted(PACK.rglob("*"))
        if path.is_file()
        and path.name not in {"pack.yaml", "pack.lock.json"}
        and path.suffix.casefold() in INCLUDED_SUFFIXES
    ]
    assets: list[dict[str, Any]] = []
    for path in paths:
        relative = path.relative_to(PACK).as_posix()
        item: dict[str, Any] = {
            "asset_id": asset_id(relative),
            "kind": kind(relative),
            "path": relative,
            "media_type": media_type(path),
            "required": True,
            "description": f"Frozen Prompt 1 MNP baseline asset: {relative}.",
        }
        item.update(metadata.get(relative, {}))
        assets.append(item)
    assets.sort(key=lambda item: item["asset_id"])
    return {
        "manifest_kind": "KG_MNP_DOMAIN_PACK",
        "schema_version": "1.0.0",
        "pack_id": "mnp",
        "pack_version": "1.0.0",
        "display_name": "Mobile Number Portability Baseline",
        "description": (
            "Migrated historical MNP semantic baseline; domain-specific and not a "
            "cross-industry or final stability claim."
        ),
        "lifecycle": "MIGRATED_BASELINE",
        "compatibility": {
            "contract_major": 1,
            "minimum_toolchain_version": "0.2.0",
        },
        "license": {"expression": "Apache-2.0", "notice_files": []},
        "capabilities": [
            "competency-questions",
            "fixtures",
            "mappings",
            "ontology",
            "queries",
            "rules",
            "shacl",
            "terminology",
        ],
        "namespaces": {
            "ontology": "https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/",
            "terms": "https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#",
        },
        "assets": assets,
        "entrypoints": {
            "competency-questions": asset_id("competency_questions/registry.yaml"),
            "fixtures": asset_id("fixtures/data/CASE-01-eligible.ttl"),
            "mappings": asset_id("mappings/modeling-rules-1.0.0.yaml"),
            "ontology": asset_id("ontology/kg-mnp.ttl"),
            "queries": asset_id("queries/query-registry-1.0.0.yaml"),
            "rules": asset_id("rules/eligibility_rules.yaml"),
            "shacl": asset_id("shapes/foundation-instance-shapes.ttl"),
            "terminology": asset_id("terminology/terminology-profile-1.0.0.yaml"),
        },
        "dependencies": [],
        "extensions": {},
    }


def manifest_bytes() -> bytes:
    return yaml.safe_dump(
        manifest_document(),
        allow_unicode=True,
        sort_keys=False,
        width=100,
    ).encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    expected = manifest_bytes()
    if arguments.check:
        if not MANIFEST.is_file() or MANIFEST.read_bytes() != expected:
            raise SystemExit("MNP DomainPackManifest is stale")
    else:
        atomic_write_bytes(MANIFEST, expected)
    print("MNP DomainPackManifest is current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
