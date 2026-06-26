# Evaluation Criteria

状态：draft
最后更新：2026-06-26
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

- Obsidian Vault 问答返回具体 Vault Note 来源。
- Obsidian 相关实现没有污染通用 Source Adapter、Source Revision、权限和审计模型。
- 能为一个任务生成 Context Bundle，而不是只返回检索片段。
- Context Bundle 按来源优先级组装：Canonical Fact > Memory > 当前任务相关 Source Revision > 当前任务生成的 Knowledge Candidate。
- stale / missing / revoked 来源不进入可用上下文，只进入 `excluded_sources` / `freshness_report`；依赖失效来源的 Canonical Fact 被标记为需要复核。
- Context Bundle 内的每个 Context Slice 都有来源、权限、新鲜度和 Citation Status。
- 每个 Context Slice 带 `evidence_role`（fact / raw / context / lead）。
- 事实性回答是 Source-Backed Answer，只基于 `fact` + `raw`；`context` 和 `lead` 不进入事实陈述位；`lead` 不单独支撑结论且带"未核实"标注。
- stale / missing / revoked 来源不进入证据，只进入报告区。
- 能产出 Knowledge Candidate，但不会在未确认前写入 Canonical Store 或 Memory。
- Knowledge Candidate 第一版至少支持 fact、preference、relationship、task、decision 五类。
- 每个 Knowledge Candidate 都包含 confidence、risk、lifecycle、source_revisions 和 why_suggested。
- 普通回答不被 User Confirmation 阻塞。
- Knowledge Candidate 具备生命周期：transient、inbox、confirm_required、discard。
- User Confirmation 只在持久化到 Canonical Store、Memory、自动化规则或高风险写入前触发。
- Canonical Fact 第一版只允许通过用户确认、用户手动创建、低风险策略接受三条路径生成。
- Canonical Fact 必须包含 statement、source_revisions、accepted_by、accepted_at、acceptance_path、confidence、risk、validity、revocation_status。
- Memory 只影响排序、语气和偏好，不作为事实证据；需要当事实用必须走 Fact Acceptance 升级为 Canonical Fact。
- 显式记忆和情境记忆可直接写入 Memory，情境记忆带范围和过期时间；普通偏好推断带置信度直接写入；重要偏好、关系、决策类推断写入 Memory 前需要 User Confirmation。
- 路径排除、删除或撤销授权后，索引和派生事实可清理。
- 能区分事实、摘要和推断。
- 默认不写回 Obsidian Vault，也不把推断自动写入长期记忆。
- 第一版索引遵守默认排除规则，不读取 `.git/`、`.obsidian/`、附件二进制、`Trash/`、`_archives/`、`tmp/`。
- 修改 Vault Note 后，对应索引片段和派生事实能通过 Vault Note Revision 失效或重建。
- 旧回答遇到 stale 或 missing 来源时不自动重写，而是展示来源状态并提供重新生成动作。

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
