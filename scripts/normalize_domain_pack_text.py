#!/usr/bin/env python3
"""Normalize declared Domain Pack text assets to repository LF bytes."""

from __future__ import annotations

import argparse
from pathlib import Path

from kg_mnp.contracts.document_io import atomic_write_bytes

ROOT = Path(__file__).resolve().parents[1]
PACKS = ROOT / "domain_packs"
TEXT_SUFFIXES = {".json", ".md", ".rq", ".ttl", ".xml", ".yaml", ".yml"}


def candidates() -> tuple[Path, ...]:
    return tuple(
        path
        for path in sorted(PACKS.rglob("*"))
        if path.is_file() and path.suffix.casefold() in TEXT_SUFFIXES
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    stale: list[Path] = []
    for path in candidates():
        raw = path.read_bytes()
        normalized = raw.replace(b"\r\n", b"\n")
        if raw != normalized:
            stale.append(path)
            if not arguments.check:
                atomic_write_bytes(path, normalized)
    if arguments.check and stale:
        raise SystemExit(
            "Domain Pack text assets are not LF-normalized: "
            + ", ".join(path.relative_to(ROOT).as_posix() for path in stale)
        )
    print(f"Domain Pack text normalization is current ({len(candidates())} files).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
