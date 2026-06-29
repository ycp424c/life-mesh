# Memory Model

状态：draft
最后更新：2026-06-26
职责边界：定义 LifeMesh 如何写入、读取、确认、过期和删除长期记忆。

## 记忆类型

| 类型 | 内容 | 写入规则 |
|---|---|---|
| 显式记忆 | 用户明确说“记住……” | 可直接写入，但仍需可编辑和可删除 |
| 推断记忆 | 多次行为中归纳出的偏好 | 需要置信度，重要偏好应确认 |
| 情境记忆 | 某项目、某阶段的临时上下文 | 必须有范围和过期时间 |

## 与 Canonical Fact 的边界

Memory 和 Canonical Fact 都已确认、可复用，但在 Context Bundle 中承担不同角色，不可混用：

- **Canonical Fact = 事实证据**。已核实、带 `source_refs` 的客观陈述，可以在 Source-Backed Answer 里被引用为“这件事是真的”。`source_refs` 可以指向 SourceRevision，也可以指向 Manual Input record / extraction。
- **Memory = 语境与偏好**。长期偏好、目标、关系语境、情境记忆。它影响排序、语气、风格和默认假设，但不能作为事实证据出现在回答里。

硬边界：

- Memory 永远不能升级成事实证据被引用。如果一条 Memory 实际上需要被当作事实使用，它必须走 Fact Acceptance 变成 Canonical Fact，而不是留在 Memory 里当事实用。
- Canonical Fact 不承担偏好或语气职责，它只负责“真不真”，不负责让回答“更像用户”。
- 一句话：Fact 是“真不真”，Memory 是“像不像用户”；Memory 想当事实用，就得走 Fact Acceptance 升级。

## 每条记忆应包含

- 内容
- 类型
- 来源
- 置信度
- 生效范围
- 过期策略
- 最近使用记录
- 用户确认状态
- 删除和纠错入口

## 读取规则

- 默认只读取与当前任务相关的记忆。
- 高敏记忆需要更严格授权。
- 推断记忆在输出给 Agent 时应带上不确定性。
- 过期记忆不能静默影响 Agent 行为。
- Memory 只能影响排序、语气和偏好，不能作为事实证据；需要当事实用时必须走 Fact Acceptance 升级为 Canonical Fact。

## 写入与确认规则

- **显式记忆**（用户明确说“记住……”）：可直接写入 Memory，仍可编辑、可删除，不需要确认。
- **情境记忆**（某项目、某阶段的临时上下文）：可直接写入，但必须带范围和过期时间，过期后不能静默影响 Agent 行为。
- **推断记忆**（从多次行为归纳出的偏好、关系、决策）：写入 Memory 前分两档：
  - 普通偏好（如”倾向简洁回复”）：带置信度直接写入，输出时标注不确定性，不需要确认。
  - 重要偏好 / 关系 / 决策类推断：作为 Knowledge Candidate 进 inbox，经用户确认后写入 Memory（`preference`/`relationship`/`decision` 候选 confirm → Memory）。
