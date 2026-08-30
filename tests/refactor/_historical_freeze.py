"""Exact Prompt 1 snapshot gate for retained historical semantic layers.

The former phase gates compared paths byte-for-byte with commits that predate
the authorized package rename and Domain Pack extraction.  This gate preserves
their fail-closed intent by pinning the complete post-migration semantic tree,
while separately proving that each historical closure commit and the immutable
Prompt 1 baseline remain ancestors of the current branch.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
BASELINE_SHA = "e45da340267de8d4b7b3a54177822aa641e3a601"
BASELINE_TAG = "kg-mnp-phase06-baseline-2026-08-30"
PROTECTED_ROOTS = (
    "src/kg_mnp",
    "schemas",
    "config",
    "domain_packs/mnp",
    "deploy",
    "scripts",
    "tests",
    "web",
    "examples",
)
SELF_PATH = "tests/refactor/_historical_freeze.py"

# Updated only after the sanctioned Prompt 1 migration passes the retained
# semantic validators.  The helper excludes itself to avoid a self-referential
# digest; every other intended repository file below PROTECTED_ROOTS is bound.
EXPECTED_FILE_COUNT = 978
EXPECTED_TREE_SHA256 = "25bb5818de52132f71056d543f3b019aeb8bbbe9a04bf2b82ff522b89e7c4c24"


def _git(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ("git", *arguments),
        cwd=ROOT,
        check=check,
        capture_output=True,
    )


def semantic_tree_identity() -> tuple[int, str]:
    listed = _git(
        "ls-files",
        "-z",
        "--cached",
        "--others",
        "--exclude-standard",
        "--",
        *PROTECTED_ROOTS,
    ).stdout.decode("utf-8").split("\0")
    relative_paths = sorted(
        path for path in set(listed) if path and path != SELF_PATH
    )
    digest = hashlib.sha256()
    for relative in relative_paths:
        path = ROOT / PurePosixPath(relative)
        assert path.is_file(), f"protected semantic file is missing: {relative}"
        content = path.read_bytes()
        if b"\0" not in content:
            content = content.replace(b"\r\n", b"\n")
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(content).digest())
        digest.update(b"\n")
    return len(relative_paths), digest.hexdigest()


def assert_prompt01_semantic_snapshot(historical_commit: str) -> None:
    baseline_target = _git("rev-list", "-n", "1", BASELINE_TAG).stdout.decode().strip()
    assert baseline_target == BASELINE_SHA, (
        f"immutable baseline tag target changed: {baseline_target or '<missing>'}"
    )
    for commit in (historical_commit, BASELINE_SHA):
        exists = _git("cat-file", "-e", f"{commit}^{{commit}}", check=False)
        assert exists.returncode == 0, f"historical authority commit unavailable: {commit}"
        ancestry = _git("merge-base", "--is-ancestor", commit, "HEAD", check=False)
        assert ancestry.returncode == 0, (
            f"historical authority commit is not an ancestor of HEAD: {commit}"
        )

    actual_count, actual_digest = semantic_tree_identity()
    assert actual_count == EXPECTED_FILE_COUNT, (
        f"Prompt 1 protected semantic file count changed: {actual_count}"
    )
    assert actual_digest == EXPECTED_TREE_SHA256, (
        "Prompt 1 protected semantic tree changed without an audited snapshot update: "
        f"{actual_digest}"
    )
