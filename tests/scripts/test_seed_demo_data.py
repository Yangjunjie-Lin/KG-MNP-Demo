"""Seed demo data produces consistent CASE-06 history and no orphan artifacts."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from kg_mnp_demo.application.assessment_service import AssessmentService
from kg_mnp_demo.application.persist import find_orphan_artifacts
from kg_mnp_demo.namespaces import CASE_JSON_FILES
from kg_mnp_demo.storage import AssessmentRepository, ArtifactRepository, Database

ROOT = Path(__file__).resolve().parents[2]


def _load_seed_module():
    path = ROOT / "scripts" / "seed_demo_data.py"
    spec = importlib.util.spec_from_file_location("seed_demo_data", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_seed_demo_data_case06_and_no_orphans(tmp_path):
    seed_mod = _load_seed_module()
    runtime = tmp_path / "runtime_data"
    db = Database(runtime / "kg_mnp.sqlite3")
    repo = AssessmentRepository(db)
    arts = ArtifactRepository(runtime / "executions")
    service = AssessmentService()

    for _ in range(2):
        for case_id in sorted(CASE_JSON_FILES):
            seed_mod.seed_json_case(case_id, service, repo, arts)

    rows = repo.list_executions(limit=1000)
    case06 = [r for r in rows if r["case_id"] == "CASE-06"]
    assert len(case06) == 2

    hist = None
    cur = None
    for summary in case06:
        record = repo.get_execution(summary["execution_id"])
        result = record["result"]
        if str(result.get("assessment_time", "")).startswith("2026-05-15"):
            hist = result
        if str(result.get("assessment_time", "")).startswith("2026-07-01"):
            cur = result
    assert hist is not None and cur is not None
    assert hist["decision"] == "ELIGIBLE"
    assert cur["decision"] == "BLOCKED"
    hist_rule = next(r for r in hist["rule_results"] if r["rule_id"] == "MNP-ELIG-005")
    cur_rule = next(r for r in cur["rule_results"] if r["rule_id"] == "MNP-ELIG-005")
    assert hist_rule["version"] == "1.0" and hist_rule["status"] == "PASS"
    assert cur_rule["version"] == "1.1" and cur_rule["status"] == "FAIL"

    orphans = find_orphan_artifacts(repo, arts)
    assert orphans["orphan_directories"] == []
