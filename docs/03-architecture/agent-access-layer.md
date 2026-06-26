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

## 消费 Context Bundle

Agent 拿到 Context Bundle 后，按每个 Context Slice 的 `evidence_role` 消费，不自己判断角色：

- **事实性陈述的回答**必须是 Source-Backed Answer，只能基于 `fact` + `raw`，不能基于 `context` 或 `lead`。
- **建议、规划、草稿类输出**可以用 `context` 调整风格和排序，用 `lead` 提供灵感，但必须区分"基于事实"和"基于偏好/线索"两部分。
- **`lead` 永远不能单独支撑一个结论**：候选线索要进回答，必须带"未核实"标注，或先走 Fact Acceptance 变成 `fact`。

Agent 不得：

- 把 `context`（偏好）写成客观事实。
- 把 `lead`（候选）当成已确认结论。
- 在事实性回答里引用失效来源；stale / missing / revoked 来源只能进报告区。

## 待决问题

- 是否采用 MCP 作为首个 Agent 接口协议？
- 是否每类数据源独立暴露服务？
- Agent 会话授权和长期授权如何区分？
- 工具调用日志是否进入用户可见时间线？
