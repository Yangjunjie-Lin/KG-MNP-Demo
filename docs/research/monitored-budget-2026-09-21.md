# 当前本机接口：经确认的本地用量监控预算协议

本轮承接develop@84522072和此前未提交修订。用户确认继续当前接口并改变原预算协议。
此前Luna/Astra可正常响应、但请求级token上限不被执行的证据保持不变。

## 明确变化

新研究运行统一`gpt-5.6-luna`、low，使用`http://localhost:51900/v1`。
`max_completion_tokens=8192`继续发出，但明确为advisory；不宣称网关保证它。
按官方模型最大输出128000加实际输入UTF-8上界/开销预留每次请求，
本地总调用和有效计费检查必须在发出请求前原子完成。
官方模型上界仅是本地保守预留依据，不是第三方服务计费承诺，单次仍可能超过预期。

原总预算仍325311 calls / 10659790848 tokens，不自动增额。
同一budget.sqlite中新增monitor_policies、monitored_attempts；旧authorization/attempts不改写。
所有旧调用、失败、未知、探测与原预留继续占账。新成功请求只有在完整有效usage返回后按实际用量
结算；失败或未知保留预留，已知高于预留的用量追加扣账，绝不低估。
原snapshot.reserved_tokens仍代表历史原始保守预留总和；新monitor.effective_charged_tokens
代表此协议下的实际控制金额（token，不是货币），两者不得混同。费用未知仍null。

## 权限、绑定与停机

只有本轮明确授权文档、当前历史账目摘要及违规ID完全匹配时才创建新policy。
policy绑定模型/端点/推理档与原总上限，不能被生成Agent自报授权。
普通旧reserve继续因历史latch拒绝；新broker入口只对绑定policy的请求承接旧违规。
新违规、超过保守预留、usage缺失/非法/不一致会停止新policy，不自动重试或自动承认新错误。

旧STOP文件不删除；新policy记录并承接其原摘要。旧STOP字节变化仍停机。
另外创建`runtime_reports/full-ontology-experiment-20260914/RUN_STOP`，或
`revisions/<new-revision>/STOP`，即可停止新派发。已经发出的请求不能保证供应商即时停止计费。
未知中断不重发相同request_id，不重用旧冻结Worker快照或将模型更名到旧结果。

## 实施与复验

`tools/authorize_ontology_monitoring.py`只追加授权，不调用模型；新引用存入
原Protocol.total_run_authorization.budget_monitor，未为旧协议增加默认序列化字段。
`live_runner.init --monitor-reference`创建新revision，冻结当前代码、输入、模型及真正OS canary。
Worker无模型凭据/网络/gold；原两个Agent、共享编译、任务输出和评分链不另建。
模型请求和公开响应继续保存，新增记录说明建议上限被超过与实际预留。
生产服务/工作台的审批、权限、导出契约及ID不变。

smoke、pilot必须完成且无失败才能继续；full每个任务仍保留全部计划分母。
CQ2Onto完整原生评分尚未接通，full调度保留其pending作业但不消耗模型调用；
LLMs4OL及CQ2Term hard评分可先执行。不能把可执行任务的结束冒称全部benchmark完成。
后续修复使用独立开发/smoke/pilot，不读取full gold调优；实现改动必须新revision。

最终执行/验证结果单独记录在`runtime_reports/monitored-luna-20260921/`，
本文不预填完整评测成绩。正式质量分、提升和95%CI只由完整冻结预测的独立评分产生。

官方依据：[Luna模型](https://developers.openai.com/api/docs/models/gpt-5.6-luna)、
[Chat Completions参数及usage](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)。
官方定义仅用于参数和预留依据，网关不执行请求级上限仍按实测事实披露。
