# 全栈验收

本页用于验证 Stage Gate：`Real API Integration and E2E Verified`。验收不得启用 MSW，不得在 API 失败时回退到 Mock，也不得依赖固定执行编号。

## 自动验收

从仓库根目录执行：

```bash
python -m pip install -e ".[dev,api]"
pytest -q
python scripts/check_references.py
python scripts/check_rule_versions.py
python scripts/export_openapi.py
git diff --exit-code docs/api/openapi.json

cd frontend
npm ci
npm run api:generate
npm run api:check
npm run typecheck
npm run test
npm run build
npm run verify
npx playwright install chromium
npx playwright test
cd ..

docker compose -f docker-compose.fullstack.yml config
docker compose -f docker-compose.fullstack.yml build
```

等价聚合入口：

```bash
make verify-fullstack
```

聚合入口会安装 Chromium，显式清除 `runtime_data`、重新 Seed、启动真实 API 与前端、运行 Playwright，并在成功或失败后关闭两个服务。

CI 的 `python`、`frontend`、`docker` 和 `fullstack-e2e` 任务均必须成功；不得设置 `continue-on-error`。OpenAPI 漂移、类型错误、单元测试、构建、后端测试或 E2E 任一失败都应阻止验收。

注意：`api:check` 的 `git diff` 只能检查已跟踪文件的内容漂移；CI 还会通过 `git ls-files --error-unmatch` 确认 `src/api/generated/schema.ts` 已被 Git 跟踪，防止合并时遗漏生成文件。本地未提交的集成工作仍可执行 `make verify-frontend`。

## E2E 环境

直接在 `frontend` 目录运行 `npx playwright test` 时，`playwright.config.ts` 的 `webServer` 会执行：

```bash
python ../scripts/run_fullstack.py --reset-seed
```

该冷启动会清理并重新初始化案例一至案例九，校验案例六存在两条规则版本历史，然后启动真实 FastAPI、SQLite、语义处理链、规则引擎和 Vite。前端环境固定为：

```text
VITE_DATA_SOURCE=api
VITE_API_BASE_URL=/api/v1
```

如果 CI 或其他编排器已经启动并等待两个服务就绪，运行 Playwright 时设置：

```text
PLAYWRIGHT_EXTERNAL_SERVERS=true
```

该变量只禁用 Playwright 自身的 `webServer`，不会启用 Mock；外部服务仍必须处于 API 模式。`scripts/run_fullstack.py --playwright` 会自动为其子 Playwright 进程设置该变量，避免递归启动。

Playwright 应在失败时保留截图、视频和 trace；`playwright-report/` 与 `test-results/` 由 CI 上传。

## 自动场景断言

| 场景 | 必须验证 |
|---|---|
| 系统总览 | 页面加载；后端状态真实；九个案例存在；统计来自接口；无禁止英文 |
| 案例三 | 运行接口返回动态执行编号；结论不可携转；存在有效合约限制；显示规则四、监管条款四及等待合约到期或办理解约；追溯图只使用响应节点与边 |
| 案例六 | 历史 120 天按版本 1.0 可携转；当前 180 天按版本 1.1 不可携转；受影响评估来自后端规则更新查询 |
| 案例七 | 资格结论可携转；授权码已过期；流程不能继续 |
| 新建评估 | 从 API 加载示例；真实提交；跳转动态执行编号；SQLite 存在记录；刷新仍可打开 |
| 情景推演 | 选择案例三真实执行；只发送用户修改的 `changes`；结论和规则差异来自后端响应 |

## Docker 运行验收

完成镜像构建后实际启动：

```bash
docker compose -f docker-compose.fullstack.yml up
```

在另一终端确认：

```bash
curl --fail http://localhost:8000/api/v1/health
curl --fail http://localhost:8080/
```

浏览器完成以下操作：

1. 打开 `http://localhost:8080/overview`；
2. 确认后端可访问且数据库就绪；
3. 运行案例三；
4. 确认 URL 使用后端返回的执行编号；
5. 刷新评估详情，确认仍能从 SQLite 读取；
6. 确认结论、阻塞原因和追溯图均来自真实接口。

同时直接访问 `http://localhost:8080/assessments/new`，确认 Nginx 的 SPA 回退有效。

## 通过标准

- 默认前端使用真实 API，正式构建不读取 Mock；
- OpenAPI 类型可重复生成且无漂移；
- API DTO 与 UI View Model 由 Adapter 分离；
- 全部真实数据页覆盖加载、空状态、离线、超时、业务错误和重试；
- 后端是资格、流程、规则、语义处理、What-if 与追溯关系的唯一权威；
- 正式界面保持中文，原始英文技术码不直接可见；
- 自动测试、真实 E2E、生产构建和 Docker 全栈构建全部成功。

任何失败必须记录具体文件、原因、影响及是否阻塞 Stage Gate，不得写“基本完成”。
