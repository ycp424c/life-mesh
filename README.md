# LifeMesh

LifeMesh 是一个面向个人的 Personal Data OS：把分散在生活、工作、关系、文件、日程和决策中的个人数据，逐步整理成可检索、可理解、可授权、可审计，并能被 AI Agent 安全使用的上下文基础设施。

当前阶段已从文档结构和静态 Web 项目看板，进入第 1 阶段本地 CLI 原型。已实现 Obsidian 只读 Context Bundle、source-neutral BundleAssembler，以及 ADR-0008 的 Manual Input Inbox：本地 SQLite、FTS、sqlite-vec、LM Studio embedding/VLM、update/revoke/delete 和 inbox-derived promote 闭环。ADR-0009 的 RumorClaim / UnverifiedClaim 已有本地结构化 CLI MVP：保存通过初筛的 claim、entity/relation mentions 和最小 source envelope，默认不进入普通 Bundle，显式包含时只能作为未验证 lead，并且只能 promote 到 Knowledge Candidate。2026-07-09 已完成 Q20 真实 vault 手工验收记录并落地 Candidate inbox 最小 CLI。2026-07-15 已接受 ADR-0010 的 Unified Write Model 目标架构与实施规格；统一 schema、Acceptance、Canonical Object、Fact Review 和真实数据库迁移尚未实现。

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
- [Manual Input 数据源评估](docs/02-domain/data-sources/manual-input.md)
- [Rumor Claims](docs/02-domain/rumor-claims.md)
- [架构总览](docs/03-architecture/overview.md)
- [系统架构图说明](docs/03-architecture/system-map.md)
- [Unified Write Model 架构](docs/03-architecture/write-model-and-migrations.md)
- [渐进式路线图](docs/04-roadmap/phases.md)
- [Phase 1 落地计划](docs/04-roadmap/phase-1-delivery-plan.md)
- [决策记录](docs/05-decisions/README.md)
- [ADR-0010 Unified Write Model](docs/05-decisions/ADR-0010-unified-write-model-transactional-acceptance-and-database-migration.md)
- [Unified Write Model 实施规格](docs/superpowers/specs/2026-07-10-unified-write-model-design.md)
- [共享对话摘要](docs/06-research/source-conversation-summary.md)
- [威胁模型](docs/07-security/threat-model.md)
- [用户故事](docs/04-roadmap/user-stories.md)
- [项目看板](dashboard/index.html)
- [看板维护规则](docs/08-dashboard/project-board.md)

## 当前状态

文档基线和静态项目看板已建立。第 1 阶段已收敛为 Personal Context Layer，CLI 原型已提供 `lifemesh bundle`、Obsidian Source Adapter、source-neutral BundleAssembler、JSON Context Bundle、stale/missing 链路、agent skill，以及 Manual Input Inbox 的本地记录、语义检索、截图 VLM extraction、`--source manual-input/all` Bundle、update/revoke/delete 和 promote 到 inbox-derived 最小 task/event/memory/fact/candidate。Bundle slice 已包含 `citation` 展示字段；2026-07-09 已用真实 vault Q20 样例确认 Obsidian `citation.label` 与 stale/missing 状态报告可用。Candidate inbox 当前支持 `candidate add/list/show/discard`；ADR-0010 已确定 confirm / merge / edit、统一 Candidate handoff、Acceptance、Canonical Fact / Memory / Task / Event、Fact Review 与数据库迁移必须一次性交付，但这些能力当前仍未实现。Manual Input 检索已区分 `strong` 证据命中和 `weak` 语义近邻，弱近邻只能作为 `lead`。RumorClaim 当前支持 `lifemesh rumor add/list/show/keep/dismiss/expire/promote` 和 `bundle --source rumor` / `--include-unverified` 的 lead-only 准入；自动 source adapter、截图/图片自动抽取、外部事实核查和 review UI 尚未实现。

## 本地 CLI 原型

Obsidian 只读 Bundle：

```bash
bin/lifemesh bundle "AI 对开源生态有什么结构性冲击？" --source obsidian --vault tests/fixtures/obsidian-vault --out /tmp/lifemesh-bundle.json
```

Manual Input 使用 `~/.lifemesh/config.json` 或环境变量配置本地依赖：

```json
{
  "obsidian_vault": "/path/to/vault",
  "lmstudio_base_url": "http://localhost:1234/v1",
  "embedding_model": "local-embedding-model",
  "vlm_model": "local-vlm-model",
  "sqlite_vec_extension": "/path/to/vec0"
}
```

Manual Input 会优先使用 LM Studio 和 sqlite-vec；缺配置、本地服务不可用、embedding/VLM 失败或扩展加载失败时降级保存记录，保留 SQLite/FTS、show/list/delete/revoke 能力，并在审计事件与状态字段中标记失败原因。

```bash
bin/lifemesh input add --kind note --text "需要记住的内容"
bin/lifemesh input search "需要找什么"
bin/lifemesh bundle "需要什么上下文" --source all --vault tests/fixtures/obsidian-vault
```

`--source all` 会让 Obsidian 和 Manual Input 各自返回 candidates，再由 BundleAssembler 统一执行准入、来源层级、去重、多样性选择和 `assembly_report` 诊断。

Candidate inbox 本地 MVP：

```bash
bin/lifemesh candidate add "候选知识" --type fact --source-ref "obsidian:hot.md#L16-L22"
bin/lifemesh candidate list
bin/lifemesh candidate show <candidate-id>
bin/lifemesh candidate discard <candidate-id> --reason "不再需要"
```

RumorClaim 本地 MVP：

```bash
bin/lifemesh rumor add --claim-text "未验证线索" --claim-type factual_claim --user-relevance medium --impact medium
bin/lifemesh rumor list
bin/lifemesh rumor keep <rumor-claim-id> --reason "人工检视后继续保留"
bin/lifemesh bundle "需要未验证线索的任务" --source all --include-unverified --vault tests/fixtures/obsidian-vault
```

使用测试 vault：

```bash
bin/lifemesh bundle "AI 对开源生态有什么结构性冲击？" --source obsidian --vault tests/fixtures/obsidian-vault
```

运行测试：

```bash
python3 -m unittest discover -s tests
```
