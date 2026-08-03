"""Controlled competency-question execution (no arbitrary SPARQL from clients)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from rdflib import Graph, Literal
from rdflib.namespace import XSD

from kg_mnp_demo.application.errors import ApplicationError, ErrorCode
from kg_mnp_demo.application.serializers import json_safe
from kg_mnp_demo.evaluator import materialize_assessment
from kg_mnp_demo.inference import apply_owlrl
from kg_mnp_demo.loader import load_case_graph, project_root
from kg_mnp_demo.namespaces import CASE_FILES
from kg_mnp_demo.validator import validate_graph


def competency_root() -> Path:
    return project_root() / "competency_questions"


@lru_cache(maxsize=1)
def _registry() -> dict[str, Any]:
    path = competency_root() / "registry.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _questions() -> list[dict[str, Any]]:
    return list((_registry().get("competency_questions") or []))


class QueryService:
    def list_questions(self) -> list[dict[str, Any]]:
        return json_safe(_questions())

    def get_question(self, cq_id: str) -> dict[str, Any]:
        cid = cq_id.upper()
        for q in _questions():
            if q["id"].upper() == cid:
                return json_safe(q)
        raise ApplicationError(
            ErrorCode.QUERY_NOT_FOUND,
            message=f"未找到能力问题：{cq_id}",
            details=[cq_id],
        )

    def execute(
        self,
        cq_id: str,
        *,
        case_id: str,
        graph: Graph | None = None,
    ) -> dict[str, Any]:
        question = self.get_question(cq_id)
        if case_id not in CASE_FILES and graph is None:
            # Allow JSON-only cases assessed into a provided graph.
            raise ApplicationError(
                ErrorCode.CASE_NOT_FOUND,
                details=[case_id],
            )

        working = graph
        if working is None:
            working = load_case_graph(case_id)
            if validate_graph(working).conforms:
                apply_owlrl(working)
                materialize_assessment(
                    working, case_id, use_updated_rules=True, validate=False
                )

        query_path = competency_root() / "queries" / question["query_file"]
        if not query_path.exists():
            raise ApplicationError(
                ErrorCode.QUERY_EXECUTION_ERROR,
                message=f"查询文件缺失：{question['query_file']}",
                details=[question["query_file"]],
            )
        sparql = query_path.read_text(encoding="utf-8")
        try:
            rows_raw = working.query(
                sparql,
                initBindings={
                    "requestedCaseId": Literal(case_id, datatype=XSD.string)
                },
            )
        except Exception as exc:  # noqa: BLE001
            raise ApplicationError(
                ErrorCode.QUERY_EXECUTION_ERROR,
                message=str(exc),
                details=[str(exc)],
            ) from exc

        columns = [str(v) for v in rows_raw.vars]
        rows: list[dict[str, Any]] = []
        for row in rows_raw:
            item = {}
            for col in columns:
                val = row[col]
                item[col] = None if val is None else str(val)
            rows.append(item)
        rows = sorted(rows, key=lambda r: tuple(str(r.get(c) or "") for c in columns))

        return json_safe(
            {
                "question_id": question["id"],
                "question": question.get("question"),
                "title_zh": question.get("title_zh"),
                "case_id": case_id,
                "status": "ANSWERED",
                "columns": columns,
                "rows": rows,
                "summary": {
                    "row_count": len(rows),
                    "return_fields": question.get("return_fields") or [],
                },
            }
        )
