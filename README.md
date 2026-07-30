# KG-MNP：携号转网可追溯资格判断本体 Demo

确定性、可离线运行的 Mobile Number Portability（MNP）资格判断原型：给定脱敏案件与证据，输出资格结论、独立阻塞原因、证据/规则/监管条款/处理动作，以及可查询的追溯链。

## 中央研究问题

在运营商携号转网资格判断中，如何用本体与知识表示把**证据—规则版本—监管条款—结论—处理动作**固化为可审计、可复现的追溯结构，并在证据缺失/过期与规则更新时给出安全、可定位的结果？

## 什么不是创新 / 什么是候选贡献

**不是本项目创新：** OWL、知识图谱、RDFLib、pySHACL、OWL-RL、TM Forum Open APIs、CTO 本体本身。

**候选贡献：** 面向 MNP 的证据—规则—结论—监管条款—处理动作追溯层；证据时间与规则版本感知；多阻塞原因分解；缺失证据安全处理（`MANUAL_REVIEW`）；规则更新影响定位。

**边界：** 这是领域本体与知识表示原型，**不声称**提出新的通用推理算法。

## 开源如何使用

| 来源 | 用法 |
|------|------|
| **CTO**（GPL-3.0） | 仅概念参考与对齐说明；**不复制** OWL 文件；运行时不依赖 |
| **TM Forum** TMF629/637/620（Apache-2.0） | 通过 `mappings/tmf_to_mnp.yaml` 做字段映射；**不当作 OWL** |
| **RDFLib / pySHACL / owlrl** | MVP 运行依赖 |
| **Protégé** | 人工打开/检查本体 |
| **WIDOCO** | 可选 HTML 文档（失败不影响核心测试） |
| **neosemantics / Neo4j** | Docker Compose 实际图存储与 Cypher 追溯（可选；离线测试不依赖） |
| **neo4j Python driver** | Bolt 客户端（`pip install -e ".[neo4j]"`） |

**为何 CTO 只做概念参考：** GPL-3.0 复制分发会引入 copyleft 义务；且 CTO 侧重宽带/网络/组织，与 MNP 资格追溯层不完全同构。

**为何 TM Forum 走映射层：** 它们是 OpenAPI/JSON 数据模型，不是 OWL；禁止把 JSON schema 对象写成 `owl:equivalentClass`。

## 职责划分

| 组件 | 职责 |
|------|------|
| OWL | 概念、关系、稳定基数/互斥 |
| SHACL | 实例完整性 |
| OWL-RL | 确定类型/关系扩展 |
| Python 规则引擎 | 金额、日期、有效期、资格规则 |
| SPARQL | 离线追溯查询 |
| Neo4j + Cypher | 实际持久化与路径追溯（默认 CLI backend） |

## 安装

需要 Python 3.11+（已在 3.12 验证）。

```bash
cd kg-mnp-demo
python -m pip install -e ".[dev,neo4j]"
```

## 运行（离线 RDF）

```bash
python -m kg_mnp_demo.cli validate --case CASE-03
python -m kg_mnp_demo.cli infer --case CASE-03
python -m kg_mnp_demo.cli evaluate --case CASE-03 --backend rdf
python -m kg_mnp_demo.cli trace --case CASE-03 --backend rdf
python -m kg_mnp_demo.cli mappings
python -m kg_mnp_demo.cli sources
python -m kg_mnp_demo.cli run-all --backend rdf
```

## 运行（Neo4j 实际化，默认 backend）

```bash
docker compose up -d
python -m kg_mnp_demo.cli neo4j-ping
python -m kg_mnp_demo.cli neo4j-load --case CASE-03 --reset
python -m kg_mnp_demo.cli evaluate --case CASE-03 --backend neo4j
python -m kg_mnp_demo.cli trace --case CASE-03 --backend neo4j
python -m kg_mnp_demo.cli run-all --backend neo4j
```

详见 [`docs/neo4j_extension.md`](docs/neo4j_extension.md)。

或：`make test` / `make run-all` / `make evaluate-case03` / `make neo4j-up`

## 测试

```bash
pytest                 # 离线核心 + neo4j 测试（无库则 skip）
pytest -m neo4j        # 仅 Neo4j 集成测试
python scripts/check_references.py
```

离线核心测试**不访问网络**、不依赖 Neo4j。

## Protégé

用 Protégé 5.6.x 打开 `ontology/mnp-core.ttl`，可选加载 `mnp-compliance.ttl`。`mnp-alignments.ttl` 仅对齐注释，非运行必需。

## WIDOCO

```bash
bash scripts/generate_docs.sh
```

固定版本见脚本内 `WIDOCO_VERSION=1.4.25`。若无 Java/无法下载，脚本失败但**核心 pytest 仍应通过**。成功时检查 `docs/ontology-site/index.html`。

## 六个案例预期

| 案例 | 结论 |
|------|------|
| CASE-01 | ELIGIBLE |
| CASE-02 | BLOCKED（仅欠费） |
| CASE-03 | BLOCKED（合约；完整追溯） |
| CASE-04 | BLOCKED（欠费+合约，两条链） |
| CASE-05 | MANUAL_REVIEW（关键证据过期） |
| CASE-06 | 规则 1.0→1.1；旧评估可定位并标记重评；现评估因间隔不足 BLOCKED |

## MVP 不包含

真实运营商 API、大模型判断、付费接口、多智能体编排。  
Neo4j 已作为可选实际后端（Docker Compose）；离线 RDF 链路仍完整可用。

## 后续 Neo4j

见 `docs/neo4j_extension.md`（Compose 启动、n10s 导入、Cypher 追溯）。

## 许可证

本仓库代码与本体：Apache-2.0。第三方见 `THIRD_PARTY_NOTICES.md` 与 `references/source_manifest.yaml`。
