"""A passing process exit alone is not complete fixed-revision evidence."""
import hashlib
import json

import pytest

from tools.verify_release_candidate import summarize


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def fixture(root, *, fault=None):
    write(root / "collection/collection.json", ["a", "b"])
    for name, node in (("serial", "a"), ("parallel", "b")):
        write(root / (name + ".json"), ["a" if fault == "overlap" else node])
        reports = [{"nodeid": node, "when": phase, "outcome": "passed"} for phase in ("setup", "call", "teardown")]
        if name == "serial":
            if fault == "partial":
                reports.pop()
            elif fault == "failed-zero-exit":
                reports[1]["outcome"] = "failed"
            elif fault == "duplicate":
                reports.append(reports[1])
            elif fault == "skip":
                reports[0].update(outcome="skipped", skip_reason="explicit platform limit")
                reports.pop(1)
        write(root / name / "reports.json", reports)
        (root / name / "junit.xml").write_text("<testsuites/>", encoding="utf-8")
        (root / name / "command.log").write_text("synthetic orchestration unit receipt", encoding="utf-8")
        files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (root / name).iterdir()}
        write(root / name / "receipt.json", {"exit_code": 0, "files": files})
    if fault == "tamper":
        (root / "serial/command.log").write_text("modified", encoding="utf-8")


def test_disjoint_complete_receipts_do_not_claim_release(tmp_path):
    fixture(tmp_path)
    result = summarize(tmp_path)
    assert result["backend_status"] == "PASS"
    assert result["counts"]["passed"] == 2
    assert result["release_status"] == "NOT_ESTABLISHED_BY_BACKEND_TESTS"


@pytest.mark.parametrize("fault", ["overlap", "partial", "failed-zero-exit", "duplicate", "tamper"])
def test_partial_inconsistent_or_rewritten_receipts_cannot_pass(tmp_path, fault):
    fixture(tmp_path, fault=fault)
    assert summarize(tmp_path)["backend_status"] == "FAIL"


def test_platform_skip_is_reported_separately_never_counted_as_pass(tmp_path):
    fixture(tmp_path, fault="skip")
    result = summarize(tmp_path)
    assert result["counts"]["passed"] == result["counts"]["skipped"] == 1
    assert result["skips"][0]["reason"] == "explicit platform limit"
