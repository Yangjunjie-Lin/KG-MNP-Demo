# 每次运行的只读 Token 审计程序

本文件对应新的 portable-v1 分发版本；入口/格式/异常类型与依赖摘要按仓库规范整理。
原本地审计器和历史失败不改动，原冻结说明保存在 source-origin.json；本版有独立 freeze.json。

此程序适配当前本体 benchmark 的 `budget.sqlite / jobs.sqlite`，不是所有项目或生产服务的通用埋点。
它复用原始 job/request ID 和 2026-09-23 报告的已锁定提取函数；不新建用量账本、不调用模型、
不读凭据、不评分，也不修改正在运行的 r8luna 或冻结控制 v4。Python 3.12+，仅标准库。
本目录和依赖 `../token-report-portable-v1/export_usage.py` 必须一起保留；启动时核对依赖 SHA。

## 使用

从仓库根目录运行（控制台 stdout 只含 JSON，UTF-8 文件中的字符串使用 ASCII JSON 转义）：

```powershell
python tools/audit_ontology_tokens.py snapshot --workspace runtime_reports/full-ontology-experiment-20260914
```

默认统计同一本原账本的全部历史，含旧 revision、失败、重试、诊断与中断。
可加 `--revision r8luna` 只看该修订，或 `--job-id 原job_id` 看一次运行。
加 `--output 新文件.json` 同时保存；已有文件一律拒绝覆盖。不要将输出放进原账本工作区。
未知 job 报 JSON 错误并非“成功、零用量”；指定 revision 的空范围会明确输出 0 个已登记调用。

自动跟随当前及后续运行（每次轮询后休息 30 秒，不重启生成器）：

```powershell
python tools/audit_ontology_tokens.py watch --workspace runtime_reports/full-ontology-experiment-20260914 --output-dir runtime_reports/full-luna-20260921/token-audit-live --interval 30
```

watch 控制台输出 **JSON Lines**：每行是独立 JSON。首次补齐已有运行；之后仅输出有变化的运行，
包括刚登记的调用、供应商用量到达、失败、重试和作业终态。每次更新是该 job 的**累计**视图，
不能把同一 job 的多次事件加总。没有变化的轮询只输出全局汇总。

- `latest.json`：整体、步骤、建模/测试用量及账本核对结果，不包含庞大的全部运行列表。
- `runs/<sha256(job_id)>.json`：每个原 job 的最新视图，含每次调用、每步和总量。文件名摘要只用于安全路径，
  原始 ID 在内容中保留，绝非新 native/audit/transport ID。
- `observer-status.json / observer-scope.json / observer.lock`：独立观察器的生命周期、范围和互斥锁，
  不是生成器状态、session、Worker、审批或预算真相。进程状态仍须核对实际 PID 和启动时间。

重复启动同一输出目录被拒绝。重启观察器会从原账本重建，已有逐运行 JSON 用于避免重复输出，
不用于决定任务状态或 token 真值。视图损坏时应换新输出目录重建，不覆盖/修改源账本。
Ctrl+C 只停止观察器，不停止全量测试。此脚本没有安装开机服务；主机重启后需要重新启动观察器。

## 字段与归类

`schema_version` 为 `ontology-token-usage/1.0`。
snapshot 包含 `totals / by_usage_category / by_execution_context / steps / runs`；
每个 run 含 `job_id / run / terminal_at_snapshot / final_total_tokens / totals / steps / calls`。
每个 call 含原 `request_id`、真实 attempt、调用顺序、step、用途、角色、输入/输出/总 token、
usage_status、失败/在途状态、请求/响应摘要和归类依据；不导出 prompt、正文、答案或供应商私有 reasoning。

| 字段 | 解释 |
|---|---|
| `usage_category=modeling` | 已登记生成系统执行的本体生成、复用选择、结构设计、事实抽取、修复和直接基线 |
| `usage_category=testing` | 原账本明确登记的 preflight、模型恢复、接口复测等诊断探测 |
| `usage_category=unclassified` | 不支持/不能证明用途；不强行归类为测试或建模 |
| `execution_context=benchmark` | 调用发生在 benchmark 作业中，包括 smoke/pilot/full；不冒称生产运行 |
| `execution_context=diagnostic` | 已识别的独立诊断组；该 job 分组不是原生一次服务 run |
| `input_tokens / output_tokens / total_tokens` | 所选范围已登记调用的精确合计；任一对应分项未知即为 null |
| `known_*_tokens / unknown_*_calls` | 已知部分之和与未知调用数；已知和不是全流程最终用量 |
| `final_total_tokens` | 仅作业在一致账本快照中已经终态且全部总用量已知时给数值；运行中为 null |
| `budget_charge_tokens_not_usage` | 原预算占用，包括保守预留；绝不可当成真实用量 |

两个分类轴不能相加：测试场景中的生成调用仍是建模用途。模型测试/LLM judge 如未来采用新的账本类型，
必须显式增加适配和证据；当前不会从名称或费用猜测，也不计算 Codex 对话本身、其他项目或未登记的费用。
CPU 单测、OWL 推理器和此审计器自身没有 LLM token；未登记不等于证明整个系统从未发生其他调用。

S2/S3 从实际请求结构与该 revision 已验 SHA 的冻结源码匹配，不用 call-1/call-2 猜阶段。
S4 触发的修复仍按实际 S2/S3 调用归属；直接基线标 `DIRECT`，未知标 `UNKNOWN`。
S1—S5 都有槽位；无已登记调用时是 `NO_REGISTERED_CALLS` 和该集合的 0，
`execution_status=NOT_INFERRED_FROM_TOKEN_AUDIT`，不能解释为该步骤已执行、已通过或物理请求数已证明为零。
无模型调用的终态 job 亦保留。`INTERRUPTED_UNKNOWN` 保留 null 和预算占用，不造响应或退费。

## 一致性与限制

SQLite 使用 mode=ro 和 query_only，两个库在同一个短只读事务中取元数据；随后释放锁再读取工件。
每个 request_id 只计一次；分类/运行合计与原 SQL COUNT/SUM 核对。响应 SHA 不匹配则不采用分项。
读取竞争仅生成安全重试事件，不输出假的空快照、不暂停生成器。调用数是 caller 尝试数，
不是由独立 HTTP spy 证明的实际发送次数。本地 veto 的离线复现不能回填历史 usage=0。
watch 为规模化运行缓存已验证、完整的不可变调用；原账本元数据变化时重算。
它不是持续文件篡改监视器；要重新验证所有响应摘要，应使用新的 snapshot 进程。

测试入口：

```powershell
python -m unittest discover -s tools/ontology_usage_audit/token-audit-portable-v1 -p test_audit_tokens.py -v
python -m unittest discover -s tools/ontology_usage_audit/token-report-portable-v1 -p test_export_usage.py -v
```

测试只使用隔离合成 SQLite 和请求/响应夹具，不能当成真实质量评测或真实 HTTP 完整性证明。
原本地版本第一次预检的 Windows 换行夹具错误及修复回执保留在原运行目录，不随程序上传。
本分发版本使用独立工程回归记录，不借用旧 PASS；真实数据与观察器输出仍是本地运行产物。
