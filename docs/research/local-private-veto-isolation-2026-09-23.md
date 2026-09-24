# 样本本地隐私拒绝的隔离续跑（2026-09-23）

r8luna在控制v2下实际生成到1235项，12:27:51Z因作业3faa72fa99f5a9b5f1ba8d2c
第二个caller请求发生ToolBlocked且usage未知而停止。该作业只有一次执行尝试；它不是
HTTP502/503三次耗尽，不能伪称网络重试或复制第三次ack。原workflow状态落后于真实
进程退出；诊断以实际进程、CONTROL_STOPPED、jobs与budget为准。

冻结客户端的traced_proposal在处理context时会先运行既有public_value隐私门。
独立进程加载**原r8冻结源码与同一请求**，使用独立MockTransport spy，复现
MODEL_PRIVATE_INPUT_FORBIDDEN且spy=0；没有真实模型调用。该工程复现不反推历史物理
请求数为0，不把原usage=null填零，也不退款。原失败调用134706 tokens预留保留。

用户已明确要求继续全量、不再因样本失败反复暂停。本次控制v3只隔离这种可证明的本地
拒绝：样本仍FAILED、原请求不改、不重试、不传出被拒内容，继续其他原已授权PENDING。
隐私门、语义门、Prompt和生成器没有修改。每次自动隔离须校验原响应SHA、终态历史、
源代码锁、请求文件SHA，并在无凭据子进程中重新进行独立HTTP spy验证。
无法证明的ToolBlocked、鉴权/额度、成功但缺用量、在途不确定、新超额和证据变化仍保护。

原budget.sqlite保留既有记录，并追加带failure_class=PROVEN_LOCAL_PRIVATE_INPUT_VETO
和independent_offline_proof的操作者续跑收据。该类别与EXHAUSTED_TRANSIENT_TRANSPORT
明确分开，不是新的模型成功、审批事件、自动重试许可或外部交付类别。
所有旧生成结果、失败、费用、原ID、v1/v2控制冻结和原研究分母原样保留。

控制源码冻结于runtime_reports/full-luna-20260921/resume-control-20260923v3/；
35项控制测试（含实际冻结代码/独立spy的两个合成集成检查）+54项原回归，
共89 passed、0 failed、0 skipped，Ruff通过。真实只读preflight前后都是3439个caller请求。
13:53:42 Europe/London启动新控制PID25120；以原账本和实际后续回执判断是否持续运行。

证据：private-guard-20260923/diagnosis.json、resume-control-20260923v3-live-preflight.json、
resume-control-20260923v3-validation-final.xml、v3/freeze.json及sessions/，均在上述runtime根。
这不是正式质量分、效果提升或置信区间；评分许可/完整CQ2Onto适配和全量生成未完成的
限制保持。不提交、推送、发布、扩预算，不修改正在使用的冻结控制源码。
