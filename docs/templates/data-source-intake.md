# Data Source Intake: Source Name

状态：draft
日期：YYYY-MM-DD

## Source

- 名称：
- 类型：
- 所有人：
- 接入方式：

## Purpose

为什么要接入这个数据源？

## Data Scope

- 字段范围：
- 时间范围：
- 是否包含第三方信息：
- 是否包含高敏感信息：

## Classification

- 敏感级别：
- 是否允许进入 Raw Vault：
- 是否允许结构化抽取：
- 是否允许进入索引：
- 是否允许进入长期记忆：
- 是否允许进入模型上下文：

## Rumor Policy

如果该 source adapter 可能产出可信度未知的片段、截图或图片线索，必须填写：

- 是否允许产出 RumorClaim：
- 支持的 material types：text / screenshot / image
- 默认 sensitivity：
- raw retention：none / temporary / user_saved
- 默认 relevance scope：
- 是否允许 sensitive auto-save：
- 默认过期时间：
- 是否允许 dashboard 摘要显示内容：
- 是否允许自动 promote 到 Knowledge Candidate：

## Permissions

- 默认可读主体：
- 默认可写主体：
- 需要人工确认的动作：
- 授权过期策略：

## Audit

需要记录哪些访问、变更和派生结果？

## Deletion And Revocation

如何撤销授权？如何删除原始数据和派生数据？

## Threats

这个数据源可能带来哪些 prompt injection、越权访问、敏感外泄或记忆污染风险？
