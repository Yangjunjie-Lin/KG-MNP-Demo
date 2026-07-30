# 本地一键演示说明

本仓库提供离线可重复的携号转网资格判断本体演示。GitHub Actions 不可用时，全部验收在本地完成。

## 为什么默认使用 RDF 后端

- 不依赖 Docker、Neo4j、网络或付费 API
- 结果可复现，适合答辩与本地验收
- Neo4j 功能仍保留，但必须显式启用：`--backend neo4j`

演示脚本 `scripts/showcase_demo.py` **强制** `backend = rdf`，即使设置了 `KG_MNP_BACKEND=neo4j` 也不会切换。

## 为什么不依赖 GitHub CI

当前环境无法使用 GitHub Actions。请在本地执行安装、测试与演示命令；以本机 `pytest` 与 `showcase_demo.py` 输出为准。

## 安装

需要 Python 3.11+。

### Windows PowerShell

```powershell
cd KG-MNP-Demo
python -m pip install -e ".[dev]"
```

可选 Neo4j 客户端（演示本身不需要）：

```powershell
python -m pip install -e ".[dev,neo4j]"
```

### macOS / Linux

```bash
cd KG-MNP-Demo
python -m pip install -e ".[dev]"
# optional: python -m pip install -e ".[dev,neo4j]"
```

## 一键演示

```bash
python scripts/showcase_demo.py
```

默认行为：

1. 展示 CASE-03 输入摘要
2. SHACL 验证
3. OWL-RL 推理
4. 确定性资格判断
5. 完整本体追溯链
6. 六个案例汇总
7. 写出 `demo_outputs/*.json`
8. 生成 `demo_outputs/demo_report.html`

### 常用参数

```bash
python scripts/showcase_demo.py --case CASE-03
python scripts/showcase_demo.py --all
python scripts/showcase_demo.py --output-dir demo_outputs
python scripts/showcase_demo.py --no-html
```

### What-if（内存中改输入，不改 TTL）

```bash
python scripts/showcase_demo.py --what-if contract-expired
python scripts/showcase_demo.py --what-if add-debt
python scripts/showcase_demo.py --what-if expire-evidence
```

`contract-expired`：将 CASE-03 合约改为已到期，再重新判断。原始 TTL 文件保持不变。

## 固定评估时间

规则引擎使用固定时间：

```text
2026-07-01T00:00:00Z
```

终端、JSON 与 HTML 都会提示：本次演示使用固定评估时间，以保证结果可重复。不要误以为系统使用当前实时日期。

## 输出文件

见 [`demo_outputs/README.md`](../demo_outputs/README.md)。

HTML 报告可直接双击打开，无需启动 Web 服务器。

## 本地验收命令

```bash
python -m pip install -e ".[dev]"
pytest
python scripts/check_references.py
python scripts/showcase_demo.py
```

离线 CLI（显式 RDF）：

```bash
python -m kg_mnp_demo.cli validate --case CASE-03
python -m kg_mnp_demo.cli infer --case CASE-03
python -m kg_mnp_demo.cli evaluate --case CASE-03 --backend rdf
python -m kg_mnp_demo.cli trace --case CASE-03 --backend rdf
python -m kg_mnp_demo.cli run-all --backend rdf
```

## 常见错误

| 现象 | 处理 |
|------|------|
| `ModuleNotFoundError: kg_mnp_demo` | 先执行 `python -m pip install -e ".[dev]"` |
| Neo4j 连接失败 | 演示不需要 Neo4j；使用 `showcase_demo.py` 或 `--backend rdf` |
| HTML 打不开 / 乱码 | 用浏览器打开 `demo_outputs/demo_report.html`（UTF-8） |
| 结果与预期不一致 | 确认未改 `data/*.ttl` 与 `rules/eligibility_rules.yaml`；确认评估时间为固定值 |
| `pytest` 中 neo4j 测试 skipped | 正常；无数据库时应 skip，不影响离线验收 |

## 如何恢复环境

```bash
git status
git checkout -- data/ ontology/ rules/ shapes/ queries/
python -m pip install -e ".[dev]"
python scripts/showcase_demo.py
```

What-if 模式不会写入 TTL；若仍担心，可用 `git checkout -- data/` 恢复案例文件。

## 演示脚本如何复用现有代码

| 步骤 | 复用模块 |
|------|----------|
| 加载 | `load_case_graph` |
| 验证 | `validate_graph` |
| 推理 | `apply_owlrl` |
| 判断 | `evaluate_case` / `materialize_assessment` |
| 追溯 | `decision_trace` / `blocking_reasons` / `affected_assessments` |

脚本不重新实现资格规则，也不硬编码六个案例的最终答案。
