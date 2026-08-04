# 携号转网资格判断本体系统前端

中文 React 前端默认连接仓库内的真实 FastAPI。前端只负责输入、请求状态、数据适配和显示；资格判断、阻塞原因、版本选择、情景推演、语义推理、约束校验、查询与追溯边均由后端产生。

## 推荐启动方式

在仓库根目录执行：

```bash
python -m pip install -e ".[dev,api]"
cd frontend && npm ci && cd ..
make fullstack
```

浏览器访问 `http://127.0.0.1:5173`。开发服务器把 `/api` 代理至 `http://127.0.0.1:8000`；页面代码不需要硬编码主机和端口。

仅启动前端时，先确认 API 已在 `127.0.0.1:8000` 运行：

```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

## 环境变量

参见 `.env.example`：

```text
VITE_API_BASE_URL=/api/v1
VITE_DATA_SOURCE=api
VITE_ENABLE_TECHNICAL_VIEW=false
```

`VITE_DATA_SOURCE=api` 是开发和生产默认值。只有显式设置为 `mock` 才会启用组件开发数据；API 离线、超时或返回错误时不会自动回退到 Mock。真实全栈 E2E 始终使用 API 模式且不启用 MSW。

技术调试模式默认关闭；即使显式开启，提交仍调用真实 API。用户可见的动态状态、字段和错误均需经过中文映射，未知值不得回退为原始英文代码。

## OpenAPI 类型

`docs/api/openapi.json` 是 API DTO 的唯一类型来源：

```bash
cd frontend
npm run api:generate
npm run api:check
```

生成结果位于 `src/api/generated/schema.ts`，不得手工修改。`src/app/types/` 保留为 UI View Model，DTO 到 View Model 的转换集中在 Adapter 中。

## 验收

```bash
cd frontend
npm run api:check
npm run typecheck
npm run test
npm run build
npx playwright install chromium
npx playwright test
```

直接运行 `npx playwright test` 时，Playwright 会通过 `webServer` 冷启动真实 FastAPI、SQLite 和 Vite，重建九案例演示数据，并在测试结束后回收服务；不得在需要保留 `runtime_data` 时运行该命令。只有已经由 CI 或其他编排器启动服务时，才设置 `PLAYWRIGHT_EXTERNAL_SERVERS=true` 以禁用重复启动。

从仓库根目录运行 `make verify-frontend` 可完成安装、类型漂移检查和前端验证；运行 `make verify-fullstack` 会安装 Chromium，并连同后端、真实 E2E 和 Docker 构建一起验收。

## Docker

在仓库根目录执行：

```bash
docker compose -f docker-compose.fullstack.yml up --build
```

前端地址为 `http://localhost:8080`。Nginx 提供生产构建，将 `/api/v1` 代理至后端，并为 React Router 路由提供 `index.html` 回退。
