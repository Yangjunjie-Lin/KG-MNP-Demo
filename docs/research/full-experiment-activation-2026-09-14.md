# 全量实验真实启动记录：已安全暂停，full尚未开始

用户授权：“你帮我直接启用全量实验吧，在过程中有问题则直接进行修复就行”。
本次按此前候选包封顶325311次调用、10659790848 token保守额度激活，
不自动扩额、不更换底座、不修改生产审批、许可证或外部应用配置。

**真实执行已发生，但在pilot发现当前网关不执行输出token上限后停止。
不能将当前状态描述成full正在后台运行或完整实验完成。**

## 已完成的实质工作

- SQLite全局预算账本：每次发出请求前原子预留，跨线程/重启保持限额；失败和未知结果不退款，
  同request_id不能重发。所有probe、smoke、pilot、full共享同一上限。
- 单个模型请求放入可终止进程，固定同一配置模型/端点/修订/推理参数，拒绝任意URL、工具调用和外部JSON Schema引用。
- 利用现有Ubuntu-24.04 WSL与bubblewrap，建立独立mount/PID/network/user namespace。
  只读挂载源码/合同、运行库、单个public input与固定JAR；只给本job输出目录写权限。
  生成进程无API凭证、不能直接联网，模型请求通过JSON-only broker。
- 实际canary验证：public input可读、自己的输出可写、代码不可写；host gold canary、用户目录、
  Windows系统目录与/proc父根路径均不可读；网络命名空间与宿主不同，外网与loopback访问拒绝。
- 同一generation engine实际执行，不建立替代生成器。真实产物、公开请求/回复、失败、编译图、
  各调用用量和SHA记录在各job目录。
- 创建99501个适用full运行单元、20934个N/A位置；核心比较先行，样本/重复内固定hash排列系统。
- 独立pilot从旧pilot分区选3个来源组/任务，和full来源组无交集；不使用gold选择样本。
- 新增独立冻结导出/评分入口，full仍有PENDING/RUNNING时拒绝评分；无成功子集伪分母。

WSL环境为本任务新建独立venv，并安装OpenJDK21运行依赖；未卸载旧软件或启动Docker服务。
worker依赖锁及实际运行版本随revision保存。未下载嵌入权重或许可未澄清的数据。

## 真实执行数量

| 阶段 | 执行情况 |
| --- | --- |
| 单独参数探测 | 1次真实模型调用，JSON响应通过；283 reported tokens |
| smoke | 3类表示×3系统，共9个job全部GENERATED；21次真实调用 |
| pilot | 第1个job执行2次调用，第2次触发输出/用量超限；job FAILED；其余17个未运行 |
| full | 99501个适用job全部PENDING；0个已执行 |

总计24次真实调用，23次返回被接受，1次USAGE_BOUND_VIOLATION。
网关报告累计85852 token。已知超额用量重新计入保守扣账后charged/reserved为305917，
原始预留数保存在`reserved_at_dispatch`，没有覆盖超限记录。
费用未知；没有统计质量分、F1提升或显著性结果。

## 自动暂停的直接证据

失败job：`d3128e801b62d56ff6d754fa`，来源是独立pilot而非full。

| 字段 | 第2次模型调用 |
| --- | ---: |
| 请求max_completion_tokens | 8192 |
| 网关返回completion_tokens | 27832 |
| 网关返回prompt_tokens | 1312 |
| 网关返回total_tokens | 29144 |

原始公开响应：
`runtime_reports/full-ontology-experiment-20260914/revisions/r1/runs/d3128e801b62d56ff6d754fa/calls/2/response.json`。

根据[官方Chat Completions参数定义](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)，
max_completion_tokens应约束可见输出与推理token合计。小型JSON探测成功只证明请求被接受，
不证明所有参数被网关执行；本次pilot恰好暴露了此前明确保留的这个不确定性。

## 网关核查与可修复边界

51900监听进程实际为`C:/Program Files/Cockpit Tools/cockpit-cliproxy.exe`，
本机二进制SHA-256：`424f786f3002010d19b77caff65f8f29e2d2e419128b16a9788cfc0033e78974`。

读取同项目公开源码固定commit `c4c05a8e1ba590237340919142aad3d82e0dc52d`：
[Codex请求转换器](https://github.com/jlcodes99/cockpit-tools/blob/c4c05a8e1ba590237340919142aad3d82e0dc52d/sidecars/cockpit-cliproxy/third_party/CLIProxyAPI/internal/translator/codex/openai/responses/codex_openai-responses_request.go)
明确移除max_output_tokens、max_completion_tokens等字段，并注明Codex Responses拒绝这些参数。
代码快照/文件摘要保存在`gateway-audit/`；没有执行下载代码。

不能独立证明该二进制正好由上述commit构建，因此证据表述为：公开同项目行为与本机实际超限一致。
网关models接口只返回id/object/created/owned_by，未给出可依赖的输出硬上限；
公开catalog中Spark的context_window也不能当作本机每次请求的已验证输出预算。

这不是通过本仓库改个字段名就能可靠解决的问题。改用另一种被删除的token字段、降低reasoning、
按字数提示、截断回复或关闭超额检查，都不能证明恢复了调用/计费硬上限。
未擅自修补Cockpit安装目录、登录账户、切换模型/提供商，或把全量协议改为无token约束。

## 已落实的停止与恢复约束

- `STOP`文件暂停调度；全局预算账本另有持久latch，发现任一USAGE_BOUND_VIOLATION后，
  所有未来reserve都会在发出模型请求前拒绝。
- 重新启动脚本、删除单个失败输出、换revision或重跑activation都不能解除该预算锁。
- r1冻结源码保留。后续预算保护代码修复没有写回r1快照，不把新旧版本结果混合。
- 继续前需要：一个确实支持请求级硬token上限的API路由，或用户明确接受并授权另一套可控预算协议。
  然后独立验证、新建revision、重做smoke/pilot，仍保留并扣记本轮已消耗的调用。
- OSKGC许可、完整CQ4OE对齐/公理评分等原有独立缺口没有因为本轮启动而被伪称解决。

## 文件与命令

运行根：`runtime_reports/full-ontology-experiment-20260914/`

- `authorization.json`、`budget.sqlite`：用户授权与全部真实调用。
- `jobs.sqlite`：smoke/pilot/full完整队列、状态和失败。
- `revisions/r1/manifest.json`、`code-lock.json`、`isolation.json`：冻结版本和实际OS拒绝测试。
- `revisions/r1/runs/`：所有已执行job的请求、响应、RDF及收据。
- `gateway-audit/audit.json`：网关问题证据。
- `state.json`：当前安全暂停状态；`STOP`：显式停机原因。
- `ledger-policy-tests.xml`、`ledger-latch-tests.xml`：预算/IPC/挂载策略测试。
- `final-engineering-verification/`：最终回归及源码前后校验。

只读查看当前状态，不触发推理：

```powershell
python tools/run_ontology_benchmark_matrix.py live status --workspace runtime_reports/full-ontology-experiment-20260914 --revision r1
```

本轮新增实际执行入口是 `tools/run_ontology_benchmark_matrix.py live ...`。
原有没有强隔离的legacy `ontology-io run`门仍保留，不通过修改布尔标志绕过隔离。
没有推送、合并、发布、提交榜单或执行真实业务。

最后校验：9个GENERATED结果均与账本冻结摘要相符；全局预算latch测试7项通过。
最终ruff/typecheck退出0，完整本体工程回归的退出码及source_unchanged=true见
`final-engineering-verification/verification.json`。
机器可读摘要：[full-experiment-activation-2026-09-14-evidence.json](full-experiment-activation-2026-09-14-evidence.json)。
