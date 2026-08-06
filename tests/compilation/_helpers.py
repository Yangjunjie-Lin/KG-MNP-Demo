from __future__ import annotations

import json
from pathlib import Path

from kg_mnp_demo.compilation.artifacts import write_artifact_set
from kg_mnp_demo.compilation.compiler import build_artifact_set
from kg_mnp_demo.modeling.dependencies import load_modeling_dependencies
from kg_mnp_demo.modeling.review_policy import load_default_review_policy

ROOT = Path(__file__).resolve().parents[2]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def authorities(scenario: str = "full-confirmation") -> tuple[dict, ...]:
    dependencies = load_modeling_dependencies()
    source_name = "conflicting-values" if scenario in {"deferred-review", "issue-resolution"} else "partial-basic"
    return (
        load_json(ROOT / f"examples/modeling/inputs/{source_name}.json"),
        load_json(ROOT / f"examples/modeling/expected-proposals/{source_name}.proposal.json"),
        load_json(ROOT / f"examples/review/expected-logs/{scenario}.log.json"),
        load_json(ROOT / f"examples/review/expected-packages/{scenario}.package.json"),
        dependencies["ontology_baseline"],
        dependencies["mapping_rules"],
        dependencies["terminology_profile"],
        dependencies["proposal_policy"],
        load_default_review_policy(),
    )


def build(tmp_path: Path, scenario: str = "full-confirmation") -> tuple[Path, dict, dict[str, bytes]]:
    values = authorities(scenario)
    files, manifest = build_artifact_set(*values)
    destination = tmp_path / scenario
    write_artifact_set(destination, files)
    return destination, manifest, files
