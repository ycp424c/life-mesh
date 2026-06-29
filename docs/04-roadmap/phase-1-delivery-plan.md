# Phase 1 Delivery Plan

状态：active
最后更新：2026-06-29
职责边界：定义第 1 阶段 Personal Context Layer 的落地范围、验收方式，以及验收通过后的下一步。不替代 `phases.md`、`evaluation-criteria.md` 或 ADR。

## 定位

第 1 阶段要从 docs-first 进入最小可运行原型，但目标不是完成整个 Personal Data OS，也不是做 Obsidian 增强器。

本阶段只验证一条最小闭环：

```text
Obsidian Vault
  -> Source Revision
  -> Context Slice
  -> JSON Context Bundle
  -> Agent 按 evidence_role 生成 Source-Backed Answer
  -> Source 变化后 citation_status / freshness_report 生效
```

## 当前实现状态

截至 2026-06-29，第一轮只读原型已开始落地：

- `bin/lifemesh bundle` 可生成 JSON Context Bundle。
- `lifemesh/` 包含 Obsidian 只读扫描、Source Revision、section 提取、简单检索排序、sensitivity cap 过滤、stale / missing state 检测。
- `tests/fixtures/obsidian-vault/` 和 `tests/test_bundle_cli.py` 覆盖 fixture vault、显式 vault、路径排除、sensitivity cap、stale 和 missing。
- `skills/lifemesh/SKILL.md` 已提供 agent 使用说明。

仍未完成：

- 来源引用展示格式。
- frontmatter 结构化事实边界。
- Candidate inbox 与写侧命令。
- Canonical Fact 持久化与复核命令实现。

## 落地范围

### 必做

1. **最小 CLI**
   - 提供 `lifemesh bundle "<task>" --source obsidian --out <path>`。
   - 默认输出 JSON 到 stdout，传 `--out` 时写文件。
   - 不提供 `lifemesh ask`；回答仍由 Agent 完成。

2. **Obsidian Source Adapter**
   - 只读扫描 Markdown。
   - 遵守默认排除：`.git/`、`.obsidian/`、`_attachments/` 二进制、`Trash/`、`_archives/`、`tmp/`。
   - 为命中内容生成 Source Revision：`note_path`、`mtime`、`size`、`content_hash`、`indexed_at`。

3. **Context Bundle JSON**
   - 输出 `schema_version`、`task`、`permission_scope`、`assembled_at`、`slices[]`、`excluded_sources[]`、`freshness_report[]`。
   - 第一个原型主要产出 `evidence_role=raw` slice。
   - 每个 raw slice 必须带 `note_path`、`revision_id`、`heading`、`line_range`、`citation_status`、`content`。

4. **stale / missing 链路**
   - 文件被修改后，旧 revision 变 stale，不再被新问题命中。
   - 文件被删除、移入排除路径或授权撤销后，生成 missing / tombstone 语义。
   - stale / missing 只能进入 `freshness_report` 或报告区，不能继续作为事实证据。

5. **Agent 使用说明**
   - 编写 `skills/lifemesh/SKILL.md`，说明何时调用 CLI、如何读取 Bundle、如何按 `evidence_role` 使用。
   - skill 范围是“需要用户所有已接入信息的任务”，不限定 Obsidian。

6. **测试与样例**
   - 建立小型 fixture vault，覆盖标题、frontmatter、正文段落、路径排除、文件修改和删除。
   - 用真实 Obsidian vault 的 Q20 样例做手工验收：`hot.md` 回答“AI 对开源生态有什么结构性冲击？”。

### 契约先行，暂不完整实现

以下能力保留在 CLI / ADR / 领域文档契约中，但不要求在第一轮只读原型完整实现：

- `fact add` / `task add` / `remember`
- `candidate add` / `candidate list` / `candidate confirm`
- `fact review` / `fact revoke`
- Canonical Fact / Memory 的完整持久化存储
- dashboard 写回或交互式确认

第一轮原型可以通过 JSON fixture 或内存数据模拟 `fact` / `context` / `lead` 的 Bundle 形状，但实际读链路只要求 `raw` slice 跑通。

## 验收方式

### 自动化检查

必须通过：

- CLI 单元测试：Source Revision、heading / line range 提取、路径排除、Bundle schema。
- stale 测试：同一文件修改后旧 revision 不进入新检索，`freshness_report` 说明旧来源已变更。
- missing 测试：文件删除或移入排除路径后，不再命中新问题。
- JSON schema 检查：`excluded_sources[]` 和 `freshness_report[]` 即使为空也存在。
- 文档检查：README、docs map、roadmap、dashboard 与实现状态一致。

### 手工验收

使用真实 vault：

```bash
lifemesh bundle "AI 对开源生态有什么结构性冲击？" --source obsidian --vault <real-vault-path> --out /tmp/bundle.json
```

通过条件：

- Bundle 至少返回 `hot.md` 的相关 raw slice。
- slice 包含真实 `note_path`、`revision_id`、`heading`、`line_range`、`citation_status=current`。
- Agent 能基于 Bundle 生成 Source-Backed Answer，并引用 `note_path` + `line_range` + `citation_status`。
- 修改来源后，旧 revision 进入 stale 链路，新问题不命中旧 revision。

失败条件：

- 只返回裸文本，没有来源元数据。
- 回答只说“根据你的笔记”，没有 `note_path` / `line_range` / `citation_status`。
- stale 或 missing 来源继续作为事实证据进入新回答。
- Obsidian 特定概念污染 source-neutral 的 Source Revision / Context Bundle 模型。

## 完成定义

第 1 阶段落地可判定完成，当且仅当：

- `lifemesh bundle` 最小读链路可运行。
- fixture vault 自动化测试通过。
- Q20 真实 vault 样例手工通过。
- `skills/lifemesh/SKILL.md` 存在，并能指导 Agent 正确调用和消费 Bundle。
- 文档、ADR、README、dashboard 与实现状态同步。
- 已知未实现写侧能力在文档中明确标注为 contract-only 或后续阶段，不被看板展示为已完成能力。

## 验收通过后的下一步

优先顺序：

1. **收紧来源引用展示**
   - 定义用户看到的引用格式：`note_path`、heading、line range、citation_status、stale 提示和重新生成动作。
   - 这是把可运行 Bundle 变成可信回答体验的第一步。

2. **Candidate inbox 最小实现**
   - 先支持 `candidate add/list/show/discard`，再支持 confirm / merge / edit。
   - dashboard 继续只读展示，不做写回。

3. **受限写入**
   - 实现用户断言路径：`fact add`、`task add`、`remember`。
   - agent 推断仍只能 `candidate add`。

4. **Canonical Fact 持久化与复核**
   - 实现 `fact review list/show/revalidate/revise/invalidate` 和 `fact revoke`。
   - 支持 Source Tombstone / Fact Tombstone 的影响范围展示。

5. **进入第 2 阶段准备**
   - 当读链路、候选确认和事实复核稳定后，再进入时间与任务对象：Event、Task、Commitment、Deadline。
   - 第 2 阶段前必须复盘第 1 阶段的来源、权限、审计和撤销模型是否足够 source-neutral。

## 不在第 1 阶段做

- 不做 MCP server。
- 不做完整数据库和后台服务。
- 不做自动化外发或不可逆动作。
- 不接入金融、健康、位置等高敏数据。
- 不把 Obsidian 变成产品中心。
- 不要求一次性实现所有写侧命令。
