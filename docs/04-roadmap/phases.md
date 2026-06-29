# Roadmap Phases

状态：draft
最后更新：2026-06-29
职责边界：定义 LifeMesh 从文档基线到可行动 Agent 的渐进路线。

## 第 0 阶段：个人数据宪法

目标：先定义安全边界和不可绕过的治理规则。

产物：

- 个人数据宪法
- 数据分类
- 授权与撤销规则
- 风险登记表
- 静态 Web 项目看板和同步维护规则

## 第 1 阶段：Personal Context Layer

目标：验证 source-neutral 的 Personal Context Layer，而不是普通 RAG 或 Obsidian 增强器。

落地计划：

- [Phase 1 Delivery Plan](phase-1-delivery-plan.md)

第一阶段要证明 LifeMesh 能把一个个人数据源转成任务级上下文：

- Context Slice：最小、可追溯、带权限和新鲜度的上下文单元。
- Context Bundle：为某个 Agent 任务组装的上下文包，按来源优先级组装（Canonical Fact > Memory > 当前任务相关 Source Reference > 当前任务生成的 Knowledge Candidate），失效来源只进入 `excluded_sources` / `freshness_report`。
- Knowledge Candidate：候选事实、偏好、关系、任务或决策。
- User Confirmation：确认后才进入 Canonical Store 或 Memory。
- Canonical Fact Review：依赖来源 stale / missing / revoked 后，事实进入复核、撤销或 tombstone 级联，而不是继续作为已核实事实使用。

交付方式（`ADR-0006` + `cli-contract.md`）：

- 读：`lifemesh bundle` 产出 JSON Context Bundle。
- 写（受限）：只读原型验收后的 Phase 1 后续 milestone 是 Manual Input Inbox + promote 闭环；`fact add` / `task add` / `remember` 与底层目标对象表保持一致；`candidate add` 用于 agent 推断待确认。
- 手动输入：`input add/search/list/show/update/revoke/delete/promote` 接收用户或 Agent 提交的截图、日程、心情、活动、待办和备注；默认本地 embedding，截图默认通过本地 LM Studio VLM 同步 extraction；Manual Input 不使用 SourceRevision。
- Agent 自动捕获：Agent 可自主把非高敏个人相关信息写入 `auto_captured` Inbox，但必须在回复中说明；不得自动 promote。
- agent 推断禁止直接 `fact add`，只能走 candidate → 用户 CLI 确认 → 按 type 升级（fact→Canonical Fact、task→Task、preference/relationship/decision→Memory）。
- fact 复核与撤销：`fact review` / `fact revoke` 处理 `needs_review`、superseded、invalid、revoked 和 tombstone。
- Skill 指导 agent 调用与 `evidence_role` 消费，使用范围是用户的所有信息。
- 不引入运行时 server，不绑定 MCP；`automation` 仍 deferred 在阶段 6。

当前架构可视化：

- [System Map](../03-architecture/system-map.md)

首个验证适配器：

- Obsidian Vault：`/Users/justynchen/Documents/docs/obsidian-default`

定位：Obsidian 只验证可编辑静态知识源，不作为 LifeMesh 的产品中心。

第一版索引范围：

- 只读处理 Markdown 笔记文本、frontmatter、标题、wikilink、任务标记和附件链接元信息。
- 默认排除 `.git/`、`.obsidian/`、`_attachments/` 二进制内容、`Trash/`、`_archives/`、`tmp/`。

后续优先数据：

- 笔记
- 项目文档
- 合同
- 简历
- 证书
- 学习资料
- 旅行资料
- 重要邮件导出
- 家庭文档
- 用户或 Agent 主动提交的截图、日程、心情、活动、待办和备注

## 第 2 阶段：系统日历/任务同步与高级调度

目标：在 Phase 1 已有 inbox-derived 最小 Event / Task 对象后，接入系统日历、提醒事项和外部任务应用，支持双向同步、计划、提醒、冲突检测和 DDL 追踪。

核心对象：

- Event
- Task
- Commitment
- Deadline

## 第 3 阶段：人际上下文

目标：抽取长期有用的关系事实，而不是无差别导入聊天全文。

关注：

- 联系人
- 沟通偏好
- 组织关系
- 合作项目
- 重要纪念日
- 历史互动摘要

## 第 4 阶段：长期记忆

目标：建立显式、推断、情境三类记忆，并支持查看、修改、删除、过期。

注：第 1 阶段已纳入受限写（`remember` 显式记忆、`preference`/`relationship`/`decision` 候选确认后入 Memory）。第 4 阶段负责记忆的完整查看、修改、删除、过期和情境记忆管理能力。

## 第 5 阶段：高敏感数据

目标：在治理、权限、审计、本地处理能力成熟后，再接入金融、健康、位置等高敏感数据。

## 第 6 阶段：可行动 Agent

目标：让 Agent 从查询和建议，逐步进入可控写入、草稿生成、自动化执行。

前置条件：

- 权限模型稳定
- 审计可用
- 风险确认机制可用
- 撤销路径可用
- 用户能理解 Agent 做过什么

## 持续跟踪要求

路线图阶段、阶段状态、验收条件、阻塞项或当前重点发生变化时，必须同步更新：

- `docs/04-roadmap/` 相关文档
- `dashboard/project-state.js`
- 必要时新增或更新 ADR
