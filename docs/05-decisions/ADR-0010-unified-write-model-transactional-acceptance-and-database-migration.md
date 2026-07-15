# ADR-0010: Unified Write Model, Transactional Acceptance And Database Migration

状态：accepted
日期：2026-07-15

## Context

LifeMesh Phase 1 已有三个可运行但彼此分裂的写入口：`candidate add` 写入 `knowledge_candidates`，`input promote` 写入 `promoted_objects`，`rumor promote` 写入 `rumor_candidate_links`。它们各自管理 SQLite connection、schema 和 audit，导致 Manual Input 与 RumorClaim 产生的 handoff 无法在统一 Candidate inbox 中查询，Candidate 也没有一致的 Acceptance、Canonical Object、provenance 和 review 闭环。

真实 `~/.lifemesh/lifemesh.db` 会在设计与实施之间继续写入 RumorClaim 等数据，因此迁移不能依赖设计时固定计数。迁移还必须保留 FTS5、sqlite-vec、审计和删除语义，并在失败时安全恢复。

## Decision

采用 Unified Write Model，并在一次实现交付中完成受控切换：

- `knowledge_candidates` 是唯一 Candidate 真相源。
- `KnowledgeWorkflow` 是 Candidate handoff、Acceptance、source change 和 review 的唯一跨领域应用服务；CLI、Manual Input、RumorClaim 不自行拼接跨领域 SQL。
- Candidate confirmation 与用户显式 direct promote 共用 Acceptance 和 typed Canonical Object persistence。
- Canonical Fact、Memory、Task、Event 使用正式 typed tables；`promoted_objects`、`rumor_candidate_links` 和 legacy audit 迁移后只读。
- provenance 使用规范化 `source_references`、`candidate_source_links` 和 `object_source_links`；失效来源通过 review item 与 tombstone 级联，不能继续进入 Bundle。
- 所有连接由统一 database layer 创建，强制 `foreign_keys=ON`、busy timeout、私有权限和 versioned migration；handoff、acceptance、状态变化、review、tombstone 与 audit 在同一事务提交。
- 真实库迁移前必须获取 exclusive lock，使用 SQLite online backup API 生成备份与 manifest，并以迁移前动态 identity/count snapshot 驱动 postflight 守恒校验；设计时固定计数不能作为实施常量。
- restore 必须复用 migration 的 exclusive lock 和旧进程 preflight，在没有目标数据库 connection 存活时原子替换，并在锁内完成 integrity 与 smoke test。

完整字段、状态机、CLI、migration mapping 和验收规则见 [Unified Write Model Implementation Spec](../superpowers/specs/2026-07-10-unified-write-model-design.md)；目标架构边界见 [Unified Write Model And Migrations](../03-architecture/write-model-and-migrations.md)。

## Consequences

正向影响：

- Manual Input、RumorClaim 和 CLI handoff 进入同一 Candidate inbox。
- Acceptance、Canonical Object、provenance、review、audit 和 Bundle 准入有单一事务边界。
- 迁移验收基于实际 preflight snapshot，可覆盖持续增长的真实数据库而不漏迁。
- 备份与恢复共享并发锁和路径校验，降低真实个人数据库损坏或错覆盖风险。

代价：

- 这是一次较大的 Phase 1 写侧重构，需要集中 migration、完整 fixture、端到端验收和短暂停用 LifeMesh 写入。
- 旧表会保留为只读兼容面，短期内增加 schema 数量与迁移维护成本。
- 文件操作不能与 SQLite 完全原子，需要 outbox、reconcile 和 forensic recovery 流程。

## Alternatives Considered

1. **分两轮先统一 handoff，再补 Acceptance**
   - 未选择。会保留可运行但不完整的中间写模型，并延长双写路径和迁移负担。

2. **继续把正式对象放在通用 JSON `promoted_objects`**
   - 未选择。无法可靠表达 typed lifecycle、foreign key、review 和 Bundle 准入约束。

3. **把设计时数据库计数写死为 migration 断言**
   - 未选择。真实库在实施前会继续增长；固定计数会漏迁或产生假失败。

4. **仅靠操作提示停止连接，不实现 restore lock**
   - 未选择。旧进程或 companion file 仍可能在 `os.replace` 期间写入，无法保证恢复安全。

## Follow-ups

- 按 implementation spec 使用 TDD 实现统一 database layer、workflow、typed stores、review 和 Bundle integration。
- 在隔离 HOME 完成 legacy fixture migration、幂等、backup/restore 和 failure rollback 测试。
- 自动化验证全部通过后，备份并迁移真实数据库，交付 manifest、hash、postflight report 和恢复命令。
- 实现完成后更新领域、CLI、Agent skill、架构、路线图和 dashboard，使其从 target architecture 切换为 runtime truth。
