#!/usr/bin/env python3
"""Build the deterministic Stage 04 ontology-baseline manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = str(ROOT / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from kg_mnp_demo.modeling.dependencies import (  # noqa: E402
    ONTOLOGY_BASELINE_PATH,
    build_ontology_baseline_manifest,
)


def render_manifest(manifest: dict[str, object]) -> bytes:
    """Render stable UTF-8 JSON with a single trailing LF."""

    text = json.dumps(
        manifest,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    return (text + "\n").encode("utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build the local Stage 04 ontology baseline from the verified "
            "Stage 03 release assets."
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="repository root (default: this checkout)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="output JSON path (default: config/modeling/ontology-baseline-1.0.0.json)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    output = args.output or root / "config" / "modeling" / ONTOLOGY_BASELINE_PATH.name
    try:
        resolved_output = output.resolve()
        ontology_directory = (root / "ontology").resolve()
        if resolved_output == ontology_directory or ontology_directory in resolved_output.parents:
            raise ValueError("the manifest builder never writes under ontology/")
        manifest = build_ontology_baseline_manifest(root)
        payload = render_manifest(manifest)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(payload)
    except Exception as exc:  # fail closed at the command boundary
        print(f"ONTOLOGY BASELINE BUILD FAILED: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote deterministic ontology baseline manifest: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
