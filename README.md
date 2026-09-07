# KG-MNP Ontology Toolchain

Evidence-bound, review-governed and deterministic ontology engineering.

KG-MNP 将资料转为带证据的 KG-IR，经过候选、人工审核、确定性编译和本地发布。
**当前状态：NO_GO_OPEN_CORE_REQUIREMENTS，不是已验收发行候选。**
KG-MNP Ontology Workbench / KG-MNP 本体工程工作台已有中文界面和 Minimal 初始发布流程；
跨领域、后续版本治理和完整仓库退役仍未完成。

## What is implemented now

- 项目隔离、精确领域包版本、正式 Workspace 和 ProjectLock。
- 流式实际字节限制、SourceAsset/SourceBatch、解析 Worker、KG-IR/Evidence、来源定位和授权下载。
- 复用既有 Scope/CQ、基线、术语、映射、Provider、Proposal、逐项 Review 和 Confirmed Package 核心。
- 固定 ROBOT/HermiT、OWL、SHACL、明确 SELECT CQ Oracle、Provenance 和真实 Package 验证。
- 本地 Registry 导入、初始 Release 人工审核、CAS 发布、文件摘要 Attestation 和非空对象查询。
- 统一服务、HTTP/Local SDK、CLI、持久化 Job 和 React 工作台。
- 短期不透明 HttpOnly 会话、CSRF、同源校验、撤销和退出。
- 隔离计算 Workspace、原子项目映射与提交回执、权限重验、fencing、修订 CAS 和提交回执恢复。

精确范围见[收敛台账](docs/verification/final-requirements.json)和
[交付说明](docs/release/release-candidate-notes.md)。接入数量不是行为正确性证明。

## What is not implemented yet

以下仍属于本次必需交付，没有移出范围：

- 完整服务化 Diff/Impact/Regression/Change Evaluation、后续 Release 和指定历史环境回滚。
- 工作台完整候选修改/冲突处理、映射编辑、证据联动、版本治理和集成管理。
- Forestry Domain Pack 0.2.0、MNP/Forestry/第四领域的分级工作流。
  Forestry remains a planning scaffold only，仍为 0.1.0 PLANNED。
- 旧三套 UI、重复控制面、旧脚本及完整测试/CI 收敛。
- 完整同修订发行验收、Linux 实测、完整可访问性和性能检查。

没有在线 LLM/OCR/ASR/Vision 实现，不自动执行外部业务。
Image and WAV support is metadata-only. No Agent or LLM is an ontology authority.
GraphDB live 的许可/环境不是本地未完成功能的解释。

## 主流程和状态边界

资料 → Source → KG-IR/Evidence → Scope/CQ/Baseline → 候选 → 人工审核 →
Confirmed Package → 编译/验证 → Ontology Package → Registry → 初始 Release。

VALIDATED_UNPUBLISHED、IMPORTED_VERIFIED、RELEASED、CONTROL_PLANE_SELECTED
和外部部署是不同状态。当前界面不能将本地发布称为环境激活或外部部署。

## 准备与安装

Python 3.11+；构建工作台需要 Node 22.12+；语义编译需要 Java 11+ 和固定 ROBOT 1.9.7。
依赖、浏览器、JAR 只在显式准备阶段安装，核心运行不自动下载。
ROBOT 的准确摘要保存在 kg_mnp.semantic_kernel.snapshot.ROBOT_SHA256。

    cd workbench
    npm ci
    npm run build
    cd ..
    python -m venv .venv

激活虚拟环境后执行：

    python -m pip install -e ".[dev]"

PowerShell 使用 .\.venv\Scripts\Activate.ps1；POSIX 使用 source .venv/bin/activate。
Wheel 包含构建后的工作台，安装 Wheel 不要求 Node。

## 本地启动

Web/Worker 必须使用相同配置、同一工作目录。PowerShell 开发示例：

    $env:KG_MNP_DOMAIN_PACKS_ROOT = (Resolve-Path domain_packs).Path
    $env:KG_MNP_WORKBENCH_ROOT = (Resolve-Path workbench/dist).Path
    $env:KG_MNP_REASONER_JAR = (Resolve-Path third_party/downloads/robot-1.9.7.jar).Path
    $env:KG_MNP_ALLOW_INSECURE_LOOPBACK_SESSION = 'true'
    kg-mnp service token create --workspace runtime/local --principal-id local-human --created-by local-admin --permissions '*'
    kg-mnp service serve --workspace runtime/local

在第二个同配置终端执行：

    kg-mnp service worker --workspace runtime/local

浏览器入口：[本地工作台](http://127.0.0.1:8765/)。
凭证只在签发时显示，粘贴后被登录框清空；不得放入 URL、截图、仓库或浏览器存储。
生产浏览器会话需要 HTTPS。默认没有管理员账户。

POSIX 对应示例：

    export KG_MNP_DOMAIN_PACKS_ROOT="$PWD/domain_packs"
    export KG_MNP_WORKBENCH_ROOT="$PWD/workbench/dist"
    export KG_MNP_REASONER_JAR="$PWD/third_party/downloads/robot-1.9.7.jar"
    export KG_MNP_ALLOW_INSECURE_LOOPBACK_SESSION=true
    kg-mnp service serve --workspace runtime/local

默认审核策略为多角色生产策略，具体角色权限使用 review:role:Ontology Engineer 等名称。
合成开发示例可以由管理员显式配置 KG_MNP_REVIEW_PROFILE=DEVELOPMENT_SINGLE_REVIEWER；
该策略不支持非 loopback 服务。端口冲突报错，不杀死未知进程。
用 Ctrl+C 停止自己启动的 Web/Worker。

## CLI / SDK

HTTP 凭证通过 KG_MNP_TOKEN 提供，不放入命令行参数或 URL。

    kg-mnp service upload --url http://127.0.0.1:8765 --project-id <PROJECT_ID> --file sample.csv --media-type text/csv --idempotency-key upload-1
    kg-mnp service call --url http://127.0.0.1:8765 --project-id <PROJECT_ID> --operation ingestion.plan --request plan-request.json --idempotency-key plan-1

plan-request.json 内容为 {"batch_id":"<SOURCE_BATCH_ID>"}。
HTTP 202 仅表示任务接受，使用 job.get 读取真实结果。

    import os
    from kg_mnp.sdk.http import HTTPClient
    from kg_mnp.services.models import OperationRequest

    client = HTTPClient("http://127.0.0.1:8765", os.environ["KG_MNP_TOKEN"])
    try:
        print(client.execute(OperationRequest("project.list")).payload)
    finally:
        client.close()

Local SDK 同样调用 ApplicationService，不通过 Shell/CLI stdout 调度核心。
服务管理的 Workspace 只经服务写入，不要对内部 generation 目录并行运行旧写命令。

## 验证与构建

    python -m ruff check .
    python -m pytest
    python scripts/check_repo_hygiene.py
    python scripts/generate_mnp_prompt01_content_golden.py --check
    python tools/build_distribution.py

浏览器测试：用 tools/run_workbench_test_server.py 启动隔离合成环境，
在 workbench/ 设置 KG_MNP_BROWSER_URL、KG_MNP_BROWSER_CREDENTIAL
（服务器输出的合成凭证文件路径），然后执行 npm run test:e2e。
先显式执行 npx playwright install chromium。核心接口不 Mock，Trace/录像默认关闭。

验收原始记录在忽略的 runtime_logs/p09/；构建在 runtime/p09-distribution/。
完整测试/CI 能力化迁移仍未完成；命令存在不表示执行通过。

## 领域包与文档

| 领域包 | 状态 | 本次证明范围 |
| --- | --- | --- |
| minimal 0.1.0 | EXPERIMENTAL | 非空服务流程和初始发布浏览器场景 |
| mnp 1.0.0 | MIGRATED_BASELINE | 资产保持；完整应用工作流未完成 |
| forestry 0.1.0 | PLANNED | 原规划元数据；0.2.0 未完成 |

[提交与恢复边界](docs/architecture/service-commit-boundary.md) ·
[收敛台账](docs/verification/final-requirements.json) ·
[迁移记录](docs/migration/final-retirement-ledger.json) ·
[交付说明](docs/release/release-candidate-notes.md) ·
[领域包规范](docs/domain-packs/domain-pack-contract-v1.md) ·
[公开契约](docs/contracts/public-contract-policy.md)

## License

Apache-2.0，见 [LICENSE](LICENSE) 和 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
工程机制实现不等于学术新颖性、来源真实性、行业普适性或生产安全认证已经证明。
