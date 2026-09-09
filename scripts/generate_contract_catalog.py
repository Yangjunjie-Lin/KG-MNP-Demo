#!/usr/bin/env python3
"""Regenerate or verify the deterministic packaged Contract Catalog."""

from __future__ import annotations

import argparse

from kg_mnp.contracts.catalog import regenerate_catalog_files


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    regenerate_catalog_files(check=arguments.check)
    print("Contract Catalog generated files are current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
