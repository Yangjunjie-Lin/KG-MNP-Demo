# r3 pilot上下文预算拒绝：无损去重，不放宽预算

心跳检查发现r3luna已暂停：smoke9成功，pilot17成功、1失败，full仍99501 pending。
失败为Reuse/TwoAgentKernelV1的CONTEXT_TOKEN_UPPER_BOUND_EXCEEDED，model_calls=0；
并非API失败，也不是低分结果，不走网络重试。

## 真实原因

失败首轮输入有31张卡片，cards占7631字节；检索结果再次携带相同完整卡片，retrieval占12906字节。
加上任务、动态Schema及既定输出预留，保守请求估计35921，超过既有32768门。
原失败、全部请求/产物和账目保存在r3；after-r3-context-failure快照重读26份成功产物。
生成模型没有看到gold，本次分析只看public输入及请求大小，不读取full答案或质量成绩。

## 修复内容

新增研究侧prompt_views：完整卡片目录用columns/rows/shared_fields表示；
每条检索命中以card_index引用原目录，公共method/sources/vector_score提取一次。
后续reuse引用以existing_card_index引用同一原IRI，term/decision/reason仍完整保留。
每次调用的上下文自包含，执行解码回验；原始检索和复用对象仍留在审计中。
没有生成新的原生标识、裁剪卡片/文本、截断回答、修改选择Schema枚举、增加调用或降低校验门。
NoRetrieval仍提供空检索，不通过补目录取消其消融。B0/Bbudget直接输入路径不改变。

这些数字引用只是本次请求的序列化方式，不是模型应返回的新IRI；首轮existing_iri仍必须
满足原完整枚举和既有引用校验。压缩后的GUIDE/动态构造从源码进入Prompt MD/JSON，旧请求不改写。

## 离线预检

原24000字符、32768上下文及全部预算不变。
对237个已有pilot候选和2252个full Reuse的**首轮合法public请求**逐项解码回验，
改后最大保守预留分别24031、27257，超限数均0；未调用模型，未访问scoring/gold。
这不证明后续动态模型输出永不超限，后续门仍真实执行并保留失败。

旧请求视图相等断言改为解码后逐项完全相等，验证信息保真而不是跳过或放宽旧测试。
新测试覆盖可逆元数据、不同打分/方法、非法引用、目录冲突、缺省字段与null区分、
NoRetrieval边界、39卡片规模及同源GUIDE；实际结果记录在runtime_reports/full-luna-20260921/。

代码改动在新版本r4luna中重新冻结/预检，不能修改r3冻结Worker或将r3数据冒充r4结果。
总预算与LunaFull20260921授权保持不变，旧费用/失败都留存。
正式全量分数尚未产生，不能以本次无模型预检或工程测试称实验完成。
