"""Read-only domain preservation gate; never regenerate a golden or Pack Lock."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from zhigou_toolchain.domain_packs.registry import DomainPackRegistry

ROOT = Path(__file__).resolve().parents[1]
MNP_SOURCE = "a7114eef25f2f2a262cd69793a8d3e2b444836fc"
EXPECTED = {
    "minimal": ("0.1.0", "9243d8a995a4a87b8d2048bf7cb0069203e3d7d528e57409e6d3f985ac11e014"),
    "mnp": ("1.0.0", "2554d6d4bbd98b4defd2a46243d6f4f01842320bcc929aff0a3a03ba7cc6ddd1"),
}


def check():
    golden = json.loads((ROOT / "tests/golden/domain-packs/mnp-prompt01-content.json").read_bytes())
    assert golden["source_commit"] == MNP_SOURCE
    assert len(golden["assets"]) == 84
    for row in golden["assets"]:
        original = subprocess.check_output(["git", "show", MNP_SOURCE + ":" + row["path"]], cwd=ROOT)
        assert hashlib.sha256(original.replace(b"\r\n", b"\n")).hexdigest() == row["sha256"], row["path"]
        current = (ROOT / row["path"]).read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(current).hexdigest() == row["sha256"], row["path"]
    registry = DomainPackRegistry(ROOT / "domain_packs")
    for name, (version, digest) in EXPECTED.items():
        assert registry.resolve(name, version).lock.content_digest == digest, name
    # Discovery alone does not verify locks. Include every advertised version,
    # not only the two historical anchors, so new/archived packs fail early.
    verified = []
    for pack_id, version, _path in registry.list():
        registry.resolve(pack_id, version)
        verified.append(f"{pack_id}@{version}")
    return {"status": "PRESERVED", "mnp_original_assets": 84, "read_only": True,
            "verified_pack_versions": verified}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="always read-only, with or without this flag")
    parser.parse_args()
    print(json.dumps(check()))


if __name__ == "__main__":
    main()
