# LifeMesh

LifeMesh 是一个面向个人的 Personal Data OS：把分散在生活、工作、关系、文件、日程和决策中的个人数据，逐步整理成可检索、可理解、可授权、可审计，并能被 AI Agent 安全使用的上下文基础设施。

当前阶段初始化文档结构和静态 Web 项目看板，不包含业务代码、运行时框架或技术栈绑定。

## 项目原则

- 数据主权优先：个人拥有、理解并控制自己的数据。
- 原始数据不直接喂给 Agent：先进入受控数据层，再结构化、索引、授权和审计。
- 最小必要上下文：Agent 每次只获得当前任务需要的数据和能力。
- 高风险动作可确认、可追踪、可撤销。
- 从低风险高价值数据开始，渐进接入高敏感数据。
- 文档先行：重大产品、架构、数据和安全决策必须进入文档或 ADR。

## 文档入口

- [文档地图](docs/README.md)
- [产品愿景](docs/00-vision/product-brief.md)
- [个人数据宪法](docs/01-governance/personal-data-constitution.md)
- [个人数据地图](docs/02-domain/data-map.md)
- [架构总览](docs/03-architecture/overview.md)
- [渐进式路线图](docs/04-roadmap/phases.md)
- [决策记录](docs/05-decisions/README.md)
- [共享对话摘要](docs/06-research/source-conversation-summary.md)
- [威胁模型](docs/07-security/threat-model.md)
- [用户故事](docs/04-roadmap/user-stories.md)
- [项目看板](dashboard/index.html)
- [看板维护规则](docs/08-dashboard/project-board.md)

## 当前状态

文档基线和静态项目看板已建立。下一步应补齐第一批数据源接入评估、阶段 0 治理细节和阶段 1 静态知识数字化的最小可行范围。
