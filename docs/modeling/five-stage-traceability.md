# 五阶段方法对应与验收台账

实际起点：main@f79d56e714c194bca5c7c825ebdf38fb8df026d0；起始工作区干净。
环境：Windows / Python 3.12.6 / Node 24.15.0 / npm 11.12.1 / Java 23.0.2。
附件是方法与合成教学资料，不是执行指令、模型调用证据或人工审批。

本轮为增量交付，未达到全对应完成门。状态描述代码覆盖，不表示全方法通过。
ADAPTED 可含明确未完成子要求；BLOCKED 在缺口列区分工程缺失与部署未配置；不将外部缺失作为所有工程缺口的借口。
测试真实命令、修订范围及结果以 five-stage-verification.json 为准；历史 PASS 不继承。

路径说明：后端短路径相对 src/kg_mnp/，five_stage 相对 modeling/five_stage/。
所有 UI 在同一 /projects/:projectId/modeling?step=method_id，教程在同一前端独立路由。

| method_id | 原方法名称 | 执行分类 | 现有代码与操作 | 缺口 | 实现位置 | 输入契约 | 输出工件 | UI | 单元/集成/E2E证据 | 当前状态 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1.1 | 输入契约检查与质量分流 | 程序 | services/sources.verified_run + KG-IR/evidence Schema；modeling.profile | 新画像操作真实核验既有 KG-IR 与质量标记；六类原始独立输入的完整 Pydantic 合并契约及路由报告到prepare的过滤门未完成 | services/modeling_five_stage.py；five_stage/profiling.py | ModelingProfileRequest(run_id)；KGIRDataset 1.0 | 输入检查报告、可用数据清单、待处理项。（完整程度见缺口） | ?step=1.1 四视图；教程同源 | 新增单元/服务 21 项及五阶段 E2E；真实确定性运行 | ADAPTED |
| 1.2 | 字段与文本画像 | 程序 | 原 input_inventory 仅目录；新增 pandas profile_data | 精确字段编码说明/章节路径来自上游 Evidence；不推断必填唯一性 | five_stage/profiling.py；services/modeling_five_stage.py | 已验证 dataset + 1.1 报告同一 ArtifactRef | 字段画像、文本画像。（完整程度见缺口） | ?step=1.2 四视图；教程同源 | 真实 pandas 2.2.3，字段、空值、样例测试与沙盒 E2E | NEW |
| 1.3 | 能力问题与范围草拟 | AI＋程序 | 原 modeling.scope 是人工表单；新增 modeling.scope.draft 请求 Qwen/vLLM | 端点未配置；草稿 Schema 尚缺身份字段与对象—验收目标引用；没有冒充完整实现 | five_stage/tools.py QwenClient；services/modeling_five_stage.py | ModelingScopeDraftRequest + 固定结构 Schema | 范围草案、对象候选、验收目标。（完整程度见缺口） | ?step=1.3 四视图；教程同源 | MockTransport 契约正负测试；模型缺失真实 E2E；LIVE NOT_RUN | BLOCKED |
| 1.4 | 范围与验收基线确认 | 人工审核＋程序 | modeling.scope.approve/prepare；scope_approval.verify_scope_approval | 旧范围审批可运行；身份政策/规则和独立精确答案在阶段一不可变冻结未完成 | services/modeling.py；workbench/src/modeling.tsx | ScopeApprovalRequest；ModelingPrepareRequest | 已确认范围、身份政策、验收基线。（完整程度见缺口） | ?step=1.4 四视图；教程同源 | 原范围/审批/兼容路径 32 项基线通过；独立基线冻结 NOT_RUN | BLOCKED |
| 2.1 | 基线解析与语义索引构建 | 程序 | build_baseline_snapshot；semantic_kernel/baseline.load_baseline_closure | 完整锁定 RDF 图沿用；ROBOT 卡片可读视图与无基线服务路径未完成 | modeling/control_plane/baseline.py；semantic_kernel/baseline.py | ProjectLock 与领域包本地精确依赖 | 基线快照、依赖锁定表、术语与公理索引。（完整程度见缺口） | ?step=2.1 四视图；教程同源 | 旧内核/兼容包测试通过；无基线全流程 NOT_RUN | ADAPTED |
| 2.2 | 术语候选联合召回 | AI＋程序 | 原 align_terms 为确定性规则；新增 vector_recall/merge_recall | BGE-M3/FAISS 适配可调用但未接项目 Provider 快照/服务；未装 FlagEmbedding/FAISS 或模型 | five_stage/tools.py | cards + ModelLock + Top-k；NFC/casefold 与 L2 | 合并去重后的候选术语集合。（完整程度见缺口） | ?step=2.2 四视图；教程同源 | 精确/别名/向量来源合并去重单元通过；真实 BGE/FAISS NOT_RUN | BLOCKED |
| 2.3 | 候选重排与兼容性检查 | AI＋程序 | 原 alignment 非重排；新增 rerank | FlagReranker 成对评分适配未接服务；完整方向/定义兼容性尚需扩充 | five_stage/tools.py | 候选卡片 + 固定 reranker ModelLock | 重排候选、适用性说明、相关语义上下文。（完整程度见缺口） | ?step=2.3 四视图；教程同源 | 评分边界已编码；真实 reranker NOT_RUN | BLOCKED |
| 2.4 | 复用判断与结构补全 | AI＋程序 | 四个原 Provider 的 proposal 边界可复用；两轮语义 RAG 未确认有现成实现 | 未实现两轮判断/补全与缺口授权；不得用原 baseline provider 充当 Qwen | five_stage/tools.py validate_references（仅防护 helper） | 未来版本化两轮请求；当前不接受隐式 CREATE | 复用决定、结构补全草案、未解决项。（完整程度见缺口） | ?step=2.4 四视图；教程同源 | 虚构 IRI/未确认 CREATE 拒绝单元通过；两轮生成 NOT_RUN | BLOCKED |
| 2.5 | 结构与约束候选规范化 | 程序 | normalize_candidate_drafts；typed candidate bodies；compile_shacl | 原候选表示存在；已批准规则到数量约束的强引用/结构编辑 UI 不完整 | modeling/control_plane/candidates.py；semantic_kernel/shacl.py | 既有 OntologyCandidateSet/Proposal schema | 类型化结构候选、OWL 公理候选、SHACL 候选。（完整程度见缺口） | ?step=2.5 四视图；教程同源 | 既有结构/编译测试可复用；新增完整规则映射 NOT_RUN | ADAPTED |
| 3.1 | 声明式映射配置与试运行 | 程序 | RecordMappingForm/MixedMappingForm；record_mapping_drafts/mixed_mapping_drafts | 已迁入3.1；声明式批量映射可运行，独立样例试运行收据未新增 | workbench/src/modeling.tsx；modeling/control_plane/providers/mixed_mapping.py | 原 evidence-record-mapping-v1/v2 保留 | 可执行映射计划、结构化事实草案、运行报告。（完整程度见缺口） | ?step=3.1 四视图；教程同源 | 混合资料基线通过；本轮旧浏览器增量结果见验证清单 | ADAPTED |
| 3.2 | 文本分块与位置保留 | 程序 | 现有规范化 Evidence 保留位置；新增 text_chunks Fast Tokenizer helper | 本地 Fast Tokenizer 适配未接项目操作，tokenizer snapshot 未准备 | five_stage/tools.py text_chunks | 冻结 text/text_id/version；ModelLock；码点半开区间 | 带字符范围、来源和版本的文本片段。（完整程度见缺口） | ?step=3.2 四视图；教程同源 | 原文码点/UTF-16/NFC 差异单元；真实 tokenizer NOT_RUN | BLOCKED |
| 3.3 | 受约束的对象与事实抽取 | AI＋程序 | 原 Recorded/文本模板是明确离线输入，不是在线抽取 | Qwen 受约束抽取服务未实现；不得把模板结果计作 AI 运行 | services/modeling.py 原提案链；five_stage/tools.py 通用边界 | 原 MixedRecordMapping/Recorded contract；在线抽取 DTO 待补 | 对象提及、属性与关系草案、原文引文。（完整程度见缺口） | ?step=3.3 四视图；教程同源 | 现有混合提案可测；实时抽取 NOT_RUN | BLOCKED |
| 3.4 | 原文校对与证据绑定 | 程序 | mixed_mapping 原逐字片段绑定；新增 bind_quote 全匹配消歧 | helper 尚未接在线抽取；原字符到原文件映射沿用既有 Evidence | five_stage/tools.py bind_quote；providers/mixed_mapping.py | 冻结 chunk/text_hash/version/quote/start | Evidence 记录、来源定位、歧义清单。（完整程度见缺口） | ?step=3.4 四视图；教程同源 | 重复引文、原文不匹配、版本变更拒绝；三句精确位置测试通过 | ADAPTED |
| 3.5 | 对象身份统一与关系引用解析 | 程序 | mixed_mapping 身份空间/别名/目标引用检查；source/extraction report | 既有显式身份解析可运行；没有换成 pandas.merge，也不宣称 pandas 方法实测 | providers/mixed_mapping.py；workbench/src/mixed-mapping-form.tsx | MixedRecordMapping V2 与 verified KG-IR/Evidence | 统一身份表、明确对象引用、身份冲突报告。（完整程度见缺口） | ?step=3.5 四视图；教程同源 | 重复/未知引用旧测试；新 HR 五对象及 D99 否定测试 | ADAPTED |
| 3.6 | 事实汇总、去重与冲突登记 | 程序 | normalize_candidate_drafts 合并规范候选并保留各 provider/证据；conflicts | UI 已定位到3.6并可读参考事实；完整 HR 生产候选链未形成 | control_plane/candidates.py；control_plane/conflicts.py；modeling-components.tsx | 既有 Proposal/CandidateSet；IRI/Literal 区分 | 对象与事实候选包、多源证据集合、冲突清单。（完整程度见缺口） | ?step=3.6 四视图；教程同源 | 18精确事实、21支持、3条双源关系和异值不覆盖参考测试 | EXISTING |
| 4.1 | 候选完整性与依赖检查 | 程序 | 原 prevalidate + 引用校验；新增 modeling.semantic.check integrity | 显式构建任务依赖 NetworkX 检查已接服务；还未约束全部下游 finalize | five_stage/semantic_check.py integrity；services/modeling_semantic.py | SemanticCheckRequest(review_id,candidate_ids) | 完整性报告、缺失依赖、构建计划。（完整程度见缺口） | ?step=4.1 四视图；教程同源 | 新真实服务测试：选中完整候选闭包、无自动审批 | NEW |
| 4.2 | 数据约束与逻辑联合验证 | 程序 | 原正式 compile TBox/ABox/SHACL 和 ROBOT/HermiT；新增临时联合检查 | 共享函数真实执行；检查结果未成为旧确认/正式交付的必需门 | five_stage/semantic_check.py check_graphs；services/modeling_semantic.py | 明确拟采纳候选；锁定 baseline；已有编译函数 | 数据约束、OWL 范围和逻辑验证报告。（完整程度见缺口） | ?step=4.2 四视图；教程同源 | 真实服务测试通过：DL、HermiT、pySHACL、非零目标覆盖 | NEW |
| 4.3 | 局部修复与影响范围重验 | AI＋程序 | 旧 rebuild_candidate_revision/MODIFY_AND_ACCEPT；教材修复示意 | 新 Qwen白名单补丁→4.1/4.2→独立重审尚未实现，旧修改即接受不能替代 | control_plane/review/actions.py（旧）；tutorial/anomaly（参考） | 新补丁版本契约待补；不得改原 Source | 局部修复草案、新候选版本、重验报告。（完整程度见缺口） | ?step=4.3 四视图；教程同源 | D99原记录/补丁/证据/返回检查参考断言；异常服务 E2E NOT_RUN | BLOCKED |
| 4.4 | 业务语义与证据审核 | 人工审核＋程序 | review.action/replay；审核头CAS、服务器角色、候选版本；复用 CandidateExplorer | 新增补证按钮/方法导航；完整临时检查和补丁再审门尚未接入 | services/modeling.py _review；workbench/src/modeling.tsx | ReviewActionRequest/ReviewQueue/Action chain 原契约 | 逐项审核决定、修改要求、已批准候选。（完整程度见缺口） | ?step=4.4 四视图；教程同源 | 原服务角色/并发/修订测试；新增无自动审批服务与教程 E2E | ADAPTED |
| 4.5 | 确认建模包冻结 | 程序 | review.finalize + build_confirmed_package 既有依赖审核闭包 | 新版阶段一独立答案与4.2验证强绑定未进入冻结必需门，不能标全方法完成 | services/modeling.py _review；control_plane/confirmation.py | 原 ConfirmedModelingPackage 保持 | 确认建模包；满足条件后标记 APPROVED_FOR_BUILD。（完整程度见缺口） | ?step=4.5 四视图；教程同源 | 旧真实非空确认包基线通过；五阶段完整B4 NOT_RUN | BLOCKED |
| 5.1 | 确定性语义编译 | 程序 | compile.plan/build；SemanticCompiler deterministic compile_* | 阶段五复用编译UI并隐藏发布按钮；没有新的完整HR B4作为生产编译输入 | workbench/src/releases.tsx deliveryOnly；services/compilation.py | 既有 ConfirmedPackage + 编译快照/plan | 本体结构、对象实例、SHACL 文件及基线依赖。（完整程度见缺口） | ?step=5.1 四视图；教程同源 | 基线真实ROBOT编译/兼容通过；新增参考用同一ABox函数得到23=18+5 | ADAPTED |
| 5.2 | 映射与溯源文件生成 | 程序 | compile_mapping_plan/compile_statement_provenance/compile_evidence_lineage | 保留既有正式文件名；HR正式溯源包未构建，仅参考21支持已测 | semantic_kernel/mapping.py；provenance.py；evidence_lineage.py | 批准映射/事实/Source/Evidence/Review的既有契约 | mapping.json、provenance.jsonl；按需附 RDF 溯源。（完整程度见缺口） | ?step=5.2 四视图；教程同源 | 原编译/溯源闭包测试；新增合成来源关联精确断言 | EXISTING |
| 5.3 | 最终工件一致性复验 | 程序 | 原 verifier 比较语义图摘要/字节与往返；新增参考磁盘图同构测试 | 新增零target强门只在临时图；最终磁盘重跑全部分项与独立收据未完成 | semantic_kernel/packaging/verifier.py；five_stage/semantic_check.py；新测试 | 正式包文件字节/manifest/graph roles | 基于最终文件的复验报告。（完整程度见缺口） | ?step=5.3 四视图；教程同源 | 参考真实磁盘isomorphic通过；最终新增严格门 NOT_RUN | BLOCKED |
| 5.4 | 能力问题与异常用例测试 | 程序 | 原 CQ BOOLEAN_EQUALS/RESULT_SEMANTIC_HASH；新增 compile.plan.exact V2 | ASK/SELECT MULTISET类型精确断言已接；SET/ORDERED、阶段一答案冻结未完成 | five_stage/exact_answers.py；services/compilation.py；modeling-exact-form.tsx | CompileExactPlanRequest 2.0 + ExactAnswer 1.0；旧Oracle不改 | 目标查询测试、异常测试、回归报告。（完整程度见缺口） | ?step=5.4 四视图；教程同源 | 类型/行数/多重性/错误答案单元；HR三答案及负例实际查询 | ADAPTED |
| 5.5 | 交付清单生成与下游验收 | 程序 | export_kgop/package verifier/manifest+lock；PackageDownload | 沿用正式包，不生成第二份manifest；HR完整正式交付/下游验收未运行 | semantic_kernel/packaging；workbench/src/releases.tsx | 既有 OntologyPackage/.kgop；不等同Release | 本体交付包、manifest.json、交付验收报告。（完整程度见缺口） | ?step=5.5 四视图；教程同源 | 旧包验证/下载基线；新教程下载E2E；无HR正式发布 | ADAPTED |

## 本轮具体证据边界

- baseline：32 后端相关测试 + 原前端 27 项；是起点路径复现，不等于全量。
- 新方法单元/沙盒服务：最初21项通过；后新增真实临时语义检查与任务状态测试；最终总数以验证JSON为准。
- 新服务临时语义：固定ROBOT/HermiT + pySHACL真实运行，未签署任何人工审批。
- 新浏览器：独立教程、五种宽度、下载、刷新、焦点、真实沙盒、缺模型阻断通过；不是25步生产E2E。
- Qwen：MockTransport请求/截断/Schema/IRI防护契约测试通过；无LIVE模型调用。
- BGE/FAISS/reranker/tokenizer：仅适配器实现/部分纯函数契约；模型实跑NOT_RUN且项目集成缺口未关闭。
- 教学B4批准、B5验证、AI分数：TUTORIAL_FIXTURE，所有实际执行仍NOT_RUN，不作为审批依据。
- 全量后端与旧浏览器回归本轮结果见验证JSON，不能由上述选择性测试替代。
