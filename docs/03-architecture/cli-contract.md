# CLI Contract

状态：draft
最后更新：2026-06-29
职责边界：定义第 1 阶段 LifeMesh CLI 的命令、JSON Bundle schema 和配套 skill 契约。实现状态以本文件的“当前实现”段落、README 和测试为准。

## 定位

第 1 阶段 Agent 接口 = 薄 CLI + skill（见 `ADR-0006`）。CLI 读索引、组装 JSON Context Bundle、写入 Manual Input、事实、待办、记忆和候选；skill 指导 Agent 如何调用与消费。不引入运行时 server。

## 当前实现

当前已实现：

- `lifemesh bundle` 的 Obsidian 只读链路。
- Obsidian Source Revision、raw slice、路径排除、sensitivity cap、stale / missing 检测。
- Manual Input Inbox：`input add/search/list/show/update/revoke/delete/promote`。
- Manual Input SQLite 主库、FTS、sqlite-vec 向量检索、LM Studio embedding 和截图 VLM extraction。
- `lifemesh bundle --source manual-input` 与 `lifemesh bundle --source all`。

兼容性说明：`lifemesh bundle` 默认仍为 `--source obsidian`，避免旧的只读原型被 Manual Input 本地依赖状态影响；跨源合并必须显式使用 `--source all`。

## 读命令

```bash
lifemesh bundle "<task>" \
  [--source all|obsidian|manual-input] \
  [--vault <path>] \
  [--out <path>] \
  [--max-slices 20] \
  [--sensitivity-cap Private] \
  [--home <path>] \
  [--lmstudio-base-url <url>] \
  [--embedding-model <name>] \
  [--vlm-model <name>] \
  [--sqlite-vec-extension <path>]
```

- `<task>`（必填）：自然语言任务描述。
- `--source`：Source Adapter，默认 `obsidian`；显式 `all` 会合并 Obsidian 和 Manual Input；也可筛选 `manual-input`。
- `--vault <path>`：Obsidian vault 路径；fallback 为 `LIFEMESH_OBSIDIAN_VAULT`，再到 config `obsidian_vault`。
- `--out <path>`：写 JSON 到文件（默认写 stdout）。
- `--max-slices`：Bundle 大小上限，防爆上下文。
- `--sensitivity-cap`：允许的最高敏感级，默认 `Private`；`Sensitive` 记录默认排除。
- Manual Input 相关 source 会加载本地配置；缺 LM Studio、embedding/VLM 调用失败或 sqlite-vec 不可用时降级为 SQLite/FTS 路径，并在状态和审计中记录失败原因。

不提供直接返回答案的命令，回答是 Agent 的职责，CLI 只交付 Bundle。

## Manual Input 命令

Manual Input 命令写入统一 Inbox，默认数据目录为 `~/.lifemesh/`。

### Add

```bash
lifemesh input add \
  --kind note|screenshot|event|mood|activity|task \
  [--text "..."] \
  [--file /path/to/image] \
  [--occurred-at <datetime>] \
  [--starts-at <datetime>] \
  [--ends-at <datetime>] \
  [--due-at <datetime>] \
  [--timezone <tz>] \
  [--declared-kind note|event|mood|activity|task] \
  [--sensitivity Internal|Private|Sensitive] \
  [--tags "a,b,c"] \
  [--source-type manual_cli|agent_auto_capture|agent_delegated] \
  [--auto-captured] \
  [--no-extract]
```

行为：

- 生成 `ManualInputRecord`。
- `--kind screenshot` 默认复制文件到 `~/.lifemesh/raw-assets/manual-input/`。
- 截图默认同步执行本地 OCR / VLM extraction；`--no-extract` 跳过 VLM。没有可检索文本时仍保存记录和 managed asset，但标记为不可检索降级状态。
- 文本和截图可检索内容优先调用本地 embedding；embedding 失败时保留 SQLite/FTS。
- 缺配置、sqlite-vec 加载失败、LM Studio embedding 失败或截图 VLM extraction 失败时不丢弃输入；记录保存为降级状态，能通过 show/list/update/revoke/delete 管理，有文本时继续进入 FTS。
- `--auto-captured` 写入状态为 `auto_captured`。

### Search

```bash
lifemesh input search "<query>" \
  [--kind note|screenshot|event|mood|activity|task] \
  [--status active|auto_captured|promoted|revoked] \
  [--since <date>] \
  [--until <date>] \
  [--sensitivity-cap Private] \
  [--limit 20]
```

行为：

- 使用向量相似度 + FTS + 时间新鲜度 + kind boost 混合排序；向量不可用时使用 FTS-only。
- 默认排除 `revoked` 和 deleted tombstone。
- 默认 `sensitivity-cap=Private`，排除 `Sensitive`。

### List / Show

```bash
lifemesh input list \
  [--kind note|screenshot|event|mood|activity|task] \
  [--status active|auto_captured|promoted|revoked] \
  [--since <date>]

lifemesh input show <input-id>
```

`show` 必须展示：

- input 原文或摘要
- kind / declared_kind / inferred_kind / effective_kind
- status
- sensitivity
- source_type 和 source_excerpt
- embedding / extraction 状态
- raw asset metadata
- derived object links
- audit events

### Update

```bash
lifemesh input update <input-id> \
  [--text "..."] \
  [--kind note|screenshot|event|mood|activity|task] \
  [--occurred-at <datetime>] \
  [--sensitivity Internal|Private|Sensitive] \
  [--tags "a,b,c"] \
  [--declared-kind note|event|mood|activity|task]
```

行为：

- 修改写 audit event。
- 更新后使旧 embedding 标记 stale，并重新 embedding。
- 修改截图 kind 不删除原始 asset。

### Revoke / Delete

```bash
lifemesh input revoke <input-id>
lifemesh input delete <input-id>
```

- `revoke`：状态改为 `revoked`，停止检索和 Bundle 准入，保留 tombstone、审计和派生关系。
- `delete`：删除 managed raw asset、embedding、extraction 和主记录内容，只保留最小 deletion tombstone。

### Promote

```bash
lifemesh input promote <input-id> --to task \
  --title "..." [--due-at <datetime>] [--status open]

lifemesh input promote <input-id> --to event \
  --title "..." --starts-at <datetime> [--ends-at <datetime>] [--timezone <tz>]

lifemesh input promote <input-id> --to memory \
  --text "..." [--scope <range>] [--confidence <0-1>]

lifemesh input promote <input-id> --to fact \
  --statement "..." [--source-ref <ref>...]

lifemesh input promote <input-id> --to candidate \
  --statement "..." --type fact|preference|relationship|task|decision \
  [--confidence <0-1>] [--risk low|medium|high]
```

硬规则：

- Promote 必须带目标对象关键字段。
- Agent 可以辅助提取字段，但缺字段时只能转 candidate 或停留在 Inbox。
- `auto_captured` 不能被 Agent 自动 promote；必须有用户确认。
- Promote 创建 inbox-derived 最小目标对象表记录，并保留 `derived_from_input_id`。
- Manual Input 不创建 SourceRevision；promote 后的目标对象通过 `derived_from_input_id`、input content_hash 和 audit event 保留来源。
- Phase 1 的 `task` / `event` promote 不接入系统日历、提醒事项或外部任务应用，只验证本地最小对象闭环。

## 传统写命令

这些命令仍是契约，后续会与 Manual Input promote 共享底层对象表。

```bash
lifemesh fact add "<statement>" [--source-ref <ref>...] [--user-asserted]
#   → Canonical Fact, acceptance_path=manual；无来源时标记 user_asserted

lifemesh task add "<todo>" [--due <date>]
#   → Task

lifemesh remember "<info>" [--scope <range>] [--expires <date>]
#   → 显式 Memory

lifemesh candidate add "<statement>" --type fact|preference|relationship|task|decision [--source-ref ...]
#   → Knowledge Candidate 进 inbox，lifecycle=confirm_required
```

## Agent 写入规则

- Agent 可以自主判断非高敏、个人相关且值得记录的信息，并调用 `input add --auto-captured`。
- Agent 自动捕获后必须在回复中说明：input id、kind、摘要、sensitivity、Bundle 可用性。
- Agent 自动捕获只进入 Manual Input Inbox，状态为 `auto_captured`。
- Agent 不得自动 promote。
- Agent 推断出的事实、待办、记忆和决策不得直接写入目标层，必须走 `input promote --to candidate` 或用户明确确认后的 promote。
- 用户明确提交的高敏信息可写入 Inbox，但必须标记 `Sensitive`；Agent 不得自动捕获明显高敏信息。`Sensitive` 默认不进入 Bundle、长期记忆、事实层或模型上下文。

## 本地模型与配置

默认配置文件：

```text
~/.lifemesh/config.json
```

配置优先级：

```text
CLI 参数 > 环境变量 > config 文件
```

Manual Input 可选本地模型配置：

```json
{
  "lmstudio_base_url": "http://localhost:1234/v1",
  "embedding_model": "<local-embedding-model>",
  "vlm_model": "<local-vlm-model>",
  "sqlite_vec_extension": "/path/to/vec0"
}
```

可选 Obsidian 配置：

```json
{
  "obsidian_vault": "/path/to/vault"
}
```

环境变量：

```text
LIFEMESH_HOME=~/.lifemesh
LIFEMESH_LMSTUDIO_BASE_URL=http://localhost:1234/v1
LIFEMESH_EMBEDDING_MODEL=<local-embedding-model>
LIFEMESH_VLM_MODEL=<local-vlm-model>
LIFEMESH_SQLITE_VEC_EXTENSION=/path/to/vec0
LIFEMESH_OBSIDIAN_VAULT=/path/to/vault
```

约束：

- LM Studio 只作为本地 provider，不把模型运行时绑死进 LifeMesh；当前实现会在配置缺失或调用失败时降级为 FTS-only / metadata-only。
- sqlite-vec 扩展由用户通过路径提供，不 vendoring 到仓库；加载失败时 Manual Input 继续使用 SQLite/FTS，并记录 `vector_error`。
- 每次 embedding / extraction 记录 provider、base_url、model、dimension、content_hash 和时间。
- 远程 embedding 只能作为后续显式 opt-in，不是第一版默认。

## 事实复核与撤销命令

当 Source Revision 或 Manual Input 变为 stale / missing / revoked / deleted，依赖它的 Canonical Fact 进入复核队列。

```bash
lifemesh fact review list
lifemesh fact review show <fact-id>
lifemesh fact review revalidate <fact-id> --source-ref <ref>
lifemesh fact review revise <fact-id> "<statement>" [--source-ref <ref>...]
lifemesh fact review invalidate <fact-id>
lifemesh fact revoke <fact-id>
```

硬规则：

- Agent 不得替用户执行 `revalidate` / `revise` / `invalidate` / `revoke`，除非用户明确发出该操作指令。
- `needs_review` / `invalid` / `superseded` / `revoked` 的事实不得作为 `fact` slice 进入 Bundle。
- 所有复核与撤销命令都必须生成审计事件。

## JSON Bundle schema（v1）

```json
{
  "schema_version": "1",
  "bundle_id": "uuid",
  "task": { "description": "...", "agent_capability": "search" },
  "permission_scope": {
    "allowed_sources": ["obsidian", "manual-input"],
    "sensitivity_cap": "Private"
  },
  "assembled_at": "ISO-8601",
  "slices": [
    {
      "slice_id": "...",
      "evidence_role": "raw",
      "provenance": {
        "source": "manual-input",
        "input_id": "mi_...",
        "status": "active",
        "kind": "mood",
        "content_hash": "sha256:..."
      },
      "citation_status": "current",
      "sensitivity": "Private",
      "content": "...用户记录..."
    }
  ],
  "excluded_sources": [
    { "source": "manual-input", "input_id": "mi_...", "reason": "sensitivity_cap_exceeded" }
  ],
  "freshness_report": [
    { "slice_id": "...", "citation_status": "stale", "note": "来源已修改，建议复核" }
  ]
}
```

约束：

- 每个 slice 必带 `evidence_role` + `provenance` + `citation_status`。
- Obsidian raw slice 带 `note_path`、`revision_id`、`heading`、`line_range`。
- Manual Input raw slice 带 `input_id`、`kind`、`status`、`content_hash`。
- `active` Manual Input 默认可作为 `raw`。
- `auto_captured` Manual Input 最多作为 `lead`，回答必须标注未复核。
- `promoted` input 通过目标对象进入对应层，原 input 只作为 provenance。
- `revoked` 和 deleted tombstone 不进入新 Bundle。
- `Sensitive` 默认被 `--sensitivity-cap Private` 排除。
- `excluded_sources` / `freshness_report` 即使为空也要在。

## Skill 契约

skill 随仓库版本化（如 `skills/lifemesh/SKILL.md`），内容契约：

1. **何时用**：当任务需要用户的所有信息或需要写入用户个人上下文时调用。
2. **怎么读**：`bundle` 拿上下文；默认 source 为 `obsidian`，跨 Obsidian + Manual Input 时显式使用 `--source all`。
3. **怎么写**：Manual Input 走 `input add`；Agent 自动捕获必须 `--auto-captured` 并透明说明。
4. **怎么检索**：`input search` 可直接查 Inbox，`bundle` 可跨 Obsidian + Manual Input 组装上下文。
5. **怎么 promote**：只有用户明确确认时才 `input promote` 到 task/event/memory/fact/candidate。
6. **怎么消费**：事实回答只用 `fact` + `raw`；`lead` 标未复核；`context` 只调语气；stale/missing/revoked 必须提示。
7. **边界**：Agent 不能自动 promote，不能把 `auto_captured` 当事实，不能引用失效来源。

## 非目标

- 不在第一版做后台截屏、系统日历同步或活动追踪器接入。
- 不默认使用远程 embedding API。
- 不把截图 VLM extraction 直接当 Canonical Fact。
- 不暴露 `automation`（外发、不可逆动作），仍 deferred 在阶段 6。
- 不引入长期运行 server；LM Studio 是用户本机已启动的本地 provider。
