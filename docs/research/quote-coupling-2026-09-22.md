# 显式研究模式：事实与引用耦合、程序严格定位

r6 smoke9成功、pilot17成功/1失败。失败是Flagship/TwoAgentKernelV1的空修复拒绝，
不是网络故障，不作为网络重试直到成功。原3次调用、13378 reported tokens、原回复及错误均保留，
after-r6-empty-repair独立快照重读26个成功产物。

仅分析独立pilot的public输入与模型提案，未读取full gold或质量成绩：
首轮模型有53条实际triples、54条evidence（索引0–53），54个quote都唯一精确存在于原文，
但只有1个模型填写的start正确。要求模型同时维护并行数组和手算Unicode偏移，产生了无谓脆弱性。

## 新模式与旧模式分开冻结

原MODEL_ABSOLUTE_OFFSET默认路径完全保留，错offset仍被原规则拒绝。
新模式PROGRAM_UNIQUE_QUOTE_V1通过`live init --program-quote-locators`显式写入新Protocol和manifest。
它不是修改r6冻结Worker或把r6失败改成通过，不混合旧/新版本质量结果。

文本生成的模型JSON改为facts数组，每行只有实际triple、同一行的verbatim quote；
SCHEMA_ABOX同一行还必须包含对应schema。模型不提供offset或另一个evidence_index数组。
解码器按实际返回顺序投影为原canonical triples/schemas，不增删、去重或语义改写任何事实。
原公开响应仍留存，可逐行对应；原生IRI及业务交接Schema不改变。

## 不是放宽来源验证

- quote必须在**完整冻结原文**中恰好出现一次，且落在原冻结chunk窗口中。
- 仍调用原bind_quote重核文本/hash和真实位置；跨窗口、源漂移、虚构或重复歧义引用均不能绑定。
- 重叠chunk覆盖同一个全局位置不会制造重复来源；真正多个来源位置依然拒绝，需要更明确的原文quote。
- 位置声明为PROGRAM_EXACT_UNIQUE_SOURCE_MATCH / model_supplied_offset=false，不伪称模型算对。
- 引用位置不证明事实蕴含；词汇、typed关系、OWL/SHACL、空修复及审核边界不取消。
- 网络错误重试不用于语义问题；预算/修复次数不增加。原空修复回归和新模式空修复回归都须FAILED。

这属于研究方法的显式新输入输出模式，不是对旧模型答案做后处理美化。
DirectGeneralLLM/DirectBudgetControl不要求引用；DirectRetrievalContext仍是一次直接控制，
不会被宣称有程序引用绑定。CQs-only不造ABox或无意义的引用动作。

新测试覆盖原模式不变、每行事实保真、typed一一绑定、模型offset字段拒绝、Unicode、重叠窗口、
歧义/虚构/源漂移/跨窗口拒绝、原编译往返、两种消融引用门和空修复拒绝。
Prompt目录从源码重生成，声明实际动态Schema，不能从当前模式倒造历史消息。
新r7luna及真实执行结果写runtime_reports/full-luna-20260921/quote-coupling-*。
完整分数、提升及CI尚未产生；不能用本次工程验证替代全量研究结论。

本轮核对[OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)：
JSON mode只保证JSON格式，不保证Schema/内容正确。当前网关仍按实际json_object模式记录，
未假称服务端严格Schema已验证；本地校验和来源门继续真实执行。
