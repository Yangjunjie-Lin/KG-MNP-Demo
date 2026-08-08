#!/usr/bin/env python3
"""Fetch exact WebVOWL and OWL2VOWL commits without mutable-branch fallback."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

from kg_mnp_demo.webvowl.policy import load_webvowl_policy


def _remove_readonly(func, path, _exc_info) -> None:
    os.chmod(path, stat.S_IWRITE)
    func(path)


def _run(args: list[str], cwd: Path) -> str:
    return subprocess.run(
        args, cwd=cwd, check=True, text=True, capture_output=True
    ).stdout.strip()


def fetch_one(
    repository: str, commit: str, destination: Path, expected_tree: str | None = None
) -> dict[str, str]:
    destination = destination.resolve()
    if destination.exists():
        shutil.rmtree(destination, onerror=_remove_readonly)
    destination.mkdir(parents=True)
    _run(["git", "init", "--quiet"], destination)
    _run(["git", "remote", "add", "origin", repository], destination)
    # Fetch only the requested object.  There is intentionally no branch/tag
    # fallback: a missing object is a hard failure instead of a mutable-source
    # substitution.
    _run(["git", "fetch", "--quiet", "origin", commit], destination)
    _run(["git", "checkout", "--quiet", "--detach", commit], destination)
    head = _run(["git", "rev-parse", "HEAD"], destination)
    if head != commit:
        raise RuntimeError(f"upstream SHA mismatch: expected {commit}, got {head}")
    status = _run(["git", "status", "--porcelain"], destination)
    if status:
        raise RuntimeError(f"upstream worktree is not clean: {destination}")
    tree = _run(["git", "rev-parse", "HEAD^{tree}"], destination)
    if expected_tree and tree != expected_tree:
        raise RuntimeError(
            f"upstream tree SHA mismatch: expected {expected_tree}, got {tree}"
        )
    return {"commit_sha": head, "tree_sha": tree}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("upstream-source"))
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    policy = load_webvowl_policy()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    result = {
        "webvowl": fetch_one(
            policy["webvowl"]["repository"],
            policy["webvowl"]["commit_sha"],
            out / "webvowl",
            policy["source_tree_hashes"]["webvowl"],
        ),
        "owl2vowl": fetch_one(
            policy["owl2vowl"]["repository"],
            policy["owl2vowl"]["commit_sha"],
            out / "owl2vowl",
            policy["source_tree_hashes"]["owl2vowl"],
        ),
    }
    result["license"] = {"webvowl": "MIT", "owl2vowl": "MIT"}
    payload = json.dumps(result, sort_keys=True, indent=2) + "\n"
    destination = args.json or out / "upstream-lock.json"
    destination.write_text(payload, encoding="utf-8", newline="\n")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
