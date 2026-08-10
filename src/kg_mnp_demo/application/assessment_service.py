"""Assessment service retained for the legacy eligibility example.

Reuses existing input_adapter, rdf_builder, validator, OWL-RL, evaluator, and
trace_graph. Does not re-implement eligibility rules.
"""

from __future__ import annotations

import json
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rdflib import Graph

from kg_mnp_demo.application.contracts import (
    SCHEMA_VERSION,
    build_assessment_response,
    empty_process,
    empty_validation,
)
from kg_mnp_demo.application.errors import ApplicationError, ErrorCode
from kg_mnp_demo.application.serializers import (
    deep_merge,
    json_safe,
    sort_stable,
    to_iso_utc,
)
from kg_mnp_demo.evaluator import evaluate_case
from kg_mnp_demo.inference import apply_owlrl
from kg_mnp_demo.input_adapter import (
    InputValidationError,
    NormalizedCaseInput,
    normalize_case_input,
)
from kg_mnp_demo.loader import merge_reference_graph, project_root
from kg_mnp_demo.rdf_builder import build_case_graph
from kg_mnp_demo.rule_engine import RuleConfigurationError
from kg_mnp_demo.trace_graph import TraceSubgraphIntegrityError, build_assessment_subgraph
from kg_mnp_demo.validator import validate_graph


def _new_execution_id() -> str:
    return str(uuid.uuid4())


def _validation_payload(label: str, result) -> dict[str, Any]:
    return {
        "label": label,
        "status": "PASSED" if result.conforms else "FAILED",
        "conforms": bool(result.conforms),
        "detail": result.text if not result.conforms else "",
    }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _artifact_rel_names() -> dict[str, str]:
    return {
        "normalized_input": "normalized_input.json",
        "input_graph": "input_graph.ttl",
        "input_validation": "input_validation.json",
        "inference": "inference.json",
        "evaluation": "evaluation.json",
        "assessment_graph": "assessment_graph.ttl",
        "assessment_validation": "assessment_validation.json",
        "trace_subgraph": "trace_subgraph.json",
        "assessment_response": "assessment_response.json",
    }


def write_assessment_artifacts(
    execution: "AssessmentExecution",
    artifact_dir: Path | str,
    *,
    write_html: bool = False,
) -> dict[str, str]:
    """Write artifacts to ``artifact_dir``. Returns relative artifact names only."""
    output_dir = Path(artifact_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    names = _artifact_rel_names()

    if execution.normalized is not None:
        _write_json(output_dir / names["normalized_input"], execution.normalized)

    if execution.instance_graph is not None:
        execution.instance_graph.serialize(
            destination=output_dir / names["input_graph"], format="turtle"
        )

    validations = execution.response.get("validations") or {}
    if validations.get("input_graph"):
        _write_json(output_dir / names["input_validation"], validations["input_graph"])
    elif validations.get("json_schema"):
        _write_json(output_dir / names["input_validation"], validations["json_schema"])

    if execution.response.get("inference"):
        _write_json(output_dir / names["inference"], execution.response["inference"])

    if execution.evaluation is not None:
        _write_json(output_dir / names["evaluation"], execution.evaluation)

    if execution.assessment_graph is not None:
        execution.assessment_graph.serialize(
            destination=output_dir / names["assessment_graph"], format="turtle"
        )

    if validations.get("assessment_graph"):
        _write_json(
            output_dir / names["assessment_validation"],
            validations["assessment_graph"],
        )

    if execution.response.get("trace_subgraph"):
        _write_json(
            output_dir / names["trace_subgraph"],
            execution.response["trace_subgraph"],
        )

    _write_json(output_dir / names["assessment_response"], execution.response)

    if write_html and execution.normalized is not None and execution.evaluation is not None:
        from kg_mnp_demo.pipeline import _render_report

        html = _render_report(
            execution.normalized,
            validations.get("input_graph") or empty_validation("Input Graph Validation"),
            validations.get("assessment_graph")
            or empty_validation("Assessment Graph Validation"),
            execution.evaluation,
            execution.response.get("trace_subgraph") or {"nodes": [], "edges": []},
            execution.response.get("inference") or {},
        )
        (output_dir / "report.html").write_text(html, encoding="utf-8")
        names = {**names, "report": "report.html"}

    return {k: v for k, v in names.items()}


@dataclass
class AssessmentExecution:
    """In-memory assessment result plus optional RDF graphs for callers that need them."""

    response: dict[str, Any]
    normalized: dict[str, Any] | None = None
    evaluation: dict[str, Any] | None = None
    instance_graph: Graph | None = None
    assessment_graph: Graph | None = None
    exit_code: int = 0
    error: ApplicationError | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def publishable(self) -> bool:
        return bool((self.response.get("publication") or {}).get("publishable"))

    @property
    def decision(self) -> str | None:
        return self.response.get("decision")

    @property
    def case_id(self) -> str | None:
        return self.response.get("case_id")


def evaluate_normalized_case(
    normalized: NormalizedCaseInput,
    *,
    execution_id: str | None = None,
    use_updated_rules: bool = True,
    raise_on_input_shacl: bool = False,
    raise_on_assessment_shacl: bool = False,
    include_process: bool = True,
    process_payload: dict[str, Any] | None = None,
) -> AssessmentExecution:
    """Pure in-memory evaluation. Does not write files."""
    exec_id = execution_id or _new_execution_id()
    normalized_dict = json_safe(normalized.to_dict())
    assessment_time = to_iso_utc(normalized.assessment_time)
    warnings: list[str] = []

    json_schema_validation = {
        "label": "JSON Schema Validation",
        "status": "PASSED",
        "conforms": True,
        "detail": "",
    }

    try:
        instance = build_case_graph(normalized, process=process_payload)
        working = merge_reference_graph(instance)
    except Exception as exc:  # noqa: BLE001
        raise ApplicationError(
            ErrorCode.INTERNAL_ERROR,
            message=f"构建 RDF 实例失败：{exc}",
            details=[str(exc)],
        ) from exc

    input_shacl = validate_graph(working)
    input_validation = _validation_payload("Input Graph Validation", input_shacl)

    if not input_shacl.conforms:
        response = build_assessment_response(
            execution_id=exec_id,
            case_id=normalized.case_id,
            assessment_time=assessment_time,
            decision=None,
            publication={"publishable": False, "status": "NOT_PUBLISHABLE"},
            validations={
                "json_schema": json_schema_validation,
                "input_graph": input_validation,
                "assessment_graph": empty_validation(
                    "Assessment Graph Validation", status="SKIPPED"
                ),
            },
            input_summary=normalized_dict,
            warnings=["Input SHACL failed; eligibility not evaluated"],
        )
        err = ApplicationError(
            ErrorCode.INPUT_GRAPH_INVALID,
            details=[input_validation.get("detail") or ""],
        )
        if raise_on_input_shacl:
            raise err
        return AssessmentExecution(
            response=json_safe(response),
            normalized=normalized_dict,
            instance_graph=instance,
            assessment_graph=None,
            exit_code=1,
            error=err,
        )

    before = len(working)
    apply_owlrl(working)
    inference = {
        "triples_before": before,
        "triples_after": len(working),
        "triples_added": len(working) - before,
    }

    try:
        evaluation = evaluate_case(
            working,
            normalized.case_id,
            use_updated_rules=use_updated_rules,
            assessment_time=normalized.assessment_time,
            validate=False,
        )
    except RuleConfigurationError as exc:
        raise ApplicationError(
            ErrorCode.RULE_CONFIGURATION_ERROR,
            message=str(exc),
            details=[str(exc)],
        ) from exc

    evaluation = json_safe(evaluation)
    evaluation["assessment_time"] = assessment_time

    assessment_shacl = validate_graph(working)
    assessment_validation = _validation_payload(
        "Assessment Graph Validation", assessment_shacl
    )
    publishable = bool(assessment_shacl.conforms)
    if publishable:
        evaluation["validation_status"] = "PASSED"
        evaluation["validation_detail"] = ""
        evaluation["publishable"] = True
        evaluation["publication_status"] = "PUBLISHABLE"
    else:
        evaluation["validation_status"] = "FAILED"
        evaluation["validation_detail"] = assessment_validation["detail"]
        evaluation["publishable"] = False
        evaluation["publication_status"] = "NOT_PUBLISHABLE"
        warnings.append("Assessment SHACL failed; result is not publishable")

    try:
        subgraph = build_assessment_subgraph(working, normalized.case_id)
    except TraceSubgraphIntegrityError as exc:
        raise ApplicationError(
            ErrorCode.TRACE_INTEGRITY_ERROR,
            message=str(exc),
            details=[str(exc)],
        ) from exc

    subgraph = json_safe(subgraph)

    process = empty_process()
    if include_process:
        try:
            from kg_mnp_demo.application.process_service import evaluate_process_state

            process = evaluate_process_state(
                working,
                normalized.case_id,
                decision=evaluation.get("decision"),
                assessment_time=normalized.assessment_time,
                payload={"process": process_payload} if process_payload else normalized_dict,
            )
        except ImportError:
            pass
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Process evaluation skipped: {exc}")

    evidence = sort_stable(list(evaluation.get("evidence") or []))
    rule_results = sort_stable(list(evaluation.get("rules") or []))
    blocking_reasons = sort_stable(list(evaluation.get("blocking_reasons") or []))
    remediation_actions = sort_stable(list(evaluation.get("remediation_actions") or []))

    response = build_assessment_response(
        execution_id=exec_id,
        case_id=normalized.case_id,
        assessment_time=assessment_time,
        decision=evaluation.get("decision"),
        publication={
            "publishable": publishable,
            "status": evaluation.get("publication_status")
            or ("PUBLISHABLE" if publishable else "NOT_PUBLISHABLE"),
        },
        validations={
            "json_schema": json_schema_validation,
            "input_graph": input_validation,
            "assessment_graph": assessment_validation,
        },
        input_summary=normalized_dict,
        evidence=evidence,
        rule_results=rule_results,
        blocking_reasons=blocking_reasons,
        remediation_actions=remediation_actions,
        process=process,
        trace_subgraph=subgraph,
        inference=inference,
        warnings=warnings,
        artifacts={},
    )

    err = None
    exit_code = 0
    if not publishable:
        err = ApplicationError(
            ErrorCode.ASSESSMENT_GRAPH_INVALID,
            details=[assessment_validation.get("detail") or ""],
        )
        exit_code = 1
        if raise_on_assessment_shacl:
            raise err

    return AssessmentExecution(
        response=json_safe(response),
        normalized=normalized_dict,
        evaluation=evaluation,
        instance_graph=instance,
        assessment_graph=working,
        exit_code=exit_code,
        error=err,
    )


class AssessmentService:
    """Stable façade for dict/file assessment and what-if scenarios."""

    def __init__(self, *, default_artifact_root: Path | None = None) -> None:
        self.default_artifact_root = default_artifact_root or (
            project_root() / "runtime_outputs"
        )

    def assess_dict(
        self,
        payload: dict[str, Any],
        *,
        persist_artifacts: bool = False,
        artifact_dir: Path | None = None,
        write_html: bool = False,
        execution_id: str | None = None,
        raise_on_error: bool = False,
    ) -> dict[str, Any]:
        """Assess a JSON-compatible dict. Returns the stable assessment contract.

        On schema errors raises ``ApplicationError`` (or returns error dict when
        ``raise_on_error`` is False is not used for schema — schema always raises
        unless callers catch). Schema failures always raise.
        """
        try:
            normalized = normalize_case_input(payload)
        except InputValidationError as exc:
            err = ApplicationError(
                ErrorCode.INPUT_SCHEMA_ERROR,
                details=list(exc.errors),
            )
            if raise_on_error:
                raise err
            return err.to_dict()
        except json.JSONDecodeError as exc:
            err = ApplicationError(
                ErrorCode.INPUT_SCHEMA_ERROR,
                message="JSON 解析失败。",
                details=[str(exc)],
            )
            if raise_on_error:
                raise err
            return err.to_dict()

        process_payload = payload.get("process") if isinstance(payload.get("process"), dict) else None

        try:
            execution = evaluate_normalized_case(
                normalized,
                execution_id=execution_id,
                process_payload=process_payload,
            )
        except ApplicationError as exc:
            if raise_on_error:
                raise
            return exc.to_dict()

        if persist_artifacts:
            out = Path(artifact_dir) if artifact_dir else (
                self.default_artifact_root / (execution.case_id or "unknown")
            )
            artifacts = write_assessment_artifacts(
                execution, out, write_html=write_html
            )
            execution.response["artifacts"] = artifacts

        if raise_on_error and execution.error is not None:
            # Attach response for callers that want both.
            execution.error.details = list(execution.error.details) + [
                {"execution_id": execution.response.get("execution_id")}
            ]
            # Soft SHACL failures still return response by default.
            if execution.error.code in (
                ErrorCode.INPUT_GRAPH_INVALID,
                ErrorCode.ASSESSMENT_GRAPH_INVALID,
            ):
                return execution.response
            raise execution.error

        return execution.response

    def assess_file(
        self,
        input_path: Path,
        *,
        persist_artifacts: bool = False,
        artifact_dir: Path | None = None,
        write_html: bool = False,
        execution_id: str | None = None,
        raise_on_error: bool = False,
    ) -> dict[str, Any]:
        path = Path(input_path)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            err = ApplicationError(
                ErrorCode.CASE_NOT_FOUND,
                message=f"输入文件不存在：{path.name}",
                details=[path.name],
            )
            if raise_on_error:
                raise err from exc
            return err.to_dict()
        except json.JSONDecodeError as exc:
            err = ApplicationError(
                ErrorCode.INPUT_SCHEMA_ERROR,
                message="JSON 解析失败。",
                details=[str(exc)],
            )
            if raise_on_error:
                raise err from exc
            return err.to_dict()

        if not isinstance(raw, dict):
            err = ApplicationError(
                ErrorCode.INPUT_SCHEMA_ERROR,
                details=["(root) must be a JSON object"],
            )
            if raise_on_error:
                raise err
            return err.to_dict()

        return self.assess_dict(
            raw,
            persist_artifacts=persist_artifacts,
            artifact_dir=artifact_dir,
            write_html=write_html,
            execution_id=execution_id,
            raise_on_error=raise_on_error,
        )

    def run_what_if(
        self,
        baseline_payload: dict[str, Any],
        changes: dict[str, Any],
        *,
        persist_artifacts: bool = False,
        artifact_dir: Path | None = None,
    ) -> dict[str, Any]:
        """Deep-merge ``changes`` into baseline and re-assess with full diffs."""
        from kg_mnp_demo.application.comparison import build_what_if_diff

        merged = deep_merge(deepcopy(baseline_payload), changes)
        baseline = self.assess_dict(baseline_payload, raise_on_error=False)
        scenario = self.assess_dict(
            merged,
            persist_artifacts=persist_artifacts,
            artifact_dir=artifact_dir,
            raise_on_error=False,
        )
        diff = build_what_if_diff(baseline, scenario, changes=changes)
        return {
            "schema_version": SCHEMA_VERSION,
            **diff,
            "decision_changed": bool((diff.get("decision_change") or {}).get("changed")),
        }

    def assess_execution(
        self,
        payload: dict[str, Any],
        *,
        persist_artifacts: bool = False,
        artifact_dir: Path | None = None,
        write_html: bool = False,
        execution_id: str | None = None,
    ) -> AssessmentExecution:
        """Like ``assess_dict`` but returns the full ``AssessmentExecution``."""
        try:
            normalized = normalize_case_input(payload)
        except InputValidationError as exc:
            raise ApplicationError(
                ErrorCode.INPUT_SCHEMA_ERROR,
                details=list(exc.errors),
            ) from exc

        process_payload = payload.get("process") if isinstance(payload.get("process"), dict) else None
        execution = evaluate_normalized_case(
            normalized,
            execution_id=execution_id,
            process_payload=process_payload,
        )
        if persist_artifacts:
            out = Path(artifact_dir) if artifact_dir else (
                self.default_artifact_root / (execution.case_id or "unknown")
            )
            artifacts = write_assessment_artifacts(
                execution, out, write_html=write_html
            )
            execution.response["artifacts"] = artifacts
        return execution
