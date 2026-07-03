# System Map

状态：draft
最后更新：2026-07-03
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
- Source Revision 负责 Obsidian 等可编辑外部来源的版本身份；Manual Input 不使用 SourceRevision，而以 input record、content_hash、状态和 audit event 作为 source reference。
- RumorClaim 不新增独立架构层，也不是 Manual Input kind；它是 Personal Context Layer 中从可信度未知材料抽取出的未验证 claim，默认只作为 review lead。
- Personal Context Layer 通过 BundleAssembler 产出 Context Bundle，而不是裸检索结果或 adapter 级拼接结果。
- Source Adapter / Retriever 产出 source-backed candidates；最终准入、来源优先级、去重、多样性和 `assembly_report` 由 BundleAssembler 执行。
- Knowledge Candidate 在确认或策略接受前不能成为 Canonical Fact 或 Memory。
- Canonical Fact 可以作为 Context Bundle 来源，但必须可追溯、可复核、可撤销。
- Agent Access 在第 1 阶段通过 CLI + skill 获取授权后的 JSON Context Bundle；只读原型验收后，ADR-0008 定义 Manual Input Inbox 作为 Phase 1 后续 milestone。

## Context Bundle 来源优先级

组装 Context Bundle 时按以下优先级纳入来源：

1. Canonical Fact（已核实，但先检查 validity / revocation / 来源新鲜度）
2. Memory（影响排序、语气和偏好，不替代事实证据）
3. 当前任务相关的 Source Reference（Source Revision 或 Manual Input，新鲜证据，用于补充或复核）
4. 当前任务生成的 Knowledge Candidate（只作为可能线索，不能伪装成事实）
5. 明确请求未验证线索时的 RumorClaim（只能作为 lead）
6. 被排除或失效的来源只进入 `excluded_sources` / `freshness_report`，不进入可用上下文

失效来源不静默丢弃：依赖失效 source reference 且没有其他 current supporting source 的 Canonical Fact 标记为 `needs_review`，不能继续作为"已核实"使用。

跨源 Bundle 由 BundleAssembler 执行该优先级。`bundle --source all` 不拼接多个已完成 Bundle，而是把 Obsidian、Manual Input 和后续 source 的候选放入同一组装策略。

## Manual Input Inbox

ADR-0008 将 Manual Input 定义为 Phase 1 后续 milestone：

- Manual Input 接收用户或 Agent 主动提交的截图、日程、心情、活动、待办和备注。
- 默认存储在用户级 `~/.lifemesh/`，以 SQLite、FTS、本地 embedding 和 Raw Vault managed assets 支撑检索。
- Agent 可自动捕获非高敏信息到 `auto_captured` Inbox，但必须透明说明，且不得自动 promote。
- `input promote` 只创建 inbox-derived 最小 Task / Event / Memory / Fact / Candidate 对象；系统日历、提醒事项和外部任务应用同步属于第 2 阶段。

## RumorClaim / UnverifiedClaim

ADR-0009 将 RumorClaim 定义为 Phase 1 follow-on 契约。当前已实现本地结构化 CLI MVP；自动 source adapter、截图/图片自动抽取、review UI 和外部 fact-check 尚未实现：

- 输入可以是文字片段、截图或普通图片。
- 原始物料默认只进入 temporary parsing sandbox，不长期保存。
- 主资产是 `claim_text`、`entity_mentions[]` 和 `relation_mentions[]`。
- 只有通过相关性或影响门槛的 claim 才持久化。
- 默认不进入普通 Context Bundle；明确请求未验证线索时只能作为 `lead`。
- 只能 promote 到 Knowledge Candidate。

## Canonical Fact 生成路径

第一版只允许三条路径生成 Canonical Fact：

- 用户确认 Knowledge Candidate。
- 用户手动创建事实。
- 低风险策略自动接受。

偏好、关系、任务、决策和高敏事实不得自动进入 Canonical Fact。

## Canonical Fact 复核与撤销

只有 `validity=valid`、`revocation_status=active`、且至少有 current supporting source reference 的 Canonical Fact，才能作为 `fact` slice 进入 Bundle。

Source Revision stale / missing / revoked，或 Manual Input revoked / deleted 后：

- Source Tombstone 阻止旧 revision 被新检索命中。
- Manual Input Tombstone 阻止旧 input、extraction 和 embedding 被新检索命中。
- 依赖事实进入复核队列或报告区。
- 用户复核后可 revalidate、revise、invalidate 或 revoke。
- Fact Tombstone 阻止被撤销或失效的旧 fact 继续进入新 Bundle，同时保留历史审计。
