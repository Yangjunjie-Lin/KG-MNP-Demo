# 全量启动：有限传输恢复、完整分母与持续检查

用户明确授权“完整启动运行，并完成所有的全量”。延续已确认的本机Luna/low与本地用量监控协议，
总325311 calls / 10659790848 tokens上限不变，不改变账号/提供商、不输出密钥或升级为生产发布。
基线develop@84522072；继承此前未提交工作，不复用旧源码PASS。

## 先保留已发生的失败

r2luna smoke 9/9成功；pilot此前4任务成功，第5个TwoAgentKernelV1任务的第二次调用ReadTimeout，
120秒无完整公开响应/usage。原任务失败、未知用量及135840预留保持不变，不能填0或退款。
完整账目快照在runtime_reports/monitored-luna-20260921/after-pilot-timeout/，13个生成产物重读通过。
后续使用新policy和新revision，不修改r1/r2源码、请求、响应或原结果。

## 新实现

- HTTP请求超时300秒；父传输进程330秒；每job按照冻结调用预算计算壁钟上限，最大3600秒。
- 显式授权的同一job最多3次实际尝试。只对ReadTimeout/连接类临时错误及HTTP500/502/503/504
  等预先白名单的传输故障恢复。认证、额度、JSON/Schema、低分和语义校验不触发网络重试。
- 每次使用新的`job:attempt-XX:call-N`请求ID，输出目录隔离。execution_attempts保存尝试开始/结束、
  真实失败和结果绑定；不是新增计算Agent或生产状态库。
- 原budget.sqlite追加transport_recovery_ack；只能承接与原账目响应SHA匹配的FAILED传输，
  不承接USAGE_BOUND_VIOLATION，第三次后停止。旧失败和未知预留一字不改、不退款。
- 原RUN_STOP、新revision STOP、变更后的旧STOP、预算及5GiB剩余磁盘门继续停止派发。
- `tools/continue_ontology_full.py`实际串行执行smoke→pilot→full→独立评分；不创建新预算、
  不搜索新密钥、不自动切换模型、不删除历史目录。预检有失败不会启动full。
- `--include-unscorable-generation`仅在新freeze时显式授权全部生成任务。它不修改任何scorer门；
  CQ2Onto尚缺完整原生评分这一事实仍单独记录。生成完成不能当作质量报告完整。
- 最终评分前核对冻结public input全集及sample×system×replicate笛卡尔清单，拒绝少行、重复和输入漂移。
  每次调用（含失败重试）重读原公开响应摘要；导出费用/调用数包含所有尝试，不只最后成功。

## 计划范围及实际前置检查

full输入保持Flagship3471、Reuse2252、CQ2Term6、CQ2Onto6，三次重复及既定对照/消融。
全量99501适用job、20934 N/A位置保留；N/A来自父组件不适用，不是隐藏失败或完成样本。
公开输入最大JSON字符分别8475、8059、5176、6608，均不超过现有24000输入门，没有缩短或抽样替代。
当前D盘约195GB可用，运行时继续检查磁盘，不删除历史资料换取空间。

这是一项长期运行，不能用最初几项成功推断总体效果。相同模型、输入、协议与资源锁跨系统保持，
gold仅独立评分侧读取；正式测试结果不可用于调优生成。新代码/配置需要新冻结版本。

已为本任务设置每小时后续检查：先确认活动revision和真实进程，不启动重复调度；
正常推进时不反复通知，完成/重要失败/需要用户行动时才通知。机器、Codex和本机网关需要保持运行。
自动检查不是已经完成所有作业的证明；实际结果以原jobs/budget账本及新runtime回执为准。

## 仍须单独完成的评分边界

LLMs4OL固定原生exact/fuzzy、CQ2Term hard已有评分入口。CQ2Onto完整对齐/公理/层级/CQCoverage
适配及权重/依赖锁仍需补齐；不能把exact-only自行更名成完整官方评分。
OSKGC许可问题不得绕过，也不把它的未授权数据加入此次生成范围。
最终质量分、提升与95%CI只从完整冻结预测导出，允许负提升或不显著。
评分不可用或预测失败时保持原null/失败分母，不为了数值结果放宽旧门。

测试、同源码验证及实际启动记录写runtime_reports/full-luna-20260921/。
本说明不预填全量通过或虚构正式分数。官方超时/有限退避建议参考
[OpenAI错误处理](https://developers.openai.com/api/docs/guides/error-codes)，
持续本地任务条件参考[Scheduled tasks](https://developers.openai.com/codex/app/automations)。
