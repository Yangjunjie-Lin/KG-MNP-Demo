"""Read-only stage projection of actual operations, never inferred execution."""
from __future__ import annotations

from zhigou_toolchain.contracts.canonical import stable_urn

from .agents import OWNERS
from .contracts import StageRun, artifact, verify_handoff
from .registry import registry

# These are navigation/lineage adapters. They do NOT assert that all named
# algorithms ran inside an old operation. Only explicit StepRun receipts do.
OPERATION_OUTPUTS = {
    "ingestion.run": [("0.0", "run", "REPORT"), ("1.1", "quality", "REPORT")],
    "modeling.scope": [("1.3", "scope", "CONFIGURATION")],
    "modeling.scope.approve": [("1.4", "approval", "REPORT")],
    "modeling.prepare": [("2.1", "baseline", "CONFIGURATION"), ("2.2", "alignments", "REPORT"),
                         ("3.1", "mappings", "MODELING_CANDIDATE"), ("1.4", "questions", "CONFIGURATION")],
    "modeling.proposal": [("3.6", "proposal", "MODELING_CANDIDATE"), ("4.1", "prevalidation", "REPORT"),
                          ("3.5", "extraction", "REPORT")],
    "review.action": [("4.4", "action", "REPORT")],
    "review.finalize": [("4.5", "confirmed_package", "MODELING_CANDIDATE")],
    "compile.plan": [("5.1", "plan", "CONFIGURATION")],
    "compile.plan.exact": [("5.1", "plan", "CONFIGURATION"), ("5.4", "independent_expected_answers", "CONFIGURATION")],
    "compile.build": [("5.1", "manifest", "SEMANTIC_DELIVERY"), ("5.3", "reports", "REPORT")],
}


def project_flow(project_id: str, results: list[dict], jobs: list[dict]) -> dict:
    """Project history is not one session. UI must explicitly select its scope.

    The project-level observation ID intentionally says `flow-observation`,
    not ModelingSession: no fabricated B4 approval or B5 delivery is minted.
    """
    session_id = stable_urn("flow-observation", {"project_id": project_id})
    artifacts, step_runs = [], []
    for result in results:
        for step, key, kind in OPERATION_OUTPUTS.get(result["operation"], []):
            value = result["result"].get(key)
            if value:
                item = artifact(value, project_id=project_id, session_id=session_id, step_id=step,
                                produced_by=result["operation"], data_kind=kind)
                artifacts.append({**item, "job_id": result["job_id"], "authority_revision": result["revision"],
                                  "observation": "LEGACY_OPERATION_OUTPUT_NOT_METHOD_RECEIPT"})
        fresh = result["result"].get("five_stage", {})
        artifacts.extend(fresh.get("artifacts", []))
        step_runs.extend({**row, "job_id": result["job_id"]} for row in fresh.get("step_runs", []))
    # Preserve exact refs in every downstream read bundle. These are observed
    # handoff views, not a second approved-package store or sequential scheduler.
    bundles, inherited, parents = [], [], []
    for stage in range(6):
        added = [a["ref"] for a in artifacts if a["ref"]["stage_id"] == stage]
        bundle_id = stable_urn("stage-observation", {"project": project_id, "stage": stage,
                              "parent": parents, "inherited": inherited, "new": added})
        bundle = StageRun(bundle_id=bundle_id, stage_id=stage, session_id=session_id,
                          parent_bundle_refs=parents, inherited_artifact_refs=inherited,
                          new_artifact_refs=added)
        if bundles:
            verify_handoff(bundles[-1]["inherited_artifact_refs"] + bundles[-1]["new_artifact_refs"], inherited)
        bundles.append(bundle.model_dump())
        inherited = [*inherited, *added]
        parents = [bundle_id]
    methods = []
    for method in registry()["methods"]:
        receipts = [r for r in step_runs if r["step_id"] == method["method_id"]]
        observed = [a["ref"] for a in artifacts if a["ref"]["step_id"] == method["method_id"]]
        status = receipts[-1]["status"] if receipts else "NOT_RUN"
        relevant_operations = {
            '1.1': {'modeling.profile', 'modeling.tutorial.seed'},
            '1.2': {'modeling.profile', 'modeling.tutorial.seed'},
            '1.3': {'modeling.scope.draft'},
            '4.1': {'modeling.semantic.check'}, '4.2': {'modeling.semantic.check'},
        }.get(method['method_id'], set())
        # JobStore.list_project is newest first, including successful retries.
        relevant = [j for j in jobs if j['operation_id'] in relevant_operations]
        reason = None if receipts else '没有此方法的完整执行收据；相关旧操作产物仅作可追溯参考。'
        if relevant and relevant[0]['status'] != 'SUCCEEDED':
            current = relevant[0]
            status = {'QUEUED':'READY', 'RUNNING':'RUNNING', 'CANCEL_REQUESTED':'RUNNING',
                      'CANCELLED':'CANCELLED', 'FAILED':'FAILED', 'RECOVERY_REQUIRED':'BLOCKED'}.get(current['status'], 'BLOCKED')
            code = (current.get('error') or {}).get('code')
            if code == 'BLOCKED_BY_PROVIDER':
                status = 'BLOCKED'
            reason = f"任务 {current['job_id']}：{code or current['status']}。旧收据不是本次重跑成功证明。"
        methods.append({"method_id": method["method_id"], "status": status,
                        "validation_status": receipts[-1]["validation_status"] if receipts else "NOT_RUN",
                        "review_status": "PENDING", "receipt_count": len(receipts), "artifact_refs": observed,
                        "reason": reason})
    return {"schema_version": "1.0.0", "session_id": session_id, "authority": "OBSERVATION_ONLY",
            "agent_roles": OWNERS, "agent_runs": [r["result"]["agent_execution"] for r in results if "agent_execution" in r["result"]],
            "methods": methods, "bundles": bundles, "artifacts": artifacts, "step_runs": step_runs,
            "jobs": jobs, "delivery_status": "NOT_CERTIFIED_BY_PROJECTION",
            "limitations": ["项目历史观察不是单一 ModelingSession。跨会话下游失效尚未接入，不能作为五阶段完成凭证。"]}
