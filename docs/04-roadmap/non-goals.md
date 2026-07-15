# Non Goals

状态：draft
最后更新：2026-07-15
职责边界：明确当前阶段不做什么，降低后续范围膨胀。

## 当前不做

- 不写超出 [Phase 1 Delivery Plan](phase-1-delivery-plan.md) 的业务代码。
- 不选定完整前端、后端、数据库或部署技术栈；Phase 1 只允许最小 CLI、本地文件产物，以及 ADR-0008 milestone 明确限定的用户级 SQLite / Raw Vault 本地存储。
- 不默认接入真实个人数据；真实 vault 仅能由用户显式传入路径或环境变量，用于只读手工验收，不持久化原文。
- 不处理真实敏感样例。
- 不实现 Agent 自动执行。
- 不建立金融、健康、位置等高敏感数据接入。
- 不做全量聊天记录导入。
- 不实现 RumorClaim 自动源接入、raw material ingestion、外部通知、review UI 或自动联网 fact-check；ADR-0009 当前只落地结构化 CLI MVP。
- 不把向量数据库当作唯一架构核心。

## 进入 Phase 1 扩展前必须完成

- 第一批数据源已明确：Obsidian Vault。
- 第一批用户故事已记录在 `user-stories.md`。
- 数据分类和授权策略已有第 0 阶段草案。
- Agent 最小交付架构仍是 CLI + JSON Bundle + skill，不引入 MCP 或 Agent server。ADR-0011 仅允许用户按需启动、绑定 `127.0.0.1` 的只读 Console Server；它不是 Agent 接口或后台服务。
- 审计、删除、复核和撤销策略已有 ADR / 治理文档。
- 最小 CLI 原型、ADR-0008 限定的 Manual Input 本地 Inbox 和 Candidate inbox `add/list/show/discard` 已落地。candidate confirm / merge / edit、正式对象与数据库迁移边界已由 ADR-0010 确认；实现必须遵守一次完整切换、动态 preflight、备份恢复和用户确认合同。Richer citation UI、frontmatter 结构化抽取、ADR-0010 范围外写命令或 Agent 自动执行仍需另行决策。
