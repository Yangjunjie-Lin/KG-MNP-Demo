# 名称迁移与安全恢复

开始分支 main，HEAD `f79d56e714c194bca5c7c825ebdf38fb8df026d0`，起始工作区**不干净**。
先保存未提交/未跟踪文件和 binary diff 到 `runtime_reports/upgrade-recovery-*`，再切换
`codex/zhigou-full-chain`。没有 reset、clean、覆写用户业务数据或发布历史包。

主产品名为知构工具链 / ZhiGou Toolchain。唯一 Python 实现已移到 `src/zhigou_toolchain`。
`src/kg_mnp` 只有薄导入/CLI 兼容层，新旧模块引用同一类和资源，不建第二套全局状态。
发行包及新 CLI 为 `zhigou-toolchain`；`python -m zhigou_toolchain` 为不依赖 PATH 的主入口。
旧 CLI 提示弃用。插件原声明身份、契约 IRI 和稳定 URN 保留，见 allowlist。

新 `ZHIGOU_` 与旧 `KG_MNP_` 环境变量同值可兼容，不同值报错且不回显配置值/密钥。
迁移后的 Python 类型检查覆盖新的实际源码目录；当前文件边界测试同步迁移，历史 git-show 验证路径不变。

GitHub 原仓库保持 `Yangjunjie-Lin/KG-MNP-Demo`，origin 未改。
附件中“原地更名/提交”的指令不是本次对外操作的直接授权；本轮没有创建替代仓库、推送、合并、标签或外部发布。
远端目标 `Yangjunjie-Lin/zhigou-toolchain` 为 **NOT_EXECUTED_REQUIRES_USER_DIRECTION**，不是已完成。
经用户明确同意后，应先比较 repository id、管理权限和目标占用，执行原地 rename，核对同一 id 后再更新 origin。

代码仍为本地未提交增量；最终验证使用源码清单摘要，不能把上述基准 commit 当作升级代码的受测提交。

林业工单新项目使用 `forestry-workorders@0.1.1`：修正了早期 0.1.0 从原六条示例复制来的说明计数。
实际 CSV 始终为 3 株古树、3 条巡查、2 个区域。0.1.0 的早期工程快照保留给既有合成审核/包复验，
不覆盖其原锁、不将既有项目静默指向 0.1.1。
当前目录仍严格要求目录名等于 pack_id；旧精确版本保存在 `.versions/<版本>/<pack_id>/`，
注册表显式扫描并校验版本目录，不通过放松 pack_id 检查接受任意别名目录。

清理范围：仅删除已经没有引用的 `workbench/src/modeling-tutorial.tsx`。
替代为同一工作台的五阶段组件和普通批次加载入口，旧 URL 保留重定向。
原文件在起始恢复 ZIP 中可恢复；Python 教学资源、历史证据、领域包与用户数据未删除。
构建时清理的 `build/lib/kg_mnp` 是本项目生成缓存，避免旧实现混进新 Wheel，不是源目录。
