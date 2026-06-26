# Architecture Overview

状态：draft
最后更新：2026-06-26
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
       - Context Slice
       - Context Bundle
       - Knowledge Candidate
       - User Confirmation
  -> Canonical Knowledge
       - Canonical Fact
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
- Canonical Fact 和 Memory 可以进入 Context Bundle，但必须保留 provenance、撤销路径和风险级别。
- Agent Access Layer 只暴露授权后的工具和资源。
- Audit Layer 记录读取、写入、删除、授权和动作执行。
- Source Adapter 负责接入具体数据源，但核心生命周期、权限、溯源和审计语义必须保持 source-neutral。

## 可视化边界

`dashboard/` 中的 Web 看板只是架构、路线图和风险状态的可视化入口，不是架构事实源。

架构事实以 `docs/03-architecture/` 和已接受 ADR 为准。看板展示的架构视图发生变化时，必须先确认对应架构文档或 ADR 已同步。
