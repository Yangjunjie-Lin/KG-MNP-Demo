# KG-MNP

## Ontology and Knowledge Graph Foundation

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
Deterministic Formal Semantic Compiler
        ↓
OWL / RDF Dataset / SHACL / ABox / Provenance / Review Artifacts
        ↓
Verified GraphDB Knowledge Graph
        ↓
WebVOWL TBox Visualization
        ↓
EndToEndPublicationPackage
```

## 阶段状态

| Stage | Status |
|---|---|
| Stage 01 Repository Baseline | PASS |
| Stage 02 Semantic Governance | PASS |
| Stage 03 Formal Ontology Release | PASS |
| Stage 04 Modeling Contracts and Proposal Generation | PASS |
| Stage 05 Human Review and Confirmed Modeling Package | PASS |
| Stage 06 Deterministic Formal Semantic Compilation | PASS |
| Stage 07 GraphDB Assembly and Import | PASS |
| Stage 08 WebVOWL and End-to-End Publication | PASS |

**Foundation pipeline status = COMPLETE through Stage 08.**

This completes the ontology and knowledge graph foundation.

## Application Layer

### Phase 01 — Read-Only Semantic Query and Traceability Layer

**Application Phase 01 status = PASS.**

The Application API is a read-only projection layer over a verified GraphDB
repository and its `EndToEndPublicationPackage` / `PublicationAttestation`. It is
not a semantic authority, decision engine, ontology authority, review authority,
GraphDB authority, eligibility engine, or source of new business facts.

The runtime starts only after the publication package is deterministically
reconstructed by the frozen Stage 08 authority validator for an explicit,
controlled publication scenario; the `PUBLICATION_VERIFIED` attestation,
publication semantic hash, compilation lineage, GraphDB publication lineage,
named-graph set, and repository id must all match. Startup then exports the live
explicit dataset through the fixed `infer=false` read-only endpoint and compares
the frozen Stage 07 semantic hash with the publication-bound GraphDB semantic
hash. Every result carries `publication_id`, `publication_semantic_hash`, and a
deterministic `result_semantic_hash`; timing remains isolated in
`runtime_metadata` and is excluded from that hash.

Phase 01 contains:

- `config/application/query-registry-1.0.0.yaml`: the only executable query registry;
- `queries/application/`: 12 versioned SELECT templates covering Foundation metadata,
  ontology, business facts, provenance, review, source, evidence, and cross-trace;
- an independent `ReadOnlyGraphDBClient` with only health, repository metadata,
  explicit `infer=false` N-Quads snapshot, SELECT, and ASK capabilities (Phase 01
  registers no CONSTRUCT query);
- exact RDF-term projection preserving IRI/literal identity, lexical form,
  datatype, and language;
- exact fact-level `owl:Axiom` traceability to candidate/effective candidate,
  `ReviewDecision`, reviewer, evidence, source, compilation, graph, and publication;
- a local-only FastAPI runtime pinned to `fastapi==0.115.0` and
  `uvicorn==0.30.6`, with no sessions, cookies, accounts, ORM, background jobs,
  arbitrary SPARQL endpoint, or write route.

GraphDB access is read only. SPARQL UPDATE, `SERVICE`, Graph Store writes,
repository creation/deletion, and arbitrary query passthrough are rejected before
transport. The low-level SPARQL POST transport independently revalidates the body
as SELECT or ASK, so direct `application/sparql-query` UPDATE attempts also fail
closed. The HTTP server accepts only `127.0.0.1`; `0.0.0.0` is forbidden.
Rejected or deferred candidates are absent from business queries while their
review-audit history remains available through the registered review trace.

```bash
kg-mnp application query list
kg-mnp application query describe provenance.fact
kg-mnp application publication verify \
  --publication-package runtime_outputs/publication/full-confirmation \
  --attestation runtime_reports/publication/<publication-hash>/publication-attestation.json \
  --publication-scenario full-confirmation
kg-mnp application runtime check \
  --publication-package runtime_outputs/publication/full-confirmation \
  --attestation runtime_reports/publication/<publication-hash>/publication-attestation.json \
  --publication-scenario full-confirmation
kg-mnp application serve \
  --publication-package runtime_outputs/publication/full-confirmation \
  --attestation runtime_reports/publication/<publication-hash>/publication-attestation.json \
  --publication-scenario full-confirmation
make verify-application-phase-01-offline
# Requires the same legal external GraphDB license as Stage 07/08:
make verify-application-phase-01
```

Phase 01 adds no Stage 09, Agent, LLM, GraphRAG, embedding, vector database,
natural-language-to-SPARQL, MCP, prompt system, reasoning chain, business frontend,
or eligibility decision authority.

### Stage 08 authority boundary

- **ConfirmedModelingPackage** is the semantic decision authority.
- **OWL/SHACL** is the formal semantic authority.
- **GraphDB** carries the full verified TBox + ABox + Provenance + Review knowledge graph.
- **WebVOWL** visualizes the ontology TBox only. WebVOWL JSON is a presentation projection and is not a semantic authority.

The WebVOWL and OWL2VOWL sources are fetched at exact audited commits into the ignored
`upstream-source/` directory. Conversion reads only the Stage 03 root ontology and frozen local runtime
dependencies; remote IRI/import resolution is forbidden. WebVOWL's legacy npm graph is installed only by
`npm ci` from the tracked shrinkwrap (SHA-256
`74c5094525121337d6b71d0862ec9543a0356e536b00fe67b45f03d031f0fdda`). The formal normalized VOWL
JSON contains no business instances, review/provenance records, GraphDB runtime metadata, license data, or
browser artifacts.

```bash
kg-mnp webvowl package build --output-dir runtime_outputs/webvowl/package
kg-mnp webvowl package validate --package-dir runtime_outputs/webvowl/package
kg-mnp publication build --scenario full-confirmation --output-dir runtime_outputs/publication/full-confirmation
kg-mnp publication validate --scenario full-confirmation --package-dir runtime_outputs/publication/full-confirmation
make verify-stage-08-offline
# Requires an external GraphDB license, Docker, Playwright 1.49.1, and
# Chromium 131.0.6778.33 (revision 1148):
make verify-stage-08
```

Stage 03 已完成正式 IRI 迁移、模块归属、Protégé catalog、SHACL profile 拆分，
以及 OWL 2 DL 一致性检查。Stage 04 已增加离线 Modeling Contract、冻结的
版本化依赖、稳定 ID、语义验证器和确定性 ModelingProposal Generator。Stage 05
已增加冻结 Review Policy、显式人工 Review Action、文件式审核工作流、以及确定性
`ConfirmedModelingPackage` Builder。Stage 06 增加了 authority-gated、确定性的正式
OWL ABox、RDF Dataset、建模来源图、审核审计图、SHACL Validation Report、OWL 2 DL
Consistency Report 和 Compilation Manifest。ROBOT 是固定版本的命令行封装，HermiT 是由
它调用的 OWL 推理器；二者的版本在正式证明中分别记录。Stage 07 已使用合法运行时 FREE
license 在 GraphDB 11.4.2 上完成真实导入：13 个 named graphs 完整保留，physical default graph
为空，repository ruleset 为 `empty`，无 inferred statements，显式导出与输入 Dataset 语义相等，
并已验证 Rejected/Deferred exact assertion isolation。Stage 08 已完成冻结上游、TBox-only 投影、
coverage / representation-loss / ABox leakage 校验和四场景发布包；真实 Chromium 浏览器在
127.0.0.1:8080 隔离 runtime 上完成节点/边、恶意标签与外部网络阻断验证，并生成最终
`PUBLICATION_VERIFIED` attestation。

Stage 03 收尾还将旧资格判断 JSON Schema 从根 `schemas/` 移至
`examples/eligibility-use-case/schemas/`，并把 `$id` 迁移到项目稳定的 HTTPS
Schema namespace。该 legacy eligibility contract 与中央 `CleanedPartialData`
contract 不同，且不会被 Modeling Pipeline 当作输入适配器。

## 当前边界

- 当前没有产品或业务前端，也没有 Vite/Nginx application runtime。Node 12 仅存在于固定摘要的
  WebVOWL 构建镜像及固定目的地 loopback relay；Playwright 1.49.1 / Chromium 131.0.6778.33
  （revision 1148）仅用于 Stage 08 live 浏览器验收，不进入 Python core、语义权威或产品运行路径。
- 当前不以携号转网资格判断为中央任务；九个 legacy 案例作为 eligibility profile 回归资产保留。
- Application Phase 01 提供仅绑定 `127.0.0.1` 的 read-only HTTP projection；仍没有 SQLite 执行历史、会话、用户、cookie 或写入服务。
- 当前可以从 CleanedPartialData 生成确定性的、仅供审核的 ModelingProposal。
- 当前可以人工审核 Proposal，并生成 `ReviewDecisionLog` 与 `ConfirmedModelingPackage`。
- 当前没有默认决定、批量确认、自动确认或 LLM Reviewer。
- 当前可以从完整权威输入编译正式 OWL ABox、RDF Dataset、Provenance 与 Review Audit。
- 当前可以执行冻结 SHACL 验证和 Package 级 OWL 2 DL consistency check。
- 当前不能只从 Proposal 编译；BLOCKED ConfirmedModelingPackage 会被拒绝。
- Stage 07 已加入确定性的 runtime TBox/ABox 装配、GraphDB repository 配置、闭包导入包、
  SPARQL/Graph Store 验证套件、独立包重建校验器、受限 client/importer/verifier、运行时
  attestation 以及 Docker 集成 harness，并已在 GraphDB 11.4.2 上完成 licensed live verification。
  后续重跑若未提供合法外部 license，live 目标仍必须明确失败，不能用离线检查替代。
- Stage 08 只增加隔离的 upstream WebVOWL 可视化 runtime、浏览器验证 harness 与 publication CLI；
  未增加 application business frontend、eligibility decision UI、GraphRAG、LLM、Agent、production API、Neo4j 或 Stage 09。
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
| `src/kg_mnp_demo/compilation/` | Stage 06 正式语义编译、canonical RDF、SHACL、OWL consistency 与 validator |
| `config/compilation/` | 冻结 Compiler Policy 与 SHACL profile bundle |
| `examples/compilation/` | Stage 06 golden artifact layout 与 invalid authority examples |
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
make verify-stage-06
make verify-stage-07
make verify-stage-08-offline
make verify-stage-08
make verify-application-contracts
make verify-application-query-registry
make verify-application-readonly
make verify-application-traceability
make verify-application-security
make verify-application-http
make verify-application-authority-binding
make verify-application-live-binding
make verify-application-rehash-attacks
make verify-application-foundation-freeze
make verify-application-phase-01-offline
make verify-application-phase-01
```

`verify-stage-06` 是 CI 和本地收尾的完整入口；它先完整执行 `verify-stage-05`，
再执行 Stage 06 Contracts、Policy、Candidate Mapping、Graph Separation、Canonical
RDF、SHACL、OWL consistency、Manifest/Determinism、Security、CLI 与 Stage 06 边界门禁。
`verify-stage-05` 仍完整执行 `verify-stage-04`，
再依次执行 Review Contracts、Policy、Workflow、Determinism、Confirmed Package、
Readiness、Security（fail-closed finalize / independent package reconstruction）、
CLI 与 Stage 05 边界门禁。`review finalize` 执行完整语义验证；`package validate`
从权威输入独立重派生 Expected Package，自洽 self-hash 不是授权证明。`verify-stage-03` 内部严格按以下顺序执行：Stage 03
core（其中包含 Stage 01/02 回归）、Schema Identifier 门禁、ROBOT 校验、HermiT 实际运行、runtime run
验证、正式报告验证、运行态旧术语扫描。Schema Identifier 门禁只解析本地
`*.schema.json` 与 namespace 配置，不访问 `$id`、不下载远程 Schema。默认 `reasoner-check` 只写已忽略的
`runtime_reports/ontology/`，不得改动受版本控制文件。

`verify-stage-07` 会重建四个 Stage 06 authority 场景的 GraphDB 导入包，并运行离线
契约、策略、装配、闭包包重建、安全和 CLI 检查；最后启动固定的
`ontotext/graphdb:11.4.2` 镜像执行真实 repository 创建、N-Quads 导入、查询、导出
和删除。GraphDB 11.4.2 license 必须只通过运行时环境提供，例如：

```bash
GRAPHDB_LICENSE_FILE=/secure/path/graphdb.license make verify-graphdb-live
```

`GRAPHDB_LICENSE_FILE` 指向的文件、`GRAPHDB_LICENSE_CONTENT` 的内容或严格编码的
`GRAPHDB_LICENSE_B64` 不会写入版本库，
也不会进入镜像构建上下文。没有外部 license 时，live 目标会明确失败并清理它创建的
容器、网络和 volume。

Stage 07 的闭合验证已在 GraphDB 11.4.2 FREE edition 上完成。验证确认 13 个 named graphs、
2332 个 quads、physical default graph statement count 为 0、repository ruleset 为 `empty`、
inferred statement count 为 0；显式与完整导出的 semantic hash 均与导入 Dataset 相等，
Rejected/Deferred exact assertion isolation 以及 fail-closed 攻击回归均通过。

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

Python core 与 PR 离线门禁不依赖 Node、浏览器或外部 GraphDB/WebVOWL；完整 reasoner
只需要 Java 17+ 和固定校验的 ROBOT。受信任的 `main` push 与 `workflow_dispatch` 另行执行
licensed GraphDB integration，许可证只从 GitHub encrypted secret 注入；成功后上传严格闭包、
经过大小写不敏感 JSON/文件敏感信息扫描的 Stage 07 Attestation artifact，以及
`stage08-publication-attestation-<commit SHA>` Stage 08 publication artifact，以及仅含
`application-attestation.json`、query registry/golden/security summary 和 GraphDB before/after
hash 的 `application-phase01-attestation-<commit SHA>` artifact。Application artifact 在上传前会
独立重新校验五文件 closed set、publication authority reconstruction、expected/before/after
GraphDB semantic hash 三者相等、query registry hash，以及 golden/mutation/live-tamper count
闭合，不只信任 attestation status。Stage 08/Application live job 的
Node/Playwright 环境与 Python core 隔离，并固定 Playwright/Chromium 版本；所有 CI job 最后均断言
`git diff` 与 `git status --short` 为空，确保 runtime 产物不会污染正式仓库。

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
kg-mnp compile build \
  --input examples/modeling/inputs/partial-basic.json \
  --proposal examples/modeling/expected-proposals/partial-basic.proposal.json \
  --decision-log examples/review/expected-logs/full-confirmation.log.json \
  --package examples/review/expected-packages/full-confirmation.package.json \
  --output-dir runtime_outputs/compilation/full-confirmation
kg-mnp compile validate \
  --input examples/modeling/inputs/partial-basic.json \
  --proposal examples/modeling/expected-proposals/partial-basic.proposal.json \
  --decision-log examples/review/expected-logs/full-confirmation.log.json \
  --package examples/review/expected-packages/full-confirmation.package.json \
  --compilation-dir runtime_outputs/compilation/full-confirmation
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
