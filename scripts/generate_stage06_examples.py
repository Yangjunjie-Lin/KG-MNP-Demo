#!/usr/bin/env python3
"""Generate the four deterministic Stage 06 compilation examples."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = str(ROOT / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from kg_mnp_demo.compilation.compiler import compile_formal_semantics  # noqa: E402
from kg_mnp_demo.modeling.dependencies import load_modeling_dependencies  # noqa: E402
from kg_mnp_demo.modeling.review_policy import load_default_review_policy  # noqa: E402


SCENARIOS = (
    "full-confirmation",
    "modified-confirmation",
    "rejection",
    "issue-resolution",
)


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _authorities(scenario: str) -> tuple[dict, ...]:
    dependencies = load_modeling_dependencies()
    source = "conflicting-values" if scenario == "issue-resolution" else "partial-basic"
    return (
        _json(ROOT / f"examples/modeling/inputs/{source}.json"),
        _json(ROOT / f"examples/modeling/expected-proposals/{source}.proposal.json"),
        _json(ROOT / f"examples/review/expected-logs/{scenario}.log.json"),
        _json(ROOT / f"examples/review/expected-packages/{scenario}.package.json"),
        dependencies["ontology_baseline"],
        dependencies["mapping_rules"],
        dependencies["terminology_profile"],
        dependencies["proposal_policy"],
        load_default_review_policy(),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=ROOT / "examples" / "compilation" / "expected",
    )
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    for scenario in SCENARIOS:
        manifest = compile_formal_semantics(
            *_authorities(scenario),
            output_dir=args.output_root / scenario,
            force=args.force,
        )
        print(f"{scenario}: {manifest['compilation_semantic_hash']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
