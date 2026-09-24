# 经授权的Cockpit限额修复尝试：当前OAuth上游拒绝该字段

用户在“继续检查并修改本机Cockpit Tools网关”问题后回复“授权”。本轮承接
[Luna恢复诊断](luna-recovery-2026-09-21.md)，基线仍为develop@84522072；
前轮未提交修改保留。本轮无新提供商/新账号/增额/关闭预算门授权。

## 实际诊断与修改范围

已安装Cockpit Tools 1.3.57，其sidecar SHA256：
`5ab1b1c51c24777ca54f8ef2501bade0287e3bd10d85e635c876779897aba0ce`。
公开tag v1.3.57解析到commit `3a83b85a18f9f62ff2f4b34679796229072b4129`；
独立只读源码在runtime_reports/gateway-repair-20260921/cockpit-source/，
未声称公开源码与安装二进制存在可验证构建证明。

源码Chat Completions转换器注释掉token-limit映射，Responses转换器主动删去字段，
说明是Codex上游拒绝。executor在转换后调用ApplyPayloadConfigWithRequest，
因此无需直接替换安装文件，可先用已有payload override补回max_output_tokens验证。

仅建立临时本机实例，使用同一已安装二进制：

- 绑定127.0.0.1临时端口；原服务51900不停机、不重启、不改默认路由。
- 原配置/manifest/额度状态先备份；active auth JSON仅复制到应用旁ACL限制目录。
  原auth目录14份历史.bak不复制、不删除、不视为活动账号。
- 保留原授权OAuth账号范围、native Luna模型和strict无备用提供商路由。
- 关闭请求重试，最多尝试一个凭据；关闭图像生成、自动凭据刷新和完整请求日志。
- override只对codex协议下的gpt-5.6-luna设置max_output_tokens=128。
- 固定独立合成输入（1到500的整数数组），不读取benchmark/gold或用户业务资料。
- 无论结果成功、失败或异常，都终止本次临时进程；不自动部署未验证方案。

私有备份/测试配置在用户应用目录下`ontology-luna-gateway-20260921-01/02/03`，
访问权限限定当前用户和SYSTEM，未输出其中API key、access token、邮箱或账号标识。

## 真实结果

**临时网关返回HTTP400：`Unsupported parameter: max_output_tokens`。**

这次不是“字段继续被忽略”：补回字段后出现明确的不支持错误，和转换源码说明一致。
当前配置的两个账号均为OAuth类型，没有可直接切换的官方API-key路由。
不能把官方API参数定义、客户端截断或更换字段名称当作本端点已经具备服务端硬上限。
同样不能由此推断所有GPT-5.6 Luna部署均不支持token上限。

新回执：`runtime_reports/gateway-repair-20260921/forwarding-probe-02/`：

- change-plan.json：修改内容、固定二进制/原配置摘要；没有秘密正文。
- authorization.json、request.json：当前授权和实际发出的合成请求。
- response-public.json：HTTP状态、不支持字段的安全白名单信息及响应SHA；
  不保存原错误全文、请求头或供应商私有推理，不声称原字节完整轨迹。
- result.json：真实结果、原预算前后、历史账目/STOP/安装文件未改的核查。
- cleanup.json：临时进程47572已停止；原服务进程45904继续运行。

调用端仅发出一次POST；已在配置层禁重试，但没有独立上游物理请求spy，
故不把网关内部物理请求数写成已被独立证明的1。

## 预算和历史记录

使用原budget.sqlite，未增加总额度、未删除STOP、未改旧revision。
增加1条FAILED记录：此前25条attempts逐行保持不变。
本次响应没有usage，计为未知，不填0、不假定免费，也不退还130516的保守预留。
累计请求预留26次，已知reported tokens仍87355但已是不完整总数；费用未知。
普通生成latch仍有效；新增gateway_change_sha256唯一约束，换临时端口也不能
对同一个修改重复付费探测。没有full任务在后台继续。

## 工程修复及验证

新增gateway_repair模块及测试，追加恢复账本的修改摘要唯一键，纳入原ontology-io-engineering。
覆盖配置不原地修改、仅本机监听、无跨提供商fallback、无自动重试、备份/日志秘密保护、
上游拒绝的未知用量核账、改端口拒绝重复、错误后的临时进程清理与历史证据不变。

预检失败保留：首次测试相对导入导致收集失败；首次真实准备因尚未审阅原生路由配置拒绝；
第二次准备发现.bak；第三次启动拒绝图像配置的内部枚举all，改用文档允许的true后重测。
以上均在发出模型POST之前，不补写为成功、也不消耗模型调用预留。
最终测试/静态检查和源码身份见同目录FINAL_REPORT.md，不能借用旧PASS。

## 为什么不能仅在本机修成完整e2e

配置透传路径已实测，但上游服务明确拒绝控制字段，本地改源码不能赋予上游该能力。
没有将会持续报400的测试配置部署到正式服务，也没有通过截断响应/降低reasoning/
关闭超限检查制造“修复成功”。正式本体质量分数、提升幅度、95%CI仍为null。

继续需要用户在本机配置支持Luna输出硬上限的授权API服务，并确认该路由的计费授权。
官方API凭据与订阅OAuth凭据不可互换，不能搜集其他应用密钥或转发现有OAuth token到新域名。
新路由合格后才进行审计恢复、新revision、独立开发修复及冻结后的完整成对生成/评分。

依据：[官方Chat Completions参数](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)、
[Luna模型](https://developers.openai.com/api/docs/models/gpt-5.6-luna)、
[固定Cockpit源码](https://github.com/jlcodes99/cockpit-tools/tree/3a83b85a18f9f62ff2f4b34679796229072b4129/sidecars/cockpit-cliproxy)。
官方说明用于核对字段含义，不能替代本机转发/上游实测。
