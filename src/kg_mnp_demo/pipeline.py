"""JSON → RDF → eligibility assessment pipeline.

File I/O and CLI live here. Core evaluation is delegated to
``kg_mnp_demo.application.AssessmentService`` so REST APIs share one path.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from kg_mnp_demo.application.assessment_service import (
    AssessmentService,
    write_assessment_artifacts,
)
from kg_mnp_demo.application.errors import ApplicationError
from kg_mnp_demo.loader import merge_reference_graph, project_root
from kg_mnp_demo.trace_graph import render_subgraph_html

# Re-export for existing imports (tests / showcase).
__all__ = ["run_pipeline", "merge_reference_graph", "main", "build_parser"]


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run_pipeline(
    input_path: Path | str,
    output_dir: Path | str,
    *,
    write_html: bool = True,
    print_rdf: bool = False,
) -> dict[str, Any]:
    """Full JSON input pipeline. Returns result dict and writes artifacts.

    Compatibility wrapper around ``AssessmentService``. Return shape preserves
    fields expected by existing tests and CLI.
    """
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    service = AssessmentService()
    try:
        raw = json.loads(input_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ApplicationError(
                "INPUT_SCHEMA_ERROR",
                details=["(root) must be a JSON object"],
            )
        execution = service.assess_execution(raw, persist_artifacts=False)
    except json.JSONDecodeError:
        raise
    except ApplicationError as exc:
        if exc.code.value == "INPUT_SCHEMA_ERROR":
            payload = {
                "status": "JSON_SCHEMA_FAILED",
                "errors": exc.details,
                "publishable": False,
            }
            _write_json(output_dir / "input_validation.json", payload)
            return {
                "exit_code": 1,
                "publishable": False,
                "case_id": None,
                "decision": None,
                "errors": exc.details,
                "input_validation": payload,
                "assessment_validation": None,
                "evaluation": None,
                "trace_subgraph": None,
                "output_dir": str(output_dir),
                "assessment_response": exc.to_dict(),
            }
        raise

    artifacts = write_assessment_artifacts(
        execution, output_dir, write_html=write_html
    )
    execution.response["artifacts"] = artifacts

    if print_rdf and execution.instance_graph is not None:
        print(execution.instance_graph.serialize(format="turtle"))

    response = execution.response
    validations = response.get("validations") or {}
    assessment_time = response.get("assessment_time")
    if isinstance(assessment_time, str):
        try:
            assessment_time_dt = datetime.fromisoformat(
                assessment_time.replace("Z", "+00:00")
            )
        except ValueError:
            assessment_time_dt = assessment_time
    else:
        assessment_time_dt = assessment_time

    return {
        "exit_code": execution.exit_code,
        "publishable": execution.publishable,
        "case_id": execution.case_id,
        "decision": execution.decision,
        "blocking_reasons": response.get("blocking_reasons"),
        "input_validation": validations.get("input_graph"),
        "assessment_validation": validations.get("assessment_graph"),
        "evaluation": execution.evaluation,
        "trace_subgraph": response.get("trace_subgraph"),
        "inference": response.get("inference"),
        "normalized": execution.normalized,
        "assessment_time": assessment_time_dt,
        "input_graph": execution.assessment_graph,  # legacy: working graph snapshot
        "assessment_graph": execution.assessment_graph,
        "output_dir": str(output_dir),
        "assessment_response": response,
        "errors": (
            [execution.error.message]
            if execution.error and execution.decision is None
            else None
        ),
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
