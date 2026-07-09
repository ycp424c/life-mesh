# Obsidian Retrieval Sample

状态：draft
最后更新：2026-07-09
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
      "citation": {
        "format": "obsidian-note-line-range-v1",
        "source": "obsidian",
        "note_path": "hot.md",
        "heading": "## Active Threads",
        "line_range": [16, 21],
        "citation_status": "current",
        "label": "hot.md › ## Active Threads (L16-L21) · citation_status: current"
      },
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
      "citation": { "format": "obsidian-note-line-range-v1", "label": "hot.md › ## Key Takeaways (L23-L28) · citation_status: current" },
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
> 来源：`hot.md › ## Active Threads (L16-L21) · citation_status: current`；`hot.md › ## Key Takeaways (L23-L28) · citation_status: current`

agent 必须按 `evidence_role` 消费：事实回答只用 `raw`，并优先展示 `citation.label`；不能只说"根据你的笔记"。

## stale 场景（第二幕）

`hot.md` 在索引后被编辑：

- 同一任务的 Bundle 里，s1/s2 的 `citation_status` 变成 `stale`，并进 `freshness_report`，`note` 提示"原文已修改，建议基于当前版本复核"。
- agent 回答**不**用旧内容当事实，而是提示"来源已变更，建议基于当前版本重新生成"，并提供重新生成动作。
- 新问题不得命中 stale revision。

## 2026-07-09 手工验收记录

命令：

```bash
/Users/justynchen/Documents/code/life-mesh/bin/lifemesh bundle "AI 对开源生态有什么结构性冲击？" --source obsidian --out /tmp/lifemesh-q20-bundle-2026-07-09.json
```

结果：

- `schema_version=1`，`permission_scope.allowed_sources=["obsidian"]`，`include_unverified=false`。
- 返回 20 个 `raw/current` slices，`excluded_sources` 返回 6 个默认排除目录，`freshness_report=[]`。
- 第 1 个 slice 来自专题归档页 `归档/正在腐烂的开源世界：从理想主义的狂欢到AI时代的公地悲剧.md` 的 `## AI的冲击`，说明当前 vault 已有比 `hot.md` 更专门的来源。
- `hot.md` 仍作为第 2 个 slice 返回，citation label 为 `hot.md › ## Active Threads (L16-L22) · citation_status: current`。
- `--source all` 对同一 Q20 问题没有选入 Manual Input candidates，因此本轮只验证不会把 Manual Input weak lead 当成事实；独立 weak lead 展示仍需另选 Manual Input 真实任务样例。

Source-Backed Answer 验收样例：

> AI 对开源生态的结构性冲击不是“写代码更快”本身，而是 AI 在开发者和开源项目之间形成中间层：使用量上升时，文档访问、bug 报告、社区互动和维护者回报反而下降，维护成本与噪音负担继续增加。回答应引用 `归档/正在腐烂的开源世界：从理想主义的狂欢到AI时代的公地悲剧.md › ## AI的冲击 (L71-L94) · citation_status: current` 和 `hot.md › ## Active Threads (L16-L22) · citation_status: current`，不能只写“根据你的笔记”。

stale / missing 验收使用真实 `hot.md` 的 `/tmp` 临时副本完成，没有修改真实 vault：

- stale：修改临时副本后，旧 revision 进入 `freshness_report`，`citation_status=stale`，同时新 slice 使用 current revision。
- missing：删除临时副本后，Bundle 返回 0 个 slices，旧 revision 进入 `freshness_report`，`citation_status=missing`。
- stale 和 missing 来源没有进入可用事实证据；agent 应提示来源已变更或不可用，并建议基于当前来源重新生成。

## 验收标准

通过条件：

- `bundle` 返回的每个 slice 带真实 `note_path` + `revision_id` + `heading` + `line_range` + `citation_status` + `citation.label`。
- agent 的事实回答引用了 `citation.label`，不只说"根据你的笔记"。
- `excluded_sources` / `freshness_report` 即使为空也在 JSON 里，表示"已检查"而非"未检查"。
- 来源被编辑后，stale 链路生效：旧内容不当事实、进 `freshness_report`、新问题不命中 stale revision。

失败条件：

- 回答引用了来源但没给 `citation.label`、`line_range` 或 `citation_status`。
- stale 来源被当事实用，或新问题命中 stale revision。
- `excluded_sources` / `freshness_report` 字段缺失。

## 非目标

- 不要求覆盖全 vault 检索，只验证最小链路：索引 → bundle → 来源引用 → stale 失效。
- 不在本样例验证写命令（`fact add` / `candidate add`），写侧验收另定。
