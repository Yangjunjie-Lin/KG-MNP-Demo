"""Verify the frozen P7 Git tree before an authorized P8 snapshot update."""
from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "9ae308ef86e74a08eb4daab1e20dd66cced87b16"


def main():
    sys.path.insert(0, str(ROOT))
    from tests.refactor._historical_freeze import (
        PROTECTED_ROOTS,
        SELF_PATH,
        semantic_tree_identity,
    )
    roots = [root for root in PROTECTED_ROOTS if root != "workbench"]
    archive = subprocess.run(["git", "archive", SOURCE, *roots], cwd=ROOT, capture_output=True, check=True).stdout
    digest = hashlib.sha256()
    count = 0
    with tarfile.open(fileobj=io.BytesIO(archive)) as tree:
        for entry in sorted(tree.getmembers(), key=lambda entry: entry.name):
            if not entry.isfile() or entry.name == SELF_PATH:
                continue
            data = tree.extractfile(entry).read()
            if b"\0" not in data:
                data = data.replace(b"\r\n", b"\n")
            digest.update(entry.name.encode() + b"\0" + hashlib.sha256(data).digest() + b"\n")
            count += 1
    assert (count, digest.hexdigest()) == (1486, "d382179e7322ccb802a5b01d4bbf7fa3f7c113a597c74e932fb52297b19f72b3")
    print(json.dumps({"historical_source": SOURCE, "historical_snapshot": "PASS", "count": count,
                      "digest": digest.hexdigest(), "current_snapshot": semantic_tree_identity()}))


if __name__ == "__main__":
    main()
