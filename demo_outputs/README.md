# demo_outputs

本目录存放本地一键演示的自动生成结果。

## 生成方式

```bash
python scripts/showcase_demo.py
```

或指定输出目录：

```bash
python scripts/showcase_demo.py --output-dir demo_outputs
```

## 文件说明

| 文件 | 说明 |
|------|------|
| `case03_input_summary.json` | CASE-03 输入摘要（从 RDF 解析） |
| `case03_validation.json` | SHACL 验证结果 |
| `case03_inference.json` | OWL-RL 推理前后三元组与示例推导 |
| `case03_evaluation.json` | 资格判断完整机器可读结果 |
| `case03_trace.json` | SPARQL 追溯与人类可读追溯链 |
| `all_cases_summary.json` | 六个案例汇总 |
| `demo_report.html` | 可双击打开的 HTML 演示报告 |
| `case03_what_if.json` | 仅在使用 `--what-if` 时生成 |

**请勿手工编辑 JSON / HTML 结果文件。** 重复运行脚本会覆盖生成内容。
