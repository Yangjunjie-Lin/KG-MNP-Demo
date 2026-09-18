# 阶段验收收口（2026-09-16）

2026-09-18 复用本入口对 01–17 新增差异冻结复验，基线为干净 9f6c036。
`--input-archive` 只接入所提供说明包的 upstream；原指定精简版缺失与补充名称更新版分别记录。
执行范围包含新的服务评价/批次测试、双 Agent/逐步审计与两类真实浏览器用例。
每个案例另保留 ontology-combined.zip（downstream + 有效本地诊断），不把程序轨迹塞入 executions。
新回执写 `runtime_reports/alignment-20260918/`，下面的历史失败与原命令仍保留。

本轮起点 develop@979128ee16746cd124aca29257a23910e8edcea0，工作树干净。
Git commit 与源码文件清单 SHA-256 是不同的身份对象。旧交付、历史失败和旧摘要保持原样。

实施顺序：独立 negative_case_plan 冻结及执行 → 会话有效祖先/原生包/轨迹关联 →
阶段总 ZIP 独立读取验证 → 完成文档 → 冻结全部受测文件 → 实跑回归及两个新服务工作区 → 总包。

本轮运行证据单独写入 `runtime_reports/stage-closeout-20260916/`，不写回冻结实现。
这里描述接口及验收规则；实际结论以该目录的 FINAL_REPORT.md、source-snapshot.json、
stage-verification.json 与 full-regression-summary.json 为准，不预先填写 PASS。

## 权限和范围

保留原会话、审核、编译、Worker/CAS/租约/STALE。负例验收是观察记录，不是新的审批或版本库。
不改原 v3 Schema、原生 ID/IRI 或历史签名，不执行付费模型、发布、推送或旧研究实验。
完整生产 Worker 沙箱及 LIVE broker 联调不纳入本轮；纯程序/RECORDED 仅交本地诊断。

## 已实现接口与兼容

`modeling.session.open` 新增可选 `negative_case_plan`，在原 frozen 验收输入中规范化并参与原 session 身份。
计划变更必须新开会话，不能塞进生成配置或修改已确认输出。未传计划的旧请求保持原行为。
生成/修复上下文不消费此字段，内容记录过滤该字段；验收计划只在授权验收/交付侧读取。

`modeling.handoff.check`（package_id、expected_revision）需要 acceptance:run、source:read、package:read。
它在原 Worker/CAS 边界内取冻结计划，调用固定校验器在临时副本上实际执行，生成不可变 report_id；
不签署审批、不改 .kgop、不改变 session revision、不发布。`modeling.handoff.export` 有计划时需显式
`negative_report_id`，同时沿用 source:export / acceptance:export 等原权限。界面可执行冻结负例并选择对应结果。

新导出使用 **zhigou-ontology-handoff/1.1.0**，独立 Schema 为 handoff-1.1.schema.json。
旧 1.0.0 Schema 与原 v3 原字节不变；旧本体包仍可只读检查，不追认阶段验收。
tests/negative_cases.json 现在包含实际 plan/report/status；无计划为 NOT_RUN，有计划未执行也不变为 PASS。
manifest.stage_acceptance 独立于包格式 VERIFIED、本体审核和发布状态。

HR / 林业计划在 tests/fixtures/handoff/ 中，分别依据原 EmployeeShape.employeeId、TreeShape.treeCode
的既有 minCount/datatype，以及原溯源、清单、会话和权限门控定义 14 个合成用例。
变异方式是封闭枚举，不接受代码、表达式或 ZIP 内脚本。每例保存计划/用例/受测原生包/变异输入摘要、
原始变异字节、校验器及版本、真实结果、时间和日志。校验器错误/超时不是检出成功。
NOT_APPLICABLE 不合并成 PASS；本阶段两领域交付需完整覆盖约定的 14 类变异。

## 不可变关联与信任

交付绑定读取原 session 的 CURRENT 输出与真实已提交作业，重新核验提交回执和工件摘要。
scope/proposal/确认包/编译计划/最终包与原生归档交叉检查；被 STALE 淘汰的旁支不能进入有效祖先集合。
S1 合法早期运行可早于最终 revision，且不机械要求它使用后续 S2 工具配置；输入/规则/验收依赖仍须一致。

`modeling.evolution.export` 可传 target_package_id、expected_revision，服务端绑定本次目标和实际输出引用。
context 的外部/原生 run、task/job、版本、输入、原生 archive SHA、结果摘要及 harness/task_start 必须闭合。
本地 journal 保留原事件字节，前置程序步骤和 RECORDED 不伪装成严格 v2。手工协议夹具不得进入正式样例。

新总封面为 zhigou-handoff-cover/1.1.0；旧 1.0.0 只报 LEGACY_FORMAT_CHECKED / NOT_ATTESTED。
只有 downstream 可独立交付，演进缺失/受阻会明确列原因。

**自包含哈希不是授权签名。** 验证单包的授权一致性需通过 `--receipt` 使用从服务认证 API 取得的
导出任务回执，而不是信任包内自述。最终总 ZIP 通过 `--sha256` 固定从本轮交付消息/可信 sidecar 得到的摘要。
无外部信任锚仍可检查结构/闭包，但只报 CONSISTENCY_ONLY、阶段 UNATTESTED，不能冒称真实授权。
这样即使攻击者改 context/计划/结果并重新生成所有内部清单，也不能替换已授权的包。

字节哈希为 SHA-256(raw bytes)；项目 JSON 聚合为排序键紧凑 UTF-8 JSON+LF；原 semantic_hash 与原生 RDF
语义摘要沿用原算法。关联字段明确对象，不拿 Git commit、文件字节哈希与语义哈希混比。

## 总 ZIP 与独立验包

```powershell
python -m zhigou_toolchain.modeling.delivery.cli validate-handoff CASE.zip --receipt AUTHORIZED_EXPORT_RECEIPT.json
python -m zhigou_toolchain.modeling.delivery.cli validate-stage STAGE.zip --sha256 TRUSTED_SHA256 --replay-negatives
```

总包包含 hr/、forestry/ 的服务下载包、验证回执、实际可用的本地诊断，以及 evidence/ 冻结清单和原始测试证据。
stage_manifest 逐文件记录 SHA/长度/用途/案例/访问级别，演进状态单列；manifest 不含自身摘要，总 ZIP 摘要另存 sidecar。
读取器在内存中安全解包，限制路径、链接、重复名称、数量和展开量，绝不执行包内脚本。
它复核各内层包、冻结负例、有效祖先、实际目标、harness、测试回执和源码快照；可再次执行封闭负例配方。
生成后必须重读磁盘上的最终 ZIP，不以压缩前字典验证代替。

## 冻结与复验

```powershell
git -c core.autocrlf=false worktree add --detach runtime_reports/stage-closeout-20260916/baseline-979128e-raw 979128ee16746cd124aca29257a23910e8edcea0
python tools/verify_stage_handoff.py runtime_reports/stage-closeout-20260916/frozen-run-03 --baseline runtime_reports/stage-closeout-20260916/baseline-979128e-raw --parallel-full
```

目标目录必须未存在。干净基线按 Git 原字节检出，避免系统 autocrlf 对历史 JSON 引入仅换行差异；不改历史原件。
原卫生脚本与两个测试不修改，基线和当前分别实跑并逐文件比对；约束冲突时保留真实 FAIL，不自动加白名单。

冻结政策 GIT_TRACKED_AND_UNTRACKED_NONIGNORED_FILE_BYTES_V1 覆盖全部跟踪/未忽略的新文件，包含文档、
全部配置、测试、领域包、前端工具配置和依赖定义；另记录实际安装 Python 依赖和固定推理器摘要。
Git HEAD、原始 dirty diff 摘要、状态摘要、完整文件清单共同计算 snapshot_id。
运行输出写 ignored 的独立目录，不加入自身指纹；每条命令前后及最终压缩后复核同一范围。
任何源码变化都会中止本次资格，必须新目录重新冻结，不通过删除测试/配置来获得 source_unchanged=true。

首次 frozen-run-01 在完整回归前中止：有界读取曾为每个小文件申请上限大小缓冲。
已保留 ABORTED 回执，修正为按实际大小+1读取，并拒绝捕获期间增长/缩小；不减少任何文件范围或摘要校验。
正式执行请用未存在的新目录（本轮后续为 frozen-run-02），不能用中止记录替代验收。

frozen-run-02 完整后端在中断续办后得到 2172 PASS / 2 继承 FAIL / 9 SKIP，源码未变；
但最终归档发生包装器日志与 pytest 原始日志同名冲突，独立验包正确拒绝。
失败 ZIP 与 PACKAGING_FAILED.json 保留；已将原始日志放到独立 full-backend-raw/ 子目录，
并新增防覆盖回归。后续从新目录 frozen-run-03 重新冻结验证，不将失败包重写为通过。
`--parallel-full` 只并行独立检查进程，完整后端仍为原四 Worker 命令；不改变收集范围、权限或任何测试门槛。

脚本执行用户列明的专项、静态检查、本体 suite、4-worker 全仓、前端、原服务/安全测试，以及真实 API/Worker
的同一导出任务浏览器下载；实际 CLI/API/浏览器字节相同才通过。具备固定 WSL 环境时复跑隔离，否则明确 NOT_RUN。
计数由实际收集产生，逐节点 PASS/FAIL/SKIP 和原因保留。阶段模块、相对基线新增回归、全仓原始结果分别输出。

## 外部待确认（不阻断独立本体交付）

1. 首次模型前/纯程序工具 turn 如何表示？严格 v2 出口受此影响；本地完整 journal 不受阻。
2. 2026-09-18 verdict 已确认 pass/fail，pass 可无 annotations；answer 按任务实际结果原样保存，不要求本体专用业务 Schema。该字段问题已解决，不再作为当前阻塞。
3. 本体违规码/评分接口与真实接收器如何接入？尚无接收回执，始终 NOT_CONTACTED，不能称 COLLECTED 或可训练。

原 v3、LIVE 模型、真人运行评价、外部研究效果与生产发布未被追认为完成。
整个生产 Worker OS 沙箱、跨进程 LIVE broker 和付费实验不在本轮必须完成范围。
