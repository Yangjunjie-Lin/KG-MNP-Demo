# 构建、独立安装与启动

发行构建与最终验收是两件事。构建成功不会创建 Tag、公共 Release 或部署。
最终交付必须引用干净固定修订的实际验收记录；脏工作树构建仅供开发预检。

## 显式准备

使用独立 Python 3.11+ 虚拟环境。运行依赖、可选文档解析依赖和测试依赖分别定义在 `pyproject.toml`；开发环境的实际解析版本由 `requirements-dev.lock` 固定。
Node 仅用于前端构建和测试；安装 Wheel 后运行工作台不需要 Node。Java 与固定 ROBOT 用于真正的语义编译，不由核心运行时自动下载。

```text
python -m pip install -c requirements-dev.lock -e ".[dev,webvowl]"
npm ci --prefix workbench
python tools/prepare_reasoner.py
```

浏览器测试还需显式安装锁定版本的 Chromium：

```text
npm --prefix workbench exec -- playwright install chromium
```

## 构建与当前平台的安装验证

```text
python tools/build_distribution.py
python tools/verify_distribution.py
```

每次创建独立输出目录，不覆盖旧验收产物。构建输出包括 Wheel、Sdist、`toolchain-examples.zip` 和 `build-manifest.json`。示例包仅收录版本控制中的 Domain Pack 和合成接入示例；不包含 Runtime Workspace、凭证或用户上传资料。

安装验证从 Sdist 重新构建 Wheel，对比 Python/契约/前端资源的实际字节；再分别建立两个全新非 editable 环境。它在隔离解释器中检查契约和 Policy、打包的页面与深层刷新、API 401/404、独立 Worker、授权下载、Web 进程重启与历史 Job、幂等重放、端口占用和缺 Reasoner 状态。

该命令只验证执行它的平台。Windows 通过不能替代 Linux，安装预检也不能替代全量后端、浏览器和最终固定修订验收。日志及每条命令退出码保存在输出目录中。

## 无源码目录安装

解压构建生成的 `toolchain-examples.zip` 到一个新目录。下面的 `<WHEEL>` 是实际输出的 Wheel 文件路径，`<EXAMPLES>` 是解压目录。不要把既有用户工作区当作示例解压目标。

```text
python -m venv toolchain-env
```

PowerShell：

```powershell
.\toolchain-env\Scripts\Activate.ps1
python -m pip install <WHEEL>
$env:KG_MNP_DOMAIN_PACKS_ROOT = '<EXAMPLES>\domain_packs'
$env:KG_MNP_ALLOW_INSECURE_LOOPBACK_SESSION = 'true'
$env:KG_MNP_REVIEW_PROFILE = 'DEVELOPMENT_SINGLE_REVIEWER'
kg-mnp service token create --workspace local-workspace --principal-id local-human --created-by local-admin --permissions '*'
kg-mnp service serve --workspace local-workspace
```

POSIX：

```sh
. toolchain-env/bin/activate
python -m pip install <WHEEL>
export KG_MNP_DOMAIN_PACKS_ROOT='<EXAMPLES>/domain_packs'
export KG_MNP_ALLOW_INSECURE_LOOPBACK_SESSION=true
export KG_MNP_REVIEW_PROFILE=DEVELOPMENT_SINGLE_REVIEWER
kg-mnp service token create --workspace local-workspace --principal-id local-human --created-by local-admin --permissions '*'
kg-mnp service serve --workspace local-workspace
```

两种环境都在另一个终端激活同一环境、设置相同变量后运行：

```text
kg-mnp service worker --workspace local-workspace
```

Wheel 默认加载自身包含的工作台资源，不需要设置 `KG_MNP_WORKBENCH_ROOT`。
需要编译时，在 Web 与 Worker 两个终端都设置 `KG_MNP_REASONER_JAR` 为经过摘要核验的本地 ROBOT JAR；没有它不得把编译标为通过。

默认入口是 `http://127.0.0.1:8765/`。开发单人审核与非 Secure loopback Cookie 仅用于本地合成测试；生产需要 TLS 和多角色、至少两名独立人工审核者。凭证只在本地签发时显示，不要保存到日志或 Git。

只用 Ctrl+C 停止自己启动的服务。端口被占用时选择另一个明确端口（`KG_MNP_SERVICE_PORT`），不要终止未知进程。重启使用原运行目录；不要删除 Job DB、Project Catalog 或工作区来“修复”失败。
