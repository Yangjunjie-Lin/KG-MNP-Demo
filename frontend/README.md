# 携号转网资格判断本体系统 — 前端

## 启动

```bash
cd frontend
npm ci
npm run dev
```

浏览器打开本地开发地址（默认 `http://localhost:5173`）。

## 验收

```bash
npm run verify
```

等价于依次执行类型检查、测试与生产构建：

```bash
npm run typecheck
npm run test
npm run build
```

## 说明

- 当前前端使用**模拟数据**，尚未连接真实 FastAPI。
- 后续接口连接集中在 `src/app/services/`：
  - `assessmentService.ts`
  - `caseService.ts`
  - `ontologyService.ts`
  - `ruleService.ts`
- 「技术调试」原始数据输入默认关闭。仅在开发环境且设置 `VITE_ENABLE_TECHNICAL_VIEW=true` 时可见，正式演示界面不会出现。
- 用户可见文案全部经 `src/app/i18n/zh-CN.ts` 中文化映射；未知值显示中文未知提示，不会回退为英文原始码。

## 环境变量

参见 `.env.example`：

```text
VITE_ENABLE_TECHNICAL_VIEW=false
```
