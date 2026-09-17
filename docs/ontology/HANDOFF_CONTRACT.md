# 本体结果与演进轨迹交接契约

2026-09-17 新增项目本地 `zhigou-modeling-step-audit/1.0.0` 前后快照 ZIP，见
[逐步审计契约](AGENT_STEP_AUDIT.md)。独立于本体交换/v2，不修改旧 Schema 或历史包。
记录、审批、程序验收、提交和发布仍分别记账。

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
    native/<package-id>.kgop         # 已生成原生包时保留；不伪造
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

本次拟实现的逐文件正式交换视图应使用独立、明确的项目格式标识，例如 `zhigou-ontology-handoff/1.0.0`，并标为本项目约定；不能沿用 `MEETING_REFERENCE_EXAMPLE` 假装实跑，也不能冒充原 `ontology-delivery/3.0.0`。既有生产 v3 Schema 不变。

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

任务执行成功不等于本体语义正确、人工批准或已发布。建议本体任务的 `answer` 使用有类型的结果对象，分别包含产物引用、验证状态、审核状态与发布状态；该对象是**本项目拟议格式，仍需对方评价器适配**，不得硬塞政务许可字段。

`model`、`temperature`、`usage`、`duration_ms` 按实际可用信息记录。将 provider 的 `prompt_tokens/completion_tokens` 对应到 `input_tokens/output_tokens`；未知用量不填 0；不把全部请求 token 与输出 token 错算为输入。未配置或未返回的参数不编造。

## 5. turn、配对、失败与并发

`turn` 是模型调用轮次，不是 S1—S5 编号，也不是工具序号。按原文“从 1 开始、跳跃隔离”执行连续的 1、2、3……；每次真实模型重试开启新轮，两个 Agent 共用该真实运行的轮次分配器。

每次调用分配新 `call_id`，结果复用对应调用的 ID。唯一性约束作用于**调用实例**，不应把配对结果对相同 ID 的引用误判为重复；LLM 与工具调用也不得碰撞。新生产者对所有模型/工具配对均写 call_id，满足并发场景，不依赖位置推断。

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

以下摘要范围是本项目建议：

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

对方人工评价字段为 `review_id / exec_id / verdict / annotations / reviewer / ts`，`corrected_answer` 和 `violations` 可选。新生产者应确保 fail 附带真实 annotations；没有真实人工评价就不生成评价记录，不用程序结果填“审核员A”。

原文只给出了 fail 场景，完整 verdict 枚举继承未提供的 v0；不要假定未展示的所有枚举都已确认。接入时读取接收方实际 Schema，或在协议确认记录中固定完整枚举。

aspect 已列出：引用准确性、事实正确性、格式合规、完整性、其他。severity：info/minor/major/critical。对方 violations 现有码包含 `citation_unverified / bad_law_ref / bad_decision / answer_not_object / status_answer_mismatch / empty_answer / assess_error / decision_reasons_missing`。

这些违规码明显含政务许可语义，不能把 SHACL、IRI 或 OWL 错误全部映射成 bad_law_ref。未匹配的本体问题先保留到自身 validation 与人工 annotations 的准确描述；新增 ontology 违规码、自动评价对象和任务 answer Schema 必须单独确认。不要伪称对方现有评价器已经支持本体建模。

## 8. 安全、权限与数据隔离

保留当前 `AgentRun` 的低敏哈希审计，不直接把 prompts/source values 塞进该公共审计。新增独立、可配置、受权限控制的内容轨迹存储，并限定导出主体与数据用途。

记录实际发送的消息时不导出 Authorization、API key、Cookie、带秘密的 URL、供应商私有 reasoning 字段。对真实资料明确授权、许可、脱敏和留存策略；未授权不得默认采集全文。

优先在模型输入前完成允许的去标识化，此时日志仍能准确描述实际消息。若对导出轨迹进行后置脱敏或删节，应在关联附件明确 `REDACTED/PARTIAL`、修改范围及可用性，不冒称逐字完整。只有哈希或引用的记录也不能声称满足对方要求的完整 messages。

`tests/`、`acceptance_private/`、人工 corrected_answer、评分 gold 及包含答案的整包 HTML/Word/ZIP、审查报告和 evidence 检查记录 不能挂入运行时生成或修复环境。开发 Agent 可以读合成测试资料以实现代码，但运行时模型只能读生成白名单。目录分开不是权限隔离的证明，应使用真实访问控制并测试不可读。

全交接包含验收资料时只向具有相应权限的接收方导出；一般演进生成流程不能直接访问该整包。生成视图剥离文件后须重新生成其 manifest，不留下悬空引用，也不得声称仍是原归档的完整副本。

## 9. 批次清单和原子投递

对方 `upstream_manifest.json` 的字段为 `batch_id / deliverer / ts / files`；每项使用 **name、sha256、size**。这是对方字段，不是原本体包的 path/size_bytes。

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
- `modeling.evolution.export`：job_id、batch_id、profile（strict-v2 或 local）。关闭录制的旧任务返回 TRACE_UNAVAILABLE，不能反推 prompt。`local` 是诊断 ZIP，不含伪造 upstream_manifest。完整严格出口遇到程序轮次缺口、删节或不闭合时拒绝。
- `modeling.evolution.review`：真实身份提交 fail 与 annotations，需 trace:review 和 source:read。只实现原附件已明确的 verdict=fail；其他 verdict 等待完整 v0/接收器 Schema。开发单人测试配置的评价标 SYNTHETIC_ENGINEERING，禁止作为正式人工样本导出。暂未增加 corrected_answer/violations 提交 UI。
- 下载 `GET /projects/{id}/handoffs/{export-job-id}/archive` 重新检查任务范围、当前授权和提交快照字节。CLI 的 export-handoff 下载这个同一服务快照，不提供绕过鉴权的本地业务导出入口。
- `assemble-handoff` 可用总封面关联独立结果、已通过本地验证的演进根和诊断目录；三种 manifest 不合并成同一协议。未接收始终 NOT_CONTACTED。

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
