#!/usr/bin/env python3
"""Lightweight ontology Chinese label coverage check."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ZH_CN = ROOT / "frontend" / "src" / "app" / "i18n" / "zh-CN.ts"
RESOLVER = ROOT / "frontend" / "src" / "app" / "i18n" / "graphChineseResolver.ts"


def main() -> int:
    if not ZH_CN.exists():
        print("missing zh-CN.ts", file=sys.stderr)
        return 1
    text = ZH_CN.read_text(encoding="utf-8")
    if "ontologyClassLabels" not in text or "ontologyRelationLabels" not in text:
        print("missing ontology label maps", file=sys.stderr)
        return 1
    if not RESOLVER.exists():
        print("missing graphChineseResolver.ts", file=sys.stderr)
        return 1
    resolver = RESOLVER.read_text(encoding="utf-8")
    if "resolveGraphChineseLabel" not in resolver:
        print("missing resolveGraphChineseLabel", file=sys.stderr)
        return 1
    # Ban naive "contains Chinese => display" helper in ontology browser.
    browser = ROOT / "frontend" / "src" / "app" / "pages" / "OntologyBrowser.tsx"
    if browser.exists():
        src = browser.read_text(encoding="utf-8")
        if re.search(r"containsChinese\(.*\)\s*return", src):
            print("OntologyBrowser still uses naive Chinese detection", file=sys.stderr)
            return 1
    print("Ontology i18n coverage check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
