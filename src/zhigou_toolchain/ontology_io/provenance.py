"""Reusable source identity for engineering receipts and research runs."""
from __future__ import annotations

import hashlib
import platform
import subprocess
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from zhigou_toolchain.contracts.canonical import semantic_hash


def source_fingerprint(root):
    root = Path(root).resolve(strict=True)
    names = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=root).decode("utf-8").split("\0")
    files = {}
    prefixes = ("src/", "tests/", "tools/", "scripts/", ".github/", "workbench/src/", "workbench/tests/", "domain_packs/", "config/")
    exact = {"pyproject.toml", "setup.py", "MANIFEST.in", "requirements-dev.lock", "pyrightconfig.json", ".gitattributes",
        "workbench/package.json", "workbench/package-lock.json"}
    for name in sorted(set(names) - {""}):
        if name.startswith(prefixes) or name in exact:
            path = root / name
            if path.is_symlink() or not path.resolve().is_relative_to(root):
                raise ValueError("SOURCE_FINGERPRINT_LINK_REJECTED")
            # Tracked deletions must change the fingerprint as well.
            files[name] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "DELETED"
    return {"digest": semantic_hash(files), "files": files, "policy": "GIT_TRACKED_AND_UNTRACKED_IMPLEMENTATION_V1"}


def source_identity(root):
    fingerprint = source_fingerprint(root)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    return {"commit": commit, "fingerprint": fingerprint,
        "identity_scope": "COMMIT_PLUS_ACTUAL_WORKTREE_BYTES_NOT_COMMIT_ALONE"}


def runtime_versions():
    versions = {}
    for package in ("rdflib", "jsonschema", "pyshacl", "networkx", "httpx", "pydantic"):
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            versions[package] = None
    return {"python": platform.python_version(), "os": platform.system(), "packages": versions}
