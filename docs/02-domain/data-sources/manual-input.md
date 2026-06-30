# Manual Input

状态：draft
最后更新：2026-06-30
职责边界：定义 Phase 1 后续 milestone 中，用户和 Agent 主动提交的截图、日程、心情、活动、待办和备注如何进入 LifeMesh Inbox、索引、Bundle 和 promote 流程。不定义后台截屏、系统日历同步、活动追踪器接入或远程 embedding 默认策略。

## Source

- 名称：Manual Input
- 类型：用户级本地数据源
- 所有人：用户
- 接入方式：CLI、Agent Skill 受控调用、本地 Raw Vault
- 默认数据目录：`~/.lifemesh/`
- 主存储：SQLite
- 检索：SQLite FTS + 本地 embedding / SQLite 向量扩展

## Purpose

Manual Input 用于补齐 LifeMesh 暂未自动接入的数据源，并立即验证“记录后可检索、可进入 Bundle、可被 Agent 使用”的闭环。

典型输入：

- 手机或电脑截图
- 手动录入的日程、会议、约定、DDL
- 心情记录
- 活动记录
- 待办
- 临时备注、事实材料、要记住的信息

Manual Input 是缓冲层和检索源，不等同于事实层。进入 Task、Event、Memory、Canonical Fact 或 Knowledge Candidate 必须通过 promote。

Manual Input 不使用 SourceRevision。它的来源身份由 input record、可选 extraction、content_hash、状态和 audit event 表达；当它进入 Bundle 或支撑 Canonical Fact 时，作为 source reference 参与 current / revoked / deleted 准入检查。

## Kinds

第一版支持六个顶级 `kind`：

| kind | 说明 | 默认状态 | 默认 Bundle role |
|---|---|---|---|
| `note` | 泛用备注、事实材料、临时信息 | `active` 或 `auto_captured` | strong 可作 `raw`，weak / auto_captured 作 `lead` |
| `screenshot` | 图片或截图文件 | `active` 或 `auto_captured` | extraction strong 可作 `raw`，weak / auto_captured 作 `lead` |
| `event` | 手动日程、会议、约定、DDL | `active` | strong 可作 `raw`，promote 后进入 Event |
| `mood` | 心情、状态、主观感受 | `active` 或 `auto_captured` | strong 可作 `raw`，weak / auto_captured 作 `lead`，通常不作为事实 |
| `activity` | 活动记录、运动、出行、工作片段 | `active` 或 `auto_captured` | strong 可作 `raw`，weak / auto_captured 作 `lead` |
| `task` | 待办或行动项 | `active` | strong 可作 `raw`，promote 后进入 Task |

高敏语义如 health、location、finance、relationship 不作为第一版顶级 kind。只有用户明确提交时，才可通过基础 kind + `sensitivity=Sensitive` + tags 表达；这不等同于正式接入高敏数据源。

## Data Scope

| 输入 | 最小字段 | 额外字段 | 默认敏感级别 |
|---|---|---|---|
| 截图 | file、occurred_at、declared_kind、note、sensitivity | original_path、stored_path、sha256、media_type、inferred_kind、effective_kind、extraction_status | Private；含身份/金融/健康/位置/第三方信息时 Sensitive |
| 日程 | text/title、starts_at、timezone、sensitivity | ends_at、location、participants、source_excerpt | Private |
| 心情 | text、occurred_at、sensitivity | mood_label、intensity、tags、source_excerpt | Private；健康诊断或自伤风险为 Sensitive |
| 活动 | text、started_at 或 occurred_at、sensitivity | ended_at、location_hint、tags | Private；精确位置或健康数据为 Sensitive |
| 待办 | text/title、created_at、sensitivity | due_at、project、priority | Private |
| 备注 | text、created_at、sensitivity | tags、purpose、source_excerpt | Internal 或 Private |

真实个人截图不得进入仓库或测试 fixture。测试只能使用虚构或脱敏图片。

## Storage

默认路径：

```text
~/.lifemesh/lifemesh.db
~/.lifemesh/raw-assets/manual-input/YYYY/MM/<input-id>.<ext>
```

配置路径：

```text
~/.lifemesh/config.json
```

Manual Input 的本地模型与向量配置为 `lmstudio_base_url`、`embedding_model`、`vlm_model` 和 `sqlite_vec_extension`；缺失时降级为 metadata-only 或 FTS-only。同名 `LIFEMESH_*` 环境变量可覆盖 config，CLI 参数优先级最高。Obsidian vault 也走同一配置层：`--vault` > `LIFEMESH_OBSIDIAN_VAULT` > config `obsidian_vault`。

文件策略：

- 截图默认复制到 LifeMesh Raw Vault，并保留 `original_path`。
- 撤销只停止使用 managed copy，不碰原文件。
- 删除会移除 managed copy、embedding、extraction 和主记录内容，只保留最小 deletion tombstone。
- `~/.lifemesh/` 权限为 `0700`，数据库和 raw asset 文件权限为 `0600`。
- 第一版不做透明加密；加密方案单独评估。

## Indexing

Manual Input 第一版必须可检索：

- FTS：索引用户文本、标题、标签、截图 extraction、模型摘要和必要元数据。
- Embedding：默认通过 LM Studio 本地 OpenAI-compatible `/v1/embeddings`。
- Vector store：通过配置路径加载用户提供的 `sqlite-vec` 扩展；第一版不 vendoring 二进制，扩展不可用时降级为 FTS-only。
- Embedding 粒度：每条 Manual Input 至少一个主 embedding，覆盖用户文本和可检索 extraction 内容。
- 排序：向量相似度 + FTS 匹配 + 时间新鲜度 + kind boost。
- 命中分级：FTS 命中或向量分数达到 `vector_evidence=0.75` 才是 `strong`；向量分数达到 `vector_lead=0.45` 但低于证据阈值时是 `weak`，只能作为低置信线索。

每条 embedding 至少记录：

- provider
- base_url
- model
- dimension
- embedded_at
- content_hash
- embedding_subject：`input_text`、`asset_extraction` 或 `promoted_object`
- status：`ready`、`failed`、`stale`

## Screenshot Extraction

截图默认同步执行本地 OCR / VLM extraction，可通过 `--no-extract` 跳过；跳过时仍必须提供可检索文本，并成功生成 embedding。

VLM provider：

- LM Studio 本地 OpenAI-compatible endpoint
- 模型：通过 `vlm_model` 配置指定，例如 `qwen3-vl-8b` 或等价本地视觉模型

截图类型处理：

- `declared_kind`：录入时由用户或 Agent 初始设置。
- `inferred_kind`：OCR / VLM 后模型判断。
- `effective_kind`：用于搜索和 Bundle 的最终类型。
- 如果 declared 与 inferred 冲突，保留 `kind_conflict=true`，不静默覆盖。

VLM 输出可参与检索和 Bundle，但必须带 model/provider/confidence/extracted_at。它不是 Canonical Fact，promote 仍需用户明确确认。

## Agent Capture

Agent 可以自主判断对个人数据有价值的非高敏信息并写入 Inbox。自动捕获规则：

- 状态写为 `auto_captured`。
- 保存轻量来源：`source_session_id`、`source_message_id`、`source_excerpt`、`captured_reason`。
- 不保存整段对话。
- 写入后回复必须说明 input id、kind、摘要、sensitivity、Bundle 可用性。
- Agent 不得自动 promote。

Agent 不得自动捕获明显高敏内容。用户明确提交的高敏内容必须标记 `Sensitive`，默认不可进入 Bundle、长期记忆、事实层或模型上下文。

## Promote

Manual Input 可以 promote 到：

- Task
- Event
- Memory
- Canonical Fact
- Knowledge Candidate

Promote 必须带目标对象的明确字段。缺关键字段时，只能转 candidate 或停留在 Inbox。Promote 后：

- 创建 inbox-derived 最小目标对象表记录。
- 写入 `derived_from_input_id`。
- 记录 audit event。
- 原 input 状态改为 `promoted`，但仍作为 provenance 保留。

Phase 1 的 Task / Event promote 只验证本地 Inbox 到最小目标对象的闭环，不接入系统日历、提醒事项或外部任务应用同步。

## Bundle Admission

`lifemesh bundle --source all` 会让 Obsidian 和 Manual Input 各自返回 source-backed candidates，再交给 BundleAssembler 统一组装。CLI 默认仍为 `--source obsidian`，用于保持既有只读原型在无 Manual Input 配置时可用。

Manual Input adapter 的职责是返回 input record / extraction / content_hash / status / sensitivity / 检索排序等候选元数据。最终准入、与其他来源的分层选择、去重、多样性和 `assembly_report` 诊断由 BundleAssembler 执行。

Manual Input 准入规则：

- `active` + `retrieval.match_status=strong`：可按权限作为 `raw` slice。
- `active` + `retrieval.match_status=weak`：最多作为 `lead`，必须标注弱相关近邻，不能支撑事实回答。
- `auto_captured`：可检索；进入 Bundle 时最多作为 `lead`，回答必须标注未复核。
- `promoted`：通过目标对象进入对应层，原 input 只作 provenance。
- `revoked` / deleted tombstone：不进入检索或 Bundle。
- `Sensitive`：默认被 `--sensitivity-cap Private` 排除；只有显式 cap 到 `Sensitive` 才可进入。

## Permissions

- 默认可读主体：用户显式授权的 LifeMesh CLI / Agent。
- 默认可写主体：用户和遵守 skill 规则的 Agent。
- Agent 可自动写入低/中敏 Inbox，但必须透明说明。
- Agent 不能自动捕获明显高敏内容，也不能自动 promote。
- 用户明确提交的高敏数据本地可记录和 embedding，但默认不可复用。

## Audit

每条 Manual Input 至少记录：

- input_id
- kind / declared_kind / inferred_kind / effective_kind
- status
- created_at / occurred_at
- source_type：`manual_cli`、`agent_auto_capture`、`agent_delegated`
- source_session_id / source_message_id / source_excerpt
- sensitivity
- tags
- content_hash
- asset metadata
- embedding_status
- extraction_status
- derived object links
- add / update / promote / revoke / delete audit events

## Deletion And Revocation

- `revoke`：停止检索和 Bundle 准入，保留 tombstone、审计和派生关系。
- `delete`：移除 managed raw asset、embedding、extraction 和主记录内容，只保留最小 deletion tombstone。
- 依赖该 input 的 Candidate 标记 discarded 或 needs_review。
- 依赖该 input 的 Canonical Fact 进入 `validity=needs_review`。
- 依赖该 input 的 Memory 需要展示来源撤销，并允许删除或修订。

## Threats

| 威胁 | 说明 | 初始缓解 |
|---|---|---|
| Agent 沉默记忆 | Agent 自动捕获后用户不知道 | 回复必须说明 id、kind、摘要、sensitivity 和 Bundle 可用性 |
| 截图泄露第三方信息 | 截图可能包含聊天、邮件、客户、家庭成员或身份信息 | 默认 Private；高敏线索升为 Sensitive；真实截图不进 fixture |
| VLM 误读 | 本地模型错误理解截图 | extraction 带 provider/model/confidence；promote 必须确认 |
| 高敏信息进入普通 Bundle | Sensitive 被默认复用 | 默认 sensitivity cap 为 Private；Sensitive 不进入普通 Bundle |
| 本地模型不可用 | LM Studio 未启动或模型未加载 | 降级保存：记录和 managed asset 保留，FTS 可用时继续检索，状态和 audit 记录失败原因 |
| Prompt injection | 截图或手动文本诱导 Agent 越权 | 输入内容作为 data，不作为 instruction；工具层隔离 |
| 删除不彻底 | 原始输入删了但派生事实还在 | tombstone + derivation links + Fact Review |
