# Agent Access Layer

状态：draft
最后更新：2026-06-26
职责边界：定义 AI Agent 如何通过受控接口访问 LifeMesh，而不是直接访问底层数据。

## 目标

- 给 Agent 提供足够上下文。
- 限制 Agent 的数据范围和动作范围。
- 让每次访问可审计。
- 让用户能撤销授权和纠正结果。

## 逻辑接口

初始可以把 Agent 能力拆成多个逻辑服务：

- personal-memory-server
- calendar-task-server
- document-search-server
- contacts-server
- finance-readonly-server
- health-readonly-server
- automation-server

这些名称代表职责边界，不代表已经选择具体实现。

## 能力分级

| 能力 | 示例 | 默认要求 |
|---|---|---|
| Resource | 读取授权范围内的文档、记忆、事件 | 审计读取 |
| Search | 查询相关资料并返回来源 | 返回引用和置信度 |
| Draft | 生成邮件、提醒、任务草稿 | 用户确认后写入 |
| Write | 写入记忆、任务、标签 | 可撤销、可审计 |
| Act | 发送消息、提交表单、调用外部服务 | 强制人工确认 |

## 待决问题

- 是否采用 MCP 作为首个 Agent 接口协议？
- 是否每类数据源独立暴露服务？
- Agent 会话授权和长期授权如何区分？
- 工具调用日志是否进入用户可见时间线？
