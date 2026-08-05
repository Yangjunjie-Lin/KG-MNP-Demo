#!/usr/bin/env python
"""Offline reference integrity checks (no network)."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    manifest = yaml.safe_load((ROOT / "references" / "source_manifest.yaml").read_text(encoding="utf-8"))
    sources = manifest["sources"]
    required = {
        "Point-Topic/cto-ontology",
        "tmforum-apis/TMF629_CustomerManagement",
        "tmforum-apis/TMF637_ProductInventory",
        "tmforum-apis/TMF620_ProductCatalog",
        "RDFLib/rdflib",
        "RDFLib/pySHACL",
        "RDFLib/OWL-RL",
        "protegeproject/protege",
        "dgarijo/WIDOCO",
    }
    names = {s["name"] for s in sources}
    missing = required - names
    if missing:
        print("Missing sources:", sorted(missing))
        return 1

    for s in sources:
        for key in [
            "name",
            "repository_url",
            "purpose",
            "license",
            "version_or_commit",
            "retrieved_at",
            "local_path",
            "runtime_dependency",
            "reuse_mode",
        ]:
            if key not in s:
                print(f"{s.get('name')}: missing {key}")
                return 1
        if s["name"] == "Point-Topic/cto-ontology":
            assert s["runtime_dependency"] is False
            assert s["reuse_mode"] == "conceptual_reference"
        if s["runtime_dependency"] is True and not s.get("license"):
            print(f"Runtime source without license: {s['name']}")
            return 1

    cto_review = ROOT / "references" / "cto_review.md"
    if "cto_core.ttl" not in cto_review.read_text(encoding="utf-8"):
        print("cto_review.md should mention reviewed files")
        return 1

    print("Reference checks OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
