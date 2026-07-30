"""JSON → RDF → eligibility assessment pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from rdflib import Graph

from kg_mnp_demo.evaluator import evaluate_case
from kg_mnp_demo.inference import apply_owlrl
from kg_mnp_demo.input_adapter import InputValidationError, load_and_normalize
from kg_mnp_demo.loader import load_graph, ontology_paths, project_root, reference_paths
from kg_mnp_demo.rdf_builder import build_case_graph
from kg_mnp_demo.trace_graph import build_assessment_subgraph, render_subgraph_html
from kg_mnp_demo.validator import validate_graph


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _validation_payload(label: str, result) -> dict[str, Any]:
    return {
        "label": label,
        "status": "PASSED" if result.conforms else "FAILED",
        "conforms": result.conforms,
        "detail": result.text if not result.conforms else "",
    }


def merge_reference_graph(instance: Graph) -> Graph:
    """Merge ontology + reference systems/regulations into a working graph."""
    base = load_graph(ontology_paths() + reference_paths())
    for triple in instance:
        base.add(triple)
    return base


def run_pipeline(
    input_path: Path | str,
    output_dir: Path | str,
    *,
    write_html: bool = True,
    print_rdf: bool = False,
) -> dict[str, Any]:
    """Full JSON input pipeline. Returns result dict and writes artifacts."""
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        normalized = load_and_normalize(input_path)
    except InputValidationError as exc:
        payload = {
            "status": "JSON_SCHEMA_FAILED",
            "errors": exc.errors,
            "publishable": False,
        }
        _write_json(output_dir / "input_validation.json", payload)
        return {
            "exit_code": 1,
            "publishable": False,
            "case_id": None,
            "decision": None,
            "errors": exc.errors,
            "input_validation": payload,
            "assessment_validation": None,
            "evaluation": None,
            "trace_subgraph": None,
            "output_dir": str(output_dir),
        }

    normalized_dict = normalized.to_dict()
    _write_json(output_dir / "normalized_input.json", normalized_dict)

    instance = build_case_graph(normalized)
    instance.serialize(destination=output_dir / "input_graph.ttl", format="turtle")
    if print_rdf:
        print(instance.serialize(format="turtle"))

    working = merge_reference_graph(instance)
    input_graph_snapshot = deepcopy(working)

    input_shacl = validate_graph(working)
    input_validation = _validation_payload("Input Graph Validation", input_shacl)
    _write_json(output_dir / "input_validation.json", input_validation)

    if not input_shacl.conforms:
        return {
            "exit_code": 1,
            "publishable": False,
            "case_id": normalized.case_id,
            "decision": None,
            "errors": [input_validation["detail"]],
            "input_validation": input_validation,
            "assessment_validation": None,
            "evaluation": None,
            "trace_subgraph": None,
            "normalized": normalized_dict,
            "assessment_time": normalized.assessment_time,
            "output_dir": str(output_dir),
        }

    before = len(working)
    apply_owlrl(working)
    inference = {
        "triples_before": before,
        "triples_after": len(working),
        "triples_added": len(working) - before,
    }
    _write_json(output_dir / "inference.json", inference)

    evaluation = evaluate_case(
        working,
        normalized.case_id,
        use_updated_rules=True,
        assessment_time=normalized.assessment_time,
        validate=False,
    )
    evaluation["assessment_time"] = normalized.assessment_time.strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    evaluation["publishable"] = False  # set after assessment SHACL

    working.serialize(destination=output_dir / "assessment_graph.ttl", format="turtle")

    assessment_shacl = validate_graph(working)
    assessment_validation = _validation_payload(
        "Assessment Graph Validation", assessment_shacl
    )
    _write_json(output_dir / "assessment_validation.json", assessment_validation)

    publishable = assessment_shacl.conforms
    if not publishable:
        evaluation["validation_status"] = "FAILED"
        evaluation["validation_detail"] = assessment_validation["detail"]
        evaluation["publishable"] = False
        evaluation["publication_status"] = "NOT_PUBLISHABLE"
    else:
        evaluation["validation_status"] = "PASSED"
        evaluation["validation_detail"] = ""
        evaluation["publishable"] = True
        evaluation["publication_status"] = "PUBLISHABLE"

    _write_json(output_dir / "evaluation.json", evaluation)

    subgraph = build_assessment_subgraph(working, normalized.case_id)
    _write_json(output_dir / "trace_subgraph.json", subgraph)

    if write_html:
        html = _render_report(
            normalized_dict,
            input_validation,
            assessment_validation,
            evaluation,
            subgraph,
            inference,
        )
        (output_dir / "report.html").write_text(html, encoding="utf-8")

    exit_code = 0 if publishable else 1
    return {
        "exit_code": exit_code,
        "publishable": publishable,
        "case_id": normalized.case_id,
        "decision": evaluation.get("decision"),
        "blocking_reasons": evaluation.get("blocking_reasons"),
        "input_validation": input_validation,
        "assessment_validation": assessment_validation,
        "evaluation": evaluation,
        "trace_subgraph": subgraph,
        "inference": inference,
        "normalized": normalized_dict,
        "assessment_time": normalized.assessment_time,
        "input_graph": input_graph_snapshot,
        "assessment_graph": working,
        "output_dir": str(output_dir),
    }


def _render_report(
    normalized: dict[str, Any],
    input_validation: dict[str, Any],
    assessment_validation: dict[str, Any],
    evaluation: dict[str, Any],
    subgraph: dict[str, Any],
    inference: dict[str, Any],
) -> str:
    import html as html_mod

    def esc(v: Any) -> str:
        return html_mod.escape("" if v is None else str(v))

    reasons = evaluation.get("blocking_reasons") or []
    reason_html = "".join(
        f"<li><code>{esc(r.get('reason_code'))}</code> · rule {esc(r.get('rule_id'))} "
        f"v{esc(r.get('rule_version'))} · clause {esc(r.get('regulatory_clause'))} "
        f"· action {esc(r.get('action_code'))}</li>"
        for r in reasons
    ) or "<li class='muted'>无阻塞原因</li>"

    pub = evaluation.get("publication_status") or (
        "PUBLISHABLE" if evaluation.get("publishable") else "NOT_PUBLISHABLE"
    )
    tree = render_subgraph_html(subgraph)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>KG-MNP JSON 输入流水线报告 — {esc(evaluation.get('case_id'))}</title>
<style>
  :root {{ --ink:#1c2430; --muted:#5b6777; --line:#d7dde6; --bg:#f3f6fa; --panel:#fff; --accent:#0b6e4f; --warn:#9b2c2c; }}
  body {{ margin:0; font-family:"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif; color:var(--ink);
    background: radial-gradient(1000px 420px at 0% -10%, #dceee6 0%, transparent 55%), var(--bg); }}
  main {{ max-width:960px; margin:0 auto; padding:1.5rem; }}
  section {{ background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:1.1rem 1.25rem; margin:1rem 0; }}
  h1 {{ font-size:1.55rem; }} h2 {{ font-size:1.15rem; margin:0 0 .75rem; }}
  .badge {{ display:inline-block; padding:.45rem .8rem; border-radius:8px; background:#fff5f5; border:1px solid #f0c2c2; color:var(--warn); font-weight:700; }}
  .badge.ok {{ background:#f0fff4; border-color:#c6f6d5; color:#276749; }}
  .muted {{ color:var(--muted); }}
  table {{ width:100%; border-collapse:collapse; }} th,td {{ border-bottom:1px solid var(--line); padding:.45rem .3rem; text-align:left; }}
  .subgraph ul.tree {{ list-style:none; padding-left:1rem; }}
  .subgraph .pred {{ color:var(--accent); font-family:ui-monospace,Consolas,monospace; font-size:.9rem; margin-right:.35rem; }}
  .subgraph .node {{ display:inline-block; margin:.15rem 0; padding:.2rem .45rem; background:#f8fafc; border:1px solid var(--line); border-radius:6px; }}
  .subgraph .ntype {{ color:var(--muted); font-size:.78rem; margin-right:.35rem; }}
  .subgraph .nlabel,.subgraph .leaf {{ font-weight:600; }}
</style>
</head>
<body>
<main>
  <h1>KG-MNP JSON → RDF 资格判断报告</h1>
  <p class="muted">评估时间：{esc(evaluation.get('assessment_time'))} · 发布状态：{esc(pub)}</p>

  <section>
    <h2>输入摘要</h2>
    <table>
      <tr><th>案件编号</th><td>{esc(normalized.get('case_id'))}</td></tr>
      <tr><th>申请人</th><td>{esc(normalized.get('subscriber', {}).get('subscriber_id'))}</td></tr>
      <tr><th>脱敏号码</th><td>{esc(normalized.get('phone_number', {}).get('masked_number'))}</td></tr>
      <tr><th>账户</th><td>{esc(normalized.get('account', {}).get('account_id'))}</td></tr>
      <tr><th>合约状态</th><td>{esc(normalized.get('evidence', {}).get('contract', {}).get('contract_status'))}</td></tr>
      <tr><th>合约截止</th><td>{esc(normalized.get('evidence', {}).get('contract', {}).get('contract_end_time'))}</td></tr>
    </table>
  </section>

  <section>
    <h2>两次 SHACL 验证</h2>
    <p>输入图 SHACL：<strong>{esc(input_validation.get('status'))}</strong></p>
    <p>评估结果图 SHACL：<strong>{esc(assessment_validation.get('status'))}</strong></p>
    <p class="muted">OWL-RL 新增三元组：{esc(inference.get('triples_added'))}</p>
  </section>

  <section>
    <h2>资格结论</h2>
    <div class="badge {'ok' if evaluation.get('decision')=='ELIGIBLE' else ''}">{esc(evaluation.get('decision'))}</div>
    <ul>{reason_html}</ul>
    {"<p><strong>NOT_PUBLISHABLE</strong>：评估结果图未通过验证，结论仅供调试。</p>" if not evaluation.get("publishable") else ""}
  </section>

  <section>
    <h2>资格判断追溯子图</h2>
    <p class="muted">仅展示真实 RDF 对象属性；非线性伪链。</p>
    {tree}
  </section>

  <section>
    <h2>研究边界</h2>
    <p>JSON 为合成业务输入；监管条款为演示条款；非生产运营商系统；不含真实外部接口。</p>
  </section>
</main>
</body>
</html>
"""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="KG-MNP JSON → RDF eligibility assessment pipeline"
    )
    p.add_argument("--input", required=True, help="Path to case JSON input")
    p.add_argument(
        "--output-dir",
        default=None,
        help="Output directory (default: runtime_outputs/<case>)",
    )
    p.add_argument("--no-html", action="store_true")
    p.add_argument("--print-rdf", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    args = build_parser().parse_args(argv)
    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = project_root() / input_path

    output_dir = Path(args.output_dir) if args.output_dir else None
    if output_dir is None:
        stem = input_path.stem
        output_dir = project_root() / "runtime_outputs" / stem
    elif not output_dir.is_absolute():
        output_dir = project_root() / output_dir

    try:
        result = run_pipeline(
            input_path,
            output_dir,
            write_html=not args.no_html,
            print_rdf=args.print_rdf,
        )
    except FileNotFoundError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"错误：JSON 解析失败：{exc}", file=sys.stderr)
        return 1

    print("=" * 60)
    print("KG-MNP JSON → RDF 资格判断流水线")
    print("=" * 60)
    print()
    if result.get("errors") and result.get("decision") is None and result.get("case_id") is None:
        print("JSON Schema 验证：FAILED")
        for err in result["errors"]:
            print(f"  - {err}")
        return result["exit_code"]

    print(f"案件编号：{result.get('case_id')}")
    at = result.get("assessment_time")
    if isinstance(at, datetime):
        print(f"评估时间：{at.strftime('%Y-%m-%dT%H:%M:%SZ')}")
    print(f"输入图 SHACL：{(result.get('input_validation') or {}).get('status')}")
    print(f"评估结果图 SHACL：{(result.get('assessment_validation') or {}).get('status')}")
    if result.get("evaluation"):
        print(f"资格结论：{result['evaluation'].get('decision')}")
        print(f"发布状态：{result['evaluation'].get('publication_status')}")
        for r in result["evaluation"].get("blocking_reasons") or []:
            print(f"  - {r.get('reason_code')} ({r.get('rule_id')} v{r.get('rule_version')})")
    print()
    print(f"输出目录：{result.get('output_dir')}")
    return int(result["exit_code"])


if __name__ == "__main__":
    sys.exit(main())
