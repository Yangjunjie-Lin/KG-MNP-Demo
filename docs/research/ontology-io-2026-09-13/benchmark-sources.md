# 固定资源、原生指标与适配追踪

核对日期 2026-09-13。旧 commit 均保留；新增获取的是同一 commit 中此前遗漏的
提示词/指标目录及 Git tree 清单，不是静默升级。下载校验 Git blob、长度、SHA-256；
`asset-lock-<旧摘要>.json` 保留每个旧清单，当前锁是追加并集。
完整文件/函数行号/依赖/摘要：
`runtime_reports/ontology-io-source-audit-20260913-v2/native-source-audit.json`。
官方网页快照、获取时间与内容摘要：同目录 `official-web-audit.json` 和 `public-source-*.txt`。

## 外部权威与许可证

| 资源 | 固定版本 | 核实范围与许可证 |
| --- | --- | --- |
| [LLMs4OL](https://github.com/sciknoworg/LLMs4OL-Challenge) | `315a9a5d883eada26e00fef1356a05802936c584` | ISWC2026 相关共享任务，不是本项目发表/获奖。根 LICENSE 为 SciKnowOrg MIT；保留声明。原始本体的外部授权并不由本次代码许可证审计统一担保 |
| [CQ4OE](https://github.com/oeg-upm/cq4oe-benchmark) | `248e0c6cfa498c4630b17a83290628d9f8adc4b6` / 0.0.1 | 根 LICENSE Apache-2.0；公开 benchmark，论文接收/期刊分区未核实。其六套来源本体有各自来源，不据根许可证断言取得全部第三方商业权利 |
| [OSKGC](https://github.com/HeraclesWang/OSKGC) | `b6a12ed38f131abb10ba22a785bba1d5d886aee0` | 代码 MIT；benchmark/LICENSE 标题 CC BY-NC-SA 4.0、正文 CC BY 4.0 冲突未解决。新数据获取与真实运行 BLOCKED_LICENSE；旧 Airport 文件原样保留，不作为授权证明，不装入商业包 |
| [Onto-Generation](https://github.com/dersuchendee/Onto-Generation) | `13d2e17a448b8697811438f2ed88c213e9b47b63` | README 声明软件 MIT；[DOI](https://doi.org/10.1007/978-3-031-94575-5_18) 的 Crossref 元数据确认 2025 Springer 章节《Ontology Generation Using Large Language Models》，README 指 ESWC Research Track。未把替换 backbone 的重测当作作者原始成绩 |

[CEUR Vol-4041](https://ceur-ws.org/Vol-4041/) 实际将 OSKGC 列在 KBC-LM Workshop，
与 ISWC2025 同地举办；不是 ISWC 主会论文。该卷论文 CC BY 4.0 不自动解决 GitHub
benchmark 数据许可证冲突。本次读取 proceedings 元数据和固定源码；没有冒称全文重新审稿。

## LLMs4OL：官网与固定代码确有差异

实际读取 [Flagship](https://sites.google.com/view/llms4ol2026/flagship-task)、
[Reuse](https://sites.google.com/view/llms4ol2026/reuse-task)、
[Submission](https://sites.google.com/view/llms4ol2026/submission)。

- 训练量官网/固定数据一致：Task A 4303、Task B 2774。
- Reuse 明确提供 initial ontology、possible terms/types；适配现在使用原记录字段，
  B0/Bbudget/旧 pilot 同样收到，绝不从 extended gold 反推。
- Submission 明确 Reuse 输出 **new triplets**。`additions_only` 按锁定 scorer 的
  lower/strip/whitespace 规则剔除已提供的边，并保存剔除数；不丢弃错误的新边。
- 官网列出标准/子任务 P/R/F1；固定 graph_similarity.py 只返回 Edge F1、Neighborhood、
  Taxonomy、Graph Similarity 四项，无任务级 P/R 汇总驱动。因此那些 P/R 与官方汇总仍未复现。
- 官网 Neighborhood 描述只提 outgoing；固定函数同时含 IN/OUT。
- 官网 Taxonomy 描述 ancestor sets；固定函数合并 ancestors 和 descendants，
  可能对方向反转仍给出高 taxonomy 分。Edge F1 是另一指标，不能互换。
- 官网说完全一致为 1，但固定函数对无 taxonomy 的相同普通边是 2/3、空图对空图是 1/3。
  保留原行为，不修成“更直观”的分数。
- 官网 Flagship 链接 `2026/graph_similarity_metric.py`；固定树实际文件是
  `2026/metrics/graph_similarity.py`。本地以固定代码为准，披露不一致。
- 官方 Submission 说明不使用公开 leaderboard，Google Form 私下评分。没有提交表单、issue 或排行榜。
- 固定 tree 有 test_task_a.json/test_task_b.json；本轮未获取/生成这两套官方测试预测。
  官方网页公布 2018/1799；这是官方描述，不是本地实际完成数。无测试 gold/官方评分。
- 官方禁止训练使用的目标本体列表含 FOAF、FoodOn、DBpedia、Wine、SchemaOrg 等；
  本次冻结检索资源为空，不使用这些目标本体、向量库、邻题答案或 few-shot 缓存。

`graph_similarity.py` SHA-256：
`4eb22bfb304a0239269951c3ac65ff8fa39a8fd69fe1159ee40bbeba676159c9`。
exact/fuzzy 仅执行原始函数 AST，跳过顶层
`SentenceTransformer("nomic-ai/nomic-embed-text-v1.5", trust_remote_code=True)`。
fuzzy=0.90，RapidFuzz 3.14.3 / NumPy 2.4.6 / SciPy 1.15.2；仅安装 RapidFuzz，未更换现有数值库。
semantic_match 默认 threshold=0.90，内部 align_triples_semantic 默认 0.80，
调用链会覆盖后者；模型代码/权重修订未锁，semantic=null，不以 fuzzy/exact 代替。

## source → task → I/O → 原实现 → 本地适配 → 测试 → 执行证据

下表所有路径的 `ontology_io/` 前缀均指 `src/zhigou_toolchain/ontology_io/`。
“已测试”只指原生函数等价/工程契约，不是模型正确率研究结果。

| source / task / 合法输入→输出 | 指标 / 官方实现 | 本地适配与测试 | 实际执行/缺口 |
| --- | --- | --- | --- |
| LLM A：context→primitive triples | 四种图指标；`graph_similarity.py::{exact_match,edge_f1,neighborhood_similarity,taxonomy_similarity}` | `native_metrics.llms4ol_exact`；`test_ontology_io.py` | 历史 exact 边界回归继续执行；新 full 输入已冻结；模型预测 0 |
| LLM B：context+initial+terms/types→new triples | 同上；新增边协议见 Submission | `adapters.{adapt_llms4ol,additions_only,project_prediction}`；`test_ontology_io_extended.py::test_reuse_public_terms_types_and_gold_metamorphic_fixed_request` | 修改 gold 不改变适配输入或固定模型请求；并非 OS 隔离证明 |
| LLM fuzzy（A/B图分析） | `fuzzy_match`、Hungarian align、fuzz.ratio，阈值 .90 | `native_metrics.llms4ol_fuzzy`；8 个独立原函数 parity 情形 | 实际离线执行；不是 Reuse 官方主排名口径证明 |
| LLM semantic | `semantic_match` / `build_embeddings` | `native_status` 明确阻断 | null：未锁 nomic 代码、权重、依赖、评分网络环境 |
| CQ2Term：整本体 CQs→逐复合 ID 的 classes/properties | `CQ2Term/scripts/eval_cq_terms.py::{evaluate_per_method,collect_unique_terms}` 与 `concept_label_matching.py::cal_metrics` | `cq4oe.native_term_hard`、`cli.score`、`freeze_task_prediction`；独立原函数等价、空/重复/大小写/CamelCase、冻结 CLI/失败样本测试 | 仅原生 **hard per-method term** P/R/F1/coverage；不是完整 top-3 alignment / CQ-local coverage |
| CQ2Onto：整本体 CQs→OWL TBox | ClassProperty：concept/eval_concept.py、property/eval_property.py | `adapters.freeze_task_prediction` 保留 Turtle/匿名限制；`cli.score` 阻断完整评分 | 输出/保存往返可执行；原生完整对齐未接通，不报告分数 |
| CQ2Onto properties | `property/eva_char_in_property.py::eval_characteristics` | 源函数清单/摘要已锁；无本地完整调用 | null，不因 registry 中有名字视作实现 |
| CQ2Onto TBox triples | `triple/eval_triple.py::evaluate` | 源函数清单/摘要已锁 | null；这是结构三元组，不是 ABox 事实 |
| CQ2Onto axioms | `axioms/Axioms_atomic.py::extract_tbox_axioms`、`eval_axioms.py` | 源函数清单/摘要已锁 | null；不能把 OWL 限制平铺成字符串边评分 |
| CQ2Onto hierarchy/CQCoverage | `hierarchy/eval_hierarchy.py::{compute_hermit_evaluation,compute_cq_coverage_closure}` | 源函数清单/摘要已锁 | null；CQCoverage 为公理覆盖，不是 SPARQL 答案率 |
| OSKGC：text+category schema→facts+对应类型/schema | `BaseEvaluator::{calculate_metrics,process_record,calculate_scores_from_ss}`；Joint/Pipeline file aggregation | `oskgc.score_native`；typed artifacts；`cli.score` 分重复原生汇总；`test_oskgc_native.py` | 原生函数与 typed 往返离线测试；真实数据链因许可阻塞。非可加 CLI compare 拒绝 sample-F1 均值代替 native micro |
| Ontogenia：story+CQs+patterns+procedure→OWL | 固定 `PromptingTechniques/README.md` 两个 design_ontology 代码片段 | 仅方法审计；不伪造论文 baseline 实现或结果 | patterns.csv 和独立 procedure 文件未在固定 tree 找到；CQs-only 与有 story 论文设置不同，待明确冻结适配 |
| Memoryless CQbyCQ：story+单 CQ、rdf为空→模块合并 | 同 README 完整 prompt | 仅方法审计 | 未执行；不把把文本临时改造为 CQ 叫论文复现 |

CQ4OE 完整驱动明确使用：hard/sequence/Levenshtein/Jaro-Winkler/semantic 五类候选，
top_n=3，class final_threshold=.6，property final_threshold=.7，embeddinggemma；
HermiT 从 owlready2 包定位 JAR。当前缺锁定 embeddinggemma 权重、完整词法/OWLReady2 运行环境、
正式评分配置的审计适配。即使系统 Java 23 和生产 ROBOT 可用，也不自动证明这是同一原生 HermiT 配置。
无下载远程模型或未知代码执行。

OSKGC scorer SHA：`d2684f2fb64e4f47d8b297a2932ea2eafe8fe6c54116b1cbcd319f48de40854c`；
hierarchy SHA：`070cb4ad219f3083a949fe033fedf1473a9938654a5eb4ffdd065056df77674a`。
保留预测 strip/lower、gold underscore→space/lower、全局 triple set micro、
每文件先 round(3) 再平均的 macro，以及首个同关系 gold schema 与额外 schema 惩罚。
实体类型声明及 schema/domain/range 不加入事实评分；不存在“删光事实=语义合规”的测试捷径。

## 论文方法与验证工具

作者原始设置是 GPT-4 1106，temperature/frequency_penalty/presence_penalty=0；
当前配置是既有 Astra 网关别名，不能称同一权重版本，也不是作者原始成绩。
作者原评估含 OOPS!、modelled CQs、superfluous components 和专家判断；
本地没有独立人工评审，不用 CQ4OE 自动分或 LLM 自评顶替。
作者公开给出 ZIP 密码，未绕过访问控制；此次未解压原始 gold ontology 模块、未再分发其数据。

pySHACL、ROBOT/HermiT 和 RDF graph isomorphism 是验证/保存保真工具。
SHACL 合规、OWL 一致性、类可满足性必须分开，domain/range 的开放世界推理不当作数据库错误。
这些工具不是本项目自建的语义准确率 benchmark，也不构成跨 benchmark 总分。
