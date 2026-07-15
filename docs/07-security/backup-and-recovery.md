# Backup And Recovery

状态：draft
最后更新：2026-07-15
职责边界：记录 LifeMesh 对数据备份、恢复和灾难处理的要求。

## 需要备份的数据

- Raw Vault
- Canonical Store
- 授权记录
- 审计日志
- 长期记忆
- 配置和策略

Phase 1 的 `lifemesh.db` 备份必须包含完整 SQLite 页面，包括业务表、FTS5 和 sqlite-vec 数据；不得用逻辑 `.dump` 代替迁移前快照。Raw Vault managed assets、配置与策略需要独立 manifest，不能假设数据库备份已经包含文件资产。

## 恢复目标

- 用户能恢复误删的低敏数据。
- 用户能理解恢复会影响哪些派生事实和索引。
- 恢复不应绕过已撤销的授权。
- 高敏数据恢复需要更强确认。

## Unified Write Model 迁移备份

ADR-0010 已决定：

- Migration 与 restore 共用 `~/.lifemesh/.database.lock` exclusive lock，并检查旧进程、活跃连接和 WAL/SHM/journal。
- 迁移前使用 SQLite online backup API 生成 `0600` 备份和 manifest；备份目录必须为 `0700`。
- manifest 记录路径、size、SHA-256、schema 和不含个人内容的动态聚合/identity 摘要。
- 迁移前后以同一 preflight manifest 做集合守恒、integrity、foreign key 和 sqlite-vec 验收，不使用设计时固定计数。
- Restore 只接受当前 HOME 受管备份目录中的 manifest；验证连接必须在 `os.replace` 前关闭，并在 exclusive lock 内完成替换、companion cleanup、integrity 和只读 smoke test。
- 失败数据库及 companion files 保留为受管 forensic 副本，直到人工确认恢复完成。

完整执行规则见 [ADR-0010](../05-decisions/ADR-0010-unified-write-model-transactional-acceptance-and-database-migration.md) 和 [Unified Write Model Implementation Spec](../superpowers/specs/2026-07-10-unified-write-model-design.md)。

## 待决问题

- 是否支持端到端加密备份？
- 审计日志如何在隐私删除和安全追踪之间取舍？
