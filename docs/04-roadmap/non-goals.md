# Non Goals

状态：draft
最后更新：2026-06-29
职责边界：明确当前阶段不做什么，降低后续范围膨胀。

## 当前不做

- 不写超出 [Phase 1 Delivery Plan](phase-1-delivery-plan.md) 的业务代码。
- 不选定完整前端、后端、数据库或部署技术栈；Phase 1 只允许最小 CLI 和本地文件产物。
- 不接入真实个人数据。
- 不处理真实敏感样例。
- 不实现 Agent 自动执行。
- 不建立金融、健康、位置等高敏感数据接入。
- 不做全量聊天记录导入。
- 不把向量数据库当作唯一架构核心。

## 进入 Phase 1 扩展前必须完成

- 第一批数据源已明确：Obsidian Vault。
- 第一批用户故事已记录在 `user-stories.md`。
- 数据分类和授权策略已有第 0 阶段草案。
- 最小可行架构已明确：CLI + JSON Bundle + skill，不引入 server。
- 审计、删除、复核和撤销策略已有 ADR / 治理文档。
- 最小只读 CLI 原型可以启动；在扩展到 richer citation UI、frontmatter 结构化抽取、candidate inbox 或写侧命令前，仍需确认对应边界。
