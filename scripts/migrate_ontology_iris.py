#!/usr/bin/env python3
"""Deterministic IRI migration for Stage 03 formal namespaces.

Dry-run by default. Use --apply to write changes.
Does not modify third-party URLs, historical docs/migration narratives,
or demo_outputs snapshots (allowlisted).
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from stage03_constants import (  # noqa: E402
    DATA_NS,
    OLD_TERM_NS,
    TERM_NS,
)

OLD_MODULE_RE = re.compile(
    r"http://example\.org/kg-mnp/(core|identity|account-billing|service-contract|"
    r"process|compliance|evidence-time|code-list|alignments)"
)

ALLOWLIST_PREFIXES = (
    "docs/migration/",
    "demo_outputs/",
    "docs/ontology/iri-migration.csv",
    "docs/ontology/term-change-log.csv",
)

MIGRATE_GLOBS = [
    "ontology/*.ttl",
    "ontology/*.xml",
    "shapes/**/*.ttl",
    "examples/**/*.ttl",
    "data/*.ttl",
    "queries/*.rq",
    "competency_questions/**/*.rq",
    "mappings/*.yaml",
    "rules/*.yaml",
    "schemas/*.json",
    "src/kg_mnp_demo/**/*.py",
    "tests/**/*.py",
    "scripts/**/*.py",
    "config/*.yaml",
]


def is_allowlisted(path: Path) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    return any(rel.startswith(p) or rel == p.rstrip("/") for p in ALLOWLIST_PREFIXES)


def load_term_map() -> dict[str, str]:
    path = ROOT / "docs" / "ontology" / "iri-migration.csv"
    mapping: dict[str, str] = {}
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            old, new = row["old_iri"], row["new_iri"]
            if old and new and old != new:
                mapping[old] = new
    # Namespace prefixes
    mapping[OLD_TERM_NS] = TERM_NS
    mapping["http://example.org/kg-mnp#"] = TERM_NS
    return mapping


MODULE_MAP = {
    "core": "mnp-core",
    "identity": "mnp-identity",
    "account-billing": "mnp-account-billing",
    "service-contract": "mnp-service-contract",
    "process": "mnp-process",
    "compliance": "mnp-compliance",
    "evidence-time": "mnp-evidence-time",
    "code-list": "mnp-code-list",
    "alignments": "mnp-alignments",
}


def migrate_text(text: str, term_map: dict[str, str]) -> str:
    # Longest-first replacement for term IRIs
    for old in sorted(term_map, key=len, reverse=True):
        text = text.replace(old, term_map[old])

    def mod_sub(m: re.Match[str]) -> str:
        local = m.group(1)
        new = MODULE_MAP.get(local, local)
        return f"https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/{new}"

    text = OLD_MODULE_RE.sub(mod_sub, text)
    return text


def candidate_files() -> list[Path]:
    files: list[Path] = []
    for pattern in MIGRATE_GLOBS:
        files.extend(ROOT.glob(pattern))
    # unique, skip allowlisted and binary-ish
    out = []
    seen = set()
    for p in sorted(files):
        if not p.is_file():
            continue
        key = p.resolve()
        if key in seen:
            continue
        seen.add(key)
        if is_allowlisted(p):
            continue
        if p.suffix.lower() not in {".ttl", ".rq", ".yaml", ".yml", ".json", ".py", ".xml", ".md"}:
            continue
        # Don't rewrite the migration script's OLD constants definitions carelessly —
        # stage03_constants and iri-migration are sources of truth.
        rel = p.relative_to(ROOT).as_posix()
        if rel in {
            "scripts/stage03_constants.py",
            "scripts/migrate_ontology_iris.py",
            "docs/ontology/iri-migration.csv",
            "docs/ontology/term-change-log.csv",
            "docs/ontology/term-inventory.csv",
        }:
            continue
        out.append(p)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Write changes")
    parser.add_argument("--dry-run", action="store_true", default=True)
    args = parser.parse_args()
    apply = args.apply
    term_map = load_term_map()
    changed = 0
    for path in candidate_files():
        original = path.read_text(encoding="utf-8")
        updated = migrate_text(original, term_map)
        # Instance data: also rewrite @prefix if still old
        if path.suffix == ".ttl" and "data/" in path.as_posix().replace("\\", "/"):
            # Ensure data prefix available — cases keep individuals under DATA_NS via second pass
            updated = updated.replace(
                f"@prefix mnp: <{TERM_NS}> .",
                f"@prefix mnp: <{TERM_NS}> .\n@prefix data: <{DATA_NS}> .",
            )
            # Avoid double-adding data prefix
            while updated.count(f"@prefix data: <{DATA_NS}> .") > 1:
                updated = updated.replace(
                    f"@prefix data: <{DATA_NS}> .\n@prefix data: <{DATA_NS}> .",
                    f"@prefix data: <{DATA_NS}> .",
                    1,
                )
        if updated != original:
            changed += 1
            rel = path.relative_to(ROOT)
            print(f"{'APPLY' if apply else 'DRY'}: {rel}")
            if apply:
                path.write_text(updated, encoding="utf-8", newline="\n")
    print(f"{'Applied' if apply else 'Would change'} {changed} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
