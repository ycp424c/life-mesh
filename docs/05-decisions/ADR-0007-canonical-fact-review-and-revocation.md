# ADR-0007: Canonical Fact Review And Revocation

状态：accepted
日期：2026-06-29

## Context

Canonical Fact 是 Context Bundle 的最高优先级来源，但它依赖可复核的 source reference。Obsidian Vault 等可编辑外部来源使用 Source Revision；Manual Input 不使用 SourceRevision，而使用 input record、extraction、content_hash、状态和审计事件表达来源身份。如果 source reference 失效后 Canonical Fact 仍作为已核实事实进入 Bundle，Agent 会继续使用过期或不可访问的证据；如果立即删除事实，又会丢失历史审计和用户确认记录。

Q21 需要定义 Source Revision 或 Manual Input 变 stale / missing / revoked / deleted 后，Canonical Fact 如何进入复核、如何撤销，以及 tombstone 如何级联到 Bundle、索引和审计。

## Decision

采用三段式处理：来源失效先进入复核，不立即删除；只有用户复核或策略判定后，才重新确认、修订、失效或撤销事实。

Canonical Fact 增加明确状态语义：

- `validity=valid`：事实当前可作为 `evidence_role=fact` 使用。
- `validity=needs_review`：事实依赖的必要来源已 stale / missing / revoked，不能作为可用事实进入 Bundle，只能进入报告区。
- `validity=invalid`：事实已被判定不成立。
- `validity=superseded`：事实被更新事实替代，旧事实保留历史。
- `revocation_status=active`：未被用户撤销。
- `revocation_status=revoked`：用户撤销，后续 Bundle 不得使用。

Bundle 使用硬规则：

- 只有 `validity=valid`、`revocation_status=active`、且至少有一个 current supporting source reference 的 Canonical Fact，才能进入 `slices[]` 并作为 `evidence_role=fact` 使用。
- `needs_review` / `invalid` / `superseded` / `revoked` 的事实不得进入可用上下文，只能进入 `freshness_report` 或 `excluded_sources`。
- `stale` 不是事实为假的证明，只是证据需要复核；`missing`、路径排除、授权撤销和 Manual Input 删除生成 tombstone，阻止旧来源被新检索命中。

复核动作：

- `revalidate`：用户或策略确认当前来源仍支持该 statement，绑定 current supporting source reference，恢复 `valid`。
- `revise`：statement 需要修改，生成新的 Canonical Fact，旧 fact 标记 `superseded`。
- `invalidate`：事实不再成立，标记 `invalid`。
- `revoke`：用户撤销该事实，设置 `revocation_status=revoked`，生成 Fact Tombstone。

Tombstone 级联：

- Source Tombstone：记录 Source Revision 因删除、移动到排除路径或授权撤销而不可用；它阻止旧 revision 进入新检索，并触发依赖 fact / candidate 的复核。
- Manual Input Tombstone：记录 Manual Input 因 revoke 或 delete 而不可用；它阻止 input、extraction 和 embedding 进入新检索，并触发依赖 fact / candidate / memory 的复核或停止使用。
- Fact Tombstone：记录 Canonical Fact 被撤销、失效或替代；它阻止旧 fact 进入新 Bundle，但保留历史审计链。

每次状态变化都必须生成审计事件，记录触发原因、操作者、旧状态、新状态、影响的 source reference / Fact / Bundle。

## Consequences

正向影响：

- stale 来源不会被继续当作已核实事实使用。
- 用户确认过的历史事实不会被静默删除，审计链保留。
- Bundle 规则简单清晰：可用事实必须 valid + active + current-supported。
- 删除、路径排除和授权撤销能级联到索引、facts 和候选知识。

代价：

- Canonical Fact 需要维护更多状态字段和审计事件。
- 第 1 阶段实现时必须有复核队列或报告区，不能只做静态事实表。
- 多来源支持同一事实时，需要判断是否仍有 current supporting source reference。

## Alternatives Considered

- 来源 stale 后立即删除 Canonical Fact：实现简单，但丢失历史、用户确认和审计，不适合 Personal Data OS。
- stale 后继续使用旧 fact：回答体验顺滑，但会把过期或撤销来源继续作为证据，风险不可接受。
- 每次来源变更都强制用户同步确认：安全但打断普通使用，不符合 User Confirmation 不阻塞普通回答的原则。

## Follow-ups

- CLI 契约已补充 review / revoke 命令形状；后续实现时再落 CLI 代码。
- 设计 dashboard 只读展示复核队列和 tombstone 影响范围。
- 定义多来源事实的 current support 判定规则。
