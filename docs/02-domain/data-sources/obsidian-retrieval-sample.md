# Obsidian Retrieval Sample

状态：draft
最后更新：2026-06-26
职责边界：用真实 vault 数据定义第 1 阶段 Obsidian 检索的可验收样例，验证 `cli-contract.md` 的 `bundle` 命令、JSON Bundle schema 和 Citation Status 链路。

## 定位

这不是实现，而是一个**可验收样例**：给定具体任务，期望 CLI 产出什么样的 JSON Bundle、agent 据此给出什么样的 Source-Backed Answer、来源变更后 stale 链路如何生效。用于在第 1 阶段实现前钉死"做对了"的判据。

样例数据来自真实 vault `/Users/justynchen/Documents/docs/obsidian-default` 的 `hot.md`（有 frontmatter、多级标题、实质内容）。

## 样例任务

```bash
lifemesh bundle "AI 对开源生态有什么结构性冲击？" --source obsidian --out /tmp/bundle.json
```

## 期望 JSON Bundle（节选）

```json
{
  "schema_version": "1",
  "task": { "description": "AI 对开源生态有什么结构性冲击？", "agent_capability": "search" },
  "permission_scope": { "allowed_sources": ["obsidian"], "sensitivity_cap": "Private" },
  "slices": [
    {
      "slice_id": "s1",
      "evidence_role": "raw",
      "provenance": {
        "source": "obsidian",
        "note_path": "hot.md",
        "revision_id": "rev#<content_hash>",
        "mtime": "2026-06-24T...",
        "content_hash": "sha256:..."
      },
      "citation_status": "current",
      "sensitivity": "Private",
      "heading": "## Active Threads",
      "line_range": [16, 21],
      "content": "- **AI 对开源生态的结构性冲击** — 从 Tailwind CSS 收入崩溃到 xz 后门事件，维护者流失和 AI 中间层效应是核心线索 ..."
    },
    {
      "slice_id": "s2",
      "evidence_role": "raw",
      "provenance": { "source": "obsidian", "note_path": "hot.md", "revision_id": "rev#<content_hash>", "...": "..." },
      "citation_status": "current",
      "heading": "## Key Takeaways",
      "line_range": [23, 28],
      "content": "- 开源繁荣建立在脆弱的社会契约之上，AI 正在切断维护者与用户之间的最后连接 ..."
    }
  ],
  "excluded_sources": [],
  "freshness_report": []
}
```

若 vault 中存在专属 wiki 页（如"开源公地悲剧""Tailwind CSS"），应作为额外 `raw` slice 出现；本样例以 `hot.md` 为最小可验证来源。

## 期望 agent Source-Backed Answer

> AI 对开源生态的结构性冲击主要在维护者流失和"AI 中间层效应"：从 Tailwind CSS 收入崩溃到 xz 后门事件，核心线索是 AI 切断了维护者与用户之间的连接——开源繁荣建立在脆弱的社会契约之上。
>
> 来源：`hot.md` › `## Active Threads` (L16–21) · `## Key Takeaways` (L23–28) · citation_status: current

agent 必须按 `evidence_role` 消费：事实回答只用 `raw`，并引用 `note_path` + `heading` + `line_range` + `citation_status`。

## stale 场景（第二幕）

`hot.md` 在索引后被编辑：

- 同一任务的 Bundle 里，s1/s2 的 `citation_status` 变成 `stale`，并进 `freshness_report`，`note` 提示"原文已修改，建议基于当前版本复核"。
- agent 回答**不**用旧内容当事实，而是提示"来源已变更，建议基于当前版本重新生成"，并提供重新生成动作。
- 新问题不得命中 stale revision。

## 验收标准

通过条件：

- `bundle` 返回的每个 slice 带真实 `note_path` + `revision_id` + `heading` + `line_range` + `citation_status`。
- agent 的事实回答引用了 `note_path` + `line_range` + `citation_status`，不只说"根据你的笔记"。
- `excluded_sources` / `freshness_report` 即使为空也在 JSON 里，表示"已检查"而非"未检查"。
- 来源被编辑后，stale 链路生效：旧内容不当事实、进 `freshness_report`、新问题不命中 stale revision。

失败条件：

- 回答引用了来源但没给 `line_range` / `citation_status`。
- stale 来源被当事实用，或新问题命中 stale revision。
- `excluded_sources` / `freshness_report` 字段缺失。

## 非目标

- 不要求覆盖全 vault 检索，只验证最小链路：索引 → bundle → 来源引用 → stale 失效。
- 不在本样例验证写命令（`fact add` / `candidate add`），写侧验收另定。
