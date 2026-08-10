from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STAGE_08_COMMIT = "4dc09d9cfb15da3746f108755593ceb9fe805cd7"
FROZEN_AUTHORITY_PATHS = (
    "ontology",
    "shapes",
    "schemas/modeling",
    "schemas/compilation",
    "schemas/graphdb",
    "schemas/webvowl",
    "schemas/publication",
    "config/modeling",
    "config/compilation",
    "config/graphdb",
    "config/webvowl",
    "src/kg_mnp_demo/modeling",
    "src/kg_mnp_demo/compilation",
    "src/kg_mnp_demo/graphdb",
    "src/kg_mnp_demo/webvowl",
    "src/kg_mnp_demo/publication",
)


def _git(*arguments: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ("git", *arguments),
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except OSError as exc:
        raise AssertionError(f"cannot execute git for Foundation freeze check: {exc}") from exc


def test_phase01_preserves_stage08_foundation_authority_bytes() -> None:
    baseline = _git("cat-file", "-e", f"{STAGE_08_COMMIT}^{{commit}}")
    assert baseline.returncode == 0, (
        "Stage 08 authority commit is unavailable; the freeze gate fails closed. "
        + baseline.stderr.strip()
    )

    ancestry = _git("merge-base", "--is-ancestor", STAGE_08_COMMIT, "HEAD")
    assert ancestry.returncode == 0, (
        "Stage 08 authority commit is not an ancestor of HEAD; "
        "the freeze comparison is not authoritative. "
        + ancestry.stderr.strip()
    )

    changes = _git(
        "diff",
        "--no-ext-diff",
        "--name-status",
        STAGE_08_COMMIT,
        "--",
        *FROZEN_AUTHORITY_PATHS,
    )
    assert changes.returncode == 0, changes.stderr.strip()
    assert not changes.stdout.strip(), (
        "Foundation authority paths differ from Stage 08:\n" + changes.stdout
    )

    untracked = _git(
        "ls-files",
        "--others",
        "--exclude-standard",
        "--",
        *FROZEN_AUTHORITY_PATHS,
    )
    assert untracked.returncode == 0, untracked.stderr.strip()
    assert not untracked.stdout.strip(), (
        "untracked files were added inside frozen Foundation authority paths:\n"
        + untracked.stdout
    )
