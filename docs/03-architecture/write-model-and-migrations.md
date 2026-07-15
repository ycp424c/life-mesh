# Unified Write Model And Migrations

状态：active
最后更新：2026-07-15
职责边界：记录 ADR-0010 已接受的 Unified Write Model 目标架构、事务边界和数据库切换边界；不宣称这些能力已实现，也不重复 implementation spec 的逐字段映射和测试清单。

## 当前状态

ADR-0010 的目标架构已经确认，实施尚未开始。当前运行时真相仍是三条分裂写路径：

```text
candidate add  -> knowledge_candidates
input promote  -> promoted_objects
rumor promote  -> rumor_candidate_links
```

因此 dashboard 和 roadmap 可以把 Unified Write Model 标记为“已设计、待实现”，但不能把统一 schema、Acceptance、Canonical Object 或真实库迁移标记为已完成。

## 目标写路径

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

- Migration 和 restore 共用 `~/.lifemesh/.database.lock` exclusive lock，并检查旧进程、活跃连接和 WAL/SHM/journal。
- 迁移使用 SQLite online backup API 保留 FTS5、sqlite-vec 和数据库页面，不使用逻辑 `.dump`。
- preflight manifest 从迁移当时的真实库动态生成 normalized identity 集合和聚合计数；postflight 以集合守恒为准，不依赖设计时固定数字。
- Source Reference 必须先于任何引用它的 Candidate/Object link 回填。
- Restore 在没有目标 DB connection 存活时原子替换，在仍持有 exclusive lock 时完成 integrity 与只读 smoke test。
- 旧表迁移后只读并保留，直到用户确认新模型和恢复路径稳定。

## 正式来源

- [ADR-0010](../05-decisions/ADR-0010-unified-write-model-transactional-acceptance-and-database-migration.md)
- [Unified Write Model Implementation Spec](../superpowers/specs/2026-07-10-unified-write-model-design.md)
- [Backup And Recovery](../07-security/backup-and-recovery.md)
