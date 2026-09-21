# 全量实验续办：失败用量修复与离线完整台账

本轮继续实现和验证，不新增付费推理、不解除此前的超限停机锁。
develop HEAD仍为 `adc2a40512f8b029b6c21420b905628c32952d00`；工作树不是干净提交。
本轮实际源码摘要、工作树diff和逐命令日志保存在
`runtime_reports/full-ontology-experiment-20260914/continuation-final-verification-20260915/`。
历史r1生成快照、24次调用和失败记录未覆盖；本轮代码变更不追认到r1。

## 当前结论

**BLOCKED：尚不能回答相对直接prompt提升多少。**
full尚未运行；不存在正式F1、配对效应、置信区间或显著性结果。
工程检查通过不代表本体质量更好，也不等于“没有提升”。

| 阶段 | 成功生成job | 失败job | 未运行job | N/A位置 |
| --- | ---: | ---: | ---: | ---: |
| smoke（合成格式/链路检查） | 9 | 0 | 0 | 0 |
| pilot（独立公开来源留出） | 0 | 1 | 17 | 0 |
| full（预登记矩阵） | 0 | 0 | 99501 | 20934 |

共120462个调度位置；不是120462个独立样本。
full输入为3471条Flagship、2252条Reuse，以及CQ2Term/CQ2Onto各6套本体；
重复调用不扩大独立样本量，任务间共享来源不能当作独立来源。
实际累计24次模型调用（含单独probe），85852 reported tokens；费用未知。
本轮新增真实推理0次。

## 已修复的真实缺口

| 缺口 | 实际修复及证据 |
| --- | --- |
| JSON/Schema/拒绝/截断/错误模型回复被拒绝后丢失usage | `CompatibleClient.propose`在内容验证之前保留白名单用量和耗时；不记录隐藏推理；每次清除上一调用诊断 |
| 无效回复的超限不能进入全局账本检查 | `live_broker.dispatch`对成功receipt或失败public_response同样核对completion上限、扣账并持久停机 |
| 引擎失败资源记录把已知token变成unknown | `engine.generate_sample.ask`将失败回复中的已知用量、耗时保留；真实未知仍为null，不填0 |
| 未完成实验没有完整可复核导出 | 既有finalize入口新增`--mode snapshot`；读取原账本，逐项保留pending/failed/N/A，并核对冻结预测、响应及图往返 |

未放宽生产审批、v3 Schema、OS隔离、数据许可证或预算。
这项修复只保证核算和证据保真，不修复提供商忽略token上限的问题。
原来的24次调用均已有账本用量，因此本轮没有重写历史token数。

跨进程重导出还发现摘要清单的键顺序受Python哈希随机化影响；已固定排序。
最终用`PYTHONHASHSEED=17/43`、清除本次进程的OPENAI配置分别重跑，
`report.json`、`comparison.json`、`jobs.jsonl`、`results.csv`和`evidence-lock.json`
逐字节一致；60项原始证据摘要全部匹配。
旧的顺序不稳定导出保留，不将其改成最终版本。

## 为什么仍未恢复付费调用

重新核查现有进程配置：模型仍为`gpt-5.3-codex-spark`，端点摘要仍为
`4d47e83a1046b7cd6ee28635a01cf12b2a98aa0acddda6be0db63d0bccbb58c2`；
没有已配置的Qwen替代路由。未搜索其他应用私有凭证、未输出密钥或转送到新域名。

固定网关源码的Chat Completions转换器也注释掉了`max_tokens`和`max_completion_tokens`
到`max_output_tokens`的映射，见历史`gateway-audit/1-codex_openai_request.go`第41–57行。
所以改字段名、降低reasoning或限制文字长度不能构成请求级计费硬上限。

按照OpenAI Docs核对，[Chat Completions参数定义](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)
中的completion上限涵盖可见输出和推理token；但本机实际出现8192请求上限与27832返回completion token。
官方参数定义不能证明第三方网关执行了该参数。
[官方模型说明](https://learn.chatgpt.com/docs/models)将Spark列为研究预览；
本轮没有核实出可直接替换的同底座硬上限API路由，也未将普通Codex参数冒充Spark能力。

继续生成需要在本机配置并明确绑定一个确实执行输出硬上限的路由及其对应凭证。
如果只能换模型，要在新协议中统一更换所有系统并重新冻结，不能混合不同底座成绩。
应保留全部历史扣账与超限事件，经受审计的恢复流程建立新revision；
不要删除STOP、清空budget.sqlite、重跑activation或以另建账本绕过停机。

剩余预算也已只读复算：授权尚余325287次调用，r1未运行的full最多325311次、
剩余pilot最多56次，合计325367次，比剩余额度多80次；这还不包含新revision重做预检。
这是最坏情况预算差额，不是已经发生的费用或必然调用量。
现有全局限额仍会阻止超额请求，未自动增加额度；恢复时必须重新冻结包含预检/失败历史的总上界，
不能保证原有额度足够完成所有最坏路径。

## 可直接复现的离线交付

入口不依赖生成密钥，也不读取scoring/gold。它导出状态与完整度，不冒充原生语义评分：

```powershell
python tools/finalize_ontology_experiment.py --mode snapshot --workspace runtime_reports/full-ontology-experiment-20260914 --revision r1 --output runtime_reports/full-ontology-experiment-20260914/offline-inventory-replay
```

每次使用新的输出目录；已有目录拒绝覆盖。交付文件为：

- `results.csv`：benchmark/task/scope/system/model/profile、样本与来源组、计划/成功/失败/未运行/N/A、调用/token/耗时、指标及null分数。
- `comparison.json`：B0/Bbudget对Kernel的比较均为BLOCKED，delta/CI为null。
- `jobs.jsonl`：全部原始sample/system/repeat标识、状态、结果引用和摘要。
- `report.json`、`report.md`：当前完整度与限制；单独计入probe，避免调用数丢失。
- `evidence-lock.json`、`sha256.json`：输入数据库、冻结协议/响应/产物与导出文件摘要。

最终实际输出为`runtime_reports/full-ontology-experiment-20260914/offline-inventory-final/`，
跨哈希seed复现为相邻`offline-inventory-final-replay/`。

正式`--mode finalize`仍在full有pending时拒绝执行，不能从成功子集生成研究结论。
已生成9个smoke产物重读核对通过；不把合成typed smoke的路由配置名当作OSKGC或Reuse真实数据成绩。

## 验证和剩余范围

专项测试覆盖：五类拒绝回复保留计费、未知/非法usage不伪填0、失败回复超限停机、
无凭证/禁网络/禁gold离线重放、种子重复不扩大样本数、全量pending/N/A保留、
数据库字节不变、旧导出不覆盖以及预测/图/响应被改动时拒绝导出。
专项37项测试通过，结果见`continuation-accounting-tests.xml`；
最终完整回归210项通过（13项上游弃用警告），ruff、types及独立extended复核退出码均为0，
源码前后摘要一致`78ca300ea0dcd474ec17d29383c4d1939c5d50b378bc1ab6ee7d9a4787ce762b`。
见`continuation-final-verification-20260915/verification.json`。
该次回归使用独立`PYTEST_DEBUG_TEMPROOT`，未删除历史回归或实验目录；
628个r1冻结源码文件也逐一校验无变化。
期间的`continuation-verification-20260914/`属于修复排序前启动的中间回归，保留但不作为最终源码资格证据。

OSKGC许可证冲突、完整CQ4OE对齐/公理/CQCoverage、semantic匹配器权重、
Ontogenia论文方法实跑及全部full质量对比仍未完成。
这些独立缺口没有因为导出台账或修复失败用量而变为完成。
