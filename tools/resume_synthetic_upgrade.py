"""Resume ONLY explicit synthetic upgrade test workspaces after plan validation.

Uses the recorded, still-authorized test identity and the same ApplicationService
and Worker. This is supplemental debugging evidence, not a clean full-suite run.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from zhigou_toolchain.services.facade import ApplicationService
from zhigou_toolchain.services.models import ServiceConfiguration


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from tests.services.test_modeling_workflow import call
    from tests.upgrade.test_full_chain import (
        test_forestry_real_work_orders_feedback_and_rollback,
        test_hr_formal_package_and_source_query,
    )
    workspace = args.workspace.resolve(strict=True)
    if workspace.name not in {"upgrade-hr0", "upgrade-forest0"} or "pytest-of-" not in str(workspace):
        raise ValueError("Only explicitly named generated pytest upgrade workspaces are allowed")
    service = ApplicationService(ServiceConfiguration(str(workspace), review_profile="DEVELOPMENT_SINGLE_REVIEWER", reasoner_jar=str(root / "third_party/downloads/robot-1.9.7.jar")))
    from zhigou_toolchain.services.projects import load_catalog
    catalog = load_catalog(workspace)
    projects = list(catalog["projects"])
    if len(projects) != 1:
        raise ValueError("Expected exactly one isolated synthetic project")
    project_id = projects[0]
    jobs = service.jobs.list_project(project_id)
    failed = next(j for j in jobs if j.operation_id == "compile.plan.exact")
    params = service.jobs.parameters(failed.job_id)
    identity = params.pop("__principal")
    principal = service.tokens.resolve(identity["token_id"])
    if principal.principal_id != "synthetic-upgrade-reviewer":
        raise ValueError("Not the explicit synthetic engineering identity")
    params["version_iri"] = params["ontology_iri"] + ":" + params["package_version"]
    def run(operation, data, key):
        print(operation, flush=True)
        return call(service, principal, project_id, operation, data, "resume-" + key)
    plan = run("compile.plan.exact", params, "plan")["plan"]
    built = run("compile.build", {"plan_id": plan["plan_id"]}, "build")
    run("package.export", {"package_id": built["package_id"]}, "export")
    run("registry.import", {"package_id": built["package_id"]}, "import")
    proposed = next(c["result"] for c in catalog["commits"].values() if c["context"]["operation_id"] == "modeling.proposal")
    case = {"run": run, "built": built, "service": service, "principal": principal, "project_id": project_id, "proposed": proposed}
    if workspace.name == "upgrade-hr0":
        test_hr_formal_package_and_source_query(case)
    else:
        test_forestry_real_work_orders_feedback_and_rollback(case)
    report = {"status": "PASS", "scope": "resumed synthetic confirmed package through delivery and downstream checks", "workspace": str(workspace), "package_id": built["package_id"]}
    (root / "runtime_reports" / (workspace.name + "-resume.json")).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
