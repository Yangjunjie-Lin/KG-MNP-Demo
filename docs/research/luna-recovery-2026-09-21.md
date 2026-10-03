# GPT-5.6 Luna 评测恢复诊断：仍受当前网关输出限额阻塞

起点：干净 `develop@84522072be25e1304daf9b6ae22fef181b11f195`。
本轮用户明确要求将已下架的 Spark 改为 GPT-5.6 Luna，恢复完整 e2e，并修复过程问题。
没有据此增加原预算、改动其他应用安装/账号、换提供商，或以小样本代替完整评测。

## 真实运行结果

GET models 已列出 `gpt-5.6-luna`，不再列出旧 Spark。正式推理使用显式 Luna 模型和
low reasoning effort；主应用/用户全局环境变量未修改，旧 Spark revision 未续跑。
本机网关二进制已与旧记录不同，不能仅借旧源码判定新版行为，因此完成了新的独立诊断。

| 检查项 | 实际观察 |
|---|---|
| 输入 | 独立合成整数数组指令；无 benchmark/gold/用户资料 |
| 请求模型 / 返回模型 | `gpt-5.6-luna` / `gpt-5.6-luna` |
| 请求 max_completion_tokens | 128 |
| 返回 prompt / completion / total tokens | 477 / 1026 / 1503 |
| finish_reason | stop，不是达到请求上限后的 length |
| 结论 | BLOCKED_PROVIDER_OUTPUT_LIMIT_NOT_ENFORCED |
| 正式 benchmark 新预测 / 分数 | 0 / null |

原始请求、显式协议、公开响应、结果及逐文件 SHA 位于：
`runtime_reports/ontology-luna-20260921/live-limit-probe-01/`。
公开响应来自真实 transport worker，不保存供应商私有 reasoning、密钥或请求头。
本次只证明该实际路由未执行本次输出上限，不推断所有 Luna 部署均有此问题。

## 预算与历史保真

新增窄用途恢复诊断接口，不建立新预算、不允许普通生成跳过旧锁。
事务内核对历史违规 ID、显式本轮用户要求、目标模型、端点摘要和请求摘要；
每个模型/端点在同一账本最多一次恢复探测，重复、并发、无余额和扩大授权均拒绝。
探测按官方模型最大输出 128000 加实际请求 UTF-8 上界和2048开销预留，
而不是按正在测试的128额度预留。官方模型上界不冒充第三方网关的计费保证。

全局额度仍为325311 calls / 10659790848 reserved tokens，没有增加。
累计真实请求从24变25，reported total tokens从85852变87355；费用未知。
新请求保守预留130511 token，不退还失败预留。两次违规均保留；
本次逐行复核原24条 attempts 完全相同，旧 STOP 字节不变。
普通 reserve 仍因持久 latch 拒绝；probe 成功也不能单独授予全量恢复资格。

## 实现与验证

- `live_budget.py`：复用原全局限额校验，追加唯一约束的诊断授权及原子预留。
- `model_recovery.py`：固定合成请求、同端点/指定模型、120秒请求超时与150秒子进程上限；
  不自动重试，超时/未知用量不写0，响应接受与预算判定分离。
- `tools/probe_ontology_model_recovery.py`：要求显式本轮授权文件及执行标志；输出必须新建。
- `test_ontology_model_recovery.py`：覆盖并发仅一次、不增额度、不清锁、历史不变、模型错配、
  缺失/非法用量、真实截断与超限区分、失败不重发及不输出秘密；均为合成工程测试。
- 新测试纳入 `ontology-io-engineering`；测试结果不是研究数据，不能相加当 benchmark 样本。

初次专项35项通过；随后修复3个lint问题。最终同源码专项、工程回归、ruff与类型结果
另见 `runtime_reports/ontology-luna-20260921/` 的新日志/回执；不借用历史PASS，不预填全量结论。

## 恢复完整评测仍需什么

需要在本机配置一个对 Luna 确实执行输出限额的授权API路由，或另行明确授权修复当前网关。
不能通过降低提示词字数、客户端裁剪、关闭超限检测、删 STOP 或另建预算绕过问题。
本次不擅自修改 Cockpit Tools、登录账号或凭证路由。

新路由/网关方案确认后，仍需独立验证、审计恢复、新建冻结revision、重跑smoke/pilot；
三个对照系统统一使用 Luna，不把旧Spark结果合并到新成绩。
正式测试集不用于迭代调优，修复/提升在独立开发数据验证，再冻结后评测。
CQ4OE完整原生评分、OSKGC许可、独立性审计等缺口仍分别存在。
最终应报告真实质量分数、配对差值、来源组95%CI及失败分母，允许负提升或不显著；
在完整预测及评分完成前，这些值保持null，不以本轮诊断冒充正式e2e完成。

## 官方依据与适用范围

2026-09-21实际读取 [GPT-5.6 Luna模型页](https://developers.openai.com/api/docs/models/gpt-5.6-luna)
与 [模型说明](https://learn.chatgpt.com/docs/models)。Luna官方最大输出128000，支持low reasoning；
官方API说明不是本机第三方网关参数生效证明。模型列表/响应ID同样不构成独立权重修订证明。
