from __future__ import annotations

import json
from pathlib import Path

from kg_mnp_demo.modeling.dependencies import load_modeling_dependencies
from kg_mnp_demo.modeling.package_validation import load_term_type_index
from kg_mnp_demo.modeling.review_policy import load_default_review_policy

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples" / "review"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_proposal(name: str = "partial-basic") -> dict:
    return load_json(
        ROOT / "examples" / "modeling" / "expected-proposals" / f"{name}.proposal.json"
    )


def load_input(name: str = "partial-basic") -> dict:
    return load_json(ROOT / "examples" / "modeling" / "inputs" / f"{name}.json")


def load_expected_log(name: str) -> dict:
    return load_json(EXAMPLES / "expected-logs" / f"{name}.log.json")


def load_expected_package(name: str) -> dict:
    return load_json(EXAMPLES / "expected-packages" / f"{name}.package.json")


def load_action(scenario: str, filename: str) -> dict:
    return load_json(EXAMPLES / "actions" / scenario / filename)


def dependencies() -> dict:
    values = load_modeling_dependencies()
    values["review_policy"] = load_default_review_policy()
    values["term_types"] = load_term_type_index()
    return values
