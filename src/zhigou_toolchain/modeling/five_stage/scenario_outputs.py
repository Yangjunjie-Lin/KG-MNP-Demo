"""Versioned views of real native outputs; no independent business state."""
from __future__ import annotations

from collections import Counter
from typing import Literal

from pydantic import Field

from zhigou_toolchain.contracts.canonical import semantic_hash

from .expert import ClosedModel
from .expert_runtime import safe_view
from .scenarios import CONTRACT, frozen_scene, quality_metrics


class OutputReference(ClosedModel):
    kind: str
    identifier: str | None
    digest: str


class ScenarioStageOutput(ClosedModel):
    format: Literal["zhigou-scenario-stage/2.0.0"] = CONTRACT
    stage_id: int = Field(ge=1, le=5)
    operation: str
    scenario_id: str
    scenario_version: str
    configuration_digest: str
    stage_configuration_digest: str
    status: Literal["PROJECTED_FROM_ACTUAL_OUTPUT"]
    references: list[OutputReference]
    selected_capabilities: list[str]
    required_checks: list[str]
    output_fields: list[str]
    observed_counts: dict[str, int]
    scope_coverage: dict
    diagnostics: dict
    service_contracts: list[dict]
    independent_quality: dict
    human_approval: Literal["NOT_GRANTED_BY_THIS_PROJECTION"]


def candidates_from(result):
    proposal = result.get("proposal") or result.get("expert_routed_proposal") or {}
    result_set = [c for key in ("tbox_candidates", "abox_candidates", "mapping_candidates", "shacl_candidates") for c in proposal.get(key, [])]
    if not result_set:
        result_set = next((a["content"] for a in result.get("five_stage", {}).get("artifacts", []) if a["ref"]["step_id"] == "3.6"), [])
    return result_set


def contracts(configuration, package_id=None):
    """Only operations already registered by the service. No action executor."""
    options = configuration["stages"]["S5"]
    scene = frozen_scene(configuration)
    result = []
    for table in scene["tables"]:
        if table["record_id"] not in options["enabled_object_families"]:
            continue
        row = {"operation": "ods.query", "object_family": table["record_id"], "class_iri": table["class_iri"],
            "package_id": package_id, "status": "REGISTERED_READ_INTERFACE_REQUIRES_PACKAGE_IMPORT",
            "permissions": ["package:read"], "deployment": "NOT_ASSERTED", "mutates_business": False}
        row.update(parameters={"package_id": "required native package identifier", "class_iri": table["class_iri"], "limit": "1..1000", "offset": "0..1000000"},
            selected_fields=[f for f in options["declared_fields"] if f.split(".")[0] == table["record_id"]],
            errors=["FORBIDDEN", "PACKAGE_NOT_FOUND", "REQUEST_INVALID"],
            example={"class_iri": table["class_iri"], "limit": 10, "offset": 0, "execution": "NOT_EXECUTED_BY_CONTRACT"})
        row.update(filters={"one_of": ["class_iri", "instance_iri"], "combination": "EXCLUSIVE_EXACT_MATCH"},
            preconditions=["verified package imported in original Registry", "current package:read permission"],
            idempotency="READ_ONLY_SAME_FROZEN_PACKAGE", composition="Read returned source-bound relationships; no arbitrary combined-query feature asserted",
            action_preview={"status": "UNSUPPORTED_NO_REGISTERED_SCENE_ACTION", "executed": False})
        result.append(row)
    return result


def scope_coverage(configuration, candidates):
    """Actual typed candidate counts, not a semantic-accuracy percentage."""
    if not candidates:
        return {"status": "NOT_PROJECTED_AT_THIS_OPERATION", "meaning": "Use the linked S3 candidate and validation artifacts; absence here is not failure or success"}
    scene = frozen_scene(configuration)
    selected = configuration["stages"]["S3"]["selected_capabilities"]
    required = set(configuration["hard_requirements"]["required_capabilities"])
    objects = [c["body"] for c in candidates if c["body"]["candidate_type"] == "CLASS_ASSERTION"]
    values = [c["body"] for c in candidates if c["body"]["candidate_type"] == "DATA_PROPERTY_ASSERTION"]
    tables = []
    for table in scene["tables"]:
        enabled = table["capability"] in selected
        subjects = {b["subject_iri"] for b in objects if b["object_iri"] == table["class_iri"]}
        fields = []
        for name, policy in table["literals"].items():
            chosen = enabled and policy["capability"] in selected
            count = len({b["subject_iri"] for b in values if b["subject_iri"] in subjects and b["predicate_iri"] == policy["predicate_iri"]})
            fields.append({"field": name, "scope_kind": "REQUIRED_CAPABILITY" if policy["capability"] in required else "OPTIONAL_CAPABILITY",
                "selected": chosen, "subjects_with_value": count, "subjects_without_value_candidate": len(subjects) - count if chosen else None,
                "status": "NOT_SELECTED" if not chosen else "SOURCE_ASSERTIONS_PRESENT" if count == len(subjects) and subjects else "NO_OR_PARTIAL_VALUE_CANDIDATES"})
        tables.append({"object_family": table["record_id"], "required_capability": table["capability"] in required,
            "selected": enabled, "objects": len(subjects), "status": "NOT_SELECTED" if not enabled else "SOURCE_OBJECT_CANDIDATES" if subjects else "NO_OBJECT_CANDIDATES",
            "fields": fields})
    return {"status": "CANDIDATE_COUNTS_PROJECTED", "tables": tables,
        "meaning": "No guessed accuracy. Missing/null remain in original source and quality records; nonempty references do not replace evidence/constraint validation."}


def project_output(configuration, stage, operation, result):
    options = configuration["stages"][f"S{stage}"]
    references = []
    if result.get("package_id"):
        references.append({"kind": "native_package_result", "identifier": result["package_id"],
            "digest": semantic_hash({k: result[k] for k in ("package_id", "sha256", "size_bytes") if k in result})})
    for key, value in result.items():
        if key in {"expert_loop", "agent_execution", "step_audit_anchor", "scenario_outputs"} or not isinstance(value, dict):
            continue
        identifier = next((value[k] for k in ("scope_id", "proposal_id", "plan_id", "package_id", "modeling_input_bundle_id", "session_id") if k in value), None)
        references.append({"kind": key, "identifier": identifier, "digest": semantic_hash(value)})
    candidates = candidates_from(result)
    counts = dict(Counter(c["body"]["candidate_type"] for c in candidates))
    if candidates:
        counts["candidates_with_nonempty_evidence_refs"] = sum(bool(c["evidence_refs"]) for c in candidates)
        counts["candidates_total"] = len(candidates)
    checks = [{"step_id": r["step_id"], "validation_status": r["validation_status"]}
              for r in result.get("five_stage", {}).get("step_runs", [])]
    diagnostic = {"actual_step_checks": checks,
        "failures": [c for c in checks if c["validation_status"] not in {"PASS", "NOT_APPLICABLE"}],
        "complete_underlying_reports_retained": True}
    if stage == 1:
        diagnostic["actual_scope"] = result.get("scope", {})
        diagnostic["declared_fields"] = options["declared_fields"]
        diagnostic["cross_source_policies"] = configuration["rules"]
    if stage == 4:
        diagnostic["by_kind"] = {kind: [c["candidate_id"] for c in candidates if c["body"]["candidate_type"] == kind] for kind in sorted({c["body"]["candidate_type"] for c in candidates})}
        diagnostic["dependencies"] = [{"candidate_id": c["candidate_id"], "depends_on": c.get("dependency_candidate_refs", []),
            "evidence_refs": c["evidence_refs"]} for c in candidates]
        diagnostic["optional_diagnostics"] = {"status": "NOT_RUN", "reason": "No additional registered validator selected; all mandatory validators unchanged"}
    native = result.get("manifest", {})
    return ScenarioStageOutput(stage_id=stage, operation=operation,
        scenario_id=configuration["scenario_id"], scenario_version=configuration["scenario_version"],
        configuration_digest=configuration["digest"], stage_configuration_digest=configuration["stage_digests"][f"S{stage}"],
        status="PROJECTED_FROM_ACTUAL_OUTPUT", references=references,
        selected_capabilities=options["selected_capabilities"],
        required_checks=configuration["hard_requirements"]["checks"], output_fields=options["declared_fields"],
        observed_counts=counts, diagnostics=safe_view(diagnostic), service_contracts=contracts(configuration, native.get("package_id")) if stage == 5 else [],
        scope_coverage=scope_coverage(configuration, candidates),
        independent_quality=quality_metrics([], None), human_approval="NOT_GRANTED_BY_THIS_PROJECTION").model_dump()


def project_operation(configuration, operation, result):
    if not configuration:
        return result
    from .agents import invoke
    stages = {"modeling.profile": [1], "modeling.scope.draft": [1], "modeling.scope": [1],
        "modeling.prepare": [2], "modeling.cq": [2], "modeling.baseline": [2], "modeling.alignment": [2],
        "modeling.proposal": [2, 3], "modeling.candidate": [2, 3], "modeling.semantic.check": [4]}.get(operation, [5])
    output = []
    for stage in stages:
        output.append(invoke(stage, "scenario.project", lambda stage=stage: project_output(configuration, stage, operation, result),
            inputs={"stage_configuration_digest": configuration["stage_digests"][f"S{stage}"], "result_digest": semantic_hash(result)}))
    return {**result, "scenario_outputs": output}
