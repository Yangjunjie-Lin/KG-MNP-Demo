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
| Stage 03 Formal Ontology Release | PASS |
| Stage 04 Modeling Contracts and Proposal Generation | PASS |
| Stage 05 Human Review and Confirmed Modeling Package | PASS |
| Stage 06–08 | NOT STARTED |

Stage 03 已完成正式 IRI 迁移、模块归属、Protégé catalog、SHACL profile 拆分，
以及 OWL 2 DL 一致性检查。Stage 04 已增加离线 Modeling Contract、冻结的
版本化依赖、稳定 ID、语义验证器和确定性 ModelingProposal Generator。Stage 05
已增加冻结 Review Policy、显式人工 Review Action、文件式审核工作流、以及确定性
`ConfirmedModelingPackage` Builder。ROBOT 是固定版本的命令行封装，HermiT 是由
它调用的 OWL 推理器；二者的版本在正式证明中分别记录。正式编译、GraphDB 和
WebVOWL 仍未实施。

Stage 03 收尾还将旧资格判断 JSON Schema 从根 `schemas/` 移至
`examples/eligibility-use-case/schemas/`，并把 `$id` 迁移到项目稳定的 HTTPS
Schema namespace。该 legacy eligibility contract 与中央 `CleanedPartialData`
contract 不同，且不会被 Modeling Pipeline 当作输入适配器。

## 当前边界

- 当前没有前端，也没有 Node、Vite、Playwright 或 Nginx 运行路径。
- 当前不以携号转网资格判断为中央任务；九个 legacy 案例作为 eligibility profile 回归资产保留。
- 当前没有 HTTP API 或 SQLite 执行历史服务作为本阶段交付物。
- 当前可以从 CleanedPartialData 生成确定性的、仅供审核的 ModelingProposal。
- 当前可以人工审核 Proposal，并生成 `ReviewDecisionLog` 与 `ConfirmedModelingPackage`。
- 当前没有默认决定、批量确认、自动确认或 LLM Reviewer。
- 当前不能从 Proposal 或 Confirmed Package 生成正式 OWL、SHACL 或 RDF。
- GraphDB 和 WebVOWL 是后续阶段目标，当前均未接入。
- `schemas/modeling/` 包含 11 个 Modeling Schema，并由本地 Registry 离线解析。
- 正式本体发布版本为 **1.0.0**；Python 包版本独立，不因本体版本机械升高。

## 保留的基础资产

| 目录 | 作用 |
|---|---|
| `ontology/` | 正式模块化 OWL/Turtle（含 `kg-mnp.ttl` 与 `catalog-v001.xml`） |
| `shapes/` | foundation / ontology-schema SHACL |
| `examples/eligibility-use-case/shapes/` | legacy 资格用例 SHACL |
| `examples/eligibility-use-case/schemas/` | legacy 资格输入 JSON Schema；不属于中央 Modeling Contract |
| `schemas/modeling/` | 中央 Modeling / Review Contracts 与稳定 HTTPS 标识符 |
| `config/modeling/` | 本体基线、Mapping Rules、Terminology Profile、Proposal/Review Policy |
| `examples/modeling/` | 六类无真实 PII 的输入与确定性黄金 Proposal |
| `examples/review/` | 显式人工审核 Action 与黄金 Decision Log / Package |
| `mappings/` | TM Forum 对齐参考与 modeling evidence；不是中央可执行规则 |
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

需要 Python 3.11+。完整 OWL 2 DL 检查需要 Java 17+。门禁只允许从 ROBOT
官方 release URL 下载 `1.9.7`：
`https://github.com/ontodev/robot/releases/download/v1.9.7/robot.jar`，并固定验证
SHA-256 `91890c2e83d0f092dd08731376f154b36610544cfbe8685337a1bf7244ccaa2d`。
已有缓存也会在每次使用前验证；下载内容先写临时文件，哈希匹配后才进入缓存。

固定 JAR 的内嵌 Maven metadata 将 HermiT dependency 标识为 `1.4.5.456`。
如果未来某个经批准的 ROBOT 发行物不能可靠给出该依赖版本，报告必须明确写
`UNKNOWN`，不得把 ROBOT 版本冒充为 HermiT 版本。项目只允许该 dependency
version 字段为 `UNKNOWN`；前提是固定 ROBOT 哈希、HermiT 实际执行和全部结果
校验都成功。Consistency 或运行状态为 `UNKNOWN`/`NOT_RUN` 时绝不允许 PASS。

```bash
make install
make verify-stage-01
make verify-stage-02
make verify-stage-03-core
make verify-schema-identifiers
make verify-robot-checksum
make reasoner-check
make verify-reasoner-run
make verify-reasoner-report
make verify-no-runtime-legacy-terms
make verify-stage-03
make verify-modeling-contracts
make verify-modeling-dependencies
make verify-modeling-proposal
make verify-modeling-determinism
make verify-modeling-cli
make verify-stage-04
make verify-review-contracts
make verify-review-policy
make verify-review-workflow
make verify-review-determinism
make verify-confirmed-package
make verify-package-readiness
make verify-review-security
make verify-review-cli
make verify-stage-05
```

`verify-stage-05` 是 CI 和本地收尾的完整入口；它先完整执行 `verify-stage-04`，
再依次执行 Review Contracts、Policy、Workflow、Determinism、Confirmed Package、
Readiness、Security（fail-closed finalize / independent package reconstruction）、
CLI 与 Stage 05 边界门禁。`review finalize` 执行完整语义验证；`package validate`
从权威输入独立重派生 Expected Package，自洽 self-hash 不是授权证明。`verify-stage-03` 内部严格按以下顺序执行：Stage 03
core（其中包含 Stage 01/02 回归）、Schema Identifier 门禁、ROBOT 校验、HermiT 实际运行、runtime run
验证、正式报告验证、运行态旧术语扫描。Schema Identifier 门禁只解析本地
`*.schema.json` 与 namespace 配置，不访问 `$id`、不下载远程 Schema。默认 `reasoner-check` 只写已忽略的
`runtime_reports/ontology/`，不得改动受版本控制文件。

### Reasoner 产物与哈希

一次运行的机器结果写入：

- `runtime_reports/ontology/reasoner-run.json`
- `runtime_reports/ontology/reasoner-input.nt`
- `runtime_reports/ontology/reasoned-ontology.owl`
- `runtime_reports/ontology/unsatisfiable-debug.owl` (present only when ROBOT emits an incoherence explanation; it is not parsed as a line-oriented class list)
- `runtime_reports/ontology/unsatisfiable.txt`
- `runtime_reports/ontology/unexpected-equivalences.json`

这里使用三个不同含义的哈希：

- `release_source_hash` 以稳定相对路径和 LF-normalized 内容覆盖根本体、配置声明
  的全部 runtime module、模块配置与 Protégé catalog；默认发布 profile 明确
  排除 optional alignments。
- `reasoner_input_semantic_hash` 覆盖 HermiT 实际读取图的 canonical RDF 表示，
  因而不受 Turtle 三元组顺序或 blank node 临时标识影响。
- `reasoner_input_file_hash` 是 HermiT 实际读取文件的逐字节 SHA-256，用于审计
  本次物理输入；它不再被当作发布源哈希。

Canonicalization 直接影响可复现哈希，因此两个依赖清单都精确固定
`rdflib==7.6.0`；runtime evidence 与正式 attestation 也记录该版本。

正式发布证明由受版本控制的
`docs/ontology/reasoner-attestation.json` 单一驱动，
`docs/ontology/reasoner-report.md` 必须从该 JSON 确定性生成，不得分别手工维护。
Markdown 中只保存 `python scripts/run_reasoner.py` 这类便携命令，不保存盘符、
用户名、临时目录或本机项目路径。普通本地运行和 CI 不更新正式证明；只有在
审核一次成功运行并确实要刷新发布证明时，才显式执行：

```bash
make reasoner-check
make verify-reasoner-run
python scripts/run_reasoner.py --update-attestation
make verify-reasoner-report
git diff --check
```

新增的 `owl:equivalentClass` 会从 reasoned ontology 与 asserted ontology 的差异中
计算。只有 `config/reasoner-allowlist.yaml` 中明确批准的无序类对可以保留；其他
新增等价类都会使 Stage 03 失败。`owl:Nothing` 相关项由不可满足命名类检查单独
处理，不能用等价类 allowlist 掩盖。

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
完整 reasoner 只需要 Java 17+ 和固定校验的 ROBOT。CI 执行单一完整门禁
`make verify-stage-03`，随后断言 `git diff` 与 `git status --short` 均为空，确保
Reasoner runtime 产物不会污染正式仓库。

## Legacy Eligibility Use Case

携号转网资格判断仍用于保护已有研究结果，包括九个案例、资格规则、JSON
输入、RDF 物化、SHACL、OWL-RL 与 SPARQL 追溯测试。它不是新的建模
Pipeline，也不进入默认 README 工作流。

其 JSON 输入合同位于
`examples/eligibility-use-case/schemas/mnp_case_input.schema.json`，使用项目
`schemas.legacy` 下的稳定、带版本 `$id`。它只服务 legacy eligibility 输入，不是
未来中央 Pipeline 的 `CleanedPartialData` 合同；根 `schemas/` 仍留给尚未开始的 Stage 04。

```bash
kg-mnp-eligibility --help
kg-mnp-eligibility evaluate --case CASE-03 --backend rdf
```

`kg-mnp` 现为中央 Modeling CLI，`kg-mnp-eligibility` 仍只运行 legacy 资格用例；
二者互不代理。中央 CLI 的典型离线命令为：

```bash
kg-mnp contracts list
kg-mnp dependencies verify
kg-mnp contracts validate --contract cleaned-partial-data \
  --input examples/modeling/inputs/partial-basic.json
kg-mnp propose --input examples/modeling/inputs/partial-basic.json \
  --output runtime_outputs/modeling/partial-basic.proposal.json
kg-mnp proposal validate \
  --input examples/modeling/expected-proposals/partial-basic.proposal.json
```

Legacy 边界与显式运行方式见
[`examples/eligibility-use-case/README.md`](examples/eligibility-use-case/README.md)。

版本化的 `demo_outputs/` 是既有研究快照；本地生成物必须写入已忽略的
`runtime_outputs/`。

## 工程记录

- Stage 04 Modeling Contracts 与 Proposal Generation：
  [`docs/migration/stage-04-modeling-contracts.md`](docs/migration/stage-04-modeling-contracts.md)
- Stage 04 合同说明：
  [`docs/modeling/modeling-contracts.md`](docs/modeling/modeling-contracts.md)
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
