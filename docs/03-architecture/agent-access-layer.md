# Agent Access Layer

状态：draft
最后更新：2026-06-30
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

## 交付方式（`ADR-0006`）

第 1 阶段 Agent 接口 = 薄 CLI + skill，不引入运行时 server。CLI 契约见 `cli-contract.md`：

- 读：`lifemesh bundle "<task>"` 产出 JSON Context Bundle。
- Phase 1 后续写入：`input add/search/list/show/update/revoke/delete/promote`（Manual Input Inbox，ADR-0008）。
- 用户断言写：`fact add` / `task add` / `remember` 后续与 Manual Input promote 共用底层目标对象。
- agent 自动捕获：只能对非高敏信息调用 `input add --auto-captured`，写入后必须透明说明 id、kind、摘要、sensitivity 和 Bundle 可用性。
- agent 推断写：`candidate add` 或 `input promote --to candidate`（进 inbox，需用户确认）。
- 事实复核：`fact review` / `fact revoke` 处理 `needs_review`、撤销和 tombstone。
- 配套 skill 指导 agent 调用与按 `evidence_role` 消费，使用范围是用户的所有信息，不限定某个 source。
- 硬规则：agent 推断禁止直接 `fact add` 或自动 promote，只能走 candidate / auto_captured → 用户确认。
- 硬规则：agent 不得替用户复核或撤销 fact，除非用户明确发出该操作指令。
- 任何能读 skill 的 agent 都能使用 LifeMesh，不绑定特定 client 或协议。

## 消费 Context Bundle

Agent 拿到 Context Bundle 后，按每个 Context Slice 的 `evidence_role` 消费，不自己判断角色：

- **事实性陈述的回答**必须是 Source-Backed Answer，只能基于 `fact` + `raw`，不能基于 `context` 或 `lead`。
- **建议、规划、草稿类输出**可以用 `context` 调整风格和排序，用 `lead` 提供灵感，但必须区分"基于事实"和"基于偏好/线索"两部分。
- **`lead` 永远不能单独支撑一个结论**：候选线索要进回答，必须带"未核实"标注，或先走 Fact Acceptance 变成 `fact`。
- **引用必须使用 Bundle 内的 `citation` 字段**：事实回答不得只写"根据你的笔记/输入"；Obsidian 至少展示 note path、heading、line range 和 citation status，Manual Input 至少展示 input id、kind、status、content hash 摘要和 citation status。
- **Manual Input 弱近邻只能作为线索**：当 `retrieval.match_status=weak` 或 `evidence_role=lead` 时，Agent 必须标注为弱相关/未核实，不得把它当作命中证据或事实来源。

Agent 不得：

- 把 `context`（偏好）写成客观事实。
- 把 `lead`（候选）当成已确认结论。
- 把 `retrieval.match_status=weak` 的 Manual Input 近邻称为精确命中。
- 在事实性回答里引用失效来源；stale / missing / revoked 来源只能进报告区。

## 待决问题

- ~~是否采用 MCP 作为首个 Agent 接口协议？~~ 已决：第 1 阶段不采用 MCP，Context Bundle 作为 JSON 产物经薄 CLI + skill 交付（`ADR-0006`）。
- ~~Bundle 产物格式：JSON 还是结构化 Markdown？~~ 已决：JSON。
- ~~第 1 阶段 CLI 契约（命令、参数、JSON schema）长什么样？~~ 已决：见 `cli-contract.md`。
- ~~配套 skill 如何组织（调用方式 + evidence_role 消费规则）？~~ 已决且第一版实体已落地：见 `cli-contract.md` 和 `skills/lifemesh/SKILL.md`。
- 后续阶段需要实时、有状态工具调用时，何时重新评估 MCP？
