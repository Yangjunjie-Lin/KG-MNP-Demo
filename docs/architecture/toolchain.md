# 工具链架构与权威边界

这里描述源码中的逻辑模块，不把模块画成尚不存在的独立微服务。运行入口是同源 API 与 Worker；二者复用同一 ApplicationService 和语义内核。

## 1. 总体层次

```mermaid
flowchart TD
  workbench["中文工作台"] -->|"资源请求"| api["FastAPI"]
  clients["服务 CLI 与 HTTP SDK"] -->|"相同请求契约"| api
  api -->|"认证后的请求"| service["ApplicationService"]
  service -->|"重验身份与权限"| identity[("Token 与 Session")]
  service -->|"持久化任务"| jobs[("JobStore")]
  jobs -->|"租约与 fencing"| worker["Worker"]
  worker -->|"调用实际能力"| kernel["接入、建模、编译、生命周期"]
  kernel -->|"隔离计算结果"| commit["原子权威发布"]
  commit -->|"工件与提交回执"| workspace[("Workspace 与 Registry")]
```

服务层负责身份、资源归属、类型化请求和执行上下文；内核负责实际领域无关操作。客户端不能以 reviewer_roles、approved 或任意服务器路径替代服务器权威。GraphDB 不在本地主链路的必需依赖中。

实现：`src/kg_mnp/api/app.py`、`services/facade.py`、`jobs/store.py`、`jobs/worker.py`、`services/execution.py`。

## 2. 数据、建模、审核与编译工件流

```mermaid
flowchart TD
  source["Source 与 Blob"] -->|"已校验字节"| ingestion["解析与规范化"]
  ingestion -->|"定位与转换记录"| kgir["KG-IR 与 Evidence"]
  kgir -->|"已验证数据引用"| bundle["Scope 与 CQ 输入包"]
  baseline["锁定基线与术语"] -->|"模型基础"| bundle
  bundle -->|"Provider 请求"| proposal["建模候选"]
  proposal -->|"证据与依赖"| review["逐项人工审核"]
  review -->|"动作重放与确认"| confirmed["Confirmed Package"]
  confirmed -->|"不可省略的输入"| compiler["确定性编译"]
  compiler -->|"实际工具结果"| validation["OWL、SHACL、CQ、Provenance"]
  validation -->|"全部必需门通过"| packageOut["Ontology Package"]
```

Provider 输出不是批准。Recorded Output 的 Prompt / Response 来自上传 Source 的真实字节摘要，不冒充在线模型。修改候选产生新 revision；未批准、被拒绝依赖和未解决阻断不能进入确认包。

编译计划绑定确认包、编译器快照和明确 Query / Oracle。CQ 的结构覆盖与执行验证分别记录；空 Oracle 不能变成通过。

实现：`ingestion/`、`modeling/control_plane/`、`semantic_kernel/`；应用适配：`services/sources.py`、`services/modeling.py`、`services/compilation.py`。

## 3. Package、Release 与 Pointer 是不同对象

```mermaid
flowchart TD
  packageOut["VALIDATED_UNPUBLISHED"] -->|"验证并导入"| registered["IMPORTED_VERIFIED"]
  registered -->|"候选与人工审核"| released["RELEASED"]
  released -->|"明确目标版本"| intent["环境提案与审核"]
  intent -->|"Generation 与 Hash CAS"| pointer["CONTROL_PLANE_SELECTED"]
  pointer -.->|"不能证明部署"| external["外部部署单独观测"]
```

这不是同一对象的自动状态升级。Release 引用不可变 Package；环境 Pointer 引用 Release。回滚只能指向已成功激活的明确历史目标，不能用清空 Pointer 代替。

后续 Release 必须闭合实际语义 Diff、版本兼容、Impact 和 Regression。消费者查询调用隔离只读执行器；新增消费者契约不能被旧回归报告遗漏。审核按每人最新决定重放，撤回的批准不累计人数。

激活前重新检查 Package / Release / Attestation 文件摘要，并比较提案自身的基准 Pointer、调用方期望值和当前权威。指针变化不会修改 Package 或 Release。

实现：`lifecycle/`、`services/lifecycle.py`、`integrations/object_query.py`。

## 4. 领域包与通用核心

```mermaid
flowchart TD
  pack["Domain Pack Manifest 与 Lock"] -->|"精确版本与摘要"| project["Project Lock"]
  project -->|"本体与术语资产"| baseline["基线复用"]
  project -->|"声明式映射"| mappings["候选生成"]
  project -->|"SHACL 字节"| shapes["约束验证"]
  project -->|"查询与 Oracle"| questions["CQ 执行"]
  baseline -->|"建模依据"| core["同一通用内核"]
  mappings -->|"待审候选"| core
  shapes -->|"实际约束结果"| core
  questions -->|"实际查询结果"| core
  core -->|"领域无关工件"| result["可验证本体包"]
```

领域差异保存在数据、IRI、约束、映射和查询中，不通过核心或前端的 Pack ID 分支实现。Minimal / MNP 资产保持；Forestry 0.2.0 是明确标注 EXPERIMENTAL 的合成示例，不代表实地效果。

## 提交与恢复

写操作在完整隔离 Workspace 中计算。正式发布采用固定锁序：凭证元数据锁 → JobStore fencing 事务 → 项目元数据锁；同一次原子项目目录表替换发布新工件根和提交回执。

计算前、提交前均验证权限和输入；旧 Worker 不能越过新 fencing token。提交后丢失 Job 完成回执，可通过实际工件摘要和提交回执恢复。无回执且租约过期的本地任务可经明确授权重试；未知外部副作用保留 RECOVERY_REQUIRED。

这是本地复制工作区方案，不是分布式事务或外部 exactly-once 证明。完整发行判定仍以固定修订的验收记录为准。

## 编译器与契约版本

当前编译器 0.5.1 与 API v1、领域包版本和工具链发行版本独立管理。编译器快照和策略使用新增 1.1.0 契约；原 1.0.0 契约仍逐字节保留用于读取旧包。策略约束、审核要求和原 Domain Pack 内容没有为通过示例而降低。

快照记录真实工具链版本、编译器版本、实现文件摘要和依赖环境；源码或环境变化产生不同快照，旧编译计划不能被当作当前计划复用。0.5.0 的真实合成 Package 已冻结为只读兼容样本，其固定 SHA 由独立测试保护，不通过修改包后重算 Hash 来实现兼容。

## 语义含义与工具职责

当前业务资料入口是 Source → Evidence-bound KG-IR；历史 CleanedPartialData 不是当前通用接入契约。Schema 的 $id 是契约身份，不是领域术语、实例或命名图 IRI。已有契约不能原地扩宽含义；新增版本必须保留旧字节和显式读取边界。

ModelingProposal 只包含待审核候选。只有明确人工审核闭合的 ConfirmedModelingPackage / Confirmed Modeling Package 才能进入正式编译。Provider 分数和一致意见只用于排序，不是校准后的真值概率，也不能用于自动批准。

建模证据解释为什么引入类、属性、映射或约束；事实证据支持具体 ABox 断言。两者都不能仅凭 Hash 证明来源内容真实。显式、推断、候选、拒绝和仅供审核的数据应分开；推断事实不得伪造原始字段证据。缺失不等于否定，未知不等于不存在，不能为图连通而编造关系，也不能由单个字段名自动生成正式 TBox。

OWL 的 Domain/Range 是推断公理，不是数据库列类型检查。SHACL 是针对实际执行约束的数据验证；SHACL violation 不等于 OWL inconsistency。默认实例填充不得绕过 Scope 和审核修改 TBox。

Protégé、GraphDB 与 WebVOWL 不是独立的本体编辑权威。发现问题后必须更新候选与审核输入、重新确认和编译；不能把工具内编辑或布局直接覆盖正式产物。LLM 必须停留在提案边界，不能 auto-confirm 或自动修复后发布。

Canonical NT/NQ 是语义摘要依据，TTL/TriG 是可读且需往返等价的视图。基线空节点的结构确定化使用本工具链的 RDF Canonical Profile，不声称获得 URDNA2015 认证。当前提交机制也不证明任意文件系统断电恢复或分布式 exactly-once。

安装的 Python Plugin 是显式受信任代码，不是 OS 沙箱；发现阶段只读取元数据，不能自动导入第三方实现。源码外使用明确的本地 Domain Pack 根；不自动解析远程本体或下载模型。
