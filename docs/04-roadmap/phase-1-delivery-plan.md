# Phase 1 Delivery Plan

状态：active
最后更新：2026-07-15
职责边界：定义第 1 阶段 Personal Context Layer 的落地范围、验收方式，以及验收通过后的下一步。不替代 `phases.md`、`evaluation-criteria.md` 或 ADR。

## 定位

第 1 阶段要从 docs-first 进入最小可运行原型，但目标不是完成整个 Personal Data OS，也不是做 Obsidian 增强器。

第一轮只读原型先验证一条最小闭环：

```text
Obsidian Vault
  -> Source Revision
  -> ContextCandidate
  -> BundleAssembler
  -> Context Slice
  -> JSON Context Bundle
  -> Agent 按 evidence_role 生成 Source-Backed Answer
  -> Source 变化后 citation_status / freshness_report 生效
```

第一轮通过后，第 1 阶段的后续 milestone 是 Manual Input Inbox（ADR-0008）：把用户和 Agent 主动提交的截图、日程、心情、活动、待办和备注写入本地 Inbox，并验证本地 embedding / VLM extraction / SQLite 向量检索 / Bundle 准入 / promote 到 inbox-derived 最小对象的闭环。

Manual Input 之后的 Phase 1 follow-on milestone 是 RumorClaim / UnverifiedClaim（ADR-0009）：为后续自动信息源提供可信度未知材料的处理契约。它只保存通过初筛的 claim、entity mention、relation mention 和最小 source envelope；原始物料默认不长期保存。当前已落地本地结构化 CLI MVP；自动 source adapter、截图/图片自动抽取、review UI 和自动 fact-check 仍不在本轮。

ADR-0010 对应的 Unified Write Model 已于 2026-07-15 完成交付：Candidate handoff、Acceptance、Canonical Fact/Memory/Task/Event、provenance、Fact Review、数据库 backup/migration/restore 已一次切换；真实本地数据库完成动态 preflight、online backup、集合守恒、postflight 和幂等复核。

## 当前实现状态

截至 2026-07-15，第 1 阶段本地 CLI 原型已开始落地：

- `bin/lifemesh bundle` 可生成 JSON Context Bundle。
- `lifemesh/` 包含 Obsidian 只读扫描、Source Revision、section 提取、简单检索排序、sensitivity cap 过滤、stale / missing state 检测。
- `lifemesh/` 包含 Manual Input 配置层、SQLite 主库、FTS、sqlite-vec 加载、LM Studio embedding/VLM 调用、审计、revoke/delete/promote 和 Bundle slice 生成。
- `lifemesh/` 包含 source-neutral BundleAssembler：Obsidian 与 Manual Input 先返回 candidates，再统一执行准入、来源层级、去重、多样性选择和 `assembly_report` 诊断。
- `tests/fixtures/obsidian-vault/`、`tests/test_bundle_cli.py` 和 `tests/test_manual_input_cli.py` 覆盖 fixture vault、显式/config vault、路径排除、sensitivity cap、stale/missing、Manual Input add/search/list/show/update/revoke/delete/promote、`bundle --source all`、跨源候选不被单一来源淹没、超大 `--max-slices` 不导致候选消失，以及模型/向量失败降级。
- `skills/lifemesh/SKILL.md` 已提供 agent 使用说明。
- 2026-06-30 已完成一次真实本机 Manual Input 验收：LM Studio 本地 `text-embedding-qwen3-embedding-0.6b` embedding、`qwen/qwen3-vl-8b` 截图 VLM extraction、sqlite-vec `vector_status=ready`、note add/search/show/update/revoke/delete、candidate promote、screenshot managed asset 清理、auto_captured lead-only Bundle 准入，以及 `bundle --source all` 均通过。验收发现的弱近邻误读风险已通过 `strong` / `weak` 命中策略处理。
- 2026-07-03 本机运行时截图 OCR / VLM 模型配置已切换为 `ornith-1.0-9b`；历史验收记录仍保留 2026-06-30 使用的 `qwen/qwen3-vl-8b`。
- 2026-06-30 已定义并实现第一版 Source-Backed Answer 引用字段和 Manual Input 检索命中策略：Bundle slice 带 `citation`；Obsidian 使用 `obsidian-note-line-range-v1`，Manual Input 使用 `manual-input-v1`；Manual Input `strong` 命中可作为 `raw`，`weak` 向量近邻只作为 `lead`。
- 2026-07-03 已实现 RumorClaim 本地结构化 CLI MVP：`rumor add/list/show/keep/dismiss/expire/promote`、持久化门槛、review queue、最小 source envelope、审计事件、`bundle --source rumor` 和 `bundle --source all --include-unverified` 的 lead-only 准入。
- 2026-07-09 已完成 Q20 真实 vault 手工验收记录：`bundle --source obsidian` 返回 20 个 `raw/current` slices，命中专题归档页和 `hot.md`，保留 `excluded_sources` / `freshness_report` 字段；基于真实 `hot.md` 临时副本验证 stale 和 missing 均只进入 `freshness_report`，新 Bundle slice 使用 current revision。`--source all` 对 Q20 未选入 Manual Input，因此这次只验证不会误用 weak lead；独立 Manual Input weak lead 真实任务样例仍可后续补充。
- 2026-07-09 已实现 Candidate inbox 最小 CLI：`candidate add/list/show/discard` 写入本地 `lifemesh.db`，按 risk / confidence 排序待确认队列；`discard` 只写 tombstone，不删除历史。
- 2026-07-15 已实现 ADR-0010 Unified Write Model：Candidate edit/merge/defer/resume/confirm、统一 Manual Input/RumorClaim handoff、Acceptance、typed Canonical Object、Fact Review、source cascade、tombstone、canonical Bundle retrieval 和数据库维护 CLI 均已落地。
- 2026-07-15 已完成真实 `~/.lifemesh/lifemesh.db` 迁移：7 Candidates、134 Source References、38 Source Tombstones 守恒，integrity/foreign-key 检查通过，二次执行为 no-op，受管备份 hash 与 manifest 一致。
- 2026-07-15 已实现 ADR-0011 的 LifeMesh Console 只读首版：React + shadcn/ui 前端读取真实本地 Manual Input、RumorClaim、Candidate、Canonical Object、Open Review 和 Obsidian/Bundle 状态，通过按需 `127.0.0.1` Console Server 提供总览、搜索、详情、图谱、时间线与非持久化 Bundle Explorer；HTTP 和浏览器验收已覆盖既定安全边界。
- 2026-07-15 已完成 Console 首轮真实规模稳定性与只读边界验收：141 条可见记录下的混合并发读全部成功且 FD 零增长；全局搜索移除同步 embedding 后，单用户 p95 为 52.9ms；真实数据库快照上的增量 Input → Fact → source stale → Open Review 级联与 integrity check 通过，原库未写入测试记录；Console Store 改用 SQLite `mode=ro`/`query_only`，空 HOME 不创建数据库或锁文件。

仍未完成：

- frontmatter 结构化事实边界。
- 自动 RumorClaim source adapter、截图/图片自动抽取、review UI、来源融合和自动 fact-check。

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
   - 输出 `schema_version`、`task`、`permission_scope`、`assembled_at`、`slices[]`、`excluded_sources[]`、`freshness_report[]` 和诊断用 `assembly_report`。
   - 第一个原型主要产出 `evidence_role=raw` slice。
   - 每个 raw slice 必须带 `note_path`、`revision_id`、`heading`、`line_range`、`citation_status`、`citation`、`content`。

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

### 第一轮只读原型中契约先行、现已补齐

以下能力在第一轮只读原型中只定义契约，现已由 Unified Write Model 实现：

- `fact add` / `task add` / `remember`
- `candidate add` / `candidate list` / `candidate confirm`
- `fact review` / `fact revoke`
- Canonical Fact / Memory 的 typed persistence、Acceptance 与 review
- dashboard 写回或交互式确认

第一轮原型可以通过 JSON fixture 或内存数据模拟 `fact` / `context` / `lead` 的 Bundle 形状，但实际读链路只要求 `raw` slice 跑通。

## 验收方式

### 自动化检查

必须通过：

- CLI 单元测试：Source Revision、heading / line range 提取、路径排除、Bundle schema。
- stale 测试：同一文件修改后旧 revision 不进入新检索，`freshness_report` 说明旧来源已变更。
- missing 测试：文件删除或移入排除路径后，不再命中新问题。
- JSON schema 检查：`excluded_sources[]` 和 `freshness_report[]` 即使为空也存在。
- BundleAssembler 检查：`--source all` 使用统一候选组装，而不是拼接两个已完成 Bundle；跨源候选必须能进入结果，`assembly_report` 必须解释候选和选择数量。
- 文档检查：README、docs map、roadmap、dashboard 与实现状态一致。

### 手工验收

使用真实 vault：

```bash
lifemesh bundle "AI 对开源生态有什么结构性冲击？" --source obsidian --vault <real-vault-path> --out /tmp/bundle.json
```

通过条件：

- Bundle 至少返回 `hot.md` 的相关 raw slice。
- slice 包含真实 `note_path`、`revision_id`、`heading`、`line_range`、`citation_status=current` 和 `citation.label`。
- Agent 能基于 Bundle 生成 Source-Backed Answer，并引用 `citation.label`。
- 修改来源后，旧 revision 进入 stale 链路，新问题不命中旧 revision。

失败条件：

- 只返回裸文本，没有来源元数据。
- 回答只说“根据你的笔记”，没有 `citation.label`、`line_range` 或 `citation_status`。
- stale 或 missing 来源继续作为事实证据进入新回答。
- Obsidian 特定概念污染 source-neutral 的 Source Revision / Context Bundle 模型。

## 第一轮只读原型完成定义

第一轮只读原型可判定完成，当且仅当：

- `lifemesh bundle` 最小读链路可运行。
- fixture vault 自动化测试通过。
- Q20 真实 vault 样例手工通过。
- `skills/lifemesh/SKILL.md` 存在，并能指导 Agent 正确调用和消费 Bundle。
- 文档、ADR、README、dashboard 与实现状态同步。
- 已知未实现写侧能力在文档中明确标注为 contract-only 或后续阶段，不被看板展示为已完成能力。

## Phase 1 后续 Manual Input milestone 完成定义

ADR-0008 对应第 1 阶段后续 milestone，不覆盖上面的只读原型完成定义。该 milestone 完成，当且仅当：

- `input add/search/list/show/update/revoke/delete/promote` 最小 CLI 路径可运行。
- Manual Input 使用 input record、content_hash、状态和 audit event 表达来源身份，不创建 SourceRevision。
- SQLite 主存储、FTS、本地 embedding、Raw Vault managed assets 和模型/向量失败降级路径有最小测试。
- 截图 extraction 可通过本地 provider 跑通；`--no-extract` 只跳过 VLM，embedding 失败时降级为 FTS-only 或 metadata-only；模型输出不自动变成事实。
- `bundle --source all` 能按权限把 Obsidian 与 Manual Input candidates 交给 BundleAssembler 统一组装；`active` 只有 strong 命中可作为 raw，weak 近邻和 `auto_captured` 最多作为 lead。
- revoke/delete 后 input、extraction、embedding 和派生对象准入状态正确更新。
- promote 只创建 inbox-derived 最小 Task/Event/Memory/Canonical Fact/Candidate 对象，并保留 normalized Manual Input Source Reference 和 derived-from link。
- 看板、CLI 契约、Agent skill、治理、安全、领域和路线图文档同步。

## Phase 1 后续 RumorClaim milestone 完成定义

ADR-0009 对应第 1 阶段后续 milestone，不覆盖只读原型或 Manual Input milestone 的完成定义。当前本地结构化 CLI MVP 完成，当且仅当：

- RumorClaim 领域文档、ADR、CLI contract 和 dashboard 状态一致。
- `rumor add/list/show/keep/dismiss/expire/promote` 最小 CLI 路径可运行。
- 默认不保存完整原始物料；只保存 claim、mentions、最小 source envelope 和审计摘要。
- 持久化门槛按 `user_relevance >= medium OR impact >= high` 执行。
- RumorClaim 默认不进入普通 Bundle；明确请求未验证线索时只能作为 `lead`。
- RumorClaim 只能 promote 到 Knowledge Candidate；该 handoff 现已写入统一 Candidate inbox，不再新增 `rumor_candidate_links`。
- Dashboard 只读展示 review queue 摘要和统计，不写回。

后续自动来源版本开始前必须满足：

- 每个可产出 RumorClaim 的 source adapter 先声明 `rumor_policy`。
- 文本、截图和图片输入统一输出 RumorClaim 结构，而不是直接进入 Manual Input kind 或 Knowledge Candidate。
- 自动抽取和 review queue 有可追溯审计，不默认保存 raw material。

## 验收通过后的下一步

优先顺序：

1. **收紧来源引用展示**
   - 首版已完成：Bundle slice 输出 `citation`，覆盖 Obsidian `note_path`、heading、line range、citation_status，以及 Manual Input `input_id`、kind、status、content_hash 摘要、citation_status。
   - 2026-07-09 已用 Q20 真实 vault 样例验证 Obsidian `citation.label`、stale 和 missing 状态报告；后续如需 UI 级体验，仍需在回答渲染层补“基于当前来源重新生成”的交互。

2. **Unified Write Model 一次性交付（已完成）**
   - 已补齐 Candidate 完整确认生命周期，统一 CLI、Manual Input、RumorClaim handoff，停止 legacy 分裂写入。
   - 已落地 Acceptance、typed Canonical Object、normalized provenance、Fact Review、tombstone 和 Bundle 准入。
   - 已使用动态 preflight manifest 完成真实数据库 online backup、migration、postflight、幂等和 restore 演练。
   - Project Board 和 LifeMesh Console 继续只读，不做写回。

3. **LifeMesh Console 只读首版（已完成）**
   - 与静态 Project Board 分离，作为用户浏览个人数据与 Context Bundle 的产品界面。
   - 按需启动并只绑定 `127.0.0.1`；不提供 LAN/public 访问、后台 daemon 或 Agent API。
   - 浏览 Manual Input、RumorClaim、Candidate、Canonical Object、Open Review、provenance、audit 和 freshness；支持非持久化 Bundle Explorer。
   - 默认首屏是总览工作台，提供全局搜索、数据健康、近期记录和队列摘要；Knowledge Graph 与 Timeline 作为独立视图。
   - 图谱只展示当前运行时已有关系，不根据相似度或视觉需要补造语义边。
   - Unified Write Model 已完成；Console 仍不提供写操作，后续如需写回必须单独做权限、确认和审计设计。
   - 141 条可见记录的首轮性能、FD 和快照级联验收已完成；后续持续观察长期数据增长、图谱密度与信息分层。增加持久化写入、常驻服务或外部监听前必须重新做产品和安全决策。

4. **RumorClaim 自动来源评估**
   - 已有结构化 CLI MVP 可验证 ADR-0009 的 source envelope、review queue、Bundle lead 和 candidate promote 边界。
   - 自动来源实现前，必须决定第一个允许产出 RumorClaim 的 source adapter 和对应 `rumor_policy`。
   - 不在该步骤引入外部通知、系统任务、日历同步或自动联网 fact-check。

5. **Manual Input 真实本机验收**
   - 首次真实本机验收已于 2026-06-30 通过：使用真实 LM Studio embedding/VLM 模型和真实 sqlite-vec 扩展路径跑通 `input add/search/show/update/revoke/delete/promote`。
   - 首次验收记录的 embedding 模型 identifier 为 `text-embedding-qwen3-embedding-0.6b`，维度为 1024；截图 VLM 为 `qwen/qwen3-vl-8b`，测试图片 extraction 成功并写入 `manual_input_extractions`。
   - 当前本机截图 OCR / VLM 配置为 `ornith-1.0-9b`。
   - 已使用 `lifemesh bundle --source all` 显式组装 Obsidian 与 Manual Input candidates，并验证 strong `active` 记录作为 `raw/current` slice、weak 近邻和 `auto_captured` 记录作为 `lead/current` slice。
   - 首版检索阈值已落地：`vector_evidence=0.75`、`vector_lead=0.45`；`strong` 可作为 `raw`，`weak` 只能作为 `lead`。
   - 后续仍需补充长期性能边界和更完整的真实任务场景验收。

6. **进入第 2 阶段准备**
   - 当读链路、候选确认、Manual Input 和事实复核稳定后，再进入系统日历/任务同步与高级调度。
   - 第 2 阶段前必须复盘第 1 阶段的来源、权限、审计和撤销模型是否足够 source-neutral。

## 不在第 1 阶段做

- 不做 MCP server。
- 不做多用户数据库、后台服务或远程托管数据层；Manual Input 的 SQLite 仅作为本机 CLI 原型存储。
- 不做自动化外发或不可逆动作。
- 不正式接入金融、健康、位置等高敏数据源；用户明确提交的 `Sensitive` Manual Input 仅作为本地隔离 Inbox 记录处理，默认不进入 Bundle。
- 不把 Obsidian 变成产品中心。
- 不要求一次性实现 ADR-0010 范围外的所有未来写侧命令；但 ADR-0010 明确列出的 Unified Write Model、迁移和恢复合同必须作为一次完整切换交付，不能留下长期双写中间态。
- 不做后台截屏、系统日历同步或活动自动追踪；这些需要独立 Source Adapter 评估。
- 不默认使用远程 embedding、远程 OCR 或远程视觉模型。
