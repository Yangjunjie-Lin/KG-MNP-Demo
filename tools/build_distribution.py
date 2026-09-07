"""Explicit preparation/build entry; core runtime never downloads dependencies."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    npm = shutil.which("npm")
    if not npm:
        raise SystemExit("Node/npm is a build-time prerequisite")
    for args in ([npm, "ci", "--no-fund"], [npm, "run", "build"]):
        subprocess.run(args, cwd=ROOT / "workbench", check=True)
    subprocess.run([sys.executable, "-m", "build", "--wheel", "--sdist", "--outdir", "runtime/p09-distribution"], cwd=ROOT, check=True)
    artifacts = [{"name":path.name,"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"bytes":path.stat().st_size}
                 for path in sorted((ROOT / "runtime/p09-distribution").iterdir()) if path.is_file()]
    print(json.dumps({"status":"BUILT_NOT_RELEASE_VERIFIED", "artifacts":artifacts}, indent=2))


if __name__ == "__main__":
    main()
