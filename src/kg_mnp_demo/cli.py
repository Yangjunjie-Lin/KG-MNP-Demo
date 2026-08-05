"""Legacy eligibility use-case CLI using the offline RDF backend."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from kg_mnp_demo.evaluator import evaluate_case, materialize_assessment
from kg_mnp_demo.inference import apply_owlrl
from kg_mnp_demo.loader import load_case_graph, load_ontology_graph
from kg_mnp_demo.mappings import load_mappings, load_source_manifest
from kg_mnp_demo.namespaces import CASE_FILES
from kg_mnp_demo.trace import (
    affected_assessments,
    blocking_reasons,
    decision_trace,
    source_alignment,
)
from kg_mnp_demo.validator import validate_graph


def _json_print(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def cmd_validate(case_id: str) -> int:
    g = load_case_graph(case_id)
    result = validate_graph(g)
    _json_print(
        {
            "case_id": case_id,
            "validation_status": "PASSED" if result.conforms else "FAILED",
            "detail": result.text,
            "backend": "rdf",
        }
    )
    return 0 if result.conforms else 1


def cmd_infer(case_id: str) -> int:
    g = load_case_graph(case_id)
    before = len(g)
    apply_owlrl(g)
    after = len(g)
    sample = []
    from rdflib.namespace import RDF
    from kg_mnp_demo.namespaces import MNP

    for s in g.subjects(RDF.type, MNP.SystemObservation):
        if (s, RDF.type, MNP.EvidenceRecord) in g:
            sample.append({"subject": str(s), "inferred_type": "mnp:EvidenceRecord"})
            break
    _json_print(
        {
            "case_id": case_id,
            "triples_before": before,
            "triples_after": after,
            "sample_inferences": sample,
            "status": "OK",
            "backend": "rdf",
        }
    )
    return 0


def cmd_evaluate_rdf(case_id: str) -> int:
    g = load_case_graph(case_id)
    apply_owlrl(g)
    result = evaluate_case(g, case_id, use_updated_rules=True)
    result["backend"] = "rdf"
    _json_print(result)
    return 0


def cmd_trace_rdf(case_id: str) -> int:
    g = load_case_graph(case_id)
    apply_owlrl(g)
    materialize_assessment(g, case_id, use_updated_rules=True)
    payload = {
        "case_id": case_id,
        "backend": "rdf",
        "decision_trace": decision_trace(g, case_id),
        "blocking_reasons": blocking_reasons(g, case_id),
        "affected_assessments": affected_assessments(g) if case_id == "CASE-06" else [],
        "source_alignment": source_alignment(load_ontology_graph(include_alignments=True)),
    }
    _json_print(payload)
    return 0


def cmd_mappings() -> int:
    _json_print({"mappings": load_mappings()})
    return 0


def cmd_sources() -> int:
    _json_print({"sources": load_source_manifest()})
    return 0


def cmd_run_all() -> int:
    results = {}
    for case_id in sorted(CASE_FILES):
        g = load_case_graph(case_id)
        v = validate_graph(g)
        apply_owlrl(g)
        result = evaluate_case(g, case_id, use_updated_rules=True)
        results[case_id] = {
            "decision": result["decision"],
            "blocking_reasons": [b["reason_code"] for b in result["blocking_reasons"]],
            "validation_status": "PASSED" if v.conforms else "FAILED",
            "trace_path_count": len(result["trace_paths"]),
            "backend": "rdf",
        }
    _json_print({"run_all": results, "backend": "rdf"})
    return 0 if all(r["validation_status"] == "PASSED" for r in results.values()) else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="kg_mnp_demo", description="KG-MNP eligibility demo CLI")
    sub = p.add_subparsers(dest="command", required=True)

    for name in ("validate", "infer"):
        sp = sub.add_parser(name)
        sp.add_argument("--case", required=True, choices=sorted(CASE_FILES))

    for name in ("evaluate", "trace"):
        sp = sub.add_parser(name)
        sp.add_argument("--case", required=True, choices=sorted(CASE_FILES))
        sp.add_argument("--backend", choices=["rdf"], default="rdf")

    sp_run = sub.add_parser("run-all")
    sp_run.add_argument("--backend", choices=["rdf"], default="rdf")

    sub.add_parser("mappings")
    sub.add_parser("sources")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "validate":
        return cmd_validate(args.case)
    if args.command == "infer":
        return cmd_infer(args.case)
    if args.command == "evaluate":
        return cmd_evaluate_rdf(args.case)
    if args.command == "trace":
        return cmd_trace_rdf(args.case)
    if args.command == "mappings":
        return cmd_mappings()
    if args.command == "sources":
        return cmd_sources()
    if args.command == "run-all":
        return cmd_run_all()
    parser.error(f"Unknown command {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
