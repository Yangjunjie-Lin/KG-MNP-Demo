# 本体功能继续实施：TwoAgentKernelV1

本次根据现有功能实现可执行的任务适配五步内核，而不是继续只维护阻塞报告。
保留旧 `TwoAgentV3` primitive pilot 与上一轮实验协议/证据，新增独立系统
`TwoAgentKernelV1`。它已连接共享方法，但不是完整生产工具链，也没有取得外部质量提升结果。

## 已实际接通的功能

| 阶段 | 所属角色 | 实际代码与行为 |
| --- | --- | --- |
| S1 | RuleAgent | `ontology_io.kernel.generate_kernel` 冻结允许输入、任务要求与资源摘要；验证独立提供的 shapes 安全性；每次工具调用后检查输入未改 |
| S2 | RuleAgent | 抽取并复用 `five_stage.assistance.retrieve_cards/select_reuse`，与生产两轮流程共用真实检索/首轮选择内核；第二轮使用任务对应的结构输出契约 |
| S3 | TaskExecutionAgent | 复用 `assistance.character_chunks` 和 `tools.bind_quote`；提取完整预测，逐条绑定引用及Unicode位置；候选词表闭集检查、typed事实/schema关系与类型约束 |
| S4 | RuleAgent | 实际调用 `semantic_kernel.tbox.compile_tbox`、`abox.compile_abox`、共享pySHACL子进程与固定ROBOT/HermiT；结构问题返回S2，事实/引用问题返回S3 |
| S5 | TaskExecutionAgent | 固定最终预测，另存同一预测的共享编译图与摘要；原生文件/投影和编译图均重读核对；保留失败版本与修复历史，不补造审批 |

`FiveStageCoordinator` 支持同阶段多个真实工具及有限反馈循环。
旧调用默认仍是单次S1→S5；生产模式不能启用该研究修复快捷路径。
所有原角色工具白名单、生产审核/版本控制保持不变。

### 分型处理

- primitive graph：最终输入/预测三元组转换为共享TBox/ABox编译候选。
  编译加入的类、谓词、NamedIndividual声明属于辅助语义图，不混入原生三元组评分。
  编译后的任务投影必须与原始三元组图同构；重复原始边仍保留给native scorer。
- typed ABox：事实、显式类型、允许的category schema分别处理；保留每条事实与schema配对。
  RDF类型/声明不算业务事实；domain/range不当成闭世界数据库校验。
- CQs→OWL：直接保留Turtle中的OWL restriction、匿名节点与公理，用共享研究序列化器冻结，
  不强塞进只支持有限候选类型的生产TBox编译器。
- CQs→terms：保留每个复合CQ编号，不覆盖重号。
- 没有合法初始本体时，复用选择N/A，不做一次空模型问答；CQs-only的S3为N/A，不制造实例。
  没有独立合法shapes时，SHACL为N/A，不从模型输出或gold反造规则。

### 验证与修复边界

每次修复按阶段的输出契约重新生成候选，不修改原输入/要求/schema，不读取评分答案。
这不是生产 `assistance.repair` 的逐字段patch API；它是任务草稿上的有界S2/S3反馈。
最大修复次数由 `kernel_profile.max_repair_cycles` 冻结，所有模型尝试仍受统一calls/token上界限制。
不能通过把非空结果删成空图来伪造零违规；该尝试失败并保留此前候选。
达到修复上限仍有问题时，保留预测和问题清单，供独立评分，不静默丢掉坏样本。

Java/推理器缺失、超时、校验器运行失败记 `INCOMPLETE_VALIDATION`，不是PASS，也不会要求模型
“修复服务器环境”。SHACL合规与OWL一致性分别记录；独立类可满足性和OWL profile尚未单独测量。
引文可定位不等于语义蕴涵，仍需要外部原生评分/专家实验。

## 行为消融与同资源对照

| system | 实际差异 | 适用条件 |
| --- | --- | --- |
| NoRetrieval | 不调用检索核，模型输入中的retrieval为空；完整合法输入保留 | 父profile确有supplied cards |
| NoConstrainedExtraction | 不提供/强制候选词表闭集；引用完整性和合法任务schema仍检查 | 文本/typed任务，非CQs-only |
| NoValidationFeedback | 仍执行验证、保存问题，但不回调模型修复 | 父profile的修复次数大于0 |
| DirectRetrievalContext | 与父profile相同的输入检索上下文，直接生成一次，不执行设计/反馈流程 | 确有检索上下文 |

测试检查真实请求内容、调用次数、修复路由与配置摘要，不是只换system_id。
默认旧协议没有kernel_profile，以上消融仍拒绝运行；无对应父组件时也在模型调用前拒绝。
没有消融引用权威、生产审批、鉴权、版本保护或访问隔离。

## 直接执行：不需要模型凭证

配置：`config/ontology_io/protocols/kernel-engineering.yaml`。
固定录制输入/响应：`tests/fixtures/ontology_io/kernel/`。
以下命令执行真实共享编译/验证/冻结，模型边界使用明确录制响应，不产生付费推理。
输出目录必须不存在，避免覆盖历史。

```powershell
$env:PYTHONUTF8 = '1'
$kernelRun = 'runtime_reports/kernel-demo-' + [guid]::NewGuid().ToString('N')
python tools/evaluate_research.py ontology-io replay tests/fixtures/ontology_io/kernel/primitive-input.json config/ontology_io/protocols/kernel-engineering.yaml tests/fixtures/ontology_io/kernel/primitive-recording.json "$kernelRun/primitive" --system TwoAgentKernelV1
python tools/evaluate_research.py ontology-io replay tests/fixtures/ontology_io/kernel/cqs-input.json config/ontology_io/protocols/kernel-engineering.yaml tests/fixtures/ontology_io/kernel/cqs-recording.json "$kernelRun/cqs" --system TwoAgentKernelV1
python tools/evaluate_research.py ontology-io replay tests/fixtures/ontology_io/kernel/typed-input.json config/ontology_io/protocols/kernel-engineering.yaml tests/fixtures/ontology_io/kernel/typed-recording.json "$kernelRun/typed" --system TwoAgentKernelV1
```

当前机器固定ROBOT JAR已存在并实际运行；新机器按现有 `tools/prepare_reasoner.py` 准备。
不要关闭JAR摘要/版本校验。没有推理器时，可以明确将新工程协议的reasoner_jar设为null，
结果会注明OWL未运行，不算一致性通过。

`replay` 只接收 `ENGINEERING_CHECK` 输入，并核对录制输入摘要、模型配置和源码前后摘要。
它禁止把 LOCAL_HOLDOUT/官方测试输入用此入口伪装为真实模型实验。
输出包含 `replay-receipt.json`、`result.json`、每次公开结构化回复、
`kernel.history`、实际 `artifacts/` 和 `kernel-artifacts/` 图/摘要。
`logical_provider_calls`是录制边界次数，`live_inference_calls`恒为0；token/费用未知不填伪零。

## 本机执行结果

本次最终源摘要：`47238715fc3aa7b4f74091cba02e28ec05d3ce92cc00ab9dfbdbd29f56c142e7`。
develop HEAD仍为`adc2a40512f8b029b6c21420b905628c32952d00`；保留上一轮未提交改动，未提交/推送/发布。

| 工程链 | 录制调用 | 修复 | 真实HermiT | 产物 |
| --- | ---: | ---: | --- | --- |
| primitive | 4 | 1，S4→S3修正引文 | CONSISTENT | `runtime_reports/kernel-v1-final-primitive` |
| CQs→OWL | 2 | 1，S4→S2修复Turtle | CONSISTENT | `runtime_reports/kernel-v1-final-cqs` |
| typed ABox | 3 | 0 | CONSISTENT | `runtime_reports/kernel-v1-final-typed` |

三条回执均声明RECORDED_ENGINEERING_ONLY、source_unchanged=true、真实推理0次、research_score=null。
这证明这些功能实际执行，不证明三个公开benchmark准确率或相对基线提升。

新增`test_ontology_io_kernel.py`覆盖实际共享核、双角色分工、两个回退方向、三种行为消融、
同检索上下文直接对照、CQs N/A、OWL匿名限制保真、typed绑定、空结果修复拒绝、预算与历史保留、
录制入口防误报，以及真实pySHACL和HermiT正反例。
最终回归记录见`runtime_reports/kernel-v1-final-verification/`和
`runtime_reports/kernel-v1-final-module-tests.xml`。

最终结果：ruff、types退出0；本体工程suite **170 passed / 13 warnings**，
新内核与原五步模块独立回归 **42 passed**（包含21个新内核测试）。
受测源码前后摘要一致。机器可读回执见
[ontology-kernel-v1-evidence.json](ontology-kernel-v1-evidence.json)。

## 仍未宣称完成的范围

这是任务适配的工程profile，不是全部五阶段生产能力或完整Ours研究方法。
检索只使用官方允许输入中的exact cards，不是BGE/FAISS/reranker实测；分块为显式Unicode方案。
RECORDS_TEXT生产记录映射、独立OWL profile/类可满足性、完整v3正式出口、全部CQ4OE/semantic
原生评分、论文baseline、受控OS隔离与授权付费full实验仍各自有缺口。
既有LIVE `run` 预算/OS门没有放宽；旧full预注册/样本清单不能在新源码下静默resume。

前次BLOCKED研究报告保留在`docs/research/ontology-io-2026-09-13/`，适用于它记录的旧指纹。
本次功能进展不追溯改写前次实验状态，也不把录制重放成绩当真实模型成绩。
