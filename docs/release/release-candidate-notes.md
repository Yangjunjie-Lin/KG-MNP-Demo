# 实施检查点 — NO_GO_REFACTOR_INCOMPLETE

这不是完整重构结束，也不是已经通过最终验收的发行候选。没有成功候选 Tag、公共 Release、生产部署或 main 合并。

## 修订与证据

- Source：9da17d126cb37166ff06084080770108da20afbe。
- 目标分支：codex/toolchain-final-consolidation-p09。
- 本检查点代码：dfcfa8ce3a0a9b4ed2f5017df2371eaf81cfff41。
- 最终 tested_commit：尚未建立。旧 3c0d0ad 全量通过仍在 final-verification.json 中作为历史检查点保留，不能认证后续代码。
- 当前产品 0.9.0.dev0；编译器 0.5.1；快照/策略新增 1.1.0 契约；原 115 Schema 原字节和 ID 保留，当前 Catalog 117 项。

## G0–G6

| 门 | 实际结果 |
| --- | --- |
| G0 | 固定源 SHA、1498 文件历史树、Tag 与祖先关系已核验 |
| G1 | 实际上传/Source/Batch/Worker/KG-IR/Evidence/原文下载，含权限、fencing、幂等和骤停恢复测试 |
| G2 | 明确 Scope/CQ、候选、逐项审核、修订与确认、实际语义编译 |
| G3 | 真实 Diff/Impact/九类回归与消费者契约、后续发布、独立审核的 CAS 激活和历史回滚 |
| G4 | Minimal、Forestry、MNP 的增量真实浏览器流程已通过；不是当前最终修订全量认证 |
| G5 | 旧 UI/CLI、根 MNP 发布流水线/showcase、重复 ApplicationService、旧写盘器/转发器已退役；共享当前事务与已验证字节读取。剩余旧状态存储/控制器及脚本仍需收敛 |
| G6 | 尚未执行最终固定修订完整验收与新发行包全平台干净安装 |

## 已完成的可复现增量

原 53 项操作作为追踪基线保留，新增操作另列；接口或 handler 数量不视为完成证明。完整映射见 final-requirements.json，状态均标明尚未完成最终同修订验证。

核心提交在隔离完整 Workspace 中计算，使用凭证锁、JobStore fencing、项目 CAS 和原子提交回执。真实进程退出覆盖提交前后；原凭证撤销、取消、失效租约和旧 Worker 不能发布未提交工件。恢复入口覆盖 API、SDK、CLI 和任务中心，不重放不确定外部副作用。

审核身份与角色来自服务端。生产发布要求五类角色覆盖及两位独立审核人；后续拒绝会撤销旧批准的计数。候选修改重新生成 ID 并重验；Scope 和 Review 均有修订冲突检查。

实际回归包括 Package、Candidate CQ、Base CQ、Diff、依赖、Impact、Provenance、Release metadata 和映射，以及当前消费者契约。它执行真正的查询/Oracle，不以文件存在或布尔字典替代正确性。

## 领域与浏览器

- 最新完整浏览器复验固定于 c77c6555d5b555eea639fc8f2258043e5c096b21：5 场景全部通过，约 32.9 分钟；不是后续源码的最终验收。
- Minimal：完整真实流程、第二版本、发布、两次激活与指定历史回滚通过，377.9 秒。
- Forestry 0.2.0 EXPERIMENTAL：6 树、6 巡查、2 地点，83 项逐项审核；真实验证、发布、6 条实例、Evidence 回溯和下载字节核对通过，808.8 秒。
- MNP 1.0.0：原 84 资产不变；非空合成 MappingRecord 经过相同 API/UI/核心，实际查询和来源下载通过，758.1 秒。
- 任意名称第四包、错误凭证/CSRF/Origin/身份切换隔离、自动键盘与可访问性检查通过。

日志、JUnit、实际截图、工件 ID、下载包及摘要位于 runtime/p09-browser-c77c655-src/runtime_logs/p09/browser-runs/managed-9ed49be445e9478bb4411c5684976267。测试服务/Worker 正常结束，临时凭证已撤销并删除。上述壁钟耗时包含同期本地诊断工作，不是隔离性能基准。后续验证字节快照安全修复尚需最终修订完整复验。

原始失败未改写：Forestry 初期 HTTP/等待失败，后续 15 秒对象查询等待不足；MNP 编译/导入等待及 20 秒下载等待不足；Minimal 曾点击旧提案，被后端 CAS 正确拒绝。分别定位、修复并复测。下载/完整校验可能需数十秒，不承诺未测量的性能 SLA。

组件容量在实际 Chromium 中测量：1000 表格记录保持分页，图限制 200 节点/400 边；单次首屏两帧测量约 197.7 ms，机器 i7-12700H/约 34 GB 内存/Windows。它不是业务吞吐提升百分比。实际截图已查看；交互式登录键盘焦点和空输入中文错误提示另行查看，未冒充人工用户研究。

## 实际退役和保留

已删除 web/workbench、web/diagnostics、web/governance 的 9 个 HTML/JS/CSS 文件；旧 URL 返回 410。没有 iframe 或 archive/legacy 备份。

约 1550 行旧本地建模/审核/生命周期 CLI 分发被同一认证 ApplicationService 入口替换。旧 application/workbench/diagnostics/governance/amendment/activation 根 CLI 返回退役提示，未知参数不再回落旧建模入口。旧调用者指定角色与 zero Prompt digest 行为不作为兼容保证。

重复整树冻结测试归并为固定 Git 历史审计；MNP 查询资产摘要单独保留。旧 UI 安全断言迁移到真实 React 与 API，11 类 XSS 字符串全部保留，历史格式篡改断言未删除。精确路径/节点映射见 final-retirement-ledger.json。

本轮还删除了旧 compilation 强制覆盖写入器、旧包构建器的 output_dir/force 分支、旧 workbench 转发器和 HTML 打包写入入口、根 MNP pipeline/showcase/export 及 AssessmentService 的持久化分支。23 个转发安全案例迁到当前 API，旧 MNP 规则/证据/双重 SHACL/时间版本测试直接运行内存评估。第二个 ApplicationService 改为无网络的有界历史查询结果读取器，十组原黄金查询结果摘要保持。

当前建模、解析、编译复用目录提交步骤，改用独占暂存区；失败不删除别人的目标或上次暂存内容，进入编译事务失败时释放锁。本轮还用真实包复现了对象、元数据和可视化“先验证后读取被替换字节”的问题，现统一读取刚捕获并验证的同一份字节，且不缓存验证结论。

旧后端 application/workbench/diagnostics/governance/amendment/activation/compilation 及部分 graphdb/webvowl/旧 modeling 实现仍存在。它们还需按真实调用者和版本化只读兼容需求合并/删除，不能将当前首批退役宣称为 REFACTOR_COMPLETE。

## 版本与兼容

新增编译器 0.5.1 快照/策略契约不更改原 Schema。旧 0.5.0 真实合成 Package 冻结为兼容样本：

- SHA256：4e6ba7225348a201c1ba2076e58f3c1bff370a97dae7000e99ebe53f9be3f983。
- 76928 字节；原包 payload 在导出前后相同。
- 新 reader 验证通过；不修改旧包后重算 Hash。

## 测试与发行状态

当前检查点分别记录了 UI/兼容/安全 169 项、CLI 9 项、版本契约 16 项、真实编译 5 项、前端 14 项等通过结果。它们不是同一最终冻结修订的累计全绿。

新 CI 分为 quality/backend/workbench/security/release-check，完整后端集合不递归重复历史 aggregate。配置解析和本地命令验证不等于远端 CI 成功。

Python 依赖按已知公告作必要升级，并在独立环境验证；保留 httpx/anyio/rdflib deprecation 信息。新完整 Wheel/Sdist 干净安装、Linux 验证、最终 collection/分区、浏览器 0.5.1、证据提交源码一致性和交付包摘要仍需最终执行。

## 明确剩余项

1. 完成旧后端重复权威、脚本和历史文档的实际收敛及逐项测试迁移。
2. 补全最终验证入口的前端、平台、安装、恢复、文档命令和交付包步骤。
3. 在新 CODE_FREEZE 上完整执行所有必需门，不能复用旧修订补齐。
4. 形成完整证据包、tested/delivery 修订一致性证明和远端状态核验。
5. 只有全部必需门通过，才考虑候选 Tag。

GraphDB live 与外部业务执行器未配置，单列可选外部阻断；不能用来掩盖上述本地未完成项。没有 Live LLM/OCR/ASR、真实林业试点、外部 exactly-once 或生产安全认证声明。

## 最新诊断检查点与修复

95b4d50f1f66a27e15d245facec43061cc0f2d73 的完整后端集合为 1703 个唯一节点：1689 通过、5 失败、9 跳过，无缺项/额外节点。四项失败为旧 Forestry 版本/空包/Lock 冻结断言，另一项暴露解析流程接受伪造 confirmed 文件；均在之后的针对性修复中保留或增强断言，不把补测拼成新修订全绿。

同检查点浏览器为 1 通过、4 失败：新增测试管理线程读取 stdin 阻塞了 Windows 验证子进程，后续 Source 任务排队。已复现并改用独立停止标记，真实 SHACL 子进程正反例的启动测试通过；未扩大业务等待时间。feba20f 固定副本的浏览器链路已结束：2 通过、3 失败。Minimal 后续导入选中了旧按钮；Forestry 新 checkout 出现 CRLF 锁失配；MNP 同请求重复验包导致下载超时。明确工件绑定、行尾规则和下载路径修复后，c77c655 的五个完整浏览器场景全部通过；原失败记录仍保留。

Windows 与 Linux 各两套新环境的预构建 Wheel / Sdist 重建 Wheel 安装检查通过，但它们来自较早的脏树预检，不能认证最新交付包。Linux 安全/兼容子集为 184 通过、1 个旧 Forestry Lock 断言失败、0 跳过；首次运行缺少 pytest basetemp 父目录的 97 个 setup error 单独保留，新的 backend 入口已改为唯一且有明确父目录的运行目录。

已进一步删除旧 HTTP/CLI 启动器、阶段报告和重复架构图、14 个空测试目录说明、旧 Catalog/Pack 迁移写入脚本；长期语义决策归并至当前架构和迁移摘要，原 53 操作改读固定 P8 Git 对象。原 Schema、领域资产、License 和有效历史包未随清理删除。剩余旧内部实现和最终固定修订全平台验收仍未完成。

最新归档读取只验证捕获副本一次，输出完全相同的已验证字节，返回前重验权限；不缓存旧权限或验包结论。6 项归档/历史包/撤销回归通过；真实旧 MNP 包读取为 1,597,671 字节、43.65 秒，独立 .kgop 校验 VALID。它不是新的最终完整流程或交付包验收。旧阶段 golden 写入脚本也已退役，原 golden 文件及8项重建/确定性测试保留并通过。

最新增量另有当前事务/提交恢复46项、MNP语义迁移56项、转发安全迁移37项通过；旧包重建首次219项中204通过/15失败，漏改的 output_dir=None 调用修正后相关24项复验通过。新快照负例先复现4项失败，修复后对象/历史包7项、元数据与HTTP边界44项、归档/撤销5项分别通过。Linux固定 a23102d 副本的事务/路径/兼容子集57通过、0跳过；它复用了准备好的锁定虚拟环境，不是新安装或完整Linux集合。这些重叠、跨增量结果不累计成全量通过，最终 tested_commit 仍未建立。
