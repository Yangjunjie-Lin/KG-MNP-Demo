"""Whole tracked/untracked non-ignored tree freeze including docs, configs and tests."""
from __future__ import annotations

import subprocess
from importlib.metadata import distributions

from .exchange_io import checked_path, digest, json_bytes, read_bounded, require

POLICY = "GIT_TRACKED_AND_UNTRACKED_NONIGNORED_FILE_BYTES_V1"


def source_snapshot(root):
    root = checked_path(root)
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=root)
    names = sorted(set(git("ls-files", "--cached", "--others", "--exclude-standard", "-z").decode("utf-8").split("\0")) - {""})
    files = {}
    for name in names:
        path = checked_path(root / name)
        require(path.is_relative_to(root), "SNAPSHOT_PATH_OUTSIDE_ROOT")
        files[name] = {"sha256": digest(read_bounded(path, limit=256_000_000)), "size_bytes": path.stat().st_size} if path.is_file() else {"status": "DELETED"}
    core = {"policy": POLICY, "algorithm": "SHA256_SORTED_COMPACT_UTF8_JSON_LF_OF_HEAD_DIFF_AND_FILE_MAP",
        "git_head": git("rev-parse", "HEAD").decode().strip(), "dirty_diff_sha256": digest(git("diff", "--binary", "HEAD", "--")),
        "status_sha256": digest(git("status", "--porcelain=v1", "-z")), "files": files,
        "installed_python_packages": dict(sorted((str(d.metadata["Name"]), d.version) for d in distributions() if d.metadata["Name"]))}
    jar = root / "third_party/downloads/robot-1.9.7.jar"
    core["reasoner_asset"] = {"sha256": digest(read_bounded(jar, limit=256_000_000)), "size_bytes": jar.stat().st_size} if jar.is_file() else {"status": "NOT_AVAILABLE"}
    return {**core, "snapshot_id": digest(json_bytes(core))}


def validate_snapshot(snapshot):
    require(snapshot["policy"] == POLICY and snapshot["files"], "SOURCE_SNAPSHOT_SCOPE_INVALID")
    require(snapshot["snapshot_id"] == digest(json_bytes({k: v for k, v in snapshot.items() if k != "snapshot_id"})), "SOURCE_SNAPSHOT_DIGEST_MISMATCH")
    require(any(p.startswith("tests/") for p in snapshot["files"]) and any(p.startswith("config/") for p in snapshot["files"])
        and "workbench/vite.config.ts" in snapshot["files"] and "pyproject.toml" in snapshot["files"], "SOURCE_SNAPSHOT_REQUIRED_SCOPE_MISSING")
    return snapshot["snapshot_id"]


def assert_unchanged(root, expected):
    actual = source_snapshot(root)
    require(actual == expected, "FROZEN_SOURCE_CHANGED_RESTART_VERIFICATION")
    return actual["snapshot_id"]
