# 本体结果与演进轨迹交接契约

## 场景 Prompt 预设内部契约（2026-09-30）

主说明见 ONTOLOGY_MODULE“场景 Prompt 预设”；不改原 native/v3/v2 Schema、六类事件或六个 harness 顶层键。

| 原 operation / 项目 toolchain API | 闭合字段 | 服务端权限和含义 |
|---|---|---|
| modeling.session.open | 原字段 + scenario: ScenarioSelection；可选 scenario_acceptance | 场景需 HUMAN/scope:approve，独立标签需 acceptance:run；输入/标签在生成前冻结；无场景旧入口仍准确显示旧模式，不能降级已启用会话 |
| modeling.scenario.preview | selection、可选 run_id | project:read/source:read；只读、0模型调用；返回冻结模板、来源适配契约、领域包兼容及缺数据/不支持情况，不授权执行 |
| modeling.scenario.save | selection、expected_revision | 原 model:propose/source:read/scope:approve、HUMAN、Worker/CAS；保存新版本，保留专家文本、使受影响指导与审核待重确认 |
| modeling.expert.save | 原闭合配置与版本字段 | 必须保留服务生成的 scene.* 必需检查点；确认绑定 scenario_stage_digest，不接受客户端自报签认摘要 |
| modeling.scenario.quality | package_id、expected_revision | acceptance:run/package:read/source:read；原Worker重新验证当前包与配置，以冻结合成标签计算独立指标，不调用模型、不批准、不修图 |

ScenarioSelection 仅为 scenario_id、scenario_version；当前资源为 v2.0.0。旧 manual_overrides、
excluded_capabilities、required_capabilities 与任意自报审批字段拒绝，不再提供逐阶段档位。
旧 v1 会话需显式预检/保存当前模板，从 S1 重确认、生成、审核；不原地改写旧冻结条件或复用旧 PASS。
资源加载地址固定，不读取客户端路径或脚本。历史 ZIP 的只读 v1 重构不参与当前生产。

同阶段输出 `zhigou-scenario-stage/2.0.0`（无 level 等档位字段） 只投影实际原生结果和引用，保留注册字段、类型、状态、
配置摘要与原方法审计关联。新词通过原 candidates→review→confirmation→compiler；候选依赖不是
伪造基线 ID。全部登记来源字段通过原映射保留，源数据原字节不改；缺失/未知字段明确报告，不能自动排除失败。

新记录融合进原审计 ZIP 的 audits/scenario-outputs.json、既有 Token 分组及 prompts 捕获。
原本体服务交接 ZIP 可附 services/scenario-contracts.json、audits/scenario-configuration.json、
匹配当前包与配置时的 audits/scenario-quality.json，全部由原 manifest 哈希/重构校验覆盖。
原 `.kgop`、TTL、签名、查询/负例/独立答案和五板块不由模型编辑，不增加第四根目录或第18项。

scenario_acceptance 是独立受限通道，包含标签集ID/版本、预先声明的 capability 投影、
EXACT_TYPED_KEY_SET_V1 匹配单位和显式合成性质；不能从生成图反造标签。领域类型、关系、属性分别
报告 TP/FP/FN 和分母；零分母为 null，无标签 NOT_EVALUATED。它及 scenario_quality 在发送前被
原隐私过滤排除，不能通过专家意见或模型审核泄漏给生成/修订。实测合成指标不证明 LIVE/行业精度。

场景摘要进入原 harness.tasks/rules/prompts，不添加顶层键。每次物理调用仍保留原三层ID、
revision_round/真实turn区分，按场景/配置、阶段/method/用途去重。只读预检、保存、纯程序和独立
评测没有模型调用时不造 llm_call。批次 upstream_manifest.json 仍是本项目每批必须项。

工作台在建模前显示三场景、五步骤生成/审核 Prompt 预览、只读输入预检；保存后的受影响专家阶段需确认。运行页显示
实际产物/诊断/契约和独立质量缺失状态，沿用原开始/继续/取消。场景中未实现的表外自由抽取、数值
推断、通用过滤/组合查询、设备/工单业务动作均明确不支持，不借模板名称宣称已部署。
投影显示还核对原 CURRENT 输出/逐方法当前审计任务；独立指标另核对当前 package_id 和配置摘要，
不能仅因配置相同就显示旧候选或旧包的指标为当前结果。旧报告仍在原历史审计中保留。

2026-09-24 新增独立研究[Token JSON 视图](../research/token-audit-json-2026-09-24.md)，
schema_version 为 ontology-token-usage/1.0，不冒充演进 v2 或第18项交付。
保留原 job/request ID、失败/重试、中断未知；input/output/total 任一未知相应合计为 null，
已知部分与预算占用分别给出。只有原 job 终态且全部用量已知才给 final_total_tokens。
无正文、密钥或私有 reasoning；该本地观察附件不改变 native/audit/transport、step_audit_anchor、
双开关、原日志下载权限、人工审核或外部接收状态，亦不证明物理 HTTP 调用数。

2026-09-24 [有授权的主机中断观察](../research/host-reboot-continuation-2026-09-24.md)是原研究
job/预算账本的从属操作者收据，不是供应商response、模型成功、业务审批或第18项交付。
原CALL身份及未知usage/response hash保留；缺失历史内容不补造，严格业务出口不因此放宽。

2026-09-23[隔离本地隐私拒绝](../research/local-private-veto-isolation-2026-09-23.md)的操作者收据
明确区分本地拒绝与耗尽的传输失败；独立spy复现不是历史调用/用量的替代证据。
原FAILED、usage=null、费用预留、三层ID和15–17保持，不产生隐私门放行或新审批事件。

2026-09-23 [研究续跑控制](../research/terminal-transport-continuation-2026-09-23.md)只向原研究预算账本
追加绑定真实用户授权的终态传输续跑收据，并保留原FAILED/请求ID/费用与三次尝试记录。
该操作者事件不是模型调用、自动重试、本体审批或新增核心交付项；15–17和原业务接口不变。

2026-09-21 的 [Luna 评测恢复诊断](../research/luna-recovery-2026-09-21.md) 是独立研究运行证据，
不是新的交付类别或正式人工评价；不改变本契约、原生 ID、审计权限与历史交接。
其真实模型调用不代表本体 benchmark 或外部接收完成。
后续 [网关参数透传诊断](../research/cockpit-gateway-repair-2026-09-21.md) 收到HTTP400；
错误响应仅留安全白名单及原响应摘要，明确不是完整原字节轨迹，也不新增正式交接类型。
后续接口复测和quality/effects研究报告仍是独立研究附件，沿用原审批、轨迹权限和交接类别。
配对质量差值与置信区间只来自完整冻结预测，不以合成接口响应或统计单测冒充正式结果。
本地预算监控授权仅供研究broker核账与新revision调度，不属于运行时Agent审批工具，
不改15–17演进事件、双开关、正文权限及native/audit/transport调用身份。
研究全量的execution_attempts及transport_recovery_ack仅是原研究任务/预算账本的从属尝试记录；
失败请求ID/响应摘要/未知用量保留，不改写为成功、不作为新的业务事实或审核真相。
研究模型上下文的card_index是本次请求内可逆引用，不是native/audit/transport ID；
实际消息记录压缩后的真实请求，旧消息不能用新编码回填，业务交接格式不变。
研究HTTP408重试继续记录独立真实请求ID、原失败与未知用量；仅更新错误分类，
不把失败输出改为成功，也不改变演进协议、审批或完整轨迹资格。
研究修复中的quote_location_hints只描述同一冻结原文的Unicode定位候选，非标准答案；
旧模型提案和失败保持原样，最终引用仍须由实际新提案通过原验证，不新增交付类别或审批权。
PROGRAM_UNIQUE_QUOTE_V1只改变显式新研究版本的模型响应契约，canonical triples/schemas、
native/audit/transport ID和业务交接Schema不变。程序派生位置须标明非模型提供，不伪称旧offset正确。
研究候选词表的输入闭包不构成人工批准或新词授权；新增来源说明记录输入词与模型提案的区别，
不修改既有原生IRI、评价或交接Schema，不用S3预测/标准答案自行扩大词表。

2026-09-18 当前字段规范，按本轮完整 Prompt 与 01–17 清单维护。旧协议原件保留，
下面已明确的字段优先于历史未决表。01–08 输入、09–14 本体成果沿用原适配/1.1 Schema；
15–17 只有执行记录、真实人工评价、批次清单三类核心交付，无第 18 类。

当前“精简版”参考由用户明确指定为《本体建模_上下游数据交接文件包_名称更新版_20260918.zip》。
原字节 SHA-256：`be5d0c703a923d095e901991b0fc507049f5458471f0b8f7711f33b7417e8094`，62,153 字节。
身份记录与只读归档在 [references/handoff-17.reference.json](references/handoff-17.reference.json)；
它替代前轮待补的参考用途，不声称与旧 Prompt 所列 bbcf5bbf… 原件相同。
包内 Markdown、HTML 和 Excel 的 01–17、六事件必填字段已对应当前实现；规范仍只在本文件维护。
原件中的历史 v2、合成样例版本/许可/摘要保持不变，整包不进入运行时模型。

2026-09-17 新增项目本地 `zhigou-modeling-step-audit/1.0.0` 前后快照 ZIP，见
[逐步审计契约](AGENT_STEP_AUDIT.md)。独立于本体交换/v2，不修改旧 Schema 或历史包。
记录、审批、程序验收、提交和发布仍分别记账。

2026-09-19 该本地审计格式增加可选方法覆盖、当前模板目录和授权请求附件，
兼容旧事件，三层调用 ID 不互换。详细兼容/权限/完整性状态只维护在
[AGENT_STEP_AUDIT.md](AGENT_STEP_AUDIT.md)。本地 MODEL 元数据不是外部第七事件；
15/16/17 不变，实际 Prompt 不用源码摘要或最新模板倒造。完整本地记录、严格 v2 资格、
已导出及对方接收分别核验，旧日志/harness 不追改。

> 2026-09-16 / 项目实现与外部协议对照。原设计原文保留；已实现接口和收缩范围见第 11 节，双方联调尚未执行。
> 外部依据：`references/evolution-upstream-v2.original.md`；现有交换样例：`references/meeting-handoff-v2.original.zip`。
> “对方要求”与“本项目建议”在本文件分开标注。不得把本建议冒称外部标准、原 v3 Schema 或已上线协议。

## 1. 交接目录与格式身份

下列顶层组织是本项目建议；`evolution/` 作为对方接收根时，其内部轨迹路径保持原文不变。

```text
handoff-<batch-id>/
  handoff_manifest.json              # 建议：总关联封面，最后生成，不包含自身摘要
  downstream/                       # 原交接组织；从真实运行导出
    manifest.json
    ontology.ttl
    instances.ttl
    shapes.ttl
    mapping.json
    provenance.jsonl
    validation.json
    review.json
    queries/*.rq
    tests/cq_*.json
    tests/negative_cases.json
    dependencies/                   # 必要且授权可交付的依赖
    native/ontology.kgop            # 已生成原生包时保留原字节；不伪造
  evolution/
    executions/run-<id>.jsonl
    reviews/reviews-<batch-id>.jsonl  # 没有真实人工评价时不生成
    upstream_manifest.json
    context/
      run_bindings.json             # 建议：原生 ID、外部 ID、产物关联
      harness_manifest.json         # 建议：六类 harness 摘要来源
```

失败任务可以只交演进包和可用诊断，不要求成功生成或发布 `.kgop` 才能交失败轨迹。已有建模结果但演进契约尚不兼容时，结果可以单独导出；总封面如实记录演进导出未就绪。

`downstream/manifest.json` 描述本体交换视图；原生归档内 manifest 描述 `.kgop`；`upstream_manifest.json` 仅承担对方定义的批次核对。不能合成一个字段含义混乱的 manifest。

当前逐文件正式交换视图为 `zhigou-ontology-handoff/1.1.0`，1.0.0 保留只读兼容；
这是本项目约定，不能沿用 `MEETING_REFERENCE_EXAMPLE` 假装实跑，也不冒充原
`ontology-delivery/3.0.0`。既有生产 v3 Schema 不变。

## 2. 结果文件如何产生

| 结果 | 实际来源与规则 |
|---|---|
| 三份 TTL | 优先取校验后的原生图原字节；确需序列化时保持 RDF 图同构，区分文件哈希与语义摘要 |
| mapping | 将真实 MappingPlan、实际映射/转换记录及原生引用关联；DECLARATIVE_NOT_EXECUTED 不能改标 EXECUTED |
| provenance | 最终语句与 evidence/source/mapping/version 的闭包；所有引用必须可解析 |
| validation | 实际检查结果，含受测文件、版本、摘要、检查器和执行状态 |
| review | 原生授权审核决定及受审内容摘要；未审核仍为待审 |
| queries/tests | 冻结查询与独立预期；不得查询最终图后将结果写成“事先正确答案” |
| dependencies | 本次冻结输入、来源和许可允许的快照；不能复制全仓库或无授权原件 |
| manifest | 真实运行、原生包、文件和依赖的绑定；真实值从系统读取，不补造 ID |

对无实例/无基线/无规则任务，显式记录适用性及缺省原因。若所选交换 Schema 要求这些内容，就拒绝该格式导出并说明不兼容；不能制造空事实或削弱原 Schema。

“导出诊断”“导出草稿”和“已审核结果交接”必须有不同状态。发布仍由原 Registry/Release 机制决定，导出不能自动批准或发布。

## 3. 运行粒度与 ID

当前 `AgentRun` 通常围绕一次真实服务操作建立，不等于五阶段完整会话。默认以真实任务/作业运行边界保存轨迹，并以 `session_id` 及原生版本关联多个运行；不能事后拼成一个虚构的全流程任务。

原生 `agent-run:<uuid>` 含冒号，不符合对方文件名 `<id>` 规则。新增独立 `transport_run_id`，仅使用 `[A-Za-z0-9._-]+`；原生 ID 不改。关联表保存两者。不得只替换非法字符而不检查碰撞。

`executions/run-<transport_run_id>.jsonl` 中 `run_id` 为文件名去掉 `run-` 和 `.jsonl` 的 `<transport_run_id>`；按对方示例，此 ID 也应是 `reviews.exec_id` 指向的执行 ID。正式联调需用对方实际收集器核对这一映射。

外部 ID 一经分配保持稳定。重导出同一次运行不能换新 ID 假装新样本；对同一收集端的重复投递要有交付账本，不能因文件内容相同就假定对方会忽略重复 run_id。

建议关联附件至少记录：`transport_run_id / native_agent_run_id / task_id / job_id / session_id / session_revision / parent_version / execution_mode / input_snapshot / output_artifacts`。其中 job 等字段只在真实系统存在时填写；缺失写明不可用，不造值。

## 4. 对方 v2 事件要求

所有事件必须含 `event / ts / run_id`。时间使用带明确偏移的 ISO-8601，例如 `+00:00` 或 `+08:00`，不得使用无时区字符串。原文公共字段允许时区偏移，其实施清单举 `+08:00`；接入配置记录所用偏移，必要时向对方确认接收器没有额外限制。

| 事件 | 必选内容 | 本项目生产者的记录原则 |
|---|---|---|
| task_start | task_id、task_input、harness | 首事件且唯一；输入及版本先冻结 |
| llm_call | turn、messages | 在一次真实模型推理请求发出前记录完整实际消息 |
| llm_output | turn、content | 保存公开输出；失败也必须闭合并记录 status/error |
| tool_call | turn、tool、args | 在真实工具调用边界记录，不能用阶段摘要代替全部工具 |
| tool_result | turn、tool、result | 记录真实返回或失败，保持与调用配对 |
| task_end | status、answer、duration_ms | 末事件且唯一；仅在真实终态记录 |

`llm_output/tool_result.status` 使用 `ok/error`；`task_end.status` 使用 `success/failed/cancelled`。

任务执行成功不等于本体语义正确、人工批准或已发布。`answer` 是该任务实际服务结果，
包括原有工件引用，不在导出时补写总结或只交摘要；协议不解析其内部业务结构。
`finish_recorders` 原样交给隐私过滤器，过滤时明确 REDACTED，严格 v2 禁止冒称完整；
内部 result digest 继续与真实已提交结果核对。旧日志的摘要 answer 保留兼容读取，不补造正文。

`model`、`temperature`、`usage`、`duration_ms` 按实际可用信息记录。将 provider 的 `prompt_tokens/completion_tokens` 对应到 `input_tokens/output_tokens`；未知用量不填 0；不把全部请求 token 与输出 token 错算为输入。未配置或未返回的参数不编造。

## 5. turn、配对、失败与并发

`turn` 是模型调用轮次，不是 S1—S5 编号，也不是工具序号。按原文“从 1 开始、跳跃隔离”执行连续的 1、2、3……；每次真实模型重试开启新轮，两个 Agent 共用该真实运行的轮次分配器。

每次调用分配新 `call_id`，结果复用对应调用的 ID。唯一性约束作用于**调用实例**，不应把配对结果对相同 ID 的引用误判为重复；LLM 与工具调用也不得碰撞。新生产者对所有模型/工具配对均写 call_id，满足并发场景，不依赖位置推断。

上述是本模块录制策略，不是外部新增必填：合法串行缺 call_id 位置配对并告警；
并行提交必须带 ID，兼容读取仍保留缺 ID 的原告警口径。非空未知 event 仅告警并保留，
继续核对公共字段及任务边界；缺少/空 event 是错误，不归入“未知”。

多个工具可同时未闭合，按 ID 和工具名精确配对。工具结果 turn 不小于对应调用 turn。取消时对能够确认中止的未完成调用写真实取消/中断错误，然后写 task_end；不能补成功结果。硬崩溃导致无法确认终态时保留未完成 `.tmp` 和诊断，不把截断文件包装成正常完成轨迹。

模型收到 HTTP 成功回复但本地 JSON/Schema 检查失败，也要保存公开回复及失败信息；不能只保存成功返回值。HTTP/网络失败、输出被截断、响应解析失败同样记录，错误信息须脱敏。

工具返回“校验发现问题”与工具本身崩溃是不同情况：前者可以是工具成功返回问题列表，不能统一改成系统错误；本体质量由验证字段表达。

### 5.1 契约未覆盖的程序步骤（阻塞项，不能自行偷改）

当前流程包含 S1 输入检查、检索、编译等可能发生在首次 llm_call 前或完全不调用模型的步骤。对方同时要求工具 turn 为正整数、turn 代表实际模型轮次，未定义这类步骤的编码。

先完整保留现有本地程序审计和独立受控运行记录，不伪造 `llm_call`，也不把 S1 写成 turn=1。对严格 v2 无法表示的完整任务，输出明确的协议缺口并阻止其被标为“完整 v2 轨迹”。

拟议联调方向：由对方确认独立程序事件/阶段元数据，或明确允许 pre-model/program-only 的 turn=0；这均属于**待协商扩展**，不是当前 v2 已允许。另一种办法是导出真实 LLM 片段并在关联表标明片段范围，但不能称完整五阶段轨迹；该接收范围也应先确认。

不得为了绕过这一缺口，把没有模型调用的任务只保留 start/end 后宣称过程完整。契约缺口只阻断不兼容轨迹，不应阻断其他可独立完成的结果导出、模型边界埋点和合法轨迹测试。

## 6. 六类 harness 摘要

对方要求 `tasks / prompts / tools / rules / knowledge / ontology` 六键，值均为 64 位 SHA-256。对方仅做格式校验，本项目应做到真实可回查，不能用相同常量填满。

以下是本项目当前录制器冻结的摘要范围，不增加外部协议必填附件：

| 键 | 开始运行前冻结的实际内容 |
|---|---|
| tasks | 本任务定义、允许输入及输入快照引用；不包括隐藏标准答案 |
| prompts | 实际生效的模板、模板版本和生成参数策略；每轮动态消息另见 llm_call |
| tools | 工具白名单、实现/源码指纹、工具 Schema 和相关依赖版本 |
| rules | 本任务实际采用的领域规则、校验策略与修复预算 |
| knowledge | 已授权、实际可用的知识/来源快照及检索资源版本 |
| ontology | 本次开始时使用的本体基线/有效依赖，不是尚未生成的最终本体 |

采用确定性序列化或明确列出文件原字节摘要；注明算法、排序规则、文件摘要与聚合摘要的区别。有意无基线或无知识时，可哈希一个明示 `NOT_APPLICABLE` 原因的真实冻结描述，而不能哈希随意空串假装存在资源。

harness 清单绑定源 commit 与脏工作树源码指纹。开始后配置变化应建立新的运行版本，不覆盖旧哈希。未来输出包与执行文件通过外部关联表绑定，避免“轨迹包含自己的最终打包哈希”或“harness 指向未来产物”的循环依赖。

## 7. 建模审核与运行评价必须分开

`downstream/review.json` 回答“谁批准了哪一版建模内容”；`evolution/reviews/*.jsonl` 回答“某一次运行哪里做得对或错”。二者可以有关联，但对象、权限和用途不同。

必填仅 `review_id / exec_id / verdict / reviewer / ts`；verdict 已确认只取 **pass/fail**。
fail 条件必填 annotations 数组，每项 aspect/severity/comment；未定义最低数量，允许空数组。
pass 可省略 annotations。fail 缺字段在生产提交报错，历史兼容读取告警，不拒绝其他有效行。
aspect：引用准确性、事实正确性、格式合规、完整性、其他；兼容未知 aspect 告警。
severity：info/minor/major/critical。

`violations` 可选数组，每项 code/evidence/suggestion，存在 severity 时仍使用上述严重性枚举；
code 保留人工填写值，不用许可业务码封闭本体问题。`corrected_answer` 保留任意人工 JSON，
不把内部 role/approved 等业务键当授权声明；外层身份仍禁止客户端自报，服务按授权真人核定。
DTO、Worker 保存、界面、JSONL 导出和验证共用这些规则，没有真实人工评价不造 reviews。

exec_id 可指本批先验证成功的执行或由可信调用方注入的历史已知运行。文件中自报的 ID/context
不是信任锚。本项目最小历史边界读取原 JobStore 与 CAS 已提交 strict-v2 导出快照，重核项目、
权限、原始字节与执行事件；这只证明 LOCAL_COMMITTED_EXPORT，不证明对方已收集。
无接收器/回执始终 NOT_CONTACTED，接收端可用性仍待真实回执。
批次验证按文件和 1-based 行号返回 accepted/quarantined，悬空、重复或坏 JSON 行不会吞掉
同文件其他合法评价；有错误时整体报告 BLOCKED，并保留可用行，不假称整个批次已接收。

## 8. 安全、权限与数据隔离

保留当前 `AgentRun` 的低敏哈希审计，不直接把 prompts/source values 塞进该公共审计。新增独立、可配置、受权限控制的内容轨迹存储，并限定导出主体与数据用途。

记录实际发送的消息时不导出 Authorization、API key、Cookie、带秘密的 URL、供应商私有 reasoning 字段。对真实资料明确授权、许可、脱敏和留存策略；未授权不得默认采集全文。

优先在模型输入前完成允许的去标识化，此时日志仍能准确描述实际消息。若对导出轨迹进行后置脱敏或删节，应在关联附件明确 `REDACTED/PARTIAL`、修改范围及可用性，不冒称逐字完整。只有哈希或引用的记录也不能声称满足对方要求的完整 messages。

`tests/`、`acceptance_private/`、人工 corrected_answer、评分 gold 及包含答案的整包 HTML/Word/ZIP、审查报告和 evidence 检查记录 不能挂入运行时生成或修复环境。开发 Agent 可以读合成测试资料以实现代码，但运行时模型只能读生成白名单。目录分开不是权限隔离的证明，应使用真实访问控制并测试不可读。

全交接包含验收资料时只向具有相应权限的接收方导出；一般演进生成流程不能直接访问该整包。生成视图剥离文件后须重新生成其 manifest，不留下悬空引用，也不得声称仍是原归档的完整副本。

## 9. 批次清单和原子投递

`upstream_manifest.json` 在本项目每批必须；历史外部读取仍兼容缺省。清单必填仅 **batch_id / files**，deliverer、ts 可选；
提供 ts 时仍需带时区。每项必填 **name、sha256、size**，不是本体包的 path/size_bytes。
`files=[]` 合法；空 executions/reviews 或没有这些文件都不需补造占位轨迹，校验退出码 0。
仅评价批次依赖可信历史引用，不需重投执行文件。主动不选运行与“所选运行受阻”不同：
录制关闭、删节、程序 turn 缺口必须保留错误，绝不洗成成功空批次。

清单内只列本次给其收集器的轨迹和真实评价文件；额外 context/本体结果由总交接封面绑定，除非对方另行确认这些路径也由其收集器处理。清单缺失可按原文退回目录扫描；清单存在但某个声明文件缺失/摘要或长度不符，必须拒绝该批收集。不要把“可选 manifest 不存在”与“manifest 声明的文件不存在”混为一谈。

文件以 UTF-8 写到 `.tmp`，完成刷新/关闭后在同一文件系统原子重命名。跨机先传 `executions/incoming/` 或 `reviews/incoming/`，完成后移至正式目录。最后原子写 manifest，确保文件不会被半写收集；多批并发必须有批次隔离和锁，不能互相覆盖同一个当前 manifest。

导出后不再修改 manifest 所绑定的文件；重新计算的包使用明确新批次并遵守重复 run 的接收约定。不能改写对方 `collected/` 或 `quarantine/`。

本项目验证器通过只能标本地协议验证通过。没有对方实际收集回执时，状态最多是已导出/待接收，不能写 COLLECTED、已入库或训练可用。

## 10. 必须通过的测试

分别覆盖：真实源数据→原生工件→交换视图的绑定；TTL 图保真；来源和映射闭包；独立答案隔离；过期版本/审核拒绝；执行、验证、审核、发布状态分离；轨迹六类事件必填和状态机；call_id 配对及跨类型唯一；连续 turn 与异步返回；模型失败重试；并行同名工具；取消；硬崩溃未完成文件；缺失用量；manifest 错字节/缺文件/穿越路径；重复运行投递；失败任务无结果包仍能输出可表达的轨迹；真实权限控制与脱敏。

严格 v2 不支持的程序步骤必须有“明确报告兼容性阻塞、没有伪造事件”的测试。附录原文的 warning/error 级别不能在兼容读取器中悄悄改变；可另设更严格的生产者规范，新输出全部遵守。

## 11. 当前项目实现（不追认外部批准）

- `modeling.handoff.import` / `POST /projects/{id}/modeling/handoff-input`：上传 **upstream 子目录内容**组成的 ZIP，不接受包含下游答案/报告的整会议 ZIP。核对摘要、版本、CSV 记录/字段和 Unicode 引文，校验固定领域包基线；进入原生 Source/Batch/Plan/Run。非支持定位种类/外部 imports 明确拒绝。原独立答案不注册成来源，也不自动生成 scope 审批。
- `modeling.handoff.export`：当前 strict session 的 package_id、expected_revision、source_grants、recipient、data_classification。经原 Worker/CAS 重新核验审核与编译绑定，导出原图、原包、执行映射收据、来源/证据闭包和冻结独立答案。`handoff.schema.json` 是单独的项目 Schema。
- `modeling.evolution.export`：batch_id 必填；旧 job_id、profile（strict-v2/local）兼容。省略 job_id 主动导出空批次；可传 review_ids 和 known_run_export_job_ids 导出仅评价批次并从原服务快照核验历史引用。local 或 target_package_id/expected_revision 关联必须选 job_id。所选旧任务未录制返回 TRACE_UNAVAILABLE，程序/删节/不闭合严格出口拒绝；local 是独立诊断 ZIP。运行、评价、批次重复/冲突保护在原 CAS 提交账本内，不是对方收集库。
- `modeling.evolution.review`：需 trace:review/source:read，授权 HUMAN 提交 pass/fail、条件 annotations、可选 violations/corrected_answer。选择旧 job_id，或 exec_id+execution_export_job_id（受信任原服务导出）；客户端不能指定 reviewer。开发单人配置标 SYNTHETIC_ENGINEERING，禁止正式 reviews 导出。已录制但不能 strict-v2 表示的本地运行可留评价，不能因此变成已收集样本。
- 下载 `GET /projects/{id}/handoffs/{export-job-id}/archive` 重新检查任务范围、当前授权和提交快照字节。CLI 的 export-handoff 下载这个同一服务快照，不提供绕过鉴权的本地业务导出入口。
- `assemble-handoff` 可用总封面关联独立结果、已通过本地验证的演进根和诊断目录；三种 manifest 不合并成同一协议。未接收始终 NOT_CONTACTED。

context/run_bindings.json 和 context/harness_manifest.json 可省略；提供时成对核验六类资源、
原生 ID 和执行集合，组合交付还必须通过原生包、确认包、输入、编译依赖和有效祖先检查。
没有 context 的核心批次可 LOCAL_PROTOCOL_VALID，但与本体组合时关联为 NOT_PROVEN_NO_CONTEXT；
包格式 VERIFIED 不代表该关联通过。服务内部记录不会因省略附件而被删除。
CLI `validate-evolution`、`assemble-handoff` 和 `validate-stage` 均可带 `--workspace WORKSPACE --project-id ID --known-run-export-job-id EXPORT_JOB`，
使用 ZHIGOU_TOKEN 重新鉴权后注入历史引用；不接受客户端“已收集”布尔声明。
组合包重读也必须从外部重新注入可信历史引用，不能信任封面自报引用有效。
正式 CLI/API/浏览器下载均使用 `export-handoff`/任务 archive 的同一已提交字节。
本地 `export-evolution` 是协议文件辅助出口，不授予服务授权或接收资格。

编译后，原解析器可能在字节一致副本间选中另一条路径。新出口重新运行原输入证明，
仅允许位置交叉表变化；工件 ID、原字节摘要、内容摘要及其他证明字段仍逐项一致。
不改原生 attestation、IRI、签名或历史摘要。

harness 使用 UTF-8、排序键、紧凑 JSON、末尾 LF 的 SHA-256，清单保存实际资源/代码指纹、
依赖版本与源码 commit/脏树指纹。六类资源在开始前冻结；模型消息在请求边界独立记录。
供应商私有 reasoning 不被读取到公开事件，失败/拒绝公开内容保留。未知 token 字段不填 0。
被过滤内容明确标 REDACTED，严格出口拒绝冒充完整消息。

源数据许可在导出时由具备 source:export 的身份逐项声明并绑定字节；不是自动法律判断。
包内 `tests/negative_cases.json` 无独立本次用例计划时为 NOT_RUN，不把仓库反例回归改名成
该业务包已跑过的反例。发布仍属于 Registry/Release，不由交接出口批准。

文件过滤与进程隔离分别验收。已测 WSL/bubblewrap 真实研究生成/修复进程无法读取
acceptance_private、tests gold、references 整包和 evidence；生产服务 Worker 仍是可信控制面，
没有把整个 Worker 改造成 OS 沙箱。生产模型无任意文件工具，模型输入继续使用既有白名单。
原研究跨进程 LIVE broker 的完整 end-to-end 轨迹合流未在本轮运行；不将录制轨迹称 LIVE。

## 12. 阶段验收与不可变关联

2026-09-16 在已提交 979128e 上扩展到项目 1.1.0：旧 Schema/历史归档不变，兼容只读。
独立负例在原 session.open 时冻结；check 操作消费同一计划，对本次原生包隔离变异，输出实际检测和日志。
export 通过显式 report_id 取结果，不从图猜测试期望，不将缺失/超时/N/A 变成 PASS。
新 cover 与 stage 验证当前有效祖先、输入快照、最终 native package/archive、harness 和真实服务结果引用。
无外部授权回执/可信总 ZIP 摘要的自洽包不授予阶段授权资格。
完整 DTO、摘要算法、版本兼容、同源码验证、总 ZIP 入口和最小协议待确认问题见 [STAGE_CLOSEOUT.md](STAGE_CLOSEOUT.md)。

## 2026-09-29 项目导航响应澄清

`GET /api/v1/projects` / `project.list` 保留项目身份、领域包、权限与路径约束，
但只提供导航元数据。正常项目返回 `status=OPEN` 和
`validation_status=NOT_RUN_BY_LIST_PROJECTION`；旧不完整映射仍返回 `LEGACY_INCOMPLETE`。
这与 `/state` 的运营投影边界一致，不将列表成功当成校验/审批/发布成功。
需要当前完整校验时使用原 `project.open` 或 `project.validate`，所有写入与 Worker 硬门控不变。
三组交付目录、五类成果及原生包 Schema 不受影响。

## 13. 专家闭环内部接口（2026-09-28）

这是原项目/会话/operation registry 的增量，不是演进 v2 第七种事件或第18类交付。
流程/审计主说明在 [AGENT_STEP_AUDIT.md](AGENT_STEP_AUDIT.md#2026-09-28-专家闭环)。

| 原服务入口（项目 toolchain/operation API） | 请求字段 | 权限与绑定 |
|---|---|---|
| modeling.session.open | 原字段 + expert_loop_enabled: boolean | 新工作台设 true；旧 API 兼容旧模式；启用后再 open 不允许 false 降级 |
| modeling.expert.save | expected_revision、expected_configuration_digest、configuration、confirm | 原 model:propose/source:read；认证 HUMAN，S1 另需 scope:approve，其余需 review:decide；全部走 Job/Worker/CAS |
| modeling.expert.reaudit | expected_revision、job_id、candidate_digest、可选 feedback | model:propose/source:read/source:export/package:read/trace:export；意见另需 HUMAN/review:decide；读取原授权审计及提交锚，不能对旧摘要补造正文 |
| 原各阶段计算入口 | 原闭合 DTO 不变 | 已启用 session 自动生成后审核/受限修订；直接 API 同样门控；执行时额外需要现行 model:propose/source:read |
| 原 job.cancel / job recovery | 原字段 | 停止沿用原权限和租约；已提交读原结果；远端未协调模型尝试禁止自动重放 |

configuration 包含 stage、pre_guidance_prompt、post_review_prompt、criteria、method_overrides、budget、
coverage_confirmed。criteria 每项有稳定 criterion_id、description、required、source；方法覆盖仅可覆盖
两份文本，不能借覆盖项删除检查点。作者、确认人、配置摘要、版本和项目范围由服务产生，不接受客户端自报。
budget 中修订轮次、物理请求数、时间、实测 Token 与网络重试分别限定；取涉及配置的保守上限。
反馈绑定认证主体、候选摘要和时间，并经过同一发送前隐私门；合成身份保持 SYNTHETIC_ENGINEERING。

闭环元数据附于结果 expert_loop 和原 session.expert.loops，包括逐 method 的输入/候选摘要、
配置/检查点版本、程序收据、AI 技术结论、patch/diff 摘要、物理调用与 token_usage。
审核/补丁正文仍经原受控通道；默认 METADATA_ONLY 不因此变完整。下载继续检查原权限。
原审计附件新增 audits/expert-loop.json、audits/token_usage.json，源码/动态专家版本放 prompts；
AI 不写 reviews/*.jsonl，不把配置确认当成人工运行评价。
批次 upstream_manifest.json 是本项目生产者每批必须，最后写；batch_id/files 必填结构不扩展。
旧接收兼容读取允许缺 manifest，但不能作为本项目生产者出口验收通过依据。

审计目标为本次业务产物/程序结果，不含本次审核报告、外层 ZIP 或最终批次清单自身，避免自引用。
S4→S2/S3、S5→计划重编译的同作业子结果继续由原提交保存，祖先选择明确 operation+job；
不以同一个 job_id 错配不同子产物，也不新造原生 ID。
三目录组织及本体五类成果不变；可交原服务导出物和独立审计附件，严格 v2 受阻仍明示，
不得以合法空批次声称该受阻运行已完整导出。未接收始终 NOT_CONTACTED。
