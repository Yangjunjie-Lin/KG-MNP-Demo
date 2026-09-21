# 本体 I/O：修改前审计（2026-09-13）

> 2026-09-14/15续办补记：下文是首次审计时的历史起点，不是当前工作树状态。
> 当前HEAD仍相同，但工作树已有本体评测增量修改；真实执行为24次调用、9个合成smoke job、
> 1个失败pilot job、0个full job。续办发现失败响应usage丢失，并修复`CompatibleClient.propose`、
> `live_broker.dispatch`和`engine.generate_sample`的核算路径；未解除上游token超限预算锁。
> 新增全量状态离线导出及摘要排序测试。实际修改前/后源码、diff、测试回执见
> `runtime_reports/full-ontology-experiment-20260914/continuation-final-verification-20260915/`；
> [续办报告](../full-experiment-continuation-2026-09-14.md)区分工程完成项与仍然BLOCKED的研究实验。

本审计记录本次工作起点，不替代历史报告。`develop` 本地 HEAD、
`git ls-remote origin refs/heads/develop` 均为
`adc2a40512f8b029b6c21420b905628c32952d00`；`git status --short` 为空。
与前次审查提交相同。`ontology_io.provenance.source_fingerprint` 的实际源码摘要为
`85956db0c41281b5e7a0d39f1bce5e3726e64b383e035d0df8e1291c4a2725de`。
该摘要覆盖 tracked/untracked 实现、配置、测试、CI；不是仅凭提交号声明受测版本。

状态层次：REGISTERED（登记）→ IMPLEMENTED（实现）→ ENGINEERING_TESTED
（工程测试）→ LIVE_SMOKE（真实合成模型调用）→ EXTERNAL_SCORED（完整外部评分）。
这些层次不能互相替代；本次开始时没有完整外部系统对比证据。

| 项目 | 起点证据 | 起点状态及必要行动 |
| --- | --- | --- |
| TwoAgentV3 | `ontology_io/engine.py::generate_sample`；`test_ontology_io_integrity.py::test_actual_five_stage_pilot_records_role_sequence_without_fake_semantic_pass` | primitive pilot。S2 一次 plan，S3 一次 triples，S4 `triples_graph`。无检索、共享编译、联合反馈。保留旧 ID/证据，不能标完整 Ours |
| 真实 API | `docs/upgrade/astra-xhigh-smoke.md`；`runtime_reports/astra-xhigh-smoke-c6d6e3a4c5ae4b7eb29c0304a2149f6c/report.json` | 历史 4 次合成调用，不是公开基准成绩；授权仅对应那次有界 smoke，非本轮全矩阵总预算 |
| 输入/产物 | `contracts.ModelingInput` 登记五种 mode；`engine.generate_sample` 只允许 TEXT_NEW/TEXT_EXTEND；`adapters.freeze_prediction` | primitive 已实现；OWL/typed ABox 未接通，必须无损分型适配 |
| LLMs4OL Reuse | `adapters.adapt_llms4ol`；固定 train_task_b.json（2774 行）字段 `terms`、`types` 均为 list | 确实遗漏合法字段。按官方字段转交所有系统，禁止从 extended triples 推导 |
| LLMs4OL scorer | `native_metrics.llms4ol_exact` + SHA 锁 + `test_ontology_io.py` | exact 原 AST 已测试。固定文件顶层 `SentenceTransformer(...trust_remote_code=True)` 不可直接 import。fuzzy 可脱离模型；semantic 权重/代码/阈值待锁 |
| LLMs4OL 指标 | 固定 `2026/metrics/graph_similarity.py::{edge_f1,exact_match,fuzzy_match,semantic_match}` | 返回四种图指标；无独立任务 P/R 或官方跨样本排名聚合入口。不能把本地 sample mean 宣称官方排名 |
| CQ4OE | `cq4oe.adapt_cq4oe`、`cli.prepare_cq4oe`、`test_cq4oe_input.py` | 只有输入；重复编号保留但未提供复合 ID。原生对齐依赖 Ollama embeddinggemma、词法包；层级依赖 HermiT。完整评分未实现 |
| CQ4OE 任务语义 | 固定 README、scripts/concept、property、triple、axioms、hierarchy | 6 套本体；TBox 结构≠ABox；CQCoverage≠查询答案准确率。论文接收未核实 |
| OSKGC | `oskgc.{adapt_oskgc,score_native,native_evaluator}`、`test_oskgc_native.py` | 原生方法测试通过，typed 输出/CLI 未接通。micro 为跨样本集合并；macro 为文件级已舍入 F1 均值；SS 原首关系匹配与额外预测惩罚保留 |
| OSKGC 许可 | 固定根 LICENSE=MIT；benchmark/LICENSE 标题 CC BY-NC-SA 4.0、正文 CC BY 4.0 | 冲突仍存在；旧“保守科研使用”不是独立许可证明。本次阻止新增数据获取/真实数据运行，不删除历史数据、不再分发商业包 |
| 数据范围 | `tools/prepare_ontology_benchmarks.py::selected`；`cli.prepare*` 默认 limit=3 | LLM train 有界留出；OSKGC 仅 Airport train；CQ 文件有界子集。需 full 无 limit、全清单和分组/近重复审计 |
| B0/Bbudget | `engine.generate_sample`、`variants.yaml` | 同模型直接生成/自检已有实现；没有外部真实运行。Bpaper 仅登记 |
| Ontogenia | 固定 Onto-Generation README | 作者声明 ESWC2025 Research Track；方法代码实际在 PromptingTechniques/README.md，不是 .py。需核对，不臆造人工评测复现 |
| 五步共享能力 | `five_stage/assistance.py::{generate,repair}`；`tools.{merge_recall,vector_recall,rerank,bind_quote}`；`semantic_check.check_graphs` | 生产已有两轮复用、固定身份抽取、受限事实修复及共享编译。研究输入没有生产身份/审核，不能伪造批准以调用它们 |
| S4 语义 | `semantic_kernel.validators.{shacl,owl_consistency,owl_profile}`；`five_stage.semantic_check` | 可复用检查器；无合法 shapes 应 N/A，CQs-only 不因缺生产 target coverage 拒绝草稿评分 |
| S5/v3 | `modeling/delivery/{v3,native}.py`；`docs/reference/ontology-v3/source-manifest.json`；`test_v3_delivery.py` | 固定 3.0.0 协议只读检查/诊断导出，不是完整原生→v3 正式出口；不放宽 Schema、不伪造 ACCEPTED |
| 隔离 | `cli.run` 声明 CLOSED_INPUT_AND_TOOL_BROKER_NOT_OS_SANDBOX | 仅分调用。实际 `docker info`：Linux engine pipe 不存在。不能声称 OS 访问拒绝通过 |
| 统计 | `statistics.{paired_comparison,holm_adjust}`、`cli.compare` | 组均值 bootstrap 用于可加 sample mean；不能直接用于 OSKGC 非可加 micro。缺跨比较 family 与非可加重算 |
| 回归/CI | `.github/workflows/ci-{quality,backend}.yml`、`tools/evaluate_research.py::SUITES` | 当前本地 ruff、check_types 已运行退出 0；ontology-io-engineering 正在独立运行，最终退出码另存，不追认历史 CI |

## 研究资格阻塞（执行前）

- BLOCKED_BUDGET_UNSET：未发现当前请求明确授权总 calls/token/费用上界；不消耗模型额度。
- BLOCKED_OS_ISOLATION：Docker CLI 存在但服务不可连接。普通 Python 子进程不视作隔离。
- BLOCKED_LICENSE：OSKGC 冲突未澄清；新数据使用/再分发不推定获准。
- BLOCKED_NATIVE_SEMANTIC_LOCK：LLMs4OL nomic 远程代码/权重未锁；CQ4OE embeddinggemma 修订未锁。
- PARTIAL_OURS：研究路径未完整接通生产内核。工程补齐不能自动把该状态改成完整。

最终修改、实际测试/样本数与未完成范围见同目录 `report.md`；上述起点不随修复改写。
