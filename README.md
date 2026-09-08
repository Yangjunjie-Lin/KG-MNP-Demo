# KG-MNP Ontology Toolchain

可插拔、可验证、可追溯的通用本体工程工具链。它把资料转成 Evidence-bound KG-IR，经候选建模、明确人工审核和确定性语义编译，产出可验证的本体包，并管理本地版本发布与环境选择。

当前版本为 0.9.0rc1 预发布候选，发行资格以[固定修订验收摘要](docs/verification/final-verification.json)为准。历史测试通过记录只适用于其记录的修订，不能认证后续代码。

## 实际能力

- 项目隔离、精确版本的 Domain Pack、完整 Workspace / Project Lock。
- 实际字节受限的上传，Source / Batch、持久化解析任务、KG-IR、Evidence 定位和授权原文下载。
- Scope / CQ、基线、术语、声明式记录与字段映射、离线或 Recorded Provider 候选。
- 逐项人工审核、拒绝、修订重验、审核头冲突检测、确认包；客户端不能声明审核身份或角色。
- 固定 ROBOT / HermiT、OWL、SHACL、明确 Query / Oracle、Provenance、确定性 Package 与 .kgop。
- 本地 Registry、语义 Diff、Impact、实际回归、消费者契约、初始和后续 Release、审核后的 CAS 环境选择及指定历史回滚。
- 一个中文 React 工作台、同一 ApplicationService、资源 API、Python SDK 和服务 CLI。
- HttpOnly 短期会话、CSRF / Origin、权限撤销、项目隔离、幂等、核心提交 fencing 和显式任务恢复。
- 固定 Package / Release 的元数据、隔离只读对象查询、分页、Typed Literal 和来源追溯。

Provider 只生成候选；服务账户不能批准。发布默认采用多角色策略，至少两位独立审核人。显式单人开发策略仅限 loopback，不代表生产审核完成。

## 主流程与状态

资料 → Source / KG-IR / Evidence → Scope / CQ / Baseline → Proposal → 人工 Review → Confirmed Package → 编译与验证 → Ontology Package → Registry → Release。

后续版本执行 Diff / Impact / Regression；环境选择与回滚有独立提案、审核和 CAS。
Release Attestation 绑定实际文件摘要，不接受客户端提供的伪造成功状态。

| 对象 | 状态含义 |
| --- | --- |
| Package：VALIDATED_UNPUBLISHED | 包内必需验证通过，但不等于发布 |
| Registry：IMPORTED_VERIFIED | 本地登记并校验 |
| Release：RELEASED | 当前发布候选经过人工审核 |
| Environment：CONTROL_PLANE_SELECTED | 本地控制面选定版本 |
| External Deployment | 必须单独观测，不能由 Pointer 或 Outbox 推断 |

## 领域包

- Minimal 0.1.0：小型真实流程和否定案例。
- MNP 1.0.0：独立领域包，保持原 84 个资产和约束；验证使用非空、有证据的合成 MappingRecord。
- Forestry 0.2.0 EXPERIMENTAL：树木档案与巡查示例，6 条 TreeRecord、6 条 InspectionRecord、2 个 Site，全部为合成数据。
- 任意名称的临时第四包用于检查前端不依赖固定 Pack ID。

旧 Forestry 0.1.0 不会被静默替换为 0.2.0；请求不可用的精确版本会失败。领域包是数据、约束和映射，不允许通过包执行 Python / Shell。

## 安装要求

Python 3.11+、构建前端用的 Node.js，以及语义编译所需的 Java 与固定 ROBOT 1.9.7。当前实测环境为 Python 3.12、Node 24、Chromium 153。安装 Wheel 后运行工作台不需要 Node。

依赖和 JAR 只在显式准备阶段安装，核心运行不会自动联网下载。ROBOT 的准确摘要见 `kg_mnp.semantic_kernel.snapshot.ROBOT_SHA256`。

从源码准备（先激活自行创建的虚拟环境）：

```text
python -m pip install -c requirements-dev.lock -e ".[dev]"
npm ci --prefix workbench
npm --prefix workbench run build
```

PowerShell 可使用 `python -m venv .venv`、`.\.venv\Scripts\Activate.ps1`；POSIX 使用 `python -m venv .venv`、`source .venv/bin/activate`。不依赖宿主机偶然安装的测试库。

## 本地启动

Web 与 Worker 使用同一配置和运行目录。在两个终端分别设置相同环境变量。以下 PowerShell 示例只用于合成开发，不连接生产服务：

```powershell
$env:KG_MNP_DOMAIN_PACKS_ROOT = (Resolve-Path domain_packs).Path
$env:KG_MNP_WORKBENCH_ROOT = (Resolve-Path workbench/dist).Path
$env:KG_MNP_REASONER_JAR = (Resolve-Path third_party/downloads/robot-1.9.7.jar).Path
$env:KG_MNP_ALLOW_INSECURE_LOOPBACK_SESSION = 'true'
$env:KG_MNP_REVIEW_PROFILE = 'DEVELOPMENT_SINGLE_REVIEWER'
kg-mnp service token create --workspace runtime/local --principal-id local-human --created-by local-admin --permissions '*'
kg-mnp service serve --workspace runtime/local
```

另一终端执行：

```text
kg-mnp service worker --workspace runtime/local
```

浏览器入口：[本地工作台](http://127.0.0.1:8765/)。没有默认账户、匿名管理员注册或“选择角色即认证”。凭证只在本地签发时显示；不要记录到日志、URL、截图、Git 或浏览器存储。非 loopback 服务需要 TLS 和 Origin 配置；生产会话使用 Secure Cookie。

POSIX 对应环境设置：

```sh
export KG_MNP_DOMAIN_PACKS_ROOT="$PWD/domain_packs"
export KG_MNP_WORKBENCH_ROOT="$PWD/workbench/dist"
export KG_MNP_REASONER_JAR="$PWD/third_party/downloads/robot-1.9.7.jar"
export KG_MNP_ALLOW_INSECURE_LOOPBACK_SESSION=true
export KG_MNP_REVIEW_PROFILE=DEVELOPMENT_SINGLE_REVIEWER
kg-mnp service serve --workspace runtime/local
```

仅用 Ctrl+C 停止自己启动的服务；端口冲突不意味着可以终止未知进程。

## CLI 与 SDK

服务 CLI 从 `KG_MNP_TOKEN` 环境变量读取凭证，不把凭证放进命令参数或 URL。

```text
kg-mnp service upload --url http://127.0.0.1:8765 --project-id <PROJECT_ID> --file sample.csv --media-type text/csv --idempotency-key upload-1
kg-mnp service call --url http://127.0.0.1:8765 --project-id <PROJECT_ID> --operation ingestion.plan --request plan-request.json --idempotency-key plan-1
```

`plan-request.json` 为 `{"batch_id":"<SOURCE_BATCH_ID>"}`。202 只表示已接收；通过 `job.get` 读取真实任务结果。网页关闭不等于取消；取消请求不等于结果已撤销。

```python
import os
from kg_mnp.sdk.http import HTTPClient
from kg_mnp.services.models import OperationRequest

client = HTTPClient("http://127.0.0.1:8765", os.environ["KG_MNP_TOKEN"])
try:
    result = client.execute(OperationRequest("project.list"))
    print(result.payload)
finally:
    client.close()
```

恢复先核验正式提交回执。只有未提交、租约已过期的本地任务可以显式重试；活动租约、取消意图、失效原凭证和未知外部副作用不会被绕过：

```text
kg-mnp service recover --url http://127.0.0.1:8765 --job-id <JOB_ID> --expected-attempt 1
kg-mnp service recover --url http://127.0.0.1:8765 --job-id <JOB_ID> --expected-attempt 1 --retry-local
```

## 质量与验收

```text
python -m ruff check .
python tools/check_types.py
python -m pytest
npm --prefix workbench run lint
npm --prefix workbench run typecheck
npm --prefix workbench test
npm --prefix workbench run build
```

静态类型门覆盖服务、API、SDK、任务和集成应用边界；语义工件另由版本化 JSON Schema 和行为测试验证。真实浏览器测试使用显式合成服务与凭证，不 Mock 核心 API。容量测试复用同一套正式组件，其结果不冒充业务流程或生产性能。

最终验收必须先固定干净的代码修订，再导出完整唯一 collection，执行所有分区、浏览器、Linux、兼容、安装和打包检查。以验证摘要和退役台账中的 tested_commit 判断证据适用范围，不以版本号推断验收状态。

## 限制与研究边界

当前是预发布候选。旧可写平台和独立网页运行入口已退役，历史解析与必要转换工具保留；发行资格仍须由完整同修订验收记录确认，不由版本号或已配置的门禁推断。

Recorded Provider 不是 Live LLM；Image / WAV 默认只有元数据，不提供虚构 OCR / ASR。GraphDB live 和外部业务执行器未配置时明确阻断，不模拟部署或执行成功。本地包和环境 Pointer 可独立使用。

当前本地提交使用复制工作区和原子权威切换，校验成本随项目增大；不承诺分布式高可用或外部 exactly-once。合成流程中有些完整校验和下载需数十秒，界面等待与真实后台状态分开处理。

Hash / Lock 证明完整性，不证明原始资料真实；OWL 一致不代表业务知识正确；SHACL 和 CQ 只覆盖实际执行的约束与 Oracle。合成 Forestry 不是实地试点。工程机制实现不自动证明学术新颖性或生产安全认证。

## License

项目使用 Apache-2.0。第三方依赖和工具的授权、来源与义务见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)；不将开源依赖描述为完全自主知识产权。
