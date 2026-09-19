# 2026-09-16 交接改造实施记录

## 2026-09-18 参考版本确认续办（当前）

用户明确要求以“名称更新版”作为本轮“精简版”进行内容对齐，原附件待补事项已关闭。
实际原件名称、SHA 和与旧 Prompt 摘要的差异锁定于 references/handoff-17.reference.json，
归档副本原字节保留。它仍是说明/合成输入参考，不是成果或批准记录，不整包提供给模型。
当前 HEAD 为干净 develop@d2dbd5147e793ea47e1f15c4093536047b330f58，已包含前轮 01–17 实现。
复核 Markdown、HTML、Excel 与当前核心字段后无需再建业务协议；本次修正参考身份判定、
工作台用语和当前文档，并修复上一轮直接启动验证器时最终归档无法导入 tests 的入口问题。
新增原件摘要、包内完整性、Excel/HTML 17 项编号、Markdown/校验器六事件字段、生成白名单
与直接入口子进程回归；隔离测试加入此新原件的实际不可读检查。

全部变更完成后重新冻结，结果以 `runtime_reports/alignment-reference-20260918/frozen-run-01/`
中的源码快照、实测报告和新成果为准。前轮完整回归与归档失败/续办证据保持不变，
不将旧源码指纹或旧回执作为本次新源码验收。字段规范仍统一维护在 HANDOFF_CONTRACT.md。

## 2026-09-18 前轮增量：01–17 字段与全链路对齐（历史）

从干净 develop@9f6c0368654bd72f82df1c18ef52fe74b762fd83 开始，不回退。
已修改演进事件/评价/批次校验、DTO、Worker 服务、CLI 和工作台；保留双 Agent、负例、
祖先关联、原生格式、权限和逐步审计。字段仅在 HANDOFF_CONTRACT.md 维护，逐项表见需求追踪。
新评价支持 pass/fail 和可选修正；合法空批次/仅评价批次走同一提交下载路径。
历史引用来自原已提交导出，始终与“外部已收集”分开；可选 context 缺失不取消内部真实性门。
answer 改为实际结果（受隐私过滤），旧摘要不补造。无真人评价不生成正式 reviews。

以下是用户此次确认之前的原始核账，不是当前待补事项：
指定“字段对齐精简版”ZIP（预期 SHA bbcf5bbf…）当时未在下载/仓库引用目录找到。
已读并实跑另一份“名称更新版”ZIP，SHA-256 为
`be5d0c703a923d095e901991b0fc507049f5458471f0b8f7711f33b7417e8094`，62153 字节；
说明、Excel 和上游样例按补充资料核对，不称已收到原指定附件。其历史 194e091/hr@0.1.0
引用未改写；仅 upstream 进入真实 Source/Batch/Run，14 个原文件原字节核验。
独立答案未进入生成源；新原生运行 ID 由真实服务生成，未授予审批。

预检发现三个新增测试夹具的 quality checked_files 未随合成子集更新，真实质量门正确拒绝；
原失败保留于 `runtime_reports/alignment-20260918/preflight-protocol.xml`。只修正新建测试夹具，
未改原附件、历史质量结果或生产门槛。后续预检回执为 preflight-protocol-02.xml。

frozen-run-01 在完整回归前由新增只读协议探针发现评价 bytes 解码会自动接受 UTF-16，
已停止资格流程并保留 ABORTED.json 和原源码快照；显式 UTF-8 解码及保留同文件合法行的
回归修复后使用新目录冻结。此失败不会改写成 PASS。

frozen-run-02 在完整回归前的组合包探针发现历史引用未透传到 cover/assemble-handoff，
已保留 ABORTED.json；补齐与 validate-evolution 相同的重新鉴权引用入口和 CLI 回归后再冻结。
封面不能通过自己的“有效”声明授信，重读仍需包外可信引用。
同期预检的阶段测试跨越了开发修改，被 STAGE_TRACE_SOURCE_BYTES_MISMATCH 正确拒绝；
记录为 preflight-stage-mixed-source.json，不将其当成最终冻结结果。新增阶段检查也参与
最终模块结论，不能忽略审计/浏览器/附件检查的实际失败。

全部修改后用 `verify_stage_handoff.py` 冻结，专项、完整后端、前端、真实浏览器及 HR/林业新服务链
写入 `runtime_reports/alignment-20260918/frozen-run-*/`。以该目录实际 source-snapshot.json、
stage-verification.json、full-regression-summary.json、FINAL_REPORT.md 为准，不在冻结文档预填 PASS。
已有卫生失败单独与干净 9f6c036 复现核账，绝不将全仓 FAIL 写成 PASS。
严格 v2 程序 turn 仍受阻，真实模型/真人运行评价/外部接收未执行，NOT_CONTACTED 不阻止本体交付。

以下 2026-09-16/17 的结论保持历史含义；其中 fail-only/verdict 未确认描述已由上述新字段覆盖。

## 2026-09-17 新任务：双 Agent 与处理前后审计

新增规划/任务执行 Agent 界面、服务与工具前后文件、显式内容捕获和受限 ZIP 下载。
实现与命令见 [AGENT_STEP_AUDIT.md](AGENT_STEP_AUDIT.md)，新回执在
`runtime_reports/agent-step-audit-20260917/`。新源码不借用上一轮指纹作为回归证明。
没有新增付费调用、正式审批或发布授权；以下历史记录保留，不追改结论。

> 下文为上一轮历史记录。当前已提交基线是 develop@979128ee16746cd124aca29257a23910e8edcea0，
> 并非仍“未提交”。本轮阶段收口接口及冻结规则见 [STAGE_CLOSEOUT.md](STAGE_CLOSEOUT.md)；
> 新的实际验收报告写入 runtime_reports/stage-closeout-20260916/，不覆盖下方旧回执。

基线：develop@194e091d13cabba5833ff1d531f814858ea968ae；开始时工作树干净。
用户要求实际完成 ZIP 中的交接改造；附件是需求材料，不是额外授权。

## 工作计划

- [x] 核对基线、读取需求、保存协议原件与历史审查。
- [x] 薄输入适配与同次运行绑定；独立的本体交换格式与验证器。
- [x] 可配置受控 TraceRecorder、真实模型/工具边界与六类 harness。
- [x] 严格 v2/兼容读取验证、原子批次与稳定 ID、人工评价分离。
- [x] 现有 operation/API/Worker 权限与下载接入；第五阶段和失败作业入口。
- [x] 新模块、HR/林业真实本地服务、OS 隔离与实际浏览器验收。
- [x] 完整回归执行并核账；最终小增量另外专项验证，不冒称同一最终源码全仓认证。
- [x] 更新 README/契约/需求追踪，保留协议差异和原始资料。

## 不变边界

不修改原 v3 Schema、原生稳定 ID、签名或历史证据。不自动提交、推送、发布、
付费调用模型或重启旧实验。不把录制/合成检查标成 LIVE、人工审核或对方接收。
严格 v2 未定义首次模型前/纯程序工具轮次；保留真实本地记录并阻断受影响出口。

## 执行证据

## 已实现的实际路径

1. 会议 **upstream 子目录 ZIP** → 摘要/版本/CSV 与 Unicode 定位/许可检查 → 原 Source/Batch/Plan/Run → KG-IR/Evidence。输入原引用与新原生 ID 保留关联；独立答案不注册为来源，原会议 CQ 不冒充已登记查询。
2. 原 session → 原五阶段/审核/共享编译 → 已验证 `.kgop` → 新逐文件视图；来源授权、同批次证据、业务规则、独立答案、审核和编译交叉核对。原图与原包字节不变。
3. `AgentRun.call` 的真实工具边界，以及 Qwen/Compatible 的实际 POST 和公开响应 → 可选私有 journal。GET models 不算推理；Schema 拒绝仍保留请求/公开输出。研究 engine 可显式 `record_trace=True`；录制重放是 `recording.replay` 工具，不是虚构 llm_call。
4. 严格 v2 验证 → executions/reviews/upstream_manifest + context；纯程序/前置工具转为明确协议阻塞，仍可导出本地诊断。批次采用原子目录/文件、manifest 最后写、本地重复投递账本，既有冻结输出不覆盖。
5. 所有业务出口走 operation registry → API → Worker → 现有授权/CAS/租约提交 → 任务绑定下载；前端不拼正式 ZIP。CLI 下载同一已提交快照。

## 可复现命令

```powershell
python -m pytest tests/upgrade/test_evolution_delivery.py tests/upgrade/test_meeting_handoff_input.py tests/upgrade/test_handoff_delivery.py -q
python -m ruff check .
python tools/check_types.py
npm --prefix workbench run lint
npm --prefix workbench run typecheck
npm --prefix workbench test
npm --prefix workbench run build
python tools/verify_handoff_isolation.py runtime_reports/new-handoff-isolation
python tools/verify_zhigou_upgrade.py --backend-only --workers 4 --skip-model-probe
python tools/evaluate_research.py --suite ontology
```

隔离验证输出目录必须不存在，使用本机已准备的 Ubuntu-24.04/bubblewrap/固定推理器；
不下载模型、不使用模型凭证。其他平台缺环境应记 NOT_RUN，不静默变成普通进程。

实际浏览器使用完成的**合成测试工作区**（测试会新增导出，不审批/发布）：

```powershell
python tools/run_browser_verification.py --selected-test handoff.e2e.ts --existing-upgrade-workspace path/to/upgrade-hr0 --startup-timeout 90
```

研究内核录制轨迹可独立复现（非 LIVE）：

```powershell
python tools/evaluate_research.py ontology-io replay tests/fixtures/ontology_io/kernel/primitive-input.json config/ontology_io/protocols/kernel-engineering.yaml tests/fixtures/ontology_io/kernel/primitive-recording.json runtime_reports/new-recorded-handoff --system TwoAgentKernelV1 --record-trace
```

## 已完成检查与原始回执

| 检查 | 实际结果 | 证据 |
|---|---|---|
| 初轮轨迹/输入/旧传输与角色 | 39 项通过 | runtime_reports/handoff-20260916/unit-tests.xml |
| 增补协议与原服务权限/CAS/租约 | 48 项通过 | runtime_reports/handoff-20260916/safety-tests.xml |
| HR/林业真实服务与原生→交接→下载 | 3 项通过（之后增加失败轨迹用例，最终回归单独记） | runtime_reports/handoff-20260916/service-tests.xml |
| 新轨迹、原角色与研究内核 | 69 项通过 | runtime_reports/handoff-20260916/trace-kernel-final.xml |
| 最后运行模式/输入/权限专项 | 59 项通过（含 Recorded Provider 标记修正） | runtime_reports/handoff-20260916/final-focused.xml |
| 前端 | 最后 46 项通过，TypeScript/ESLint/build 通过；包括异步导出失败的准确状态 | 本轮实际命令输出；浏览器见下一行 |
| 真浏览器 API/Worker 下载 | 最后重跑 1 项通过，下载字节与 SHA-256 一致；身份撤销/服务停止 | runtime_logs/p09/browser-runs/managed-3a78a9b022844bbdb4d42dcbb125fcdf/managed-receipt.json |
| CLI 下载同一服务快照 | 摘要/字节相等，独立 validate-handoff VERIFIED | evidence/cli-byte-equality.json |
| 原 README 本体 suite | 通过，运行期间源码未变 | runtime_reports/research-0227e5761bfa41f79c84f236e8e7fd2e/verification.json |
| 真实 OS 隔离生成+修复 | PASS；4 次录制调用、1 次修复，11 个禁止路径不可读，网络隔离，无凭证 | runtime_reports/handoff-20260916/isolation-run-1/receipt.json |

隔离进程尝试读取真正存在的私有 canary、仓库会议 ZIP、检查证据和测试文件；
不是只检查目录名。范围为实际研究生成/修复 worker，**不是整个生产控制面**。

首次服务实跑拒绝了路径改变的输入 attestation。原因是原解析器在编译后的字节一致副本
间选择了另一位置；已用逐 ID/字节/内容摘要校验与位置交叉表修正，不改原生历史证明。
初次完整回归的过程日志保留；冻结前补充修正不伪装为同源码完整验收。

## 完整回归核账与最终边界

| 实际运行 | 结果 | 证据 |
|---|---|---|
| 第一轮完整后端 | 2144 passed / 3 failed / 9 skipped；2156/2156 节点执行 | runtime_reports/zhigou-verification-a0ba69b7e2be4cd0a5a873ef59a2814a/verification.json |
| 第二轮完整后端 | 2147 passed / 2 failed / 9 skipped；2158/2158 节点执行 | runtime_reports/zhigou-verification-c5fc74dd0ce241c2bd3b646479814f8f/verification.json |

第一轮新增总封面的字面模式检查失败已修复，第二轮该项通过。
第二轮剩余两项都调用既有仓库卫生检查，命中 5 份基线已有且字节未改的历史证据绝对路径；
没有修改原证据或降低检查门槛。这些失败不能归为 PASS。

两次长回归期间仍有最后的运行模式标记和前端异步任务状态修正，因此两份回执的
`source_unchanged` 都为 false。最终增量另经过 **59 项后端专项、46 项前端测试、
真实浏览器 API/Worker 下载重跑、ruff、类型和构建检查**；没有再次对最终五个变动文件
重跑整仓 2159 项，不能称“最终同一源码全量全绿”。

最终源码指纹：`90aa8dad6c99fe2f12a02f12da77addc3b6ec8c66c38b78cdd0cfc19f51a6228`。
机器可读汇总：[delivery-verification.json](evidence/delivery-verification.json)。
复用本机 Python 3.12.6 / pytest 8.4.2 / FastAPI 0.115.0 等实际环境；
未重建发行锁定环境，不自动取得正式发行资格。

## 可直接取用的产物

- `runtime_reports/handoff-20260916/final-artifacts-v2/hr_case/ontology-handoff.zip`
- `runtime_reports/handoff-20260916/final-artifacts-v2/forestry_case/ontology-handoff.zip`
- 同目录 `ontology.kgop`、`handoff/`（含总封面）和 `receipt.json`。
- `runtime_reports/handoff-20260916/final-hr-validation.json` 与 `final-forestry-validation.json`：CLI 对最终两包独立重验，均 VERIFIED。
- `runtime_reports/handoff-20260916/synthetic-v2-contract-fixture/`：手工合成事件的 v2 **协议夹具**，已通过本地严格验证；不是生产调用轨迹，禁止冒充真实样本送入收集器/训练。

这些样例的 native review 经真实授权服务路径执行，但身份/数据是明确合成测试，
包内标记 SYNTHETIC_ENGINEERING；不称真实专家审核。原 native 三图与归档原字节保留。

## 外部未决与准确边界

- 对方严格 v2 未定义首次模型前/纯程序 turn。默认不启用 turn=0 扩展，不通过只留 start/end 冒充完整过程。
- 对方收集器、完整 verdict 枚举、本体 answer/违规码/评分入口未提供：NOT_CONTACTED / NOT_CONFIRMED。当前人工接口只提交已明确的 fail+annotations；无真人评价不生成正式 reviews。
- 未执行真实模型网络请求、真实专家审核或生产发布；本轮模型边界测试明确为 Mock/RECORDED，付费调用为 0。
- 完整生产 Worker 仍是可信控制面，不是 OS 沙箱；模型输入继续使用现有白名单、无任意文件工具。已测试 OS 隔离的是研究生成/修复路径，不扩大结论。
- 原 v3 正式转换不在新项目格式中冒称完成；原 diagnostic/preflight 行为保留。
- 当前输入薄适配支持会议 v2 的 CSV 记录/字段和 UTF-8 Unicode 引文、已锁定领域包基线。不支持的定位/外部 imports 明确拒绝，不静默清洗。
- 每包未提供独立负例计划时，negative_cases 为 NOT_RUN。完整包含验收答案，仅供具备 acceptance:export 的授权交付，不给生成环境。
- 历史 evidence 的绝对路径导致已有仓库卫生测试失败：5 文件与基线 Git blob 完全相同，证明见 evidence/preexisting-hygiene-failures.json。保留原件，不放宽测试。
