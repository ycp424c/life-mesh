# Canonical Objects

状态：draft
最后更新：2026-06-26
职责边界：定义规范化事实库中的核心对象，供后续数据模型和接口设计使用。

## 核心对象

| 对象 | 说明 |
|---|---|
| Source | 数据来源，如日历、文件夹、邮件导出、手动录入。 |
| RawAsset | Raw Vault 中的原始文件或记录。 |
| ExtractedFact | 从原始数据抽取出的事实。 |
| Entity | 人、组织、地点、项目、资产等实体。 |
| Event | 已发生或将发生的时间事件。 |
| Task | 可执行的任务。 |
| Commitment | 用户对自己或他人的承诺。 |
| Deadline | 截止日期或强约束时间点。 |
| Person | 联系人和关系上下文。 |
| Project | 项目、目标或阶段性工作空间。 |
| Memory | 长期或阶段性记忆。 |
| DecisionRecord | 决策及其理由。 |
| ConsentGrant | 授权记录。 |
| AuditEvent | 审计事件。 |
| ToolInvocation | Agent 或工具调用记录。 |

## 对象设计原则

- 每个对象都应关联来源和更新时间。
- 派生对象应记录抽取方式和置信度。
- 记忆、承诺、决策必须能被用户纠正。
- 与第三方相关的数据要单独标记。
- 高敏对象默认不进入通用检索上下文。
