# Data Layers

状态：active
最后更新：2026-07-15
职责边界：定义 LifeMesh 数据层分层和各层职责。

## 分层

| 层 | 责任 | 不负责 |
|---|---|---|
| Raw Vault | 保存原始文件和记录，保证可追溯、可备份、可删除、可加密 | 直接服务 Agent 推理 |
| Canonical Store | 保存规范化对象和派生事实 | 保存不可解释的模型临时输出 |
| Index Layer | 提供全文、语义和结构化检索 | 作为唯一事实来源 |
| Graph Layer | 表达人、项目、文档、事件、承诺之间的关系 | 代替权限判断 |
| Timeline Layer | 组织事件、任务、承诺、截止日期和历史变化 | 决定自动执行策略 |
| Personal Context Layer | 把 source-backed candidates 组装成 Context Slice、Context Bundle 和 Knowledge Candidate | 直接写入长期记忆或 canonical facts |
| Policy Layer | 数据分类、授权、审计、撤销 | 存储业务事实 |

## 设计注意事项

Phase 1 运行时已使用统一 SQLite database layer 保存 Candidate、Acceptance、typed Canonical Object、normalized provenance、review、tombstone 和 audit；Raw Vault managed asset 通过 file-operation outbox 与数据库状态协调。

- 向量索引是检索工具，不是事实库。
- 图谱关系需要来源和置信度。
- 时间线对象应支持过去、现在、未来三类状态。
- 删除原始数据时，需要处理派生事实、索引和记忆的级联影响。
- Context Bundle 必须是按任务和权限临时组装的结果，不应被误当成永久知识。
- Source Adapter / Retriever 负责发现候选，Index Layer 只提供检索信号；最终 Bundle 准入、来源层级、去重、多样性和诊断由 Personal Context Layer 内的 BundleAssembler 执行。
- Context Bundle 按来源优先级组装：Canonical Fact > Memory > 当前任务相关 Source Reference > 当前任务生成的 Knowledge Candidate；stale / missing / revoked / deleted 来源只进入 excluded_sources / freshness_report，不进入可用上下文。
- Canonical Fact 进入 Bundle 前必须通过 `valid + active + current-supported` 准入检查；失效来源触发 Fact Review 和 tombstone 级联。Source Reference 可以是 SourceRevision，也可以是 Manual Input record / extraction。
- RumorClaim 属于未验证线索契约，不新增独立数据层。它位于 source material 与 Knowledge Candidate 之间，默认不进入普通 Bundle；明确请求未验证线索时只能作为 `lead`。
- RumorClaim 不直接写 Graph Layer。第一版只保存 entity_mentions / relation_mentions，确认或策略接受后才进入正式 Entity / Relation / Canonical Fact。
