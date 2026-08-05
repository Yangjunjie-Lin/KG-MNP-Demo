#!/usr/bin/env python3
"""High-level ontology audit summary for Stage 03."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kg_mnp_demo.loader import load_ontology_graph  # noqa: E402


def main() -> int:
    inv = list(csv.DictReader((ROOT / "docs" / "ontology" / "term-inventory.csv").open(encoding="utf-8")))
    terms = [r for r in inv if r["term_type"] != "Ontology"]
    g = load_ontology_graph()
    report = ROOT / "docs" / "ontology" / "ontology-audit-report.md"
    lines = [
        "# Ontology Audit Report (Stage 03)",
        "",
        f"- Ontology triples (runtime merge): {len(g)}",
        f"- Inventory terms (excl. Ontology resources): {len(terms)}",
        f"- Classes: {sum(1 for r in terms if r['term_type']=='Class')}",
        f"- Object properties: {sum(1 for r in terms if r['term_type']=='ObjectProperty')}",
        f"- Datatype properties: {sum(1 for r in terms if r['term_type']=='DatatypeProperty')}",
        f"- Annotation properties: {sum(1 for r in terms if r['term_type']=='AnnotationProperty')}",
        f"- Individuals: {sum(1 for r in terms if r['term_type']=='Individual')}",
        f"- Deprecated: {sum(1 for r in terms if r['deprecated']=='true')}",
        "",
        "## Audit decisions",
        "",
    ]
    from collections import Counter

    c = Counter(r["audit_decision"] for r in terms)
    for k in sorted(c):
        lines.append(f"- {k}: {c[k]}")
    lines += [
        "",
        "## Formal IRI",
        "",
        "- Term namespace: `https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#`",
        "- Root ontology: `https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/kg-mnp`",
        "- Version: `1.0.0`",
        "",
        "## ODR references",
        "",
        "- ODR-001 number/subscription/account",
        "- ODR-002 assessment/decision/blocking",
        "- ODR-003 evidence availability vs use",
        "- ODR-004 assessment dependency",
        "- ODR-005 modeling provenance",
        "- ODR-006 SHACL profile separation",
        "",
    ]
    report.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
