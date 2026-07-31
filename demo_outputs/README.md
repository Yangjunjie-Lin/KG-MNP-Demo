# demo_outputs

本目录保存一套经过确认的离线演示快照，便于仓库访问者直接查看。

这些文件由以下命令生成：

```bash
python scripts/showcase_demo.py \
  --case CASE-03 \
  --what-if contract-expired \
  --output-dir demo_outputs
```

请勿手工修改 JSON 或 HTML。

日常运行结果应写入 `runtime_outputs/`。该目录已被 `.gitignore` 忽略，不纳入版本控制。

| 目录 | 定位 |
|------|------|
| `demo_outputs/` | 可版本控制的确认演示快照 |
| `runtime_outputs/` | 用户本地运行时生成，不进入 Git |

## 双 SHACL 验证快照

| 文件 | 含义 |
|------|------|
| `case03_input_validation.json` | 输入 RDF 图的 SHACL 验证结果 |
| `case03_assessment_validation.json` | 资格判断物化后评估图的 SHACL 验证结果 |

不再生成旧兼容文件 `case03_validation.json`（内容与 `case03_input_validation.json` 重复）。
