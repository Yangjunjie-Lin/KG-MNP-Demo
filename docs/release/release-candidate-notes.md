# KG-MNP Ontology Toolchain 0.9.0rc2 验收与交付

Final Decision：`GO_RELEASE_CANDIDATE_WITH_OPTIONAL_EXTERNAL_BLOCKERS`。

## 修订与事实边界

- Source：`9da17d126cb37166ff06084080770108da20afbe`。
- Tested code freeze：`7075a4308de655ce1bf1e8073a005aeee152bf0f`。
- Branch：`codex/toolchain-final-consolidation-p09`。
- 本次实现提交：`352f1bd42631546b417ec2804383dbb84f232b87`；精化证据坐标与 Excel 类型处理：`7075a4308de655ce1bf1e8073a005aeee152bf0f`。
- Delivery 是仅修改四份正式证据文件的后续提交 E。完整 delivery SHA、remote SHA、精确源树一致性和候选 Tag 由交付目录的 detached receipts 记录，避免提交包含自己的 Hash。
- 原 RC1 标签保持不变；历史报告可从 `80fede0c63a9b99d1ec291545cbd3565cf1ef177` 读取，不把旧结果计入本轮。

## 本轮实际关闭的能力

TXT 行、DOCX 段落/多表、XLSX 多工作表与 CSV 可以通过同一批次进入真实 Source→KG-IR→Evidence→范围/CQ→候选→人工审核→确认→编译→本体包→本地发布。Word 表格号和工作表名不再丢失；不同文件/表格的相同行号及 JSON 数组的不同记录不再坍缩为同一个默认对象。

V2 映射显式选择锁定基线类、数据属性、业务身份空间/主键、别名及跨来源关系。相同规范身份与相同事实合并来源；矛盾值不会最后写入覆盖。支持受控数字/布尔/日期类型及 Excel 原生日期表示，稀疏普通字面值按 OMIT 省略，不猜时区、不截断非零时间。

文本模板是有界固定文字与槽，不是用户正则或通用 NLP。无法匹配的段落可以选择证据片段。偏移明确是规范化 KG-IR Unicode 码点，保留原始观察和转换引用。漏映射条目必须处理或明确给出范围排除理由，不能直接确认。

规则通过已有 PluginSnapshot 配置摘要绑定到 Provider Request，并在候选 provenance 中保留摘要；快照覆盖实际实现而不只覆盖重导出入口。确认前重验配置、快照与源覆盖。客户端不能声明审核角色；服务账户不能人工批准；审核/CAS/fencing/幂等及编译边界未被绕过。

工作台增加的是现有 React 表单与来源/身份核对视图，不是第二套前端或任意 JSON 命令面板。使用说明：`docs/user-guide/mixed-source-modeling.md`。

## G0–G6 和操作映射

| 门 | 实际结果 |
| --- | --- |
| G0 | PASS：Original fixed P8 remains ancestor; RC1 tag/branches preserved; clean7075source freeze and exact collections |
| G1 | PASS：Real upload/parser/KG-IR/evidence for mixed TXT, DOCX paragraphs/tables and XLSX sheets; coordinate/source boundary regressions |
| G2 | PASS：Explicit class/key/alias/typed-field/reference/text mapping, snapshot-bound requests, human review, tamper/coverage/conflict gates and actual semantic compilation |
| G3 | PASS：Local registry/release, semantic diff/impact/regression, explicit historical rollback, object query and source trace; no external-deployment claim |
| G4 | PASS：Single Chinese Workbench; six real browser scenarios per platform plus independent text-span/keyboard/viewport inspection |
| G5 | PASS：Original retirement ledger retained/revalidated; no duplicate runtime or UI introduced; original contracts/assets and semantic-kernel files unchanged |
| G6 | PASS：Accepted same7075 full1808collection on both platforms, whole-cohort retry provenance, all6Browser each, clean installs, identical delivery artifact cross-platform installation, exact evidence-only delivery protocol |

原 53 操作及后来增加的资源操作继续完整保留在 `docs/verification/final-requirements.json`，包含旧状态、当前实现、API、SDK、CLI、UI、正负测试与修订。没有删除缺失行来制造覆盖率。本轮复用 modeling.prepare/proposal/review/compile 原有入口，未新增第二套权威。

## 固定修订验证

| 平台/门 | 结果 |
| --- | --- |
| Windows 后端 | 1800 passed / 8 platform skipped / 0 failed / 0 errors；唯一1808节点 |
| Linux 后端 | 1808 passed / 0 skipped / 0 failed / 0 errors；唯一1808节点 |
| 前端 | 两端 lint/type/build 通过；各27单元测试通过 |
| 真实浏览器 | 每端6场景全部通过：任意包、混合资料、Minimal及回滚、Forestry、MNP、安全隔离 |
| 安装 | 两平台各自Wheel/Sdist干净安装；选定的同一Linux交付文件又在Windows安装验证 |
| 额外检查 | 原契约/资产、源码卫生、2组件容量测试、独立键盘/视觉、公开依赖公告50pins及npm审计 |

Windows 原完整并行分区曾在启动就绪等待失败，之后是整个1301节点分区顺序重跑，并与同7075的完整507节点串行分区核对并集。不是替换一个失败用例。Linux 原浏览器5通过1等待失败，之后整套6场景重跑通过，不是合并单独场景。原始失败、命令、exit code、JUnit、nodeids与摘要都保留。

详细源树、collection、partition、环境/版本、每条命令、跳过原因、警告、文件摘要与接受依据见 `docs/verification/final-verification.json` 及证据包。只在同一7075修订内组合完整分区；不使用旧修订累计通过数。

## 领域与真实工件

- Minimal0.1.0：非空完整链路，两个真实编译版本、Diff/Impact/Regression、发布、明确历史回滚。
- Forestry0.2.0 EXPERIMENTAL：6树/6巡查/2地点，合成数据，实际关系查询与原文追溯；旧0.1.0不静默替换。
- MNP1.0.0：非空合成MappingRecord，全链路及包内验证/对象追溯；原84资产保持，不声称真实携号转网生产部署。
- Mixed：TXT、DOCX段落/表格、XLSX两表共5记录，显式别名后输出2实体，来源发生次数3/2；相同行号的不同对象保持不同。
- 临时第四包：任意名称项目/UI通用性检查，不冒充另一套完整行业试点。

### mixed

- project_id：`urn:kg-mnp:project:14e27e40d74d70b93832bac4559402ddef8fc3ad5fce8d5dc40372b68c0f8842`。
- source_id：`urn:kg-mnp:source:f057ab8fc62cf637b195cadcc8fda4f67590270440ffe7f3642877c86416a34a`。
- run_id：`urn:kg-mnp:ingestion-run:0d4abce1c1c2f78bc5da9d5f360c44d23e4bb6c39831f51470a06a5f1b9e2706`。
- scope_id：`urn:kg-mnp:ontology-scope:1571700605110276ac304e0e4c4e81df53dd7a561a5911bed5ff1496b3327c8c`。
- proposal_id：`urn:kg-mnp:ontology-modeling-proposal:1e82c8a0fb6c04327c7ced985ce03b680dcbf6d9a4c225bc01fb37d21e40f819`。
- review_id：`urn:kg-mnp:ontology-review-queue:58f98f4dfc2376287a30fbdf74d9dff7c56913407c4dfc60734bcda42e2fd0ac`。
- package_id：`urn:kg-mnp:ontology-package:f7297c5eb23979727205969419380144f38cee27211ec3ba6b16a532916c771f`。
- release_id：`urn:kg-mnp:release:87d0cd65a1f9963b7ea916266c62459c1b50e24708766373de8ca211980e5ea6`。

### mnp

- project_id：`urn:kg-mnp:project:0fef9631791bc5c722f1515ab596f30119da872593d3d9f9962f4ca187ea1249`。
- source_id：`urn:kg-mnp:source:e1a1ab7efe1facd155bce8a4a689cac0f11d545f0c19d7aff441182489eb87f3`。
- run_id：`urn:kg-mnp:ingestion-run:b4eb4caf0574de4d99050fe0804b2c8931fd5a1620a4c315dc508f99bae01617`。
- scope_id：`urn:kg-mnp:ontology-scope:3dcf1089d9b96a4cb0a4e02e50f270831592b83a4179183b6dc7b8bc27af1532`。
- proposal_id：`urn:kg-mnp:ontology-modeling-proposal:78bf546d34f815fc613127b588fec7ca54c613335fd75de3bd811379ade05805`。
- review_id：`urn:kg-mnp:ontology-review-queue:5eaeeb58bbca426e39c7724f0cdfc475a52dfb5f25ec958fcf5cc0a75adad471`。
- package_id：`urn:kg-mnp:ontology-package:57342f0f553a865e25c0af4fba3a4f8e68c34def76641b0c7ea0cbba08e2b897`。
- release_id：`urn:kg-mnp:release:eb23e5903d18e29cb2c5203619e61ecf852fbbee046ff08429699bdcb353d847`。

### forestry

- project_id：`urn:kg-mnp:project:3c4209152760752d04357f006e772ef55a84c0dcd22158d71e7d2bc5d2279882`。
- source_id：`urn:kg-mnp:source:d390bf268ec4e4fcc0c6963adae20c80486535c037e68f0d4b2dcbab25e476e5`。
- run_id：`urn:kg-mnp:ingestion-run:9f6fc8cd535a8a9ac5e01eb111980e9419af707678b488d64d239912bca6e63e`。
- scope_id：`urn:kg-mnp:ontology-scope:a5a9436b21eb28160dd395c9fc87477f93f1e61a784162795ac6cd3174b9bf58`。
- proposal_id：`urn:kg-mnp:ontology-modeling-proposal:55957e42f52bfb93888303484c9fe7a28558960bb4ea5d66a9ec30f5898cab59`。
- review_id：`urn:kg-mnp:ontology-review-queue:3fe7915307f01d61298be5ffb7bc9c9f61881cb06f24e91f9af1c72ec8e70b75`。
- package_id：`urn:kg-mnp:ontology-package:dfc829211057569361480b6c0c3215c752c7ebd44331a96f6b724318971c7b93`。
- release_id：`urn:kg-mnp:release:39e186a1d333bb02e88ca4e5c283a5577c25b58381f689ad38c3401b24b94a8c`。

### minimal

- project_id：`urn:kg-mnp:project:c13a2b9c25528873f03ceaa1be3575a07cc7dc003ae0c2ca8b78d6ea5ffc9381`。
- source_id：`urn:kg-mnp:source:a6b96e697f242db622efb316e435372f68ce9881611213756e7736b9b406cbb6`。
- run_id：`urn:kg-mnp:ingestion-run:61aa3f574f91a2207b147ada8ea3c0cf22bf9a92bee9c5a7cf2907b083e3b125`。
- scope_id：`urn:kg-mnp:ontology-scope:456d42dfc4ed6961973592ced646d23e8135893998b7da2a20772c2dbb0e671f`。
- proposal_id：`urn:kg-mnp:ontology-modeling-proposal:e195ad27feeddc57dba4ef818e7f4eadb2ee247b55b5a312d31b650696305ba5`。
- review_id：`urn:kg-mnp:ontology-review-queue:85b946d5229af3630e33f385a5f689a8454b95249578074af2627d634ec60c7e`。
- package_id：`urn:kg-mnp:ontology-package:df3012f249b7b2bd2359dc0cc933fc708e91721985868c0251e034054639e9c0`。
- release_id：`urn:kg-mnp:release:2b0c7c8294da822aa0dfcf2d9d78faa35fdb888c9e4f139d477a321bd25613f2`。

## 工程、安全、清理与研究声明

上传限制实际字节、受权下载、短期HttpOnly会话、CSRF/Origin、身份切换、权限撤销、fencing、CAS、幂等与任务恢复继续由原统一服务实现并在全量集合重验。环境指针仅是CONTROL_PLANE_SELECTED，Outbox仅是REQUEST_ENQUEUED；不声称外部副作用exactly-once。

原115Schema字节/$id和当前117目录项保持；Minimal、MNP84及语义编译器文件相对受测RC1无变更，Compiler仍0.5.1。V1记录映射和历史有效Package保持可验证。旧三套UI、重复写入口、文档/测试迁移的完整历史台账保留于 `docs/migration/final-retirement-ledger.json`，本轮未复制旧实现或新建平行registry/framework。文件/测试数量仅报告范围，不当作质量指标。

实际图表容量测试使用1000表格条目、200节点/400边；本机一次首屏测量约122.7ms。独立键盘操作、自动axe扫描和实际截图复核分别记录。只读文本的Home/Arrow诊断存在浏览器原生控件一致的行为差异；实际词选区+ShiftArrow已成功形成精确标注。不宣称穷尽所有辅助技术或浏览器。

研究主线仍是契约化通用工具链、证据绑定KG-IR、候选/人工审核/确定性编译分权、语义差异/回归/受控生命周期。工程机制不等于学术新颖性已证明，hash不等于内容真实，一致性与CQ通过不等于所有业务知识正确。

## 交付文件与命令

- `kg_mnp_toolchain-0.9.0rc2-py3-none-any.whl`：1085637 bytes；SHA256 `63aa3b476ab055856e7698431ac32657523e6727783eec70c1ced351efcceb4d`。
- `kg_mnp_toolchain-0.9.0rc2.tar.gz`：899024 bytes；SHA256 `cc920bfb452df7b0c8c848eea3d4b847ab843b0dd0ababf1ea61c82a0b722515`。
- `toolchain-examples.zip`：109656 bytes；SHA256 `9d9687cbf410f21d3755291e8897ba7dd9f22cdea6d346be97ed79b9f8c921e6`。
- 验收证据：`p09-0.9.0rc2-evidence.zip`，20476300 bytes、799 entries，SHA256 `bde0b93aa7d7491adba16ec6999df64219b70a253e640e509233b2d3d392ab92`；CRC和限定秘密信息扫描通过。

交付目录为 `runtime_logs/p09/delivery-7075a43`。安装包含构建的唯一Workbench静态资源；examples为独立领域包/示例。原始Workspace、JobDB、Token/Session、用户资料不进入Git或发行包。

PowerShell/POSIX启动及可选文档依赖见README和用户指南；Web/Worker必须使用同一配置。实际干净安装检查了无源码Contract/Policy读取、SPA深链刷新、API401/404、受权下载、独立Worker、重启/幂等恢复及缺Reasoner诚实阻断。

复核入口：`python tools/verify_candidate.py`；本轮接受的完整分区/浏览器重跑命令另在证据中精确记录。源码、测试与构建输入若变化，必须建立新修订并重新验收。

## 外部阻断与限制

- TXT/DOCX/XLSX/CSV mixed-source workflow is offline, explicitly mapped and human-reviewed; not arbitrary natural-language understanding or globally optimal/redundancy-free ontology induction
- No live LLM/OCR/ASR/Vision or automatic approval; DOCX/XLSX optional parsing dependencies required, not legacy DOC/XLS
- First-row unique table headers; business identity uses explicit space/key/aliases; no implicit cross-version/global entity resolution
- Text spans address normalized KG-IR Unicode codepoints, not original byte offsets; original observations and transformations remain traceable
- Coverage is item-level, not proof every sentence is understood; contradictory values require human treatment
- OWL consistency, SHACL conformance and CQ success cover only actually executed constraints and query/oracles; they do not prove source truth, all-domain suitability or academic novelty
- Synthetic Forestry EXPERIMENTAL and MNP fixtures are not field trials or production business execution
- Read-only query preparation and copy-on-write workspace work can be slow under contention; recorded timing failures and complete-cohort reruns are retained; no general latency guarantee
- Chromium-only browser verification; explicit visual/keyboard scope, not exhaustive accessibility or production-security certification
- GraphDB live and external executors remain unconfigured; pointer selection and queued outbox entries do not imply external deployment
- Deprecation warnings and platform skips are retained; no warning-free claim

本地必需能力无剩余未完成项。外部GraphDB live和业务执行器未配置、未实际部署；它们是单列可选阻断，不用于掩盖本地功能或测试缺口。最终候选Tag只能在正常推送和detached交付一致性验证后创建；不覆盖RC1、不合并main、不创建公共Release。
