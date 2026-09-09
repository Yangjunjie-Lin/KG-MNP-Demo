# 能力门与最终验收

测试按保证的能力组织；目录名不是冻结整个旧产品的理由。安全、篡改、证据、审核、并发和历史包读取断言必须保留或有明确替代，映射记录在主退役台账中。

## CI 职责

| 工作流 | 唯一职责 |
| --- | --- |
| ci-quality | lint、应用层静态类型、契约/领域基线/摄取示例一致性、仓库卫生、前端类型 |
| ci-backend | Windows / Linux 分别运行完整 pytest collection 一次，包含安全和兼容测试 |
| ci-workbench | 前端组件测试、构建、合成服务与真实浏览器，以及独立的图布局/键盘/容量渲染检查 |
| ci-security | Python / npm 已知依赖公告核查 |
| ci-release-check | Windows / Linux 新环境安装、Sdist 重建与实际 API/Worker 探针，不自动发布 |

不再递归运行历史阶段 aggregate。同一平台完整后端 collection 包含安全和兼容能力，其他工作流不重复执行这些 pytest 节点。普通 backend/CI 入口为 tools/run_backend_tests.py，它创建唯一的证据与临时目录；不会假定干净 checkout 已有 runtime 目录，也不清除以前的基准目录。配置了 CI 不表示远端运行已通过。

长期分支仅保留 `main` 和 `develop`；全部五个工作流在推送到这两个分支、以它们为目标的 PR 和手动触发时执行，不使用路径过滤跳过检查。同一工作流、同一引用的新运行会取消过时运行；Windows / Linux 矩阵不因另一平台失败而取消。失败时仍上传已产生的后端、浏览器、渲染、依赖与安装包诊断证据。以 GitHub Actions 对应提交 SHA 的实际结论判断 CI 状态，不将旧 RC 验收记录视为新提交的通过证据。

所有准备显式安装锁定依赖和固定摘要 ROBOT；核心执行不会联网下载。GraphDB live 与外部执行器需要另行授权，未配置不是本地功能失败的替代解释。

历史 Compilation / GraphDB / Publication 的 expected 工件、已审计 OWL2VOWL 原始输入及原样装入包内的 WebVOWL 策略绑定精确字节；`.gitattributes` 对这些固定集合禁用文本换行转换。Windows 的 `core.autocrlf=true` 不能改变其 Git blob 字节，回归测试同时核对转换后的字节和实际工作区字节；不能通过重写历史工件、重算哈希或放宽验证解决 checkout 漂移。

## 固定修订验收

1. 完成实现、迁移、文档与构建配置，提交 CODE_FREEZE，工作树干净。
2. `python tools/verify_release_candidate.py prepare` 导出唯一 collection、源码摘要和两个不相交分区。
3. 在同一代码修订运行 serial / parallel；每个分区使用独立显式 basetemp 并保存命令、退出码、节点和 JUnit。
4. summarize 检查执行并集等于原 collection。重复补测不增加唯一覆盖，失败或缺失不能拼接成通过。
5. 在同一修订执行前端、浏览器、平台、安装/构建、历史包、恢复和文档命令验证。
6. 证据提交只允许明确列名的摘要文件变化；受测源码、配置、测试和构建输入改变就重新冻结。

`runtime_logs/` 原始证据不进 Git。浏览器证据只用合成身份，归档时移除 Cookie / Authorization / CSRF 值但保留失败断言。库 deprecation、平台 skip、未执行项和可选外部阻断分别报告。

## 视觉、键盘与容量

自动 axe 扫描与逐步键盘检查分别记录，截图必须实际查看。工作台容量测试用同一套真实 React 组件，不能把测试页 props 当作业务 API 成功。

`npm --prefix workbench run test:rendering` 默认由 Playwright 启动并关闭独立 loopback Vite 测试服务（端口 4174，冲突时失败，不复用未知进程）；也可用 `KG_MNP_RENDERING_URL` 显式指定已有测试服务。业务 E2E 则用 `python tools/run_browser_verification.py` 创建独立合成服务和真实 Worker；不替换业务 API。

完整发行候选还需要独立干净环境安装和实际启动。tools/verify_distribution.py 在当前平台执行两套独立安装，并可通过 --prebuilt 验证同一工件在另一平台的行为。Wheel/Sdist 构建成功不是运行、兼容或发行验收通过。

浏览器管理使用独立本地停止标记，不使用持续读取标准输入的线程；后者会阻塞 Windows 验证子进程启动。--smoke-only --probe-subprocess 会运行真实 SHACL 子进程的正反例，不能仅凭 HTTP 健康页认定 Worker 的隔离验证可用。此合成测试启动器不是生产进程管理器；硬杀其父进程后的残留测试进程应按已知句柄与运行目录人工审计，不能按端口杀未知进程。

`--selected-test security.e2e.ts` 仅供增量边界诊断，回执明确标为 SELECTED_BROWSER_E2E，不能替代默认的五场景完整验收。网络负例同时覆盖实际 Chromium 的 HTTP/HTTPS/WS/WSS CSP 阻断，并安装请求中止保护以避免测试回归时发出外部连接。

0.9.0rc1 是待验收候选版本标识，不表示已获 GO。只有固定修订的完整后端、浏览器、双平台安装、视觉/键盘与交付一致性全部闭合后，才允许创建成功候选 Tag。
