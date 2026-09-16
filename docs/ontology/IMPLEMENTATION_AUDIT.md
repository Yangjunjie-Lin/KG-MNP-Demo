# 交接改造前审查记录

日期：2026-09-16。性质：附件实际检查 + GitHub 固定提交关键文件静态审阅，不是完整仓库实跑。

> 下文完整保留附件的改造前审查。当前本地代码实现、实跑结果与未完成项另见
> [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)。不追溯修改原附件检查结论。

## 1. 本次审查范围

输入一为演进组《上游数据对接说明（暂定）》，定义执行记录 v2、人工评价、批次清单与原子投递。输入二为用户现有交接 ZIP，内含会议版 v2.0 上下游样例、README、HTML、Word 和检查脚本。

GitHub 连接已读取当前分支信息：

| 分支 | 本次读取的 HEAD | 关系 |
|---|---|---|
| develop | `194e091d13cabba5833ff1d531f814858ea968ae` | 比 main 多一个提交 |
| main | `adc2a40512f8b029b6c21420b905628c32952d00` | 是上述 develop 提交的父提交 |

新增提交题为 `Implement task-adapted TwoAgentKernelV1 profile`。因此本轮以 develop 为审查基线，不能只根据仓库首页的 main 判断最新实现。

通过 GitHub 连接读取了文档、相关目录树和以下关键源文件。普通 web 页面读取和本地 git clone 不可用，本次没有取得完整可执行工作树，没有运行项目测试；不据此推断全仓库所有文件均已审阅。

## 2. 已确认的关键发现

| 发现 | 直接证据 | 对本次改造的影响 |
|---|---|---|
| 两个角色已经存在 | `five_stage/agents.py` 中 OWNERS、RuleAgent、TaskExecutionAgent | 不重建第二套 Agent 或版本库 |
| 工具审计是摘要型 | AgentRun.call 记录 input_sha256/output_sha256，注释明确不向该审计写来源值、提示词和答案 | 新增独立受控轨迹通道；不能把摘要重命名为完整事件流 |
| 原生运行 ID 不兼容接收文件名 | AgentRun 默认使用 `agent-run:` 前缀 | 新建外部 transport ID 并保留映射，不能修改原生标识 |
| 原生 AgentRun 多为一次服务操作 | execute_routed 每次按请求建立 AgentRun | 以真实作业为运行边界，完整会话用关联表连接，不伪装单一连续运行 |
| 两个模型客户端的记录能力不同 | CompatibleClient.propose 保留部分 request/response、last_public_response；QwenClient.propose 主要返回 hash | 埋点需覆盖两个客户端和真实异常，不能只拿成功返回值 |
| 工具调用外层可包住模型调用 | AgentRun.call 先记录 RUNNING 再执行 action；Qwen 的 health 在模型请求前执行 | 对方未定义首次模型调用前工具 turn 的规则，需显式兼容性处理 |
| 逐文件完整导出不是现有 diagnostic | delivery/native.py 的 analyze_native 返回 BLOCKED_REQUIRED_BOUND_INPUTS；diagnostic_bytes 仅导出三图与缺口说明 | 补充同次运行绑定后再导出 mapping/provenance/review 等，不把 diagnostic 当正式交接 |
| 当前 delivery CLI 命令有限 | cli.py 仅 inspect / preflight-native / export-diagnostic | 新交接命令是待新增接口，文档不能写成现在已经能运行 |
| 新内核是任务适配研究实现 | docs/upgrade/ontology-kernel-v1.md 明确不是全部生产能力，也不是外部质量提升结果 | 不因新增轨迹和文件导出修改研究结论或重新启动付费实验 |

这里“待补”是根据已审阅入口与声明确认的缺口；执行改造时仍需全仓检索可能存在的新适配器，优先复用，不能因为本审查未见就创建重复实现。

## 3. 现有交接包实际检查

本轮本地检查了 3 份 manifest，分别覆盖 13、24、13 个声明条目（含依赖副本，不能相加当独立文件数）；每项文件存在、字节长度及 SHA-256 均匹配。

包内 JSON/JSONL 语法检查无错误；7 个 TTL 文件均能解析（含重复依赖）。下游三图三元组数分别为 ontology 26、instances 7、shapes 33。运行现有 `queries/cq_01.rq` 返回 `https://example.org/ontology/D-01`，与同包冻结预期中的 IRI 一致。

以上是对合成会议样例的有限复核，不是实际语义正确性、完整证据闭包或生产导入导出验收。当前环境无 pySHACL，本轮未执行 SHACL、HermiT、项目后端、浏览器、真实模型、人工审核或演进收集器联调。

原包 `downstream/manifest.json` 自身明确：

- package_kind 为 `MEETING_REFERENCE_EXAMPLE`；输入绑定为 `UNBOUND_EXAMPLE`。
- 原生运行/编译/映射等引用没有真实绑定，native_binding.status 为 `NOT_NATIVE_PACKAGE`。
- validation/review/release 状态为 `PARTIAL_VALIDATION / PENDING_REVIEW / NOT_RELEASED`。
- 整包包含受限验收答案，不能直接作为模型上下文。

不修改以上原始状态，也不把本轮查询复核写成正式批准。检查记录见 `evidence/attachment-check.json`。

## 4. 调整建议的优先级

| 优先级 | 调整 | 可以独立验收的结果 |
|---|---|---|
| P0 | 统一角色责任和格式身份，保留两份原始资料与适配差异 | 模块说明、交接契约、Agent 规则清楚，不再混用“本体审核”和“运行评价” |
| P1 | 固定真实输入/原生工件/会话/版本的绑定，完善结果导出 | 一次真实本地运行可导出可重验的逐文件交接包 |
| P2 | 增加统一受控 trace recorder，接入模型与工具真实边界 | 成功、失败、重试、并发、取消均可追踪；没有从摘要倒造消息 |
| P3 | 实现 v2 状态机校验、外部 ID、harness、manifest 与原子导出 | 可表示的轨迹通过本地协议测试；不可表示的程序步骤明确受阻 |
| P4 | 增加真实评价接口及引用，接入现有 API/Worker/下载界面 | 人工评价绑定正确运行；失败任务不因没有结果包而被丢弃 |
| P5 | 回归、双方收集器联调和文档状态更新 | 分别列出本地导出、实际接收、评价器支持和剩余阻塞项 |

不将 P2/P3 等同于重建演进系统，不实现演进训练器、奖励优化器或自动发布；也不以一个对方协议未决点阻塞其他独立实现。

## 5. 需要保留的协议差异

| 原文涉及处 | 必须保留的差异/未决信息 |
|---|---|
| call_id 同 run 唯一，同时要求结果复用调用 ID | 唯一的是调用实例，不是事件行；本解释应由接收器用例确认 |
| turn 是模型轮次且正整数 | 首次模型前和纯程序运行未定义，不能伪造调用或默认允许 turn=0 |
| 并行必须带 call_id，同时缺失时可降级告警 | 新生产者全部带 ID；兼容读取不能悄悄改变原文级别 |
| fail 必須 annotations，汇总却列为 warning | 新输出满足要求；接收兼容行为仍以对方实现为准 |
| 时间字段允许偏移，实施清单举 +08:00 | 使用明确偏移并确认实际接收格式，不用无时区时间 |
| 人工评价继承未提供 v0 | 完整 verdict 枚举仍需对方 Schema；不要暗自补齐 |
| 示例与违规码偏向许可/法条 | 只证明轨迹协议需求，不证明评价器支持本体输出对象 |
| manifest 可选 | manifest 文件不存在与其声明文件缺失是两个不同情形 |

## 6. 本次文档与未来代码的边界

本次已生成 README 修订稿、专门模块说明、交接契约、AGENTS.md 和可执行改造 Prompt。它们是可合并的文档，不是已经修改远端代码的证明。

未修改 GitHub 分支；未提交、推送、合并或发布；未产生生产轨迹；未执行任何付费模型调用；未将原会议包改造成虚构的真实运行数据。

## 7. 固定来源索引

仓库固定前缀：
`https://github.com/Yangjunjie-Lin/KG-MNP-Demo/blob/194e091d13cabba5833ff1d531f814858ea968ae/`

主要已读文件：

1. `README.md`：项目定位、当前模块、启动/测试说明及明确限制。
2. `docs/upgrade/ontology-io.md`：已读相关章节，区分双 Agent、原生/v3、研究入口和历史状态。
3. `docs/upgrade/ontology-kernel-v1.md`：新内核的 S1—S5、修复、录制重放及边界。
4. `src/zhigou_toolchain/modeling/five_stage/agents.py`：AgentRun、角色、工具白名单、execute_routed。
5. `src/zhigou_toolchain/modeling/five_stage/compatible.py`：CompatibleClient.propose、公开响应、失败与用量处理。
6. `src/zhigou_toolchain/modeling/five_stage/tools.py`：QwenClient、health/propose/_request、检索和引文工具。
7. `src/zhigou_toolchain/modeling/delivery/native.py`：GRAPH_PATHS、analyze_native、diagnostic_bytes。
8. `src/zhigou_toolchain/modeling/delivery/cli.py`：现有三个子命令。

分支关系依据 GitHub branches 和 compare 接口。附件原字节 SHA-256：

| 原件 | SHA-256 |
|---|---|
| 上游数据对接说明（暂定）.md | `a05062507098c4abe19f3106f715a78ad4a1604eb1ef9bd4f281482e3f7fb796` |
| 本体建模_上下游交接文件包.zip | `0535fdfaa29d4bcb4948a43cf955d93e396f17c558eed653054facbc957f27c4` |

本目录 references 保留上述原件的字节副本。源码进展、附件事实与本次设计建议必须分开陈述。
