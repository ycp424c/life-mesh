# ADR-0003: Vault Note Revision

状态：accepted
日期：2026-06-26

## Context

Obsidian Vault 是 LifeMesh 的第一个真实验证数据源，但它不是不可变归档。用户会持续编辑、移动、删除笔记，路径排除规则也可能变化。如果索引和引用只指向“当前文件路径”，旧回答、派生事实和审计记录会在源文件变化后失去可信来源。

## Decision

LifeMesh 将 Obsidian Vault 建模为可编辑源。每篇进入索引的 Vault Note 都生成 `VaultNoteRevision`，由 `path + mtime + size + content_hash + indexed_at` 标识。

来源引用、索引片段、摘要和抽取事实都指向具体 revision。当前笔记变化后，旧 revision 标记为 stale；删除、移动到排除目录或撤销授权时生成 tombstone，使旧索引和派生事实不可再用于新的检索命中。

旧回答不自动重写。旧回答中的引用展示 `current`、`stale` 或 `missing` 状态；当来源不再 current 时，系统提示用户基于当前笔记重新生成。

## Consequences

正向影响：

- 回答来源可以解释为“当时索引的版本”，不会静默漂移。
- 修改、删除和排除路径可以触发精确失效。
- 审计记录能解释旧回答为什么引用了旧内容。
- 旧回答保持历史可审计性，同时让用户知道来源是否仍然有效。

代价：

- 索引层需要记录 revision 状态。
- 查询或刷新前需要做轻量变更检测。
- 后续引用格式需要表达 revision 是否仍然有效。

## Alternatives Considered

- 只引用当前文件路径：简单，但编辑后旧回答和派生事实会失去可靠来源。
- 全量复制 immutable snapshot：溯源最强，但会复制大量私人内容，并增加删除和隐私处理成本。
- 依赖 vault 内 `.git` 历史：不选择，因为 `.git` 当前被排除，且 LifeMesh 不应假设用户始终维护可用历史。
