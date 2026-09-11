"""Explicit preparation/build entry; core runtime never downloads dependencies."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "runtime" / ("distribution-" + uuid4().hex))
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    npm = shutil.which("npm")
    if not npm:
        raise SystemExit("Node/npm is a build-time prerequisite")
    for args in ([npm, "ci", "--no-fund"], [npm, "run", "build"]):
        subprocess.run(args, cwd=ROOT / "workbench", check=True)
    subprocess.run([sys.executable, "-m", "build", "--wheel", "--sdist", "--outdir", str(output)], cwd=ROOT, check=True)
    # Companion examples are version-controlled assets only, never a Runtime
    # Workspace. Their bytes/locks are unchanged and not a second core default.
    names = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z", "domain_packs", "examples/ingestion"], cwd=ROOT).decode().split("\0")
    example_files = {}
    with zipfile.ZipFile(output / "toolchain-examples.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(set(filter(None, names))):
            path = ROOT / name
            if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
                raise ValueError("linked example asset is forbidden")
            content = path.read_bytes()
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, content)
            example_files[name] = hashlib.sha256(content).hexdigest()
    artifacts = [{"name":path.name,"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"bytes":path.stat().st_size}
                 for path in sorted(output.iterdir()) if path.is_file()]
    manifest = {"status":"BUILT_NOT_RELEASE_VERIFIED", "artifacts":artifacts, "example_files":example_files,
        "workbench_files": {p.relative_to(ROOT / "workbench/dist").as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT / "workbench/dist").rglob("*")) if p.is_file()},
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "dirty_source": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip())}
    (output / "build-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), **manifest}, indent=2))


if __name__ == "__main__":
    main()
