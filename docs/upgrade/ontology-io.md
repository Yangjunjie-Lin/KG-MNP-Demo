# 双 Agent、v3 与本体 I/O 评测：当前可复现实行范围

本轮是增量实现，**尚未完成用户要求的完整 TwoAgentV3、原生→v3 正式导出和所有外部实测**。
本页区分已执行的工程检查、可执行的原型，以及尚未集成的研究能力。不能据此宣布 80% / 90% / 90% 立项目标达标。

## 资料与权威边界

任务依据及原件摘要见根目录 `requirement_traceability.md`。
已读取真实 v3 ZIP 的 41 个文件，原 Schema 保持字节不变。
用户后补的 `技术栈.docx` 覆盖全部 25 个方法；桌面 HTML 实际是本地模拟的 v1，不能当作双 Agent v3 已实现的证据。
本轮不自动提交、推送、合并、发布、提交排行榜或执行真实业务动作。

## 双 Agent 后端

`RuleAgent` 执行 S1、S2、S4；`TaskExecutionAgent` 执行 S3、S5。
实际工具调用经过固定白名单，并记录输入/输出摘要、父版本、依赖、时间、工具/模型版本和结果。
DENIED 调用在动作发生前拒绝，仍保留审计；异常不把提供者错误中的秘密复制进摘要收据。
生产入口在原有 Worker 私有生成与 CAS 提交链内调用，不建立第二套候选、审核或版本库。
记录映射已推迟到实际 S2 设计完成后执行。修复沿用 S4 分流→S3 受限事实补丁→S4 重验。
提交失败的计算收据仅能通过原租约约束的任务失败路径保留，不能由旧 Worker 越权写入。

尚缺：通用文本实体发现策略的完整生产集成、结构补丁返回 S2 的全链路、研究模式复用全部语义反馈内核。
研究中的顺序协调器仅是自动计算原型，不应被称为全部方法已完成。

## v3 与原生包

从仓库根目录运行（依赖使用现有开发环境/锁文件）：

```powershell
python -m zhigou_toolchain.modeling.delivery.cli --report runtime_reports/v3-reference.json inspect "path/to/本体建模输出_规范参考交付包_v3.zip" --shacl
python -m zhigou_toolchain.modeling.delivery.cli --report runtime_reports/native-v3-preflight.json preflight-native docs/upgrade/evidence/hr-delivery.kgop
python -m zhigou_toolchain.modeling.delivery.cli export-diagnostic docs/upgrade/evidence/hr-delivery.kgop runtime_reports/hr.ontology-diagnostic.zip
```

参考包检查覆盖：固定 Schema 与必须的文件绑定、ZIP/路径/摘要、锁定本地 imports、
实例图同构、对象目录、来源版本与定位、逐字引文、陈述/映射/转换闭包、反向引用、
术语/公理与实际 RDF、真实查询答案。查询与 SHACL 有独立子进程时间上限；
网络查询、外部 FROM、更新语句及可执行 SHACL 扩展不在该读取器允许范围。
规则/约束/证据图不进入默认业务查询图。OWL 与真实审批没有运行时仍明确 NOT_RUN。
不声称正式标准全文符合性通过，不把证据可回查等同于语义支持或事实正确。

`export-diagnostic` 输出三个原生语义图的原字节和缺口说明，**不是 v3 交付包**。
现有 HR 原生样例包含 23 条实例图三元组，其中 5 条为 `owl:NamedIndividual` 声明，业务事实为 18 条；均保留，不能静默丢失或混计。
预检列出 v3 必需的冻结范围/规则、许可来源快照和定位、执行映射、独立答案行以及审核交叉引用。
原包仅有答案摘要时，不能查询当前输出后把查询结果冒充独立基线。

完整原生→v3 导出、服务端正式下载操作和权限/许可证绑定仍未实现。
原 v3 3.0.0 要求非空规则/映射及已接受事实；CQs-only、无实例/无规则、未审核研究草稿不自动满足该协议。
不要放宽原 Schema 或借用参考包的 HR 内容/模拟审核来掩盖不兼容。

## 外部资源锁定与输入准备

```powershell
python tools/prepare_ontology_benchmarks.py --benchmark llms4ol_2026 --with-data
python tools/prepare_ontology_benchmarks.py --benchmark cq4oe_0_0_1 --with-data
python tools/prepare_ontology_benchmarks.py --benchmark oskgc --with-data
python tools/evaluate_research.py ontology-io verify-assets runtime/ontology-io/upstream/llms4ol_2026/315a9a5d883eada26e00fef1356a05802936c584
python tools/evaluate_research.py ontology-io prepare-inputs runtime/ontology-io/upstream/llms4ol_2026/315a9a5d883eada26e00fef1356a05802936c584 runtime_reports/flagship-inputs --task flagship --limit 3
python tools/evaluate_research.py ontology-io prepare-inputs runtime/ontology-io/upstream/llms4ol_2026/315a9a5d883eada26e00fef1356a05802936c584 runtime_reports/reuse-inputs --task reuse --limit 3
python tools/evaluate_research.py ontology-io prepare-inputs runtime/ontology-io/upstream/oskgc/b6a12ed38f131abb10ba22a785bba1d5d886aee0 runtime_reports/oskgc-inputs --task schema_guided_abox --limit 3
python tools/evaluate_research.py ontology-io prepare-inputs runtime/ontology-io/upstream/cq4oe_0_0_1/248e0c6cfa498c4630b17a83290628d9f8adc4b6 runtime_reports/cq2onto-inputs --task cq2onto --limit 3
```

输出目录必须不存在，防止覆盖已冻结实验。CQ2Term 使用 `--task cq2term` 和不同输出目录。
资源获取只读取固定 commit 的白名单，校验 Git blob、长度、SHA-256；不执行下载的模块初始化代码。
完整上游审计目录含 gold，不能挂入生成环境。输入适配只使用任务白名单；目标另存 scoring 目录。
LLMs4OL/OSKGC 的小样本由训练集按规范化文本哈希分组，再固定选择留出组，不按答案挑样本。
CQ4OE 的统计单位是整组本体 CQs，当前标 ADAPTED_ANALYSIS，不冒称官方测试或已建立开发/测试划分。
其 ODRL CQ2Term 文件确实存在重复编号 CQ13、CQ26；保留所有原始问题并登记歧义。

| 任务 | 已实现/实际执行 | 仍未完成 |
| --- | --- | --- |
| LLMs4OL Flagship、Reuse | 输入白名单、留出准备、原始预测与磁盘 RDF 绑定、exact 原函数及边界回归；Reuse 按原生 lower/空白归一化仅剔除输入已有边 | fuzzy/semantic 模型与配置隔离，官方 P/R/排名聚合确认、官方提交协议、真实完整流程对比 |
| CQ4OE CQ2Term、CQ2Onto | 固定发布版资源、CQs-only 输入，无 gold 注入/伪造实例 | 原生 TBox 输出、对齐/推理器/全部原生评分集成；未声称论文接收已核实 |
| OSKGC Airport 子集 | XML 输入及类别级 schema 白名单；固定原生 P/R、micro/macro F1、SS 方法测试和训练留出准备 | 带类型的实际语义输出适配与生成/评分 CLI 联通；未做完整 benchmark 模型实验 |
| Onto-Generation | 固定参考入口 | 原公开方法未复现，不能作为已运行 B1 |

LLMs4OL exact 原行为被保留：空图对空图 Graph Similarity 为 1/3；无 taxonomy 的完全相同普通关系图为 2/3。
不将其修改成我们的公式。OSKGC micro 用跨样本三元组集合，macro 用每文件已舍入 macro 的平均；
SS 保留按关系寻找首个 gold schema 及额外 schema 惩罚的原实现，不擅自修正。
OSKGC 代码 MIT，数据许可证标题为 CC BY-NC-SA 4.0、正文为 CC BY 4.0；保守限制科研使用，不进入商业建模交付。

## 公平比较原型与预算

配置见 `config/ontology_io/protocols/primitive-smoke.yaml` 和 `variants.yaml`。
默认模型名是显式占位符，不自动花费额度。使用前冻结模型 ID、声明修订、样本、主指标、
重采样和预算；不能看成绩后改这些字段。
本轮只检查到现有 Spark 兼容服务配置存在；配置别名不等于可核实权重修订，也不证明调用额度或有效性。

```powershell
python tools/evaluate_research.py ontology-io run runtime_reports/flagship-inputs config/ontology_io/protocols/primitive-smoke.yaml runtime_reports/ours-dry --system TwoAgentV3 --dry-run
# 以下 run 为真实提供者调用入口，不是本轮已经执行的成绩；先配置与审核隔离环境和预算。
python tools/evaluate_research.py ontology-io run runtime_reports/flagship-inputs config/ontology_io/protocols/primitive-smoke.yaml runtime_reports/b0 --system DirectGeneralLLM
python tools/evaluate_research.py ontology-io run runtime_reports/flagship-inputs config/ontology_io/protocols/primitive-smoke.yaml runtime_reports/ours --system TwoAgentV3
python tools/evaluate_research.py ontology-io run runtime_reports/flagship-inputs config/ontology_io/protocols/primitive-smoke.yaml runtime_reports/control --system DirectBudgetControl
python tools/evaluate_research.py ontology-io score runtime_reports/b0 runtime_reports/flagship-inputs runtime/ontology-io/upstream/llms4ol_2026/315a9a5d883eada26e00fef1356a05802936c584 runtime_reports/b0-report.json
python tools/evaluate_research.py ontology-io score runtime_reports/ours runtime_reports/flagship-inputs runtime/ontology-io/upstream/llms4ol_2026/315a9a5d883eada26e00fef1356a05802936c584 runtime_reports/ours-report.json
python tools/evaluate_research.py ontology-io compare runtime_reports/b0-report.json runtime_reports/ours-report.json runtime_reports/paired-report.json
python tools/evaluate_research.py ontology-io export runtime_reports/paired-report.json runtime_reports/public-scorecard.json
python tools/evaluate_research.py ontology-io schema runtime_reports/ontology_io_report.schema.json
```

当前 `TwoAgentV3` 系统 ID 对应**primitive pilot**：真实顺序执行 S1–S5，但 S4 仅图结构检查，
没有接入完整共享语义反馈修复，也没有获准 benchmark 检索资源。报告明确这些限制，不能称完整 Ours。
未启用的父组件不产生“消融成绩”；NoRetrieval 等变体在调用前拒绝，不运行成相同流程后改标签。
B0 为一次直接调用；DirectBudgetControl 按相同最大调用数做直接自检。人工比较 NOT_RUN。

相同输入/字符/上下文上界政策应用于所有变体，不截断一侧。每次失败也计入调用预算并保存公共回复；
未知 token/价格为 null，不当作 0。UTF-8 上界是保守计账，不冒充模型原生 tokenizer。
输入列表、样本×重复次数、失败、输出目录、实际图投影和源码工作树指纹全部核对。
漏行/重复行/改组/改协议不能让失败消失。成对统计先按独立组汇总重复，使用 95% bootstrap、
配对随机化及预先指定的 Holm 主指标校正；无跨任务自定义总分。

生成和评分为分开的 CLI 调用，模型没有文件/评分工具。但当前未实现强 OS 沙箱启动器，
本机 Docker Linux 引擎检查失败；不得把此原型称为已完成文件挂载级隔离。
因此本轮只执行离线/工程检查和 dry-run，**没有真实 B0/Ours 研究成绩、改进结论或专家验收结果**。

## 回归与界面

```powershell
python tools/evaluate_research.py --suite ontology-io-engineering
npm --prefix workbench test
npm --prefix workbench run typecheck
npm --prefix workbench run lint
npm --prefix workbench run build
python tools/run_browser_verification.py --selected-test ontology-io.e2e.ts
```

真实浏览器路由为 `/projects/:projectId/modeling/io`。文件上传使用现有鉴权 API，
拒绝不合法格式/敏感字段，区分 0、null/NOT_RUN、null/UNSCORABLE，显示对比/资源/限制。
导入报告只是外部声明，不是服务器签名、更不是生产审批。
浏览器测试验证导入前后项目权威版本、结果和 Registry 不变，退出后撤销临时测试凭证。
原始失败回执保留；最新汇总见 `requirement_traceability.md` 的执行记录。

## 后续 API 烟雾测试记录

用户随后明确要求使用本地 API key 和 `gpt-6-astra` / `xhigh`。
已完成 4 次真实合成工程请求：直接文本、双 Agent primitive 原型及双图识别均通过。
这更新了“尚无真实 API 烟雾调用”的历史状态，但不改变“完整外部基准对比未完成”的结论。
详见 [Astra/xhigh 实测说明](astra-xhigh-smoke.md)。
