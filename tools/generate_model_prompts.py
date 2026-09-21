"""Generate the source-derived catalogue; never calls a model or reads answers."""
from pathlib import Path

from zhigou_toolchain.modeling.delivery.exchange_io import json_bytes
from zhigou_toolchain.modeling.five_stage.coverage import implementation_view
from zhigou_toolchain.modeling.five_stage.prompts import markdown, source_catalogue


def main():
    root = Path(__file__).resolve().parents[1] / "docs/ontology"
    catalogue = source_catalogue()
    (root / "MODEL_CALL_PROMPTS.json").write_bytes(json_bytes(catalogue))
    (root / "MODEL_CALL_PROMPTS.md").write_text(markdown(catalogue), encoding="utf-8", newline="\n")
    audit = root / "AGENT_STEP_AUDIT.md"
    before, tail = audit.read_text(encoding="utf-8").split("<!-- METHOD_AUDIT_START -->", 1)
    _, after = tail.split("<!-- METHOD_AUDIT_END -->", 1)
    rows = ["", "| 方法 / 原名称 | 实际函数 | 原操作入口 / 条件 |", "|---|---|---|"]
    for row in implementation_view():
        rows.append(f"| {row['method_id']} {row['name']} | `{row['function']}` | {row['operations']}；{row['condition']} |")
    audit.write_text(before + "<!-- METHOD_AUDIT_START -->\n" + "\n".join(rows) + "\n\n<!-- METHOD_AUDIT_END -->" + after, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
