"""Historical failures remain inspectable, byte-preserved and non-current."""
import hashlib
import json
import zipfile

from tools.redact_historical_evidence import (
    ARCHIVE,
    FILES,
    ROOT,
    published_view,
    redact,
    verify,
)


def test_all_originals_and_only_documented_redactions_are_preserved():
    assert verify() == 5
    with zipfile.ZipFile(ROOT / ARCHIVE) as archive:
        for path in FILES:
            raw = archive.read(path)
            current = json.loads((ROOT / path).read_bytes())
            assert current == published_view(path, raw)
            assert current["publication_provenance"]["original_sha256"] == hashlib.sha256(raw).hexdigest()
            assert current["publication_provenance"]["current_source_validation"] == "NOT_CLAIMED_BY_HISTORICAL_EVIDENCE"


def test_redaction_preserves_results_types_and_relative_paths():
    result = {"status": "FAIL", "passed": False, "calls": 3, "usage": None,
              "path": "runtime_reports/check/failure.xml", "sha256": "a" * 64}
    assert redact(result) == result


def test_original_archive_and_views_pass_unmodified_hygiene_rules():
    from scripts.check_repo_hygiene import run_checks
    assert run_checks([*FILES, ARCHIVE]) == []
