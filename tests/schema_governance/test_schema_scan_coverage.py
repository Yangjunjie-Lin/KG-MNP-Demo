"""Exercise runtime legacy-identifier coverage for schema-bearing paths."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import check_runtime_legacy_terms as checker  # noqa: E402


HTTP_DOCUMENT_NAMESPACE = "http://example.org/" + "kg-mnp/"
HTTPS_SCHEMA_NAMESPACE = "https://example.org/" + "kg-mnp/"


def _initialize_repository(root: Path) -> None:
    subprocess.run(
        ["git", "init", "--quiet"],
        cwd=root,
        check=True,
        capture_output=True,
    )


def _write_policy(
    root: Path,
    *,
    scan_roots: list[str],
    allowed_occurrences: list[dict[str, object]] | None = None,
) -> Path:
    policy_path = root / "legacy-policy.yaml"
    policy_path.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "scan_roots": scan_roots,
                "legacy_terms": sorted(checker.REQUIRED_LEGACY_TERMS),
                "allowed_occurrences": allowed_occurrences or [],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return policy_path


def _write_asset(root: Path, relative_path: str, text: str) -> Path:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_production_policy_covers_schema_roots_and_legacy_namespaces() -> None:
    policy = checker.load_policy()

    assert "schemas" in policy.scan_roots
    assert "examples" in policy.scan_roots
    assert {
        "http://example.org/" + "kg-mnp#",
        HTTP_DOCUMENT_NAMESPACE,
        HTTPS_SCHEMA_NAMESPACE,
    } <= set(policy.terms)


@pytest.mark.parametrize(
    ("relative_path", "legacy_identifier"),
    [
        ("schemas/term.schema.json", "http://example.org/" + "kg-mnp#"),
        ("schemas/test.schema.json", HTTP_DOCUMENT_NAMESPACE),
        (
            "examples/eligibility-use-case/schemas/test.schema.json",
            HTTPS_SCHEMA_NAMESPACE,
        ),
    ],
)
def test_schema_paths_reject_legacy_identifiers(
    tmp_path: Path,
    relative_path: str,
    legacy_identifier: str,
) -> None:
    _initialize_repository(tmp_path)
    _write_asset(
        tmp_path,
        relative_path,
        '{"$id": "' + legacy_identifier + 'schemas/old.schema.json"}\n',
    )
    policy_path = _write_policy(tmp_path, scan_roots=["schemas", "examples"])

    result = checker.audit_repository(root=tmp_path, policy_path=policy_path)

    assert not result.ok
    assert any(
        "unapproved legacy identifier" in error and relative_path in error
        for error in result.errors
    )


def test_migration_history_requires_an_exact_allowance(tmp_path: Path) -> None:
    _initialize_repository(tmp_path)
    relative_path = "docs/migration/schema-iri-history.md"
    line_text = "Previous schema namespace: " + HTTPS_SCHEMA_NAMESPACE
    asset_path = _write_asset(tmp_path, relative_path, line_text + "\n")
    policy_path = _write_policy(
        tmp_path,
        scan_roots=["docs/migration"],
        allowed_occurrences=[
            {
                "term": HTTPS_SCHEMA_NAMESPACE,
                "path": relative_path,
                "line_text": line_text,
                "count": 1,
                "category": "migration_source",
                "reason": "Exact historical schema namespace reference.",
            }
        ],
    )

    approved_result = checker.audit_repository(root=tmp_path, policy_path=policy_path)
    assert approved_result.ok, "\n".join(approved_result.errors)

    asset_path.write_text(
        line_text + "\nUnapproved duplicate: " + HTTPS_SCHEMA_NAMESPACE + "\n",
        encoding="utf-8",
    )
    rejected_result = checker.audit_repository(root=tmp_path, policy_path=policy_path)

    assert not rejected_result.ok
    assert any(
        "unapproved legacy identifier" in error
        for error in rejected_result.errors
    )
