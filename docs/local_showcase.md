# 本地一键演示说明

本仓库提供离线可重复的携号转网资格判断本体演示。GitHub Actions 不可用时，全部验收在本地完成。

## 为什么默认使用 RDF 后端

- 不依赖 Docker、Neo4j、网络或付费 API
- 结果可复现，适合答辩与本地验收
- Neo4j 功能仍保留，但必须显式启用：`--backend neo4j`

演示脚本 `scripts/showcase_demo.py` **强制** `backend = rdf`，即使设置了 `KG_MNP_BACKEND=neo4j` 也不会切换。

## 两类证据关系

| 关系 | 含义 |
|------|------|
| `MNPCase hasCaseEvidence EvidenceRecord` | 该案件可使用 / 已收集的证据集合 |
| `EligibilityAssessment usesEvidence EvidenceRecord` | 某一次评估实际选用的证据快照 |

规则引擎与输入摘要**仅**通过 `hasCaseEvidence` 选择证据，不再依赖 `Ev-03-*` 等 IRI 前缀。

## 真实追溯子图

追溯展示为以 `EligibilityAssessment` / `BlockingReason` 为中心的**依赖子图**，每条箭头对应真实 RDF 对象属性。  
边选择的唯一来源是 `queries/assessment_subgraph.rq`；`trace_graph.py` 只做 SPARQL 结果 → nodes/edges 转换与完整性校验，不再维护第二套 predicate 清单。

## 时间感知规则版本

规则按 `assessment_time` 落在 `effective_from`/`effective_to` 闭区间内选择唯一版本。重叠或无适用版本会抛出 `RuleConfigurationError`。

```bash
python scripts/check_rule_versions.py
```

## 两次 SHACL 验证

1. **Input Graph Validation**：判断前的输入实例完整性（含 `hasCaseEvidence`）。失败则不生成正式资格结论，非零退出。
2. **Assessment Graph Validation**：物化评估/决定/原因/依赖后的结果图。失败则标记 `NOT_PUBLISHABLE`，非零退出。

## JSON 外部输入

合成业务 JSON（非运营商真实接口）可直接进入完整流水线：

```bash
python scripts/showcase_demo.py --input inputs/case03.json --output-dir runtime_outputs/case03

python -m kg_mnp_demo.pipeline \
  --input inputs/case03.json \
  --output-dir runtime_outputs/pipeline-case03
```

输入样例见 `inputs/case03.json`；Schema 见 `schemas/mnp_case_input.schema.json`。

评估时间取自 JSON 的 `assessment_time`（不使用系统当前时间）。

## 为什么不依赖 GitHub CI

当前环境无法使用 GitHub Actions。请在本地执行安装、测试与演示命令；以本机 `pytest` 与 `showcase_demo.py` 输出为准。

## 安装

需要 Python 3.11+。

```powershell
cd KG-MNP-Demo
python -m pip install -e ".[dev]"
```

## 一键演示（预置 TTL 案例）

```bash
python scripts/showcase_demo.py --case CASE-03
```

默认行为：

1. 展示 CASE-03 输入摘要
2. 输入图 SHACL → OWL-RL → 资格判断 → 评估结果图 SHACL
3. 真实 RDF 追溯子图
4. 六个案例汇总
5. 写出 `demo_outputs/*.json` 与 `demo_report.html`

### 常用参数

```bash
python scripts/showcase_demo.py --case CASE-03
python scripts/showcase_demo.py --all
python scripts/showcase_demo.py --output-dir demo_outputs
python scripts/showcase_demo.py --no-html
python scripts/showcase_demo.py --input inputs/case03.json --output-dir runtime_outputs/case03
```

### What-if（内存中改输入，不改 TTL）

```bash
python scripts/showcase_demo.py --what-if contract-expired
python scripts/showcase_demo.py --what-if add-debt
python scripts/showcase_demo.py --what-if expire-evidence
```

What-if 通过 `hasCaseEvidence` + `evidenceType` 定位目标证据，不依赖 IRI 前缀。

## 固定评估时间

预置案例模式使用固定时间：

```text
2026-07-01T00:00:00Z
```

JSON 模式使用输入中的 `assessment_time`。两者都不使用系统当前时间。

## 输出文件

| 目录 | 定位 |
|------|------|
| `demo_outputs/` | 可版本控制的确认演示快照 |
| `runtime_outputs/` | 用户本地运行时生成，不进入 Git |

预置案例快照：见 [`demo_outputs/README.md`](../demo_outputs/README.md)。

JSON 流水线会在本地写出（目录可自定，以下仅为示例路径）：

```text
runtime_outputs/case03/
├── normalized_input.json
├── input_graph.ttl
├── input_validation.json
├── inference.json
├── evaluation.json
├── assessment_graph.ttl
├── assessment_validation.json
├── trace_subgraph.json
└── report.html
```

这些文件不会被提交；重新运行命令即可复现。

## 本地验收命令

```bash
python -m pip install -e ".[dev]"
pytest
python scripts/check_references.py
python scripts/showcase_demo.py --case CASE-03
python scripts/showcase_demo.py --input inputs/case03.json --output-dir runtime_outputs/case03
python -m kg_mnp_demo.pipeline --input inputs/case03.json --output-dir runtime_outputs/pipeline-case03
```

离线 CLI（显式 RDF）：

```bash
python -m kg_mnp_demo.cli evaluate --case CASE-03 --backend rdf
python -m kg_mnp_demo.cli trace --case CASE-03 --backend rdf
python -m kg_mnp_demo.cli run-all --backend rdf
```

## 当前边界

* JSON 是合成业务输入；
* 监管条款是演示条款，不是正式法律条文；
* 不是生产运营商系统；
* 不包含真实外部接口、大模型、Web 前端或 Neo4j 必选依赖。

## 演示脚本如何复用现有代码

| 步骤 | 复用模块 |
|------|----------|
| 加载 | `load_case_graph` / `rdf_builder` |
| 验证 | `validate_graph`（两次） |
| 推理 | `apply_owlrl` |
| 判断 | `evaluate_case` / `materialize_assessment` |
| 追溯 | `trace_graph.build_assessment_subgraph` |
| JSON | `input_adapter` → `pipeline` |
