# KG-MNP Ontology and Knowledge Graph Foundation

KG-MNP 本体与知识图谱基础构建阶段。

仓库当前围绕可审计的语义建模与知识图谱发布基础展开。中央链路为：

```text
Cleaned Partial Data
→ Auditable Modeling Proposal
→ Confirmed Modeling Package
→ OWL / SHACL / RDF Knowledge Graph
→ GraphDB / WebVOWL
```

Stage 01 只完成旧系统退场和仓库入口清理；Proposal、确认包、GraphDB 与
WebVOWL 尚未在本阶段实现。

## 当前边界

- 当前没有前端，也没有 Node、Vite、Playwright 或 Nginx 运行路径。
- 当前不以携号转网资格判断为中央任务。
- 当前没有 HTTP API 或 SQLite 执行历史服务。
- 当前不使用 Neo4j 作为正式后端；相关实现和 Docker 入口已移除。
- GraphDB 和 WebVOWL 是后续阶段的发布目标，本阶段尚未接入。
- 现有资格规则、案例和追溯代码仅作为下游示例资产保留。

## 保留的基础资产

| 目录 | 作用 |
|---|---|
| `ontology/` | 现有模块化 OWL/Turtle 本体 |
| `shapes/` | SHACL 数据质量约束 |
| `mappings/` | TM Forum 字段到 KG-MNP 术语的显式映射 |
| `queries/` | 离线 SPARQL 查询 |
| `config/ontology_modules.yaml` | 本体模块装载清单 |
| `references/` | 来源、许可与复用审计材料 |
| `src/kg_mnp_demo/loader.py` | RDFLib 本体与案例加载入口 |
| `src/kg_mnp_demo/inference.py` | OWL-RL 离线推理 |
| `src/kg_mnp_demo/validator.py` | pySHACL 离线验证 |

本阶段没有修改这些本体资产的核心语义。

WIDOCO 文档站点是可再生成的构建输出，不进入版本控制；需要时运行
`scripts/generate_docs.sh`，产物写入已忽略的 `docs/ontology-site/`。

## 安装与验证

需要 Python 3.11+。

```bash
make install
make verify-python-core
```

等价的独立命令为：

```bash
python -m pip install -e ".[dev]"
python -m pytest tests/test_ontology.py tests/test_shacl.py tests/test_inference.py \
  tests/test_mappings.py tests/test_input_adapter.py tests/test_rdf_builder.py \
  tests/ontology tests/scripts/test_repo_hygiene.py
python scripts/check_references.py
python scripts/check_repo_hygiene.py
```

测试与 CI 门禁不依赖 Node、浏览器、Docker、数据库服务或外部运行服务；首次安装
Python 依赖时仍可能需要访问包索引。

## Legacy Eligibility Use Case

携号转网资格判断仍用于保护已有研究结果，包括九个案例、资格规则、JSON
输入、RDF 物化、SHACL、OWL-RL 与 SPARQL 追溯测试。它不是新的建模
Pipeline，也不进入默认 README 工作流。边界与显式运行方式见
[`examples/eligibility-use-case/README.md`](examples/eligibility-use-case/README.md)。

版本化的 `demo_outputs/` 是既有研究快照；本地生成物必须写入已忽略的
`runtime_outputs/`。

## 工程记录

- Stage 01 基线与迁移审计：
  [`docs/migration/stage-01-repository-baseline.md`](docs/migration/stage-01-repository-baseline.md)
- 本体模块说明：[`ontology/README.md`](ontology/README.md)
- 来源审计：[`references/source_manifest.yaml`](references/source_manifest.yaml)

## 许可证

仓库代码与本体使用 Apache-2.0；第三方说明见
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)。
