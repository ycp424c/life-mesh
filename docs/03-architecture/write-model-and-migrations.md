# Unified Write Model And Migrations

状态：active
最后更新：2026-07-15
职责边界：记录 ADR-0010 Unified Write Model 的运行时架构、事务边界和数据库切换边界；不重复 implementation spec 的逐字段映射和测试清单。

## 当前状态

ADR-0010 已于 2026-07-15 实现并完成真实本地数据库切换。当前写路径统一为：

```text
CLI / Manual Input / RumorClaim
  -> KnowledgeWorkflow
  -> unified Candidate / Acceptance / Canonical Object tables
```

`promoted_objects`、`rumor_candidate_links` 和 legacy audit 表只保留迁移前兼容数据，不再接受新 handoff；所有新 Candidate 都能从统一 inbox 查询和确认。真实库已由 migration `0001_unified_write_model` 完成 online backup、动态集合守恒、integrity/foreign-key 检查和幂等复核。

## 当前写路径

```text
CLI / Manual Input / RumorClaim
  -> KnowledgeWorkflow
      -> Candidate handoff
      -> Acceptance
      -> Source change / review
  -> LifeMeshDatabase transaction
      -> knowledge_candidates
      -> source_references + links
      -> acceptances
      -> typed Canonical Object tables
      -> review items + tombstones
      -> audit events
  -> Bundle retriever
      -> valid Fact as fact
      -> active Memory as context
      -> invalid or needs_review objects only in reports
```

## 责任边界

- `LifeMeshDatabase` 统一创建 connection、事务、schema migration、backup、integrity、权限和 lock。
- `KnowledgeWorkflow` 编排跨领域原子操作；repository 只持有本领域读写和校验。
- Manual Input 与 RumorClaim 保留来源领域所有权，只把 handoff 委托给 workflow。
- Canonical Fact、Memory、Task、Event 使用 typed persistence，不再把通用 JSON 表作为长期真相源。
- Source Reference 和 link 表负责 provenance；JSON 只保留不可结构化 metadata 或 legacy snapshot。
- CLI 只做 parser、输入规范化、workflow dispatch 和稳定 JSON/error 输出。

## 事务与文件操作

Candidate handoff、Acceptance、source status、review、tombstone 和 audit 必须在单一 SQLite transaction 内提交。外部模型请求不进入写事务。

managed asset 无法与 SQLite 完全原子：新增文件先进入私有 staging，数据库记录 file-operation outbox；提交后执行 rename/delete，失败保留可重试状态并由 reconcile 命令恢复。

## Migration 与 Restore

- 普通数据库连接在存活期持有 `~/.lifemesh/.database.lock` shared lock；Migration 和 restore 获取同一文件的 exclusive lock。
- 迁移使用 SQLite online backup API 保留 FTS5、sqlite-vec 和数据库页面，不使用逻辑 `.dump`。
- preflight manifest 从迁移当时的真实库动态生成 normalized identity 集合和聚合计数；postflight 以集合守恒为准，不依赖设计时固定数字。
- Source Reference 必须先于任何引用它的 Candidate/Object link 回填。
- Restore 在没有目标 DB connection 存活时原子替换，在仍持有 exclusive lock 时完成 integrity 与只读 smoke test。
- 旧表迁移后只读并保留，直到用户确认新模型和恢复路径稳定。

## 已完成的切换验收

- 真实迁移 preflight：7 Candidates、134 Source References、38 Source Tombstones、0 Canonical Objects。
- postflight 与上述动态集合完全守恒，`PRAGMA integrity_check=ok`、无 foreign-key violation。
- 同一 migration 再次执行为 no-op；从迁移前 manifest 恢复的真实形状演练可回到 legacy schema。
- 备份文件和 manifest 使用 `0600`，受管 backup 目录使用 `0700`，manifest SHA-256 已与文件复核一致。

## 正式来源

- [ADR-0010](../05-decisions/ADR-0010-unified-write-model-transactional-acceptance-and-database-migration.md)
- [Unified Write Model Implementation Spec](../superpowers/specs/2026-07-10-unified-write-model-design.md)
- [Backup And Recovery](../07-security/backup-and-recovery.md)
