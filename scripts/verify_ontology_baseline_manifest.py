#!/usr/bin/env python3
"""Verify the frozen Stage 04 ontology baseline against Stage 03 assets."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = str(ROOT / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from kg_mnp_demo.modeling.dependencies import (  # noqa: E402
    ONTOLOGY_BASELINE_PATH,
    verify_ontology_baseline_manifest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify that the Stage 04 ontology baseline exactly represents "
            "the current local Stage 03 formal release."
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="repository root (default: this checkout)",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="manifest to verify (default: config/modeling/ontology-baseline-1.0.0.json)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    manifest = (
        args.manifest
        or root / "config" / "modeling" / ONTOLOGY_BASELINE_PATH.name
    )
    errors = verify_ontology_baseline_manifest(
        root=root,
        manifest_path=manifest,
    )
    if errors:
        print("ONTOLOGY BASELINE CHECK FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Ontology baseline manifest matches the Stage 03 release assets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

