# 正式调用参数候选与完整清单

本次已生成参数、合法输入副本、逐样本×系统×重复清单和预算表；**没有执行付费推理，也没有代替用户授权**。
本文件区分官方参数定义、网关已观察配置、代码验证和实验设计建议；不是“实测最优超参数”声明。

## 1. 我为本轮选择的参数

| 参数 | 采用值 | 核实程度/理由 |
| --- | --- | --- |
| 模型 | `gpt-5.3-codex-spark` | 当前端点GET models检查可见；不混用历史Astra结果 |
| 修订 | `configured-alias:gpt-5.3-codex-spark` | 网关声明，不是可独立验证的权重快照 |
| API | 现有`OPENAI_BASE_URL`下的`chat/completions` | 复用现有transport，不更换端点，不在文件中复制密钥 |
| 完成token上限 | `max_completion_tokens: 8192` | 官方通用字段；8192是设计值。本地请求形态已测试，Spark网关是否执行仍待探测 |
| 返回格式 | `response_format: {type: json_object}` | 保留现有JSON模式，本地继续完整Schema验证；不假装是服务端严格Schema |
| 返回数量 | `n: 1` | 不用一次请求多个choices冒充独立重复 |
| 流式 | `stream: false` | 简化完整响应、失败和usage记账；不是延迟最优结论 |
| 存储选项 | `store: false` | 明确请求不存为API distillation/evals输出；不代表已核实网关整体留存政策 |
| 网络超时 | 120秒 | HTTPX各阶段/读取空闲超时，不是整个worker硬wall-time上限 |
| reasoning_effort | 不发送（协议为null） | 当前配置同样未设置；不是把值设为`none`，也不是宣称模型不推理 |
| temperature / top_p | 不发送 | 没有核实Spark专属支持范围，不猜`temperature=0`，不伪造固定有效温度 |
| 模型seed | 不发送 | 专属支持未核实；3次重复记replicate_id=0/1/2，不把[17,29,43]冒充已发送 |
| 单次应用上下文预算 | 32768 token保守上界 | 这是应用请求预算，**不是Spark模型context-window规格** |
| 输入字符上限 | 24000 | 与逐请求UTF-8保守上界同时执行；各系统同样拒绝超长输入，不只截断一方 |
| 修复上限 | 1轮 | 结构回S2、事实回S3；所有修复仍占调用/token预算 |
| 自动重试 | 0 | 失败保留，不能用隐形重试扩大预算或挑最优结果 |
| 重复次数 | 3 | 沿用实验设计选择；不是社区强制标准 |
| bootstrap / seed | 2000 / 1729 | 统计重采样随机种子，不是模型生成seed |
| CI / 多重比较 | 95% / Holm | 按真实来源组配对，重复不膨胀独立样本数 |
| 评分 | native exact主、fuzzy=.90次 | 保留既有原生函数；semantic模型未锁时继续null |
| LLM裁判 | 关闭 | DeepEval仅包装原生分数，不另造质量总分 |

[官方Chat Completions参考](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)
明确`max_completion_tokens`包括可见输出和推理token，`max_tokens`为旧字段；`seed`已经标注deprecated/beta，
也不保证确定性。官方字段定义不自动证明第三方/本地网关接受和执行该字段。

[官方模型页面](https://learn.chatgpt.com/docs/models)将Spark描述为文本专用research preview、面向快速编码迭代。
本次未找到Spark独立、完整的HTTP参数/价格/权重快照表；没有拿普通`gpt-5.3-codex`的参数或价格替代Spark。
OpenAI Docs的核对因此影响了本次配置：省略未核实的采样参数，保留当前模型，单列网关探测状态。

`json_schema`可以在明确支持的模型/网关上另行验证后采用；当前不静默切换。
服务器若返回`system_fingerprint`，现在会记录；它只是服务端指纹，不是权重文件SHA-256。

## 2. 请求形态

下面展示参数信封；真实任务prompt和输出Schema仍从既有engine/kernel读取，运行后保存每次实际payload。
S2/S3/S4会依赖前次模型输出，不能提前编造所有动态请求内容。

```json
{
  "model": "gpt-5.3-codex-spark",
  "messages": [
    {"role": "system", "content": "既有任务指令及该任务的完整输出Schema"},
    {"role": "user", "content": "冻结的合法任务输入；不含评分gold"}
  ],
  "max_completion_tokens": 8192,
  "response_format": {"type": "json_object"},
  "n": 1,
  "stream": false,
  "store": false
}
```

这是信封示例，不是已发请求。`RequestProfile`已接入真实transport代码路径，测试确认以上字段发送，
而temperature/top_p/seed/reasoning_effort未凭空添加；未选择新profile的原服务保持旧请求默认行为。
声明修订与配置修订不一致时，在模型调用前拒绝。

## 3. 每个系统的调用上界

按照当前代码最长的有界修复路径计算，并用脚本化路由测试实际执行核对上界，不再统一按6次估算。

| 系统 | Flagship | Reuse | 每套CQs任务 |
| --- | ---: | ---: | ---: |
| DirectGeneralLLM | 1 | 1 | 1 |
| DirectBudgetControl | 4 | 5 | 2 |
| TwoAgentKernelV1 | 4 | 5 | 2 |
| NoRetrieval | N/A | 5 | N/A |
| NoConstrainedExtraction | 4 | 5 | N/A |
| NoValidationFeedback | 2 | 3 | 1 |
| DirectRetrievalContext | N/A | 1 | N/A |

上述Reuse数据实际都有可用输入cards。若将来某输入没有cards，相应消融/对照会按输入标N/A，
而不是跑相同行为后换名字。Bbudget按同任务的相同最大调用预算自检。

### 全量枚举结果

本次清单覆盖：Flagship3471、Reuse2252、CQ2Term6套、CQ2Onto6套；各3次重复。
是现有本地留出/公开CQ范围，不冒称官方隐藏测试；也不是全部外部benchmark都已运行。

- 主比较B0/Bbudget/Kernel：**168213次调用上界**，保守token预留 **5512003584**。
- 加上所有适用消融及同检索上下文对照：**325311次调用上界**，token预留 **10659790848**。
- 有效待运行单元99501，另20934个矩阵位置为N/A；不把N/A记为模型失败或成功。
- 费用未知。这些是应用层最坏上界，不是预计实际消耗，更不构成付费授权。

OSKGC许可冲突、Ontogenia缺失资源/任务适配、Memoryless CQbyCQ任务适配和semantic模型锁
继续单列BLOCKED，数量不明处保持null；没有悄悄把它们遗漏后宣称“全部测试完成”。

## 4. 生成的完整文件

目录：`runtime_reports/formal-ontology-call-pack-20260914/`

- `call-pack.json`：总清单、实际模型配置、源码身份、预算候选、阻塞和未涵盖项目。
- `protocols/*.json`：4个任务的独立、可被当前Protocol读取的参数文件。
- `generation/<task>/inputs.json`：合法输入副本；没有scoring目录，没有gold正文。
- `jobs.jsonl`：全部样本/系统/重复及各自调用与token上界，约40MB。
- `budget.csv`：28个任务/系统组合的范围和预算汇总。
- `source-after.json`：生成后的源码摘要，已确认前后相同。

从仓库根目录生成另一份，不覆盖已有证据：

```powershell
$env:PYTHONUTF8 = '1'
$formalPack = 'runtime_reports/formal-call-pack-' + [guid]::NewGuid().ToString('N')
python tools/prepare_ontology_call_pack.py --output $formalPack
```

该命令只读取已有public inputs，并对当前模型端点执行GET models；不做推理。
旧prepared清单的raw摘要和新规范化输入摘要分别记录，不把新默认字段冒充旧输入字节。
正式生成/评分必须重新绑定对应prepared与源码，不能直接resume旧source freeze。

参数生效路径：`Protocol.request_profile` → `engine.generate_sample` →
`CompatibleClient.configure_request_profile` → 实际HTTP payload。
调用预算路径：`formal_calls.call_cap` → 每个job的max_calls/max_reserved_tokens。

## 5. 执行前还差什么

这是一份**正式候选调用包**，状态为`FORMAL_CALL_PACK_PREPARED_NOT_AUTHORIZED_NOT_EXECUTED`。
不是已经具备OS隔离的执行器，也没有把总预算写成已批准。

1. 先小规模核验当前网关POST参数：接受/拒绝、完成原因、usage、回显fingerprint及实际返回格式。
   HTTP成功也不能单独证明推理强度、权重版本或服务端严格解码。
2. 当前配置的采样默认值仍未独立证实。是否改用明确reasoning设置、是否采用json_schema，
   应在独立pilot阶段决定，然后冻结，不能看到full结果再改。
3. 完整基准生成仍需要受控OS环境和worker总时限；120秒HTTPX超时不替代这些前置项。
4. CQ4OE完整native对齐/公理/层级链仍需补齐；现有hard术语指标不是全部CQ4OE成绩。
5. 用户必须明确总预算授权；应用预算还依赖网关正确执行输出限制，不能只凭models列表承诺账单上界。

建议下一次先授权的**参数探测候选预算**：最多6次推理、每次输出上限1024，
总保守token预留不超过32768；只用独立合成格式输入，不触及benchmark gold或正式测试集。
这是待确认的建议，不是已经执行或已经取得授权。全量预算应待此检查后再确定。

## 6. 验证记录

请求形态/上界专项：`tests/upgrade/test_ontology_request_profile.py`；
原Astra协议回归：`tests/upgrade/test_astra_transport.py`。
确认modern token字段可在reasoning省略时发送、旧服务默认不变、修订不一致拒绝、非法参数拒绝、
最长S2回退路径不超调用预算、清单不读取gold。
最终回执保存在`runtime_reports/formal-call-final-verification/`及
`runtime_reports/formal-call-final-module-tests.xml`。
这些是本地代码/模拟传输验证，不是当前Spark网关POST实测或本体质量成绩。

最终验证：ruff/types退出0；本体工程suite186项通过（13 warnings）；
请求参数及原Astra接口专项20项通过。受测前后源码摘要一致，调用包与最终源码同为
`1f1e79ef26eae85bf8e2291a7e466b34fc28819463be57ee262297657a55516e`。
[机器证据](formal-call-parameters-2026-09-14-evidence.json)保留预算、模型元数据、退出码与回执位置。
