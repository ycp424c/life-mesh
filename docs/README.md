# LifeMesh 文档地图

状态：active
最后更新：2026-06-26
职责边界：说明文档体系如何组织、维护和演进。

## 目录结构

```text
docs/
  00-vision/        产品愿景、原则、术语
  01-governance/    数据宪法、分类、授权、安全治理
  02-domain/        数据地图、数据源评估、领域对象、记忆模型、溯源
  03-architecture/  系统架构、数据层、Agent 接入、安全审计
  04-roadmap/       渐进式阶段、里程碑、非目标
  05-decisions/     ADR 决策记录
  06-research/      共享对话、外部材料、调研摘要
  07-security/      威胁模型、访问控制、工具安全、备份恢复
  08-dashboard/     Web 项目看板维护规则
  templates/        RFC、ADR、数据源接入等模板
```

## 文档状态

- draft：草案，允许频繁调整。
- active：当前有效版本，后续实现应以它为准。
- superseded：被新文档替代，保留历史。
- archived：历史材料，不再作为当前依据。

## 当前关键入口

- [Obsidian Vault 数据源评估](02-domain/data-sources/obsidian-vault.md)
- [Knowledge Candidates](02-domain/knowledge-candidates.md)
- [Canonical Facts](02-domain/canonical-facts.md)
- [Context Bundle](02-domain/context-bundle.md)
- [CLI Contract](03-architecture/cli-contract.md)
- [System Map](03-architecture/system-map.md)
- [渐进式路线图](04-roadmap/phases.md)
- [项目看板维护规则](08-dashboard/project-board.md)

## 演进规则

- 新增能力前，先确认它属于哪个路线图阶段。
- 新增数据源前，先完成数据源接入评估。
- 新增 Agent 动作前，先定义权限、审计和人工确认策略。
- 改变核心架构或治理原则时，必须新增 ADR。
- 研究结论进入产品或架构前，需要从 `06-research` 提炼到正式文档。
- 改变项目状态、路线图、架构、风险或决策时，必须同步更新 `dashboard/project-state.js`。
- 每次交付前必须确认 Web 看板与文档状态一致。
