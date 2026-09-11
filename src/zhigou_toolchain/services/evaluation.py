"""Independent module contract checks over verified persisted service receipts."""
from time import perf_counter

from zhigou_toolchain.contracts.canonical import semantic_hash

from .errors import ServiceBoundaryError
from .execution import committed_result

MODULES = {
    "framework": {"task.execute"}, "ingestion": {"ingestion.run", "modeling.tutorial.seed", "source.sample.load"},
    "ontology": {"compile.build", "modeling.semantic.check"},
    "evolution": {"evolution.evaluate", "evolution.activate", "evolution.rollback"},
}
TARGETS = {
    "framework": {"target": "Typical forestry tasks and complete prototype; no universal numeric threshold"},
    "ingestion": {"project_name_applicant_accuracy": 0.85, "unit_processing_time_reduction": 0.10},
    "ontology": {"object_property_relation_accuracy": 0.80, "expert_reviewed_published_accuracy": 0.90, "source_trace_completeness": 0.90},
    "evolution": {"anomaly_identification_accuracy": 0.80, "task_completion_improvement_percentage_points": 10},
}


def execute(app, project, request, principal):
    started = perf_counter()
    module = request.parameters["module"]
    job = app._job(request.parameters["job_id"], principal)
    if job.project_id != project.project_id or job.operation_id not in MODULES[module]:
        raise ServiceBoundaryError("MODULE_INPUT_MISMATCH", "Select a matching module run in the same project", status_code=422)
    content = committed_result(app, job)
    if content is None:
        raise ServiceBoundaryError("MODULE_RUN_NOT_COMMITTED", "An actual verified module output is required", status_code=409)
    checks = [{"name": "committed_output_integrity", "required": True, "status": "PASS"}]
    sample_size = 0
    if module == "ingestion":
        from .sources import verified_run
        data = verified_run(project.root, content["run"]["run_id"]).dataset
        sample_size = len(data["items"])
        checks.append({"name": "evidence_bound_nonempty_input", "required": True,
                       "status": "PASS" if data["items"] and data["evidence_records"] else "FAIL"})
    elif module == "framework":
        from .business import load
        data = load(project.root)
        execution = content["execution"]
        sample_size = len(data["plans"][execution["plan_id"]]["objects"])
        checks.append({"name": "business_receipt_readback", "required": True, "status": "PASS" if all(
            r["order_id"] in data["orders"] and semantic_hash(data["orders"][r["order_id"]]) == r["state_digest"]
            for r in execution["receipts"]) else "FAIL"})
    elif module == "ontology":
        if job.operation_id == "compile.build":
            from zhigou_toolchain.semantic_kernel.packaging.archive import (
                read_verified_package_files,
            )

            from .compilation import package_path
            files, verified = read_verified_package_files(package_path(project, content["package_id"]))
            sample_size = len(files)
            checks.append({"name": "independent_disk_package_verification", "required": True, "status": "PASS" if verified["status"] == "VALID" else "FAIL"})
        else:
            artifacts = content["five_stage"]["artifacts"]
            sample_size = len(artifacts)
            checks.append({"name": "joint_semantic_checks", "required": True, "status": "PASS" if
                any(a["ref"]["step_id"] == "4.2" and a["content"]["status"] == "PASS" for a in artifacts) else "FAIL"})
    else:
        candidate = content.get("candidate", {})
        sample_size = candidate.get("evaluation", {}).get("sample_size", 0)
        checks.extend(candidate.get("evaluation", {}).get("checks", []))
    report = {"schema_version": "1.0.0", "module": module, "job_id": job.job_id, "project_id": project.project_id,
        "data_digest": semantic_hash(content), "sample_size": sample_size, "checks": checks,
        "status": "FAIL" if any(c["status"] == "FAIL" for c in checks) else "PASS" if sample_size and all(c["status"] == "PASS" for c in checks) else "INSUFFICIENT_EVIDENCE",
        "sample_unit": {"ingestion": "KG_IR_ITEMS", "framework": "BUSINESS_OBJECTS", "evolution": "REGRESSION_DECISIONS"}.get(module,
            "PACKAGE_FILES" if job.operation_id == "compile.build" else "SEMANTIC_CHECK_ARTIFACTS"),
        "source_data_origin": "NOT_INFERRED_FROM_EXECUTION_MODE",
        "mode": "DETERMINISTIC", "environment": "LOCAL", "duration_seconds": perf_counter() - started,
        "research_targets": TARGETS[module], "research_status": "INSUFFICIENT_EVIDENCE",
        "annotation_source": None, "gold_standard": None, "comparison_method": "Module contract and immutable artifact checks only",
        "research_qualification": "No independent labeled holdout, comparable timing baseline or real expert review; no research target attainment claim"}
    return {"report": report}
