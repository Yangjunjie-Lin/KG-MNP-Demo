# 主机重启后的有授权续跑（2026-09-24）

用户在“保留重启中断/结果未知、不重试、不退款、继续其余队列”的明确问题后回复“继续完成”。
新冻结控制v4只绑定job39568dfb965570f4e92b338d的attempt-01:call-3，不覆盖未来其他在途不确定请求。
生成revision仍r8luna，源码/Prompt/输入/模型参数、三次尝试上限与总预算不变。

恢复前重新核对当前主机启动时间、其他进程、请求文件与清单摘要、原账本/job/尝试四类
CAS前像。原budget.sqlite及jobs.sqlite均为DELETE journal，使用同一附加数据库事务
保存完整前像和本次授权收据，再做本地生命周期迁移：caller由RESERVED变为
INTERRUPTED_UNKNOWN，job与执行尝试标本地失败。它不宣称供应商请求失败或成功。
usage、result_hash、实际远端结束时间保持null，136620 tokens原预留与charge不变；
没有生成response.json，没有transport重试ack，也不重发该作业。

收据保存在原账本operator_host_reboot_interruptions，从属于原job/attempt，不能成为
另一套本体业务真相。重复相同操作只核对既有收据；其他RESERVED、晚到响应、并发进程、
预算/前像/文件漂移仍拒绝。两个计算角色、审核、CAS与原native/audit/transport身份不变。

最终导出核账适配仅对经过冻结授权、原请求及账本前后像核验的中断，允许明确记录
“供应商响应缺失”，附独立本地观察摘要。没有用观察记录冒充response或补造token。
原生成、原生评分、失败分母、配对CI和质量表代码不变；AST核对确保只有该核账分支有差异。
未知项及失败仍进入完整分母，不能据此宣布正式质量评分已完成。

25项新增中断/导出测试+89项原控制和相关回归：114 passed、0 failed、0 skipped。
真实只读前置核验前后5648次caller请求，费用不变。重启后首次WSL canary超时回执保留，
随后基础Linux命令可用，在新目录按原校验重跑通过；凭据为空、代码只读、网络隔离及
已记录Python/依赖版本一致，未更改安全门或超时定义，没有模型调用。

冻结控制：runtime_reports/full-luna-20260921/resume-control-20260924v4/。
2026-09-24 11:43 Europe/London启动PID18516；首次新full作业0ac8d9b747d27445c83984fb已实际GENERATED。
原中断作业保持FAILED/一次执行尝试，原调用仍未知且预留保留。真实状态以后续原账本/进程为准。
明细回执见同运行根REBOOT_RESUME_20260924.md、v4/sessions/、v4-validation-final.xml、
v4-live-preflight.json及v4-isolation-02/receipt.json。

没有提交、推送、发布、扩预算或下载未确认许可的模型。Gemma许可、完整CQ2Onto评分
适配与正式全量统计仍按原未完成项处理，最终token报告会如实保留该未知用量。
