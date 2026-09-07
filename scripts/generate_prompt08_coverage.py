"""Generate truthful operation/requirement coverage from actual passing receipts."""
from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree

from kg_mnp.services.operations import HANDLERS, build_operation_catalog

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "tests/services/test_prompt08_boundary.py::"
OWNER_TEST = "test_owner_open_validate_catalog_pack_inspect_and_empty_environment"
SUCCESS = {
    "project.create": "test_created_project_is_valid_workspace_without_path_disclosure",
    "project.open": OWNER_TEST, "project.validate": OWNER_TEST,
    "project.list": "test_project_list_and_open_reject_empty_scope_outsider",
    "project.lock": "test_formal_lock_check_is_byte_preserving_and_rejects_tampering",
    "domain-pack.discover": "test_discovery_is_real_and_available_before_project_creation",
    "domain-pack.inspect": OWNER_TEST,
    "job.get": "test_legacy_job_payloads_are_not_returned_and_cancel_is_scoped",
    "job.events": "test_legacy_job_payloads_are_not_returned_and_cancel_is_scoped",
    "operation.catalog": OWNER_TEST, "environment.inspect": OWNER_TEST,
}
ROUTES = {
    "project.create": "POST /api/v1/projects", "project.list": "GET /api/v1/projects",
    "project.open": "GET /api/v1/projects/{project_id}",
    "project.validate": "GET /api/v1/projects/{project_id}/validation",
    "project.lock": "POST /api/v1/projects/{project_id}/lock",
    "domain-pack.discover": "GET /api/v1/domain-packs",
    "job.get": "GET /api/v1/jobs/{job_id}", "job.events": "GET /api/v1/jobs/{job_id}/events",
    "operation.catalog": "GET /api/v1/operations",
}
REQUIREMENT_TESTS = {
    "A1": ["test_created_project_is_valid_workspace_without_path_disclosure", "test_pack_version_unavailable_does_not_create_project",
           "test_formal_lock_check_is_byte_preserving_and_rejects_tampering", "test_incomplete_p7_project_is_not_silently_upgraded"],
    "A2": ["test_discovery_is_real_and_available_before_project_creation", "test_empty_pack_root_and_parse_failure_are_distinct", OWNER_TEST],
    "A3": ["test_project_list_and_open_reject_empty_scope_outsider", "test_jobs_cannot_be_read_by_another_principal",
           "test_legacy_job_payloads_are_not_returned_and_cancel_is_scoped", "test_service_account_cannot_approve_scope_or_reviews"],
    "A4": ["test_health_is_minimal_even_for_authenticated_reader", "test_resource_api_and_compatibility_dto_reject_unknown_fields"],
    "A5": ["test_sync_idempotency_rejects_changed_body", "test_sync_idempotency_is_concurrent_and_principal_scoped",
           "test_job_idempotency_scope_includes_principal_project_operation", "test_revoked_job_principal_cannot_execute",
           "test_expired_lease_cannot_complete_or_renew_and_is_recovery_required", "test_failed_sync_request_and_unknown_outcome_are_not_reexecuted"],
}


def main():
    passed = set()
    receipt_paths = []
    for receipt in (ROOT / "runtime_logs/prompt08").glob("*/receipt.json"):
        value = json.loads(receipt.read_text(encoding="utf-8"))
        if value["exit_code"] != 0 or not (receipt.parent / "junit.xml").is_file():
            continue
        receipt_paths.append(receipt.relative_to(ROOT).as_posix())
        for case in ElementTree.parse(receipt.parent / "junit.xml").findall(".//testcase"):
            if not any(case.find(name) is not None for name in ("failure", "error", "skipped")):
                passed.add(case.attrib["classname"].replace(".", "/") + ".py::" + case.attrib["name"])
    rows = []
    for name, operation in build_operation_catalog().items():
        positive = PREFIX + SUCCESS[name] if name in SUCCESS else None
        if name == "registry.verify":
            positive = "tests/services/test_unified_service.py::test_project_isolation_is_enforced_by_service"
        negative = PREFIX + f"test_missing_permission_is_denied_before_handler[{name}]" if name in HANDLERS else None
        status = "DECLARED_ONLY" if name not in HANDLERS else "IMPLEMENTED_AND_TESTED" if positive in passed and negative in passed else "IMPLEMENTED_NOT_VERIFIED"
        rows.append({"operation_id": name, "service_handler": HANDLERS.get(name),
                     "input_contract": operation.request_contract, "output_contract": operation.response_contract,
                     "contract_boundary": "closed service DTO; public domain contracts unchanged" if name in HANDLERS else "catalogue declaration only",
                     "required_permissions": list(operation.required_permissions),
                     "api_route": ROUTES.get(name, "POST /api/v1/operations/" + name),
                     "execution_mode": operation.execution_mode,
                     "success_test_nodeid": positive if positive in passed else None,
                     "negative_test_nodeid": negative if negative in passed else None,
                     "status": status, "blocked_reason": "No service-to-core handler; rejected before enqueue" if name not in HANDLERS else "Positive and negative service success coverage incomplete" if status == "IMPLEMENTED_NOT_VERIFIED" else None})
    output = ROOT / "docs/verification"
    coverage = {"source_sha": "9ae308ef86e74a08eb4daab1e20dd66cced87b16", "operation_count": len(rows),
                "backend_gate": "FAIL", "receipts": sorted(receipt_paths), "operations": rows,
                "status_counts": {status: sum(row["status"] == status for row in rows) for status in
                                  ("IMPLEMENTED_AND_TESTED", "IMPLEMENTED_NOT_VERIFIED", "DECLARED_ONLY", "EXTERNAL_DEPENDENCY_BLOCKED", "OUT_OF_SCOPE")},
                "note": "Passing a rejection test is never positive business-handler coverage. APIs for missing required resources are not implemented."}
    (output / "prompt-08-service-coverage.json").write_text(json.dumps(coverage, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    requirements = [
        ("baseline", "PASS", "fixed SHA, clean entry, P1-P7 ancestry and old snapshot checked"),
        ("A1", "PASS", "real Workspace/Lock mapping; legacy incomplete records retained"),
        ("A2", "PASS", "real exact-version local Pack discovery, empty/error/denied distinct"),
        ("A3", "PARTIAL", "project/job isolation tested; evidence resource/download not implemented"),
        ("A4", "PASS", "minimal health and administrator-only doctor"),
        ("A5", "PARTIAL", "scoped idempotency, credential revalidation, lease/cancel recovery; no core commit fencing"),
        ("A6", "FAIL", "39 required/declared service handlers absent"),
        ("typed-resource-api", "PARTIAL", "closed implemented-operation requests; most resource families and typed responses absent"),
        ("backend-http-workflow", "FAIL", "real socket/SDK gate stops at upload 404 and Source 501"),
        ("browser-session-security", "NOT_IMPLEMENTED", "Bearer only; no cookie session/auth cache/CSRF acceptance"),
        ("unified-ui", "NOT_RUN", "8A gate failed; no formal UI acceptance"),
        ("modeling-review-compilation-browser", "NOT_RUN", "8A gate failed"),
        ("package-release-pointer-browser", "NOT_RUN", "8A gate failed"),
        ("minimal-cross-domain", "NOT_RUN", "Pack preserved; full browser workflow not executed"),
        ("mnp-cross-domain", "NOT_RUN", "Pack preserved; full browser workflow not executed"),
        ("forestry-0.2.0", "NOT_IMPLEMENTED", "original PLANNED 0.1.0 retained"),
        ("fourth-pack-ui-smoke", "NOT_RUN", "no unified frontend"),
        ("legacy-retirement", "NOT_IMPLEMENTED", "nine files explicitly retained until verified equivalents exist"),
        ("production-workbench-build-install", "NOT_RUN", "no frontend or bundled Workbench wheel"),
        ("browser-e2e-accessibility-visual-performance", "NOT_RUN", "8A gate failed; no screenshots claimed"),
        ("catalog-and-freeze", "PARTIAL", "115 schema bytes unchanged; authorized implementation snapshot tracked separately"),
        ("final-full-regression", "SEE_FINAL_REPORT", "collection and command receipts; repeated counts are not added"),
        ("P9-admission", "BLOCKED", "Prompt 8 unfinished"),
    ]
    mapping = {"requirements": [{"requirement": key, "status": status, "evidence_or_blocker": detail,
                                  "test_nodeids": [PREFIX + test for test in REQUIREMENT_TESTS.get(key, []) if PREFIX + test in passed]}
                                 for key, status, detail in requirements],
               "browser_required_operations": [{"operation_id": row["operation_id"], "api": row["api_route"],
                                                 "handler": row["service_handler"], "service_test": row["success_test_nodeid"],
                                                 "browser_test": None, "browser_status": "NOT_RUN_BACKEND_GATE_FAILED"} for row in rows]}
    (output / "prompt-08-requirement-test-map.json").write_text(json.dumps(mapping, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(coverage["status_counts"]))


if __name__ == "__main__":
    main()
