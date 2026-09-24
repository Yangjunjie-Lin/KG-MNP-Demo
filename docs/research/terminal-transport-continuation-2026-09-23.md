# 终态传输失败后的授权续跑（2026-09-23）

用户在原三次HTTP502/503/503暂停通知之后明确要求继续全量、不再暂停。
原r8luna生成器、模型/low参数、输入、Prompt、评分定义、作业ID和总预算保持。
新建的是独立冻结的操作者续跑控制版本，不重建研究作业或重跑成功/失败样本。

原失败作业仍为FAILED、仍恰好三次尝试，三次未知用量的401838 tokens预留不退款。
原自动重试函数仍拒绝对第三次失败授予自动重试。新授权由原budget.sqlite中的
operator_continuation_grants及operator_terminal_transport_continuations追加记录；
对原readiness查询的兼容记录必须与该操作者收据在同一事务中写入，明确不是第四次重试。
原jobs/execution_attempts、调用、用量、失败、政策原件不被改写。

作用域只限full中已耗尽三次且有真实响应SHA绑定的临时传输失败；后续继续其他PENDING作业。
重复故障自动60/300/900秒退避；401/403/429、Schema/语义错误、在途不确定、新超额、
证据变更、用户STOP和磁盘/预算门仍受保护。两个计算角色、人工审核、原生/CAS真相不变。

新控制目录：runtime_reports/full-luna-20260921/resume-control-20260923v2/。
v1真实启动被manifest文件SHA与canonical摘要口径不一致拦下，零新调用、零账本解锁；
原源码/freeze/测试/失败记录保持，v2分别锁定两种摘要并通过真实只读前置验证。
v2验证：28项新控制测试+54项原相关回归，82 passed、0 failed、0 skipped；Ruff通过。
这不是新的质量benchmark分数，原350项工程回执也不用于冒充研究结果。

2026-09-23T10:27:47Z启动PID35968；首个新full作业7d75c627e11a1033d1d1c524为
TwoAgentKernelV1，10:29:37Z实际GENERATED；两次新模型调用SUCCEEDED并返回usage。
原失败作业ad5f79eda32cbe5a5102b42a保持FAILED/三次尝试，监控ready=true。
当次检查full为1108 GENERATED、48 FAILED、1 RUNNING、98344 PENDING；
20934 N/A仍保留。只是恢复运行，不是全部完成。

完整质量分、提升幅度、95%CI与多重比较结论仍须等待完整预测与独立评分。
Gemma许可未确认，CQ2Onto完整原生适配尚未完成，既有null/完整分母规则不改变。
未提交、推送、发布或扩预算。主执行回执见同目录sessions/及外部RESUME_20260923.md。

OpenAI Docs参考：https://developers.openai.com/api/docs/guides/error-codes
官方退避建议用于本次控制设计；不把本机代理503直接归因于官方服务过载。
