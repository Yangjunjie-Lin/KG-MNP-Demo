#!/usr/bin/env python
"""Seed CASE-01..CASE-09 assessments into local SQLite (explicit only)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kg_mnp_demo.application.assessment_service import AssessmentService
from kg_mnp_demo.application.persist import (
    assert_execution_consistency,
    find_orphan_artifacts,
    persist_assessment,
)
from kg_mnp_demo.loader import project_root
from kg_mnp_demo.namespaces import CASE_JSON_FILES
from kg_mnp_demo.storage import AssessmentRepository, ArtifactRepository, Database


def seed_json_case(
    case_id: str,
    service: AssessmentService,
    repo: AssessmentRepository,
    arts: ArtifactRepository,
) -> str:
    path = project_root() / "inputs" / CASE_JSON_FILES[case_id]
    payload = json.loads(path.read_text(encoding="utf-8"))
    result = persist_assessment(
        payload=payload,
        repository=repo,
        artifacts=arts,
        assessment_service=service,
        persist=True,
        force_recompute=True,
    )
    assert_execution_consistency(result)

    if case_id == "CASE-06":
        hist_path = project_root() / "inputs" / "case06_history.json"
        hist_payload = json.loads(hist_path.read_text(encoding="utf-8"))
        hist = persist_assessment(
            payload=hist_payload,
            repository=repo,
            artifacts=arts,
            assessment_service=service,
            persist=True,
            force_recompute=True,
        )
        assert_execution_consistency(hist)
        if hist.get("decision") != "ELIGIBLE":
            raise SystemExit(
                f"CASE-06 history must be ELIGIBLE under v1.0, got {hist.get('decision')}"
            )
        rule = next(
            (r for r in (hist.get("rule_results") or []) if r.get("rule_id") == "MNP-ELIG-005"),
            None,
        )
        if not rule or rule.get("version") != "1.0" or rule.get("status") != "PASS":
            raise SystemExit(f"CASE-06 history MNP-ELIG-005 must be v1.0 PASS, got {rule}")

    return result.get("decision")


def main() -> int:
    db = Database()
    repo = AssessmentRepository(db)
    arts = ArtifactRepository()
    service = AssessmentService()
    results = {}
    for case_id in sorted(CASE_JSON_FILES):
        decision = seed_json_case(case_id, service, repo, arts)
        results[case_id] = decision
        print(f"{case_id}: {decision}")

    orphans = find_orphan_artifacts(repo, arts)
    if orphans["orphan_directories"]:
        print("WARNING orphan artifacts:", orphans["orphan_directories"])
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(json.dumps({"artifacts": orphans}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
