# Provenance And Lifecycle

状态：draft
最后更新：2026-06-26
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

Obsidian Vault 这类来源不是不可变归档。LifeMesh 应先用 `VaultNoteRevision` 验证可编辑来源语义，但核心抽象应是 source-neutral 的 `SourceRevision`。

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

引用、索引片段、摘要和抽取事实都应指向具体 SourceRevision。当前文件发生编辑、移动、删除或被排除后，旧 revision 进入 stale 状态，不再用于新的检索命中。

第一版变更检测策略：

- 查询前或手动刷新时扫描允许范围内的 Markdown 文件。
- 先比较 `mtime + size`，只对疑似变化文件计算 content hash。
- 修改过的笔记重建索引片段。
- 被删除、移动到排除目录或撤销授权的笔记生成 tombstone，使旧索引和派生事实失效。

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
