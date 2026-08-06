"""CLI security tests for package validate against rehashed forgeries."""

from __future__ import annotations

import json
from pathlib import Path

from kg_mnp_demo.modeling.cli import main
from kg_mnp_demo.modeling.review_identifiers import confirmed_package_id, package_semantic_hash

from ._helpers import EXAMPLES, ROOT, load_expected_package


def test_package_validate_cli_rejects_rehashed_ready_forgery(tmp_path: Path, capsys):
    package = load_expected_package("deferred-review")
    package["publication_manifest"]["package_status"] = "READY_FOR_COMPILATION"
    package["publication_manifest"]["compile_allowed"] = True
    package["publication_manifest"]["unresolved_blocking_issue_ids"] = []
    digest = package_semantic_hash(package)
    package["package_semantic_hash"] = digest
    package["package_id"] = confirmed_package_id(digest)
    forged = tmp_path / "forged.package.json"
    forged.write_text(json.dumps(package), encoding="utf-8")
    code = main(
        [
            "package",
            "validate",
            "--input",
            str(ROOT / "examples" / "modeling" / "inputs" / "conflicting-values.json"),
            "--proposal",
            str(
                ROOT
                / "examples"
                / "modeling"
                / "expected-proposals"
                / "conflicting-values.proposal.json"
            ),
            "--decision-log",
            str(EXAMPLES / "expected-logs" / "deferred-review.log.json"),
            "--package",
            str(forged),
        ]
    )
    captured = capsys.readouterr()
    assert code == 1
    assert "error" in captured.err.lower() or "SemanticValidationError" in captured.err
