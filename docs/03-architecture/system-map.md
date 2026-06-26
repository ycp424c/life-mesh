# System Map

状态：draft
最后更新：2026-06-26
职责边界：说明 Web 看板中的 LifeMesh 系统架构图及其层级含义。

## 定位

系统架构图展示 LifeMesh 从个人数据源到 Agent 可用上下文的主流程。它是 `docs/03-architecture/overview.md` 的可视化补充，不替代 ADR 或架构事实源。

## 主路径

```text
Source Adapters
  -> Source Lifecycle
  -> Index / Graph / Timeline
  -> Personal Context Layer
  -> Canonical Knowledge
  -> Agent Access
```

## 横切能力

以下能力贯穿所有层：

- Policy
- Consent
- Audit
- Risk Controls
- Deletion / Revocation

## 关键边界

- Source Adapter 接入具体数据源，但核心语义保持 source-neutral。
- Source Revision 负责可编辑来源的版本身份。
- Personal Context Layer 产出 Context Bundle，而不是裸检索结果。
- Knowledge Candidate 在确认或策略接受前不能成为 Canonical Fact 或 Memory。
- Canonical Fact 可以作为 Context Bundle 来源，但必须可追溯、可撤销。
- Agent Access 只能拿到授权后的 Context Bundle 和工具能力。

## Context Bundle 来源优先级

组装 Context Bundle 时按以下优先级纳入来源：

1. Canonical Fact（已核实，但先检查 validity / revocation / 来源新鲜度）
2. Memory（影响排序、语气和偏好，不替代事实证据）
3. 当前任务相关的 Source Revision（新鲜证据，用于补充或复核）
4. 当前任务生成的 Knowledge Candidate（只作为可能线索，不能伪装成事实）
5. 被排除或失效的来源只进入 `excluded_sources` / `freshness_report`，不进入可用上下文

失效来源不静默丢弃：依赖失效 Source Revision 的 Canonical Fact 标记为需要复核，不能继续作为"已核实"使用。

## Canonical Fact 生成路径

第一版只允许三条路径生成 Canonical Fact：

- 用户确认 Knowledge Candidate。
- 用户手动创建事实。
- 低风险策略自动接受。

偏好、关系、任务、决策和高敏事实不得自动进入 Canonical Fact。
