# 前端集成契约

## 权威边界

正式前端只负责输入、HTTP 请求、请求状态、DTO 适配、中文展示和交互可视化。FastAPI 后端是以下内容的唯一权威：

- 资格结论与阻塞原因；
- 规则及版本选择；
- RDF、OWL-RL、SHACL 与能力问题查询；
- 情景推演的结论和差异；
- 证据链、时间线及追溯图边关系。

前端不得重算、补造或覆盖这些结果。Neo4j 是可选扩展，不是本阶段运行或健康检查的依赖。

## 地址与类型

浏览器默认 Base URL 为相对地址 `/api/v1`。本地 Vite 代理到 `http://127.0.0.1:8000`；Docker 中 Nginx 代理到 Compose 服务 `backend:8000`。

接口路径版本为 `/api/v1`，响应 `schema_version` 为 `1.0`。`docs/api/openapi.json` 是前端 API DTO 的唯一类型来源：

```bash
cd frontend
npm run api:generate
npm run api:check
```

API DTO 与 UI View Model 必须由 `src/api/adapters/` 隔离；页面不应散落后端 `snake_case` 字段拼接。

## 数据源契约

```text
VITE_API_BASE_URL=/api/v1
VITE_DATA_SOURCE=api
VITE_ENABLE_TECHNICAL_VIEW=false
```

`api` 是默认正式数据源。`mock` 只能显式用于组件开发和单元测试：

- API 模式不得导入 Mock fixture；
- API 失败不得回退到 Mock；
- 离线、超时、无记录和业务错误必须显示对应中文状态；
- 全栈 E2E 不得使用 MSW；
- 技术调试模式默认关闭，开启时也必须提交真实 API。

## Service 端点映射

| Service | 真实端点 |
|---|---|
| `systemService` | `GET /health`、`GET /ready`、`GET /meta` |
| `dashboardService` | `GET /views/dashboard`、`GET /examples` |
| `exampleService` | `GET /examples`、`GET /examples/{case_id}`、`POST /examples/{case_id}/run` |
| `caseService` | `GET /cases`、`GET /cases/{case_id}`、`GET /cases/{case_id}/history`、`GET /cases/{case_id}/latest`、`GET /views/cases/{case_id}` |
| `assessmentService` | `POST /assessments`、`GET /assessments`、`GET /assessments/{execution_id}`、`GET /assessments/compare`、`GET /assessments/{execution_id}/artifacts`、`GET /views/assessments/{execution_id}`、`GET /views/assessments/{execution_id}/timeline`、`GET /views/assessments/{execution_id}/trace` |
| `ontologyService` | `GET /ontology/summary`、`GET /ontology/modules`、`GET /ontology/classes`、`GET /ontology/properties`、`GET /ontology/graph`、`GET /views/ontology` |
| `ruleService` | `GET /rules`、`GET /rules/{rule_id}`、`GET /rules/{rule_id}/versions`、`GET /rule-updates/affected-assessments` |
| `competencyService` | `GET /competency-questions`、`GET /competency-questions/{cq_id}`、`POST /competency-questions/{cq_id}/execute` |
| `whatIfService` | `POST /assessments/{execution_id}/what-if`；仅在需要组合视图时使用 `POST /views/what-if` |

表中路径均相对于 `/api/v1`。系统状态页面只能展示 `/health`、`/ready` 和 `/meta` 实际返回的信息，不得伪造延迟、可用率或服务列表。

## 请求与错误

新建评估请求结构：

```json
{
  "payload": {},
  "persist": true,
  "force_recompute": false
}
```

同一 `case_id`、`assessment_time`、`input_hash` 在 `persist=true` 且 `force_recompute=false` 时复用已有执行，不创建新制品目录。`force_recompute=true` 只有在新记录成功保存后才替换原记录并删除旧制品。

请求体上限由 `KG_MNP_MAX_REQUEST_BYTES` 控制，默认 1048576 字节；超限返回 HTTP 413 和 `REQUEST_TOO_LARGE`。统一错误体为：

```json
{
  "error": {
    "code": "INPUT_SCHEMA_ERROR",
    "message": "...",
    "details": [],
    "retryable": false
  }
}
```

前端不得直接显示 traceback、HTML 错误页、英文代码或英文字段路径。422 字段路径必须映射为中文；未知路径显示“未识别字段”。

## 不可变案例语义

| 案例 | 后端权威结果 |
|---|---|
| 案例六历史评估 | 2026-05-15，规则版本 1.0，120 天，可携转 |
| 案例六当前评估 | 2026-07-01，规则版本 1.1，180 天，不可携转 |
| 案例七 | 资格结论可携转；授权码已过期；流程不能继续 |

规则更新影响查询必须使用：

```text
GET /api/v1/rule-updates/affected-assessments?rule_id=MNP-ELIG-005&old_version=1.0&new_version=1.1
```

该接口查询 SQLite 历史，前端不得硬编码案例六。

## 前端禁止事项

- 提交任意 SPARQL 或 TTL；
- 重新实现资格规则或流程判断；
- 发明追溯边或修改响应中的节点身份和关系；
- 在本地计算 What-if 差异；
- 将演示条款表述为正式法律文本；
- 请求失败时保留 Mock 数据冒充真实结果。
