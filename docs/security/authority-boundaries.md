# 权限、证据与执行边界

## 身份不是客户端表单字段

本地管理员签发随机访问凭证，服务端只保存摘要。浏览器换取短期不透明 HttpOnly 会话；生产 Cookie 使用 Secure 和 SameSite。HTTP 例外必须显式启用且仅用于 loopback。

写请求检查 Origin / CSRF，服务端从 TokenStore 重建 Principal。角色、审核人、审核人数和批准状态不能由请求 JSON 提供；服务账户不能进行人工批准。退出清除浏览器查询缓存，撤销和到期在后续请求与任务提交时重新检查。

生产 Release 策略要求现有五类角色覆盖及至少两位独立审核人。一人持有多个角色仍不能满足两人要求。开发单人策略有独立的有效策略身份，只能显式用于 loopback，不能被生产候选复用。

## 项目和工件

项目句柄、核心 Workspace、Registry、上传暂存和 Artifact 位置不是同一个目录。任何 Source、Evidence、Job、Package 或 Release 读取都检查项目归属。

上传文件名仅用于展示。服务器计算实际字节摘要并限制收到的字节数；客户端不能传入任意服务器绝对路径。Source 内容是资料，不安装插件或执行代码。原文下载强制作为附件；界面不执行原文 HTML 或脚本。

路径先做词法约束，再检查符号链接、junction / reparse point 和解析后的归属。原始 ASGI 路径和 Host 在 URL 重建及静态文件解析前校验，Windows UNC 请求不会进入静态路径解析。

## 人工决定与提交

Scope 批准带当前 approval revision，Review Action 带当前审核头；冲突要求重新读取，不能自动重复批准。候选修改产生新 ID 并重验。Release 和环境审核按每位审核人的最后决定计算，旧批准不能覆盖新的拒绝。

Job 幂等域包含 Principal、Project、Operation 和 Key；同 Key 不同正文冲突。工作页关闭不取消任务；Cancel Requested 不等于 Cancelled，更不撤销已提交工件。

Worker 提交与租约检查共享权威提交序列；租约时间在获取 SQLite 写锁后重新读取。失去租约、取消、权限撤销或 CAS 改变都阻止未提交工件发布。真实进程骤停测试分别覆盖原子提交前后。

恢复先验证提交回执和实际工件字节。显式本地重试重验原凭证、恢复操作者及 expected_attempt，并增加 fencing token；取消意图或未知外部副作用不能被这样重放。

## 查询与集成

对象查询绑定明确 Package，或绑定经验证的 Release / Package 对。只读查询在独立进程中运行，限制时间、结果和分页；IRI 不能注入 SPARQL。消费者查询同样禁止 UPDATE、SERVICE、远程 FROM 和自动修复。

GraphDB / Workflow 计划、协议检查、真实可用性和执行观测分别报告。offline_only 不因批准计划而被取消。Outbox 入队不代表外部业务执行，Pointer 切换不代表部署。局部 loopback 例外不能变成任意主机或 metadata 地址的出口许可。

## 证据的含义

Hash、Lock 和闭合性不证明来源内容真实；角色声明的真实性来自本地凭证权威，而不是字段本身。本工具不是企业 IAM、分布式高可用 Registry 或安全认证。

测试只使用合成账号和资料。浏览器超时日志可能包含 Cookie，因此归档前脱敏，保留失败断言和位置；长期凭证、用户工作区和临时运行数据不进入 Git 或发行包。

依赖公告检查只覆盖查询时已知的公开公告。最终安全与回归判定必须绑定实际受测修订，不能把配置了安全门等同于运行通过。
