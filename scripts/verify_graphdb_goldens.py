#!/usr/bin/env python3
"""Independently reconstruct every committed Stage 07 golden package."""

from __future__ import annotations

import json
from pathlib import Path

from kg_mnp_demo.compilation.policy import load_compiler_policy
from kg_mnp_demo.graphdb.package_validator import validate_graphdb_import_package
from kg_mnp_demo.modeling.dependencies import load_modeling_dependencies
from kg_mnp_demo.modeling.review_policy import load_default_review_policy

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ("full-confirmation", "modified-confirmation", "rejection", "issue-resolution")


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    dependencies = load_modeling_dependencies()
    compiler_policy = load_compiler_policy()
    for scenario in SCENARIOS:
        source = "conflicting-values" if scenario == "issue-resolution" else "partial-basic"
        values = (
            _json(ROOT / f"examples/modeling/inputs/{source}.json"),
            _json(ROOT / f"examples/modeling/expected-proposals/{source}.proposal.json"),
            _json(ROOT / f"examples/review/expected-logs/{scenario}.log.json"),
            _json(ROOT / f"examples/review/expected-packages/{scenario}.package.json"),
            dependencies["ontology_baseline"], dependencies["mapping_rules"],
            dependencies["terminology_profile"], dependencies["proposal_policy"],
            load_default_review_policy(),
        )
        package = ROOT / "examples" / "graphdb" / "expected" / scenario
        result = validate_graphdb_import_package(
            package,
            compilation_directory=ROOT / "examples" / "compilation" / "expected" / scenario,
            cleaned_partial_data=values[0], proposal=values[1],
            final_review_decision_log=values[2], confirmed_modeling_package=values[3],
            ontology_baseline=values[4], mapping_rules=values[5],
            terminology_profile=values[6], proposal_policy=values[7],
            review_policy=values[8], compiler_policy=compiler_policy,
        )
        print(f"{scenario}: {result['publication_id']} PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
