# CLI Contract

状态：draft
最后更新：2026-06-29
职责边界：定义第 1 阶段 LifeMesh CLI 的命令、JSON Bundle schema 和配套 skill 契约。只定义契约，不绑定实现。

## 定位

第 1 阶段 Agent 接口 = 薄 CLI + skill（见 `ADR-0006`）。CLI 读索引、组装 JSON Context Bundle、写入事实/待办/记忆/候选；skill 指导 agent 如何调用与消费。不引入运行时 server。

## 读命令

```bash
lifemesh bundle "<task>" [--source obsidian] [--out <path>] [--max-slices 20] [--sensitivity-cap Private]
```

- `<task>`（必填）：自然语言任务描述。
- `--source`：Source Adapter，第 1 阶段默认且只有 `obsidian`。
- `--out <path>`：写 JSON 到文件（默认写 stdout）。
- `--max-slices`：Bundle 大小上限，防爆上下文。
- `--sensitivity-cap`：允许的最高敏感级，阶段 5 前 `Sensitive` 不允许。

不提供直接返回答案的命令——回答是 agent 的职责，CLI 只交付 Bundle。

## 写命令

写命令分两类：用户断言路径（直接写）与 agent 推断路径（走候选）。

### 用户手动上传（直接写，可编辑可撤销）

```bash
lifemesh fact add "<statement>" [--source-rev <ref>...] [--user-asserted]
#   → Canonical Fact, acceptance_path=manual；无来源时标记 user_asserted

lifemesh task add "<todo>" [--due <date>]
#   → Task（待办）

lifemesh remember "<info>" [--scope <range>] [--expires <date>]
#   → 显式 Memory（Q14 可直接写入）
```

### agent 推断（走候选，需确认）

```bash
lifemesh candidate add "<statement>" --type fact|preference|relationship|task|decision [--source-rev ...]
#   → Knowledge Candidate 进 inbox，lifecycle=confirm_required
```

### 硬规则：agent 禁止直接 `fact add`

- `fact add` / `task add` / `remember` 是**用户断言路径**，只能由用户发起（用户直接写，或用户明确指示 agent 代为执行 manual 路径，事实来源是用户断言）。
- agent 自己推断出的事实/待办/记忆，**禁止直接写**，必须走 `candidate add` → inbox → 用户确认 → 升级。这条规则保住 Q12 的"不让 LLM 自动把偏好/关系/任务/决策写成 Canonical Fact"边界。

## 事实复核与撤销命令

当 Source Revision 变为 stale / missing / revoked，依赖它的 Canonical Fact 进入复核队列。第 1 阶段先定义命令契约，不实现：

```bash
lifemesh fact review list
#   → 列出 validity=needs_review 的 Canonical Fact

lifemesh fact review show <fact-id>
#   → 展示 statement、失效来源、review_reason、可用 current source、影响范围

lifemesh fact review revalidate <fact-id> --source-rev <ref>
#   → 绑定 current Source Revision，恢复 validity=valid

lifemesh fact review revise <fact-id> "<statement>" [--source-rev <ref>...]
#   → 生成新 Canonical Fact，旧 fact 标记 superseded

lifemesh fact review invalidate <fact-id>
#   → 标记 validity=invalid

lifemesh fact revoke <fact-id>
#   → 设置 revocation_status=revoked，生成 Fact Tombstone
```

硬规则：

- agent 不得替用户执行 `revalidate` / `revise` / `invalidate` / `revoke`，除非用户明确发出该操作指令。
- `needs_review` / `invalid` / `superseded` / `revoked` 的事实不得作为 `fact` slice 进入 Bundle。
- 所有复核与撤销命令都必须生成审计事件。

## JSON Bundle schema（v1）

```json
{
  "schema_version": "1",
  "bundle_id": "uuid",
  "task": { "description": "...", "agent_capability": "search" },
  "permission_scope": {
    "allowed_sources": ["obsidian"],
    "sensitivity_cap": "Private"
  },
  "assembled_at": "ISO-8601",
  "slices": [
    {
      "slice_id": "...",
      "evidence_role": "raw",
      "provenance": {
        "source": "obsidian",
        "note_path": "notes/local-first.md",
        "revision_id": "rev#abc",
        "mtime": "...",
        "content_hash": "sha256:..."
      },
      "citation_status": "current",
      "sensitivity": "Private",
      "content": "...原文片段...",
      "heading": "## 为什么本地优先",
      "line_range": [12, 30]
    }
  ],
  "excluded_sources": [
    { "source": "obsidian", "path": "Trash/old.md", "reason": "index_scope_excluded" }
  ],
  "freshness_report": [
    { "slice_id": "...", "citation_status": "stale", "note": "原文已修改，建议复核" }
  ]
}
```

约束：

- 每个 slice 必带 `evidence_role` + `provenance` + `citation_status`（source-backed 的）。
- 第 1 阶段实际主要产出 `raw` slice；`fact`/`context`/`lead` 的 schema 位保留，第 1 阶段常为空。
- `provenance` 形状按 role 区分：`raw` 带源 revision 字段；`fact` 带 canonical fact id + source_revisions；`context` 带 memory id + 生效范围；`lead` 带 candidate id + confidence/risk/why_suggested/lifecycle。
- `excluded_sources` / `freshness_report` 即使为空也要在，表示"已检查、无失效"而非"未检查"。

## Skill 契约

skill 随仓库版本化（如 `skills/lifemesh/SKILL.md`），内容契约：

1. **何时用**：当任务需要用户的所有信息（跨全部已接入 source，不限定 Obsidian）时调用。
2. **怎么调**：`bundle` 拿上下文；`task`/`remember`/`fact` 写用户手动信息；推断走 `candidate`；`candidate list/confirm` 复核候选。
3. **怎么调复核**：`fact review list/show/revalidate/revise/invalidate` 和 `fact revoke` 处理 `needs_review` 的事实；agent 只有在用户明确指示时才能代执行。
4. **怎么消费**：按 `evidence_role`——事实回答只用 `fact`+`raw` 并引 `note_path`+`revision_id`+`line_range`+`citation_status`；`context` 只调语气；`lead` 标"未核实"；`freshness_report` 的 stale/missing 要在回答里提示。
5. **边界**：agent 推断不得直接 `fact add`，只能 `candidate add`；不引用失效来源；不把 `context`/`lead` 当事实；不把 `needs_review` fact 当作可用事实。

skill 实体文件是 follow-up，等 CLI 实现时再写；当前只把契约钉进文档。

## 非目标

- 不在第 1 阶段实现 CLI（只定义契约）。
- 不暴露 `automation`（外发、不可逆动作），仍 deferred 在阶段 6。
- 不锁死 JSON schema 之外的传输细节。
