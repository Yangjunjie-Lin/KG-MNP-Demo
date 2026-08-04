# 全栈快速启动

## 前置条件

- Python 3.11 或 3.12；
- Node.js 20 与 npm；
- 本地启动可使用 GNU Make，也可直接运行 Python 启动脚本；
- Docker 启动需要 Docker Engine 和 Compose v2。

Neo4j 不是运行必需项。默认链路使用 FastAPI、SQLite、RDF、OWL-RL、SHACL 和确定性规则引擎。

## 本地一键启动

在仓库根目录执行：

```bash
python -m pip install -e ".[dev,api]"
cd frontend && npm ci && cd ..
make fullstack
```

Windows 未安装 Make 时，使用等价命令：

```powershell
python scripts/run_fullstack.py
```

启动器会：

1. 校验 SQLite 是否包含案例一至案例九，且案例六同时有历史与当前评估；缺失或不完整时运行 `scripts/seed_demo_data.py` 补齐；
2. 启动 FastAPI 于 `127.0.0.1:8000`；
3. 等待健康检查成功；
4. 以 API 数据源启动 Vite 于 `127.0.0.1:5173`；
5. 在任一服务异常退出或收到 `Ctrl+C` 时清理两个进程组。

访问：

| 服务 | 地址 |
|---|---|
| 中文前端 | `http://127.0.0.1:5173` |
| API 健康检查 | `http://127.0.0.1:8000/api/v1/health` |
| API 就绪检查 | `http://127.0.0.1:8000/api/v1/ready` |
| API 文档 | `http://127.0.0.1:8000/docs` |

如已自行初始化数据，可运行 `python scripts/run_fullstack.py --skip-seed`。也可以用 `make api`、`make frontend` 分别调试，但基本演示无需手工打开多个命令窗口。

## Docker 全栈启动

```bash
docker compose -f docker-compose.fullstack.yml up --build
```

访问：

| 服务 | 地址 |
|---|---|
| Nginx 前端 | `http://localhost:8080` |
| FastAPI | `http://localhost:8000` |

生产前端由 `npm run build` 构建并由 Nginx 提供。浏览器的 `/api/v1` 请求同源反向代理到后端，任意 SPA 路由刷新均回退到 `index.html`。SQLite 与制品保存在命名卷 `kg_mnp_fullstack_runtime`，容器重启不会丢失历史；卷为空或九案例数据不完整时后端自动补齐，并在 Seed 失败时停止启动。

停止容器：

```bash
docker compose -f docker-compose.fullstack.yml down
```

该命令保留命名卷。只有明确需要清除演示历史时才应另行删除该卷。

## 数据源与调试模式

正式默认配置为：

```text
VITE_API_BASE_URL=/api/v1
VITE_DATA_SOURCE=api
VITE_ENABLE_TECHNICAL_VIEW=false
```

Mock 仅供组件开发和单元测试；API 失败不会自动回退。技术调试模式默认关闭，开启时也不会绕过后端资格判断。

## 验证

```bash
make verify-frontend
make verify-fullstack
```

`make verify-fullstack` 会使用 `--reset-seed --playwright` 重建本地演示数据库，启动真实前后端，执行 Playwright 后自动回收服务进程。该验收会清除 `runtime_data` 中原有的本地运行历史。

也可以从 `frontend` 目录单独执行真实 E2E：

```bash
npx playwright install chromium
npx playwright test
```

Playwright 默认通过 `webServer` 冷启动 `scripts/run_fullstack.py --reset-seed`，因此同样会清除本地运行历史。只有外部编排器已启动 `127.0.0.1:8000` 和 `127.0.0.1:5173` 时，才设置 `PLAYWRIGHT_EXTERNAL_SERVERS=true`；CI 使用该模式避免重复启动服务。

完整检查项及手工验收步骤见 [`fullstack_acceptance.md`](fullstack_acceptance.md)。
