# ADR-0008: Manual Input Inbox With Local Retrieval

状态：accepted
日期：2026-06-29

## Context

LifeMesh 第 1 阶段已经有 `lifemesh bundle` 只读原型，并在契约层保留了 `fact add`、`task add`、`remember` 和 `candidate add`。只读原型验收后，Phase 1 的后续 milestone 需要接收用户主动提供的数据，包括手机/电脑截图、手动日程、心情记录、活动记录、待办和临时备注。

这些输入不能只被保存；如果不能被检索、进入 Context Bundle 并被 Agent 使用，就无法验证 LifeMesh 的价值。同时，它们也不能绕过 Personal Context Layer 的权限、溯源、审计和撤销边界。

本决策基于以下产品方向：

- 使用统一 Manual Input Inbox，而不是为每种输入先做独立入口。
- 入口优先做 CLI，并同步 agent skill，使 Agent 可通过受控命令调用。
- Agent 可以自主判断与个人数据相关且值得记录的信息，自动写入 Inbox，但必须在回复中明确说明记录内容。
- 用户明确提交的高敏信息可以进入 Inbox，但标记 `Sensitive`；Agent 不得自动捕获明显高敏内容。Sensitive 默认不进入 Bundle、长期记忆、事实层或模型上下文。
- 记录必须可检索、可进入 `lifemesh bundle`，否则手动输入闭环不可验证。

## Decision

ADR-0008 是 Phase 1 后续 milestone，不改变当前只读 Obsidian bundle 原型的完成定义。该 milestone 把 Manual Input 作为统一 Inbox 和本地检索源实现。Manual Input 第一版必须覆盖记录、检索、Bundle 准入、更新、撤销、删除和 promote 闭环。

### 输入类型

第一版支持六个 `kind`：

- `note`
- `screenshot`
- `event`
- `mood`
- `activity`
- `task`

`health`、`location`、`finance`、`relationship` 等高敏语义先不作为顶级 kind。只有用户明确提交时，才通过 `kind=note` 或对应基础 kind + `sensitivity=Sensitive` + tags 表达，避免过早产品化高敏分类或正式接入高敏数据源。

### 存储与索引

Manual Input 的默认数据目录是用户级 `~/.lifemesh/`，不放进仓库。

第一版存储策略：

- SQLite 作为主存储：`~/.lifemesh/lifemesh.db`
- Raw Vault 管理截图副本：`~/.lifemesh/raw-assets/manual-input/YYYY/MM/<input-id>.<ext>`
- JSONL 只作为可选 append-only audit/export log，不承担主查询路径。
- `~/.lifemesh/` 使用 `0700` 权限，数据库和 raw asset 使用 `0600` 权限。
- 第一版不做 SQLite 透明加密；后续单独评估 SQLCipher 或 OS keychain。

第一版检索策略：

- SQLite FTS 作为文本检索和 fallback。
- 使用本地 embedding + 用户配置路径加载的 `sqlite-vec` 作为主要语义检索路径。
- 默认本地 embedding provider 为 LM Studio OpenAI-compatible API。
- `sqlite-vec` 扩展不 vendoring 到仓库；缺配置或加载失败时 Manual Input 降级到 SQLite/FTS。
- schema 必须保留 provider / model / dim / content_hash，避免长期锁死具体扩展。
- 排序采用混合策略：向量相似度 + FTS 匹配 + 时间新鲜度 + kind boost。

### 本地模型

第一版默认本地模型路径：

- 文本 embedding：LM Studio 本地 OpenAI-compatible `/v1/embeddings`。
- 截图 OCR / VLM：LM Studio 本地 `qwen3-vl-8b` 或等价本地视觉模型。

截图录入默认同步执行 OCR / VLM extraction，可用 `--no-extract` 跳过。第一版采用降级依赖行为：

- 缺少 `lmstudio_base_url`、`embedding_model`、`vlm_model` 或 `sqlite_vec_extension` 时记录仍可保存，但 embedding、extraction 或 vector 状态标记为 failed/degraded。
- `input add` 优先调用 LM Studio `/v1/embeddings`；失败时保留 SQLite/FTS，有文本则仍可关键词检索。
- `input add --kind screenshot` 默认尝试调用 LM Studio VLM；失败时保留 managed asset 和用户文本，模型输出为空且 extraction_status=failed。
- `sqlite-vec` 扩展从配置路径加载；加载失败时向量检索不可用，但 FTS 和管理命令继续工作。

截图是载体，不是语义类型。截图录入时可先给 `declared_kind`；OCR / VLM 后写入 `inferred_kind`。最终检索和 Bundle 使用 `effective_kind`。当两者冲突时保留冲突信息，不能静默覆盖。

### Inbox 状态

Manual Input 使用五态：

| 状态 | 含义 | Bundle 行为 |
|---|---|---|
| `active` | 用户明确提交或确认的 Inbox 记录 | 可按权限作为 `raw` slice |
| `auto_captured` | Agent 自主判断并自动记录 | 可检索；进入 Bundle 时最多作为 `lead` |
| `promoted` | 已派生为 Task / Event / Memory / Canonical Fact / Knowledge Candidate | 目标对象进入对应层，input 保留 provenance |
| `revoked` | 用户撤销，不再使用 | 不进入检索或 Bundle，仅保留 tombstone / audit |
| `deleted` | 用户删除内容 | 不进入检索或 Bundle，仅保留最小 deletion tombstone / audit |

`auto_captured` 不能自动 promote。Promote 必须来自用户明确确认、批处理接受或后续显式规则；第一版不做自动 promote 规则。

Manual Input 不使用 `SourceRevision` 表达每次编辑。它通过 input record、extraction、content_hash、状态和 audit event 表达来源身份、新鲜度与撤销路径。进入 Bundle 或支撑 Canonical Fact 时，它作为 source reference 参与 current / revoked / deleted 准入检查。

### Agent 自动捕获

Agent 可以自主判断非高敏、个人相关且值得记录的信息并写入 Manual Input Inbox。写入后必须在回复中透明说明：

- `input_id`
- `kind`
- 摘要
- `sensitivity`
- Bundle 可用性

Agent 自动捕获只写入 Inbox，状态为 `auto_captured`。它不能直接创建 Task、Event、Memory、Canonical Fact 或 Knowledge Candidate。

Agent 不得自动捕获明显高敏内容。用户明确提交的高敏内容可进入 Inbox，但必须标记 `Sensitive`。默认 sensitivity cap 为 `Private` 时，Sensitive 记录不进入 Bundle、长期记忆、事实层或模型上下文。

### Promote

第一版实现 `promote` 到 inbox-derived 最小对象表，而不是只记录状态：

- `task`
- `event`
- `memory`
- `fact`
- `candidate`

Promote 必须带明确字段。Agent 可以辅助提取字段，但缺关键字段时只能 promote 到 `candidate` 或停留在 Inbox，不能强行创建正式对象。

所有目标对象必须保留 `derived_from_input_id` 和审计事件。Phase 1 的 `task` / `event` promote 只生成 LifeMesh 本地最小对象，用于验证 Inbox 到目标层的闭环；系统日历、提醒事项或外部任务应用同步属于第 2 阶段。

### Update, Revoke, Delete

第一版支持：

- `input update`：修改文本、kind、时间、标签、敏感级别等，所有修改写 audit。
- `input revoke`：停止检索和 Bundle 准入，保留 tombstone 和审计。
- `input delete`：删除 managed raw asset、embedding、extraction 和主记录内容，保留最小 deletion tombstone。

## Consequences

正向影响：

- 手动输入不只是收集材料，而是立刻可检索、可组装进 Bundle、可被 Agent 使用。
- 使用本地 LM Studio 和 SQLite 避免第一版引入远程 embedding 或外部向量服务。
- 降级语义避免模型或向量依赖失败导致用户输入丢失，同时用状态和审计暴露不可检索或部分可检索记录。
- Agent 自动捕获与透明说明并存，减少沉默记忆风险。
- Promote 到真实对象表让 Inbox 能闭环到 Task、Event、Memory、Canonical Fact 和 Candidate。
- 删除、撤销、敏感级别和 provenance 在第一版就进入核心模型。

代价：

- 第一版复杂度明显高于纯 JSONL Inbox。
- 需要处理本地 LM Studio 未启动、模型未加载、embedding 维度变化、sqlite 向量扩展不可用等降级路径。
- 截图 VLM extraction 可能误读，必须通过 `inferred_kind`、confidence、model metadata 和 promote 确认来约束。
- SQLite 不透明加密意味着本机文件权限是第一版安全边界，需要后续评估加密。

## Alternatives Considered

1. **只用 JSONL append-only store**
   - 未选择。JSONL 不适合作为主查询、向量检索、promote 关系和分析的长期基础。

2. **先做 FTS，不做向量检索**
   - 未选择。用户明确要求第一版可验证语义检索效果；没有向量检索会让记录价值过低。

3. **远程 embedding API 优先**
   - 未选择。Manual Input 可能包含高敏个人信息；默认远程 embedding 会破坏本地优先边界。

4. **截图只保存文件，不做 OCR / VLM**
   - 未选择。截图如果不能被理解和检索，会降低 Manual Input 的核心价值。第一版允许本地 VLM extraction，但输出不自动变成事实。

5. **Agent 自动记录后可自动 promote**
   - 未选择。自动 promote 会把闲聊、误读或模糊信息直接写进长期层；第一版必须用户确认。

## Implementation Notes And Follow-ups

- CLI 已覆盖 `input add/search/list/show/update/revoke/delete/promote`。
- `lifemesh bundle` 支持 `--source all|obsidian|manual-input`；为兼容旧只读原型，默认仍为 `obsidian`，跨源组装需显式 `--source all`。
- Manual Input adapter 负责返回带 input record、content_hash、status、sensitivity 和检索排序的 candidates；最终 raw/lead 准入、与 Obsidian 等来源的跨源选择、以及 `assembly_report` 诊断由 BundleAssembler 执行。
- 配置统一走 `~/.lifemesh/config.json`、环境变量和 CLI 参数；Obsidian vault 同样使用该 fallback 链。
- 测试使用脱敏/虚构 fixture 和 mocked LM Studio HTTP，不写入真实个人数据。
- 2026-06-30 已用真实本机 LM Studio 模型和真实 sqlite-vec 扩展完成首次手工验收：embedding 模型为 `text-embedding-qwen3-embedding-0.6b`，维度 1024；截图 VLM 为 `qwen/qwen3-vl-8b`。后续仍需补充长期性能边界、检索 score threshold 和空结果展示策略。
