# 本体建模评测交付：PARTIAL / BLOCKED

本次完成了版本审计、部分必要实现、固定外部源码/网页核对、全范围输入清单与预算枚举、
离线原生函数测试及防误报交付。**没有完成用户要求的完整五步 Ours、受控 OS 生成环境、
全部原生评分或真实外部 baseline 比较。没有取得支持提升的实验结果。**

研究结论各任务均为 **BLOCKED**，不是 SUPPORTED_IMPROVEMENT，也不是已经证明无提升。
score、paired delta、CI、p 均为 null；没有实验数据，不能推断等效、退步或跨任务优越。

## 实际版本与修改

起点本地/远端 develop：`adc2a40512f8b029b6c21420b905628c32952d00`，与前审提交相同；
起始工作树干净。最终实现摘要：
`45688ee99f530c1fa20bb322959e4b1fdc4f7cebcf2392b16ab8310b63267eb5`。
受测前后摘要相同；源码身份覆盖未提交新文件，不把工作树冒充原 HEAD。
未提交、推送、合并、发布、提交 Google Form/排行榜，也未执行业务动作。

- Reuse 将官方 terms/types 与 initial ontology 一并交给所有系统；不从 gold 推导。
- CQs 保留原始编号与稳定复合 occurrence ID；整套本体作为独立组，同本体跨任务绑定。
- B0/Bbudget 增加 CQs→terms、CQs→OWL 和 typed ABox 输出契约；OWL 匿名限制/公理保留，
  typed facts 与 schema 对应保存。冻结产物重读、哈希和图同构验证，不生成第二份“美化答案”。
- LLMs4OL exact/fuzzy 独立调用固定原函数；fuzzy 的阈值和依赖已锁。
  CQ2Term 仅接通原生 hard per-method term P/R/F1/coverage，明确不是完整 benchmark scorer。
  OSKGC 评分 CLI 接入原生分重复聚合，但授权真实数据端到端运行仍未完成。
- 增加跨任务 source/exact-text/5-shingle 近重复连通组、无 limit 分区准备、全清单、
  有界预算枚举及不可变上下文 resume。公开目标本体、训练示例/检索语料均未授予生成访问。
- 新增非可加指标原生重算的 paired cluster bootstrap / 小样本精确 cluster exchange 工具。
  可加报告 compare 已改成先每重复聚合再平均，保留组内样本权重；非可加 CLI 比较在未连接
  native payload callback 前明确拒绝，不退化为平均每题 F1。
- 真实 benign canary 证明普通 `python -I` 子进程仍能读相邻 scoring 目录。
  `run` 在总预算未授权、OS隔离未实现时 fail closed，不靠 `raw_gold_access=false` 放行。
- 没有修改鉴权、审批、版本保护、v3 正式 Schema 或其他业务方向。

旧 `TwoAgentV3` 仍是 **PRIMITIVE_PILOT_PARTIAL**；没有改名冒充完整 Ours。
`OursFull` 只出现在“待执行矩阵”中，未实现、未被调用；NoRetrieval、NoConstrainedExtraction、
NoValidationFeedback 继续阻断，因为其父研究系统没有实际启用组件。
没有伪造消融、SHACL shapes、CQs-only ABox、人工 APPROVED/ACCEPTED 或生产交付。

## 实际准备范围与完成度

| benchmark / task | full 已准备样本 / 独立组 | 计划系统×重复 | 成功 / 失败 / 未运行 | 分数及结论 |
| --- | ---: | ---: | ---: | --- |
| LLMs4OL Flagship | 3471 / 3471 | 3×3 | 0 / 0 / 31239 | null / BLOCKED |
| LLMs4OL Reuse | 2252 / 2252 | 3×3 | 0 / 0 / 20268 | null / BLOCKED |
| CQ2Term | 6 / 6 | 3×3 | 0 / 0 / 54 | null / BLOCKED |
| CQ2Onto | 6 / 6 | 3×3 | 0 / 0 / 54 | null / BLOCKED |
| OSKGC 全类别官方 test | 0 / 未知 | 尚不能定总样本数 | 0 / 0 / 未知 | null / BLOCKED_LICENSE |
| Ontogenia / Memoryless CQbyCQ | 未冻结论文数据运行 | 未执行 | 0 / 0 / 未知 | null / BLOCKED |

以上是计划记录，不是调用量。**本轮真实模型调用 0，真实外部预测 0、外部评分 0。**
失败数 0 不意味着完成；51,615 个可枚举行全部 NOT_RUN。调用 token/时间/费用未知项为 null，
真实已发模型 calls=0。历史 Astra 四次合成 smoke 保留，不计入本轮对比。

LLM 官方 train 全量是 4303/2774，冻结分区分别为：

| 分区 | Flagship | Reuse | 用途 |
| --- | ---: | ---: | --- |
| smoke | 408 | 285 | 仅冻结 hash 分区，未运行；不是建议对所有分区样本做 smoke 付费 |
| pilot | 424 | 237 | 与 full 分组不交叉；未运行，不用于 full 调参 |
| full | 3471 | 2252 | 全部冻结本地留出候选，无 limit、无结果筛选 |

分区规则为公共记录连通组 hash %10：0 smoke、1 pilot、2–9 full。
`FULL_LOCAL_HOLDOUT` 是计划范围名称，**尚未获得强防泄漏正式实验资格**：
历史开发触及范围审计、缺失的源本体分组/语义近重复仍未清除；不能把词法 hash 当成完全独立证明。
预训练污染标 `POSSIBLE_PUBLIC_DATA_CONTAMINATION`。

CQ 的六套本体全部保留给 full，不拿它们重复做公开 pilot。
实际 CQ2Onto 为 AWO 7、ODRL **18**、SWO 35、VGO 31、Water 21、Wine 5（共117）；
CQ2Term 为7、19、26、22、20、5（共99）。固定 README 对 ODRL CQ2Onto 写19，
实际锁定输入文件为18，报告采用文件数，不补造第19题。
每个任务独立本体数都是6，不能把117/99题或3次调用重复视为更多独立领域。

OSKGC 完整 tree 枚举到57个 test XML文件（19主题×3三元组规模）；未下载新数据，
不把全数据集10183的 README 描述当成本地 test 样本数。旧 Airport 数据未删除/再分发。

## 预算与实验资格

仅枚举上述可用 full 输入：5735任务输入 × 3系统 × 3重复 = **51,615运行单元**。
设计最多 **154,845次调用**：B0 17,205、Bbudget 68,820、OursFull计划68,820。
按每运行120,000 token保守额度，预留上限 **6,193,800,000 token**。
这是保守设计额度，不是预测实际消耗；Ours完整组件未定、论文/OSKGC范围未定，
因此不是全项目可靠付费上界。费用=null，不自行转换为金额，不新增任何付费调用。

模型协议暂记既有 smoke 配置 `gpt-6-astra / xhigh`，声明修订为网关 alias，
不是独立验证权重。当前 transport 不发送 seed，也未固定生成采样参数，协议明确
`BLOCKED_NOT_PREREGISTERED_READY`；[17,29,43] 只是待服务支持时的设计选择。
配置中 `total_budget_authorization: null`，不是人工审核，更不是付费授权。

具体阻塞：

1. **BLOCKED_BUDGET_UNSET**：本轮未授权整套付费预算；旧4-call授权不能无限扩展。
2. **BLOCKED_OS_ISOLATION**：Docker Linux engine不可用；独立权限账户/最小挂载/模型端点唯一网络
   放行 worker 未实现，canary 实际可读。未修改用户账号、系统ACL、防火墙或启动Docker服务。
3. **PARTIAL_OURS**：尚未把完整共享两轮复用、结构设计、受约束抽取、共享编译和S4→S2/S3反馈
   接进研究输入。不以生产中存在这些函数推断研究 Ours 已调用。
4. **CQ4OE完整原生评分**：top3对齐、embeddinggemma权重、OWLReady2/HermiT与完整公理/CQCoverage
   配置未冻结；hard term测试不是替代品。LLMs4OL semantic同样因远程模型锁阻塞。
5. **OSKGC许可**：冲突未澄清，不推定数据使用或再分发授权。
6. **Bpaper**：读取作者实际提示词/代码片段；Ontogenia所引用patterns.csv/独立procedure资源
   在固定树中缺失。Memoryless提示词可见，但CQs-only与论文story输入适配、原始数据使用及预算未冻结。
   两者均未复现；没有用LLM自评替代作者的人工指标。
7. **正式v3出口**：仍缺，不改变研究草稿可以单独评分的边界。

只有预算授权也不足以启动有效 full；其余工程/资源阻塞仍须解除。
因此本次不是“实验完成但没提升”，而是“增量实现完成一部分，正式实验未完成”。

## 实际工程验证

最终受测源码未变化，以下命令均退出0：

- `python -m ruff check .`
- `python tools/check_types.py`：0 errors / warnings。
- `python tools/evaluate_research.py --suite ontology-io-engineering`：**149 passed，13 warnings**。
- 变更模块新增测试独立重跑：**26 passed**。

26个检查涵盖fuzzy原函数等价、CQ原函数hard等价、空/部分/重复/反向/类实例混淆/层级、
OWL restriction往返、typed绑定、gold修改请求不变、失败不缩小分母、无凭证评分、resume漂移、
非可加指标重算、canary证实未隔离。没有 semantic 原模型测试或真正OS访问拒绝成功测试。
原五步角色、模型辅助、v3、native delivery、服务 fencing 回归仍由原 suite执行；不重做平台。

日志/源码清单：`runtime_reports/ontology-io-final-verification-20260913/`；
suite详细日志/JUnit：`runtime_reports/research-5895dd59a83e4762bd50f339cabea8a3/`。
首轮 `research-7cc8176ba88c4d43aa47f23d4176648d` 的123个测试通过，但期间源码修改，
整轮source guard失败，原失败回执保留；不能算有效最终验证。
开发期间捕获的语法/类型/lint问题已修复；详见[失败分析](failure-analysis.md)。

## 交付索引与离线复现

- [修改前审计](audit-before.md)、[资源和指标追踪](benchmark-sources.md)。
- [机器证据](execution-evidence.json)、[逐系统结果CSV](results.csv)、[比较状态](comparison.json)。
- `manifests/`：5735条 full样本ID/组ID及各task资源/输入/split摘要；不含gold正文。
- `native-source-audit.json`：固定上游函数/依赖/文件SHA；不执行上游初始化。
- `scorecards/`：5份通过现有报告Schema的task级NOT_RUN文档，可上传现有只读报告页。
  导入不能授予审批，也不会将这些null改成测量值。
- 完整public inputs/scoring targets分目录、split/近重复审计、逐样本×系统×重复NOT_RUN台账、
  资源/运行/文件哈希保存在 `runtime_reports/ontology-io-final-matrix-20260913/`。
- full首次回执：`full/attempts/45f3240c0c364bc6bc7ea84f0391fde6/`；实际resume回执：
  `full/attempts/7ac6182696cc448987efefb776bc8521/`。freeze相同，旧尝试/失败不覆盖。

[复现命令](reproduce.ps1)可直接在仓库根目录PowerShell执行，不需要模型凭证。
矩阵命令现在**执行准备/冻结/资格核查并返回BLOCKED**，不是已经实现完整付费生成的入口。
不提供一个假装加预算就能跑完整Ours的命令。

已有合法冻结预测可以独立离线重评分：

```powershell
python tools/evaluate_research.py ontology-io score '<冻结run目录>' '<对应prepared目录>' '<固定upstream目录>' '<新的score.json>'
```

支持LLMs4OL exact/fuzzy、CQ2Term hard-per-method、许可满足的OSKGC原生聚合；
不需要读取模型配置/凭证。当前没有本轮真实预测目录，所以该命令不能产生本轮研究成绩。
完整CQ2Onto/semantic会返回明确阻塞，不生成伪零分。

统计工具和CI测试是计算正确性的证据，不是有效性实验的效应量。
每个benchmark分别报告，不构造跨任务“本体质量总分”。
