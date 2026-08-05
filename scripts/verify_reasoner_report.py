#!/usr/bin/env python3
"""Verify docs/ontology/reasoner-report.md matches current ontology hash and PASS."""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def ontology_hash() -> str:
    h = hashlib.sha256()
    for path in sorted((ROOT / "ontology").glob("*.ttl")):
        h.update(path.name.encode())
        h.update(path.read_bytes())
    return h.hexdigest()


def main() -> int:
    report = ROOT / "docs" / "ontology" / "reasoner-report.md"
    if not report.is_file():
        print("Missing reasoner-report.md")
        return 1
    text = report.read_text(encoding="utf-8")
    status_m = re.search(r"- Status: `([^`]+)`", text)
    hash_m = re.search(r"- Ontology hash[^:]*: `([0-9a-f]+)`", text)
    if not status_m or not hash_m:
        print("reasoner-report.md missing Status or Ontology hash fields")
        return 1
    status = status_m.group(1)
    reported = hash_m.group(1)
    current = ontology_hash()
    errors = []
    if reported != current:
        errors.append(f"ontology hash mismatch: report={reported} current={current}")
    if status != "PASS":
        errors.append(f"reasoner status is {status}, expected PASS")
    if errors:
        print("REASONER REPORT CHECK FAILED")
        for e in errors:
            print(" -", e)
        return 1
    print("Reasoner report check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
