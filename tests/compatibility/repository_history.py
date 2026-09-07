"""Historical provenance audit, no longer a freeze of the live source tree.

P9 explicitly authorizes development and retirement without resetting an
ever-changing whole-repository hash. Immutable Git objects are audited here;
behavioral, authority, package and security tests protect the current product.
"""

from __future__ import annotations

import hashlib
import io
import subprocess
import tarfile
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE_SHA = "e45da340267de8d4b7b3a54177822aa641e3a601"
BASELINE_TAG = "kg-mnp-phase06-baseline-2026-08-30"
PROMPT01_HEAD_SHA = "a7114eef25f2f2a262cd69793a8d3e2b444836fc"
PROMPT02_HEAD_SHA = "d04e9b494a99932532ae9c359653878aa32261d7"
PROMPT03_HEAD_SHA = "52fb0bc064ed7a715ddc3269d23e89a1a78c917c"
PROMPT04_HEAD_SHA = "eccc5092831503974c8aa54f158e6674445b1cb4"
PROMPT05_HEAD_SHA = "7aaa039b2b2c4eb80fa959b956e6452a814bb5b3"
PROMPT06_HEAD_SHA = "1e31c53f6a441cf9c0c11b02ad9db5fca1ebabfc"
PROMPT07_HEAD_SHA = "9ae308ef86e74a08eb4daab1e20dd66cced87b16"
PROMPT08_HEAD_SHA = "9da17d126cb37166ff06084080770108da20afbe"
PROTECTED_ROOTS = (
    "src/kg_mnp",
    "schemas",
    "config",
    "domain_packs",
    "deploy",
    "scripts",
    "tests",
    "web",
    "workbench",
    "examples",
)
SELF_PATH = "tests/refactor/_historical_freeze.py"

# Fixed historical values, never updated for current product source changes.
EXPECTED_FILE_COUNT = 1498
EXPECTED_TREE_SHA256 = "595558b7b32f0b64cd84729349dc81aae58dde6bc93624188646766727ce69cd"


def _git(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ("git", *arguments),
        cwd=ROOT,
        check=check,
        capture_output=True,
    )


def assert_repository_history() -> None:
    baseline_target = _git("rev-list", "-n", "1", BASELINE_TAG).stdout.decode().strip()
    assert baseline_target == BASELINE_SHA, (
        f"immutable baseline tag target changed: {baseline_target or '<missing>'}"
    )
    for commit in (
        PROMPT01_HEAD_SHA,
        PROMPT02_HEAD_SHA,
        PROMPT03_HEAD_SHA,
        PROMPT04_HEAD_SHA,
        PROMPT05_HEAD_SHA,
        PROMPT06_HEAD_SHA,
        PROMPT07_HEAD_SHA,
        PROMPT08_HEAD_SHA,
        BASELINE_SHA,
        "3254656ffcd1c42b601d30b6ea313c6f81642bef",
        "9e7684bb9b988cec796e86ed9a6c51c59fa3a741",
        "4dc09d9cfb15da3746f108755593ceb9fe805cd7",
        "79b7d34125b0c5cb2d5fe8546e1f4e6a95ca8106",
        "3ef40b9cfbd657b55d8c5f446cfc247335db87f0",
        "06898e8ef3fbe93bd7e7a030f4361c0bef7a76c9",
    ):
        exists = _git("cat-file", "-e", f"{commit}^{{commit}}", check=False)
        assert exists.returncode == 0, f"historical authority commit unavailable: {commit}"
        ancestry = _git("merge-base", "--is-ancestor", commit, "HEAD", check=False)
        assert ancestry.returncode == 0, (
            f"historical authority commit is not an ancestor of HEAD: {commit}"
        )

    actual_count, actual_digest = historical_tree_identity()
    assert actual_count == EXPECTED_FILE_COUNT, (
        f"Historical P8 protected file count changed: {actual_count}"
    )
    assert actual_digest == EXPECTED_TREE_SHA256, (
        "Historical P8 Git object audit failed: "
        f"{actual_digest}"
    )


@lru_cache(maxsize=1)
def historical_tree_identity() -> tuple[int, str]:
    """Only immutable Git object bytes are cached; no live-state verdicts."""
    data = _git("archive", PROMPT08_HEAD_SHA, *[p for p in PROTECTED_ROOTS if p != "workbench"]).stdout
    digest, count = hashlib.sha256(), 0
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        for item in sorted(archive.getmembers(), key=lambda entry: entry.name):
            if not item.isfile() or item.name == SELF_PATH:
                continue
            content = archive.extractfile(item).read()
            if b"\0" not in content:
                content = content.replace(b"\r\n", b"\n")
            digest.update(item.name.encode() + b"\0" + hashlib.sha256(content).digest() + b"\n")
            count += 1
    return count, digest.hexdigest()
