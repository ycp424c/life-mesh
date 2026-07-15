# Unified Write Model Implementation Spec

状态：active
最后更新：2026-07-15
职责边界：把 ADR-0010 和正式架构文档约束展开为 LifeMesh Phase 1 Unified Write Model 的实施、迁移与验收规格。架构决策以 ADR-0010 为准，目标架构以 `docs/03-architecture/write-model-and-migrations.md` 为准；本文不定义外部日历/任务同步、自动 Rumor source adapter、远程服务或 dashboard 写回。

正式决策与架构来源：

- [ADR-0010 Unified Write Model, Transactional Acceptance And Database Migration](../../05-decisions/ADR-0010-unified-write-model-transactional-acceptance-and-database-migration.md)
- [Unified Write Model And Migrations](../../03-architecture/write-model-and-migrations.md)

## 1. 背景

LifeMesh 已有三个可运行的本地写侧原型，但它们没有形成统一闭环：

- `candidate add` 写入 `knowledge_candidates`。
- `input promote` 写入通用 JSON 表 `promoted_objects`。
- `rumor promote` 写入 `rumor_candidate_links`。

三个模块各自打开 SQLite、各自建表、各自写审计，没有集中 schema version、foreign key、共享事务和统一 provenance。结果是 Manual Input 和 RumorClaim 能报告“已产生 Candidate”，但 `candidate list` 看不到这些 handoff；Candidate 也不能 confirm 到正式 Fact、Memory 或 Task。

本次采用完整架构、单次交付和单次切换。实现内部仍按可测试的小步骤完成，但不会保留“第一轮只接 handoff、第二轮再做 acceptance”的中间产品状态。代码与文档全部通过后，直接备份并迁移真实 `~/.lifemesh/lifemesh.db`。

## 2. 目标

本次交付必须同时完成：

1. 集中 SQLite 连接、事务、schema version、migration、backup、integrity 和恢复能力。
2. `knowledge_candidates` 成为唯一 Candidate 真相源。
3. CLI、Manual Input、RumorClaim 通过同一 Candidate handoff workflow 创建候选。
4. 实现 Candidate `add/list/show/edit/merge/defer/confirm/discard` 和过期准入。
5. 实现统一 Acceptance workflow，把确认后的候选或用户显式 promote 写入正式 Fact、Memory、Task、Event。
6. 实现 Canonical Fact 持久化、Bundle 准入、review/revalidate/revise/invalidate/revoke 和 tombstone。
7. 使用规范化 source reference/link 表表达 Candidate 和正式对象 provenance。
8. 来源 stale/missing/revoked/deleted 时创建 review item，并阻止失效 Fact/Memory 继续进入 Bundle。
9. 迁移旧 `promoted_objects`、`rumor_candidate_links` 和 legacy audit，旧表停止接受新写入。
10. 更新 ADR、领域文档、架构文档、路线图、README、skill 和 dashboard，使它们反映真实实现。
11. 备份、迁移并验收真实数据库；失败时可恢复到经校验的备份。

## 3. 非目标

- 不接入系统日历、提醒事项或外部任务应用。
- 不实现自动 RumorClaim source adapter、图片自动抽取 pipeline、自动 fact-check 或 review UI。
- 不引入 MCP server、后台服务、多用户数据库或远程托管。
- 不实现完整的 Phase 4 Memory 管理产品；本轮只提供 Phase 1 所需的最小正式 Memory 存储、查看和撤销。
- 不实现 dashboard 写回；dashboard 继续只读展示静态项目状态。
- 不允许 Agent 自行 confirm、accept、review 或 revoke。`acceptance_path=policy` 只保留数据模型能力，本轮没有可执行自动接受策略。
- Agent 推断出的偏好、关系和决策不能直接写 Memory，只能进入 Candidate 或 `auto_captured` Manual Input；用户显式 `remember` 才可走 manual Acceptance。

## 4. ADR-0010 实施约束

[ADR-0010](../../05-decisions/ADR-0010-unified-write-model-transactional-acceptance-and-database-migration.md) 已接受以下不可绕过的决策；本节只列实施必须遵守的约束，不替代 ADR：

- `knowledge_candidates` 是唯一 Candidate 真相源。
- `KnowledgeWorkflow` 是跨领域写入的唯一应用服务。
- Manual Input 与 RumorClaim 保持来源领域所有权，handoff 委托给 `KnowledgeWorkflow`。
- Candidate confirmation 和用户显式 direct promote 共用 Acceptance 与正式对象写入逻辑。
- Canonical Fact、Memory、Task、Event 使用正式领域表；`promoted_objects` 不再是长期真相源。
- provenance 使用规范化 `source_references`、`candidate_source_links`、`object_source_links`；JSON 只用于不可结构化 metadata 和 legacy snapshot。
- handoff、acceptance、状态变化、review、tombstone 和 audit 必须在同一数据库事务内提交。
- 所有连接由统一数据库层创建，并强制 `foreign_keys=ON`、busy timeout、私有权限和 versioned migration。
- 真实库迁移前必须使用 SQLite online backup API 备份，迁移必须幂等、可验证、可恢复。

## 5. Module 边界

### 5.1 `lifemesh/database.py`

负责：

- `LifeMeshDatabase` 连接工厂。
- `PRAGMA foreign_keys=ON`、`busy_timeout`、row factory。
- `BEGIN IMMEDIATE` 写事务与 rollback。
- `schema_migrations` 和 checksum 验证。
- SQLite online backup、manifest、integrity/foreign-key checks。
- 数据库文件 `0600`、目录 `0700`。

它不负责领域校验和对象状态机。

### 5.2 `lifemesh/migrations.py`

负责顺序、幂等、可校验的 migration。每个 migration 有稳定 ID、名称和 checksum。同 ID 不同 checksum 必须硬失败，不能用 `INSERT OR IGNORE` 隐藏冲突。

### 5.3 `lifemesh/knowledge_workflow.py`

对外提供深接口：

- `handoff_candidate(...)`
- `edit_candidate(...)`
- `merge_candidate(...)`
- `defer_candidate(...)`
- `confirm_candidate(...)`
- `promote_manual_input(...)`
- `review_fact(...)`
- `cascade_source_change(...)`

所有跨表事务、幂等、状态检查、provenance 复制和审计在此完成。CLI、Manual Input、RumorClaim 不自行拼接跨领域 SQL。

### 5.4 `lifemesh/candidates.py`

保留 Candidate repository、读取模型和字段校验；不再自行创建连接和 schema，不理解 RumorClaim 或 Manual Input。

### 5.5 `lifemesh/canonical_store.py`

负责正式 Canonical Object 的 typed persistence、Fact Review 和 Bundle retrieval：

- Canonical Fact
- Memory
- Task
- Event

### 5.6 来源模块

- `manual_input.py`：只拥有 Manual Input、asset、extraction、embedding 和检索。
- `rumor_claims.py`：只拥有 RumorClaim、mentions、review queue 和 lead-only retrieval。
- `obsidian.py`：继续拥有 Vault scan、Source Revision 和 stale/missing 检测，并把当前 source status 同步给统一 provenance 层。

### 5.7 `lifemesh/cli.py`

只负责 parser、输入规范化、workflow dispatch 和 JSON 输出，不持有业务事务。

## 6. 目标数据模型

### 6.1 数据库与审计

`schema_migrations`

- `migration_id TEXT PRIMARY KEY`
- `name TEXT NOT NULL`
- `checksum TEXT NOT NULL`
- `applied_at TEXT NOT NULL`

`migration_legacy_map`

- `legacy_table`
- `legacy_id`
- `new_type`
- `new_id`
- `metadata_json`
- 唯一约束 `(legacy_table, legacy_id, new_type)`

`audit_events`

- `event_id`
- `aggregate_type`
- `aggregate_id`，允许 legacy deleted target 为 null
- `action`
- `actor_type`
- `actor_id`
- `old_state_json`
- `new_state_json`
- `reason`
- `correlation_id`
- `legacy_event_key`，可选且唯一
- `occurred_at`

`file_operations`

- `operation_id`
- `operation_type`: `promote_staged_asset | delete_managed_asset`
- `idempotency_key TEXT UNIQUE`
- `source_path`
- `target_path`
- `status`: `pending | completed | failed`
- `attempts`
- `last_error`
- `created_at`
- `completed_at`

### 6.2 Source Reference 与 Tombstone

`source_references`

- `source_ref_id`
- `source_kind`: `obsidian_revision | manual_input | manual_input_extraction | rumor_claim | user_assertion | opaque`
- `adapter`
- `source_item_id`
- `revision_id`
- `content_hash`
- `citation_label`
- `sensitivity`
- `status`: `current | stale | missing | revoked | deleted | inactive | unknown`
- `metadata_json`
- `identity_key`，由结构化来源身份计算且唯一
- `created_at`
- `updated_at`

无法解析的旧字符串 ref 迁为 `opaque/status=unknown`，不得伪造 revision、content hash 或 current 状态。

`identity_key` 的规则固定如下：

- Obsidian：`obsidian_revision:<vault-id>:<note-path>:<content-hash>`。编辑产生新 ref，旧 ref 原子标记 stale。
- Manual Input：有内容时为 `manual_input:<input-id>:<content-hash>`；deleted 且内容已清除时为 `manual_input:<input-id>:tombstone:<deleted-at>`。它不是 SourceRevision，但每个内容快照有独立 source reference；update 创建新 ref，旧 ref stale 并触发级联。
- Manual Input Extraction：`manual_input_extraction:<input-id>:<extraction-id>:<content-hash>`。
- RumorClaim：`rumor_claim:<rumor-claim-id>`；claim body 不可编辑，dismiss/expire 只更新 status。
- User Assertion：`user_assertion:<assertion-id>:<statement-hash>`，在用户撤销前 current。
- Opaque：`opaque:<sha256(raw-ref)>`，永远不能作为 Fact 的唯一 supporting source。

迁移时为全部现有 Manual Input 和 RumorClaim 建立 source reference，而不只为已 handoff 的 7 条建立：Manual Input active/promoted/auto-captured → current，revoked → revoked，deleted → deleted；Rumor parked/reviewed_parked/candidate_created → current，dismissed/expired → inactive。source metadata 不复制 claim/input 正文。

`source_tombstones`

- `tombstone_id`
- `source_ref_id` FK
- `reason`
- `created_by`
- `operation_key TEXT UNIQUE`
- `created_at`

用户手动断言通过 `source_kind=user_assertion` 建模。它是合法 source reference，在用户撤销前为 current；因此 user-asserted Fact 可以满足 current supporting source 门槛，而不是成为无来源事实。

### 6.3 Candidate

`knowledge_candidates`

- `candidate_id TEXT PRIMARY KEY`
- `type TEXT NOT NULL CHECK (type IN ('fact', 'preference', 'relationship', 'task', 'decision'))`
- `summary TEXT NOT NULL`
- `confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1)`
- `confidence_basis`
- `risk TEXT NOT NULL CHECK (risk IN ('low', 'medium', 'high'))`
- `sensitivity TEXT NOT NULL CHECK (sensitivity IN ('Public', 'Internal', 'Private', 'Sensitive', 'Restricted'))`
- `status TEXT NOT NULL CHECK (status IN ('pending', 'deferred', 'confirmed', 'merged', 'discarded'))`
- `confirmation_required INTEGER NOT NULL CHECK (confirmation_required IN (0, 1))`
- `why_suggested TEXT NOT NULL`
- `expires_at`
- `deferred_until`
- `merged_into_candidate_id` FK
- `resolved_at`
- `handoff_key`，来源 handoff 使用且唯一，纯 CLI add 可为空
- `created_at`
- `updated_at`

`transient` Candidate 不持久化。旧 `inbox`、`confirm_required` 迁为 `pending`；旧 `discard` 迁为 `discarded`。`expired` 是由时间计算的 effective status，不重复持久化。

Candidate sensitivity 是显式值与全部来源 sensitivity 的最大值。handoff、merge、edit source 和 confirm 只能保持或提高敏感度，不能降低。默认 `candidate list` 使用 `--sensitivity-cap Private`；Sensitive/Restricted 需要显式提高 cap，confirm 时目标对象继承 Candidate sensitivity。

`candidate_source_links`

- `candidate_id` FK
- `source_ref_id` FK
- `relationship`: `derived_from | supports | contradicts | legacy_reference`
- `required INTEGER`
- `legacy_payload_json`，仅迁移兼容
- `legacy_risk_label`，仅迁移兼容
- `created_at`
- 唯一约束 `(candidate_id, source_ref_id, relationship)`

`candidate_decisions`

- `decision_id`
- `candidate_id` FK
- `decision`: `edit | defer | resume | confirm | merge | discard`
- `actor_type`
- `actor_id`
- `reason`
- `payload_json`
- `decided_at`

### 6.4 Canonical Object

`canonical_objects`

- `object_id TEXT PRIMARY KEY`
- `object_type TEXT NOT NULL CHECK (object_type IN ('fact', 'memory', 'task', 'event'))`
- `sensitivity TEXT NOT NULL CHECK (sensitivity IN ('Public', 'Internal', 'Private', 'Sensitive', 'Restricted'))`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`

`canonical_objects` 不复制领域状态，避免与 typed table 漂移。各 typed table 是自身状态的唯一真相源：

`canonical_facts`

- `fact_id TEXT PRIMARY KEY REFERENCES canonical_objects(object_id)`
- `statement TEXT NOT NULL`
- `confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1)`
- `risk TEXT NOT NULL CHECK (risk IN ('low', 'medium', 'high'))`
- `validity TEXT NOT NULL CHECK (validity IN ('valid', 'needs_review', 'invalid', 'superseded'))`
- `revocation_status TEXT NOT NULL CHECK (revocation_status IN ('active', 'revoked'))`
- `review_reason TEXT`
- `review_started_at TEXT`
- `reviewed_at TEXT`
- `superseded_by_fact_id TEXT REFERENCES canonical_facts(fact_id)`

`memories`

- `memory_id TEXT PRIMARY KEY REFERENCES canonical_objects(object_id)`
- `text TEXT NOT NULL`
- `memory_type TEXT NOT NULL CHECK (memory_type IN ('explicit', 'inferred', 'contextual'))`
- `scope TEXT`
- `confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1)`
- `confirmation_status TEXT NOT NULL CHECK (confirmation_status IN ('manual', 'confirmed'))`
- `status TEXT NOT NULL CHECK (status IN ('active', 'needs_review', 'revoked', 'superseded'))`
- `expires_at TEXT`

`tasks`

- `task_id TEXT PRIMARY KEY REFERENCES canonical_objects(object_id)`
- `title TEXT NOT NULL`
- `description TEXT`
- `due_at TEXT`
- `task_status TEXT NOT NULL CHECK (task_status IN ('open', 'in_progress', 'completed', 'cancelled'))`

`events`

- `event_id TEXT PRIMARY KEY REFERENCES canonical_objects(object_id)`
- `title TEXT NOT NULL`
- `starts_at TEXT NOT NULL`
- `ends_at TEXT`
- `timezone TEXT`
- `event_status TEXT NOT NULL CHECK (event_status IN ('scheduled', 'occurred', 'cancelled'))`

`object_source_links`

- `object_id` FK → `canonical_objects`
- `source_ref_id` FK
- `relationship`: `derived_from | supports | contradicts`
- `required INTEGER`
- `created_at`
- 唯一约束 `(object_id, source_ref_id, relationship)`

`acceptances`

- `acceptance_id`
- `candidate_id` nullable FK
- `object_id` FK
- `acceptance_path`: `user_confirmation | manual | policy`
- `accepted_by`
- `policy_id` nullable
- `idempotency_key`，Candidate confirm 或 direct promote 的稳定唯一键
- `payload_hash`，direct promote 的 normalized payload hash
- `accepted_at`
- Candidate acceptance 唯一约束，防止重复 confirm。

本轮不提供可执行 policy acceptance；数据库允许该值只是为了不阻断未来演进。

`object_tombstones`

- `tombstone_id`
- `object_id` FK
- `reason`
- `replacement_object_id` nullable FK
- `operation_key TEXT UNIQUE`
- `created_at`

### 6.5 Review

`review_items`

- `review_id`
- `candidate_id` nullable FK
- `object_id` nullable FK
- 两者恰好一个非空
- `trigger_source_ref_id` FK
- `review_kind`: `source_stale | source_missing | source_revoked | source_deleted | conflict`
- `status`: `open | resolved | dismissed`
- `reason`
- `opened_at`
- `resolved_at`
- `resolution`
- `operation_key TEXT UNIQUE`

同一 subject、trigger source、review kind 同时只能存在一条 open review；使用 partial unique index 保证重复 source scan 不重复开单。Source tombstone 同样使用稳定 `operation_key` 防止重复写入。

## 7. 状态机与准入

### 7.1 Candidate

```text
pending
  -> deferred -> pending
  -> confirmed
  -> merged
  -> discarded
  -> expired
```

- 默认 list 只展示有效 `pending` 和到期可恢复的 `deferred`。
- `confirmed/merged/discarded` 只有显式 `--status` 才展示；`--status expired` 查询时间投影。
- stored status 只保存 `pending/deferred/confirmed/merged/discarded`。`expires_at <= now` 时 effective status 为 expired；`deferred_until <= now` 时 effective status 为 pending。
- 时间投影不写数据库、不生成 audit；edit/defer/resume 等显式动作才写 decision/audit。show 同时返回 `stored_status` 和 `effective_status`，confirm 按 effective status 校验。
- merge 把 loser 的 source links 原子复制给 winner，loser 标记 merged。
- merge 只允许相同 Candidate type；跨 type 必须先 edit，避免目标对象映射含糊。
- Agent 只能 add，不能 confirm。
- required source 失效时不把 Candidate 静默 discard；创建 review item 并阻止 confirm，用户可 edit source、merge 或 discard。

### 7.2 Confirm 映射

- `fact` → Canonical Fact
- `task` → Task
- `preference | relationship | decision` → Memory

Candidate confirmation 必须创建 decision、acceptance、typed object、object source links、audit，并把 Candidate 标记 confirmed；任一步失败全部 rollback。

Fact Candidate 的 `derived_from` Rumor/Manual link 不自动等于 supporting evidence。confirm 时若没有 current `supports` link，用户确认动作同时创建明确的 `user_assertion` source reference；因此事实来源是用户确认，而不是把 RumorClaim 偷换成已验证证据。Opaque legacy ref 永远不能单独满足 current supporting source 门槛。

### 7.3 Manual Input

- `input promote --to candidate` 走 Candidate handoff，不走 Acceptance。
- `input promote --to fact|memory|task|event` 走 manual Acceptance。
- 一个 input 可以派生多个不同对象；相同 input、target type、normalized payload hash 幂等返回既有对象。
- `promoted` 只表示至少存在一个派生对象，真实关系以 source/object links 和 acceptance 为准。
- revoked/deleted input 不得产生新 handoff 或 acceptance。

### 7.4 RumorClaim

- parked 或 reviewed_parked 可 handoff 到 Candidate。
- candidate_created 不得重复 promote；幂等重试返回已有 Candidate。
- dismissed/expired 不得 handoff。
- RumorClaim 永远不能直接进入 Fact、Memory、Task、Event。
- 用户确认 Candidate 只确认“Candidate 进入某个正式对象”；RumorClaim 本身仍保留未验证历史语义。

### 7.5 Canonical Fact

严格保持 ADR-0007：

- 只有 `validity=valid`、`revocation_status=active` 且至少一个 current supporting source reference，才能以 `evidence_role=fact` 进入 Bundle。
- source 失效后进入 `needs_review`，不立即删除。
- `revalidate` 绑定 current source 并恢复 valid。
- `revise` 创建新 Fact，旧 Fact superseded，并建立 replacement tombstone。
- `invalidate` 设置 invalid。
- `revoke` 设置 revoked 并创建 object tombstone。

多来源判定算法：

1. `derived_from` 只解释来源，不计入事实支持。
2. `supports` 才计入 Fact support；`contradicts` 只开 conflict review。
3. 任一 `required=1` 的 supports link 非 current，Fact 进入 needs_review。
4. 没有任何 current supports link，Fact 进入 needs_review。
5. 只有全部 required supports current 且至少一个 supports current，Fact 才保持 valid。
6. optional supports 失效但仍有其他 current support 时只记录 audit/freshness，不停用 Fact。

Pending Candidate 的 required source 非 current 时创建 open review 并阻止 confirm；Candidate 不被静默 discard。Confirmed Candidate 不重新打开，改由其正式对象的 source links 和 review item 管理。

### 7.6 Memory、Task、Event

- Memory source 失效时将 `memories.status=needs_review`，停止进入 Bundle context。
- Task/Event source 失效不静默取消业务状态，只创建 review item；它们本轮不进入 Bundle。
- revoke 后 Memory 标记 revoked；Task/Event 分别标记 cancelled 并创建 object tombstone，全部保留历史。

### 7.7 Review 闭环

- Fact review 只通过 `fact review revalidate/revise/invalidate` 或 `fact revoke` 解决。
- Candidate review 通过 edit source、merge 或 discard 解决；存在 open review 时 confirm 被拒绝。
- Memory/Task/Event review 通过通用 `review resolve --action keep|revoke` 解决。
- `keep` 会创建明确的 `user_assertion` source reference、关闭 review；Memory 恢复 active，Task/Event 保持原业务状态。
- `revoke` 委托对象自身 revoke/cancel，并关闭 review。
- 所有 resolve 都必须在同一事务写 source link、对象状态、review resolution 和 audit，不能产生永久不可达的 needs_review。

## 8. 原子事务

必须原子化：

1. Rumor handoff：Candidate + source reference/link + Rumor status + decision/audit。
2. Manual Input handoff：Candidate + source reference/link + input status + audit。
3. Candidate confirm：decision + acceptance + canonical object/typed row + object source links + Candidate status + audit。
4. Manual direct promote：acceptance + canonical object/typed row + object source links + input status + audit。
5. Source change：source status + tombstone + dependent review items + fact/memory usage state + audit。
6. Fact revise/revalidate/invalidate/revoke：Fact 状态、新旧关系、review、tombstone、audit。

外部 LM Studio 请求不得在写事务内执行。Manual Input update 先完成外部计算，再用 content hash 乐观检查提交结果。

文件删除不能伪装成可回滚的 SQLite 操作。managed asset 使用 file-operation outbox：数据库先记录待执行操作，提交后执行；失败保留可重试状态。新增截图先进入私有 staging，数据库提交成功后原子 rename。

## 9. CLI

完整交付包含：

```text
lifemesh db status
lifemesh db migrate [--dry-run | --apply]
lifemesh db restore <backup-manifest> --apply
lifemesh db reconcile-files [--dry-run | --apply]

lifemesh candidate add/list/show/edit/merge/defer/resume/confirm/discard

lifemesh fact add/show
lifemesh fact review list/show/revalidate/revise/invalidate
lifemesh fact revoke

lifemesh remember <text>
lifemesh memory list/show/revoke
lifemesh task add/list/show/close/revoke
lifemesh event list/show/cancel/revoke

lifemesh review list/show
lifemesh review resolve <review-id> --action keep|revoke

lifemesh input promote
lifemesh rumor promote
```

`db migrate` 默认 dry-run，只有 `--apply` 修改真实库。本次在全套验证通过后由实施流程显式调用 `--apply`。

`fact add`、`task add`、`remember` 与 Manual Input direct promote 共用 Acceptance/正式对象 repository，不形成旁路。

`fact add` 必须带 source ref，或显式使用 `--user-asserted` 创建 `user_assertion` source reference；不能静默创建无来源、可进入 Bundle 的事实。

Candidate 参数固定为：

- `add <summary> --type ... [--source-ref ...] [--confidence 0.5] [--risk medium] [--sensitivity Private] [--why-suggested ...] [--expires-at ...]`
- `list [--status ...] [--type ...] [--sensitivity-cap Private] [--limit 20]`
- `edit <id> [--summary ...] [--type ...] [--confidence ...] [--risk ...] [--sensitivity ...] [--expires-at ...] [--add-source-ref ...] [--remove-source-ref ...]`；sensitivity 不得低于来源最大值。
- `merge <winner-id> <loser-id> [--reason ...]`；winner scalar fields 不自动改变，source links 合并，sensitivity 取最大值。
- `defer <id> [--until ...] [--reason ...]` 与 `resume <id>`。
- `confirm <id> [--user-asserted] [--accepted-by local-user]`。没有 current supports 的 Fact Candidate 必须显式 `--user-asserted`，不能把 derived Rumor link 自动升级为 supports。

本地 CLI 没有身份认证，无法从技术上判断调用者是否为 Agent。“Agent 不能 confirm”是 capability/governance 约束：skill 和 Agent runtime 在没有用户当前明确指令时不得调用 confirm/review/revoke；CLI 审计 actor 固定记录实际传入的本地 actor，不宣称它是鉴权 token。

file outbox 在原命令返回前立即尝试一次；失败时领域记录已不可检索，但响应必须返回 `file_cleanup_pending=true` 和非零状态。managed 文件仍留在私有目录，后续用 `db reconcile-files --apply` 幂等重试。

## 10. Bundle 集成

新增 Canonical Context retriever：

- valid/current-supported Fact → `evidence_role=fact`
- active、未过期 Memory → `evidence_role=context`
- invalid/review/revoked/superseded 对象只进入报告区

`bundle --source all` 在原有 Obsidian、Manual Input candidates 之外加入正式 Fact 和 Memory，再由现有 BundleAssembler 统一按 `Canonical Fact > Memory > Source Reference > lead` 组装。

RumorClaim 仍只在 `--source rumor` 或 `--include-unverified` 时作为 lead。持久化 Candidate inbox 默认不进入普通 Bundle；本轮不新增“把整个 inbox 塞进回答上下文”的行为。

## 11. 真实库迁移

### 11.1 迁移前动态基线

真实库会在设计完成与实施之间继续变化，因此迁移不得把设计时计数当成验收常量。`db migrate --dry-run` 必须在持有迁移锁后生成不含个人内容的 preflight manifest，并用同一份 manifest 驱动迁移后守恒校验。

2026-07-15 的只读规划快照仅用于证明数据库已经发生漂移，不是实施验收值：

- Manual Input 9：active 3、promoted 1、revoked 1、deleted 4。
- `promoted_objects` 1，类型 candidate。
- RumorClaim 125：candidate_created 6、dismissed 33、parked 46、reviewed_parked 40。
- `rumor_candidate_links` 6；`knowledge_candidates` 表尚不存在。
- 当前可推导 legacy Candidate handoff 7：Manual Input 1 + RumorClaim 6。
- 当前 primary source identity 134：Manual Input 9 + RumorClaim 125；额外 legacy refs 必须规范化后去重计算。
- 当前 source tombstone 38：revoked/deleted Manual Input 5 + dismissed RumorClaim 33。
- 正式 Fact/Memory/Task/Event 当前均为 0；初始 review item 0。
- 有 1 条 deleted input 的 audit-only promotion；只迁 audit，禁止复活为 Candidate。

preflight manifest 必须动态记录并派生：

1. 每张 legacy 业务表的按状态/类型聚合计数，以及 FTS、embedding、sqlite-vec 的聚合计数。
2. Candidate 期望集合：existing `knowledge_candidates`、`promoted_objects(candidate)`、`rumor_candidate_links` 按稳定 legacy identity 合并，排除 audit-only deleted promotion。
3. Source Reference 期望集合：全部 Manual Input、RumorClaim、existing Candidate refs 和 legacy payload refs 先规范化 identity，再全局去重；不得用 `manual_count + rumor_count` 代替实际 identity 集合。
4. Candidate/object source link 期望集合：按规范化 `(subject, source_ref, relationship)` 去重，并记录 required 语义。
5. Tombstone 期望集合：根据迁移时真实 revoked/deleted/inactive 状态派生。
6. Canonical Object、review item 和 audit 期望集合：根据实际 legacy 类型、source status 和稳定 event key 派生。

迁移后验收比较 preflight 与 postflight 的集合摘要和计数；任何未解释的新增、丢失或 identity 冲突都 rollback。

### 11.2 Legacy 字段映射

旧 handoff 的 confidence 是 `low/unverified` 文本，risk 是业务标签，不能直接写入新 CHECK：

- 非 deleted 来源的原 payload 保留在 legacy snapshot/audit。deleted input 只迁 event key、input/object ID、target type、时间、payload hash 和 `legacy_target_missing`；不得把已删除正文重新复制进新表。
- `low/unverified` 映射为 `confidence=0.25`。
- `confidence_basis=legacy_label_mapping`。
- Sensitive/Restricted 或 relationship → high risk，其余 → medium。
- 原 risk 保存为 `legacy_risk_label`。
- 未识别值硬失败，不静默默认。
- 旧 object ID 原样成为 Candidate ID。
- Rumor 到期时间不继承给已 handoff Candidate；来源有效期保留在 source metadata。
- legacy source ref 先解析已知 `manual-input:<id>` / `rumor:<id>` / Obsidian 格式并复用结构化 ref；与 primary source 相同则去重，不额外建 link。只有无法解析的 ref 才创建 opaque/legacy_reference；可解析但不同的 ref 仅在 evidence-eligible/current 时作为 supports，否则作为 derived_from。

完整 legacy 映射：

- 统一 confidence normalizer：合法 0..1 数字保留；`low/unverified` → 0.25；缺失 Candidate/Fact → 0.5；缺失显式 Memory → 1.0；其他字符串硬失败。所有默认/映射写入 migration audit。
- 统一 risk normalizer：`low/medium/high` 保留；否则 Sensitive/Restricted 或 relationship → high，其余 → medium；原标签保留在 legacy snapshot/audit。
- 统一 sensitivity：取来源最大值；没有可解析来源时保守使用 Private。
- `why_suggested` 映射必须确定且非空：existing Candidate 保留非空原值，否则使用 `legacy_candidate_migration`；Manual Input handoff 使用 `legacy_manual_input_handoff`；Rumor handoff 使用 `legacy_rumor_handoff`。这些值只解释迁移来源，不伪造用户理由。
- `handoff_key` 映射必须稳定：existing Candidate 保留原值，旧 direct CLI Candidate 可为空；Manual Input handoff 使用 `manual-input:<input-id>:candidate:<normalized-payload-sha256>`；Rumor handoff 使用 `rumor:<rumor-claim-id>:candidate`。相同 key 内容一致时 noop，内容冲突时 rollback。
- 已存在的旧 `knowledge_candidates` 先改名为受管 legacy table，再重建新表，保留 candidate ID、summary/type/time。`inbox/confirm_required/transient` → pending，`discard` → discarded；全部未确认旧候选 `confirmation_required=1`。可解析 current evidence ref → supports，其他 ref → derived_from/legacy_reference；表不存在也必须可迁移。
- 旧 `candidate_audit_events` 使用稳定 legacy event key 回填统一 audit。
- `promoted_objects(candidate)` → Candidate + Manual Input `derived_from` primary source link；status=pending、confirmation_required=1、sensitivity=max(source)，并使用上面的 Manual Input `why_suggested` 与 `handoff_key`。
- `rumor_candidate_links` → Candidate + RumorClaim `derived_from` primary source link；status=pending、confirmation_required=1、sensitivity=max(source)，并使用上面的 Rumor `why_suggested` 与 `handoff_key`。Rumor link 不得因迁移自动变为 `supports`。
- `promoted_objects(fact)` → Canonical Fact + manual Acceptance + Manual Input `derived_from/supports` links；revocation_status=active；有 current support 时 validity=valid，否则 needs_review；accepted_by=legacy_local_user，accepted_at=created_at。
- `promoted_objects(memory)` → Memory + manual Acceptance + source link；memory_type=explicit、confirmation_status=manual、status 在 source current 时 active，否则 needs_review；accepted_by=legacy_local_user，accepted_at=created_at。
- `promoted_objects(task)` → Task + manual Acceptance + source link；title 必填，description/due_at 原样可空，合法旧 status 保留，否则 task_status=open；source 非 current 时开 review 但不取消 task。
- `promoted_objects(event)` → Event + manual Acceptance + source link；title/starts_at 必填，ends_at/timezone 原样可空，合法旧 status 保留，否则 event_status=scheduled；source 非 current 时开 review 但不取消 event。
- 真实库后四类当前为 0，但 migration fixture 必须覆盖，不允许只为当前数据写特例。
- 旧 `promoted_objects`、`rumor_candidate_links` 和 legacy audit 保留只读，不再接受新写入。

### 11.3 备份与迁移顺序

1. 在 `~/.lifemesh/.database.lock` 使用 `fcntl.flock` 获取 exclusive lock；所有新数据库连接在存活期持有 shared lock，因此 migration 能拒绝新版本并发访问。
2. 检查 DB 存在、权限、journal/WAL/SHM 和活跃连接。旧版本进程不遵守 lockfile，因此 `lsof`/companion-file 检查是额外 preflight；检测到活跃 writer 或变化中的 WAL 时硬失败。
3. guard connection 对真实库执行 `BEGIN IMMEDIATE`，在写入任何 DDL/DML 前阻止其他 writer。
4. 独立只读 source connection 在 guard connection 持锁期间执行 SQLite online backup API；禁止在持有 `BEGIN IMMEDIATE` 的同一 connection 上调用 `backup()`，避免 Python sqlite3 自阻塞。禁止 `.dump` 或逻辑重建，以保留 FTS5/sqlite-vec 页面。
5. 设置备份目录 `0700`、文件 `0600`。
6. 生成 manifest：源/备份路径、size、SHA-256、schema、聚合计数、时间。
7. 对备份执行 integrity check；失败立即 rollback，禁止继续迁移。
8. 在已持有的写事务中创建完整 schema、索引、FK、migration record。
9. 按 preflight identity 集合先回填全部 Manual Input、RumorClaim、existing Candidate 和 legacy payload Source Reference；同 identity 必须去重，冲突必须 rollback。
10. 再按 preflight Candidate 集合回填 Candidate，并只引用第 9 步已存在的 Source Reference 创建 source links；`foreign_keys=ON` 下不得依赖 deferred FK 或插入顺序巧合。
11. 回填 legacy audit；audit-only deleted promotion 只保留为 `legacy_target_missing`。
12. 生成 revoked/deleted/inactive source tombstone 和必要 review item。
13. 执行所有计数、冲突、孤儿、checksum 断言后才 commit。
14. 使用新连接执行 post-migration 验收和 CLI smoke test。
15. 收紧 `~/.lifemesh/raw-assets/**`：目录 `0700`、managed files `0600`，并记录 security hardening audit/report。

权限收紧使用 `lstat`，遇到 symlink 直接拒绝并报告，禁止跟随 symlink chmod 到 managed tree 之外。

自动化测试必须真实执行“guard connection 持有 BEGIN IMMEDIATE + 独立 read-only source connection online backup + guard connection 继续 migration”的连接序列，证明不阻塞且备份与迁移前快照一致。

旧表原样保留、停止新写入，不在本次物理删除。迁移报告明确标记它们为 legacy read-only。

### 11.4 幂等

- 重跑 migration 后 Candidate、Source Reference、source link、tombstone、review 和 audit 集合必须与首次 postflight manifest 相同，不得按当时计数倍增。
- legacy ID 已存在且规范化内容一致 → noop。
- legacy ID 已存在但内容冲突 → rollback。
- source link 依靠唯一约束防重。
- legacy audit 使用稳定 event key 防重。
- Rumor/Manual handoff 重试返回既有对象，不重复创建。

### 11.5 回滚

若 commit 后验收失败，`db restore` 必须执行：

1. 获取与 migration 相同的 `~/.lifemesh/.database.lock` exclusive lock；获取失败时不得继续。
2. 复用 migration preflight 检查旧版本进程、`lsof`、活跃连接和变化中的 WAL/SHM/journal；只提示“停止连接”不算通过。
3. 校验 manifest 的 HOME、目标路径、备份 size/SHA-256 和 integrity，并确认目标位于受管目录。
4. 关闭 restore 自身用于校验的 SQLite connection；`os.replace` 前不得持有目标数据库 connection。
5. 将失败库及其 companion files 移入同一受管 forensic 目录，保留原权限和 manifest，不覆盖原备份。
6. 将备份恢复到目标目录临时文件，设置 `0600`，fsync 文件和父目录后使用 `os.replace` 原子替换数据库。
7. 在仍持有 exclusive lock 时清理目标路径残留 companion files，再用新只读连接复查 integrity、旧表聚合计数和 CLI smoke test。
8. 验收完成后才释放 exclusive lock；备份和 forensic 库保留到人工确认完成。

`db restore` 只接受 `~/.lifemesh/backups/` 受管目录中的 manifest；manifest 的 HOME、数据库绝对路径、backup hash/size 必须与当前目标一致。任何 `..`、symlink escape 或跨 HOME restore 都拒绝，避免路径注入和误覆盖。

## 12. 错误处理和安全

- 所有领域错误转换成稳定 CLI 错误，不输出 traceback 或个人 payload。
- migration dry-run/report 只输出 schema、计数、状态和风险，不输出 claim/input/object 内容。
- migration checksum 不匹配、备份校验失败、ID collision、unknown legacy label、orphan link、foreign key failure 均为硬失败。
- 默认 sensitivity cap 保持不变；Sensitive/Restricted 不因迁移进入普通 Bundle。
- Agent 不能通过 CLI contract 绕过 Candidate confirmation。
- RumorClaim 不能直接 accept。
- 用户删除/撤销数据后，不得因 audit backfill 或迁移恢复为可用对象。

## 13. 测试与验收

必须使用 TDD，并覆盖：

### Database/Migration

- 空库创建完整 schema。
- legacy 库到新 schema 的确定性迁移。
- Candidate 表不存在时仍可迁移。
- Candidate 旧表已存在时重建、保 ID、迁 audit。
- legacy promoted fact/memory/task/event 的通用映射。
- 旧字段 normalization。
- audit-only deleted promotion 不复活。
- 重跑 migration 幂等。
- checksum mismatch、ID collision、orphan、unknown label 回滚。
- online backup、manifest、restore。
- FTS5/sqlite-vec 表和数据不变。
- DB/backup/raw-assets 权限。

### Handoff/Candidate

- CLI、Manual Input、RumorClaim 都进入同一 inbox。
- Rumor duplicate promote 幂等。
- confidence/risk/source refs 统一。
- sensitivity=max(source)，默认 cap 隔离 Sensitive/Restricted，confirm 不得降级。
- Manual Input update/Obsidian revision change 创建新 source ref、旧 ref stale 并触发级联。
- edit/merge/defer/resume/expiry/discard。
- merged source links 不丢失。
- expired/discarded/merged Candidate 不能 confirm。

### Acceptance/Canonical Object

- 每种 Candidate type 的 confirm 映射。
- Manual direct promote 与 Candidate confirm 共用正式对象 schema。
- confirm 重试幂等。
- 事务中任一步失败整体 rollback。
- provenance 和 acceptance_path 正确。
- derived_from Rumor 不自动变 supports；无 supports Fact 必须显式 user assertion。

### Review/Tombstone/Bundle

- source stale/missing/revoked/deleted 触发 review。
- 多来源 required/optional support 判定。
- Fact 进入 needs_review 后不进 Bundle。
- revalidate/revise/invalidate/revoke。
- Fact revise 新旧关系和 tombstone。
- active Memory 可作 context，needs_review/revoked/expired Memory 不进入 Bundle。
- Candidate/Memory/Task/Event review 都有可达 resolve 路径。
- Rumor 仍只能作 lead。
- BundleAssembler 优先级和现有 source-neutral 行为不回归。

### 完整验证链

```text
git diff --check
python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m compileall lifemesh
node --check dashboard/project-state.js
node --check dashboard/app.js
```

真实库迁移后额外验证：

- `integrity_check=ok`
- `foreign_key_check` 为空
- Candidate、primary source links 和全部 candidate source links 与 preflight 派生集合一致
- Source Reference identity 集合与 preflight 规范化去重结果一致
- source tombstone、正式对象和 review item 集合与 preflight 状态派生结果一致
- audit-only deleted promotion 未创建 Candidate
- 原 Manual/Rumor/embedding/FTS 聚合计数不变
- sqlite-vec 配置加载后原向量检索可运行
- 迁移重跑为 noop
- 新增/confirm/review 的临时 smoke 数据在隔离事务或临时 HOME 验收，不污染真实个人数据

## 14. 文档和看板同步

设计评审阶段已经新增 ADR-0010，并同步 architecture overview、write-model architecture、Phase 1 roadmap、backup/recovery、README、docs map 和 dashboard。实现完成时还必须把运行时事实同步到：

- `docs/02-domain/`：Candidate、Canonical Fact/Object、Memory、Provenance、Manual Input、RumorClaim、Context Bundle、Data Map。
- `docs/03-architecture/`：更新 data layers、system map、CLI、Agent access、security/audit；`write-model-and-migrations.md` 从 target architecture 更新为 implemented truth。
- `docs/04-roadmap/`：Phase 1 plan、phases、evaluation criteria、user stories、non-goals。
- `docs/01-governance/retention-and-deletion.md`。
- `docs/07-security/backup-and-recovery.md`。
- `README.md`、`docs/README.md`、ADR index。
- `skills/lifemesh/SKILL.md`；它是全局 skill symlink 目标，更新会同步影响全局使用。
- `dashboard/project-state.js`：摘要、进度、Now/Next、system map、ADR 数量、Candidate/Fact Review 状态、Rumor handoff、recent changes。

如果 dashboard 现有数据结构足够，不修改 HTML/CSS/app.js；若新增展示结构，则同步更新看板维护规则。

## 15. 完成定义

任务仅在以下条件全部满足时完成：

1. 完整写模型代码、测试、ADR、文档、skill 和 dashboard 同步。
2. 旧写路径全部停写，所有新写入走统一 workflow。
3. 自动化测试和静态检查全部通过。
4. 真实库完成 online backup、manifest、migration 和 post-check。
5. preflight 发现的全部 legacy Candidate handoff 可在统一 inbox 查询，且没有 audit-only deleted promotion 被复活。
6. 真实库旧业务计数和向量检索没有回归。
7. 真实库 migration 重跑幂等。
8. 候选确认、正式对象、Fact Review 和 Bundle 准入在隔离 HOME 完成端到端验收。
9. 备份路径、hash、迁移报告和恢复命令已交付给用户。
10. 明确说明 dashboard 已同步；若展示结构未改，说明现有结构足以承载新状态。
