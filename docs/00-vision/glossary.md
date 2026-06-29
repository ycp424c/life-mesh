# Glossary

状态：draft
最后更新：2026-06-29
职责边界：统一 LifeMesh 的核心术语，避免后续文档语义漂移。

| 术语 | 含义 |
|---|---|
| Personal Data OS | 面向个人数据、上下文、记忆、权限和 Agent 能力的底层系统。 |
| Raw Vault | 保存原始文件、导出、扫描件、网页快照等不可随意改写的数据保险库。 |
| Canonical Store | 从原始数据抽取出的规范化事实和对象库。 |
| Memory | 可被长期复用的用户偏好、事实、目标、关系或阶段性上下文。 |
| Explicit Memory | 用户明确要求系统记住的记忆。 |
| Inferred Memory | 系统从多次行为中推断出的偏好或模式。 |
| Contextual Memory | 与某项目、某阶段或某任务有关的临时上下文。 |
| Agent Access Layer | Agent 访问数据和执行动作的受控接口层。 |
| Consent Grant | 用户授予某个 Agent 或工具访问特定数据/动作的授权记录。 |
| Audit Event | 记录系统访问、变更、授权、撤销或执行动作的审计事件。 |
| Source Adapter | 连接 LifeMesh 与某个外部或本地个人数据源的边界，同时保持生命周期、权限、溯源和审计语义一致。 |
| Source Revision | 任一可编辑数据源中某个条目的版本化来源引用；Vault Note Revision 是它在 Obsidian 场景下的特例。 |
| Personal Context Layer | 将个人数据源转成任务级、授权内、可追溯上下文的 source-neutral 层；第一阶段要验证的核心能力。 |
| Context Slice | 为某个任务选出的最小上下文单元，携带来源版本、引用状态、敏感级别和新鲜度。 |
| Context Bundle | 在特定权限边界下，为某个 Agent 任务组装的一组 Context Slice。 |
| Knowledge Candidate | 从上下文中识别出的候选事实、偏好、关系、任务或决策；确认前不是 canonical knowledge。 |
| Knowledge Candidate Type | Knowledge Candidate 的类型，第一版包括 fact、preference、relationship、task、decision。 |
| Canonical Fact | 已核实、可追溯、可撤销，并可在 Context Bundle 中复用的事实。 |
| Fact Acceptance | 将 Knowledge Candidate 或用户手动陈述转成 Canonical Fact 的动作或策略路径。 |
| Fact Review | Source Revision stale、missing 或 revoked 后，对依赖它的 Canonical Fact 进行重新确认、修订、失效或撤销的流程。 |
| Source Tombstone | 来源被删除、排除或撤销授权后的不可用标记，用于阻止旧 Source Revision 继续命中新任务。 |
| Fact Tombstone | Canonical Fact 被撤销、失效或替代后的不可用标记，用于阻止旧 fact 继续进入新 Context Bundle。 |
| User Confirmation | 候选知识进入 canonical facts、长期记忆或高风险外部动作前的用户确认；普通回答不应被确认流程阻塞。 |
| Candidate Lifecycle | Knowledge Candidate 持久化前的生命周期状态，初始包括 transient、inbox、confirm_required、discard。 |
| Obsidian Vault | LifeMesh 第一个验证适配器：本地 Obsidian 知识库，用于验证可编辑知识源，不是产品中心。 |
| Vault Note | Obsidian Vault 内的 Markdown 笔记，可能包含 frontmatter、标题、wikilink、任务和附件链接。 |
| Vault Note Revision | 某篇 Vault Note 被索引时的具体版本，由路径、修改元数据、内容哈希和索引时间识别。 |
| Stale Source | 曾经被索引但已因编辑、移动、删除或排除规则变化而不再匹配当前源文件的来源版本。 |
| Citation Status | Source-Backed Answer 中每条来源引用的新鲜度状态，初始包括 current、stale、missing。 |
| Source-Backed Answer | 带来源引用的回答，需要区分来源事实、摘要和模型推断。 |
