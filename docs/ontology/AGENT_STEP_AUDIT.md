# 双 Agent 与逐步审计（2026-09-17）

在 develop@979128e 及现有本地交接改造上增量实现。旧冻结报告、原包和历史证据不变，
旧源码指纹不自动覆盖本次新增代码。

| 工作台封装 | 原生身份 | 步骤 |
|---|---|---|
| 规划 Agent | RuleAgent；PlanningAgent 是同一类的别名 | S1 输入检查、画像与范围；S2 问题、基线、术语、对齐、映射计划与结构；S4 完整性、语义校验及修复分流 |
| 任务执行 Agent | TaskExecutionAgent | S3 映射、抽取、证据与事实规范化；S5 编译计划、编译、原生验证、导出及本体交接 |

保留原 operation registry、Worker、工具白名单、session、STALE、审核和 CAS。
卡片仅导航，不因点击就调用模型或审批；跨阶段任务仍绑定真实任务与原生 AgentRun。
输入冻结、人工范围/逐项审核和独立验收另记授权主体，不授予 Agent 代签权限。
计划仍是计划，记录不会把 MappingPlan 变为已执行。

## 前后记录

相关任务获授权进入执行后，在服务工作区保存：

```text
service-data/modeling-step-audits/<project-hash>/<job-hash>/<attempt>/
  000001-before.json
  000002-before.json
  000003-after.json
  ...
  summary.json
```

BEFORE 在调用前写入，AFTER 保存真实输出或错误类型/已知错误码。嵌套调用按 call_id 配对，
不靠相邻行猜关系。事件绑定 job、attempt、租约 fence、请求摘要、project、操作和身份；
工具事件另绑定 run、session/revision、依赖、阶段与版本。操作前后包含输入和产物引用。
后置计算快照在发布前观察，并与该任务提交回执核验，不借用后来一次运行的输出。

默认 METADATA_ONLY，原公开 AgentRun 仍只留低敏摘要。服务显式设置
`ZHIGOU_MODELING_AUDIT_CONTENT_ENABLED=true`，且执行身份有 trace:record/source:read，
才保存过滤后的输入输出正文。独立预期、负例计划、凭证和供应商私有推理字段遮蔽。
单条正文超过 4 MB 标记 OMITTED_SIZE_LIMIT；总大小/事件数有界，不静默声称完整。
此快照不是供应商思维链或完整模型传输日志；模型原消息仍使用既有可选 TraceRecorder。

失败、取消、被替换尝试与成功分别记录；旧租约身份回查 JobStore claim 事件。
硬中断可能只有 BEFORE，导出为 INTERRUPTED，不补写成功。
旧任务未录制内容为 ARTIFACT_NOT_AVAILABLE，不能从最终结果倒造。
鉴权前拒绝、请求格式非法和未领用即取消没有计算快照，保留原平台安全/任务记录。

## 接口与包

以下接口在 `/api/v1` 下：

- `GET /projects/{project_id}/modeling/audits`：任务索引及两类 Agent 定义。
- `GET /projects/{project_id}/modeling/audits/{job_id}/archive?attempt=N`：已落盘前后记录 ZIP。

索引需 project:read/job:read 及真实项目/任务范围；下载另需 trace:export、source:read、
source:export、package:read。每次重新鉴权，不能由客户端自报权限。
ZIP 含 `steps/*-before.json`、`steps/*-after.json`、journal.jsonl、manifest.json、README.md。
事件哈希用 KG-MNP Canonical JSON v1；清单用原字节 SHA-256，不包含 manifest 自身。
哈希链不是授权或签名，下载还核验 JobStore 请求、原生运行和真实提交结果。
审计不是业务真相来源，不允许生成/修复 Agent 通过审计出口读取验收材料。
格式为 `zhigou-modeling-step-audit/1.0.0`，不是外部演进 v2、原 v3 或发布认证。

## 验证与启动

```powershell
python -m pytest tests/upgrade/test_step_audit.py tests/upgrade/test_agent_roles.py tests/services/test_five_stage_service.py -q
python -m tools.verify_agent_workbench runtime_reports/new-agent-audit-example
python tools/run_browser_verification.py --selected-test agent-audit.e2e.ts --startup-timeout 90
python tools/start_zhigou_demo.py --port 8765 --record-step-content
```

样例输出目录必须不存在；使用 HR 合成数据、真实服务/Worker/共享编译，输出逐任务 ZIP、
modeling-agent-audits.zip、verification.json 和独立服务工作区。合成审核不是专家验收；
模型调用为零，不做真实业务或外部发布。浏览器验证独立创建项目，点击运行和下载，
比较同一任务 API/浏览器原字节。回执保存在 runtime_reports/agent-step-audit-20260917/。
未重跑整仓冻结认证，不覆盖原卫生 FAIL、研究和上线限制。
