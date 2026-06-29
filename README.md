# LifeMesh

LifeMesh 是一个面向个人的 Personal Data OS：把分散在生活、工作、关系、文件、日程和决策中的个人数据，逐步整理成可检索、可理解、可授权、可审计，并能被 AI Agent 安全使用的上下文基础设施。

当前阶段已从文档结构和静态 Web 项目看板，进入第 1 阶段最小只读 CLI 原型；暂不引入运行时服务、数据库或完整技术栈绑定。

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
- [Obsidian Vault 数据源评估](docs/02-domain/data-sources/obsidian-vault.md)
- [架构总览](docs/03-architecture/overview.md)
- [系统架构图说明](docs/03-architecture/system-map.md)
- [渐进式路线图](docs/04-roadmap/phases.md)
- [Phase 1 落地计划](docs/04-roadmap/phase-1-delivery-plan.md)
- [决策记录](docs/05-decisions/README.md)
- [共享对话摘要](docs/06-research/source-conversation-summary.md)
- [威胁模型](docs/07-security/threat-model.md)
- [用户故事](docs/04-roadmap/user-stories.md)
- [项目看板](dashboard/index.html)
- [看板维护规则](docs/08-dashboard/project-board.md)

## 当前状态

文档基线和静态项目看板已建立。第 1 阶段已收敛为 Personal Context Layer，第一轮只读原型已提供 `lifemesh bundle`、Obsidian Source Adapter、JSON Context Bundle、stale/missing 链路和 agent skill；验收通过后再推进来源引用展示、Candidate inbox、受限写入和 Canonical Fact 复核实现。

## 本地 CLI 原型

第一轮只读原型已提供本地命令：

```bash
bin/lifemesh bundle "AI 对开源生态有什么结构性冲击？" --source obsidian --vault tests/fixtures/obsidian-vault --out /tmp/lifemesh-bundle.json
```

使用测试 vault：

```bash
bin/lifemesh bundle "AI 对开源生态有什么结构性冲击？" --source obsidian --vault tests/fixtures/obsidian-vault
```

运行测试：

```bash
python3 -m unittest discover -s tests
```
