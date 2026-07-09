# CLI Contract

状态：draft
最后更新：2026-07-09
职责边界：定义第 1 阶段 LifeMesh CLI 的命令、JSON Bundle schema 和配套 skill 契约。实现状态以本文件的“当前实现”段落、README 和测试为准。

## 定位

第 1 阶段 Agent 接口 = 薄 CLI + skill（见 `ADR-0006`）。CLI 读索引、组装 JSON Context Bundle、写入 Manual Input、事实、待办、记忆和候选；skill 指导 Agent 如何调用与消费。不引入运行时 server。

## 当前实现

当前已实现：

- `lifemesh bundle` 的 Obsidian 只读链路。
- Obsidian Source Revision、raw slice、路径排除、sensitivity cap、stale / missing 检测。
- Manual Input Inbox：`input add/search/list/show/update/revoke/delete/promote`。
- Manual Input SQLite 主库、FTS、sqlite-vec 向量检索、LM Studio embedding 和截图 VLM extraction。
- `lifemesh bundle --source manual-input`。
- `lifemesh bundle --source all` 通过 source-neutral `BundleAssembler` 统一组装 Obsidian 与 Manual Input candidates，不拼接两个已完成 Bundle。
- JSON Bundle 包含 `assembly_report` 诊断字段，用于解释候选、准入和选择策略。
- Bundle slice 包含 `citation` 展示字段；Manual Input 检索结果包含 `match_status`、`match_reason`、`evidence_eligible` 和 `score_breakdown`。
- Knowledge Candidate inbox 最小 CLI：`candidate add/list/show/discard`，写入本地 `lifemesh.db`，用于 `confirm_required` 候选的异步复核。
- RumorClaim / UnverifiedClaim 本地结构化 CLI MVP：`rumor add/list/show/keep/dismiss/expire/promote`、持久化门槛、review queue、最小 source envelope、`bundle --source rumor` 和 `bundle --source all --include-unverified`。

当前未实现但已进入后续契约：

- `candidate confirm/edit/merge/defer` 和 confirm 后升级到 Canonical Fact / Memory / Task。
- 自动 source adapter 产出 RumorClaim 前的 `rumor_policy`、截图/图片自动抽取、来源融合、自动事实核查、review UI。

兼容性说明：`lifemesh bundle` 默认仍为 `--source obsidian`，避免旧的只读原型被 Manual Input 本地依赖状态影响；跨源合并必须显式使用 `--source all`。

## 读命令

```bash
lifemesh bundle "<task>" \
  [--source all|obsidian|manual-input|rumor] \
  [--vault <path>] \
  [--out <path>] \
  [--max-slices 20] \
  [--sensitivity-cap Private] \
  [--include-unverified] \
  [--home <path>] \
  [--lmstudio-base-url <url>] \
  [--embedding-model <name>] \
  [--vlm-model <name>] \
  [--sqlite-vec-extension <path>]
```

- `<task>`（必填）：自然语言任务描述。
- `--source`：Source Adapter，默认 `obsidian`；显式 `all` 会让 Obsidian 和 Manual Input 各自返回 source-backed candidates，再由 `BundleAssembler` 统一准入、分层、去重和选择；也可筛选 `manual-input` 或 `rumor`。
- `--vault <path>`：Obsidian vault 路径；fallback 为 `LIFEMESH_OBSIDIAN_VAULT`，再到 config `obsidian_vault`。
- `--out <path>`：写 JSON 到文件（默认写 stdout）。
- `--max-slices`：Bundle 大小上限，防爆上下文。
- `--sensitivity-cap`：允许的最高敏感级，默认 `Private`；`Sensitive` 记录默认排除。
- `--include-unverified`：只在 `--source all` 时把 RumorClaim candidates 纳入组装；默认 false，避免未验证线索污染普通 Bundle。`--source rumor` 等价于专门查看 RumorClaim lead。
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
- `match_status=strong` 表示可作为证据候选：FTS 命中，或向量分数达到 `vector_evidence=0.75`。
- `match_status=weak` 表示低置信语义近邻：向量分数达到 `vector_lead=0.45` 但低于证据阈值；它只可作为线索，不能作为事实证据。
- 返回项必须带 `evidence_eligible` 和 `score_breakdown`，避免把近邻误读为精确命中。
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
#   → Knowledge Candidate 进 inbox，lifecycle=confirm_required；当前已实现
```

当前已实现的 Candidate inbox 命令：

```bash
lifemesh candidate add "<summary>" \
  --type fact|preference|relationship|task|decision \
  [--source-ref <ref>...] \
  [--confidence 0.5] \
  [--risk low|medium|high] \
  [--why-suggested "..."] \
  [--expires-at <datetime>]

lifemesh candidate list [--type fact|preference|relationship|task|decision] [--lifecycle confirm_required|inbox|discard] [--limit 20]
lifemesh candidate show <candidate-id>
lifemesh candidate discard <candidate-id> [--reason "..."]
```

Candidate add 默认 `lifecycle=confirm_required`、`confidence=0.5`、`risk=medium`。默认 `list` 隐藏 `discard`；显式传 `--lifecycle discard` 才列出已丢弃候选。`discard` 只写 tombstone，不删除历史记录。

## RumorClaim 命令

RumorClaim 是 Phase 1 follow-on 本地结构化 CLI MVP。它处理可信度未知的文字片段、截图和图片中抽取出的 claim，不作为 Manual Input `kind`，也不直接写入 Knowledge Candidate。当前实现要求调用方先提供结构化字段；自动 source adapter、截图/图片自动抽取、外部 fact-check 和 review UI 仍是后续能力。

```bash
lifemesh rumor add \
  --claim-text "..." \
  --claim-type factual_claim|relationship_claim|intent_or_plan_claim|risk_claim|preference_claim|unknown_claim \
  --user-relevance none|low|medium|high \
  --impact low|medium|high|critical \
  [--entity-mention "..."] \
  [--relation-mention "..."] \
  [--relevance-reason "..."] \
  [--impact-reason "..."] \
  [--extraction-confidence low|medium|high] \
  [--evidence-state unknown|single_source|corroborated|contradicted] \
  [--claim-quality vague|specific|verifiable] \
  [--assessment unverified|weak|plausible|supported|contradicted] \
  [--sensitivity Public|Internal|Private|Sensitive|Restricted] \
  [--review-queue general_review|conflict_review|sensitive_review] \
  [--source-adapter <name>] \
  [--source-item-id <id>] \
  [--material-fingerprint <digest>] \
  [--source-summary "..."] \
  [--raw-retention none|temporary|user_saved] \
  [--review-pointer <pointer>] \
  [--expires-at <datetime>]

lifemesh rumor list \
  [--queue general_review|conflict_review|sensitive_review] \
  [--status parked|reviewed_parked|candidate_created|dismissed|expired] \
  [--sensitivity-cap Private] \
  [--limit 20]

lifemesh rumor show <rumor-claim-id>

lifemesh rumor keep <rumor-claim-id> [--reason "..."]

lifemesh rumor dismiss <rumor-claim-id> [--reason "..."]

lifemesh rumor promote <rumor-claim-id> --to candidate \
  --statement "..." --type fact|preference|relationship|task|decision \
  [--confidence <0-1>] [--risk low|medium|high]

lifemesh rumor expire <rumor-claim-id>
```

硬规则：

- RumorClaim 主体是 `claim_text`、`claim_type`、`entity_mentions[]` 和 `relation_mentions[]`，不是原始材料归档。
- 原始文字、截图或图片默认只进入 temporary parsing sandbox；长期只保留最小 `source_envelope`。
- 第一版不做去重、合并或重复次数可信度提升。
- `user_relevance` 和 `impact` 是必填初筛字段；只有通过最低初筛的 claim 才持久化：`user_relevance >= medium OR impact >= high`。
- `assessment` 由规则派生为主；第一版不自动联网核查。
- 未显式提供可信度字段时，`evidence_state=unknown`，`assessment=unverified`。
- `keep` 把人工已检视并决定继续保留的 claim 标记为 `reviewed_parked`；它不进入默认复审列表，但显式请求 RumorClaim lead 时仍可被 Bundle 检索。
- `promote` 只允许到 Knowledge Candidate，不允许直接到 Canonical Fact、Memory、Task、Event 或外部动作。
- 与 Canonical Fact 冲突时，只生成 conflict lead，不自动触发正式 Fact Review。
- Dashboard 只能只读展示 RumorClaim 队列摘要和统计。
- 当前 `rumor add` 是结构化入口，不接收 raw material；raw material capture、自动抽取和 adapter `rumor_policy` 必须另行实现。

## Agent 写入规则

- Agent 可以自主判断非高敏、个人相关且值得记录的信息，并调用 `input add --auto-captured`。
- Agent 自动捕获后必须在回复中说明：input id、kind、摘要、sensitivity、Bundle 可用性。
- Agent 自动捕获只进入 Manual Input Inbox，状态为 `auto_captured`。
- Agent 不得自动 promote。
- Agent 推断出的事实、待办、记忆和决策不得直接写入目标层；可用 `candidate add` 创建 `confirm_required` 候选。只有用户明确确认并提供目标字段时，才可走 `input promote --to candidate` 或后续 confirm / promote 路径。
- 用户明确提交的高敏信息可写入 Inbox，但必须标记 `Sensitive`；Agent 不得自动捕获明显高敏信息。`Sensitive` 默认不进入 Bundle、长期记忆、事实层或模型上下文。
- 后续自动 source adapter 如需产出 RumorClaim，必须声明 `rumor_policy`；Agent 不得绕过 pipeline 直接把未验证材料写成 Candidate 或 Fact。

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
    "sensitivity_cap": "Private",
    "include_unverified": false
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
      "citation": {
        "format": "manual-input-v1",
        "source": "manual-input",
        "input_id": "mi_...",
        "kind": "mood",
        "status": "active",
        "content_hash": "sha256:...",
        "citation_status": "current",
        "label": "Manual Input mi_... · mood · active · hash:... · citation_status: current"
      },
      "sensitivity": "Private",
      "content": "...用户记录...",
      "retrieval": {
        "match_status": "strong",
        "match_reason": "fts",
        "evidence_eligible": true,
        "score": 10.2,
        "vector_score": 0.7,
        "fts_score": 9.3,
        "recency_score": 0.2,
        "kind_score": 0,
        "thresholds": { "vector_evidence": 0.75, "vector_lead": 0.45 }
      }
    }
  ],
  "excluded_sources": [
    { "source": "manual-input", "input_id": "mi_...", "reason": "sensitivity_cap_exceeded" }
  ],
  "freshness_report": [
    { "slice_id": "...", "citation_status": "stale", "note": "来源已修改，建议复核" }
  ],
  "assembly_report": {
    "selection_policy": "layered-diversified-v1",
    "candidate_counts": { "obsidian": 12, "manual-input": 1 },
    "admitted_counts": { "source-reference": 13 },
    "selected_counts": { "obsidian": 10, "manual-input": 1 }
  }
}
```

约束：

- 每个 slice 必带 `evidence_role` + `provenance` + `citation_status` + `citation`。
- Obsidian raw slice 带 `note_path`、`revision_id`、`heading`、`line_range`，并使用 `citation.format=obsidian-note-line-range-v1`。
- Manual Input raw slice 带 `input_id`、`kind`、`status`、`content_hash`，并使用 `citation.format=manual-input-v1`。
- `active` Manual Input 只有 `retrieval.match_status=strong` 且 `evidence_eligible=true` 时可作为 `raw`。
- 低置信向量近邻只能作为 `lead`，必须带 `retrieval.match_status=weak` 和提示，不得支撑事实回答。
- `auto_captured` Manual Input 最多作为 `lead`，回答必须标注未复核。
- RumorClaim 默认不进入普通 Bundle；`--source all --include-unverified` 或 `--source rumor` 时只能作为 `lead`，并必须标注未验证。
- `promoted` input 通过目标对象进入对应层，原 input 只作为 provenance。
- `revoked` 和 deleted tombstone 不进入新 Bundle。
- `Sensitive` 默认被 `--sensitivity-cap Private` 排除。
- `include_unverified` 默认 false；只有显式包含未验证线索时才为 true。
- `excluded_sources` / `freshness_report` 即使为空也要在。
- `assembly_report` 只用于调试和验收，不是事实证据；Agent 不能用它支撑事实性回答。

## Skill 契约

skill 随仓库版本化（如 `skills/lifemesh/SKILL.md`），内容契约：

1. **何时用**：当任务需要用户的所有信息或需要写入用户个人上下文时调用。
2. **怎么读**：`bundle` 拿上下文；默认 source 为 `obsidian`，跨 Obsidian + Manual Input 时显式使用 `--source all`。
3. **怎么写**：Manual Input 走 `input add`；Agent 自动捕获必须 `--auto-captured` 并透明说明。
4. **怎么检索**：`input search` 可直接查 Inbox，`bundle` 可跨 Obsidian + Manual Input 组装上下文。
5. **怎么 promote**：只有用户明确确认时才 `input promote` 到 task/event/memory/fact/candidate。
6. **怎么消费**：事实回答只用 `fact` + `raw` 并展示 `citation.label`；`lead` 标未复核；`context` 只调语气；stale/missing/revoked 必须提示。
7. **边界**：Agent 不能自动 promote，不能把 `auto_captured` 当事实，不能引用失效来源。

## 非目标

- 不在第一版做后台截屏、系统日历同步或活动追踪器接入。
- 不默认使用远程 embedding API。
- 不把截图 VLM extraction 直接当 Canonical Fact。
- 不暴露 `automation`（外发、不可逆动作），仍 deferred 在阶段 6。
- 不引入长期运行 server；LM Studio 是用户本机已启动的本地 provider。
