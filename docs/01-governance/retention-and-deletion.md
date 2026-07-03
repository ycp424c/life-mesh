# Retention And Deletion

状态：draft
最后更新：2026-07-03
职责边界：定义原始数据、派生事实、索引、记忆和审计日志的保留、归档、删除和遗忘策略。

## 为什么重要

LifeMesh 是长期记忆系统。如果没有明确的删除和遗忘语义，系统会把过期、错误或被撤销的数据继续带入 Agent 行为。

## 数据类型策略

| 数据 | 默认策略 | 删除时需要处理 |
|---|---|---|
| RawAsset | 按数据源策略保留 | 派生事实、索引、图谱关系、记忆引用 |
| ExtractedFact | 跟随来源或用户确认状态 | 来源断链、置信度、下游对象 |
| CanonicalFact | 保留用户确认和审计链；可复核、失效、替代或撤销 | Context Bundle、Source-Backed Answer、候选和索引引用 |
| Index Entry | 跟随原始或派生对象 | 全文索引、向量索引、缓存 |
| Memory | 必须可查看、可编辑、可删除、可过期 | 最近使用记录、Agent 行为影响 |
| RumorClaim | 普通 parked 默认 60 天，高影响或订阅主题 180 天；原始物料默认不长期保存 | review queue、candidate link、source envelope、统计摘要 |
| ConsentGrant | 到期或撤销后失效 | 授权期间产生的访问和派生结果 |
| AuditEvent | 按安全审计策略保留 | 与隐私删除请求之间的冲突 |

## 删除语义

- 删除原始数据：应标记所有派生对象为来源不可用，并触发索引清理。
- 删除、排除或撤销外部来源：生成 Source Tombstone，阻止旧 Source Revision 被新检索命中，并触发依赖 Canonical Fact 复核。
- revoke 或 delete Manual Input：生成 Manual Input Tombstone，阻止旧 input、extraction 和 embedding 被新检索命中，并触发依赖 Canonical Fact 复核或派生对象停止使用。
- dismiss 或 expire RumorClaim：不再检索或进入 Bundle；如果已创建 Knowledge Candidate，后续生命周期跟随 Candidate。
- 删除 RumorClaim source envelope：不得影响已确认 Canonical Fact；已确认对象必须有自己的 provenance 或 review 记录。
- 删除派生事实：不必删除原始数据，但需要从索引和图谱中移除引用。
- 撤销 Canonical Fact：生成 Fact Tombstone，不再进入新 Context Bundle；历史审计和旧回答解释仍保留。
- 删除记忆：不得继续影响 Agent 检索、排序、提示词或自动化策略。
- 撤销授权：阻止未来访问，并展示授权期间发生过的关键使用记录。

## 待决问题

- 审计日志保留多久？
- 用户删除数据时，是否允许保留不可逆脱敏统计？
- 已经进入外部模型上下文的数据如何标记为不可撤回？
- 项目级临时记忆的默认过期时间是多少？
