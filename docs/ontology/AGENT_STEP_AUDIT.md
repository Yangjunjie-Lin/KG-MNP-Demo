# 双 Agent 与逐步审计（2026-09-17）

## 场景 Prompt 预设审计（2026-09-30）

主说明在 ONTOLOGY_MODULE“场景 Prompt 预设”，接口在 HANDOFF_CONTRACT。
仍只有原 ExpertRuntime 一个有界循环；三场景资源和五阶段生成/审核补充 Prompt 冻结在原 session 场景版本中。
prepare_prompt 使生成/审核/修订使用同一 scenario_id/version/resource/effective/stage digest，
两客户端保持原 POST 和 StepAudit/TraceRecorder 捕获，不把选择/预检/保存伪装成模型调用。

scenario.project 是对真实原生结果的可验证程序投影，无 method_id，不冒充注册表中的方法执行；
投影在同阶段真实 method 的审核上下文中逐次引用。原25方法身份、原子提交锚及 HUMAN 门控不变。
新增结构词汇通过原候选依赖；确认冻结时再次用同一规则重查映射，不凭可变 sidecar 宣称已批准。
受限修订列表在提交前按原 Provider 的 draft_ref 顺序规范化，使快照和实际响应摘要逐字匹配；
后续精确摘要核验不放宽。整操作/自动重验显式失败也否决技术 PASS，不能只看部分方法成功。
配置改变后原 CURRENT/STALE 与逐方法专家版本共同门控；在途修改仍由每请求 guard 和提交 CAS 拒绝。

Token 增加 scenario_configuration_groups，仍按物理请求 ID 去重；失败、取消、重试及未知用量规则
沿用。原 audits 下可回查场景阶段投影；动态配置在本轮授权实际消息与 harness 中，不反填旧 Prompt。
source catalogue 同源增加三个场景 Prompt 资源、固定输出构造器与三个共用附加片段，不复制30套长文本。

新验证目录 runtime_reports/scenario-prompts-20260930（旧粒度回执保留历史含义）；两个客户端独立Mock spy和真实服务案例，
以及浏览器实际选择/模板预览/确认/运行/同字节下载。所有身份、输入与模型响应明确为合成/Mock。
完整例子的测试专家明确确认600000预算；生产默认200000未变，预算不足的历史拒绝保留。
独立质量标签及报告不进入任何模型上下文；没有真人不写 HUMAN reviews，没有外部接收不记已收集。

## 2026-09-28 专家闭环

本轮核实 HEAD 为 `develop@84522072be25e1304daf9b6ae22fef181b11f195`，工作树有先前研究改动；
没有回退、覆盖那些实现、推送、合并、发布或授权付费实验。以下能力是本次增量，后文保留历史说明。

### 执行与版本

`five_stage/expert.py` 保存完整十份默认文本、共用修订文本及闭合 Schema。
`python -m tools.generate_model_prompts` 生成原 MODEL_CALL_PROMPTS.md/JSON，执行侧唯一来源不手填历史。
专家配置在原 `modeling-session.json` 的 `expert.stages/history` 中保存，不建立第二个会话或审批库。
阶段默认加 method 明确覆盖；每次保存新版本/摘要、认证作者/确认人/时间和项目会话范围。
默认 DRAFT，没有假专家姓名；确认文本不等于批准任何候选。
自然语言编辑必须明确确认结构化检查点覆盖，否则闭环受阻。服务保留独立硬检查，不由模型删减。

`expert_runtime.ExpertRuntime.run` 是唯一业务修订循环，服务 `modeling_expert.coordinate` 在原
Worker staging/租约/CAS 内调用。已启用会话的原 API 也进入它，不能绕过审核直接批准、编译或下载。
原程序和模型先生成候选，收集真实 method 调用结果；逐 method/输入/产物审核，不以一个总评分
代替不同 chunk、分支及重试。确定性计算只接收已冻结配置与原输入，不改标成模型生成。
原 1.4/4.4/4.5 为人类门控，不递归 AI 批准人类动作；其先决产物必须已技术通过。
完整逐方法清单仍由下方原注册表同源生成，`coverage.implementation_view()` 增加专家继承/人类边界。

内部结论仅 PASS / REVISE / ESCALATE。模型检查点结果缺失、重复、UNKNOWN、伪造引用、未解决
阻断问题或程序硬检查失败均不能技术 PASS。审核记录由服务补 AI 主体、方法、真实候选/输入摘要、
配置/检查点版本、程序收据及物理调用。模型自报身份不授信。
补丁绑定基摘要、已核验 issue_id、来源及精确 Unicode 引文，只有阶段白名单字段可由程序应用。
补丁目标/字段还必须匹配问题 location；不能借同一问题和来源改另一个对象或字段。
business_digest 单独标识实际候选/范围/计划，不让程序报告耗时变化掩盖同一业务候选的反复震荡；
candidate_digest 仍绑定本轮完整受审业务结果，两个摘要不混为同一对象。
无变化、重复摘要/震荡、无证据、越权、未知用量及预算耗尽均停止，保留历史与未解决问题。
每次修订重建原候选/队列或计划，执行受影响检查，然后重新审核；新版本不能继承旧 PASS 或人审。

默认最多三次修订（v0 + v1/v2/v3）、64 次模型物理请求、300 秒、200000 Token 预算；
服务端上限分别为 3/128/600/1000000，输出限额单列，网络重试最多 2 次且与修订轮次分开。
未知供应商用量不当零，停止后续请求；UTF-8 字节预留仅是保守上界，不冒充实测 Token。
对大而重复的程序工件使用请求内无损引用表，所有值可展开，不静默截断、删证据或提高预算。

### 失效、恢复和授权

专家配置更新从实际阶段失效；S1 修改会使 S1 范围/旧批准及下游失效，不能统一从 S2 开始。
原 `session.revise` 对不透明配置采取保守 S1 失效。旧结果留存但不能放行。
审核条件更新可以对完全相同的已提交候选重新审核；必须有可验证原提交锚及完整授权步骤正文。
前指导或方法前指导变更要求重新生成，不用“仅重审”掩盖未使用的新指导。
只有重新技术通过的同一输入/候选可恢复为 CURRENT，原人审及下游仍按原版本门控。

每个计算检查点和物理请求前重新检查认证权限、项目、Job 租约、取消与 authority revision；
提交再次由原 CAS/凭证锁/lease fence 检查。计算后失权不会提交半版本。
已提交丢响应走原 committed_result；未提交且已有模型尝试的恢复阻止自动重发，返回
EXPERT_REMOTE_RECONCILIATION_REQUIRED，不能声称跨远端 exactly-once。
纯重审优先读取原服务提交与已录制响应；正文未录制、删节或目标过期时不补造。
原生包、原生导出快照和本体交接下载前后均核对请求的精确 package_id 与当前通过的版本；
不能借另一个包或新条件下的 PASS 下载一个未通过/已过期的旧包。原受控历史审计仍可读。

### Prompt、审计与 Token

原客户端的 `traced_proposal` 组合业务任务、可信冻结专家版本、执行用途和检查点；
Qwen/Compatible 请求包装差异保持。没有另接 HTTP 客户端。
生成输入、审核安全视图、补丁/反馈均在发送前检查私有资料/秘密；独立答案和测试计划不送给审核模型。
审核无文件执行工具，不能读取 acceptance_private、gold、纠正答案库或整包 references。
生产 Worker 仍是可信控制面，不把已有研究 canary 扩大为整个生产 Worker 的 OS 沙箱证明。

native/audit/transport 三层 ID、CALL_LINK、原 step_audit_anchor 和双录制开关不变。
工具与模型记录增加 expert_binding（loop_id、revision_round、purpose、配置摘要）。
revision_round 从 0 开始但不写成外部 turn；只有真实 POST 才产生 llm_call。
AI 意见/补丁正文留原授权 StepAudit/TraceRecorder；session/UI 默认保存摘要和问题定位引用。
原审计 ZIP 扩展 `audits/expert-loop.json`、`audits/token_usage.json`；不写 HUMAN reviews。
Token 从物理请求 scope 的供应商 usage 采集，包括有用量的失败，按实际 call_id 去重，
分阶段/method/用途/循环；未知总计为 null 并保留已知小计。工具副本/Prompt 副本不重复计量。
审计 ZIP 的 Token 汇总直接投影原 MODEL 事件，即使首个候选之前失败、取消或硬中断也不依赖成功提交。
未发送的本地拒绝不计物理调用；缺少 dispatch 回执单列待协调。有已录制响应用量时保留已知小计，
仍不把缺失记录补写成成功，历史捕获能力不明时总计保持未知。
不使用新审核调用洗白它之前无模型 turn 的程序步骤；严格 v2 和外部接收限制保持。

### 操作与验证

工作台每阶段折叠显示两份文本、版本/确认状态、高级检查点/覆盖/预算，运行区展示轮次、问题引用、
差异摘要、停止原因与实际用量。详细正文通过原受权限控制的步骤审计查看；不能把元数据称为完整历史。
运行/继续沿用本阶段原按钮，补充意见用新重审操作，停止/取消沿用任务中心；均不触发审批/发布。
旧模式明确标记。接口字段及权限在 HANDOFF_CONTRACT.md 维护。

```powershell
python -m tools.generate_model_prompts
python -m pytest tests/upgrade/test_expert_loop.py tests/services/test_expert_authority.py tests/services/test_expert_service.py -q
python -m tools.verify_expert_workbench runtime_reports/new-expert-cases --pack both
python tools/verify_zhigou_upgrade.py --backend-only --workers 4 --skip-model-probe
python -m tools.verify_expert_freeze runtime_reports/expert-loop-20260928/new-frozen-run --full-backend
```

`verify_expert_workbench` 仅新建 HR/林业合成服务空间，HTTP 仅独立 MockTransport spy；
核心服务/Worker/编译及 API 下载不 Mock。输出原服务 ontology-handoff.zip、原生 .kgop 和受控审计 ZIP，
记录精确 SHA/字节数、逐轮汇总以及模型物理核账；不是 LIVE、真人专家试用或下游接收。
这些原服务导出物不恢复第四类根目录或第18项；中间候选留原版本/审计引用，不混充最终成果。
最终结果只写新的冻结输出目录；开发预检（含预算阻止、非法测试夹具和旧目录预期失败）永久保留。

## 2026-09-19 方法与实际 Prompt 增量（当前）

起点已核实为干净 `develop@4e19b2ce5f8a98b3534fbcaa34b8439b5472ef50`。保留下面历史说明。
本地旧 `runtime_reports/alignment-reference-20260918/frozen-run-01/FINAL_REPORT.md` 可读，
其原结论是模块 PASS、全仓 FAIL（2 个失败），绑定旧源码 075eadda…；不是本轮验证证明。
本轮原始失败、开发预检与最终冻结分别写 `runtime_reports/ontology-audit-20260919/`，
最终结论以新的 `frozen-run-*/FINAL_REPORT.md`、逐节点日志和磁盘重读回执为准，不预填通过。
本轮所称 Prompt 源码摘录附件未在可访问工作区检出；不将它当运行输入或日志，也不要求重补已确认的 17 项 ZIP。

### 一份方法索引，两类证据

`five_stage/coverage.py` 只投影原 method registry、StepRun、审计事件和原生 JobStore/CAS 结果。
登记方法不删减，当前实现映射、入口、条件和测试由 `implementation_view()` 返回；
运行表引用真实 BEFORE/AFTER 的 ID/摘要及 StepRun 输入/结果工件，不把旧产物投影冒充方法收据。
`RECORDED` 只表示实际挂点有记录，不表示里面所有算法、校验或人工审核都通过。
无独立方法证据保留 NOT_RUN/OUTER_ONLY；不由有源码、亮阶段灯或无模型调用推导“全覆盖”。
NOT_APPLICABLE 只来自选定操作和真实配置条件，附源 BEFORE 引用；BGE/重排/分词器未实跑仍是 NOT_RUN。
同一方法的多次循环、chunk、重试保留各自 ID；没有聊天请求不生成空 Prompt。

<!-- METHOD_AUDIT_START -->

| 方法 / 原名称 | 实际函数 | 原操作入口 / 条件 |
|---|---|---|
| 1.1 输入契约检查与质量分流 | `five_stage/profiling.py:check_input` | modeling.profile, modeling.scope.draft, modeling.session.open, modeling.tutorial.seed；verified input |
| 1.2 字段与文本画像 | `five_stage/profiling.py:profile_data` | modeling.profile, modeling.scope.draft, modeling.tutorial.seed；analysis dependency available |
| 1.3 能力问题与范围草拟 | `services/modeling_five_stage.py:execute` | modeling.scope.draft, modeling.scope；explicit draft or scope input |
| 1.4 范围与验收基线确认 | `services/modeling.py:execute` | modeling.scope.approve；authenticated scope reviewer |
| 2.1 基线解析与语义索引构建 | `control_plane/baseline.py:build_baseline_snapshot` | modeling.prepare；locked domain baseline |
| 2.2 术语候选联合召回 | `five_stage/assistance.py:retrieve_cards; control_plane/alignment.py:align_terms` | modeling.prepare, modeling.proposal；BGE_FAISS or explicit exact substitute |
| 2.3 候选重排与兼容性检查 | `five_stage/tools.py:rerank` | modeling.proposal；BGE_FAISS + nonempty cards; substitute is not reranker |
| 2.4 复用判断与结构补全 | `five_stage/assistance.py:select_reuse` | modeling.proposal；model assistance or baseline-reuse-provider |
| 2.5 结构与约束候选规范化 | `five_stage/assistance.py:generate; services/modeling.py:_propose.check_structure_drafts` | modeling.proposal；model assistance round two, or expert-enabled explicit/revised structure safe-JSON check before original normalization |
| 3.1 声明式映射配置与试运行 | `services/modeling.py:_propose` | modeling.proposal；record mapping or selected provider |
| 3.2 文本分块与位置保留 | `five_stage/tools.py:text_chunks; five_stage/assistance.py:character_chunks` | modeling.proposal；nonempty text, local tokenizer or Unicode substitute |
| 3.3 受约束的对象与事实抽取 | `five_stage/assistance.py:generate` | modeling.proposal；one physical request per chunk |
| 3.4 原文校对与证据绑定 | `five_stage/tools.py:bind_quote; control_plane/providers/mixed_mapping.py:mixed_mapping_drafts.bind_spans` | modeling.proposal, review.finalize；returned fact/repair or explicit mixed mapping with quote |
| 3.5 对象身份统一与关系引用解析 | `control_plane/providers/mixed_mapping.py:mixed_mapping_drafts.identity; control_plane/providers/record_mapping.py:record_mapping_drafts.resolve_identity` | modeling.proposal, review.finalize；explicit v1/v2 mapped identities and actual finalization rechecks; manual identities are not recomputed |
| 3.6 事实汇总、去重与冲突登记 | `control_plane/candidates.py:normalize_candidate_drafts` | modeling.proposal；provider responses |
| 4.1 候选完整性与依赖检查 | `services/modeling_semantic.py:execute` | modeling.proposal, modeling.semantic.check；candidate integrity |
| 4.2 数据约束与逻辑联合验证 | `five_stage/semantic_check.py:check_graphs` | modeling.semantic.check；shared compiler; validators report their own NOT_RUN/errors |
| 4.3 局部修复与影响范围重验 | `services/modeling_assistance.py:assist; five_stage/assistance.py:repair` | modeling.proposal；action=REPAIR; S4 routes, S3 patches |
| 4.4 业务语义与证据审核 | `services/modeling.py:_review` | review.action；authenticated human; not Agent approval |
| 4.5 确认建模包冻结 | `control_plane/confirmation.py:build_confirmed_package` | review.finalize；review closure + CAS |
| 5.1 确定性语义编译 | `services/compilation.py:execute` | compile.plan, compile.build；confirmed package |
| 5.2 映射与溯源文件生成 | `semantic_kernel/provenance.py:compile_statement_provenance` | compile.build；real provenance construction; graph digests + manifest |
| 5.3 最终工件一致性复验 | `semantic_kernel/packaging/verifier.py:verify_package` | package.verify, compile.validate, compile.build, package.export, modeling.handoff.check, modeling.handoff.export；actual archive |
| 5.4 能力问题与异常用例测试 | `semantic_kernel/validators/competency_questions.py:execute_cq_test_plan; services/handoff.py:execute` | compile.build, modeling.handoff.check；frozen independent answers/negative plan |
| 5.5 交付清单生成与下游验收 | `services/compilation.py:execute; services/handoff.py` | package.export, modeling.handoff.export；authorized export, not receiver acknowledgement |

<!-- METHOD_AUDIT_END -->

新增/修复的实际边界：scope 内部画像（并产生原 StepRun）、session.open 输入核验、
替代策略中的精确召回、两轮结构方法区分、修复引文绑定、v1/v2 映射身份、混合文本证据、
实际溯源构造、独立 CQ 检查及磁盘归档复验。图方法记录真实图摘要/manifest；
独立 CQ 仅记录输入计划/数据摘要、真实报告引用与通过状态，答案留在原验收通道。
新审计不会给模型添加任务、改动业务 Prompt 或获得审核权；S4 仍只分流，S3 执行事实修复。
人工 finalize 的真实映射重验也进入相同双角色计算上下文，外层仍是认证审核者的原收据；
没有内部计算时不造空 AgentRun 或模型轨迹，批准操作从未加入 Agent 工具白名单。
首个 frozen-run-01 在只读检查发现此入口缺口后中止，源码未变且原回执保留；
新增真实服务 spy 复现后修复，后续必须从新目录冻结，不能使用中止快照作最终认证。
底层未建立独立挂点的细分算法不冒充已经逐算法覆盖；共享校验结果中保留自身的错误/超时/未运行。

### 三层调用关联与提交信任

原 native run_id、步骤 audit call_id、transport run_id/call_id 各自保留；
ContextVar 传递 method、父步骤/父工具、job/attempt/fence。实际 POST 产生 MODEL 元数据记录，
原 AgentRun 仅保存这些 ID、输入/请求/模板/Schema 摘要和审计事件摘要，不放消息正文。
传输请求与结果一对一，工具与模型可一对多；并发按 ID 关联，不依赖记录顺序。
记录前冻结可变输入/依赖；读取 snapshot 返回副本，后续修改不能污染已记录值。

新的 `step_audit_anchor` 在原 fenced 提交前附入结果，固定当时已写事件链头和条数；
下载对照原提交回执、原生运行和实际模型见证重新核验，重算包内哈希不能替换该锚。
执行主体与原 TokenStore/JobStore 核对；历史身份读取不构成权限授予。哈希仍不是签名。
审计落盘/索引/模型轨迹收尾故障走原平台低敏故障审计，不掩盖已完成提交，不补造 AFTER。
丢失响应仍走原 committed_result/recover_job；被替换尝试不能借后来结果补齐。

### Prompt 真相、配置与权限

[MODEL_CALL_PROMPTS.md](MODEL_CALL_PROMPTS.md) 与同名 JSON 从执行源码 AST 同源生成，
列出五条生产任务全文、研究动态任务/构造式、system 包装及动态 Schema 来源；不执行摘录。
生成命令 `python -m tools.generate_model_prompts`。未优化或改写这五条任务字符串。
源文件字节摘要、模板版本、实际 messages/request/Schema 摘要是不同身份。
源码目录为了跨 Git 换行设置使用明确的 UTF-8/LF 规范化摘要；本次请求引用和 harness
另存实际运行文件的原字节摘要，二者标记不同 hash profile，不混比或替换旧身份。
harness.prompts 现在包含 services 的 scope 来源及目录；整体源码仍由 harness.tools 证明。
旧 harness 不追改。当前模板绝不被标为历史发送消息。

在两种客户端原 POST 边界保存实际 messages（含实际角色/多模态结构）、task、动态 Schema、
实际传参、未显式传入字段清单、模型配置修订、公开 content/refusal/finish、供应商可得 request_id、
用量与耗时。Qwen 保留 structured_outputs.json；Compatible 保留 system 中的 Schema 和可选 response_format。
GET models、本地组装/隐私拒绝不计推理；HTTP/超时/JSON/Schema/拒绝失败仍保留已发请求。
超限响应保留有界前缀且标记删节；客户端请求不证明服务端聊天模板、token 序列或隐藏推理。

`modeling_audit_content_enabled` 与 `ontology_trace_enabled` 分别展示，任务绑定保存当时配置与录制授权。
步骤正文开关不代表模型物理消息已录制。默认均保持原值；仅合成验证工作区显式开启。
模型上下文在发送前检查独立答案/凭据/私有字段（含序列化 JSON）；日志过滤另层处理，
字符串引文无法安全分解时整段标 REDACTED，嵌套深度有界。不能把删节诊断称为无损重放。
corrected_answer 仍走专用授权评价通道，不进入生成/修复或普通步骤正文。

### 原接口和附件兼容

沿用 `/projects/{project_id}/modeling/audits`，可选 session_id/package_id/job_id/attempt；
package_id 只能选择原服务验证的当前有效祖先，STALE 不混入。历史尝试仍单独可读。
同前缀 `/{job_id}?attempt=N` 展开详情，`/{job_id}/archive?attempt=N` 下载同一验证快照。
详情/下载都重新检查 trace:export/source:read/source:export/package:read 与项目/任务权限，
没有权限不返回正文；新增端点不是第二套日志系统。工作台只显示/下载，不自行组 ZIP。

本地 ZIP 保持 `zhigou-modeling-step-audit/1.0.0`，兼容旧步骤文件，新增可选
`coverage.json`、授权时冻结的 `prompts/run-source-catalogue.json`、有授权留存时的 `model-trace.json`。
详细字段均在这些现有审计附件，不增加外部第 18 项；旧文件没有字段时明确未知/缺失。
原日志存储仍只有原步骤目录和原模型 journal；索引/报告按 ID/摘要引用它们。
当前模板只在详情中作为当前源码视图提供，不写入旧 ZIP；运行模板在当时授权捕获并由提交链头固定。
因此当前模板变化不能覆盖旧运行模板附件；当前版本的详情与下载核对同一归档字节。
覆盖报告是只读投影，不代替原事件/提交真相；请求所属旧模板身份另在当时 harness 与请求的 prompt 引用中冻结。

同一运行分开报告步骤记录、Prompt 追溯、严格 v2、外部接收/后续用途。
失败轨迹可有诊断价值；本地完整记录也可能因为首次模型前/纯程序 turn 或删节而不能完整 v2 导出。
绝不使用 turn=0、dummy llm_call、删除前置工具或空批次洗白。外部始终 NOT_CONTACTED，训练可用未确认。

### 核验入口与证据边界

```powershell
python -m pytest tests/upgrade/test_prompt_audit.py tests/upgrade/test_step_audit.py tests/upgrade/test_agent_roles.py tests/services/test_five_stage_service.py -q
python -m tools.verify_agent_workbench runtime_reports/new-method-audit --mock-model --pack both
python -m tools.verify_stage_handoff runtime_reports/new-frozen-method-audit --baseline CLEAN_BASELINE --parallel-full --input-archive docs/ontology/references/handoff-17-20260918.original.zip
```

verify_agent_workbench 保留默认无推理模式；显式 --mock-model 仅替换 HTTP 网络，实际消息构造、
API/Worker/CAS/编译/审核核心不 Mock。新建 HR、林业和无基线修复场景，固定合成模型响应。
独立 MockTransport spy 记录物理请求，逐条比较请求摘要/方法/父调用；故意删除内层记录必须拒绝。
用例路径虽返回原 LIVE 模式字段，另有明确 MOCK_TRANSPORT 身份，不能当真实模型或专家证据。
没有下载 BGE/reranker/tokenizer，没有运行付费推理或外部接收器，也不推送/合并/发布。
新冻结入口追加上述专项与服务案例，将原始日志/审计附件一起归档；旧卫生 FAIL 不删不白名单。
生成总 ZIP 后磁盘重读，包内清单不含自身，外部 sidecar 提供总包 SHA/长度。

2026-09-18 01–17 对齐继续复用本实现，未增加第三角色或并行真相库。
前后快照仍独立于 15 的六类事件；17 的空批次不能代表所选受阻运行已完整导出。
16 的 corrected_answer 只在授权评价保存/交付侧读取，继续从模型及可读步骤正文中遮蔽。
本轮复验回执在 `runtime_reports/alignment-20260918/`，不将下述旧回执作本次证明。

在 develop@979128e 及现有本地交接改造上增量实现。旧冻结报告、原包和历史证据不变，
旧源码指纹不自动覆盖本次新增代码。

| 工作台封装 | 原生身份 | 步骤 |
|---|---|---|
| 规划 Agent | RuleAgent；PlanningAgent 是同一类的别名 | S1 输入检查、画像与范围；S2 问题、基线、术语、对齐、映射计划与结构；S4 完整性、语义校验及修复分流 |
| 任务执行 Agent | TaskExecutionAgent | S3 映射、抽取、证据与事实规范化；S5 编译计划、编译、原生验证、导出及本体交接 |

保留原 operation registry、Worker、工具白名单、session、STALE、审核和 CAS。
卡片仅导航，不因点击就调用模型或审批；跨阶段任务仍绑定真实任务与原生 AgentRun。
输入冻结、人工范围/逐项审核和独立验收另记授权主体，不授予 Agent 代签权限。
计划仍是计划，记录不会把 MappingPlan 变为已执行。

## 前后记录

相关任务获授权进入执行后，在服务工作区保存：

```text
service-data/modeling-step-audits/<project-hash>/<job-hash>/<attempt>/
  000001-before.json
  000002-before.json
  000003-after.json
  ...
  summary.json
```

BEFORE 在调用前写入，AFTER 保存真实输出或错误类型/已知错误码。嵌套调用按 call_id 配对，
不靠相邻行猜关系。事件绑定 job、attempt、租约 fence、请求摘要、project、操作和身份；
工具事件另绑定 run、session/revision、依赖、阶段与版本。操作前后包含输入和产物引用。
后置计算快照在发布前观察，并与该任务提交回执核验，不借用后来一次运行的输出。

默认 METADATA_ONLY，原公开 AgentRun 仍只留低敏摘要。服务显式设置
`ZHIGOU_MODELING_AUDIT_CONTENT_ENABLED=true`，且执行身份有 trace:record/source:read，
才保存过滤后的输入输出正文。独立预期、负例计划、凭证和供应商私有推理字段遮蔽。
单条正文超过 4 MB 标记 OMITTED_SIZE_LIMIT；总大小/事件数有界，不静默声称完整。
此快照不是供应商思维链或完整模型传输日志；模型原消息仍使用既有可选 TraceRecorder。

失败、取消、被替换尝试与成功分别记录；旧租约身份回查 JobStore claim 事件。
硬中断可能只有 BEFORE，导出为 INTERRUPTED，不补写成功。
旧任务未录制内容为 ARTIFACT_NOT_AVAILABLE，不能从最终结果倒造。
鉴权前拒绝、请求格式非法和未领用即取消没有计算快照，保留原平台安全/任务记录。

## 接口与包

以下接口在 `/api/v1` 下：

- `GET /projects/{project_id}/modeling/audits`：任务索引及两类 Agent 定义。
- `GET /projects/{project_id}/modeling/audits/{job_id}/archive?attempt=N`：已落盘前后记录 ZIP。

索引需 project:read/job:read 及真实项目/任务范围；下载另需 trace:export、source:read、
source:export、package:read。每次重新鉴权，不能由客户端自报权限。
ZIP 含 `steps/*-before.json`、`steps/*-after.json`、journal.jsonl、manifest.json、README.md。
事件哈希用 KG-MNP Canonical JSON v1；清单用原字节 SHA-256，不包含 manifest 自身。
哈希链不是授权或签名，下载还核验 JobStore 请求、原生运行和真实提交结果。
审计不是业务真相来源，不允许生成/修复 Agent 通过审计出口读取验收材料。
格式为 `zhigou-modeling-step-audit/1.0.0`，不是外部演进 v2、原 v3 或发布认证。

## 验证与启动

```powershell
python -m pytest tests/upgrade/test_step_audit.py tests/upgrade/test_agent_roles.py tests/services/test_five_stage_service.py -q
python -m tools.verify_agent_workbench runtime_reports/new-agent-audit-example
python tools/run_browser_verification.py --selected-test agent-audit.e2e.ts --startup-timeout 90
python tools/start_zhigou_demo.py --port 8765 --record-step-content
```

样例输出目录必须不存在；使用 HR 合成数据、真实服务/Worker/共享编译，输出逐任务 ZIP、
modeling-agent-audits.zip、verification.json 和独立服务工作区。合成审核不是专家验收；
模型调用为零，不做真实业务或外部发布。浏览器验证独立创建项目，点击运行和下载，
比较同一任务 API/浏览器原字节。回执保存在 runtime_reports/agent-step-audit-20260917/。
未重跑整仓冻结认证，不覆盖原卫生 FAIL、研究和上线限制。
