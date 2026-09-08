# KG-MNP Ontology Toolchain 0.9.0rc1 验收记录

Final Decision：GO_RELEASE_CANDIDATE_WITH_OPTIONAL_EXTERNAL_BLOCKERS。

## 修订与交付边界

- Source：9da17d126cb37166ff06084080770108da20afbe。
- Tested code freeze：b63ba379327af4eb102d4a852498509cef9a3bf8。
- 分支：codex/toolchain-final-consolidation-p09。
- Delivery：只包含四个精简证据文件的后续提交。其完整 SHA、远端 SHA 和与受测源码的一致性由交付目录中的 detached delivery-receipt.json 记录，避免提交自引用自己的 Hash。
- 主源码、配置、测试、构建输入仅排除四个明确列名的证据文件；不会以整个目录作为排除项。Wheel/Sdist 内容不包含这四个文件，实际交付工件字节与已安装验证的工件相同。
- 不创建公共 Release、不部署生产、不合并 main、不改写 P1–P8 或已有 Tag。

## G0–G6 与原操作清单

| 门 | 结果 | 实际内容 |
| --- | --- | --- |
| G0 | PASS | 固定 P8、祖先、历史 Tag 与受保护快照实际核验 |
| G1 | PASS | 真实上传、Source/KG-IR/Evidence、受权下载与提交 fencing |
| G2 | PASS | 范围/CQ、候选逐项审核、确认与真实语义编译 |
| G3 | PASS | 注册、语义差异/回归、独立发布审核和 CAS 历史回滚 |
| G4 | PASS | 唯一中文工作台及三领域完整流程、第四包、会话/视觉/键盘 |
| G5 | PASS | 旧可写平台/网页/脚本退役，契约/资产保护，测试迁移与当前文档 |
| G6 | PASS | 同修订 Win/Linux 全量、双平台 Browser、发行安装及同字节交叉验证 |

原 53 项操作全部保留在 final-requirements.json，连同原状态、当前类型契约、实现、资源 API、SDK/CLI、界面和正负测试映射。新增的 14 项操作另列。操作或 Schema 数量不作为完成依据。

CQ / Baseline / Alignment 合并到 modeling.prepare；candidate 合并到 proposal；compile.validate 使用同一真实验包路径；reproduce 委派现有 SemanticCompiler.reproduce，不声称有不存在的独立 GUI 按钮。SDK 与 CLI 使用同一 ApplicationService 或相同应用层函数，不通过解析 CLI stdout 伪造服务。

## 真实主链路、安全与恢复

上传以实际接收字节限制、项目与凭证授权、受控暂存区和后端摘要生成 Source / Batch。格式、Provider 缺失、仅元数据、REVIEW_REQUIRED 与失败分开处理。KG-IR、原始观察、Locator、转换记录和下载具有实际 Source Blob 闭合证据。

Worker 在隔离完整 Workspace 内计算，提交通过凭证重验、共享提交锁、租约 fencing、项目 CAS 和原子回执。进程骤停、租约丢失、双进程争抢、执行中撤销、回执丢失、重启和幂等重放均有真实测试；不会把 JobStore.complete 拦截当作完整提交保护。取消请求不是撤销已提交结果；未知外部副作用不自动重放。

候选只是提案；身份、角色和 quorum 来自服务器，服务账户不能人工批准。修改产生新的候选 ID 并重验。未审核、错误 Oracle、缺少角色、篡改 Evidence/Package、过期 CAS 与跨项目访问均有失败路径。生产策略与显式 loopback 单人开发策略分开验证。

OWL / HermiT、SHACL、CQ / Oracle、Provenance 与 Package 校验来自实际运行。版本流程通过正式编译生成两个包，执行解析后的语义 Diff、Impact 和实际 Candidate/Base 回归，再分别审核发布、激活并回滚到指定历史 Release；不编辑 .kgop，不把清空 Pointer 当回滚。

## 工作台与跨领域分级

一个中文 React / TypeScript / Vite 工作台、一个 Router 和一套服务端状态管理。真实表单覆盖项目、资料证据、Scope/CQ、候选审核、编译发布、差异环境、对象和集成、任务。原始 JSON 仅作为类型化工件的必要展示，不代替全部交互。

总览显示真实批次、Proposal、审核队列、确认包、编译与 Release ID，并重放待处理审核；候选树、图、表选择联动且有界。映射展示类型、歧义、null/missing 策略说明以及绑定到正确 Dataset/Run/Item 的原始样本。对象浏览按固定 Package/Release 展示语义摘要、术语分页、Typed Literal、属性关系与来源；版本切换丢弃晚到的旧查询结果。

| 领域 | Pack | 接入/证据 | 建模/审核 | 编译/Package | Release/Browser | 范围 |
| --- | --- | --- | --- | --- | --- | --- |
| Minimal 0.1.0 | PASS | PASS | PASS | PASS | PASS | 两平台完整非空流程与版本回滚 |
| Forestry 0.2.0 | PASS | PASS | PASS | PASS | PASS | 合成 EXPERIMENTAL；6 树/6 巡查/2 地点，关系查询与原文定位 |
| MNP 1.0.0 | PASS | PASS | PASS | PASS | PASS | 非空合成 MappingRecord，原84资产不变 |
| 临时第四包 | PASS | 不作为该测试范围 | 不作为该测试范围 | 不作为该测试范围 | Project/UI PASS | 任意 Pack ID 不依赖前端硬编码 |

Forestry 旧 0.1.0 的 digest 是 58dbf2ab75189ecefdaf79e6c5e49ae7c796471e9be65aa48cbf0e21a21d66e9；唯一授权升级为 0.2.0 EXPERIMENTAL，6 树、6 巡查、2 地点，全部合成。新 content digest 为 c9c0d502aa9476cd35eb929f7abf90c3d65887a8ed25c88b1fca18760a479387；Lock 为 urn:kg-mnp:domain-pack-lock:c53e0af34a632f56df94ea25e0ceab9573a0e941491a7e2cf5e8e0d25fee4dd1。旧版本请求明确不可用，不静默替换。

MNP 是非空、有证据的合成 MappingRecord 兼容实例，不冒充完整携号转网业务部署；原 84 个领域资产和约束保持。第四包验证的是任意名称的 Pack / Project / UI 接通，不把它列为另一套完整行业业务试点。

以下列出 Windows 真实场景的主要标识；两平台完整标识与 Job 列表均在 final-verification.json 和原始 ids.json。

### minimal

- Project：urn:kg-mnp:project:d1c973237328a17304b05202068ff08b60e87e30ff24d322375ab8499b112370。
- Source：urn:kg-mnp:source:a6b96e697f242db622efb316e435372f68ce9881611213756e7736b9b406cbb6。
- KG-IR：urn:kg-mnp:kg-ir-dataset:4c2f1fa5f854ba3e3395cc718fee0998bb05ccd6eab2eb4f4e13fc62bbb65cf7。
- IngestionRun：urn:kg-mnp:ingestion-run:8cbc9b899049d2006ee700907ff1529f5f96e7581351aa92cd0d73d68d0a5577。
- Proposal：urn:kg-mnp:ontology-modeling-proposal:1ecc6ff55b95ec495816fbab6925a6520f6cfd6a826f7a62f690fefa78c3a256。
- Review：urn:kg-mnp:ontology-review-queue:e438532e37d524322f4864ca397d46385bc995b055d95faaedcf2cae80766222。
- Package：urn:kg-mnp:ontology-package:12a9493ccf28d1437880b84ef143b96b353e0ddd59dfed849fe18585a82a3fe5。
- Release：urn:kg-mnp:release:5ae2405115d30b958ee1d11c2e37eca50d484792c2411de6210f44666f943e9c。
- 首个 Job：job_20f717cef11d4b739a479a5994800f41。

### forestry

- Project：urn:kg-mnp:project:4d56a278294e9bf6573d3a237b7e280ed1c72b081c736e87f354eb6e0ec9a820。
- Source：urn:kg-mnp:source:d390bf268ec4e4fcc0c6963adae20c80486535c037e68f0d4b2dcbab25e476e5。
- KG-IR：urn:kg-mnp:kg-ir-dataset:ed24deb907ca3ce370e59d21e1dd27db9ee3922cb6c8e414948a8d68d9fc553e。
- IngestionRun：urn:kg-mnp:ingestion-run:84f5ab42aaee0c4e387bdb888bd4bfb4ab183e82d40b755f1f16e74389c4cd03。
- Proposal：urn:kg-mnp:ontology-modeling-proposal:4ac168c00b433bfbd93813d7f58a7abe1f2728f18ca773e439f958d0c2a1290e。
- Review：urn:kg-mnp:ontology-review-queue:a2019b94a513ad323bd790904feb389578103b066f7317c29af264bd6266edf8。
- Package：urn:kg-mnp:ontology-package:3f27d73f7f92751bf495974a7a8d2d6ba9bc40b910b3eef2266d809c24e22d7d。
- Release：urn:kg-mnp:release:a249b698dff2559d02bd21a360d10656138c1909faff901a7aa5ee3463d2bf89。
- 首个 Job：job_ea3fd1f6e9d248bdab4b6892f3172b8d。

### mnp

- Project：urn:kg-mnp:project:47f636f75fe65ad5fa9e5b85c931f781d75689b0ceac3754259b678a464883a3。
- Source：urn:kg-mnp:source:e1a1ab7efe1facd155bce8a4a689cac0f11d545f0c19d7aff441182489eb87f3。
- KG-IR：urn:kg-mnp:kg-ir-dataset:f0ee866188c1e25d62ab1cd5b881bb1c6fb0c40094ea9247738b3bc07fc643ef。
- IngestionRun：urn:kg-mnp:ingestion-run:ddd70a7f26aec2dadd141c0bce5d3ee8404f506e674602b985b7af21f29739d6。
- Proposal：urn:kg-mnp:ontology-modeling-proposal:54b6e4569e6023f90d4405898e31cfa1e7684ad4f75ce7799fa16d27b72632f0。
- Review：urn:kg-mnp:ontology-review-queue:7b92dbcb2400e2826e6004c5832ea8273f9cc052afe6872850eebf0290301788。
- Package：urn:kg-mnp:ontology-package:7c5c30dc42e0891680f1cd65e58bb90b5f53c9bca962e7c9361ad6497a26d77d。
- Release：urn:kg-mnp:release:60451c348e780327228793cc2742fdb8023d8b6df8e0419a3d6993b3d024edd9。
- 首个 Job：job_6531646780ed45f99c339cc1f7cab3e5。

## 实际退役与兼容

三套旧网页、独立旧 HTTP/CLI 控制面、GovernanceWorkspaceStore、ActivationStateStore、ActivationController、旧写盘器、旧 GraphDB 自动部署和 WebVOWL 服务器／代理／Node12 前端，以及一次性阶段资产/CQ/IRI/台账重写脚本已经实际退役。没有把整套旧平台搬到 archive/legacy/tests。

保留的是版本化 Schema、真实旧包与激活记录、只读重建和必要协议／转换工具。历史激活读取要求独立物理权威与外部信任锚，不运行旧可写控制器。Source、Workspace、Proposal/Review、Compiler、Registry、ApplicationService 与认证权威保持单一当前实现。精确路径、实际调用者、替代行为和原/新测试节点见 final-retirement-ledger.json。

原 115 个 Schema 的字节与 $id 独立核对，无差异；当前 Catalog 117 项。编译器 0.5.1 使用新增快照／策略 1.1.0 契约，不伪称旧 0.5.0 快照未变。真实旧 0.5.0 包 SHA256 为 4e6ba7225348a201c1ba2076e58f3c1bff370a97dae7000e99ebe53f9be3f983，原字节不变并通过历史读取兼容。

Minimal content digest 9243d8a995a4a87b8d2048bf7cb0069203e3d7d528e57409e6d3f985ac11e014、MNP content digest 2554d6d4bbd98b4defd2a46243d6f4f01842320bcc929aff0a3a03ba7cc6ddd1 保持。历史全树快照仅在固定 P8 Git 对象审计一次，不作为当前源码不许变化的质量门。

P8 整仓库 1687 文件，最终源码 1696 文件；相对 P8 为 528 个变更文件、24875 行新增、44634 行删除（证据提交前统计）。这些只是审计数据，不是质量分数。151 个逐路径退役记录、195 个测试迁移记录中，历史中间终点已扁平化到实际存在的最终测试，原权限／证据／篡改／并发／回滚保证未删除。

CI 按 quality、backend、workbench、security、release-check 能力分工；完整后端不递归执行历史 aggregate。这里引用的是实际本地 Windows 与 WSL Linux 运行，不把远端 CI 配置声称为已运行成功。

## 同修订测试、视觉和安装证据

| 平台 | 后端通过 | 失败/错误 | 跳过 | Browser | 前端 unit | Wheel/Sdist |
| --- | ---: | --- | ---: | --- | --- | --- |
| Windows | 1764 | 0 / 0 | 8 | 5 PASS | 24 PASS | 两个独立安装 PASS，另有同 Linux 工件的两个新环境 PASS |
| Linux / WSL Ubuntu24.04 | 1772 | 0 / 0 | 0 | 5 PASS | 24 PASS | 两个独立安装 PASS |

Collection digest：70a54ea5ac5da16a13f77c5e41ff9f502b8c72ef82e377ef160ece6501eb1daf。共同 Git 输入摘要：9d32656393ca26a77e2a2fe9d4196fa7778fc37c5cbea15188a269fd98524a87。Windows Python3.12.6/Node24.15.0/Java23.0.2，Linux Python3.12.3/Node24.18.0/Temurin17.0.20.1；Chromium均为153.0.8010.12。原始 checkout 字节摘要因LF/CRLF差异单列，不混同共同 Git 输入摘要。

唯一 pytest collection 为 1772 节点，关键串行分区 502，非重叠并行分区 1270；分区并集、实际执行并集与 collection 相等，没有缺项或额外节点。前端组件 Mock 测试与真实 Browser E2E 分开，不用 route.fulfill 替代核心接口。

Windows 的 8 项跳过是测试账户的 symlink 权限、POSIX FIFO 与执行位；这些节点在 Linux 实际执行通过。rdflib / httpx 等弃用警告、故意重复 ZIP entry 的负例警告和 NO_COLOR 提示保留在原日志，不伪称零 Warning。

实际 PNG 已逐张查看，覆盖项目/上传解析/证据/Scope-CQ/图树/映射/审核/验证/版本差异/回滚/Forestry/权限拒绝/GraphDB 阻断。自动 axe 与独立交互式键盘检查分别记录；键盘检查是代理辅助实际操作，不冒充真人可用性研究。1024、1366、1440、1920 宽度及焦点、草稿保持、任务刷新、身份切换经过实测。

最新组件容量输入 1000 条表格记录，分页保持 26 个 DOM 表格行；250 个候选输入限制为 200 节点 / 400 边。Windows i7-12700H、约 34 GB、Chromium 153 的本次首屏两帧测量 74.1 ms；不是业务吞吐或提升百分比。

Wheel 与 Sdist 重建 Wheel 都在没有源码路径依赖的新环境中验证 Contract/Policy、打包静态资源、深层刷新、API 401/404、独立 Worker、授权下载、端口冲突不杀未知进程、重启 Job、幂等重放和缺 Reasoner 的真实阻断。Linux 构建的同一份 Wheel/Sdist/Examples 字节又在 Windows 两个新环境交叉验证；不是仅验证各平台各自构建的不同工件。

交付目录：runtime_logs/p09/delivery-b63ba37；构建资源逐文件摘要见其中 build-manifest.json。

| 工件 | 字节 | SHA256 |
| --- | ---: | --- |
| kg_mnp_toolchain-0.9.0rc1-py3-none-any.whl | 1073485 | e0ee2db493701bd0df3fde7d958abaaf077e00d1c9857354354c5c4a3eb1786b |
| kg_mnp_toolchain-0.9.0rc1.tar.gz | 880773 | 8876c4f876b804bb1ac8f18411ef7a29c710e07adee8cc5d9bc0ea5b0db643e4 |
| toolchain-examples.zip | 109656 | 9d9687cbf410f21d3755291e8897ba7dd9f22cdea6d346be97ed79b9f8c921e6 |
| 验收证据 ZIP | 23366594 | 4d20c39fbbbd8664d42a17442e6d94c035ef091096c7355e59bf6dd16423d31c |

证据 ZIP：runtime_logs/p09/p09-0.9.0rc1-evidence.zip，1164个条目，CRC校验通过。

原始日志、JUnit、逐节点回执、截图、工件 ID 与失败记录放在忽略的证据 ZIP 中；排除 Workspace、Job DB、Token、Session、浏览器 auth state、真实 License 和用户 Source。已做凭证模式扫描与 ZIP CRC 检验。

## 原失败及修复

旧 NO_GO、跨修订增量和中断不改写成最终 PASS。历史失败包括未接通上传/Source、错误工作区根、输入篡改、旧 Forestry 冻结断言、Windows 子进程 stdin 阻塞、CRLF 锁失配、重复验包/下载超时、旧按钮选错候选、指针与读取快照完整性。

本次最终收尾还实际修复：未登录轮询清空草稿、POSIX 反斜线路径、测试依赖宿主机 reasoner 报告、旧一次性资产写入器、折叠图隐藏尺寸/长标签、缺少的总览/树/映射样本/对象关系界面、多 Source/工作表表头混用，以及后续 Release 测试对旧按钮的竞态选择。

Cf2 全量 1767 通过/5 失败是旧简化负例夹具缺 Evidence 记录；补全夹具后原负例断言全部保留。Cf2 Browser 4 通过/1 失败是旧候选按钮选择被后端 CAS 拒绝；以明确 Candidate ID 绑定后复验。Windows 一次准备失败是自有 Vite 占用 Rolldown native 文件，解除占用后从完整入口重跑，不修改安全权限或依赖锁。详见原始失败日志和最终同修订记录。

## 可选外部集成与研究限制

GraphDB 当前适配器有显式/完整导出、物理默认图、项目/效果/目标/配置/到期/包绑定及重定向/代理负例的协议测试；未配置经许可 live GraphDB，不能声称真实部署。工作流 Outbox 只证明入队，没有外部业务执行器。WebVOWL 保留显式离线转换与当前本地候选可视化，不保留旧网页服务器。

研究机制仍是契约化工具链、Evidence-bound KG-IR、候选/人工审核/确定性编译分离、语义回归与受控生命周期。工程实现不等于学术新颖性或跨行业效果已证明；Hash 不证明来源真实，OWL 不证明业务正确，SHACL/CQ 仅覆盖实际约束/Query/Oracle，Recorded Provider 不等于 Live LLM，合成 Forestry 不等于实地试点。

本地 copy-on-write 成本随工作区增长；没有分布式 HA、外部 exactly-once、真实硬件断电研究、企业 SSO 或生产安全认证承诺。PyPI 50 个锁定依赖和 npm 未报告已知漏洞，不排除未知漏洞。浏览器和安装实测不能替代生产环境独立审计。

## 提交与最终状态

- dc5694dbf7b5b2b0273e70d3b61595c005b28580 feat(services): connect fenced source modeling and initial release workflows
- d587d578c7bc5b365882645a7b18a026594c2223 feat(workbench): add authenticated Chinese minimal engineering workflow
- 5330df3ac02463e8c32c30e64d9ecb58f9ef0984 refactor(verification): audit fixed history and retain open consolidation scope
- c355e9527dad9ba0a6d4246dbe8585126eace229 fix(packaging): include dependency notices and isolate generated build output
- 598c7b03ca748663889518adfe2333e78408cd2a fix(security): reject drive syntax in portable source display paths
- 10b3f92f2f08ba16d9d538f472d86af5a3380e69 test(product): replace stale version and prose freezes with current invariants
- 3c0d0ad18e9640ceacc60502e227354cfff939d0 fix(contracts): preserve frozen schema bytes across platform checkouts
- e98428305b8c96d94047dca004c5438d1b28ccb6 docs(verification): bind tested revision and honest no-go delivery evidence
- 0208f7ed27c1b849d4909469c693381c6702349c feat(lifecycle): connect controlled version workflows and evidence record mappings
- 5d9c60b13a1e3e78054c2e2112bee54b8ccbbdb7 feat(workbench): add synthetic forestry and governed version views
- 310a952c92f45e4e6743b1379825cbd2e5094015 fix(core): preserve evolving workspaces and fence lease renewal
- fc5ce79c76d8160f65edc76c14e58dd4805cf372 feat(services): enforce review revisions and executable release regression
- d074bea209d396ce9a8224cd0de2971916298d40 feat(workbench): expose review policies and browser acceptance workflows
- 82eabd384177bddc18030d8a6dcd18655bc91cd7 style(tests): normalize forestry registry import
- 5a6a0f6aa757148b8658becf3af5d6fab70e4c20 fix(deps): pin patched web build and test dependencies
- 107310ce4ad8d73cc169928741b0a95e90206d73 fix(services): bound versioned queries and expose fenced job recovery
- d6f8bf67cc345afae1a349889688f1727dfa86d7 feat(workbench): add versioned browsing recovery and bounded exploration
- 442a1e35dcc6e1ceacae48f8f045dcb923491c70 fix(quality): enforce typed application boundaries and scoped loopback targets
- ca91592bd3277a60895b5b7364a66aa30c7907f2 feat(compiler): version semantic fixes and preserve historical package readers
- 382b5217cf64a9e29b292bd564aed21fda569e7c refactor(workbench): retire legacy UI and local approval dispatchers
- c1d54f89666bcaad7daaceaf322df0539e5ddb01 refactor(quality): replace phase aggregates with capability verification
- aefe6509480ae28706dcc38712bf56d73ed0988b docs(toolchain): align product architecture and migration guarantees
- 3840498b3bb2c9268efef743b3d18cf99d83e561 docs(verification): separate current checkpoint from final acceptance
- ef4374dc6c1c674c59677259affcdf659b79e074 refactor(api): retire duplicate HTTP runtimes and migrate wire security
- 551868108ce2b16532ebcc04ad680ed089442b38 test(verification): fail closed on incomplete receipts and bound browser lifecycle
- 35e5792d1ed43ff5e36489253e690cfbf2deacdc refactor(cli): remove historical modeling and activation dispatchers
- 8ec04ef2c571336046b878225b06f714d1586ac3 refactor(cli): retire eligibility entry and unify Unicode-safe JSON output
- bcc4ffba7b61960d36964ded8d072f17b3a46cba fix(service): report actual local runtime dependencies instead of stale gate
- 1ff8d055de91b0fc776ec6d5ce267b8c8e05af8e feat(distribution): verify isolated wheel sdist installs and ship synthetic examples
- 95b4d50f1f66a27e15d245facec43061cc0f2d73 feat(workbench): expose authorized verified package archive download
- 74307197ec95f9e9e7a8ca6fccf1ae242ff83588 fix(verification): unblock Windows child startup and reject forged confirmed inputs
- 18d817b38c71e14569562ebba12f7bd3315ca1fc test(backend): own unique temporary roots on fresh platform checkouts
- feba20fcbc569f52ce51a20af786ae5caf10fb03 docs(toolchain): consolidate historical reports and semantic decisions
- 99f637dd0d4816f54632c629a1f919407fd6181f refactor(contracts): retire one-time migration writers and audit fixed domain baselines
- d8587da3bafb472e6f06f6f18f4b3705eec97473 docs(verification): record complete diagnostic checkpoint and subsequent repairs
- 375f0c094fa96ddf53e23aa1ad26995cdae681a1 refactor(core): remove uncalled legacy guard and adapter modules
- 045040ea8e58631217dda1ffac3b0b37ebb31ea5 fix(workbench): bind version actions to artifact IDs and preserve checkout bytes
- 22c387d134245afdbb3d454374b8e0b93552cfd8 refactor(fixtures): retire old golden writers without changing historical artifacts
- cd74d8912d6f4ef336a466760e22e7eeb0ee741f fix(packages): validate one captured export snapshot and recheck download grants
- be2dd61dd024613dba443d8efef213c9ff674131 docs(verification): bind archive fixes and preserve browser failure evidence
- 435d2d0207515b78be1b6b62a39f355d1b7d1a55 fix(workspace): consolidate safe staged publication and preserve unowned data
- d8250b5efbaad794dd2f793b0c3efe8fcf76e522 refactor(compat): remove obsolete publishers and workbench relay
- c77c6555d5b555eea639fc8f2258043e5c096b21 refactor(mnp): retire standalone publishing demo and migrate semantic assurances
- a23102dc5891e26600abd262fd958110260f37a8 refactor(application): replace legacy runtime with bounded offline artifact reader
- dfcfa8ce3a0a9b4ed2f5017df2371eaf81cfff41 fix(reads): bind local package projections to freshly verified snapshot bytes
- c71f9e24eac5dd2d4d81fe0c25f8bb60ab0b19b1 docs(verification): record five-scenario browser pass and remaining final gates
- be8e68c685f26f956d62cc156fdea0b038a2d3ca docs(verification): bind incremental evidence bundle and Linux snapshot results
- 9ae1a5c4ccc0dfd96b398c1520a7b96a4caad39a refactor(history): retire writable governance and activation platforms
- be728cdf103f801812539aa9f5f856e3dccbdd30 fix(lifecycle): verify selected pointer history and preserve activation safeguards
- a6e4ff87d1e7a98b3f3552eae0d4483838b659cf refactor(integrations): replace obsolete runtime platforms with approved package adapters
- 9a7a1c5b3d59c4e2447db81088456eb28dfe9a45 chore(release): prepare rc1 source for clean fixed-revision acceptance
- 482e25b4e0b5409a3b08b3dc3bfd978f3d6e3f6a fix(workbench): preserve unauthenticated login drafts across background refetch
- 6f4f683d9d78990965475ed8f050a2d2791fa5fe fix(api): preserve missing environment semantics before safe pointer resolution
- 7a4e2a1a277f1e165dd14e9db2f029e98990a833 test(release): overlap disjoint partitions without duplicating critical tests
- 168b4fa3ff9cdbc4cece65f9cfd9a98277613564 fix(verification): generate independent reasoner evidence and reject portable path attacks
- 5bb880a77bb4f0e786ba420e1ffcca6fb14d354b refactor(tooling): retire one-time asset writers and close installation drift
- 0ee66b9645b44d8bda64628580fd838a3327f842 docs(release): bind candidate status to fixed-revision evidence
- b0711a85f795711461d824d187ec4a5fdb0a5b5a fix(workbench): size expanded candidate graphs and capture actual workflow evidence
- d9634d5193d683f8875680e19798a6b475dc5eb3 fix(modeling): bind CSV and spreadsheet mappings to source table evidence
- cf2ba56882d1916d0717be9c3b7e02e76cac3280 feat(workbench): complete artifact overview mapped evidence and linked object relations
- b63ba379327af4eb102d4a852498509cef9a3bf8 fix(acceptance): bind successor review controls and preserve negative fixture authority

本文作为证据提交 E，与受测 C 分开。E 的完整 SHA、远端一致性及四文件排除后的输入一致性见交付目录 delivery-receipt.json；最终候选 Tag 为 kg-mnp-toolchain-0.9.0rc1，仅在该证明通过后创建，不强制移动。main 与 P8 保持原目标，未创建公共 Release 或生产部署。
