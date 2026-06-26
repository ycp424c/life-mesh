# ADR-0005: Personal Context Layer

状态：accepted
日期：2026-06-26

## Context

LifeMesh 的第一阶段如果只做原文片段检索，会退化成普通 RAG；如果围绕 Obsidian 做知识地图，又会过拟合第一个数据源。项目目标是 Personal Data OS，需要一个能跨数据源复用的上下文层。

## Decision

第一阶段目标定义为 Personal Context Layer。

Personal Context Layer 负责把 Source Adapter 中的数据转换为任务级上下文，包括 `ContextSlice`、`ContextBundle`、`KnowledgeCandidate` 和 `UserConfirmation`。Obsidian Vault 只是第一个验证适配器，用于验证这套 source-neutral 机制。

第一阶段允许产出 Knowledge Candidate，但候选知识在用户确认或策略接受前，不能进入 Canonical Store 或 Memory。User Confirmation 不阻塞普通回答；它只在候选知识持久化、高风险写入、自动化规则或外部动作前触发。

Knowledge Candidate 初始生命周期：

- transient：仅用于当前任务。
- inbox：进入候选知识收件箱，等待用户后续整理。
- confirm_required：持久化或高风险写入前必须确认。
- discard：不保留。

Knowledge Candidate 第一版类型：

- fact
- preference
- relationship
- task
- decision

每条候选知识都应带有 confidence、risk、lifecycle、source_revisions 和 why_suggested。

Knowledge Candidate 确认流程：candidate 存本地 inbox，用户用 CLI 异步批量确认（`candidate list/confirm/discard/edit/merge/defer`），dashboard 只读展示、不写回；低风险自动接受（Q12 路径 3）；普通回答不被确认阻塞；agent 只能 `candidate add`，不能 confirm。

确认后升级映射（按 type）：`fact` → Canonical Fact（acceptance_path=user_confirmation）；`task` → Task；`preference`/`relationship`/`decision` → Memory。只有 fact 候选进 Canonical Fact，偏好/关系/决策候选进 Memory，与 Q14 边界对齐。

Canonical Fact 第一版生成路径：

- 用户显式确认 Knowledge Candidate。
- 用户手动创建事实。
- 低风险策略自动接受。

Canonical Fact 必须包含 statement、source_revisions、accepted_by、accepted_at、acceptance_path、confidence、risk、validity、revocation_status。偏好、关系、任务、决策和高敏事实不得自动接受。

Context Bundle 组装时的来源优先级：

1. Canonical Fact
2. Memory
3. 当前任务相关的 Source Revision
4. 当前任务生成的 Knowledge Candidate
5. 被排除或失效来源只进入 `excluded_sources` / `freshness_report`

规则：Canonical Fact 优先但必须先检查 validity / revocation / 来源新鲜度；Memory 只影响排序、语气和偏好，不替代事实证据；Source Revision 提供新鲜证据用于补充或复核；Knowledge Candidate 只作为可能线索，不能伪装成事实；stale / missing / revoked 内容不进入可用上下文，只进入报告区。依赖失效来源的 Canonical Fact 标记为需要复核，不立即删除。

Memory 与 Canonical Fact 的边界：

- Canonical Fact = 事实证据，带 source_revisions，可在 Source-Backed Answer 中被引用为事实。
- Memory = 语境与偏好，影响排序、语气、风格和默认假设，不能作为事实证据。
- Memory 永远不能升级成事实证据；需要当事实用必须走 Fact Acceptance 升级为 Canonical Fact。
- 推断记忆分两档：普通偏好带置信度直接写入 Memory；重要偏好、关系、决策类推断写入 Memory 前需要 User Confirmation。显式记忆和情境记忆可直接写入，情境记忆必须带范围和过期时间。

Context Bundle 与 Agent 消费：

- 每个 Context Slice 带 `evidence_role`：`fact`（Canonical Fact，可作证据）、`raw`（Source Revision，原始材料）、`context`（Memory，只影响语气/排序）、`lead`（Knowledge Candidate，未核实线索）。
- `evidence_role` 挂在 Slice 上，不挂在 Bundle 上；角色决定 Slice 带的字段子集和能在回答中出现的位置。
- 事实性回答只能是 Source-Backed Answer，基于 `fact` + `raw`；`context` 和 `lead` 不得进入事实陈述位；`lead` 不得单独支撑结论。
- Context Bundle 的逻辑结构为 `task + permission_scope + slices[] + excluded_sources[] + freshness_report[]`，第一版不锁死序列化格式或传输协议。

## Consequences

正向影响：

- 第一阶段不再是普通 RAG，也不绑定 Obsidian。
- 后续日历、任务、联系人、邮件等来源可以复用相同上下文模型。
- 候选知识和长期事实之间有明确确认边界。
- 普通问答路径保持顺畅，不退化成每次回答前的审批流。

代价：

- 第一版需要设计 Context Bundle，而不是只做检索 API。
- 验收标准必须覆盖权限、来源、新鲜度、候选知识生命周期和持久化前确认。

## Alternatives Considered

- 只做原文片段检索：实现更快，但无法证明 LifeMesh 区别于 RAG。
- 做 Obsidian 知识地图：对第一个数据源有价值，但会把产品推向 Obsidian 增强器。
