# 知构工具链 · ZhiGou Toolchain

2026-09-29 全仓回归修复：项目列表改为同一目录快照的授权导航投影，明确不代表语义校验；
显式校验、Worker、审核与发布门控不变。历史证据保留原字节归档，并提供标记脱敏的展示视图。
原因、修复与新冻结验证入口见 [回归修复说明](docs/ontology/REGRESSION_REPAIR_20260929.md)。
最终测试结论只写新的独立运行回执，旧失败不改写。

2026-09-30 按最新需求改为[三场景 Prompt 预设](docs/ontology/ONTOLOGY_MODULE.md#2026-09-30-场景-prompt-预设)：
企业组织与人员、古树档案与巡查、设备资产与维护；选择场景后查看五阶段生成/审核模板。
已移除逐步粗细度、覆盖/恢复控件及执行档位分支，原来源映射、专家闭环和安全门控保持。
旧配置必须显式迁移并从 S1 重审；历史记录和导出包不追改。新验证写
`runtime_reports/scenario-prompts-20260930/`，不借用此前全仓通过结论。

2026-09-28 增量加入[专家指导、AI 审核与有界修订](docs/ontology/AGENT_STEP_AUDIT.md#2026-09-28-专家闭环)：
沿用五阶段、两个计算角色、候选、Worker/CAS 和人工审批。工作台新建闭环会话必须确认各阶段
指导/审核版本，旧会话不追改；真实请求、逐轮问题和 Token 仍走原受控审计。
十份默认模板及共用修订模板由执行源码生成到原 Prompt 目录，默认不是已确认专家意见。
本次验证使用新目录 `runtime_reports/expert-loop-20260928/`；实际结论看冻结后回执，不复用历史 PASS。

2026-09-24 新增[逐运行 Token JSON 审计器](docs/research/token-audit-json-2026-09-24.md)：
独立只读观察原账本，自动输出每次调用、每一步与全程用量，分开标注建模/测试用途和 benchmark 场景。
未知值保留 null，预算预留不算实际用量；不修改当前冻结生成器、原报告或生产权限。

2026-09-24 用户确认后已[恢复主机重启中断的全量队列](docs/research/host-reboot-continuation-2026-09-24.md)。
独立冻结控制v4将指定调用保留为中断/远端未知，不重试、不退款，不伪造响应或用量；
原r8生成器和预算不变。114项相关检查及重启后的新隔离复验通过，后续新作业已实际生成。

同日后续：[样本本地隐私拒绝隔离](docs/research/local-private-veto-isolation-2026-09-23.md)
以新冻结控制v3保留被拒样本为FAILED，仅继续其他样本；原隐私门和生成器不变，
独立离线HTTP spy证明不用于回填历史usage或退款。89项相关工程检查通过，非正式研究成绩。

2026-09-23 用户明确授权后已[恢复原本体全量队列](docs/research/terminal-transport-continuation-2026-09-23.md)。
独立冻结的续跑控制保留原 r8 生成器、失败、三次尝试上限与总预算；终态临时传输失败
留档后继续其他作业，不增加第四次重试。实际新作业已生成，正式全量质量统计尚未完成。

可组合、可验证、可追溯的本体工程工具链（Ontology Toolchain）。以独立领域包提供业务语义，
将资料接入、五步本体建模、服务与版本管理、任务执行和反馈演进连接到同一个授权服务和 Worker。

当前源码版本 0.9.0rc2；本地增量不等于正式发行资格。受测源码与真实结果见
[升级索引](docs/upgrade/research-module-map.md)、[实施边界](docs/upgrade/modeling-five-stage.md)及
[验证记录](docs/upgrade/verification.json)。历史 PASS 只适用于原修订。

原模型与多模态的追加实测、固定输入及模型能力差异见
[原模型与多模态验收](docs/upgrade/original-models-multimodal.md)。

## 本体建模与交接（2026-09-18 按 01–17 对齐）

2026-09-19 增量以方法及物理模型请求核账：
[审计、配置与权限](docs/ontology/AGENT_STEP_AUDIT.md)、
[当前实际 Prompt 全文（源码生成）](docs/ontology/MODEL_CALL_PROMPTS.md)。
沿用审计 API/Worker/CAS，支持会话、产物和尝试筛选；历史摘要不能还原请求。
本轮验证写 `runtime_reports/ontology-audit-20260919/`，不复用旧通过结论；
MockTransport/纯程序与 LIVE 分开，严格 v2 程序 turn 与外部接收仍分别报告。

沿用 01–08 输入、09–14 本体成果、15–17 演进数据三组，工作台点击展开查看，
不增加新的核心交付类别。唯一详细字段入口是[交接契约](docs/ontology/HANDOFF_CONTRACT.md)，
逐项生产者/API/验证/测试对应见 [需求追踪](requirement_traceability.md#2026-09-18-0117-统一对应表)。
运行评价支持 pass/fail、条件 annotations 与可选 violations/corrected_answer；
空批次和有可信历史引用的仅评价批次复用原 Worker/CAS 和任务下载。
可选 context 缺失不影响基础协议有效性，但不能证明运行与本体成果关联。
人工身份由服务核定，合成测试评价不能作为正式 reviews 导出。
本轮冻结回执与新建 HR/林业成果在 `runtime_reports/alignment-20260918/`，不借用旧回执。

用户已确认“名称更新版_20260918.zip”作为本轮“精简版”参考，缺件事项已关闭。
[参考身份](docs/ontology/references/handoff-17.reference.json)锁定实际原字节 SHA，
[原件副本](docs/ontology/references/handoff-17-20260918.original.zip)仅供授权开发/验收核对；
含独立答案，不能整包提供给生成或修复模型。文件名用途确认不改写旧 ZIP、旧摘要或历史失败。
此次在 develop@d2dbd514 上继续核对，最新回执在 `runtime_reports/alignment-reference-20260918/`。
验证器支持直接脚本与模块入口，完成新的源码冻结后可运行：

```powershell
python -m tools.verify_stage_handoff runtime_reports/new-reference-verification --baseline PATH_TO_CLEAN_BASELINE --parallel-full --input-archive docs/ontology/references/handoff-17-20260918.original.zip
```

2026-09-17 新增[双 Agent 与逐步审计](docs/ontology/AGENT_STEP_AUDIT.md)：工作台按
“规划 Agent（RuleAgent，S1/S2/S4）／任务执行 Agent（S3/S5）”组织现有步骤，
真实操作和工具调用保存处理前后文件，支持失败与历史尝试审计 ZIP 下载。
演示启动加 `--record-step-content` 显式启用受控正文；默认仅摘要，旧内容不补造。

阶段收口扩展见 [阶段验收与真实打包](docs/ontology/STAGE_CLOSEOUT.md)：新增生成前冻结的负例计划、
真实校验结果、有效祖先与原生包绑定、1.1 交换格式，以及 `validate-stage` 独立总 ZIP 验包。
`verify_stage_handoff.py` 完成代码/文档后冻结全文件范围，输出独立实际回执，不更新旧历史结论。

模块职责见 [本体模块说明](docs/ontology/ONTOLOGY_MODULE.md)，文件与协议见
[交接契约](docs/ontology/HANDOFF_CONTRACT.md)，本轮状态与证据见
[实施记录](docs/ontology/IMPLEMENTATION_STATUS.md)。原方案、协议和会议样例均保留，
会议样例不等于真实运行，历史审查也不等于当前代码状态。

保留 RuleAgent（S1/S2/S4）与 TaskExecutionAgent（S3/S5）。数据组只提供数据、
来源和质量，业务方确认规则，验收方独立提供答案；本体模块不重建演进组训练平台。

新增真实 Source/Batch/Run 输入适配、`zhigou-ontology-handoff/1.1.0` 结果出口（1.0 只读兼容）、
受控内容轨迹、演进 v2 本地验证/原子批次和独立人工评价接口。
新交换格式不是原 v3，也不是原诊断包改名；`.kgop`、稳定 IRI、原 v3 Schema 不变。
第五阶段提供本体交接包和演进数据包入口，失败任务可从任务中心导出本地轨迹诊断。

```powershell
python -m zhigou_toolchain.modeling.delivery.cli validate-handoff path/to/ontology-handoff.zip
python -m zhigou_toolchain.modeling.delivery.cli validate-evolution path/to/evolution --producer
python -m zhigou_toolchain.modeling.delivery.cli inspect-input path/to/upstream
python -m zhigou_toolchain.modeling.delivery.cli export-generation path/to/upstream path/to/new-generation-view
# 从已完成的服务导出任务下载同一份字节；身份沿用 ZHIGOU_TOKEN，不在命令中填写密钥。
python -m zhigou_toolchain.modeling.delivery.cli export-handoff path/to/new-output.zip --workspace path/to/service --project-id PROJECT_ID --job-id EXPORT_JOB_ID
```

内容录制默认关闭。服务与 Worker 显式设置 `ZHIGOU_ONTOLOGY_TRACE_ENABLED=true`，
且执行身份具有 `trace:record`、`source:read` 时才录制。导出另需 `trace:export`。
本体交接需 `package:export`、`source:read`、`source:export`、`acceptance:export`，
并逐来源确认摘要、许可、授权依据和接收人。许可声明不冒充法律核验。
完整交接包含独立答案，禁止作为生成侧输入；白名单文件导出本身不是 OS 沙箱。

首次模型前和纯程序工具调用无法完整表达为对方严格 v2：保留真实本地日志并明确阻断，
不伪造模型或 turn=0。没有真实人工评价不生成 reviews；接收器与本体评价器尚未联调。
无付费授权的完整后端验证使用：

```powershell
python tools/verify_zhigou_upgrade.py --backend-only --workers 4 --skip-model-probe
```

## Windows 本地启动

在项目根目录运行。现有环境可以直接使用；首次安装按锁文件准备依赖：

```powershell
$env:PYTHONUTF8 = "1"
python -m pip install -c requirements-dev.lock -e ".[dev,modeling-analysis]"
npm --prefix workbench ci
npm --prefix workbench run build
python tools/prepare_reasoner.py
python tools/start_zhigou_demo.py --port 8765
```

本地入口：[http://127.0.0.1:8765](http://127.0.0.1:8765)。默认使用已构建的前端，
API 与 Worker 在同一**隔离合成工作区**启动。端口被占用会报错，不会杀其他进程；
也可省略 --port，使用启动信息返回的可用端口。

启动只打印 URL、工作区与临时凭证文件路径，不打印密钥。读取该本地文件的 token 并在登录页输入；
不要把凭证复制到日志、Git、截图或远端。Ctrl+C 只停止此次启动的服务器/Worker并撤销临时身份。
此方便入口的全权限身份仅用于合成演示，不应用于生产或真实用户数据。

首次登录创建 hr@0.1.0 或 forestry-workorders@0.1.1 项目，在“数据接入与规则化”加载
当前领域包的合成批次，也可上传自己的授权测试文件。加载仅进行真实规则化，不自动批准或发布。
详细操作见 [walkthrough](docs/upgrade/walkthrough.md)。

## 独立服务方式

与原服务方式兼容；需管理员明确签发最小权限身份。两个终端使用相同 workspace/config：

```powershell
$env:ZHIGOU_SERVICE_HOST = "127.0.0.1"
$env:ZHIGOU_SERVICE_PORT = "8765"
$env:ZHIGOU_ALLOW_INSECURE_LOOPBACK_SESSION = "true"
$env:ZHIGOU_DOMAIN_PACKS_ROOT = (Resolve-Path domain_packs).Path
$env:ZHIGOU_WORKBENCH_ROOT = (Resolve-Path workbench/dist).Path
$env:ZHIGOU_REASONER_JAR = (Resolve-Path third_party/downloads/robot-1.9.7.jar).Path
python -m zhigou_toolchain service serve --workspace runtime/zhigou-local
# 另一终端，使用相同环境设置：
python -m zhigou_toolchain service worker --workspace runtime/zhigou-local
```

HTTP 明文例外严格限 loopback。非本地部署使用 TLS、明确 Origin 和生产多角色审核。
示例只读身份签发命令（输出包含秘密，只在安全终端执行）：

```powershell
python -m zhigou_toolchain service token create --workspace runtime/zhigou-local --principal-id local-reader --created-by local-admin --permissions project:read,source:read,package:read
```

不要为了通过测试关闭鉴权、延长为永久会话或给真实用户全权限。
本轮验证环境为 Windows；Linux/外部部署若无对应运行证据应视为未测。

## 五个主模块

| 模块 | 实际职责 |
| --- | --- |
| 数据接入与规则化 | Source/Batch/Plan/KG-IR、类型化来源、质量与处理轨迹；独立评测 |
| 本体建模 | 输入核验与范围确认；本体复用与结构设计；数据映射与事实构建；联合校验与人工审核；语义编译与交付验收 |
| 本体服务与版本管理 | 原 Registry/Release、固定版本 OMS/对象读取/证据、环境选择与回滚 |
| 任务规划与业务执行 | 声明式领域策略通过 OMS/对象服务生成固定版本计划，只执行登记动作并重读真实工单 |
| 反馈评估与演进 | 实际执行反馈、隔离回归、人工审核、执行配置更新和回滚；本体变更仍走原版本流程 |

新版严格建模会话冻结输入、规则、配置和独立答案，后端传播 STALE，拒绝旧审核与旧计划。
五步页面不再显示 25 个小步骤或独立案例教程；旧教程 URL 重定向到建模入口。
技术详情、来源和历史收据仍可追溯；原方法台账作为历史文件保留。

## 测试与证据

```powershell
python -m ruff check .
python tools/check_types.py
python tools/evaluate_research.py --suite safety
python tools/evaluate_research.py --suite ontology
python tools/evaluate_research.py --suite framework
python tools/evaluate_research.py --suite ingestion
python tools/evaluate_research.py --suite evolution
python tools/run_backend_tests.py
npm --prefix workbench run lint
npm --prefix workbench run typecheck
npm --prefix workbench test
python tools/run_browser_verification.py --selected-test zhigou-console.e2e.ts
```

独立测试与完整回归分别记账。实际浏览器测试启动真实 API 和 Worker，不 Mock 核心服务。
合成 HR/古树工单仅证明工程链；不证明研究目标达成、实际专家准确率或外部上线。
数值目标、运行方式与适配边界见 [模块契约](docs/upgrade/module-contracts.md)。

较长 Windows 工作目录中的嵌套 Git 测试需为本次验证进程启用长路径。
以下设置保留已有进程级 Git 配置，不修改全局 Git 配置：

```powershell
$zgGitConfigIndex = 0
if ($env:GIT_CONFIG_COUNT) { $zgGitConfigIndex = [int]$env:GIT_CONFIG_COUNT }
[Environment]::SetEnvironmentVariable("GIT_CONFIG_KEY_$zgGitConfigIndex", "core.longpaths", "Process")
[Environment]::SetEnvironmentVariable("GIT_CONFIG_VALUE_$zgGitConfigIndex", "true", "Process")
$env:GIT_CONFIG_COUNT = [string]($zgGitConfigIndex + 1)
python tools/verify_zhigou_upgrade.py --backend-only --workers 4
```

该入口记录源码前后摘要、完整测试收集与执行节点、真实退出码；不因局部复测通过抹去原失败。

## 模型配置与限制

可选服务端配置：ZHIGOU_QWEN_ENDPOINT、ZHIGOU_QWEN_MODEL、ZHIGOU_QWEN_REVISION，
以及必要时的 ZHIGOU_QWEN_API_KEY。模型目录/修订必须明确，不在运行时偷偷下载。
若未配置 Qwen，可使用已有 OPENAI_BASE_URL、OPENAI_TEXT_MODEL、OPENAI_API_KEY 和 OPENAI_RESPONSE_FORMAT。
兼容网关的 json_object 输出仍经过本地 Schema、引用、逐字引文与原语义门检查；不是服务端严格 Schema 证明。
部分 Qwen 配置存在时不静默回退；未配置/无效调用明确失败，不用关键词规则冒充模型推理。
第二/三阶段可显式运行两轮建模和文本抽取，第四阶段可请求白名单修复与自动重验；
LIVE 提案同时要求 model:propose 和 source:read。新候选仍必须重新人工审核，不能直接发布。

```powershell
python tools/probe_upgrade_models.py
python tools/verify_live_assistance.py --pack hr
python tools/verify_live_assistance.py --pack forestry-workorders
python tools/verify_live_assistance.py --pack repair
```

以上验证只使用独立合成数据，记录真实调用及失败，不向生成/修复流程提供冻结的标准答案。
若额度耗尽且用户已授权，可在确认网关开放后为新的服务进程切换 OPENAI_TEXT_MODEL；
模型变更记录在新请求收据中，不把替代模型标为原模型。本任务已确认网关列出 gpt-reserve，
但模型列表本身不证明具体账号的计费路由或模型权重修订。

DETERMINISTIC、RECORDED、LIVE 分开记录。BGE-M3/FAISS/reranker、完整两轮复用、
无基线新建、模型补丁和音视频/OCR 的实际完成范围见 [五步能力与边界](docs/upgrade/modeling-five-stage.md)。
未完成正式标注/专家测试时，研究指标为 INSUFFICIENT_EVIDENCE，不能用工程全绿替代。

## 兼容和迁移

Provider 只生成候选；Recorded Provider 不是 Live LLM。EXPERIMENTAL 领域包只提供实验资产。
Ontology Package 的 VALIDATED_UNPUBLISHED 表示验证后未发布，CONTROL_PLANE_SELECTED
只表示本地控制面版本选择，不证明外部部署。Attestation 绑定受测输入与执行证据，
CAS 保护并发提交；两者都不能代替真实专家审核或研究指标验收。

唯一实现是 zhigou_toolchain；旧 kg_mnp 导入及 kg-mnp CLI 保留薄兼容入口。
ZHIGOU_ 与 KG_MNP_ 环境变量冲突会明确报错，不回显秘密。
稳定 IRI/URN、manifest_kind、旧包摘要、签名、.kgop 和合法 MNP 领域内容不因更名改写。
详见 [迁移报告](docs/upgrade/migration-report.md)和 [旧名保留清单](docs/upgrade/legacy-name-allowlist.md)。

当前远端仍为原仓库，未更名、未推送、未合并、未发布。
本地品牌/代码迁移与 GitHub 原地更名是两个独立状态，不把目标链接当作现存仓库。

以上 Git 状态描述属于前序迁移验证记录。2026-09-13 用户已另行授权将当前全部改动
集成到 develop、同步 main，并在确认提交均已保留后仅保留这两个分支。
该授权不改变功能缺口或研究结论；当前提交的 CI 状态以 GitHub Actions 检查为准。

## 双 Agent、v3 与独立本体 I/O 评测（增量实现）

2026-09-21 按用户指定对 GPT-5.6 Luna 完成一次真实恢复诊断：模型可调用，但当前网关
仍未执行输出硬上限（请求128、返回1026 completion tokens）。仅新增一次合成诊断，
不属于 benchmark 成绩；原预算、历史调用与 STOP 保留，full 未恢复。
实现、回执与继续条件见 [Luna 恢复诊断](docs/research/luna-recovery-2026-09-21.md)。
随后经授权在隔离临时 Cockpit 实例补回限额字段，上游返回HTTP400、
`Unsupported parameter: max_output_tokens`。临时实例已停止，正式网关原样保留；
这是当前OAuth路由的能力阻塞，不能用客户端裁剪冒充硬预算。
见 [网关修复尝试与上游实测](docs/research/cockpit-gateway-repair-2026-09-21.md)。
随后按用户要求对localhost:51900的Luna/Astra及Chat Completions/Responses完成8次新实测：
全部HTTP200、四项中文JSON通过，但四项128-token限额均未被执行。接口可用不等于原预算协议合格。
原finalize新增质量分、绝对/相对变化及配对95%CI导出，跨任务/基线统一Holm校正；
没有完整预测仍拒绝正式评分。详细结果见 [接口复测与质量报告补齐](docs/research/endpoint-recheck-2026-09-21.md)。
用户随后确认继续当前接口并调整原预算协议；新 [本地用量监控协议](docs/research/monitored-budget-2026-09-21.md)
使用同一总账本，保留旧失败和STOP，按新授权/新冻结revision运行Luna。
单次上限为请求建议而非网关保证，未知用量/新超额停机；不能把协议恢复写成完整质量实验已完成。
随后用户授权启动并完成所有全量。r2 pilot的一次120秒ReadTimeout已保留；
新 [全量运行方案](docs/research/full-launch-2026-09-21.md) 使用300秒请求超时、最多三次
仅网络故障尝试、完整尝试/费用台账及自动阶段推进。所有冻结全量位置保留，
生成与评分完成分开判断；CQ2Onto评分缺口不被伪称已解决。
r3随后在pilot的Reuse上下文构造处停止（17成功、1次零模型调用预算拒绝）。
新研究请求视图用可逆卡片索引/列式目录去除重复载荷，不裁剪来源或扩大预算；
原始检索/复用结果仍保留。详见[上下文修复回执](docs/research/context-repair-2026-09-21.md)。
r4遇到上游HTTP408后保留未知用量并停机；新冻结版本将408补入已有有限传输恢复名单，
不增加尝试次数或预算、不重试语义/鉴权/额度错误。状态见[408恢复记录](docs/research/http408-recovery-2026-09-21.md)。
r5有一个合成smoke在引用修复中清空了原预测，被原空修复防护拒绝。
新版本仅增强[原文定位反馈](docs/research/evidence-repair-2026-09-22.md)，提供来源精确位置候选，
不自动改事实、引用或评分答案，原空修复/歧义/预算门均保留。
r6 pilot的53条事实/54条引用暴露了两套索引和模型偏移的脆弱性；新冻结研究模式
[事实与引用耦合](docs/research/quote-coupling-2026-09-22.md)让每条事实携带原文quote，
由原程序严格唯一匹配计算位置，缺失/歧义仍失败；旧模式与旧失败不改写。
r7 Reuse预检揭示“新增词汇提案”未与任务已提供词汇闭包，导致复用项被错挡。
新[词表衔接修复](docs/research/vocabulary-repair-2026-09-22.md)保留输入词汇与原模型提案，
真正未知词仍拒绝并交回S2，不自动放行S3新词、不删除旧失败或扩预算。

已接入后端角色/工具审计、只读 v3 检查、原生包兼容预检、固定外部资源输入适配、
原生评分函数回归及研究报告页面。完整原生→v3 正式导出、全部 TwoAgentV3 研究内核、
强进程沙箱与真实外部对比尚未完成；工程通过不等于语义准确率达标。

可执行命令与明确限制见 [本体 I/O 运行说明](docs/upgrade/ontology-io.md)，
资料—方法—实现—测试记录见 [需求追踪](requirement_traceability.md)。
