# KG-MNP Ontology and Knowledge Graph Foundation

KG-MNP 本体与知识图谱基础构建阶段。

仓库当前围绕可审计的语义建模与知识图谱发布基础展开。中央链路为：

```text
CleanedPartialData
+ OntologyBaseline@version
+ MappingRules@version
+ TerminologyProfile@version
        ↓
ModelingProposal
        ↓
ReviewDecisionLog
        ↓
ConfirmedModelingPackage
        ↓
OWL / SHACL / ABox / Provenance / Review Artifacts
        ↓
GraphDB / WebVOWL
```

## 阶段状态

| Stage | Status |
|---|---|
| Stage 01 Repository Baseline | PASS |
| Stage 02 Semantic Governance | PASS |
| Stage 03–08 | 尚未实施 |

当前已经完成旧系统退场，并冻结语义治理。当前还没有 Modeling Proposal
Pipeline、Review/Confirm 实现、正式 IRI 迁移、GraphDB 或 WebVOWL。

## 当前边界

- 当前没有前端，也没有 Node、Vite、Playwright 或 Nginx 运行路径。
- 当前不以携号转网资格判断为中央任务。
- 当前没有 HTTP API 或 SQLite 执行历史服务。
- 当前不使用 Neo4j 作为正式后端；相关实现和 Docker 入口已移除。
- GraphDB 和 WebVOWL 是后续阶段的发布目标，本阶段尚未接入。
- 现有资格规则、案例和追溯代码仅作为下游示例资产保留。
- 语义权威、TBox/ABox 边界、状态词汇、命名空间与发布政策已冻结；正式编译器尚未实现。

## 保留的基础资产

| 目录 | 作用 |
|---|---|
| `ontology/` | 现有模块化 OWL/Turtle 本体 |
| `shapes/` | SHACL 数据质量约束 |
| `mappings/` | TM Forum 字段到 KG-MNP 术语的显式映射 |
| `queries/` | 离线 SPARQL 查询 |
| `config/ontology_modules.yaml` | 本体模块装载清单 |
| `config/namespaces.yaml` | 未来正式 IRI 命名空间政策 |
| `config/modeling-statuses.yaml` | 审核状态 / 问题类型 / 发布范围词汇 |
| `config/ontology-release-policy.yaml` | 本体版本发布政策 |
| `references/` | 来源、许可与复用审计材料 |
| `src/kg_mnp_demo/loader.py` | RDFLib 本体与案例加载入口 |
| `src/kg_mnp_demo/inference.py` | OWL-RL 离线推理 |
| `src/kg_mnp_demo/validator.py` | pySHACL 离线验证 |

本阶段没有修改这些本体资产的核心业务语义。现有 TTL 仍可能使用
`example.org`；正式 IRI 迁移属于 Stage 03。

WIDOCO 文档站点是可再生成的构建输出，不进入版本控制；需要时运行
`scripts/generate_docs.sh`，产物写入已忽略的 `docs/ontology-site/`。

## 安装与验证

需要 Python 3.11+。

```bash
make install
make verify-stage-01
make verify-semantic-governance
make verify-stage-02
```

等价的独立命令为：

```bash
python -m pip install -e ".[dev]"
python -m pytest -q tests/governance/test_stage_01_closure.py
python -m pytest -q tests/governance
python scripts/check_references.py
python scripts/check_repo_hygiene.py
```

测试与 CI 门禁不依赖 Node、浏览器、Docker、数据库服务或外部运行服务；首次安装
Python 依赖时仍可能需要访问包索引。CI 执行 `make verify-stage-02`。

## Legacy Eligibility Use Case

携号转网资格判断仍用于保护已有研究结果，包括九个案例、资格规则、JSON
输入、RDF 物化、SHACL、OWL-RL 与 SPARQL 追溯测试。它不是新的建模
Pipeline，也不进入默认 README 工作流。

```bash
kg-mnp-eligibility --help
kg-mnp-eligibility evaluate --case CASE-03 --backend rdf
```

`kg-mnp` 保留给未来本体建模中央 CLI，当前不得指向资格判断。边界与显式运行
方式见
[`examples/eligibility-use-case/README.md`](examples/eligibility-use-case/README.md)。

版本化的 `demo_outputs/` 是既有研究快照；本地生成物必须写入已忽略的
`runtime_outputs/`。

## 工程记录

- Stage 01 基线与收尾：
  [`docs/migration/stage-01-repository-baseline.md`](docs/migration/stage-01-repository-baseline.md)
- Stage 02 语义治理：
  [`docs/migration/stage-02-semantic-governance.md`](docs/migration/stage-02-semantic-governance.md)
- 语义权威 ADR：
  [`docs/adr/ADR-001-semantic-authority.md`](docs/adr/ADR-001-semantic-authority.md)
- 本体模块说明：[`ontology/README.md`](ontology/README.md)
- 来源审计：[`references/source_manifest.yaml`](references/source_manifest.yaml)

## 许可证

仓库代码与本体使用 Apache-2.0；第三方说明见
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)。
