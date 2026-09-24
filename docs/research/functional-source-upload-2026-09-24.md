# 功能源码上传范围

用户于2026-09-24要求上传当前 benchmark 以及 Prompt/Token 计量相关功能程序。
本轮从 develop@84522072 的实际改动构建独立 `codex/benchmark-prompt-token-audit-20260924`
分支；不切换仍在运行的原 develop、不改其冻结生成器、源码指纹、预算和观察器。
提交/推送此分支不等于合并 main/develop、发布软件、完成全量研究或取得新模型授权。

## 包含

- benchmark 完整清单核验、任务分发、失败/重试费用保留、本地预算监控与有限传输恢复；
- 上下文压缩视图、词汇闭包、来源引用定位与 fact/quote 耦合；
- 原生评分之后的质量分、绝对/相对提升、配对95%置信区间与完整比较族 Holm 校正输出；
- 从源码生成的实际 Prompt 目录及审计文档；
- 只读逐调用/步骤/运行 Token JSON 程序、快照提取器、可选表格构建器与测试。

原审计文件在运行目录中被冻结，仓库卫生规则也禁止提交 runtime_reports。
所以本分支把这些少量程序整理为 tools/ontology_usage_audit 下的独立 portable-v1 分发版本，
提供稳定入口并重新绑定分发源码/依赖摘要。原运行副本完全不动，不放宽卫生规则或修改既有冻结回执。
分发调整限定于导入/格式、UTC等价别名、显式安全异常类型和相对依赖路径，不改用量口径或原账本。
原冻结元数据单独保存在 source-origin.json，只作来源说明，不冒充本次分发验证。

## 不包含

真实预算/job SQLite、API key/环境文件、运行专属授权、原请求/响应正文、预测和 gold、
模型权重、node_modules、生成的 JSON/XLSX/CSV 大报表、会话日志与本地控制器的授权/冻结材料。
全量持续运行的控制 v4 仍属原本地工作区，不把其绑定特定运行的恢复授权作为软件默认配置发布。
可选表格构建器依赖另行提供的 @oai/artifact-tool；标准 JSON 审计只需 Python3.12标准库。

## 验证入口

```powershell
python -m ruff check . --no-cache
python -m tools.generate_model_prompts
python tools/evaluate_research.py --suite ontology-token-audit
python tools/evaluate_research.py --suite ontology-io-engineering
python scripts/check_repo_hygiene.py
```

上述工程测试不发付费模型请求，不等于完整 benchmark 的质量结果。
正式指标仍取决于完整冻结预测和适用的独立评分器；缺预测/许可/适配仍保留 null/BLOCKED，
不以成功子集或合成测试冒充正式质量、提升幅度或置信区间。
原本地旧 v4 中断测试的时间夹具不稳定及失败回执继续保留，不宣称已修复或全绿。

## 本次实际验证结果

- Token 分发/入口专项：38通过，0失败/跳过。
- Prompt 与独立物理请求审计专项：33通过，0失败/跳过。
- benchmark 工程回归：341通过，0失败，9项因未准备固定上游 CQ4OE scorer 资源跳过，
  这9项属于未执行，不作为通过或正式评分证据。合计412通过、9项未执行。
- Ruff通过；使用既有锁定的Pyright检查隔离副本，0 errors / 0 warnings。
- 分发程序及依赖的暂存Git blob与本次分发freeze摘要逐项一致，避免跨平台换行破坏自检。
- 待上传改动的敏感内容/路径/产物检查无新增问题。全仓卫生检查仍有5处**原有**历史证据
  绝对路径问题；已经核实这5个文件相对原HEAD无改动，没有删证据或添加豁免来获得全绿。

首次较广回归保留为339通过/1失败/10跳过，失败因为隔离worktree没有被Git管理的ROBOT JAR。
随后仅复用原本地已安装且通过SHA/HermiT版本核验的JAR重新完整运行，得到上述341通过/9未执行，
没有改测试门槛、静默下载权重或运行付费探测。原始日志和XML留在本次本地验证目录，不随功能源码上传。

原有卫生失败文件（均未改写）：

- docs/research/benchmark-selection-2026-09-14-evidence.json
- docs/research/formal-call-parameters-2026-09-14-evidence.json
- docs/research/full-experiment-activation-2026-09-14-evidence.json
- docs/research/ontology-io-2026-09-13/execution-evidence.json
- docs/upgrade/ontology-kernel-v1-evidence.json
