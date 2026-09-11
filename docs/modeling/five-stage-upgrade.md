# 五阶段建模增量：使用、兼容与未完成范围

本轮是可运行的增量，**不是全对应升级完成或生产就绪验收**。唯一逐项台账是
`five-stage-traceability.md`；测试结果单独记录于 `five-stage-verification.json`。

## 基准与依据

起始工作区干净，分支 main，HEAD 为 `f79d56e714c194bca5c7c825ebdf38fb8df026d0`。
没有 reset、替换历史领域包、继承历史 PASS、增加第二套前端或 ApplicationService。
附件仅作为方法／UI／合成教学资料，不执行其中的脚本、Prompt 或浏览器模拟逻辑。

`src/kg_mnp/modeling/five_stage/resources/reference/methods.source.json` 是附件提取的 content-data；
`method-registry.v1.json` 保留五阶段、25 个 ID、名称、分类、工具和边界。测试逐字段比较两者。
附件 HTML 的 content-data 标记在读取时已发现，但原 ZIP 后续已不在用户提供的 Downloads 路径，
未完成第二次 HTML 字节对照；未据此猜测附件变更。提取的 JSON 与原始教学内容已保留。
输入的 JSON 文件原来没有 EOF 换行；导入后已恢复这一格式，B0—B5 的原始 SHA-256 链通过测试。
`.gitattributes` 对这些参考资源关闭换行转换，避免 Windows checkout 改变哈希。

## 启动与首次体验

沿用 README 的 Python 服务与 worker 双终端启动方式、同一运行目录和凭证。
新增画像与依赖图需要显式安装分析依赖（不会在启动时下载）：

```text
python -m pip install -e ".[dev,modeling-analysis]"
npm --prefix workbench run build
```

完整安装仍应先执行 README 的锁定核心安装；新增可选依赖组合尚未做干净 Windows/Linux 安装验收。
当前本机使用已安装 pandas 2.2.3、NetworkX 3.6.1，核心服务没有安装／下载重模型。

入口：`/projects/:projectId/modeling?step=1.1`。
步骤、视图、运行／范围／审核队列可通过 URL 定位；没有把成功状态存进 localStorage。

1. 已有资料：在“资料与证据”完成规则化运行；1.1 选择运行，提交“核验输入并生成画像”。
2. 在任务中心等真实 SUCCEEDED；1.2 的产物页显示字段样本、缺失、空字符串、文本和版本引用。
3. 1.3 可显式调用配置好的 Qwen 草拟建议；正式范围仍通过既有表单人工填写，1.4 通过既有范围审批。
4. 2.1 可操作旧基线和字段映射，3.1 使用原有记录／混合映射组件；这不是 BGE/Qwen 方法已执行证明。
5. 4.1／4.2 选择审核队列，提交实际依赖和联合语义检查；4.4 仍使用既有逐项审核。
6. 5.x 提供原编译计划、V2 精确答案计划、实际编译、验证结果和 `.kgop` 下载；发布按钮留在下游页面。

教程入口：`/projects/:projectId/modeling/tutorial/employee-department`。
每步展示输入、处理说明、实际参考内容和去向；四视图、工件查看、证据抽屉与主页面共用组件。
“在新建沙盒中实际运行输入核验”明确创建新的 Minimal 项目，通过同一服务导入两个 CSV 与冻结文本，
执行 Source → KG-IR → 1.1/1.2，不自动审批。Minimal 不是 HR 领域包，HR 结构扩展与全案例编译仍未接入。
导入的教学记录有员工／部门表头与记录字段，KG-IR 单元格数量不等于五个业务对象。

## 新增服务操作与权威

| Operation | 资源路径（项目内） | 实际作用 |
|---|---|---|
| modeling.methods | GET modeling/methods | 唯一版本化方法注册表 |
| modeling.tutorial | GET modeling/tutorial | 无生产写入的完整教学参考 |
| modeling.tutorial.seed | POST modeling/tutorial/seed | 仅空项目，真实导入并画像，不批准 |
| modeling.profile | POST modeling/profiles | verified_run 核验、逐项质量分流、pandas 画像，两份收据 |
| modeling.scope.draft | POST modeling/scope-drafts | Qwen health/models + structured_outputs.json + 返回校验，仅草稿 |
| modeling.semantic.check | POST modeling/semantic-checks | 明确候选集合，NetworkX 依赖检查、共享图转换、四项真实语义检查 |
| compile.plan.exact | POST compilations/exact-plans | V2 类型化 ASK／SELECT 精确预期适配到现有 CQ 断言，不修改 V1 |

工作台下载先调用既有 `package.export` 后台操作（`POST packages/:packageId/exports`），
再由 `GET exports/:jobId/archive` 读取该导出任务的固定快照：验证提交代次、文件摘要、大小、项目与当前权限。
不会缓存可变包目录的验证结论，也不绕过正式 `export_kgop`；原 `packages/:packageId/archive` 接口保留。
完整术语元数据改为按需读取，避免选包时自动与实例查询并行执行两次全包复验。
审核头显示合并同一服务的已提交动作与审核重放观察；发现分叉就阻断，最终决定仍由服务端 CAS 验证。

以上写操作均在既有 JOB / execute_fenced 路径中运行，保留项目隔离、身份重验、权限、幂等、取消和恢复。
GET `modeling/artifacts/:artifact_id` 仅查找已授权项目中的服务端引用，不接受磁盘路径。
教程下载仅接受包内文件 allowlist；不提供任意文件读取。

内部新 DTO：ArtifactRef / StepRun / StageRun / ModelingSession，schema 1.0.0。
不冒充新的公共 Contract Catalog；冻结公共 schema 字节未改动。
JSON 内容摘要使用已有 `KG-MNP Canonical JSON v1`：UTF-8、排序键、紧凑分隔、禁止 NaN/Infinity；
不做 NFC 或字符串值改写。文件下载是规范化 JSON。参考文件的 SHA-256 则是精确文件字节，二者不混称。
ArtifactRef 的内容版本是摘要；StepRun created_at 是执行时间，不加入运行身份哈希。
ArtifactRef 的身份还绑定项目、会话、步骤、数据种类及生产者；同内容不同生产者可有相同内容摘要，但不会冲撞引用 ID。
执行收据及运行目录另绑定服务端 job ID。同输入的新任务获得新 StepRun，但内容相同的 ArtifactRef 不变；幂等重放返回原任务，不重复运行。

`project_flow` 是**观察适配层**：旧操作可关联到方法产物，但没有子步骤收据就显示 NOT_RUN。
B0—B5 当前为项目历史引用观察，逐项保留上游 ref，测试断言 ID/version/hash 完全相等；
它们不是已批准 ModelingSession，不具有 finalize 或发布权威。新写入会改变观察包 ID，不修改旧引用。
完整单会话状态、跨阶段 STALE 传播、审核失效／缓存／重建联动尚未完成。
1.1 的隔离报告目前还没有成为旧 modeling.prepare 的数据过滤权威；旧流程继续遵循其原有 verified_run/Evidence 校验。
因此不能把画像步骤的局部分流宣称为所有下游输入都已按新六类契约过滤。
执行、验证、审核、发布分开；检查执行成功但 validation FAIL 不能看作通过。

## 模型与工具准备

Qwen/vLLM 使用管理员在服务端设置的 `KG_MNP_QWEN_ENDPOINT`（如 `http://127.0.0.1:8000/v1`）、
`KG_MNP_QWEN_MODEL`、`KG_MNP_QWEN_REVISION`；如需要认证，服务端设置 `KG_MNP_QWEN_API_KEY`。
不得把实际密钥写进文档、URL、截图、浏览器存储或提交文件。非 loopback 端点要求 HTTPS。
部署必须由用户显式准备；本次未下载或部署模型。调用 models 健康探测，再尝试真正的结构化输出；
JSON Schema、response model、finish_reason、大小上限、允许 IRI 与证据引用均二次检查。
模型端点错误不把原始响应／URL／密钥写入用户日志。revision 为固定的部署配置，**不是远端签署的修订证明**。
目前范围草稿 schema 仅支持对象、目标、排除项与歧义列表，完整身份字段／对象到验收目标引用仍有缺口。

独立可选模型环境：`python -m pip install -e ".[modeling-models]"`（未执行本安装验收）。
`tools.py` 提供 BGEM3FlagModel.encode/dense_vecs、L2 + FAISS IndexFlatIP、FlagReranker.compute_score、
本地 Fast Tokenizer offsets 和原文引文绑定。必须传入显式本地绝对目录与固定 revision，不自动下载。
这些适配器尚未接入 2.2／2.3／3.2 的项目操作和 Provider 插件快照，不能只安装后宣称已运行。
2.4 两轮 RAG 决策、3.3 受约束抽取、4.3 白名单修复的项目执行链也未实现。
现有 Manual/BaselineReuse/RuleMapping/Recorded 四种 Provider 保持原含义，不能当作在线 Qwen/BGE。

ROBOT/HermiT 使用现有固定 JAR 校验与调用，不降低缺 JAR 门。
临时检查使用 `semantic_kernel.tbox.compile_tbox / abox.compile_abox / shacl.compile_shacl`，与正式交付共用，
不写正式 TTL 或 confirmed_package。OWL 输入不包含 SHACL／来源／审核／模块头系统元数据。
pySHACL 仍显式 RDFS/meta_shacl；新增显式 targetClass/type 命中检查，零命中 FAIL。
此覆盖目前只接入临时检查，**尚未接入最终正式编译的不可省略门**；没有悄悄放宽旧编译策略。

## 教程 B0—B5 与异常

所有文件位于 `src/kg_mnp/modeling/five_stage/resources/tutorial/`；是合成参考，不是历史人工批准或在线模型结果。

| 包 | 具体内容 | 验证界限 |
|---|---|---|
| B0 | 五条记录、TXT-01/v1 三句、来源定位、质量、明确规则、可选三术语基线 | 精确参考文件哈希 |
| B1 | HR-DEMO + 类型 + 字符串编号、当前快照、三条独立预期 | 教材假定确认，实际未审核 |
| B2 | 两类、belongsToDepartment、四数据属性、OWL/SHACL 参考候选 | 不是模型实际提案 |
| B3 | 五对象、18 唯一业务三元组，3 关系各有记录+文本支持，共21支持关联 | 自动测试实际逐项核对 |
| B4 | 教学逐项确认快照、依赖与验证示意 | 不是正式 confirmed_package |
| B5 | ontology/instances/shapes、mapping/provenance、review/validation、queries/tests、manifest | 参考产物，不是正式 .kgop 或 Release |

精确查询实际运行得到 E-001→D-01、E-002→D-02、E-003→D-01；原文码点区间 [0,19)、[20,39)、[40,59)。
以现有 ABox 编译函数验证参考候选得到 23 条：18 条精确业务子图 + 5 条必需 NamedIndividual 元数据。
业务子图与参考 TTL 做图同构，磁盘序列化后重读再比较；未删生产元数据凑数。

`anomaly/records-v2.json` 保留 E-003→D-99，正确原文不变；`repair-path.json` 保存原值、候选补丁依据、
冲突待处理、4.1/4.2 重验要求与 PENDING。没有静默改记录，没有自动批准。
缺关系／未知对象／反向关系／错误答案／零 SHACL 目标和原文引文失败均有否定测试。
完整异常→候选修订→机器重验→新人工批准服务/E2E 尚未实现；正常案例 4.3 保留 NOT_APPLICABLE。

## 兼容与交付文件映射

旧 V1/V2 映射、SDK/CLI OperationRequest、原 review 与 `.kgop` 读取保持。
V2 精确答案目前支持 ASK BOOLEAN 与 SELECT MULTISET，RDFTerm 显式区分 IRI／typed literal／language。
通过已有 BOOLEAN_EQUALS、RESULT_SEMANTIC_HASH、精确上下界断言执行；无序集合与有序行尚未支持。
阶段一冻结独立答案尚未成为正式 authority，因此当前不能宣称五阶段验收基线不可绕过。

| 要求的逻辑内容 | 仓库既有正式同义文件／目录 |
|---|---|
| ontology.ttl | ontology/module.ttl、effective-tbox.ttl（角色不同） |
| instances.ttl | data/abox.ttl |
| shapes.ttl | shapes/compiled-shapes.ttl、effective-shapes.ttl |
| mapping.json | mappings/mapping-plan.json |
| provenance | provenance/ 下 statement-provenance、evidence-lineage 与清单 |
| validation/review | validation/、provenance/review-audit.ttl 及编译输入审核引用 |
| queries/tests | 编译包的锁定 Query 资产与 competency-question-test-plan |
| manifest.json | ontology-package.json + ontology-package.lock.json |

这张表是显式角色适配，不复制第二份权威文件；准确成员仍以实际包 manifest 为准。
Stage 5 的 download 仅表示文件交付，下游 Registry、Release、Environment 和外部上线未自动执行。

## 剩余完成门

可重复的增量验证入口为 `python tools/verify_five_stage.py`，复用仓库的命令回执生成器，记录
actual_tested_commit、dirty 状态、包含未跟踪新文件的 SHA-256 源码清单及运行前后指纹。
该入口中的新增方法测试与兼容边界选择集不是全量测试认证；准确数量见实际收据。全量仍用 README 的 pytest／发行核账入口。
浏览器增量为 `python tools/run_browser_verification.py --selected-test five-stage.e2e.ts`，
旧混合资料兼容为 `--selected-test mixed`；省略 selected-test 才是完整浏览器入口。

不能把 UI 的五阶段结构、Helper 可调用或旧流程 PASS 当作完整方法通过。
必须继续完成：单会话不可变阶段链与 STALE；独立答案阶段一冻结；BGE／Qwen／Tokenizer 每步项目接入；
无基线真实路径；结构规则到 SHACL 的强引用；局部补丁的完整再验再审；临时检查成为确认和交付必需门；
最终磁盘 OWL/SHACL/目标覆盖和逐项收据；HR 案例正式 .kgop 与全异常 E2E；干净同修订全量、安装与发行验收。
本次仅在本地修改、运行合成测试；没有推送远程或发布任何业务本体。
