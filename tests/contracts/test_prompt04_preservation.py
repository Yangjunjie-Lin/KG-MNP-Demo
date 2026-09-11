from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROMPT03 = "52fb0bc064ed7a715ddc3269d23e89a1a78c917c"


def _git_bytes(path: str) -> bytes:
    return subprocess.run(
        ["git", "show", f"{PROMPT03}:{path}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout


def _git_paths(prefix: str) -> list[str]:
    output = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", PROMPT03, "--", prefix],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [item for item in output.splitlines() if item]


def _filtered_worktree_blob(path: str) -> str:
    current_path = path.replace("src/kg_mnp/", "src/zhigou_toolchain/")
    return subprocess.run(
        ["git", "hash-object", f"--path={path}", current_path],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _baseline_blob(path: str) -> str:
    return subprocess.run(
        ["git", "rev-parse", f"{PROMPT03}:{path}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_prompt03_34_contract_schema_bytes_are_unchanged() -> None:
    catalog = json.loads(_git_bytes("src/kg_mnp/contracts/catalog.json"))
    assert len(catalog["contracts"]) == 34
    for item in catalog["contracts"]:
        path = f"src/kg_mnp/contracts/{item['resource_path']}"
        assert _filtered_worktree_blob(path) == _baseline_blob(path), path


def test_plugin_api_1_0_manifests_and_pack_locks_are_byte_identical() -> None:
    manifests = _git_paths("src/kg_mnp/plugins/builtin/manifests")
    assert len(manifests) == 13
    for path in manifests:
        assert _filtered_worktree_blob(path) == _baseline_blob(path), path
    # Forestry 0.2.0 is the explicitly authorized synthetic content upgrade;
    # its own lock/version/no-real-claim tests replace the old 0.1.0 freeze.
    for pack in ("minimal", "mnp"):
        path = f"domain_packs/{pack}/pack.lock.json"
        assert _filtered_worktree_blob(path) == _baseline_blob(path), path
