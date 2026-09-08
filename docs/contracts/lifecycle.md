# 生命周期契约

生命周期 Schema 位于唯一公共 Catalog 的 lifecycle scope 中，覆盖 Registry、Feedback、Change、Diff、Consumer/Impact、Regression、Release 和 Environment。Catalog schema 版本与工具链发行、编译器和 Domain Pack 版本独立；原 115 个公共 Schema 字节和标识符保持。

当前权威资源是包内 Catalog、Schema 和 Lock。通过 scripts/generate_contract_catalog.py --check 校验 Catalog，编译器新增版本由 tools/generate_compiler_contracts.py --check 校验。旧一次性阶段生成器已退役，不能用它们重新生成旧 Catalog 版本或覆盖被冻结的 Schema。

生命周期契约和行为验证拒绝越界路径、可执行意图、错误时间、跨 Registry 引用和不受控标识。Schema 通过不替代身份、Role/Quorum、真实工件摘要、查询 Oracle、完整动作重放或 CAS 检查。具体运行入口与状态含义见[用户流程](../user-guide/local-workflow.md)和[架构](../architecture/toolchain.md)。
