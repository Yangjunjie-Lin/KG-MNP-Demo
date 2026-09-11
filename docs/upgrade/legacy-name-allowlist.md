# 旧名称保留清单

| 范围 | 保留原因 |
| --- | --- |
| `src/kg_mnp/__init__.py`、`__main__.py`、旧 CLI | 兼容既有导入和启动方式；只有别名，无业务实现副本 |
| `urn:kg-mnp:*`、`KG_MNP_*` manifest_kind、schema URL | 已持久化身份及公开契约，不因品牌迁移重签或重算 |
| 插件 `kg_mnp.plugins` entry-point group、builtin manifest distribution `kg-mnp-toolchain` | 原插件协议/签名身份；新发行包继续承载同一受控插件，不依赖旧包实现 |
| `KG_MNP_` 环境变量 | 有冲突检测的旧配置兼容层；推荐 `ZHIGOU_` |
| 历史 docs/verification、docs/modeling、git-show 路径和冻结标签 | 原始验收证据，不改写历史 |
| MNP Domain Pack、MNP IRI 与数据 | 合法领域内容，非通用产品品牌 |
| `.kgop` | 已有可验证交付格式，保持兼容 |
| GitHub origin/历史链接 | 远端未更名，链接不预先伪造 |
| 测试进程 `KG_MNP_BROWSER_*`、历史运行目录 | 本地测试协议兼容；不作为新用户配置主入口 |
| `tools/migrate_python_namespace.py` 中的匹配字符串 | 可审计的一次性机械迁移记录 |

KG-MNS/kg-mns/kg_mns 没有作为新的主入口引入。任何新增旧名需说明是资产身份还是兼容边界，不能用全局替换清零。
