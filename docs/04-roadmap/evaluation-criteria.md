# Evaluation Criteria

状态：draft
最后更新：2026-07-03
职责边界：定义 LifeMesh 每个阶段如何判断“做得对”，避免只按功能数量推进。

## 基础评估维度

| 维度 | 问题 |
|---|---|
| 可找到 | 用户能否通过自然语言找到相关资料？ |
| 可解释 | 答案是否能展示来源和生成依据？ |
| 可授权 | 数据访问是否受明确权限控制？ |
| 可审计 | 用户是否能看到 Agent 访问和执行记录？ |
| 可撤销 | 授权、记忆、派生事实和动作是否能撤销或修正？ |
| 可过期 | 临时上下文是否能自动失效？ |
| 可控风险 | 高敏感数据和高风险动作是否默认被隔离？ |
| 可同步 | 文档、ADR 和 Web 看板是否展示同一项目状态？ |

## 阶段验收

第 0 阶段通过条件：

- 数据宪法、分类、授权、风险登记表存在。
- 高敏感数据和高风险动作有默认禁用或确认策略。
- Web 看板存在，且项目阶段、风险、路线图、架构、ADR 与文档一致。
- Web 看板包含完整系统架构图，并与 `docs/03-architecture/system-map.md` 一致。

第 1 阶段通过条件：

概览与执行顺序见 [Phase 1 Delivery Plan](phase-1-delivery-plan.md)。

- Obsidian Vault 问答返回具体 Vault Note 来源。
- Obsidian 相关实现没有污染通用 Source Adapter、Source Revision、权限和审计模型。
- 能为一个任务生成 Context Bundle，而不是只返回检索片段。
- Context Bundle 按来源优先级组装：Canonical Fact > Memory > 当前任务相关 Source Reference > 当前任务生成的 Knowledge Candidate。
- Source Adapter / Retriever 只返回 candidates；source-neutral BundleAssembler 统一执行准入、来源层级、去重、多样性选择、失效来源报告和诊断。`--source all` 不能只是拼接两个已完成 Bundle。
- stale / missing / revoked 来源不进入可用上下文，只进入 `excluded_sources` / `freshness_report`；依赖失效来源的 Canonical Fact 被标记为需要复核。
- Canonical Fact 只有 `validity=valid`、`revocation_status=active`、且有 current supporting source reference 时，才能作为 `fact` slice 使用。
- Canonical Fact 复核支持 revalidate、revise、invalidate、revoke；Source Tombstone / Fact Tombstone 能阻止旧 revision 或旧 fact 被新 Bundle 使用。
- Context Bundle 内的每个 Context Slice 都有来源、权限、新鲜度、Citation Status 和可展示的 `citation`。
- 每个 Context Slice 带 `evidence_role`（fact / raw / context / lead）。
- JSON Bundle 可包含 `assembly_report`，用于验收和调试候选/准入/选择策略；该字段不能作为事实证据。
- 事实性回答是 Source-Backed Answer，只基于 `fact` + `raw`；`context` 和 `lead` 不进入事实陈述位；`lead` 不单独支撑结论且带"未核实"标注。
- stale / missing / revoked 来源不进入证据，只进入报告区。
- Context Bundle 作为可序列化 JSON 产物交付（薄 CLI + skill），第 1 阶段不引入运行时 server，不绑定 MCP。
- 配套 skill 存在，能指导 agent 调用 CLI 并按 `evidence_role` 消费 Bundle。
- CLI 契约存在（`cli-contract.md`）：`bundle` 读 + Phase 1 后续 Manual Input `input add/search/list/show/update/revoke/delete/promote` + 传统 `fact add`/`task add`/`remember`/`candidate add` 写。
- agent 自动捕获只能用于非高敏信息并进入 `auto_captured` Manual Input，必须透明说明；agent 推断不得直接 `fact add` 或自动 promote，只能走 candidate / auto_captured → 用户确认。
- RumorClaim 本地 CLI MVP 存在时，必须明确它只保存结构化 claim/mentions/source envelope；未验证线索默认不进入普通 Bundle，显式包含时只能作为 `lead`。
- candidate 确认按 type 升级：`fact`→Canonical Fact、`task`→Task、`preference`/`relationship`/`decision`→Memory。
- 低风险事实可策略自动接受；普通回答不被候选确认阻塞。
- 能产出 Knowledge Candidate，但不会在未确认前写入 Canonical Store 或 Memory。
- Knowledge Candidate 第一版至少支持 fact、preference、relationship、task、decision 五类。
- 每个 Knowledge Candidate 都包含 confidence、risk、lifecycle、source_refs 和 why_suggested。
- 普通回答不被 User Confirmation 阻塞。
- Knowledge Candidate 具备生命周期：transient、inbox、confirm_required、discard。
- User Confirmation 只在持久化到 Canonical Store、Memory、自动化规则或高风险写入前触发。
- Canonical Fact 第一版只允许通过用户确认、用户手动创建、低风险策略接受三条路径生成。
- Canonical Fact 必须包含 statement、source_refs、accepted_by、accepted_at、acceptance_path、confidence、risk、validity、revocation_status。
- Canonical Fact 复核状态必须能记录 review_reason、review_started_at、reviewed_at 和 superseded_by（按需）。
- Memory 只影响排序、语气和偏好，不作为事实证据；需要当事实用必须走 Fact Acceptance 升级为 Canonical Fact。
- 显式记忆和情境记忆可直接写入 Memory，情境记忆带范围和过期时间；普通偏好推断带置信度直接写入；重要偏好、关系、决策类推断写入 Memory 前需要 User Confirmation。
- 路径排除、删除或撤销授权后，索引和派生事实可清理。
- 能区分事实、摘要和推断。
- 默认不写回 Obsidian Vault，也不把推断自动写入长期记忆。
- 第一版索引遵守默认排除规则，不读取 `.git/`、`.obsidian/`、附件二进制、`Trash/`、`_archives/`、`tmp/`。
- 修改 Vault Note 后，对应索引片段和派生事实能通过 Vault Note Revision 失效或重建。
- 旧回答遇到 stale 或 missing 来源时不自动重写，而是展示来源状态并提供重新生成动作。
- 通过 [Obsidian 检索最小验收样例](../02-domain/data-sources/obsidian-retrieval-sample.md)：`bundle` 产出带 `note_path`+`revision_id`+`heading`+`line_range`+`citation_status`+`citation` 的 slice，agent 事实回答引用来源与状态，stale 链路生效。

Phase 1 后续 Manual Input milestone 通过条件：

- Manual Input 不使用 SourceRevision；input record、content_hash、状态和 audit event 足以支撑 Bundle provenance、撤销和复核。
- `input add/search/list/show/update/revoke/delete/promote` 最小 CLI 路径可运行。
- 本地 SQLite、FTS、embedding、Raw Vault managed assets 和模型/向量失败降级路径有最小测试。
- `bundle --source all` 能按权限统一组装 Obsidian 和 Manual Input candidates。
- `active` input 只有 strong 命中可作为 raw；weak 语义近邻和 `auto_captured` input 最多作为 lead；`Sensitive` 默认不进入普通 Bundle。
- promote 只创建 inbox-derived 最小 Task/Event/Memory/Canonical Fact/Candidate 对象；系统日历、提醒事项和外部任务应用同步不属于该 milestone。
- revoke/delete 后相关 input、extraction、embedding 和派生对象不再进入新 Bundle，依赖事实进入复核或停止使用。

Phase 1 后续 RumorClaim milestone 通过条件：

- RumorClaim 不作为 Manual Input kind，也不作为独立架构层。
- RumorClaim 默认不保存完整原始物料；只保存通过初筛的 claim、entity mentions、relation mentions 和最小 source envelope。
- `rumor add/list/show/dismiss/expire/promote`、持久化门槛、review queue、过期策略、Bundle lead 准入和 candidate promote 路径都有测试或人工验收。
- 每个自动 source adapter 在产出 RumorClaim 前声明 `rumor_policy`；自动 adapter 不属于当前结构化 CLI MVP。
- 第一版不做去重/合并，不因重复出现提升可信度。
- 与 Canonical Fact 冲突的 RumorClaim 只生成 conflict lead，不自动打开正式 Fact Review。

第 4 阶段通过条件：

- 用户能查看、修改、删除长期记忆。
- 推断记忆带置信度和来源。
- 情境记忆有范围和过期时间。

第 6 阶段通过条件：

- Agent 动作有权限检查、确认机制和审计记录。
- 外发或不可逆动作不能静默执行。

## 过程质量

每次交付前都应确认：

- 变更是否影响 Web 看板。
- 变更是否影响 README 或文档地图。
- 变更是否需要 ADR。
- 看板中最近变更、开放问题、风险、阶段状态是否仍然准确。
