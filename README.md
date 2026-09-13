# 知构工具链 · ZhiGou Toolchain

可组合、可验证、可追溯的本体工程工具链（Ontology Toolchain）。以独立领域包提供业务语义，
将资料接入、五步本体建模、服务与版本管理、任务执行和反馈演进连接到同一个授权服务和 Worker。

当前源码版本 0.9.0rc2；本地增量不等于正式发行资格。受测源码与真实结果见
[升级索引](docs/upgrade/research-module-map.md)、[实施边界](docs/upgrade/modeling-five-stage.md)及
[验证记录](docs/upgrade/verification.json)。历史 PASS 只适用于原修订。

原模型与多模态的追加实测、固定输入及模型能力差异见
[原模型与多模态验收](docs/upgrade/original-models-multimodal.md)。

## Windows 本地启动

在项目根目录运行。现有环境可以直接使用；首次安装按锁文件准备依赖：

```powershell
$env:PYTHONUTF8 = "1"
python -m pip install -c requirements-dev.lock -e ".[dev,modeling-analysis]"
npm --prefix workbench ci
npm --prefix workbench run build
python tools/prepare_reasoner.py
python tools/start_zhigou_demo.py --port 8765
```

本地入口：[http://127.0.0.1:8765](http://127.0.0.1:8765)。默认使用已构建的前端，
API 与 Worker 在同一**隔离合成工作区**启动。端口被占用会报错，不会杀其他进程；
也可省略 --port，使用启动信息返回的可用端口。

启动只打印 URL、工作区与临时凭证文件路径，不打印密钥。读取该本地文件的 token 并在登录页输入；
不要把凭证复制到日志、Git、截图或远端。Ctrl+C 只停止此次启动的服务器/Worker并撤销临时身份。
此方便入口的全权限身份仅用于合成演示，不应用于生产或真实用户数据。

首次登录创建 hr@0.1.0 或 forestry-workorders@0.1.1 项目，在“数据接入与规则化”加载
当前领域包的合成批次，也可上传自己的授权测试文件。加载仅进行真实规则化，不自动批准或发布。
详细操作见 [walkthrough](docs/upgrade/walkthrough.md)。

## 独立服务方式

与原服务方式兼容；需管理员明确签发最小权限身份。两个终端使用相同 workspace/config：

```powershell
$env:ZHIGOU_SERVICE_HOST = "127.0.0.1"
$env:ZHIGOU_SERVICE_PORT = "8765"
$env:ZHIGOU_ALLOW_INSECURE_LOOPBACK_SESSION = "true"
$env:ZHIGOU_DOMAIN_PACKS_ROOT = (Resolve-Path domain_packs).Path
$env:ZHIGOU_WORKBENCH_ROOT = (Resolve-Path workbench/dist).Path
$env:ZHIGOU_REASONER_JAR = (Resolve-Path third_party/downloads/robot-1.9.7.jar).Path
python -m zhigou_toolchain service serve --workspace runtime/zhigou-local
# 另一终端，使用相同环境设置：
python -m zhigou_toolchain service worker --workspace runtime/zhigou-local
```

HTTP 明文例外严格限 loopback。非本地部署使用 TLS、明确 Origin 和生产多角色审核。
示例只读身份签发命令（输出包含秘密，只在安全终端执行）：

```powershell
python -m zhigou_toolchain service token create --workspace runtime/zhigou-local --principal-id local-reader --created-by local-admin --permissions project:read,source:read,package:read
```

不要为了通过测试关闭鉴权、延长为永久会话或给真实用户全权限。
本轮验证环境为 Windows；Linux/外部部署若无对应运行证据应视为未测。

## 五个主模块

| 模块 | 实际职责 |
| --- | --- |
| 数据接入与规则化 | Source/Batch/Plan/KG-IR、类型化来源、质量与处理轨迹；独立评测 |
| 本体建模 | 输入核验与范围确认；本体复用与结构设计；数据映射与事实构建；联合校验与人工审核；语义编译与交付验收 |
| 本体服务与版本管理 | 原 Registry/Release、固定版本 OMS/对象读取/证据、环境选择与回滚 |
| 任务规划与业务执行 | 声明式领域策略通过 OMS/对象服务生成固定版本计划，只执行登记动作并重读真实工单 |
| 反馈评估与演进 | 实际执行反馈、隔离回归、人工审核、执行配置更新和回滚；本体变更仍走原版本流程 |

新版严格建模会话冻结输入、规则、配置和独立答案，后端传播 STALE，拒绝旧审核与旧计划。
五步页面不再显示 25 个小步骤或独立案例教程；旧教程 URL 重定向到建模入口。
技术详情、来源和历史收据仍可追溯；原方法台账作为历史文件保留。

## 测试与证据

```powershell
python -m ruff check .
python tools/check_types.py
python tools/evaluate_research.py --suite safety
python tools/evaluate_research.py --suite ontology
python tools/evaluate_research.py --suite framework
python tools/evaluate_research.py --suite ingestion
python tools/evaluate_research.py --suite evolution
python tools/run_backend_tests.py
npm --prefix workbench run lint
npm --prefix workbench run typecheck
npm --prefix workbench test
python tools/run_browser_verification.py --selected-test zhigou-console.e2e.ts
```

独立测试与完整回归分别记账。实际浏览器测试启动真实 API 和 Worker，不 Mock 核心服务。
合成 HR/古树工单仅证明工程链；不证明研究目标达成、实际专家准确率或外部上线。
数值目标、运行方式与适配边界见 [模块契约](docs/upgrade/module-contracts.md)。

较长 Windows 工作目录中的嵌套 Git 测试需为本次验证进程启用长路径。
以下设置保留已有进程级 Git 配置，不修改全局 Git 配置：

```powershell
$zgGitConfigIndex = 0
if ($env:GIT_CONFIG_COUNT) { $zgGitConfigIndex = [int]$env:GIT_CONFIG_COUNT }
[Environment]::SetEnvironmentVariable("GIT_CONFIG_KEY_$zgGitConfigIndex", "core.longpaths", "Process")
[Environment]::SetEnvironmentVariable("GIT_CONFIG_VALUE_$zgGitConfigIndex", "true", "Process")
$env:GIT_CONFIG_COUNT = [string]($zgGitConfigIndex + 1)
python tools/verify_zhigou_upgrade.py --backend-only --workers 4
```

该入口记录源码前后摘要、完整测试收集与执行节点、真实退出码；不因局部复测通过抹去原失败。

## 模型配置与限制

可选服务端配置：ZHIGOU_QWEN_ENDPOINT、ZHIGOU_QWEN_MODEL、ZHIGOU_QWEN_REVISION，
以及必要时的 ZHIGOU_QWEN_API_KEY。模型目录/修订必须明确，不在运行时偷偷下载。
若未配置 Qwen，可使用已有 OPENAI_BASE_URL、OPENAI_TEXT_MODEL、OPENAI_API_KEY 和 OPENAI_RESPONSE_FORMAT。
兼容网关的 json_object 输出仍经过本地 Schema、引用、逐字引文与原语义门检查；不是服务端严格 Schema 证明。
部分 Qwen 配置存在时不静默回退；未配置/无效调用明确失败，不用关键词规则冒充模型推理。
第二/三阶段可显式运行两轮建模和文本抽取，第四阶段可请求白名单修复与自动重验；
LIVE 提案同时要求 model:propose 和 source:read。新候选仍必须重新人工审核，不能直接发布。

```powershell
python tools/probe_upgrade_models.py
python tools/verify_live_assistance.py --pack hr
python tools/verify_live_assistance.py --pack forestry-workorders
python tools/verify_live_assistance.py --pack repair
```

以上验证只使用独立合成数据，记录真实调用及失败，不向生成/修复流程提供冻结的标准答案。
若额度耗尽且用户已授权，可在确认网关开放后为新的服务进程切换 OPENAI_TEXT_MODEL；
模型变更记录在新请求收据中，不把替代模型标为原模型。本任务已确认网关列出 gpt-reserve，
但模型列表本身不证明具体账号的计费路由或模型权重修订。

DETERMINISTIC、RECORDED、LIVE 分开记录。BGE-M3/FAISS/reranker、完整两轮复用、
无基线新建、模型补丁和音视频/OCR 的实际完成范围见 [五步能力与边界](docs/upgrade/modeling-five-stage.md)。
未完成正式标注/专家测试时，研究指标为 INSUFFICIENT_EVIDENCE，不能用工程全绿替代。

## 兼容和迁移

Provider 只生成候选；Recorded Provider 不是 Live LLM。EXPERIMENTAL 领域包只提供实验资产。
Ontology Package 的 VALIDATED_UNPUBLISHED 表示验证后未发布，CONTROL_PLANE_SELECTED
只表示本地控制面版本选择，不证明外部部署。Attestation 绑定受测输入与执行证据，
CAS 保护并发提交；两者都不能代替真实专家审核或研究指标验收。

唯一实现是 zhigou_toolchain；旧 kg_mnp 导入及 kg-mnp CLI 保留薄兼容入口。
ZHIGOU_ 与 KG_MNP_ 环境变量冲突会明确报错，不回显秘密。
稳定 IRI/URN、manifest_kind、旧包摘要、签名、.kgop 和合法 MNP 领域内容不因更名改写。
详见 [迁移报告](docs/upgrade/migration-report.md)和 [旧名保留清单](docs/upgrade/legacy-name-allowlist.md)。

当前远端仍为原仓库，未更名、未推送、未合并、未发布。
本地品牌/代码迁移与 GitHub 原地更名是两个独立状态，不把目标链接当作现存仓库。

以上 Git 状态描述属于前序迁移验证记录。2026-09-13 用户已另行授权将当前全部改动
集成到 develop、同步 main，并在确认提交均已保留后仅保留这两个分支。
该授权不改变功能缺口或研究结论；当前提交的 CI 状态以 GitHub Actions 检查为准。

## 双 Agent、v3 与独立本体 I/O 评测（增量实现）

已接入后端角色/工具审计、只读 v3 检查、原生包兼容预检、固定外部资源输入适配、
原生评分函数回归及研究报告页面。完整原生→v3 正式导出、全部 TwoAgentV3 研究内核、
强进程沙箱与真实外部对比尚未完成；工程通过不等于语义准确率达标。

可执行命令与明确限制见 [本体 I/O 运行说明](docs/upgrade/ontology-io.md)，
资料—方法—实现—测试记录见 [需求追踪](requirement_traceability.md)。
