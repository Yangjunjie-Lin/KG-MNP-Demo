# 指定本机接口复测与正式质量报告代码补齐

本轮承接develop@84522072及前轮未提交变更。用户要求重新调用
`http://localhost:51900/v1`，指出6 Astra可用，允许必要时换模型和查阅官网。
用户在对话中提供的密钥未复制到任何文件、源码、报告或命令输出；调用使用已配置且通过
鉴权的本机凭据。其前缀正确，无字面反斜杠，GET models返回200且列出两个目标模型。

## 8次真实复测

固定模型`gpt-5.6-luna`、`gpt-6-astra`，reasoning=low；
Chat Completions使用`messages/reasoning_effort/max_completion_tokens`，
Responses使用`input/reasoning.effort/max_output_tokens`，UTF-8 JSON。
两种请求都声明输出上限128，正常测试要求`{"ok":true,"label":"本体"}`，
限额测试要求生成1至500的数组；均为合成诊断，无benchmark/gold或用户业务材料。

| 模型 | 接口 | HTTP | 正常中文JSON | 限额测试输出token（请求128） |
|---|---|---:|---|---:|
| Luna | chat/completions | 两次200 | 通过 | 1029 |
| Luna | responses | 两次200 | 通过 | 1033 |
| Astra | chat/completions | 两次200 | 通过 | 1007 |
| Astra | responses | 两次200 | 通过 | 1010 |

**结论：接口和两个模型正常可调用，不是字符或模型ID错误；当前网关没有执行上述请求级限额。**
前轮“阻塞”应准确理解为不符合原严格预算协议，不能泛化成“接口/模型不可用”。
换成Astra或Responses没有消除这项限制。此前在隔离实例补回字段后收到上游HTTP400的证据保持不变。
本轮没有修改Cockpit安装、运行配置或账号范围。

独立回执位于`runtime_reports/endpoint-recheck-20260921/live-matrix-01/`：
plan/health、八个实际request/response-public/result、summary。
响应只捕获已知合成JSON、公开model/finish/usage及原响应SHA，不记录私有reasoning或请求头，
不是原字节完整轨迹。调用端无重试；网关内部物理尝试没有独立spy，不能由本地日志自证。

## 预算及不变边界

本轮明确授权的最多8项复测使用原budget.sqlite，每项按模型官方最大输出128000加请求开销
保守预留。唯一plan/model/route/case约束阻止重发；普通full生成入口和历史违规latch不解除。
原325311 calls / 10659790848 reserved tokens总额不变。

本轮8次用量均返回，共6897 reported tokens；累计请求预留34条，已知tokens94252。
前轮1条400无用量，所以累计总token仍部分未知，费用未知，不伪填0。
前26条attempts逐行不变，旧STOP字节不变；full 99501个适用job仍未运行。
未经明确确认，不将“模型能回答”视为授权放宽单请求硬限额或绕过旧停机锁。

## 本轮实际补齐的质量报告能力

保留原评分与比较入口，只扩展其结果：

1. `paired_cluster_aggregate`同时输出baseline/experiment质量分和各自95%CI、
   成对差值及95%CI、百分点变化、相对变化百分比和区间。
2. 沿用按来源/整套本体分组、保留全部重复向量的paired cluster bootstrap；
   每次重采样重新调用原聚合函数，非可加指标不退化为平均每题F1。
3. 基线为零时相对变化为null；任何bootstrap样本基线非正时不筛掉该样本，
   相对区间明确不可定义。单独来源不能靠增加重复次数获得有效CI。
4. `quality_exports.py`由原`live_exports.finalize`接入，新增
   `quality-and-effects.json`、`quality-scores.csv`、`effects.csv`和`QUALITY_REPORT.md`，
   纳入输出摘要。CSV区分null/0，失败/缺指标不会丢弃。
5. Holm校正针对全部预登记任务×两个基线×主指标，弥补旧逐比较局部校正不能代表全族的问题。
   任一主比较缺失时保留整个族，adjusted p及支持提升结论为null，不能缩小检验族求显著。
6. 负变化、跨零区间和不显著结果保持可见。报告不是官方排行榜或生产审核。

这些是已实现代码，不是本轮正式质量成绩。测试使用明确合成数值，不能当模型研究样本。
本轮没有完成CQ4OE全评分、未解除OSKGC许可，未运行完整公开数据对照，也没有现成质量分可报告。
最终专项和同源码工程回归回执见本轮runtime_reports下的FINAL_REPORT.md。

## 下一步必须明确的实验控制条件

若继续使用当前订阅网关，需用户明确接受“不由网关保证单请求硬token上限”的新预算协议，
例如保留本地总调用/用量监控、逐请求保守预留和超限停机，并承认单次可能超过预期。
这与原请求级硬限额协议不同，不能自动解锁。另一条路仍是支持该参数的授权API路由。
确认后必须新冻结revision，统一模型完成独立开发修复与完整测试，不能混合Luna/Astra成绩。

本轮实际读取官方依据：
[Luna模型](https://developers.openai.com/api/docs/models/gpt-5.6-luna)、
[Astra模型](https://developers.openai.com/api/docs/models/gpt-6-astra)、
[Astra迁移](https://developers.openai.com/api/docs/guides/latest-model/gpt-6-astra)。
官方模型名和请求格式用于核对兼容性，官方API能力不能代替第三方网关实测。
