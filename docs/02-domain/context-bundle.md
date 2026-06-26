# Context Bundle

状态：draft
最后更新：2026-06-26
职责边界：定义 Context Bundle 的组装方式、来源优先级和失效来源处理，不定义具体序列化格式。

## 定位

Context Bundle 是 Personal Context Layer 为某个 Agent 任务、在某个权限边界内临时组装的上下文包。它由若干 Context Slice 组成，每个 Slice 都带来源、权限、新鲜度和 Citation Status。

它不是：

- 一堆裸检索片段
- 永久知识或 Canonical Store 的替代品
- 直接写回来源的产物

## 来源优先级

组装 Context Bundle 时，按以下优先级纳入来源：

```text
1. Canonical Fact
2. Memory
3. 当前任务相关的 Source Revision
4. 当前任务生成的 Knowledge Candidate
5. 被排除或失效的来源只进入 excluded_sources / freshness_report
```

## 优先级规则

- **Canonical Fact 优先**：它已核实，但进入 Bundle 前必须检查 `validity`、`revocation_status` 和依赖 Source Revision 的新鲜度。
- **Memory 可影响排序、语气和偏好**，但不能替代事实证据。推断记忆在输出时应带上不确定性。
- **Source Revision 提供新鲜证据**，用于补充或复核事实，尤其用于覆盖或更新 Canonical Fact 的旧来源。
- **Knowledge Candidate 只能作为"可能线索"**，不能伪装成事实，也不能直接驱动高风险写入。
- **stale / missing / revoked 的内容不能进入可用上下文**，只能进入报告区，供 Agent 和用户判断是否需要重新生成或复核。

## 失效来源处理

被排除、过期或撤销的来源不静默消失，也不静默保留：

- 进入 `excluded_sources`：记录被排除的来源和原因（路径排除、授权撤销、敏感级别等）。
- 进入 `freshness_report`：记录 Citation Status 为 stale 或 missing 的引用，提示哪些事实需要复核。
- 依赖失效 Source Revision 的 Canonical Fact 不一定立即删除，但必须标记为需要复核，不能直接作为"已核实"使用。

## Evidence Role

`evidence_role` 是挂在**每个 Context Slice** 上的角色标签，不挂在 Bundle 上。一个 Bundle 混装事实、语境、线索和原始材料，所以角色必须是切片级粒度。

初始角色：

| role | 来源 | 必带字段 | 在回答中的位置 |
|---|---|---|---|
| `fact` | Canonical Fact | provenance(source_revisions)、validity、revocation_status | 事实陈述位 |
| `raw` | Source Revision | provenance、citation_status | 证据材料位 |
| `context` | Memory | memory ref、生效范围、过期策略 | 调味/排序/语气位，不进事实陈述 |
| `lead` | Knowledge Candidate | confidence、risk、why_suggested、lifecycle | "可能线索"位，带未核实标注 |

`context` 和 `lead` 不能出现在事实陈述位；`lead` 不能单独支撑一个结论。

## 逻辑结构

以下为 Context Bundle 的逻辑形状，用于钉死字段归属，**不是**第一版要锁死的序列化格式或传输协议。

```text
ContextBundle
  ├─ bundle_id
  ├─ task              { description, agent_capability }
  ├─ permission_scope  { allowed_sources, sensitivity_cap, revoke_token }
  ├─ assembled_at
  ├─ slices[]          ← 主体，每个 Slice 自带 evidence_role
  ├─ excluded_sources[]  { source, reason }
  └─ freshness_report[]  { slice_id, citation_status, note }
```

每个 Context Slice 的字段按 `evidence_role` 取子集：

```text
ContextSlice
  ├─ slice_id
  ├─ evidence_role     fact | context | lead | raw
  ├─ provenance        source_revision ref | memory ref
  ├─ citation_status   current | stale | missing   # 仅 source-backed slice
  ├─ sensitivity
  ├─ content
  ├─ confidence, risk  # lead 必带；fact 从 Canonical Fact 继承
  ├─ why_suggested     # 仅 lead
  └─ lifecycle         # 仅 lead
```

## Agent 消费规则

Agent 拿到 Context Bundle 后按 `evidence_role` 消费，不自己猜角色：

- **事实性陈述的回答** → 必须是 Source-Backed Answer，只能基于 `fact` + `raw`，不能基于 `context` 或 `lead`。
- **建议、规划、草稿类输出** → 可以用 `context` 调整风格和排序，用 `lead` 提供灵感，但必须区分"基于事实"和"基于偏好/线索"两部分。
- **`lead` 永远不能单独支撑一个结论**：候选线索要进回答，必须带"未核实"标注，或先走 Fact Acceptance 变成 `fact`。

Agent 不得做的事：

- 不得把 `context`（偏好）写成客观事实。
- 不得把 `lead`（候选）当成已确认结论。
- 不得在事实性回答里引用失效来源；stale / missing / revoked 只能进报告区，不能进证据。

## 产物格式

Context Bundle 序列化成 **JSON 产物**，不使用 Markdown。理由：Markdown 只是格式化呈现层，Bundle 这一层需要的是结构化字段（`evidence_role`、`provenance`、`citation_status`、`confidence` 等）供 agent 程序化消费，不需要排版。

JSON 产物承载 Q15 的逻辑结构：`task`、`permission_scope`、`slices[]`、`excluded_sources[]`、`freshness_report[]`，每个 Slice 带 `evidence_role` 和对应字段子集。

## 与 Agent 的交付：CLI + Skill

Bundle 不通过运行时 server 交付（见 `ADR-0006`），而是 **薄 CLI + skill** 的组合：

- **CLI**：读索引、按任务组装 JSON Bundle、输出到文件或 stdout。
- **Skill**：一份 agent 可读的说明，告诉 agent 如何调用 CLI、以及拿到 JSON Bundle 后按 `evidence_role` 消费（事实回答只用 `fact` + `raw`，`context` 只调语气，`lead` 标"未核实"）。

Skill 把 Q15 的消费规则固化成 agent 能直接遵循的指令，使交付保持 agent 无关——任何能读 skill 的 agent 都能正确使用 LifeMesh，不需要专门 client，也不需要长驻 server。

## 组装边界

- Context Bundle 是按任务和权限临时组装的结果，不应被误当成永久知识。
- 每个 Context Slice 必须能解释来源、权限范围和新鲜度。
- 高敏对象默认不进入通用 Context Bundle，需要更严格授权。
- Context Bundle 不应包含不带来源的 LLM 总结；总结必须能回溯到具体 Source Revision 或 Canonical Fact。

## 非目标

- 不在第一版定义 Context Bundle 的具体序列化格式或传输协议。
- 不让 Knowledge Candidate 在未确认前驱动高风险动作。
- 不把失效来源静默丢弃，也不让失效来源继续作为可用上下文。
