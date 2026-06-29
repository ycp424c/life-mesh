# Data Source Intake: Obsidian Vault

状态：draft
最后更新：2026-06-29
职责边界：记录 LifeMesh 首个验证适配器的范围、风险、接入边界和待确认问题。

## Source

- 名称：Obsidian Vault
- 本机路径：`/Users/justynchen/Documents/docs/obsidian-default`
- 类型：本地 Markdown 知识库
- 当前规模：约 1329 个 Markdown 文件，约 1941 个非 Markdown 文件或附件
- 现有特征：vault 内包含 `.obsidian` 配置、`.git`、`_attachments`、年度归档、临时笔记和索引类文件

## Purpose

用 Obsidian Vault 作为 LifeMesh 第 1 阶段“静态知识数字化”的首个真实验证适配器。

Obsidian Vault 不是产品中心。它用于验证可编辑静态知识源的 source-neutral 能力：

- Source Adapter
- Source Revision
- ContextCandidate metadata
- Citation Status
- 路径排除
- 删除级联
- 最小上下文

这个场景优先验证：

- 能否从大量 Vault Note 中找到相关资料。
- 回答能否引用来源。
- 系统能否区分原始事实、摘要和推断。
- 删除或排除某些笔记后，索引和派生结果是否不再影响回答。
- Agent 是否只拿到当前问题需要的最小上下文。
- Obsidian adapter 是否只负责只读扫描、revision、candidate metadata 和 source diagnostics，而不承担最终跨源排序或 Bundle 准入。

## Data Scope

- 初始范围：Markdown 笔记文本、frontmatter、标题、wikilink、任务标记、附件链接元信息。
- 初始排除：附件正文解析、图片 OCR、音视频转写、自动写回 vault。
- 是否包含第三方信息：可能包含，需要按 Private 处理。
- 是否包含高敏感信息：可能包含，不应假设全 vault 都可进入模型上下文。

## Initial Index Scope

第一版采用只读索引，不全量处理整个 vault。

包含：

- Markdown 笔记文本
- frontmatter
- 标题
- wikilink
- 任务标记
- 附件链接元信息

默认排除：

- `.git/`
- `.obsidian/`
- `_attachments/` 的二进制内容
- `Trash/`
- `_archives/`
- `tmp/`

这些排除规则的目的不是永久放弃这些内容，而是先降低敏感数据、历史归档、临时笔记、二进制附件和工具配置进入模型上下文的风险。

## Classification

- 敏感级别：Private，局部内容可能达到 Sensitive。
- 是否允许进入 Raw Vault：允许，只读镜像或索引引用优先。
- 是否允许结构化抽取：允许，但必须保留来源。
- 是否允许进入索引：允许，但应支持排除路径和删除级联。
- 是否允许进入长期记忆：默认不允许，除非用户明确确认。
- 是否允许进入模型上下文：只允许检索命中的最小片段。

## Permissions

- 默认可读主体：本地 LifeMesh 检索流程。
- 默认可写主体：无。
- 需要人工确认的动作：写入长期记忆、修改 vault、删除或移动 vault 文件、处理高敏感内容。
- 授权过期策略：阶段 1 原型期按本地会话或本地配置控制，尚未决策长期授权。

## Audit

需要记录：

- 查询内容。
- 命中的 Vault Note Revision。
- 使用的片段范围。
- 是否生成摘要、事实或推断。
- 是否排除敏感路径。
- 命中来源在回答时是否仍匹配当前文件。

## Change Handling

Obsidian Vault 是可编辑源，不应假设笔记索引后保持不变。

第一版处理规则：

- 每篇进入索引的 Vault Note 生成 `VaultNoteRevision`。
- `VaultNoteRevision` 是通用 `SourceRevision` 在 Obsidian 适配器下的实现。
- revision 由 `path + mtime + size + content_hash + indexed_at` 识别。
- 查询前或手动刷新时执行轻量变更检测。
- `mtime + size` 未变时可复用旧 revision；疑似变化时重新计算 content hash。
- 内容变化后重建该笔记的索引片段，并将旧 revision 标记为 stale。
- 删除、移动到排除路径或撤销授权时生成 tombstone，使旧索引和派生事实不可再命中。
- 旧回答中如果引用了 stale revision，应显示来源已变更，而不是静默当作当前来源。

## Existing Answer Behavior

旧回答不自动重写。它是历史交互记录，必须保留当时使用的 `VaultNoteRevision`。

引用状态：

- current：引用 revision 仍匹配当前 Vault Note。
- stale：笔记已修改，旧回答引用的是历史 revision。
- missing：笔记被删除、移动到排除路径或授权撤销。

如果旧回答包含 stale 或 missing 来源，界面应提示用户基于当前笔记重新生成。系统不得把 stale 或 missing revision 用于新问题检索。

## Deletion And Revocation

- 用户排除某个路径或笔记后，检索索引和派生事实必须失效。
- 不直接修改 vault 源文件。
- 如果后续需要写回 Obsidian，必须单独评估并新增权限设计。

## Threats

- 笔记内容可能包含 prompt injection。
- Vault 中可能存在高敏感个人内容。
- wikilink 和附件链接可能产生错误溯源。
- 旧笔记可能过期，但仍被检索命中。
- 将摘要或推断误写为长期记忆会污染用户画像。

## Open Questions

- Vault 内 `.git` 历史是否完全不进入 LifeMesh？
- frontmatter 的哪些字段可作为结构化事实？
- 是否需要允许用户为某些归档目录建立显式白名单？

## 相关样例

- [Obsidian 检索最小验收样例](obsidian-retrieval-sample.md)：用真实 vault 数据验证 `bundle` 命令、JSON Bundle schema 和 stale 链路。
