# 本地 6 Astra / 极高：真实 API 烟雾测试

日期：2026-09-13。结论：**4 次真实推理请求全部通过本次合成工程检查**。

配置：`http://localhost:51900/v1`，模型 `gpt-6-astra`，显式发送 `reasoning_effort: xhigh`。
认证使用用户提供的密钥，通过无回显输入传入；运行时确认与本地进程配置一致。
密钥未写入代码、回执或终端输出；没有修改全局默认模型或密钥配置，没有回退模型。

| 检查 | 推理请求 | 网关报告 token | 模型请求耗时 | 结果 |
| --- | ---: | ---: | ---: | --- |
| 直接文本生成 | 1 | 843 | 4.88 秒 | 预期 4 条合成事实全部匹配 |
| 双 Agent primitive 原型 | 2 | 2,358 | 26.02 秒 | S1–S5 顺序运行，预期 4 条合成事实全部匹配 |
| 双图颜色顺序识别 | 1 | 669 | 6.03 秒 | 两张不同排列的合成图均正确 |

总实测墙钟时间约 **39.06 秒**。网关报告合计 **3,870 token**：输入 3,043，输出 827，
其中推理 token 499（包含在输出数内，不重复相加）。这些是网关返回值，不是账户扣费证明；实际费用未知。
每次请求使用 `max_completion_tokens: 8192`，整次运行最多 4 次推理，没有自动重试。

两种文本流程生成的实际磁盘 RDF 均已独立重读，摘要/图投影校验通过。
图像检查使用两个真实 PNG 输入，不是把图片说明伪装成视觉输入。
没有发送业务文档或私有 benchmark gold，没有审批/发布版本。

## 验证边界

- 四次响应均报告模型 ID `gpt-6-astra`。
- 请求明确包含 `xhigh`，且记录到请求回执。网关没有回显推理强度，因此标为
  `REQUEST_ONLY_NOT_ECHOED`，不冒称已经独立验证代理上游的实际强度或模型权重修订。
- 这是合成工程烟雾测试，不是 LLMs4OL/CQ4OE/OSKGC 正式评测，也不是完整多模态摄取链验收。
- 双 Agent 项仍是 primitive pilot，不等于完整 TwoAgentV3 已完成；不据此宣称流程优于直接模型或立项目标达标。

## 证据与复现

- 原始实测回执：`runtime_reports/astra-xhigh-smoke-c6d6e3a4c5ae4b7eb29c0304a2149f6c/report.json`。
- 该目录保留公共模型回复、各次请求、实际 RDF、两张 PNG 和图像识别结果；不含认证头或隐藏思维链。
- 实测前后实现源码摘要相同：`4bb2119a37fbcc54fa192f45a5f6b09056ab628950fac02f121d2ca9a03fd7f2`。
- 无网络回归 **57 passed**，JUnit：`runtime_reports/astra-xhigh-offline-regression.xml`。
- 全仓 Python lint、修改模块和测试入口的类型检查通过。

显式再次测试（会产生最多 4 次新的真实推理请求）：

```powershell
python tools/test_local_astra.py --credential-source prompt
```

终端中通过隐藏输入提供密钥。不要把密钥写在命令参数或仓库文件中。
未来使用通用配置入口时，可在测试进程中设置 `OPENAI_REASONING_EFFORT=xhigh`，
并在冻结评测协议中使用同一个 `reasoning_effort`；不一致会在调用前拒绝。

参数依据：[官方模型说明](https://developers.openai.com/api/docs/models/gpt-6-astra)、
[官方推理参数说明](https://developers.openai.com/api/docs/guides/reasoning)。
