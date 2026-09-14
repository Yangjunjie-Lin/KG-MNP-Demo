# 本体建模：公开 benchmark 检索、选型与执行状态

检索日期：2026-09-14。检索官方任务、作者仓库、论文、评测框架文档；不声称穷尽整个互联网。
15个主要来源已保存只读快照及SHA-256：
`runtime_reports/ontology-benchmark-search-20260914/sources.json`。
旧LLMs4OL/CQ4OE/OSKGC/Onto-Generation锁均未升级；新候选只审计公开说明，不执行外部代码。

**选择结果：LLMs4OL 2026作为当前文本→本体主测，CQ4OE作为CQs→OWL结构补充；
DeepEval只包装固定原生指标，G-Eval不作为主质量分。完整真实模型性能测试仍未执行。**

## 1. 候选资源与适用性

| 资源 | 实际评价对象 | 选择 |
| --- | --- | --- |
| [LLMs4OL Flagship](https://sites.google.com/view/llms4ol2026/flagship-task)、[Reuse](https://sites.google.com/view/llms4ol2026/reuse-task) | 文本→primitive ontology；文本+初始本体+提供terms/types→新增三元组 | 主测，与现有任务和适配最直接。不是任意OWL公理生成基准 |
| [CQ4OE](https://github.com/oeg-upm/cq4oe-benchmark) | CQs→术语及完整OWL TBox；包含直接zero-shot/normal生成方法 | 结构补充。保留旧固定版本；完整对齐/公理/层级评分尚未接通 |
| [Text2KGBench](https://github.com/cenguix/Text2KGBench) | 给定ontology，从文本抽取事实；TekGen 10套本体、WebNLG 19套 | 适合作为事实抽取补充，不直接证明新建TBox更好。数据许可声明及上游SA/NC-SA需要另审，不自动替代OSKGC |
| [Text2KGBench-LettrIA](https://ceur-ws.org/Vol-4041/paper3.pdf) | 改进19套schema和4860句的事实标注 | 论文明确需向作者申请数据；未取得本地授权数据，暂不采用。论文CC BY不等于数据授权 |
| [SCOPE/SCION](https://github.com/wandugu/paper_scion) | 语料级关系/事件schema归纳、fusion，typed schema-edge指标 | 有相关LLM-only baseline，但不是现有OWL/primitive任务的直接替代。需要额外锁定与语料级适配，暂不引入平行实现 |
| [Onto-Generation](https://github.com/dersuchendee/Onto-Generation) | story+CQs→OWL的论文提示方法 | Bpaper候选，不把作者结果当我们同backbone成绩；人工评价部分不能由自动指标冒充 |
| [OSKGC](https://github.com/HeraclesWang/OSKGC) | 文本+category schema→事实与类型/schema | 任务适配，但保留原有数据许可冲突阻塞 |
| [OAEI](https://oaei.ontologymatching.org/2026/)、[ontoeval](https://github.com/ai4curation/ontoeval) | 本体对齐、已有本体变更 | 不是端到端文本/CQs生成的主benchmark |
| [OWL2Bench](https://github.com/kracr/owl2bench)、[OntoBench](https://github.com/VisualDataWeb/OntoBench) | 生成OWL测试数据、验证工具/推理器规模性能 | 可用于工具层压力测试，不能代表自然语言生成的语义准确率 |

用PDF技能查看了LettrIA论文相关完整页：第2页确实声明available upon request，
因此没有从第三方分享链接绕过作者的数据获取流程。只读论文副本为
`runtime_reports/ontology-benchmark-search-20260914/lettria-paper.pdf`。

### 新版本与旧锁差异

[当前CQ4OE官网](https://oeg-upm.github.io/cq4oe-benchmark/leaderboard/index.html)写：
CQ2Term 99 CQs，CQ2Onto 118 CQs / five targets，并列出归档DOI与Hugging Face入口。
仓库已锁定commit `248e0c6...` 的实际CQ2Onto输入是6套、117题，CQ2Term为6套、99题。
不能混用新版网页的数量和旧版scorer；本次保留旧锁并明确差异。未据此推断论文接收状态。

Text2KGBench根代码为Apache-2.0，而README的数据许可措辞、TekGen CC BY-SA 2.0与
WebNLG CC BY-NC-SA 4.0来源约束并不等同；没有自动推定取得商业/再分发权利。

## 2. DeepEval、Ragas、Promptfoo如何选择

[DeepEval](https://deepeval.com/docs/benchmarks-introduction)是评测框架，也支持MMLU等通用模型任务。
MMLU主要是选择题，不能回答“同一模型经过我们的本体流程是否产生更好的OWL”。
不能把通用模型知识榜单当成本体建模流水线评分。

[G-Eval](https://deepeval.com/docs/metrics-llm-evals)根据评价步骤调用LLM裁判，结果并非确定性；
它适合补充解释质量或要求遵从等人工式判断，不自动等价于OWL公理正确率。
[Faithfulness](https://deepeval.com/docs/metrics-faithfulness)检查输出相对retrieval context的支持，
也不是独立OWL语义基准。没有独立校准时，不用“另一个LLM觉得好”作为主提升证据。

[Ragas Factual Correctness](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/factual_correctness/)
侧重自然语言claims及参考答案；[Promptfoo](https://www.promptfoo.dev/docs/configuration/expected-outputs/)
可组织prompt/模型断言矩阵。它们不是无效工具，但替换当前Python/native scorer没有明显必要。

采用：[DeepEval BaseMetric](https://deepeval.com/docs/metrics-custom)薄适配现有原生评分函数。
保留本机已有4.1.0；网页当前展示4.2.2，不静默升级。代码不调用默认judge，不用Synthesizer
生成“测试gold”，不上传Confident AI，不记录隐藏推理。离线worker不继承模型/云账户凭证。

## 3. 本次已实现及实际运行

- `ontology_io/deepeval_bridge.py`：四个LLMs4OL原生图指标的exact/fuzzy包装，同步/异步都调用原函数。
- 既有 `ontology-io score` 新增 `--framework deepeval`，保留默认native；需要预先启用无凭证离线设置。
  native汇总、gold分离、预测冻结、失败分母不变。其他任务/未锁semantic不会自动换成LLM主观评分。
- `tools/check_ontology_deepeval.py`：在单独无凭证worker中检查适配。禁用dotenv、旧key文件、遥测、更新检查、云trace。
- 原生阈值和异常行为保留；metric的threshold=1只是DeepEval“满分”标志，不是研究验收或项目质量门槛。
  它也不等于图相等判据：无taxonomy的完全一致普通关系图仍只有2/3 Graph Similarity。
- Windows asyncio内部loopback自唤醒管道先由标准库初始化，再对后续Python网络操作全部拒绝；
  没有给任意localhost端点开例外，也不把此机制声称为生成环境OS级gold隔离。

实际离线结果：10种合成matcher边界 × 2种matching × 4种原生指标 = **80组同步/异步等价检查**，
结果完全保持原函数输出，网络尝试0、生成模型调用0、LLM裁判调用0。
包含空图、部分/额外预测、重复边、大小写、方向错误、class/instance混淆及层级情况。
这是**适配正确性验证**，不是80个真实benchmark预测，也不是模型质量提升实验。

首轮worker因Windows事件循环建立内部socketpair被网络guard拒绝而失败，原日志
`runtime_reports/deepeval-native-20260914/worker.log`保留。修正后没有放开外部网络。
最终适配回执：`runtime_reports/deepeval-native-20260914-final/`。
本体工程回归与source guard：`runtime_reports/deepeval-selection-final-verification/`。
新增测试：`runtime_reports/deepeval-selection-final-tests.xml`。

最终回归：ruff与types退出0；ontology-io-engineering **173 passed、13 warnings**；
新增DeepEval集成测试独立重跑 **3 passed**。source guard确认受测源码前后相同。
这些有重叠的工程测试不能相加当作研究样本。来源/运行机器证据见
[benchmark-selection-2026-09-14-evidence.json](benchmark-selection-2026-09-14-evidence.json)。

复现适配检查，不需要模型凭证：

```powershell
python tools/check_ontology_deepeval.py --workspace runtime_reports/deepeval-check-new
python -m pytest tests/upgrade/test_ontology_deepeval.py
```

不要把该命令描述成完整性能测试：它不会生成公开benchmark预测。

## 4. 决定采用的正式对照

选择配置：`config/ontology_io/benchmark-selection-20260914.yaml`，状态SELECTED_NOT_FULLY_EXECUTED。

- B0：DirectGeneralLLM，同任务合法输入、完整任务prompt、一次直接生成。
- Bbudget：DirectBudgetControl，同模型、同输入，最多6次直接自检；不使用我们的语义反馈。
- 实验系统：TwoAgentKernelV1，明确这是任务适配profile，不标成完整生产Ours。
- 先比较B0/Kernel及Bbudget/Kernel，再做父组件确实启用的消融和同检索上下文对照。
- Flagship以固定native exact Graph Similarity为主；Reuse以新增边native exact Edge F1为主。
  fuzzy=.90为次指标；semantic、未实现的任务子类P/R继续null，不用其他分数代替。
- 原生样本聚合目前为LOCAL_SAMPLE_MEAN，不能宣称共享任务官方排名。
- 每任务独立报告质量、完成率、失败、calls、可见tokens、模型/工具时间及p50/p95；费用未知null。
- 3次重复按同一源文档/本体成对，先每重复原生汇总再分层，cluster bootstrap 95%CI、
  Holm主比较校正；非可加指标每次重算，不能平均每题F1替代micro。

模型端点只读health检查成功，**当前实际配置是gpt-5.3-codex-spark**；
这是网关配置/模型列表观察，不是权重修订证明。没有悄悄换成历史Astra，也没有新增推理调用。
正式生成必须冻结相同backbone、采样、prompt、样本和允许资源后执行。

## 5. 为什么尚不能声称“完整性能测试完成”

主测已有full留出候选：Flagship3471 + Reuse2252 = 5723任务输入。
3系统×3重复=**51507运行单元**。按B0最多1次、另两系统每单元最多6次的硬上界：
**223197模型调用**；每单元120000 token保守预留合计**6180840000 token**。
这是设计最坏上界，不是实际消耗预测；不包含后续CQ/消融/论文方法，费用无法可靠估算。
不能在没有总预算授权时默认为用户同意花费这些额度。

| 部分 | 实际状态 |
| --- | --- |
| 检索、任务匹配与框架选择 | 已完成本次范围的来源核对，保留来源快照 |
| DeepEval/native适配与回归 | 已实际离线执行；不是质量研究成绩 |
| 当前新系统/B0/Bbudget公开基准预测 | 0；NOT_RUN |
| 成对F1/质量差值/CI/p | null；没有生成数据可统计 |
| 总付费预算 | BLOCKED_BUDGET_UNSET |
| 强OS生成隔离 | Docker Linux engine不可连接；已有launcher未实现受控环境，仍BLOCKED |
| 全CQ4OE native评分 | 对齐模型/完整公理-层级链仍BLOCKED，DeepEval不消除此缺口 |
| 最终采样与历史留出接触审计 | 尚未完成，不能继承旧source freeze直接resume |

本次未自动推送、提交排行榜、联系作者、授权云上传或执行真实业务。
在预算/隔离/原生评分前置条件未满足时，不将“80组检查通过”冒充完整性能结果。
需要用户明确本轮总模型调用与token预算；预算授权也不能替代其他工程前置条件。
