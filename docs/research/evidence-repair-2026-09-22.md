# r5空修复拒绝：补充源定位反馈，保留原门

心跳检查r5luna已停止：smoke8成功/1失败，pilot/full未启动。
失败为合成smoke-text/TwoAgentKernelV1，在S4报告三个EVIDENCE_QUOTE_UNBOUND后，
模型的修复调用把原四条triples改成空列表；REPAIR_EMPTY_OUTPUT_REJECTED正确拒绝。
这不是网络错误，不能按传输重试直到成功，也不能删除该失败。
原3次真实调用、3696 reported tokens、提案/错误和快照全部保留于r5及after-r5-empty-repair。

## 新的修复指导

原反馈只有错误类型/triple_index，没有告诉模型原引用在冻结文本中的实际位置。
新增evidence_hints仅用本次public text、原模型引用和冻结chunks进行转义后的精确文字查找，
位置再经原bind_quote核对。输出Unicode code-point半开区间、原proposed_start、短预览及实际匹配数量。
最多8条提示、每条最多4个位置，诊断省略数量及预览是否完整明确标注；原完整输入/错误列表不裁剪。
重复引用返回多个候选，不静默任选；不存在的引用返回0；源版本不一致仍拒绝。

提示不是gold，不新增事实，不证明引用与三元组的语义蕴含，不修改原提案或自动绑定错误offset。
模型仍须返回完整新提案并通过原引用、语义/编译及非空修复门；原回归明确验证空修复仍FAILED。
修复提示说明：位置错误本身不表示事实不存在，应核查原文并修复引用，不能清空结果隐藏错误。
规划提示同时重申所有系统已有的primitive记法is-a/instance-of，不在事后把模型别名改成正确答案。

## 不变与验证

不增加修复轮数、模型调用上限、字符/上下文/总token预算，不重试低分，不读取full gold或质量结果。
只在新的r6luna源码快照中执行，r5不改写。模型依然Luna/low，同一本预算账本和授权。
合成测试覆盖Unicode、重复/虚构引用、冻结文本漂移、有界提示、原数据不变及空修复仍拒绝。
同源Prompt MD/JSON重新生成；实测与最终源码回执写runtime_reports/full-luna-20260921/evidence-*。
正式全量分数、提升与CI仍未产生，不把这些工程检查当作研究成绩。
