# 模块契约与独立调用

原模型和独立多模态观察接口的追加验收、运行方法及边界见 [原模型与多模态实测](original-models-multimodal.md)。OCR/ASR 观察不是确定性 Evidence 文本，不会由原接入流程自动入库。

所有操作通过同一 `ApplicationService.execute(OperationRequest, principal)`、Python SDK、CLI 或认证 HTTP API。
写操作沿用 Worker + copy-on-write generation + 项目 CAS；权限在提交和发布代次时再次检查。
通用 HTTP：`POST /api/v1/operations/{operation}`，JSON 中带 `project_id` 和该操作 DTO 字段，写请求带幂等键。
工作台适配：`POST /api/v1/projects/{id}/toolchain/{operation}`，只开放明确白名单。

| 模块 | 输入 | 输出/可独立调用操作 |
| --- | --- | --- |
| 接入 | 文件上传或已登记 Source；显式 Batch、Plan | `source.batch`、`ingestion.plan/run`；KG-IR、Evidence、quality。`source.sample.load` 仅空项目加载锁定领域包的合成 CSV/TXT |
| 建模 | verified run、业务规则、冻结精确预期、配置、范围审核 | `modeling.session.open/revise`；原 scope/prepare/proposal/semantic.check/review.finalize |
| 服务/版本 | 固定已验证包或明确 Release | 原 registry.import/release/oms.metadata/ods.query/object.trace/environment 操作 |
| 执行 | 包版本、业务目标；Domain Pack 中锁定的声明式动作策略 | `task.plan`、`task.execute`、`business.inspect`；计划、工单、待核实清单、动作收据与磁盘重读 |
| 演进 | 实际 execution_id、人工反馈、候选 priority/version | `evolution.propose/evaluate/review/activate/rollback`；回归前后、审核、活动配置及历史 |

## 新版建模会话

`modeling.session.open` 输入：run_id、business_rules、acceptance（每项为 query_asset_id + ExactAnswer）、configuration、expected_revision。
服务重读 verified_run，冻结内容摘要。新旧会话留在项目 `registry/`，每次写入仍由项目代次事务发布。
同输入不会凭空生成新语义结果。换输入、映射、配置或结构后，下游引用标 STALE；
旧审核、旧确认包、旧编译计划不能用于新活动会话。历史正式包不删除。
只读历史和旧 API 的兼容工作区不是五阶段认证；严格门需显式开启会话。

冻结门要求 integrity、explicit_target_coverage、SHACL、OWL Profile、HermiT 对**完全相同拟采纳候选**和依赖均 PASS。
NOT_RUN/FAIL/ERROR/TIMEOUT/UNSUPPORTED 不等于通过。修复由新映射/新候选开始，重新检查和审核；
严格会话拒绝 MODIFY_AND_ACCEPT。第五步只能使用第一步冻结的类型化独立答案。

无业务基线时可选择 `empty@0.1.0`（只有本体管理头，没有既有业务类/属性/约束），
通过 `modeling.proposal` 的 `manual_drafts` 提交现有闭合 CandidateDraft 契约。
该参数只能与单独的 manual-candidate-provider 使用，不能混入另一份 record_mapping。
新结构仍需检查、逐项人工审核和精确查询验收，不接受上传的 APPROVED 字段作为权威。
自由文本业务规则被版本化冻结；自动把任意自然语言规则完整转成 SHACL 并证明等价仍未实现，
需明确的领域包/结构化候选约束与独立预期，不能声称所有自然语言语义已经校验。

## 可选 LIVE 建模提案

`modeling.proposal` 的 `model_assistance` 配置包含 execution_mode=LIVE、action=GENERATE/REPAIR、
retrieval=LLM_SUBSTITUTE/BGE_FAISS、chunking=UNICODE_SUBSTITUTE/LOCAL_TOKENIZER、
approved_new_iris 和当前 expected_session_revision。REPAIR 另需当前 parent_proposal_id，
不能同时替换父版本的映射/手工输入。providers 使用 manual-candidate-provider（闭合草案传输）及可选 baseline-reuse-provider。
服务在同一 Worker 暂存代次中生成新候选和完整语义重验；失败检查不授予冻结资格。

BGE_FAISS 使用服务器 `ZHIGOU_BGE_{MODEL,REVISION,PATH}` 和 `ZHIGOU_RERANKER_{MODEL,REVISION,PATH}`；
LOCAL_TOKENIZER 使用 `ZHIGOU_TOKENIZER_{MODEL,REVISION,PATH}`。须提前准备本地快照，不自动下载。
兼容 API 使用 OPENAI_BASE_URL、OPENAI_TEXT_MODEL、OPENAI_API_KEY、OPENAI_RESPONSE_FORMAT；
显式 Qwen 配置存在但不完整时不回退。密钥不写入项目、URL、日志或前端。

合成 API 全链路验证：`python tools/verify_live_assistance.py --pack hr`，
或 `--pack forestry-workorders`、`--pack repair`。输出目录每次独立，失败也保留记录。
生成/修复上下文不包含第一阶段冻结的标准答案。录制传输层与 LIVE 调用收据分别说明。

## 动作与反馈

动作注册表只允许 `create_work_order@1.0.0`，权限 `action:work-order:create`。
Domain Pack 提供类/谓词/明确状态字面值，不提供脚本或权限。未知值进入 VERIFY，否定值 SKIP。
工单自然键是项目+业务对象+巡查，重复请求、重复规划和重复包版本不能重复建单。
所有执行读取固定包的 OMS、对象与证据，不连接任意数据库。
当前批量对象读取服务在一次请求内复用同一份新鲜验证包，并一次重验来源闭包；
不跨请求缓存“验证通过”，也不反复为同一不可变快照重新加载整个包。
反馈只支持已实现的工单优先级配置分支；不声称自动优化任意 Prompt/规则。
激活前回归检查和人工审核必需；生产审核配置拒绝作者自审；激活再次核验审核身份。
回滚使用活动配置摘要 CAS，不回溯改写既有业务记录。

## 独立评测与模式

`module.evaluate(module, job_id)` 只读取同项目、匹配模块的已提交真实运行，验证代次和输出摘要。
模块为 framework/ingestion/ontology/evolution。报告保留样本量、分母适用范围、时长和证据。
`python tools/evaluate_research.py --suite <模块>` 提供独立工程测试命令；`safety` 提供负向边界。
不把契约评测当作模型准确率评测。DETERMINISTIC、RECORDED、LIVE 分开，数据来源与执行环境另记。

## 适配覆盖

CSV/TXT/JSON/Markdown、DOCX/XLSX 和可提取文本 PDF 沿用现有真实解析器。
图片、WAV 的元数据解析不称 OCR/ASR；图像 OCR、音视频转写、卫星遥感、SFTP、队列和政务 SDK
需要独立适配/部署与真实样本。REST 上传和 Python SDK 是现有可调用边界，不冒充所有上游系统已接通。
