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
| Stage 03 Formal OWL/SHACL Semantic Audit and Ontology Release Baseline | PASS |
| Stage 04–08 | NOT STARTED |

Stage 03 已完成正式 IRI 迁移、模块归属、Protégé catalog、SHACL profile 拆分，
以及 OWL 2 DL（ROBOT + HermiT）一致性检查。尚未实施 Modeling Proposal
Pipeline、Review/Confirm、GraphDB 或 WebVOWL。

## 当前边界

- 当前没有前端，也没有 Node、Vite、Playwright 或 Nginx 运行路径。
- 当前不以携号转网资格判断为中央任务；九个 legacy 案例作为 eligibility profile 回归资产保留。
- 当前没有 HTTP API 或 SQLite 执行历史服务作为本阶段交付物。
- GraphDB 和 WebVOWL 是后续阶段目标，本阶段尚未接入。
- 正式本体发布版本为 **1.0.0**；Python 包版本独立，不因本体版本机械升高。

## 保留的基础资产

| 目录 | 作用 |
|---|---|
| `ontology/` | 正式模块化 OWL/Turtle（含 `kg-mnp.ttl` 与 `catalog-v001.xml`） |
| `shapes/` | foundation / ontology-schema SHACL |
| `examples/eligibility-use-case/shapes/` | legacy 资格用例 SHACL |
| `mappings/` | TM Forum 字段到 KG-MNP 术语的显式映射 |
| `queries/` | 离线 SPARQL 查询 |
| `config/ontology_modules.yaml` | 本体模块装载清单（Loader 唯一来源） |
| `config/namespaces.yaml` | 正式 IRI 命名空间政策 |
| `config/modeling-statuses.yaml` | 审核状态 / 问题类型 / 发布范围词汇 |
| `config/ontology-release-policy.yaml` | 本体版本发布政策 |
| `references/` | 来源、许可与复用审计材料 |
| `src/kg_mnp_demo/loader.py` | 配置驱动的 RDFLib 离线加载 |
| `src/kg_mnp_demo/inference.py` | OWL-RL 离线推理 |
| `src/kg_mnp_demo/validator.py` | SHACL profile 验证 |

## 安装与验证

需要 Python 3.11+。完整 OWL 2 DL 检查需要 Java 17+（ROBOT/HermiT）。

```bash
make install
make verify-stage-01
make verify-stage-02
make verify-stage-03-core
make reasoner-check
make verify-reasoner-report
make verify-stage-03
```

### Protégé

打开 `ontology/kg-mnp.ttl`，确保同目录 `catalog-v001.xml` 可用（离线 imports）。

### SHACL profiles

```python
from kg_mnp_demo.validator import validate_graph, validate_ontology_schema
validate_graph(data_graph, profile="foundation")
validate_graph(data_graph, profile="eligibility")
validate_ontology_schema(ontology_graph)
```

### Legacy CLI

```bash
kg-mnp-eligibility evaluate --case CASE-03 --backend rdf
kg-mnp-eligibility trace --case CASE-03 --backend rdf
```

```bash
python -m pip install -e ".[dev]"
python -m pytest -q tests/governance
python scripts/check_references.py
python scripts/check_repo_hygiene.py
```

测试与 CI 门禁不依赖 Node、浏览器、Docker、数据库服务或外部 GraphDB/WebVOWL；
完整 reasoner 需要本机/CI 的 Java。CI 执行 `make verify-stage-03-core`、
`make reasoner-check` 与 `make verify-reasoner-report`。

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

- Stage 03 本体发布基线：
  [`docs/migration/stage-03-ontology-release.md`](docs/migration/stage-03-ontology-release.md)
- Stage 02 语义治理：
  [`docs/migration/stage-02-semantic-governance.md`](docs/migration/stage-02-semantic-governance.md)
- Stage 01 基线与收尾：
  [`docs/migration/stage-01-repository-baseline.md`](docs/migration/stage-01-repository-baseline.md)
- 语义权威 ADR：
  [`docs/adr/ADR-001-semantic-authority.md`](docs/adr/ADR-001-semantic-authority.md)
- 本体模块说明：[`ontology/README.md`](ontology/README.md)
- 来源审计：[`references/source_manifest.yaml`](references/source_manifest.yaml)

## 许可证

仓库代码与本体使用 Apache-2.0；第三方说明见
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)。
