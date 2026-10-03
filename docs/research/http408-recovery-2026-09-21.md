# r4 HTTP408停机与有限恢复分类修复

心跳检查确认r4luna已停止：smoke9成功，pilot2成功/1失败/15待运行，full尚未启动。
失败job 948acb10ab990caaf688bff0 的第一调用成功，第二调用实际返回HTTP408，
没有usage；原公开响应、失败和135244保守预留保留，不推断为免费或零用量。
这次不是上下文去重失效：失败任务为Flagship且不是新卡片请求路径。

已有有限重试名单包含本地ReadTimeout和部分5xx，却漏掉HTTP层的Request Timeout（408）。
本次只补齐408分类，不增加max_attempts=3或总预算，不重试Schema/语义错误、401/403/429或预算违规。
新增参数化回归检查408仍须匹配原FAILED请求、响应SHA、job/attempt与授权；原费用不退款，
后续尝试必须使用新的ID和独立目录。冻结的r4源码和结果不改写，修复进入新revision。

本轮读取[OpenAI错误处理文档](https://developers.openai.com/api/docs/guides/error-codes)核对有限超时重试原则，
并保留其“认证/额度错误不能靠重试恢复”的边界；该页面未直接列出本机网关的408实现，
具体408来自本次真实HTTP状态，不以官网文字代替本机回执。

失败快照：runtime_reports/full-luna-20260921/after-r4-http408/。
代码/测试/新运行回执：同目录http408-*产物。全量分数仍未产生，不冒称所有实验完成。
