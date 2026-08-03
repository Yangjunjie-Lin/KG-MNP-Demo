#!/usr/bin/env python
"""Export OpenAPI schema for frontend client generation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    try:
        from kg_mnp_demo.api.app import create_app
    except SystemExit as exc:
        print(exc, file=sys.stderr)
        return 1

    app = create_app()
    schema = app.openapi()
    out = ROOT / "docs" / "api" / "openapi.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
