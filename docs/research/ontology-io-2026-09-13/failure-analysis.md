# 失败、未运行与限制

| 记录 | 原因 | 处理和结论 |
| --- | --- | --- |
| 首轮 `research-7cc8176ba88c4d43aa47f23d4176648d` | 测试过程源码发生变更；123 tests返回0，source guard返回非0 | 保留原文件；仅新最终回执可支持受测源码工程结论 |
| typed/OWL adapter开发首轮 | JSON Schema字典括号未闭合，后续ast.Module类型与import排序问题 | 在新增模块修复；全量ruff/types和149项suite最终重跑，未抹掉原工具输出 |
| 同用户子进程canary | `python -I`仍读得到相邻scoring/canary.txt | 真实观察为access_denied=false；不能声称OS隔离成功，LIVE入口拒绝 |
| Docker探测 | Linux engine命名管道不存在 | 未自动启动daemon或更改系统网络，仍BLOCKED |
| 51,615个full计划单元 | 未授权预算、完整Ours/隔离等资格缺失 | NOT_RUN，不记模型FAILED，不省略分母，不把空预测特殊分数填进结果 |
| LLMs4OL固定指标/网页不一致 | Neighborhood、Taxonomy、空图与无taxonomy特例、P/R函数缺失 | 报告代码/描述差异，固定函数不修改。无semantic权重时null，不用exact冒充 |
| CQ4OE ODRL | README写CQ2Onto 19，锁定输入18；CQ2Term还有重复编号 | 保留实际18题；重复CQ使用复合ID，未补造或覆盖问题 |
| CQ4OE评分环境 | embeddinggemma未锁；完整对齐与HermiT公理链未集成 | 只对已实现hard term方法做工程评分等价；其余原生指标null |
| OSKGC数据许可证 | 标题NC-SA vs正文BY冲突 | 阻止新数据使用，不以“科研”自动推定许可；旧证据不删除 |
| Ontogenia/Memless | 前者引用文件未随固定树提供；后者虽有完整prompt，适配/运行未完成 | 两者都不算已运行baseline；没有假造论文人工评分 |
| 非可加统计 | 跨样本集合micro不是均值F1；CLI尚缺native payload比较接口 | 新bootstrap回调重算通过单元反例；不接通的CLI路径拒绝，研究CI/p为null |

没有模型错误分类频次、专家语义错误分析或质量-成本曲线：本次外部生成0次，
这些需要真实预测。合成故障注入只验证错误保留机制，不能冒充模型失败率。
