# Provenance And Lifecycle

状态：draft
最后更新：2026-07-03
职责边界：定义数据从原始进入、派生、使用、过期到删除的生命周期。

## 生命周期

1. 发现数据源
2. 完成接入评估
3. 捕获来源版本
4. 导入 Raw Vault 或建立只读索引引用
5. 抽取规范化事实
6. 建立索引、图谱或时间线
7. 授权给 Agent 或工具使用
8. 记录使用和变更审计
9. 用户纠错、撤销或删除
10. 到期归档或清除

## 可编辑来源

Obsidian Vault 这类来源不是不可变归档。LifeMesh 应先用 `VaultNoteRevision` 验证可编辑外部来源语义，但核心抽象应是 source-neutral 的 `SourceReference`。`SourceRevision` 是一种 Source Reference；Manual Input 不使用 SourceRevision。

不同 Source Adapter 都应能表达：

- 当前条目身份
- 当前条目版本
- 是否仍在授权范围内
- 是否仍在索引范围内
- 当前版本是否匹配旧引用

`VaultNoteRevision` 至少应记录：

- vault 标识
- note path
- mtime
- size
- content hash
- indexed_at
- index scope

引用、索引片段、摘要和抽取事实都应指向具体 source reference。当前文件发生编辑、移动、删除或被排除后，旧 revision 进入 stale 状态，不再用于新的检索命中。Manual Input 则通过状态、content_hash 和 audit event 判断 current / revoked / deleted。

第一版变更检测策略：

- 查询前或手动刷新时扫描允许范围内的 Markdown 文件。
- 先比较 `mtime + size`，只对疑似变化文件计算 content hash。
- 修改过的笔记重建索引片段。
- 被删除、移动到排除目录或撤销授权的笔记生成 Source Tombstone，使旧索引不可再命中，并触发依赖派生事实复核。

## Tombstone 与事实复核

Tombstone 是不可用来源或事实的保留标记，不是简单删除。

| tombstone | 触发条件 | 影响 |
|---|---|---|
| Source Tombstone | source 被删除、移出索引范围、授权撤销 | 旧 revision 不再被新检索命中；依赖它的 fact / candidate 进入复核 |
| Manual Input Tombstone | input 被 revoke 或 delete | 输入不再检索或进入 Bundle；依赖对象进入复核或停止使用 |
| RumorClaim Tombstone | rumor claim 被 dismiss 或 expire | 未验证线索不再检索或进入 Bundle；已创建 candidate 的 claim 跟随 candidate 生命周期 |
| Fact Tombstone | Canonical Fact 被撤销、失效或替代 | 旧 fact 不再进入新 Bundle；历史回答和审计仍可解释 |

依赖 source reference 的 Canonical Fact 使用三段式处理。Obsidian 等可编辑外部来源使用 Source Revision；Manual Input 使用 input record、content_hash、状态和 audit event：

1. 来源 stale / missing / revoked 后，先进入 `validity=needs_review`，不立即删除。
2. `needs_review` 的 fact 不能作为 `evidence_role=fact` 进入可用 Bundle，只进入 `freshness_report`。
3. 复核后执行 `revalidate`、`revise`、`invalidate` 或 `revoke`，每次状态变化都生成审计事件。

## Manual Input 生命周期

Manual Input 是可编辑、可检索、可撤销的用户级来源。它不使用 SourceRevision 表达每次编辑，而是通过 input record + audit event + content_hash 表达当前状态和变更历史。

第一版状态：

| 状态 | 触发 | 默认行为 |
|---|---|---|
| active | 用户手动提交或确认 | 可检索；strong 命中按权限作为 raw slice，weak 近邻最多作为 lead |
| auto_captured | Agent 自主记录 | 可检索；进入 Bundle 时最多作为 lead |
| promoted | 用户确认并派生为正式对象 | 目标对象进入对应层，input 保留 provenance |
| revoked | 用户撤销 | 不检索，不进 Bundle，仅保留 tombstone/audit |

删除与撤销分开：

- `revoke` 保留 tombstone、审计和派生关系，用于解释为什么目标对象需要复核。
- `delete` 删除 managed raw asset、embedding、extraction 和主记录内容，只保留最小 deletion tombstone。

截图类 input 默认复制 managed asset 到 `~/.lifemesh/raw-assets/manual-input/`，并记录 original path、stored path、sha256、mtime、size 和 media type。撤销不会删除 original path；删除只删除 managed copy。

Manual Input 的 VLM/OCR extraction 与 embedding 必须记录 provider、model、content_hash 和状态。模型输出可被检索，但不是已核实事实；进入 Canonical Fact、Memory、Task 或 Event 必须通过 promote。

## RumorClaim 生命周期

RumorClaim 处理可信度未知的文字片段、截图和图片材料。它不使用 SourceRevision，也不默认保留完整原始物料；来源身份由最小 SourceEnvelope、processing_run_id、可选 material_fingerprint 和审计摘要表达。

第一版状态：

| 状态 | 触发 | 默认行为 |
|---|---|---|
| parked | 通过最低初筛 | 可在 rumor review 中查看；普通 Bundle 默认不含 |
| candidate_created | 用户或规则把 claim promote 到 Knowledge Candidate | 当前 MVP 只保留本地 candidate link；完整 Candidate inbox 落地后跟随 Candidate 生命周期 |
| dismissed | 用户或规则判定无价值 | 不检索，不进 Bundle，仅保留最小 tombstone / 统计 |
| expired | 到期未复核 | 不检索，不进 Bundle，默认只保留审计摘要 |

默认过期策略：

- 普通 parked claim：60 天。
- 高影响或用户订阅主题：180 天。
- candidate_created：当前 MVP 只保留本地 candidate link；完整 Candidate inbox 落地后跟随 Knowledge Candidate 生命周期。
- 用户显式 pin/save：不自动过期，但仍是未验证线索。

当 RumorClaim 与 Canonical Fact 冲突时，只生成 conflict lead，不自动让 Canonical Fact 进入 `needs_review`。正式 Fact Review 需要用户明确复核，或后续多个高质量来源支持。

## 旧回答与来源状态

旧回答是历史交互记录，不应在来源变化后自动重写。每条来源引用应展示 `Citation Status`：

| 状态 | 含义 | 默认行为 |
|---|---|---|
| current | 引用的 revision 仍匹配当前 Vault Note | 可以正常展示 |
| stale | Vault Note 已修改，旧回答引用的是历史 revision | 展示来源已变更，并提供重新生成动作 |
| missing | 笔记被删除、移动到排除路径或授权撤销 | 展示来源不可用，并禁止用于新检索 |

新问题不能命中 stale 或 missing revision。用户打开旧回答时，如果存在 stale 或 missing 来源，系统应提示“部分来源已变更，建议基于当前笔记重新生成”。

## 溯源要求

派生事实必须能回答：

- 来自哪个原始数据？
- 来自哪个来源版本？
- 何时抽取？
- 由什么规则、模型或人工操作生成？
- 置信度是多少？
- 最近被哪个 Agent 或工具使用？
- 是否被用户确认或纠正过？
- 当前来源版本是否仍然有效？
- 如果进入复核或撤销，触发原因、操作者和替代事实是什么？
