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
以及 OWL 2 DL 一致性检查。ROBOT 是固定版本的命令行封装，HermiT 是由它调用的
OWL 推理器；二者的版本在正式证明中分别记录。尚未实施 Modeling Proposal
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
make verify-robot-checksum
make reasoner-check
make verify-reasoner-run
make verify-reasoner-report
make verify-no-runtime-legacy-terms
make verify-stage-03
```

`verify-stage-03` 是 CI 和本地收尾的完整入口，并严格按以下顺序执行：Stage 03
core（其中包含 Stage 01/02 回归）、ROBOT 校验、HermiT 实际运行、runtime run
验证、正式报告验证、运行态旧术语扫描。默认 `reasoner-check` 只写已忽略的
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
