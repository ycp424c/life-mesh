# ADR-0004: Source-Neutral Core

状态：accepted
日期：2026-06-26

## Context

Obsidian Vault 是 LifeMesh 第一个真实验证适配器，但 LifeMesh 的目标不是做 Obsidian 增强器。后续个人数据会来自日历、任务、邮件、联系人、文件夹、决策记录和其他来源。若核心模型围绕 Obsidian 设计，后续接入其他数据源会被迫套用笔记语义。

## Decision

LifeMesh 的核心模型保持 source-neutral。Obsidian 只作为第一个 Source Adapter，用于验证可编辑静态知识源。

通用概念优先使用 `SourceAdapter`、`SourceReference`、`CitationStatus`、权限、审计、删除级联和最小上下文。`SourceRevision` 是 Obsidian 等可编辑外部来源的 Source Reference 类型；Manual Input 不使用 SourceRevision，而以 input record、content_hash、状态和 audit event 表达来源身份。`VaultNoteRevision` 是 `SourceRevision` 在 Obsidian 场景下的特例，而不是整个系统的中心模型。

## Consequences

正向影响：

- 后续接入日历、任务、邮件、联系人时不会被 Obsidian 语义绑住。
- Obsidian 原型验证出的 revision、stale、missing、tombstone 能沉淀为通用源生命周期能力。
- 产品定位保持 Personal Data OS，而不是单一知识库工具。

代价：

- 第一版实现需要区分通用抽象和 Obsidian 适配器细节。
- 文档和看板必须避免把 Obsidian 表述成产品中心。

## Alternatives Considered

- 以 Obsidian 为中心推进第一版：能更快落原型，但会把笔记、wikilink、vault 结构误当成通用个人数据模型。
- 先抽象所有数据源再实现：更完整，但会拖慢第一个真实验证场景。
