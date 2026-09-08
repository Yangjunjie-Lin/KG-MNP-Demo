# 能力门与最终验收

测试按保证的能力组织；目录名不是冻结整个旧产品的理由。安全、篡改、证据、审核、并发和历史包读取断言必须保留或有明确替代，映射记录在主退役台账中。

## CI 职责

| 工作流 | 唯一职责 |
| --- | --- |
| ci-quality | lint、应用层静态类型、生成器一致性、前端类型 |
| ci-backend | Windows / Linux 分别运行完整 pytest collection 一次，包含安全和兼容测试 |
| ci-workbench | 前端组件测试、构建、合成服务与真实浏览器 |
| ci-security | Python / npm 已知依赖公告核查 |
| ci-release-check | Windows / Linux 新环境安装、Sdist 重建与实际 API/Worker 探针，不自动发布 |

不再递归运行历史阶段 aggregate。同一平台完整后端 collection 包含安全和兼容能力，其他工作流不重复执行这些 pytest 节点。普通 backend/CI 入口为 tools/run_backend_tests.py，它创建唯一的证据与临时目录；不会假定干净 checkout 已有 runtime 目录，也不清除以前的基准目录。配置了 CI 不表示远端运行已通过。

所有准备显式安装锁定依赖和固定摘要 ROBOT；核心执行不会联网下载。GraphDB live 与外部执行器需要另行授权，未配置不是本地功能失败的替代解释。

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

`npm --prefix workbench run test:rendering` 需要指向仅供测试的 Vite 服务的 `KG_MNP_RENDERING_URL`。业务 E2E 则用 `python tools/run_browser_verification.py` 创建独立合成服务和真实 Worker；不替换业务 API。

完整发行候选还需要独立干净环境安装和实际启动。tools/verify_distribution.py 在当前平台执行两套独立安装，并可通过 --prebuilt 验证同一工件在另一平台的行为。Wheel/Sdist 构建成功不是运行、兼容或发行验收通过。

浏览器管理使用独立本地停止标记，不使用持续读取标准输入的线程；后者会阻塞 Windows 验证子进程启动。--smoke-only --probe-subprocess 会运行真实 SHACL 子进程的正反例，不能仅凭 HTTP 健康页认定 Worker 的隔离验证可用。此合成测试启动器不是生产进程管理器；硬杀其父进程后的残留测试进程应按已知句柄与运行目录人工审计，不能按端口杀未知进程。
