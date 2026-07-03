# Knowledge Candidates

状态：draft
最后更新：2026-07-03
职责边界：定义第一版 Knowledge Candidate 的类型、共同字段和持久化边界。

## 定位

Knowledge Candidate 是从 Context Bundle 中识别出的候选知识。它可以帮助用户发现事实、偏好、关系、任务或决策，但在被用户确认或策略接受前，不是 canonical knowledge，也不是 Memory。

RumorClaim / UnverifiedClaim 是 Knowledge Candidate 的前置线索形态，不等同于 Knowledge Candidate。它来自可信度未知的文字片段、截图或图片，只在通过相关性、影响和可信度初筛后，才可 promote 到 Knowledge Candidate。

## 第一版类型

| 类型 | 说明 | 示例 | 默认生命周期 |
|---|---|---|---|
| fact | 带来源的客观陈述 | 某篇笔记提到“本地优先架构” | transient 或 inbox |
| preference | 用户偏好或长期倾向 | 用户倾向本地优先、可审计、低耦合 | inbox 或 confirm_required |
| relationship | 人、项目、主题、组织之间的关系 | 某人参与某项目，某主题关联某文档集 | inbox |
| task | 可能需要行动的事项 | 某笔记里出现“下周补设计文档” | inbox 或 confirm_required |
| decision | 用户做过的选择及其理由 | 选择静态看板而不是前端框架 | inbox 或 confirm_required |

## 共同字段

每个 Knowledge Candidate 至少应包含：

- `type`
- `summary`
- `confidence`
- `risk`
- `lifecycle`
- `source_refs[]`
- `why_suggested`
- `created_at`
- `expires_at`，可选

## 生命周期

- `transient`：仅用于当前任务，不进入候选收件箱。
- `inbox`：进入候选知识收件箱，等待用户批量整理。
- `confirm_required`：写入 Canonical Store、Memory、任务、自动化规则或外部动作前必须确认。
- `discard`：不保留。

## 持久化边界

- fact 可以在来源明确且风险低时作为临时上下文使用，但进入 Canonical Store 前仍需满足策略。
- 被确认或策略接受的 fact 可以转为 Canonical Fact。
- preference 默认不自动写入 Memory。
- relationship 涉及第三方时应提高风险级别。
- task 进入任务系统前需要确认。
- decision 需要保存来源和理由，不能只保存结论。
- RumorClaim `candidate_created` 只表示已生成 Knowledge Candidate，不表示 claim 已被核实。

## 确认流程

candidate 存在本地 inbox（第 1 阶段为 `.lifemesh/candidates.json`），用户用 CLI 异步批量确认，dashboard 只读展示、不写回：

```bash
lifemesh candidate list                      # 看待确认 inbox，按 risk/confidence 排序
lifemesh candidate show <id>                 # 看详情：来源、why_suggested、置信度
lifemesh candidate confirm <id>             # 接受
lifemesh candidate edit <id> "<text>"        # 先改再接受
lifemesh candidate merge <id1> <id2>         # 合并重复
lifemesh candidate discard <id>             # 丢弃
lifemesh candidate defer <id>               # 留在 inbox，下次再看
lifemesh candidate confirm --ids i1,i2,i3   # 批量
lifemesh candidate discard --type preference --older-than 30d
```

确认特性：

- **异步、不阻塞**：candidate 进 inbox 后，普通回答照常返回，不逼用户当场逐条确认。`bundle` 产出候选时只提示"本次产生 N 条候选，可 `candidate list` 复核"。
- **低风险自动接受**（Q12 路径 3）：非常明确、非画像的事实（"某笔记标题是 X""某文件在路径 Y""某 revision hash 是 Z"）不走人工确认，策略直接接受。
- **批量 + defer**：支持批量 confirm/discard，拿不准的留 inbox。
- **agent 不能 confirm**：agent 只能 `candidate add`，确认只能由用户发起。

## 确认后升级映射

确认不是无脑变 fact，candidate type 决定它升级成什么：

| candidate type | confirm 后变成 | 依据 |
|---|---|---|
| `fact` | Canonical Fact | Q12 路径 1（用户确认候选），acceptance_path=user_confirmation |
| `task` | Task（待办） | 任务系统 |
| `preference` / `relationship` / `decision` | Memory | Q14：这些是记忆形，不是事实；重要类正好需要确认，此流程即那个确认 |

只有 `fact` 候选确认后进 Canonical Fact；偏好/关系/决策候选确认后进 Memory。这样 fact 生成路径（Q12）与 Memory/Fact 边界（Q14）通过 type 对齐。

## 非目标

- 不把所有候选知识自动写入长期记忆。
- 不把候选知识当成模型已经确认的事实。
- 不在普通回答前强制用户逐条确认候选知识。
