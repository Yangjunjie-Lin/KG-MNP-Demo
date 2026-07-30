#!/usr/bin/env python
"""Validate eligibility rule version metadata and non-overlapping windows."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from kg_mnp_demo.rule_engine import RuleConfigurationError, validate_rule_configuration


def main() -> int:
    try:
        validate_rule_configuration()
    except RuleConfigurationError as exc:
        print(f"Rule version check FAILED: {exc}")
        return 1
    print("Rule version checks OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
