#!/usr/bin/env python3
"""Build and run two frozen OWL2VOWL conversions in network-none containers."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]


def _git(repository: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        timeout=30,
    )


def _git_value(repository: Path, *arguments: str) -> str | None:
    completed = _git(repository, *arguments)
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def _safe_exact_worktree(
    repository: Path, *, expected_commit: str, expected_tree: str, remote: str
) -> bool:
    """Require an exact, detached Git checkout with no extra filesystem input."""
    try:
        repository = repository.resolve(strict=True)
        git_marker = repository / ".git"
        if (
            not repository.is_dir()
            or repository.is_symlink()
            or not git_marker.is_dir()
            or git_marker.is_symlink()
        ):
            return False

        top = _git_value(repository, "rev-parse", "--show-toplevel")
        git_dir = _git_value(repository, "rev-parse", "--absolute-git-dir")
        if top is None or Path(top).resolve() != repository:
            return False
        if git_dir is None or Path(git_dir).resolve() != git_marker.resolve():
            return False
        if _git_value(repository, "remote", "get-url", "origin") != remote:
            return False

        # A staged tree reconstructed without a commit is not an upstream
        # checkout.  HEAD must be the frozen commit and detached exactly as the
        # retrieval policy requires.
        if (
            _git_value(repository, "rev-parse", "--verify", "HEAD^{commit}")
            != expected_commit
            or _git_value(repository, "rev-parse", "HEAD^{tree}") != expected_tree
            or _git(repository, "symbolic-ref", "-q", "HEAD").returncode == 0
        ):
            return False

        status = _git(
            repository,
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--ignore-submodules=none",
        )
        if status.returncode != 0 or status.stdout:
            return False
        # `git status` intentionally hides ignored files.  They are still
        # additional Docker build inputs, so exact-source readiness rejects
        # them as well.
        ignored = _git(
            repository,
            "ls-files",
            "--others",
            "--ignored",
            "--exclude-standard",
            "-z",
        )
        if ignored.returncode != 0 or ignored.stdout:
            return False

        indexed = _git(repository, "ls-files", "--stage", "-z")
        if indexed.returncode != 0:
            return False
        tracked: set[str] = set()
        for record in indexed.stdout.split("\0"):
            if not record:
                continue
            metadata, separator, relative = record.partition("\t")
            fields = metadata.split()
            path = PurePosixPath(relative)
            if (
                not separator
                or len(fields) != 3
                or fields[0] not in {"100644", "100755"}
                or fields[2] != "0"
                or path.is_absolute()
                or ".." in path.parts
                or "\\" in relative
            ):
                return False
            tracked.add(path.as_posix())

        tracked_directories = {
            PurePosixPath(*path.parts[:index]).as_posix()
            for relative in tracked
            for path in (PurePosixPath(relative),)
            for index in range(1, len(path.parts))
        }
        # Inspect the actual filesystem, not just Git's index.  This rejects
        # symlink/junction escapes, ignored files, nested repositories, and
        # untracked empty directories that Docker COPY would otherwise see.
        for current, directories, files in os.walk(repository, followlinks=False):
            current_path = Path(current)
            if current_path == repository:
                directories[:] = [name for name in directories if name != ".git"]
            for name in list(directories):
                candidate = current_path / name
                relative = candidate.relative_to(repository).as_posix()
                is_junction = bool(getattr(candidate, "is_junction", lambda: False)())
                if (
                    candidate.is_symlink()
                    or is_junction
                    or not candidate.resolve().is_relative_to(repository)
                    or relative not in tracked_directories
                ):
                    return False
            for name in files:
                candidate = current_path / name
                relative = candidate.relative_to(repository).as_posix()
                if (
                    candidate.is_symlink()
                    or not candidate.resolve().is_relative_to(repository)
                    or relative not in tracked
                ):
                    return False
        return True
    except (OSError, UnicodeError, subprocess.SubprocessError, ValueError):
        return False


def _exact_sources_ready(policy: dict, *, root: Path = ROOT) -> bool:
    source_root = Path(root).resolve() / "upstream-source"
    lock_path = source_root / "upstream-lock.json"
    if source_root.is_symlink() or lock_path.is_symlink() or not lock_path.is_file():
        return False
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        for name in ("webvowl", "owl2vowl"):
            expected_commit = policy[name]["commit_sha"]
            expected_tree = policy["source_tree_hashes"][name]
            if (
                lock[name]["commit_sha"] != expected_commit
                or lock[name]["tree_sha"] != expected_tree
            ):
                return False
            candidate = source_root / name
            resolved = candidate.resolve(strict=True)
            if (
                candidate.is_symlink()
                or not resolved.is_relative_to(source_root.resolve())
                or not _safe_exact_worktree(
                    resolved,
                    expected_commit=expected_commit,
                    expected_tree=expected_tree,
                    remote=policy[name]["repository"],
                )
            ):
                return False
        return True
    except (
        OSError,
        KeyError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
        subprocess.SubprocessError,
    ):
        return False


def main() -> int:
    from kg_mnp_demo.compilation.manifest import json_bytes
    from kg_mnp_demo.webvowl.converter import convert_with_owl2vowl_docker
    from kg_mnp_demo.webvowl.coverage import build_coverage_report
    from kg_mnp_demo.webvowl.normalizer import (
        normalize_vowl_json,
        normalized_vowl_bytes,
    )
    from kg_mnp_demo.webvowl.policy import load_webvowl_policy
    from kg_mnp_demo.webvowl.source import build_visualization_source

    policy = load_webvowl_policy()
    image = "kg-mnp-owl2vowl:" + policy["owl2vowl"]["commit_sha"][:12]
    if not _exact_sources_ready(policy):
        subprocess.run(
            [
                "python",
                "scripts/fetch_webvowl_upstream.py",
                "--output",
                "upstream-source",
            ],
            cwd=ROOT,
            check=True,
        )
    if not _exact_sources_ready(policy):
        raise RuntimeError(
            "exact upstream sources are not a clean, safe checkout of the frozen SHAs"
        )
    subprocess.run(
        [
            "docker",
            "build",
            "--target",
            "owl2vowl-cli-builder",
            "-t",
            image,
            "-f",
            "deploy/webvowl/Dockerfile.integration",
            ".",
        ],
        cwd=ROOT,
        check=True,
    )
    source = build_visualization_source()
    raw = [convert_with_owl2vowl_docker(source, image=image) for _ in range(2)]
    raw_bytes = [json_bytes(value) for value in raw]
    normalized = [
        normalize_vowl_json(
            value, exclusion_policy=policy["normalization_exclusion_policy"]
        )
        for value in raw
    ]
    normalized_bytes = [normalized_vowl_bytes(value) for value in normalized]
    coverage = build_coverage_report(normalized[0], source=source)
    differences = []
    if raw_bytes[0] != raw_bytes[1]:
        differences.append("raw_vowl")
    if normalized_bytes[0] != normalized_bytes[1]:
        differences.append("normalized_vowl")
    if coverage["status"] != "PASS":
        differences.append("coverage")
    audited_raw = (ROOT / policy["conversion"]["audited_raw_fixture"]).read_bytes()
    if any(value != audited_raw for value in raw_bytes):
        differences.append("audited_raw_fixture")
    if any(
        hashlib.sha256(value).hexdigest()
        != policy["conversion"]["audited_normalized_sha256"]
        for value in normalized_bytes
    ):
        differences.append("audited_normalized_fixture")
    out = ROOT / "runtime_outputs/webvowl/raw"
    out.mkdir(parents=True, exist_ok=True)
    (out / "run-1.json").write_bytes(raw_bytes[0])
    (out / "run-2.json").write_bytes(raw_bytes[1])
    (out / "normalized.json").write_bytes(normalized_bytes[0])
    report = {
        "contract_version": "1.0",
        "converter": "OWL2VOWL",
        "version": policy["owl2vowl"]["source_version"],
        "network": "none",
        "raw_run_1_sha256": hashlib.sha256(raw_bytes[0]).hexdigest(),
        "raw_run_2_sha256": hashlib.sha256(raw_bytes[1]).hexdigest(),
        "normalized_run_1_sha256": hashlib.sha256(normalized_bytes[0]).hexdigest(),
        "normalized_run_2_sha256": hashlib.sha256(normalized_bytes[1]).hexdigest(),
        "sha256_differences": differences,
        "coverage_status": coverage["status"],
    }
    (out / "conversion-report.json").write_bytes(json_bytes(report))
    print(json.dumps(report, sort_keys=True))
    return 0 if not differences else 1


if __name__ == "__main__":
    raise SystemExit(main())
