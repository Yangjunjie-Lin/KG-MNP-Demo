# AGENTS.md

2026-09-18 按 01–17 对齐，最新字段的唯一详细入口为 `docs/ontology/HANDOFF_CONTRACT.md`，
对应表在 `requirement_traceability.md`。本轮参考 develop@9f6c036 不是强制回退目标。
verdict 已确认为 pass/fail；fail 必须有 annotations 数组但没有新增最少条数，pass 可省略。
violations/corrected_answer 原样贯通；批次清单仅 batch_id/files 必填。
空批次、仅评价批次、可信历史导出引用复用原 Worker/CAS；本地登记不是对方已收集。
串行 call_id 可选，未知非空 event 只告警；并行生产提交必须有 ID。
评价逐行隔离，不能吞有效行；可选 context 不成为第 18 项，也不替代内部真实性检查。
`task_end.answer` 记录实际服务结果，隐私过滤明确标记；旧摘要日志不反推正文。
冻结验证入口增加 `--input-archive`，只接入附件 upstream，不能将说明/答案整包送入模型。
用户后续已明确确认“名称更新版”作为本轮“精简版”参考，不再列为待补附件。
身份锁定在 `docs/ontology/references/handoff-17.reference.json`，原字节副本为
`handoff-17-20260918.original.zip`；实际 SHA 为 be5d0c70…，不是旧 Prompt 的 bbcf5bbf…。
确认参考用途不等于两个历史 ZIP 字节相同，也不追改旧回执。当前续办基线 d2dbd514；继续前仍先核实 HEAD。

2026-09-17 新增 `docs/ontology/AGENT_STEP_AUDIT.md`。PlanningAgent 只是 RuleAgent 别名；
不要添加第三个计算角色。逐步审计不替代 JobStore/session/CAS，不给 Agent 审批工具。
默认仅元数据，正文必须显式启用并按权限记录/下载；旧处理前内容缺失不可补造。

本文件供后续开发 Agent 使用，作用于本仓库；更细目录指令应一并读取。本文件不代替本轮用户要求，不赋予运行时 Agent 额外权限。

## 先读什么

处理本体建模与交接任务时，先读根 README、`docs/ontology/ONTOLOGY_MODULE.md`、`docs/ontology/HANDOFF_CONTRACT.md`、`docs/ontology/IMPLEMENTATION_AUDIT.md`，再读本轮任务 Prompt 与对应源码。

协议原件在 `docs/ontology/references/`；当前代码与历史证据在 `docs/upgrade/` 及需求追踪。先确认当前 HEAD、分支和脏工作树；2026-09-16 的审查基线是 develop@194e091，不应把静态基线当成永远最新代码。

## 模块责任

本体模块承接规则化输入，负责 S1—S5、结果交接与自身运行轨迹。数据处理不需预造本体审批/编译工件；演进组负责其自己的收集、训练、优化与更新。本轮交接任务不自动授权重建演进平台或业务 Action 系统。

保留当前两个角色：RuleAgent 执行 S1/S2/S4，TaskExecutionAgent 执行 S3/S5；审批仍归授权审核者。新日志或导出器不能成为另一套 session/candidate/review/version 真相来源。

## 实现原则

复用 Source/Batch/KG-IR/Evidence、modeling.session、共享语义编译、原生 .kgop、权限、Worker、CAS/租约、STALE 和 Registry/Release。新增适配器应薄且可单测，不能为了导出而另写一套 ID、事实生成或审批逻辑。

同时检查 `five_stage/agents.py`、`compatible.py`、`tools.py` 和 `delivery/` 的真实边界，不只根据 README 猜实现状态。研究内核的能力不自动代表生产路径具备同等能力。

## 格式与真实性

区分会议样例、项目正式交换视图、原生 .kgop、原 v3、演进轨迹 v2。不能改扩展名或 schema_version 冒充兼容；原 v3 Schema、稳定 IRI、签名和历史摘要不随意改动。

工具哈希摘要不是完整消息轨迹；旧哈希不能反推真实 prompt。记录实际发生的请求、公开响应和工具动作，保留失败、重试和取消。录制/Mock/合成验证须明确标注，不能称为 LIVE 或正式人工评价。

不伪造原生 ID、调用、审核、标准答案、成功状态或 token 用量。程序调用成功、语义验证通过、审核通过、已导出、对方已收集、已发布分别记录。

## 演进契约重点

外部 run_id 需符合文件名规则，保留与原生含冒号 ID 的映射。turn 为实际模型调用轮次，不是阶段编号；call_id 每个调用唯一，结果复用对应 ID，支持并发乱序。

严格 v2 未定义首次模型调用前/纯程序步骤的 turn。不得伪造模型事件或默许 turn=0；保留真实本地记录并准确报告不兼容。仅阻断受影响出口，其余独立能力继续实现。

六类 harness 哈希来自真实冻结资源。人工运行评价与本体 review.json 分开。对方的政务许可违规码不强套到本体问题；未确认扩展单独记录，不冒充对方规则。

## 权限与数据

原 AgentRun 保持低敏摘要审计；完整内容日志必须独立、可配置、受权限控制。不得泄露 API key、Authorization、Cookie、秘密 URL、供应商私有 reasoning 或非授权资料。

开发 Agent 可读取明确的合成夹具实现测试；运行时生成/修复 Agent 不能访问 acceptance_private、tests 中的预期答案、scoring/gold 或含答案的 references 整包、审查报告及 evidence 检查记录。目录分类不是沙箱证明，必须测试实际不可读。脱敏/删节的导出不能冒称原字节完整。

## 验证与文档

先新模块单测，再现有相关回归；模型网络边界可明确用 Mock/录制，但不得用它们替代真实核心服务的集成验证。缺依赖、缺授权、缺接收器分别记 NOT_RUN/BLOCKED，不为了全绿放宽语义门、鉴权、预算或旧测试。

每次接口/产物变化同步 README、模块说明、交接契约及 requirement_traceability.md；保存原协议和历史失败证据。交付实际变更、执行命令、产物、分项结果和剩余限制，不止给建议。

没有本轮授权不推送/合并/发布、不删除历史分支或资料、不执行付费实验或真实业务动作。不把已生成文档写成已实现代码，不把本地导出写成对方已经收集。

## 2026-09-16 增量实现索引

新交换格式与验证在 `modeling/delivery/handoff.py` / `handoff.schema.json`；输入适配在
`meeting_input.py`，轨迹在 `trace.py` / `evolution.py`，总封面在 `cover.py`。
服务入口统一为 `services/handoff.py`，受控日志在 `services/ontology_traces.py`，
不将内容日志放入 AgentRun 公共摘要。CLI `export-handoff` 下载已提交服务快照。

继续任务时先读 `docs/ontology/IMPLEMENTATION_STATUS.md` 的真实结果和限制。
使用完整验证器时，无明确付费授权必须加 `--skip-model-probe`；默认旧验证器末尾有 LIVE 推理探测。
隔离研究内核的 canary 成功不代表整个生产 Worker 已 OS 沙箱化，不能扩大结论。

## 阶段验收收口

979128e 之后的 negative_case_plan、1.1 交接/祖先关联、阶段 ZIP 与验证规则见
`docs/ontology/STAGE_CLOSEOUT.md`。负例计划属于独立验收输入，不给生成/修复流程。
`modeling.handoff.check` 是程序验收，不是审批；PASS 表示预先规定的拒绝被实际检出。
`verify_stage_handoff.py` 冻结后不得再修改实现、配置、测试或被冻结文档；结论只写独立输出。
若必须修复，保留失败回执，新目录重新冻结。历史卫生 FAIL 不删测试、不加 skip/白名单、不过滤隐藏。
独立包自洽不等于授权；按契约使用服务回执/包外可信 SHA，不能信任 ZIP 自报“已批准”。
