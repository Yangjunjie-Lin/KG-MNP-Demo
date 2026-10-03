# 自动逐运行 Token JSON 审计

2026-09-24，develop@84522072 上新增独立审计程序。原工作树已有改动保持。
程序位于 `runtime_reports/full-luna-20260921/token-audit-20260924v1/audit_tokens.py`，
详细接口与字段见同目录 README。它是当前 benchmark 工作区的只读附属观察器，
不改变 r8luna 生成指纹 `23cb49bf415fff4999597aec27cbec4dc40c1a39eee03455c8a63d6d7646ae75`，
不改冻结控制 v4，不创建新 run/session/审核/预算数据库，也不调用模型。

## 一次输出与自动输出

```powershell
python runtime_reports/full-luna-20260921/token-audit-20260924v1/audit_tokens.py snapshot --workspace runtime_reports/full-ontology-experiment-20260914
python runtime_reports/full-luna-20260921/token-audit-20260924v1/audit_tokens.py snapshot --workspace runtime_reports/full-ontology-experiment-20260914 --revision r8luna --job-id 原job_id --output 新文件.json
python runtime_reports/full-luna-20260921/token-audit-20260924v1/audit_tokens.py watch --workspace runtime_reports/full-ontology-experiment-20260914 --output-dir runtime_reports/full-luna-20260921/token-audit-live --interval 30
```

snapshot stdout 是一个 JSON；watch stdout 是每行一个 JSON 的 JSONL。
watch 首次补齐历史，以后调用/运行发生变化后自动输出累计视图，轮询间隔30秒；
全局汇总在 `token-audit-live/latest.json`，每个 job 在 `token-audit-live/runs/`。
不能将同一个 job 的累计更新事件反复相加。可从原 job_id 的 UTF-8 SHA256 定位文件，内容保留原ID。
观察器重启会读原账本重建；不是开机服务，须单独恢复。停止观察器不停止原全量生成。
数据文件是原子更新的可重建投影，不是新的真相来源；独立输出锁不碰原 supervisor.lock。

## 两种用途与两个分类轴

- `modeling`：实际生成系统的本体设计/复用/抽取/修复/直接基线调用。
- `testing`：原账本已明确登记的预检、模型恢复与接口复测探测。
- `unclassified`：不能证明用途的新/未知调用。

`execution_context=benchmark` 说明建模调用发生在 smoke/pilot/full 测试中，并非生产服务；
`diagnostic` 说明独立诊断。用途与场景各自分区合计，两个维度绝不能相加。
未登记的LLM评分、其他项目、Codex对话和程序测试运行时间不会被臆算为 token。
这不是全站自动埋点；新的账本/运行入口需要另行适配，不根据目录名猜用途。

每一步和每个调用包含 input/output/total。未知为 null，`known_*_tokens` 是已知部分，
`unknown_*_calls` 说明缺失范围；预算 charge/reserved 独立命名，绝不替代实际 token。
`final_total_tokens` 只对已终态且用量完整的原 job 给数值；失败但有已知用量仍保留真实用量，
未知失败和主机中断仍使最终用量为 null。只登记零调用的步骤不表示实际执行或通过。

S2/S3 匹配实际请求与经过摘要验证的对应冻结源码；S4修复按实际回到S2/S3归类。
直接对照为DIRECT，不强贴五阶段。无匹配为UNKNOWN，不按调用轮次猜阶段。
输出不含prompt、输入正文、模型答案、密钥或供应商私有reasoning；原权限与受控审计不变。
caller记录不是独立物理HTTP见证，本地veto复现也不能追认历史用量为0。

## 验证证据

单测、旧提取器回归、原预算/恢复相关回归、真实账本快照及独立启用回执保存在
`runtime_reports/full-luna-20260921/token-audit-20260924v1/evidence/`。
首个预检发现 Windows 测试夹具文本换行导致摘要不符，失败保留；修复夹具按原字节取摘要，
没有放宽完整性规则。真实快照按源 SQL COUNT/SUM、调用去重与分类/运行分区逐项核对。
原生成继续运行；本附件不提供或暗示正式质量分数、提升幅度或置信区间已完成。
审计器版本冻结及启动信息保存在本目录 `freeze.json` 与 `evidence/activation.json`。

额外执行未修改的冻结 v4 中断测试时，两轮扩展97项回归分别为96通过/1失败、95通过/2失败。
失败都在夹具 setup 后的严格时间门：模拟请求 started_at 与模拟 boot_utc 相等；
第一轮保留的 SQLite 与日志均为 `2026-09-24T11:21:28.989868+00:00`。
这是旧时间夹具的不稳定性，不能标为扩展回归全绿；没有改冻结测试、跳过失败或放宽安全门。
独立审计器/旧提取器/原预算和传输用例另有专项回执；该附件的生效不声称修复了旧冻结测试。

## 本次实际启用

审计与账本专项72项通过、0失败/0跳过；代码在11:25 UTC独立冻结。
观察器 PID30792 于2026-09-24 12:25:35 Europe/London启动；原生成 PID18516 未重启。
`evidence/observer-live-verification.json` 记录4次真实轮询，登记调用从5775增至5784，
初始补齐后新增7条运行更新，包含真实终态作业；第二观察器被独立锁实际拒绝。
截至11:28:32 UTC，全部历史已知11,501,710 tokens，其中建模用途11,493,027、诊断测试8,683；
20次用量未知（含1次在途），所以总量仍为null，不冒充全量最终值。
这些数字是有时间戳的验证快照；后续以 `token-audit-live/latest.json` 为准。

单次实际运行示例：`outputs/01a0c3f7-597f-7be2-97df-cd64d43ff5ab/token-audit-20260924/run-token-usage.json`。
原job `e5939e9a7b5aa214e1ce719d` 的S2为1,709、S3为2,113，总计3,822；
与原账本按相同job重新查询得到的请求集合和SUM(usage)一致。
未新增付费调用、未提交/推送/发布；旧阶段报告、失败、预算与冻结文件保持原样。
