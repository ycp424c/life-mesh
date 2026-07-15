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

ADR-0010 已实现；2026-07-15 的真实库切换已按以下合同执行：

- Migration 与 restore 共用 `~/.lifemesh/.database.lock` exclusive lock，并检查旧进程、活跃连接和 WAL/SHM/journal。
- 迁移前使用 SQLite online backup API 生成 `0600` 备份和 manifest；备份目录必须为 `0700`。
- manifest 记录路径、size、SHA-256、schema 和不含个人内容的动态聚合/identity 摘要。
- 迁移前后以同一 preflight manifest 做集合守恒、integrity、foreign key 和 sqlite-vec 验收，不使用设计时固定计数。
- Restore 只接受当前 HOME 受管备份目录中的 manifest；验证连接必须在 `os.replace` 前关闭，并在 exclusive lock 内完成替换、companion cleanup、integrity 和只读 smoke test。
- 失败数据库及 companion files 保留为受管 forensic 副本，直到人工确认恢复完成。

当前 CLI：

```bash
lifemesh db status
lifemesh db migrate              # 只读 preflight
lifemesh db migrate --apply      # backup + migration
lifemesh db restore <manifest> --apply
lifemesh db reconcile-files      # dry-run
lifemesh db reconcile-files --apply
```

真实迁移的受管 manifest 位于 `~/.lifemesh/backups/`；文件名包含 migration id 和 UTC 时间。文档只记录数量、校验状态和摘要，不记录个人内容。

2026-07-15 独立 review 发现旧 audit-only deleted promotion 的嵌套 payload 可能被复制到统一 audit。迁移逻辑已改为只保留 object id、target type 和 normalized payload hash；真实库在受管 online backup 后净化 1 条统一审计副本，并通过 integrity check。旧只读 legacy audit 不在这次修复中改写。

完整执行规则见 [ADR-0010](../05-decisions/ADR-0010-unified-write-model-transactional-acceptance-and-database-migration.md) 和 [Unified Write Model Implementation Spec](../superpowers/specs/2026-07-10-unified-write-model-design.md)。

## 待决问题

- 是否支持端到端加密备份？
- 审计日志如何在隐私删除和安全追踪之间取舍？
