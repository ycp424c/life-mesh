# Architecture Overview

状态：draft
最后更新：2026-07-15
职责边界：描述 LifeMesh 的高层架构，不绑定具体技术栈。

## 一句话架构

原始数据不要直接喂给 Agent；先进入受控数据层，再经过结构化、索引、权限、审计，最后通过工具接口供 Agent 调用。

## 高层流程

```text
个人数据源
  -> 采集连接器 / 手动上传 / OCR / API 导入
  -> Raw Vault 原始数据保险库
  -> 清洗、去重、实体抽取、时间线化、标签化
  -> 个人知识层
       - 文档库
       - 结构化数据库
       - 向量索引
       - 知识图谱
       - 事件时间线
  -> Personal Context Layer
       - Source-backed Candidate Retrieval
       - BundleAssembler
       - Context Slice
       - Context Bundle
       - Knowledge Candidate
       - User Confirmation
  -> Canonical Knowledge
      - Canonical Fact
      - Fact Review / Tombstone
       - Memory
       - Decision Record
  -> 权限与策略层
       - 数据分类
       - 授权范围
       - 审计日志
       - 撤销机制
  -> Agent 工具层
       - 搜索
       - 总结
       - 日程
       - 任务
       - 邮件草稿
       - 提醒
       - 决策辅助
  -> 用户确认 / 自动执行 / 反馈修正
```

## 关键边界

- Raw Vault 保存原始数据，不被 Agent 直接任意读取。
- Canonical Store 保存可解释、可追溯的事实。
- Index 和 Graph 用于检索与关联，但不能替代来源。
- Personal Context Layer 负责把不同来源的材料组装成任务级上下文，而不是把检索结果直接交给 Agent。
- Source Adapter 不直接产出最终 Bundle；它们产出带来源、权限和检索排序的 candidates，BundleAssembler 统一执行准入、分层、去重、多样性和诊断。
- Canonical Fact 和 Memory 可以进入 Context Bundle，但 Canonical Fact 必须保留 provenance、复核/撤销路径和风险级别，并通过 current source 支撑检查。
- Agent Access Layer 只暴露授权后的工具和资源。
- Audit Layer 记录读取、写入、删除、授权和动作执行。
- Source Adapter 负责接入具体数据源，但核心生命周期、权限、溯源和审计语义必须保持 source-neutral。
- Manual Input 是用户或 Agent 主动提交的数据源入口，不等同于后台自动采集。它不使用 SourceRevision，而通过 input record、extraction、content_hash、状态和 audit event 表达 source reference。截图、心情、活动、待办和手动日程必须先保留 provenance、敏感级别、用途和撤销路径，再进入事实、记忆、任务或候选流程。
- Manual Input 第一版使用用户级本地存储：`~/.lifemesh/lifemesh.db` + Raw Vault managed assets。检索层包含 FTS、本地 embedding 和 SQLite 向量索引；LM Studio 作为默认本地 embedding/VLM provider。
- Agent 可以自动捕获非高敏个人相关信息进入 Inbox，但必须透明说明，且不能自动 promote 到长期层或正式对象；明显高敏信息必须由用户明确提交。
- RumorClaim 是处理可信度未知材料的 Phase 1 follow-on 契约：它不是独立架构层，也不是 Manual Input kind；主资产是抽取出的 claim、entity mention 和 relation mention，原始物料默认只进 temporary parsing sandbox。
- RumorClaim 默认不进入普通 Context Bundle，明确请求未验证线索时只能作为 `lead`，且只能 promote 到 Knowledge Candidate。

## Unified Write Model 目标架构

ADR-0010 已确认 Unified Write Model 目标架构，但实现尚未开始。目标状态由统一 database layer 和 `KnowledgeWorkflow` 收敛 CLI、Manual Input、RumorClaim 的 Candidate handoff、Acceptance、Canonical Object、provenance、review、tombstone 与 audit；当前三个 legacy 写路径在迁移完成前仍是运行时真相。

迁移与恢复必须共享 exclusive lock，使用 SQLite online backup，并以迁移当时动态生成的 identity/count manifest 做守恒验收。详细边界见 [Unified Write Model And Migrations](write-model-and-migrations.md) 和 [ADR-0010](../05-decisions/ADR-0010-unified-write-model-transactional-acceptance-and-database-migration.md)。

## 可视化边界

`dashboard/` 中的 Web 看板只是架构、路线图和风险状态的可视化入口，不是架构事实源。

架构事实以 `docs/03-architecture/` 和已接受 ADR 为准。看板展示的架构视图发生变化时，必须先确认对应架构文档或 ADR 已同步。
