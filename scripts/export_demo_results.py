#!/usr/bin/env python
"""Export evaluate results for all cases to JSON (offline)."""

from __future__ import annotations

import json
from pathlib import Path

from kg_mnp_demo.evaluator import evaluate_case
from kg_mnp_demo.inference import apply_owlrl
from kg_mnp_demo.loader import load_case_graph
from kg_mnp_demo.namespaces import CASE_FILES

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "demo_results.json"


def main() -> None:
    payload = {}
    for case_id in sorted(CASE_FILES):
        g = load_case_graph(case_id)
        apply_owlrl(g)
        payload[case_id] = evaluate_case(g, case_id, use_updated_rules=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
