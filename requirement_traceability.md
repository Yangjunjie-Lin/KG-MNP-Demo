# 立项 方法 实现与独立证据

本轮基点：`main@58473106efafb2e380e39577674d6968b3f62b82`，起始工作区干净；本轮不自动推送、合并、发布或提交榜单。

## 已核对资料

| 材料 | 实际证据与边界 |
| --- | --- |
| 本次任务 | 实际读取用户粘贴文本；本任务优先，不执行参考材料中的脚本/操作指令 |
| 研究内容(1).pptx | 指定文件未找到；实际读取仓库已锁定的 `docs/reference/zhigou-upgrade/附录/研究内容.pptx` 五页副本。不声称两个文件字节相同 |
| 技术栈.docx | 用户补充桌面原件，完整读取正文与全部五阶段方法；SHA-256 `a548949dff7158b8fc97acadd3327dad6e6c235dcb2663f6f290fc68d0251e69`。不声称与“技术栈(1)”字节相同 |
| 本体建模五阶段方法.docx | 指定独立文件仍未找到；技术栈正文覆盖了 1.1–5.5，按本次任务明确要求对齐 |
| 本体建模操作台 HTML | 已读取用户补充桌面原件，实际标识 `five-stage-console-v1`、页面自述本地模拟，SHA-256 `b8bec8e9ff553f5cf8ee0397b37bd4ba4ba961058e9cbe06107383f2dca19932`；不是 v3 双 Agent HTML，不执行或复制其中模拟逻辑 |
| 规则与任务执行 Agent v3 HTML | 指定版本仍未找到；实际双角色分工依据用户本次明确要求和已读取的 v3 交付配置 |
| v3 ZIP | 实际解压并读取 41 个文件；ZIP SHA-256 `e0f8967163a1731eea677866a9f68e3fcd8e31904f76170172300d9fdc82acf3`；文件摘要见 `docs/reference/ontology-v3/source-manifest.json` |
| v3 Schema | 原件 `contracts/delivery.schema.json` SHA-256 `21519fcac6c85fe1e2b3d2c3bd080e0576a135c2882d9d01326b8dc0cbf8fd80`，保持原义，不改写其 3.0.0 定义 |
| v3 采用边界 | 选择性参考；标准正式全文未核验，不继承参考包的“已核实”声明为本轮独立结论 |

## 工作对应表

| 立项/任务条目 | 五阶段 | 已有实现 | 本轮修改边界 | 证据与缺口 |
| --- | --- | --- | --- | --- |
| 对象 属性 关系识别 | S1 范围、S2 结构、S3 映射抽取 | `modeling/five_stage/`、`modeling/control_plane/` | RuleAgent 管 S1/S2；TaskExecutionAgent 管 S3；保持现有候选权威 | 原工程实测不能替代外部语义成绩；准确率粒度/分母待确认，另报 P/R/F1 |
| 专家审核后正确性 | S4 | `services/modeling_sessions.py`、原 review/权限/Worker | RuleAgent 自动校验，真实人类独立审核；旧版本 STALE | 真实专家实验 NOT_RUN；开发测试身份不得算专家 |
| 来源完整率 | S3/S4/S5 | Source、KG-IR、Evidence、`semantic_kernel/` | 逐字定位与语义支持分开，保留多来源，不凭同名合并 | 工程闭包、引用存在、位置可回查、事实支持分别报告 |
| 两个真实角色与路由 | S1→S2→S3→S4→S5 | 当前只有操作和投影，没有完整双角色调度 | 固定工具权限、摘要交接和执行收据；不新增第三个 Agent | 必须验证实际调用与拒绝路径，不能只改标签 |
| 语义与人工控制 | S4/S5 | pySHACL、OWL Profile、HermiT、冻结/精确编译 | 共用内核，不取消正式审核，不自动发布 | 原失败/未运行/超时保留，不计为 PASS |
| v3 与 .kgop 交付 | S5 | 原生 .kgop、摘要绑定导出、Registry | 从同一规范内容派生 v3；隔离加载与只读校验 | v3 Schema 含非空规则/映射、事实 ACCEPTED 等限制；不可无损表达的任务必须显式阻断或使用非生产诊断格式，不能伪造规则/审核 |
| 独立 I/O 评测 | 自动 S1–S5 | `tools/evaluate_research.py` 目前只跑工程测试 | 独立 generation/scoring、输入/输出适配、外部 scorer 锁定、BENCHMARK_DRAFT | 不把科研评测做成演进 Agent，不将分数带回生成 |
| 公平 B0/Ours | 自动阶段 | 尚无完整外部同模型比较 | 同输入、底座、预算与中立包装；保留失败和空输出 | 研究结果必须实际生成/计分；不预设提升 |
| 统计与界面 | 评测侧 | 现有 `stage-console.tsx` | 角色/真实状态与独立 I/O 页；原生分数、成对差值、CI、资源 | 不计算跨任务自定义总分；NOT_RUN 为 null |

## 本轮实际落地与未完成项（2026-09-13）

详细命令见 `docs/upgrade/ontology-io.md`。这里的“已测试”指工程测试，不是实测模型的语义成绩。

| 方法 | 修改/复用位置 | 本轮验证与边界 |
| --- | --- | --- |
| 1.1 输入核验 | 原 profile/input bundle；`five_stage/agents.py` | S1 后端路由、Worker 故障路径和范围不授予审批已测试；未新增来源权威 |
| 1.2 数据画像 | 原 five-stage profile | 真实种子接入/画像回归；没有提前生成新业务事实 |
| 1.3 范围与 CQ 草案 | 原 scope draft、配置模型 transport | 原缺模型/权限拒绝路径回归；本轮未调用真实模型生成研究结果 |
| 1.4 真实范围确认 | 原 session/review/权限 | 保留现有审核，Agent 不能调用 approve/publish；独立真人研究审核 NOT_RUN |
| 2.1 完整基线/imports | 原 baseline/编译器；`delivery/v3.py` | v3 仅加载锁定本地 imports，不联网，不合并历史；原完整基线能力复用 |
| 2.2 精确/向量召回 | 原 assistance/tools；真实 S2 invoke | 调用归属已落地；本轮 BGE/FAISS 研究实测 NOT_RUN，不伪造向量分数 |
| 2.3 重排与兼容 | 原 rerank | S2 路由；本轮原重排模型实测 NOT_RUN |
| 2.4 复用优先/受限补全 | `five_stage/assistance.py` | 原两轮生成、显式批准 IRI 与源绑定回归；研究 primitive pilot 不是完整复用流程 |
| 2.5 结构/约束候选 | 原候选/共享编译器；v3 closure | v3 目录、术语、domain/range、公理与实际 RDF 的闭包检查；不自动批准结构 |
| 3.1 映射 | `services/modeling.py`、assistance 的 deferred record_builder | 实际 S2 调用结束后才执行 records.map；原映射器/失败项复用 |
| 3.2 分块 | 原 tokenizer 与显式 Unicode 替代路径 | S3 真实工具路由、Unicode 定位回归；替代路径不冒充 tokenizer 实测 |
| 3.3 抽取 | 原 text.extract | S3、极性/未解决项边界测试；本轮仅录制/合成测试，不作 LIVE 结论 |
| 3.4 引文与证据 | 原 bind_quote；`delivery/closure.py` | 来源字节/版本、JSON Pointer、记录编号、字符区间/行号实际核验；不把定位当蕴涵 |
| 3.5 身份 | 原记录身份；研究 PER_SAMPLE_CANDIDATE_LABEL_V1 | 不改生产同名/未知目标策略；公共文本新实体发现的完整生产集成仍未完成 |
| 3.6 去重/冲突 | 原 normalize；v3 陈述/证据闭包 | 多证据保留，反向/负面/条件支持不折成肯定事实；研究 typed 输出未完整集成 |
| 4.1 完整性 | 原 integrity；v3 closure | 孤立陈述、缺规则/转换/目标、无效指针等负例；对象业务关系环不等于构建依赖环 |
| 4.2 语义检查 | 原 shared compiler、pySHACL、ROBOT/HermiT | 原候选语义服务真实回归；v3 SHACL 子进程真实运行、超时不 PASS；研究 pilot OWL NOT_RUN |
| 4.3 有限修复 | `services/modeling_assistance.py` | S4→S3 事实补丁→S4 重验保留；结构补丁返回 S2 与 research 完整反馈仍未完成 |
| 4.4 真实审核 | 原 review/session | 不把 benchmark/导入报告转成审批；没有新专家实验 |
| 4.5 冻结 | 原 confirmed package、CAS/session | 原 `.kgop` 重新验证；不新增状态/版本权威；Worker 失效仍禁止覆盖 |
| 5.1 三图编译 | 原 semantic_kernel | 诊断导出逐字保留原生三图；不是新生成的完整 v3 内容 |
| 5.2 配套明细 | 原 statement provenance；v3 reader | 引用/映射/转换闭包核验；原包欠缺的快照/定位/规则执行/审核交叉引用明确预检 |
| 5.3 实物复验 | `delivery/v3.py`、`ontology_io/adapters.py` | 固定 Schema 不能被清单关闭；磁盘图/投影/冻结输入与结果哈希校验；非完整正式符合性声明 |
| 5.4 独立验收 | 原 CQ 内核；v3 bounded SELECT | v3 原契约只接受精确 MULTISET SELECT；不从输出反造独立答案行；查询/SHACL 超时独立记录 |
| 5.5 v3 交付 | `delivery/native.py`、`delivery/cli.py` | 只读检查与原生兼容预检/非 v3 诊断导出已实现；完整原生→v3 导出和服务下载仍未实现 |

## 独立科研实现核账

- `ontology_io/contracts.py` 与 `config/ontology_io/ontology_io_report.schema.json`：机器报告格式、null/0、数据类型和状态约束一致性测试。
- `ontology_io/provenance.py`：提交号加实际工作树（含未提交/新文件）摘要；生成/评分运行时版本记录。不能只把脏工作树标为 HEAD 对应代码。
- `ontology_io/cli.py`：冻结样本×重复清单、路径/分组/协议一致性，失败不能缩小分母。generation/scoring 分调用，但强 OS 文件挂载隔离仍未实现。
- `ontology_io/statistics.py`：以文档/本体组而非三元组/重复调用为独立单位；95% bootstrap、成对随机化、预注册 Holm 主指标校正。无自创跨任务总分。
- `ontology_io/engine.py`：显式 bounded B0、直接自检预算控制和 two-role primitive pilot；保留失败、公开回复与未知 token/成本。不是完整 TwoAgentV3。
- LLMs4OL：Flagship/Reuse 各准备 3 个真实留出输入；锁定 exact 函数回归；Reuse 采用原生 lower/空白归一化剔除已有输入边，错误预测不丢弃。
- CQ4OE：CQ2Onto/CQ2Term 各准备 3 组真实公开 CQs；仅输入白名单，无虚构实例；ODRL 重复 CQ 编号保留。原生 TBox 产物与全套评分仍未接通。
- OSKGC：准备 3 个真实 Airport 训练留出输入；独立锁定 base_evaluator 和 hierarchy，原 P/R、micro/macro F1、SS 方法已做离线边界测试。typed 工件/生成/score CLI 集成未完成。
- `ontology.io.inspect`：真实鉴权、敏感字段拒绝和项目文件不变的后端测试；界面已跑真实浏览器上传及错误分支，非模拟业务 API。
- 已探测兼容模型配置为 `gpt-5.3-codex-spark` / `configured-alias:gpt-5.3-codex-spark`，没有发起本轮模型调用。别名不证明权重修订或可用额度。
- Docker 客户端存在，但 Linux engine 命名管道缺失；未声称当前达到强 OS 沙箱。未调用备用额度、未产生付费研究调用。

## 已保留执行记录

| 实际执行 | 结果 | 回执 |
| --- | --- | --- |
| 早期聚焦回归 | 58 passed；对应当时增量代码，不冒充最终全量 | `runtime_reports/two-agent-v3-focused.xml` |
| 第一次汇总工程回归 | 115 passed、1 failed，失败发生在新审计测试的种子任务，原租约门拒绝过期租约；不覆盖原失败 | `runtime_reports/research-74d26e68a14343d1817629f28cd53a01/` |
| 后续同组回归 | 116 passed；源码前后未变；未把不同实验成绩拼接 | `runtime_reports/research-b86131b5aa6843dbbc347b7047cffabd/` |
| 真实浏览器报告链路 | PASS；一次早先测试名字含 `/` 被项目校验正确拒绝，修正测试名称后通过；业务 API 未 mock | `runtime_logs/p09/browser-runs/managed-90fdba1b178a4ed19ddc0559841a5f30/managed-receipt.json` |
| v3 参考原包重读 | 工程检查/pySHACL PASS；OWL、REAL_APPROVAL NOT_RUN | `runtime_reports/two-agent-v3/reference-inspection.json` |
| 原生包兼容预检 | 原生 VALID；v3 导出 BLOCKED_REQUIRED_BOUND_INPUTS；没有新正式 v3 包 | `runtime_reports/two-agent-v3/native-preflight.json` |
| 原生语义诊断导出 | 3 图原字节 + 缺口说明，不含研究 gold、源码或来源快照；不是 v3 | `runtime_reports/two-agent-v3/hr.ontology-diagnostic.zip` |
| primitive pilot dry-run | DRY_RUN、score=null，未调用模型 | `runtime_reports/ontology-io-smoke/flagship-dry-run/run.json` |
| 前端组件/静态检查 | 42 tests passed；构建、TypeScript 和 ESLint 通过 | 本轮命令输出；真实浏览器另有上述持久回执 |

最终专项回归 **118 passed、0 failed、0 skipped**，源码前后摘要一致：
`7ca8206c287963fc4b34acc5ae2cc2a5e87a3c273c4cb351114c2619af22865d`。
回执：`runtime_reports/research-32f978ad886b40ac8ec484a4b1125a2b/verification.json`。
此外原生包/映射—审核工作流补充回归 **7 passed**，回执：`runtime_reports/two-agent-v3/native-workflow-regression.xml`。
全仓 `src tests tools` 的 Ruff、新增模块及服务 Pyright 检查均通过；没有声称跑完本轮全仓所有后端测试。
首次租约失效的具体时钟/调度根因尚未证实；没有延长/取消生产租约检查来隐藏这次失败。
最后新增了 primitive `is-a`/`instance-of` 大小写归一化的 RDF 角色回归，并显式升级研究投影编码；
原 `ontology-delivery/3.0.0`、`.kgop`、领域包锁和业务 IRI 均未改写。

机器可读工程/研究状态索引：`docs/upgrade/ontology-io-verification.json`。
结论仍是工程部分完成、没有新的真实外部模型对比成绩、三个立项目标均缺独立验收证据。

## 用户指定 Astra / xhigh 后续实测

2026-09-13：使用用户提供且与当前本地配置相同的认证密钥，完成 4 次 `gpt-6-astra` 真实推理请求。
全部显式发送 `reasoning_effort=xhigh`，未切换模型，未改变全局默认配置。直接文本生成、双 Agent primitive
原型均匹配 4 条合成事实并通过实际磁盘 RDF 复验；一次双图请求正确识别两个不同颜色排列。
合计约 39.06 秒；网关报告 3,870 token（推理 token 499 已包含在输出 token 中）。
网关未回显 effort，故仅确认请求配置，未证明代理上游强度/权重修订。

实测回执：`runtime_reports/astra-xhigh-smoke-c6d6e3a4c5ae4b7eb29c0304a2149f6c/report.json`。
无网络回归：57 passed，`runtime_reports/astra-xhigh-offline-regression.xml`。
对应说明与复现入口见 `docs/upgrade/astra-xhigh-smoke.md`；这是后续合成工程记录，不修改此前独立基准分数为空、完整实现未完成的结论。

## 立项目标与研究结论边界

自动识别准确率 ≥80%、专家审核后准确率 ≥90%、来源可追溯完整率 ≥90% 均保留为立项验收目标。当前没有独立专家标注与定义清楚的准确率分母，均不能宣布达标。外部任务按其原始公式分别评分，不以 F1 偷换“准确率”，不把工程检查或 v3 合规视为语义正确性。
