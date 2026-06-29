# Canonical Objects

状态：draft
最后更新：2026-06-29
职责边界：定义规范化事实库中的核心对象，供后续数据模型和接口设计使用。

## 核心对象

| 对象 | 说明 |
|---|---|
| Source | 数据来源，如日历、文件夹、邮件导出、手动录入。 |
| SourceAdapter | 连接某类个人数据源的边界。 |
| SourceReference | 支撑 Context Slice、Knowledge Candidate 或 Canonical Fact 的来源引用总称。 |
| SourceRevision | 可编辑外部来源中某个条目的具体版本，是 SourceReference 的一种。 |
| RawAsset | Raw Vault 中的原始文件或记录。 |
| ManualInputRecord | 用户主动提交的截图、日程、心情、活动或备注入口，承载用户断言、原始文件和后续派生关系。 |
| ManualInputExtraction | 从 Manual Input 或 RawAsset 中通过本地模型抽取出的文本、摘要、语义类型或候选字段。 |
| EmbeddingRecord | 某条输入、抽取结果或正式对象的向量索引记录，保存 provider、model、dimension、content_hash 和状态。 |
| VaultNoteRevision | Obsidian Vault 中某篇笔记被索引时的具体版本，是 SourceRevision 的特例。 |
| ContextSlice | 面向任务选出的最小上下文单元。 |
| ContextBundle | 按任务和权限组装的一组上下文。 |
| KnowledgeCandidate | 候选事实、偏好、关系、任务或决策。 |
| CanonicalFact | 已核实、可追溯、可撤销，并可在 Context Bundle 中复用的事实。 |
| FactAcceptance | 将候选知识或用户手动陈述转成 CanonicalFact 的动作或策略路径。 |
| SourceTombstone | 来源被删除、排除或撤销授权后的不可用标记，用于阻止旧 revision 继续命中。 |
| FactTombstone | CanonicalFact 被撤销、失效或替代后的不可用标记，用于阻止旧 fact 继续进入 Bundle。 |
| UserConfirmation | 用户对候选知识或高风险写入的确认或拒绝。 |
| ExtractedFact | 从原始数据抽取出的事实。 |
| Entity | 人、组织、地点、项目、资产等实体。 |
| Event | 已发生或将发生的时间事件。 |
| Task | 可执行的任务。 |
| Commitment | 用户对自己或他人的承诺。 |
| Deadline | 截止日期或强约束时间点。 |
| ActivityLog | 用户手动记录的活动材料，只有在明确建模后才派生为 Event、Task、Memory 或 Canonical Fact。 |
| Person | 联系人和关系上下文。 |
| Project | 项目、目标或阶段性工作空间。 |
| Memory | 长期或阶段性记忆。 |
| DecisionRecord | 决策及其理由。 |
| ConsentGrant | 授权记录。 |
| AuditEvent | 审计事件。 |
| ToolInvocation | Agent 或工具调用记录。 |

## 对象设计原则

- 每个对象都应关联来源和更新时间。
- 对可编辑外部来源，派生对象应关联 SourceRevision，而不是只关联当前路径；Manual Input 不创建 SourceRevision，应关联 input id、content_hash、状态和审计事件。
- ContextSlice 必须能解释来源、权限范围和新鲜度。
- ContextSlice 必须带 `evidence_role`（fact / raw / context / lead），角色决定它带的字段子集和能在回答中出现的位置。
- KnowledgeCandidate 在确认前不能等同于 ExtractedFact、Memory 或 Canonical Store 内容。
- KnowledgeCandidate 第一版类型为 fact、preference、relationship、task、decision。
- KnowledgeCandidate 应带有 CandidateLifecycle，用于区分本次任务临时使用、候选收件箱、持久化前确认和丢弃。
- ManualInputRecord 是 source-neutral 的手动入口，不等同于 CanonicalFact。截图、心情和活动记录默认先作为 raw/lead/context material；只有用户明确 promote 或确认候选后，派生内容才进入目标层。
- ManualInputRecord 第一版状态为 `active`、`auto_captured`、`promoted`、`revoked`。`auto_captured` 最多作为 lead 使用，不能当作已核实事实。
- 截图类 RawAsset 默认复制到 LifeMesh Raw Vault，并保留 original path；OCR 或视觉理解结果保存为 ManualInputExtraction，带 provider/model/confidence，不能直接成为已核实事实。
- EmbeddingRecord 可以用于 ManualInputRecord、ManualInputExtraction 和 promoted object；当前 Manual Input 优先生成 embedding，失败时降级为 FTS-only 或 metadata-only，并通过状态和 audit 暴露不可检索或部分可检索记录。
- Promote 到 Task、Event、Memory、CanonicalFact 或 KnowledgeCandidate 必须保留 `derived_from_input_id` 和 audit event。Phase 1 后续 milestone 中的 Task/Event 是 inbox-derived 最小对象，不等同于系统日历或任务应用同步。
- CanonicalFact 可作为 Context Bundle 的高优先级来源，但必须保留 provenance 和撤销路径。
- CanonicalFact 只有在 `validity=valid`、`revocation_status=active` 且有 current supporting source reference 时，才能作为 `fact` slice 使用。source reference 可以是 SourceRevision，也可以是 Manual Input record/extraction。
- 依赖失效来源的 CanonicalFact 先进入 `needs_review`，复核后 revalidate、revise、invalidate 或 revoke；撤销和失效通过 tombstone 阻止后续使用。
- Context Bundle 按来源优先级组装：Canonical Fact > Memory > 当前任务相关 Source Reference > 当前任务生成的 Knowledge Candidate；失效来源只进入 excluded_sources / freshness_report。
- Manual Input 通过显式 `bundle --source all` 或 `bundle --source manual-input` 参与检索；`active` 可作为 raw slice，`auto_captured` 可作为 lead，`revoked` 和 deleted tombstone 不进入新 Bundle。
- CanonicalFact 第一版只允许通过用户确认、用户手动创建、低风险策略接受三条路径生成。
- UserConfirmation 只应用于持久化或高风险写入，不应阻塞普通回答生成。
- 派生对象应记录抽取方式和置信度。
- 记忆、承诺、决策必须能被用户纠正。
- Memory 与 Canonical Fact 不得混用：Memory 只影响排序、语气和偏好，不能作为事实证据；需要当事实用必须走 Fact Acceptance 升级为 Canonical Fact。
- 推断记忆分两档：普通偏好带置信度直接写入；重要偏好、关系、决策类推断写入 Memory 前需要 User Confirmation。
- 与第三方相关的数据要单独标记。
- 高敏对象默认不进入通用检索上下文。
