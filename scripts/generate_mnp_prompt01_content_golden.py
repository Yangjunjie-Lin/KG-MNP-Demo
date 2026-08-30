#!/usr/bin/env python3
"""Generate/check the immutable Prompt 1 MNP semantic content manifest."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
from pathlib import Path

from kg_mnp.contracts.document_io import atomic_write_json, deterministic_json_bytes

ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA = "a7114eef25f2f2a262cd69793a8d3e2b444836fc"
OUTPUT = ROOT / "tests" / "golden" / "domain-packs" / "mnp-prompt01-content.json"
EXCLUDED = {
    "domain_packs/mnp/README.md",
    "domain_packs/mnp/pack.yaml",
    "domain_packs/mnp/pack.lock.json",
}


def _git(*arguments: str) -> bytes:
    return subprocess.run(
        ("git", *arguments),
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout


def build() -> dict[str, object]:
    paths = _git("ls-tree", "-r", "--name-only", SOURCE_SHA, "--", "domain_packs/mnp").decode("utf-8").splitlines()
    assets = []
    for path in sorted(item for item in paths if item not in EXCLUDED):
        content = _git("show", f"{SOURCE_SHA}:{path}").replace(b"\r\n", b"\n")
        assets.append({"path": path, "sha256": hashlib.sha256(content).hexdigest()})
    return {
        "manifest_kind": "KG_MNP_PROMPT01_CONTENT_GOLDEN",
        "schema_version": "1.0.0",
        "source_commit": SOURCE_SHA,
        "normalization": "TEXT_CRLF_TO_LF",
        "assets": assets,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    value = build()
    expected = deterministic_json_bytes(value)
    if arguments.check:
        if not OUTPUT.is_file() or OUTPUT.read_bytes() != expected:
            raise SystemExit("MNP Prompt 1 content golden is stale")
    else:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(OUTPUT, value)
    print(f"MNP Prompt 1 content golden is current ({len(value['assets'])} assets).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
