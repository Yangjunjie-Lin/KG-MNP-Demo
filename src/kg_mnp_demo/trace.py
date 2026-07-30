"""SPARQL-based trace helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rdflib import Graph, Literal

from kg_mnp_demo.loader import query_path


def _load_query(query_file: str, replacements: dict[str, str] | None = None) -> str:
    text = Path(query_path(query_file)).read_text(encoding="utf-8")
    if replacements:
        for key, value in replacements.items():
            text = text.replace(key, value)
    return text


def run_query(
    graph: Graph,
    query_file: str,
    *,
    replacements: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    text = _load_query(query_file, replacements)
    rows = []
    for row in graph.query(text):
        item = {}
        for key in row.labels:
            val = row[key]
            item[str(key)] = str(val) if val is not None else None
        rows.append(item)
    return rows


def decision_trace(graph: Graph, case_id: str) -> list[dict[str, Any]]:
    return run_query(
        graph,
        "decision_trace.rq",
        replacements={"__CASE_ID__": case_id},
    )


def blocking_reasons(graph: Graph, case_id: str) -> list[dict[str, Any]]:
    return run_query(
        graph,
        "blocking_reasons.rq",
        replacements={"__CASE_ID__": case_id},
    )


def affected_assessments(graph: Graph) -> list[dict[str, Any]]:
    return run_query(graph, "affected_assessments.rq")


def source_alignment(graph: Graph) -> list[dict[str, Any]]:
    return run_query(graph, "source_alignment.rq")
