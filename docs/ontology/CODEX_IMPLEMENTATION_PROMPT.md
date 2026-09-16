# Codex 执行 Prompt：接通本体结果与演进轨迹交付

将下列整个任务交给有仓库访问权限的开发 Agent 执行。它要求实际实现和验证，不是只修改文档。真实模型/外部服务调用仍受本轮授权、预算、权限和环境限制。

---

你正在改造 `Yangjunjie-Lin/KG-MNP-Demo`，代码包为 `zhigou_toolchain`。本轮目标是：**保留现有五阶段与双 Agent 内核，让一次真实本体建模运行能够导出本体结果交接包，并让本模块真实运行轨迹满足演进组接收要求中可兼容的部分；未定义协议部分明确隔离，不伪造数据。**

不要重建整个项目，不实现演进组的训练/优化/发布系统，不以只写计划或缺口报告替代可以完成的代码工作。

## A. 先读依据和现状

按顺序阅读：

1. 根目录 `AGENTS.md` 及目录作用域内已有 Agent 指令。
2. `docs/ontology/ONTOLOGY_MODULE.md`。
3. `docs/ontology/HANDOFF_CONTRACT.md`。
4. `docs/ontology/IMPLEMENTATION_AUDIT.md`。
5. `docs/ontology/references/evolution-upstream-v2.original.md`。
6. `docs/ontology/references/meeting-handoff-v2.original.zip` 内 README、两端 manifest、mapping/provenance/review/validation、queries/tests；这些是合成会议样例，不是运行时可直接投喂的整包。
7. 项目现有 README、`docs/upgrade/ontology-io.md`、`docs/upgrade/ontology-kernel-v1.md` 及有关原生契约。

2026-09-16 审查基线是 `develop@194e091d13cabba5833ff1d531f814858ea968ae`，当时 main 为其父提交 `adc2a40512f8b029b6c21420b905628c32952d00`。首先核实当前 HEAD、分支、工作树和较新实现。不要倒退新代码，不丢弃既有修改，不因仓库默认是 main 就遗漏新双 Agent 内核。没有本轮授权不得推送、合并、发布、删除分支或重启旧 benchmark 付费任务。

来源冲突时保留原文并记录差异；本项目建议不能伪装成对方已经批准的契约。发现更合适的已有适配器先复用。

## B. 不能改变的职责与内核

数据处理组只交数据、来源、质量与批次；业务方确认目标规则；平台方交可选基线；验收方交独立预期。本模块不能要求上游预造候选、原生 IRI、审核或编译计划。

保留 `RuleAgent` 负责 S1/S2/S4、`TaskExecutionAgent` 负责 S3/S5 的现有安排。RuleAgent 不自动取得人工审批权，后者不是下游业务 Action Agent。

复用已有 Source/Batch/Plan/Run、KG-IR/Evidence、modeling.session、共享编译、原生 .kgop、审核、CAS/租约、STALE、Registry/Release。不能新增第二套 session/candidate/review/version 真相来源。不能用日志和导出器绕过权限或审核。

不将研究模式修复快捷路径静默用于生产；不更改原 v3 Schema、原生稳定 IRI、签名或历史摘要。框架通用，HR 和林业只作为领域包。

## C. 实现真实输入和结果绑定

对原会议输入格式新增或复用薄适配。将 manifest、规则化记录/文本、source_locator、quality_report 和可选基线解析到原生实体；核对文件摘要、路径、引用、版本、许可与数据访问范围。不能把整个 meeting mapping JSON 当成原生 DTO。

将真实项目、批次、KG-IR、证据、session/revision、规则/基线、候选/映射、确认包、编译快照和原生归档关联起来。字段从现有服务端工件产生，禁止使用例子 ID 冒充真实 ID。生成和修复输入中不得出现独立答案。

遇到数据不合格按原流程拒绝或分流；不要另写清洗系统，也不要先生成漂亮静态文件绕过真实接入。

## D. 实现本体结果正式交换出口

优先扩展 `src/zhigou_toolchain/modeling/delivery/`，复用同次运行的原生工件，输出原交接组织：

`ontology.ttl`、`instances.ttl`、`shapes.ttl`、`mapping.json`、`provenance.jsonl`、`validation.json`、`review.json`、`queries/*.rq`、`tests/cq_*.json`、`tests/negative_cases.json`、`manifest.json`，以及必要的授权 dependencies 和已存在的 `.kgop`。

三个图对应现有 native.py 中 `ontology/effective-tbox.ttl`、`data/abox.ttl`、`shapes/effective-shapes.ttl`。原字节优先；重序列化须图同构，保留空白节点、OWL restriction、公理和 NamedIndividual 声明；不能为接近会议示例而改名、删边或重分配 IRI。

补齐 native.py 当前列出的真实绑定缺口：范围与规则、授权来源/定位、实际映射执行、独立验收答案和审核交叉引用。不能从 ontology 图猜业务规则，不能从输出查询回填预期，不能把 DECLARATIVE_NOT_EXECUTED 改成执行成功。

当前 export-diagnostic 仍是诊断，不可改名冒充完整出口。为新逐文件视图登记独立项目格式和 Schema，不冒充原 v3 或 .kgop。任务与格式不兼容时诚实拒绝该格式；无实例/无规则场景不造数据。

独立记录执行、验证、审核和发布状态；待审/未验证的草稿与正式交接区分。失败任务仍保存可用诊断，不能以没生成正式本体包为由丢弃轨迹。

## E. 实现统一、受控的真实轨迹记录

先检查并复用既有审计/存储工具；建议抽出一个小型 TraceRecorder、契约验证器、harness 冻结器和导出器，不新建业务状态机替代原服务。

核心接入点至少检查：

- `five_stage/agents.py`：AgentRun.call、execute_routed、真实工具开始/返回/异常及当前阶段上下文。
- `five_stage/compatible.py`：CompatibleClient.propose 的实际请求、公开响应、Schema/JSON 拒绝和用量。
- `five_stage/tools.py`：QwenClient.propose/_request；health/GET models 不是 LLM 推理轮次。
- 原 Worker/作业终态：真实失败、取消、租约失效、持久化和导出状态；失败收据不得绕过原权限提交。
- 研究模型 broker 和 `ontology_io.kernel.generate_kernel` 所在实际路径：需要共享埋点时复用适配器，明确 LIVE/RECORDED/DETERMINISTIC，不重新搭研究内核。

一次高层工具可能调用多次模型；每次实际推理请求只记一次，不在客户端外层和 transport 内层重复记。完整失败请求与公开失败回复需要在异常抛出前进入受控轨迹，不只读取成功函数返回。

保留现有 AgentRun 的低敏摘要审计。新增内容日志不能把来源、prompt、API key 塞到原公共审计里；记录必须可配置、受访问控制，真实资料需要明确授权。对外不泄露凭证、Cookie、秘密 URL、供应商私有 reasoning、验收答案或非授权来源全文。后置脱敏须明确标 REDACTED/PARTIAL，不声称原字节完整。历史哈希不可还原消息，不能事后补写虚构 prompt。

## F. 按对方 v2 生成事件，不暗改语义

事件仅按确认契约生成：task_start、llm_call、llm_output、tool_call、tool_result、task_end。公共字段 event/ts/run_id；时间为带偏移的 ISO-8601；每条轨迹一个 UTF-8 JSONL 文件。

保留原生 `agent-run:<uuid>`，另分配合法稳定的 `transport_run_id` 供文件名和事件使用，并在关联表保存外部/原生运行、任务、会话和版本。多个作业不拼成假单次运行；同次运行重导出不制造新样本 ID。

turn 是实际模型调用轮次，从 1 连续递增，模型重试开启新轮；两个角色在同一真实运行中共用分配器。call_id 对每次调用唯一，结果复用对应调用 ID。支持多槽并行、同名工具、乱序结果和异步跨轮返回；模型输出 turn 与其调用一致，工具结果 turn 不早于调用。

保留工具和模型的失败、重试、取消。模型/工具 status 为 ok/error，任务为 success/failed/cancelled；未知用量不填零。任务正常结束前调用全部闭合；不可确认的硬崩溃保留未完成记录和诊断，不补成功尾事件。

**特别处理：** 原 v2 未定义首次模型前或纯程序任务如何分配工具 turn。完整记录真实本地程序过程，但严格导出对不兼容运行明确报告协议阻塞；不伪造 llm_call、不把阶段号当 turn、不自行把 turn=0 当已允许。把可能的程序事件/turn=0 扩展放到独立待确认配置与协议记录，默认不启用。可表示的真实模型轨迹、结果出口及其他独立工作继续完成，不因这一未决点全停。

新生产者全部带 call_id、fail 评价带 annotations；兼容读取器对原文 warning/error 的行为分别保存，不能暗改对方规则。

## G. harness、关联与人工评价

task_start.harness 必须含 tasks/prompts/tools/rules/knowledge/ontology 六个真实 SHA-256。冻结源文件和配置清单，定义排序/序列化与摘要算法；记录 commit、脏工作树指纹、模型与依赖版本。ontology 指本次开始采用的基线，不指未来最终输出。确实不适用的资源可冻结明确 N/A 描述并计算真实哈希，不用随意常量。

建议新增 context/run_bindings.json 和 context/harness_manifest.json 作为本项目关联附件。扩展字段与接收器原字段分开，不假设对方会解析这些附件。

避免哈希循环：harness 在运行开始前可计算；轨迹不包含自身最终包摘要；最终关联表在轨迹和产物完成后绑定它们；总封面最后生成。

运行评价使用对方 reviews/*.jsonl 格式，与本体 review.json 分开。只有真实人工提交的评价可成为正式人工样本；程序检查不冒充人工，测试评价标合成。exec_id 绑定接收器可识别的外部运行 ID。无人工评价则不生成 reviews 文件或虚构审核员。

对方法规/决策违规码不直接适用全部本体问题。保留准确 annotations 和自身 validation，不自造对方枚举或强套 bad_law_ref。完整 verdict 枚举、本体 answer 对象、ontology 违规码和评分入口写入待确认项；收集成功不代表评价器支持。

## H. 批次导出、CLI、服务与界面

evolution 接收根保留 executions/、reviews/ 和 upstream_manifest.json。manifest 使用对方字段 name/sha256/size，字节数按实际 UTF-8 文件；声明文件缺失或摘要错误整批失败。额外 context 和本体包由本项目总封面关联，不自行改变对方收集路径。

原子写 .tmp→同文件系统 rename；跨机先 incoming；manifest 最后写。处理多批并发、输出存在、目录穿越、符号链接、大小限制、重复 run 投递和幂等冲突，不覆盖已冻结文件。不改对方 collected/quarantine。

在现有 delivery CLI 中新增结果导出、轨迹导出和协议验证能力，具体参数遵循现有风格；现有 inspect/preflight-native/export-diagnostic 行为保持兼容。新增命令在代码实现前不能在 README 写成已可用。

将服务端导出接入现有 operation registry、API、Worker、权限检查和任务结果，不用前端内存拼装正式 ZIP。可以采用 modeling.handoff.export / modeling.evolution.export 等名称，但先查是否已有同功能操作，保持唯一入口。

第五阶段只增加简洁的“本体交接包”“演进数据包”下载入口及准确状态。失败作业从作业详情导出可用失败轨迹，不要求先通过第五阶段。不新增演进训练界面，不恢复已废弃教程，不扩大主页面信息量。

## I. 实际测试与交付证据

先为新模块单测，再跑原有本体/服务/安全相关回归。至少覆盖：

1. 同一次真实本地服务运行→原生 .kgop→逐文件包；所有版本、图、映射、来源、审核和 manifest 绑定正确。
2. HR 合成样例及项目已有林业领域包的可用流程；样例身份与生产数据分离。缺依赖明确 NOT_RUN，不静默降级。
3. 真正生成/修复进程无法读取 acceptance_private、tests 标准答案和 references 中的整包及 docs/ontology/evidence 检查记录；不能只检查目录名。
4. 过期审核、过期 revision、越权导出、失效 Worker、CAS 冲突、非法来源依赖不能通过。
5. 模型成功、HTTP 失败、JSON/Schema 拒绝、模型重试、工具错误后重试、多工具同名并发、跨轮返回、取消、硬崩溃、缺用量。
6. 重复 call_id、孤立 result、跳轮、错 run_id、非法时区、截断 JSON、manifest 少文件/错摘要/错长度/路径穿越、重复投递。
7. 首次模型前/纯程序运行被准确报告为严格 v2 未覆盖，且没有虚构模型事件；结果导出和其他可兼容工作不被整体阻断。
8. CLI/API/Worker 实际输出同一内容，界面下载真实服务端产物，不 Mock 核心服务；模型网络边界可明确用录制/Mock 做工程测试，但不能说 LIVE 已通过。

复用 README 已有命令：ruff、tools/check_types.py、evaluate_research.py --suite ontology、相关后端测试和必要前端检查。先核对现有选项和依赖，不凭文档猜不存在的命令。完整回归、浏览器和外部接收器未执行时分别列出，不把局部绿灯写成全部通过。

没有本轮明确预算授权不新增付费模型请求；已有录制回放/合成测试可验证代码链。对方收集器不可用时输出本地验证证据与未联调状态，不宣称已接收、可训练或评分达标。

## J. 同步文档并交付

更新 README、docs/ontology/ONTOLOGY_MODULE.md、HANDOFF_CONTRACT.md、IMPLEMENTATION_AUDIT.md、根 AGENTS.md 和现有 requirement_traceability.md 的相关条目。保留原始资料和历史失败记录。文档中的已实现、已实测、待确认、未执行必须分开。

最终交付：实际代码变更清单、输入到输出的真实路径、可复现命令、合成实跑生成的包、分项测试证据、协议差异及未决项。包中的运行模式和审核性质要准确，不把测试夹具变成正式人工/生产轨迹。

本轮完成门槛是能真实导出、可验证、可回查且不破坏现有语义与权限。若外部接口阻塞完整投递，交付所有已经完成的独立能力，并明确仍缺哪一条对方约定；不要仅给“后续建议”，也不要宣称全部上线。
