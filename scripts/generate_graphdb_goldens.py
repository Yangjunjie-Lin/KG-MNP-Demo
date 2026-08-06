#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from kg_mnp_demo.compilation.artifacts import write_artifact_set
from kg_mnp_demo.compilation.policy import load_compiler_policy
from kg_mnp_demo.graphdb.package_builder import build_graphdb_import_package
from kg_mnp_demo.modeling.dependencies import load_modeling_dependencies
from kg_mnp_demo.modeling.review_policy import load_default_review_policy

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = {
    "full-confirmation": "partial-basic",
    "modified-confirmation": "partial-basic",
    "rejection": "partial-basic",
    "issue-resolution": "conflicting-values",
}


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    dependencies = load_modeling_dependencies()
    common = (
        dependencies["ontology_baseline"], dependencies["mapping_rules"],
        dependencies["terminology_profile"], dependencies["proposal_policy"],
        load_default_review_policy(), load_compiler_policy(),
    )
    for scenario, source in SCENARIOS.items():
        authorities = (
            _json(ROOT / f"examples/modeling/inputs/{source}.json"),
            _json(ROOT / f"examples/modeling/expected-proposals/{source}.proposal.json"),
            _json(ROOT / f"examples/review/expected-logs/{scenario}.log.json"),
            _json(ROOT / f"examples/review/expected-packages/{scenario}.package.json"),
            *common,
        )
        result = build_graphdb_import_package(
            ROOT / f"examples/compilation/expected/{scenario}", *authorities
        )
        destination = ROOT / "examples" / "graphdb" / "expected" / scenario
        write_artifact_set(destination, result["files"], force=True)
        print(f"{scenario}: {result['manifest']['publication_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
