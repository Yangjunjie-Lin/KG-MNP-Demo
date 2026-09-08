# 历史迁移与当前边界

历史原件由 Git 与不可移动的 kg-mnp-pre-final-consolidation-p08 基线 Tag 保留，不复制到 archive/legacy 目录。
固定 P8 是 9da17d126cb37166ff06084080770108da20afbe；更早的 kg-mnp-phase06-baseline-2026-08-30 指向 e45da340267de8d4b7b3a54177822aa641e3a601。

## 过去的问题不能改写成通过

P7 曾给出 GO_CORE_WITH_INTEGRATION_BLOCKERS，同时明确未完成最终 aggregate。P8 进一步发现声明不等于服务接通：53 项操作中 12 项已测试、2 项未充分验证、39 项只有声明；真实 HTTP 链路止于上传 404 和 Source 501。最终判定是 NO_GO_BACKEND_NOT_READY，无浏览器会话、统一 UI 或 Forestry 工作流完成证据。

P8 完整尝试为 1490 通过、7 失败、9 跳过；后续修复形成 1510 个节点的混合修订并集（最新结果 1501 通过、9 跳过），但不是单一最终修订全量通过。原中断、失败和平台未执行不转换成 PASS。旧报告可通过 git show kg-mnp-pre-final-consolidation-p08:docs/verification/prompt-08-final-report.md 复查。

当前实现已接通真实上传、KG-IR/Evidence、建模审核编译、注册发布与受控回滚。G1–G4 的必需替代流程通过后才开始退役旧入口。最新增量、已知失败和最终验收状态以[验收摘要](../verification/final-verification.json)和[逐项台账](final-retirement-ledger.json)为准；此迁移说明不是发行认证。

## 保留与替代

- 保留原 115 公共 Schema 的字节与 $id；编译器 0.5.1 使用新增快照/策略 1.1.0 契约。旧包不会通过改写内容、重算 Hash 或假装旧编译快照未变来获得兼容。
- Minimal 与 MNP 原 84 资产保持。Forestry 0.1.0 的 PLANNED 空包仅作为历史版本；唯一授权升级是 0.2.0 EXPERIMENTAL 的合成示例。请求不可用的 0.1.0 明确失败，不静默替换。
- 新 Catalog 会使旧 Project Lock 陈旧；不自动赋予旧无主记录所有权，不覆盖旧 Workspace 或把新包版本重新绑定给历史工件。
- 已删除三套旧 UI 和独立旧 HTTP/CLI 启动器；同源会话、CSRF、严格 JSON、路径隔离、角色/quorum、CAS 与恢复由当前 API 测试保护。旧 URL 返回 410。客户端自报身份和旧 zero Prompt digest 不作为兼容保证。
- 原来只断言阶段标题、目录空白、全树冻结或旧命令拼写的门迁移为能力检查。篡改、权限、证据、并发与历史包读取保证不得因清理而丢失；旧 nodeid 与替代位置逐项记账。
- 历史 eligibility 业务不是当前产品目标；领域规则、术语、法律来源和原始资产不能随旧入口一起丢弃。保留的历史模块限于实际验包所需的只读解析、纯重建与规则评估；它们不提供第二套可写运行控制面。
- 根 eligibility 流水线、独立 showcase HTML、旧工作台转发器，以及旧编译/GraphDB/发布/WebVOWL/工作台的写盘入口已退役。原有 MNP 规则、证据、双重 SHACL 和版本时间断言改为直接内存评估；旧包校验保留只读字节重建，不再附带 force 覆盖接口。冻结 MNP 资产内的历史 README 可能仍引用旧命令：它是资产原文，不是当前启动指南；当前操作以根 README 为准。
- 当前 Workspace 事务共享目录提交步骤，使用独占暂存目录；失败不清理不属于本次事务的目标，也不删除此前待检查的暂存数据。Worker 的权限重验、租约 fencing、项目 CAS 与提交回执仍由服务层统一控制，文件改名重试不等于 exactly-once。

## 长期决策

旧状态控制器已实际退役：GovernanceWorkspaceStore、ActivationStateStore、ActivationController 和旧解析/部署启动器不再存在。历史激活数据通过独立的只读事件重放校验，并用退役前保存的原始记录检验兼容；不会在读报告时新建旧数据库或执行控制器。GraphDB 使用当前已审核集成计划和真实显式/完整导出比对，旧自动容器/许可证写入流程已删除。旧 WebVOWL 页面、服务器与代理已删除，仅保留显式、离线、只读挂载的文件转换工具。

一次性的 MNP 术语/CQ/IRI/案例重写脚本、旧 ingestion CLI smoke 以及会重写实施台账的 consolidation_audit 已退役；领域资产原字节保持，实际保障由当前语义、资产锁、历史兼容、上传解析和服务传输等价测试接替。只删除指向这些已退役脚本的精确旧术语豁免，不扩大扫描例外。仍保留只读本体检查、基线重建校验和带确定性 --check 的合成解析样本生成器；本体检查复用现有命名空间，不再保留阶段常量副本。

早期 Stage01 曾删除旧 Neo4j/fullstack 平台，把携号转网资格评估降为领域示例；这不是永久禁止 Node、API 或数据库。当前中文工作台和持久化服务由后续明确需求建立，不能继续引用早期“Python-only”阶段说明作为现行架构。该次操作日志由固定 Git 历史保留。

原阶段文档中的长期原则已归并到[当前架构](../architecture/toolchain.md)、[安全边界](../security/authority-boundaries.md)和[研究证据对照](../research/implementation-evidence.md)：观察/提案/确认/编译分离、Core 绑定身份与来源、离线精确依赖、不可变包、真实 Oracle、独立 Release/Pointer 与外部部署观测。

有持续价值的 ADR 保留其历史背景，并标注被当前契约或入口迁移替代的条款。阶段报告和一次性失败计数不是永久产品文档；移除它们不改变原历史结果，也不移除法律授权、第三方声明或领域来源义务。
