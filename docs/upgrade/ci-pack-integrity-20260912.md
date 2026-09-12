# CI 领域包完整性修复（2026-09-12）

## 原因

`99a87e7` 的 Linux/Windows 后端失败和工作台 HR 选项禁用，主要来自同一问题：三个 `pack.yaml` 原来混用了 LF/CRLF，Git 的统一 LF 规则改变了字节，但锁文件仍绑定原始 SHA-256。语义与所有资产都没有变化，严格锁检查正确拒绝了清单。

旧的质量门只验证 minimal/MNP 两个历史锚点，没有验证新增 HR、林业及归档版本的锁，因此直到较晚的服务和浏览器测试才暴露问题。

## 修复

从此前本机验证过的分发包中恢复原始清单，恢复前同时核对原锁 SHA-256 与归一化文本相等；没有重新生成锁、改变锁 ID、修改业务内容或绕过校验。

| 包 | 恢复后的原始清单 SHA-256 |
| --- | --- |
| hr@0.1.0 | `02758d3d68925673dee2ec2a2cc678cb0a8af6f1f0a341dec9e8961f6039a11e` |
| forestry-workorders@0.1.1 | `1d185a4c94195277981f1bd2f59666e6f789da8792a37acab5e4059a6374f82f` |
| forestry-workorders@0.1.0（归档） | `654f31de71412f88e9c368c977b33f0c28d58789991cdfa3519149df4bd42a38` |

`.gitattributes` 对这三个清单明确禁用文本转换；其余文件继续遵守原规则。`check_domain_baselines.py` 现在验证全部七个注册版本，同时保留 minimal/MNP 原始历史摘要检查。

新增回归检查覆盖：新包/归档包的换行漂移必须拒绝且不改写锁，以及 `core.autocrlf=true/false` 两种全新 Git 检出后全部包锁仍一致。原有注册表测试也改为逐一解析全部版本。

## 本地复测

- 包完整性、Git 检出、运行时就绪和会话恢复：14 项通过。
- 原 Windows OWL 超时用例：在原限制下单独复测通过。
- 原失败的工作台 `zhigou-console.e2e.ts`：真实浏览器通过，服务器、Worker 和临时凭证已清理。
- 无缓存 lint 与类型检查通过。

原始 CI 失败及本地复测证据保存在 `runtime_reports/ci-fix-20260912/`，浏览器收据为 `runtime_logs/p09/browser-runs/managed-00bbfc4538274b77931cd39358912bba/managed-receipt.json`。本次不延长 OWL 限时，不添加失败自动重试，不跳过测试；最终远端结论以修复提交的完整 Actions 运行结果为准。
