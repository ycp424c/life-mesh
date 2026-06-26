# Knowledge Candidates

状态：draft
最后更新：2026-06-26
职责边界：定义第一版 Knowledge Candidate 的类型、共同字段和持久化边界。

## 定位

Knowledge Candidate 是从 Context Bundle 中识别出的候选知识。它可以帮助用户发现事实、偏好、关系、任务或决策，但在被用户确认或策略接受前，不是 canonical knowledge，也不是 Memory。

## 第一版类型

| 类型 | 说明 | 示例 | 默认生命周期 |
|---|---|---|---|
| fact | 带来源的客观陈述 | 某篇笔记提到“本地优先架构” | transient 或 inbox |
| preference | 用户偏好或长期倾向 | 用户倾向本地优先、可审计、低耦合 | inbox 或 confirm_required |
| relationship | 人、项目、主题、组织之间的关系 | 某人参与某项目，某主题关联某文档集 | inbox |
| task | 可能需要行动的事项 | 某笔记里出现“下周补设计文档” | inbox 或 confirm_required |
| decision | 用户做过的选择及其理由 | 选择静态看板而不是前端框架 | inbox 或 confirm_required |

## 共同字段

每个 Knowledge Candidate 至少应包含：

- `type`
- `summary`
- `confidence`
- `risk`
- `lifecycle`
- `source_revisions[]`
- `why_suggested`
- `created_at`
- `expires_at`，可选

## 生命周期

- `transient`：仅用于当前任务，不进入候选收件箱。
- `inbox`：进入候选知识收件箱，等待用户批量整理。
- `confirm_required`：写入 Canonical Store、Memory、任务、自动化规则或外部动作前必须确认。
- `discard`：不保留。

## 持久化边界

- fact 可以在来源明确且风险低时作为临时上下文使用，但进入 Canonical Store 前仍需满足策略。
- 被确认或策略接受的 fact 可以转为 Canonical Fact。
- preference 默认不自动写入 Memory。
- relationship 涉及第三方时应提高风险级别。
- task 进入任务系统前需要确认。
- decision 需要保存来源和理由，不能只保存结论。

## 非目标

- 不把所有候选知识自动写入长期记忆。
- 不把候选知识当成模型已经确认的事实。
- 不在普通回答前强制用户逐条确认候选知识。
