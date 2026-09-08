"""Build Wheel/Sdist/examples and verify two fresh, non-editable installations.

This validates the running platform only; Windows execution never certifies Linux.
The directory and environments are unique and retained with their receipts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import sys
import tarfile
import zipfile
from pathlib import Path, PurePosixPath
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def extract_sdist(source: Path, target: Path) -> Path:
    target.mkdir(parents=True, exist_ok=False)
    with tarfile.open(source) as archive:
        members = archive.getmembers()
        for member in members:
            relative = PurePosixPath(member.name)
            if relative.is_absolute() or ".." in relative.parts or "\\" in member.name or ":" in member.name or not (member.isdir() or member.isfile()):
                raise ValueError("unsafe Sdist member")
        archive.extractall(target, members=members, filter="data")
    roots = list(target.iterdir())
    if len(roots) != 1 or not (roots[0] / "pyproject.toml").is_file():
        raise ValueError("Sdist must have one project root")
    return roots[0]


def wheel_payload(wheel: Path) -> dict:
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("duplicate Wheel entries")
        result = {}
        for name in names:
            parts = PurePosixPath(name).parts
            if name.startswith("/") or ".." in parts or "\\" in name or ":" in name:
                raise ValueError("unsafe Wheel member")
            if any(part in {"node_modules", "runtime", "__pycache__", ".env"} for part in parts) or name.endswith((".pyc", ".sqlite3", ".license", ".key")):
                raise ValueError("runtime or sensitive material in Wheel")
            # RECORD necessarily changes with metadata; compare actual installed
            # package/resource payload rather than ZIP timestamps/compression.
            if name.startswith("kg_mnp/"):
                result[name] = hashlib.sha256(archive.read(name)).hexdigest()
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "runtime_logs/p09" / ("distribution-" + uuid4().hex))
    parser.add_argument("--prebuilt", type=Path, help="verify these exact existing artifacts on another platform, without requiring Node")
    args = parser.parse_args()
    directory = args.output.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(ROOT / "tools"))
    from verify_release_candidate import run
    receipts = {}

    def command(name, argv, *, cwd=ROOT):
        receipts[name] = run(directory, name, argv, cwd=cwd,
            environment={"PYTHONPATH": "", "PYTHONHOME": ""})
        if receipts[name]["exit_code"]:
            raise RuntimeError(f"Distribution verification command failed: {name}")

    status = "FAIL"
    try:
        built = args.prebuilt.resolve(strict=True) if args.prebuilt else directory / "artifacts"
        if not args.prebuilt:
            command("build", [sys.executable, str(ROOT / "tools/build_distribution.py"), "--output", str(built)])
        manifest = json.loads((built / "build-manifest.json").read_bytes())
        for artifact in manifest["artifacts"]:
            name = artifact["name"]
            if Path(name).name != name or "/" in name or "\\" in name or ":" in name:
                raise ValueError("invalid artifact manifest filename")
            file = built / name
            assert not file.is_symlink() and file.stat().st_size == artifact["bytes"]
            assert hashlib.sha256(file.read_bytes()).hexdigest() == artifact["sha256"]
        wheel, = built.glob("*.whl")
        sdist, = built.glob("*.tar.gz")
        unpacked = extract_sdist(sdist, directory / "sdist-source")
        rebuilt = directory / "rebuilt"
        command("rebuild-sdist", [sys.executable, "-m", "build", "--wheel", "--outdir", str(rebuilt), str(unpacked)])
        rebuilt_wheel, = rebuilt.glob("*.whl")
        payload = wheel_payload(wheel)
        assert payload == wheel_payload(rebuilt_wheel), "Wheel rebuilt from Sdist has different package bytes"
        assert {name.removeprefix("kg_mnp/workbench_static/"): digest for name, digest in payload.items() if name.startswith("kg_mnp/workbench_static/")} == manifest["workbench_files"]
        examples = directory / "examples"
        examples.mkdir()
        with zipfile.ZipFile(built / "toolchain-examples.zip") as archive:
            assert set(archive.namelist()) == set(manifest["example_files"])
            for name in archive.namelist():
                relative = PurePosixPath(name)
                assert not relative.is_absolute() and ".." not in relative.parts and "\\" not in name and ":" not in name
                content = archive.read(name)
                assert hashlib.sha256(content).hexdigest() == manifest["example_files"][name]
                destination = examples / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(content)
        historical = directory / "historical-compiler-0.5.0.kgop"
        shutil.copyfile(ROOT / "tests/compatibility/fixtures/compiler-0.5.0.kgop", historical)
        for name, artifact in (("wheel", wheel), ("rebuilt-wheel", rebuilt_wheel)):
            environment = directory / (name + "-venv")
            command(name + "-create-env", [sys.executable, "-m", "venv", str(environment)])
            python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            command(name + "-install", [str(python), "-I", "-m", "pip", "install", "--disable-pip-version-check", "-c", str(ROOT / "requirements-dev.lock"), str(artifact)])
            command(name + "-pip-check", [str(python), "-I", "-m", "pip", "check"])
            command(name + "-probe", [str(python), "-I", str(ROOT / "tools/probe_installed_distribution.py"),
                "--directory", str(directory / (name + "-runtime")), "--packs", str(examples / "domain_packs"), "--historical-package", str(historical)], cwd=directory)
        status = "PASS"
    finally:
        summary = {"status": status, "platform": platform.platform(), "python": sys.version, "commands": receipts,
            "scope": "Current platform only; no Browser E2E/other-platform/release approval implied",
            "artifacts": {p.relative_to(directory).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in directory.glob("*/*") if p.is_file() and p.suffix in {".whl", ".gz", ".zip", ".json"}}}
        if "manifest" in locals():
            summary["input_artifacts"] = manifest["artifacts"]
            summary["build_source_commit"] = manifest["source_commit"]
            summary["dirty_build"] = manifest["dirty_source"]
        (directory / "distribution-verification.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps({"status": status, "evidence": str(directory)}), flush=True)


if __name__ == "__main__":
    main()
