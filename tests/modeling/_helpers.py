from __future__ import annotations

import json
from pathlib import Path

from kg_mnp_demo.modeling.dependencies import load_modeling_dependencies
from kg_mnp_demo.modeling.proposal import generate_modeling_proposal

ROOT = Path(__file__).resolve().parents[2]


def load_input(name: str) -> dict:
    return json.loads(
        (ROOT / "examples" / "modeling" / "inputs" / f"{name}.json").read_text(
            encoding="utf-8"
        )
    )


def generate(name: str) -> dict:
    dependencies = load_modeling_dependencies()
    return generate_modeling_proposal(
        load_input(name),
        dependencies["ontology_baseline"],
        dependencies["mapping_rules"],
        dependencies["terminology_profile"],
        dependencies["proposal_policy"],
        term_iris=set(dependencies["term_iris"]),
    )

