# ADR-0009: Unverified Rumor Claims

状态：accepted
日期：2026-07-03

## Context

LifeMesh 已有 Manual Input Inbox、`auto_captured`、弱检索 `lead`、Knowledge Candidate 和 Canonical Fact 复核边界。后续接入更多自动信息源后，系统会遇到大量可信度未知的材料：文字片段、截图、普通图片、转发内容、系统通知、网页摘录或其他来源的简短信号。

这些材料不适合直接进入 Manual Input `kind`。`kind` 表达载体或入口，例如 note、screenshot、event、mood、activity、task；“rumor” 表达材料的未验证语义状态，不是载体类型。它也不应该成为一整层与 Personal Context Layer 并列的新架构层，否则会增加生命周期、权限和复核模型的重复。

同时，原始流言材料往往是污染源：它可能含有广告、重复转发、第三方隐私、错误 OCR、截图噪声或无关片段。LifeMesh 应优先保留从材料中抽取出的 claim、entity mention 和 relation mention，而不是默认把原始文本或截图长期保存为资产。

## Decision

新增 source-neutral 的 `RumorClaim` / `UnverifiedClaim` 契约，作为 Phase 1 follow-on milestone。当前已落地本地结构化 CLI MVP；自动 source adapter、截图/图片自动抽取、review UI 和自动 fact-check 仍属于后续能力。

RumorClaim 的定位：

- 不作为独立架构层。
- 不作为 Manual Input `kind`。
- 不等同于 Knowledge Candidate。
- 主资产是抽取出的 claim、entity mentions 和 relation mentions。
- 原始物料默认只进入 temporary parsing sandbox，不长期保存。
- 只有通过最低初筛的 claim 才持久化。
- 通过规则门槛后，RumorClaim 只能 promote 到 Knowledge Candidate。

推荐处理链路：

```text
incoming text / screenshot / image
  -> temporary parsing sandbox
  -> claim extraction
  -> entity_mentions[] / relation_mentions[]
  -> user relevance + impact triage
  -> credibility dimensions
  -> persistence gate
  -> optional Knowledge Candidate promotion
```

## RumorClaim 字段

第一版最小字段集：

- `claim_text`
- `claim_type`
- `entity_mentions[]`
- `relation_mentions[]`
- `user_relevance`
- `relevance_reason`
- `impact`
- `impact_reason`
- `extraction_confidence`
- `evidence_state`
- `claim_quality`
- `assessment`
- `status`
- `expires_at`
- `review_queue`
- `sensitivity`
- `source_envelope`

`claim_type` 不直接复用 Knowledge Candidate 类型，但保持可映射：

| claim_type | 说明 | 候选映射 |
|---|---|---|
| `factual_claim` | 事实性陈述 | candidate `fact` |
| `relationship_claim` | 人、项目、组织、地点、资产之间的关系陈述 | candidate `relationship` |
| `intent_or_plan_claim` | 疑似计划、意图、安排或后续动作 | candidate `task` / `decision` / `fact`，视内容而定 |
| `risk_claim` | 潜在风险、异常、负面变化或预警 | candidate `fact` 或 `task` |
| `preference_claim` | 疑似偏好、倾向或判断标准 | candidate `preference` |
| `unknown_claim` | 已抽取但暂时无法归类 | 不自动 promote |

`user_relevance` 使用离散等级：

- `none`
- `low`
- `medium`
- `high`

`impact` 使用离散等级：

- `low`
- `medium`
- `high`
- `critical`

最低持久化门槛：

```text
save if user_relevance >= medium OR impact >= high
```

明显无关、广告、闲聊噪声、重复低质内容和低影响低相关 claim 直接丢弃，只保留处理计数和审计摘要。

## Credibility

第一版可信度不使用单一裸分，保留三个维度和一个规则派生标签：

| 字段 | 取值 | 说明 |
|---|---|---|
| `extraction_confidence` | `low` / `medium` / `high` | 系统是否读懂原始材料，尤其用于截图、图片和 OCR |
| `evidence_state` | `unknown` / `single_source` / `corroborated` / `contradicted` | 仅基于 LifeMesh 内部材料判断的证据状态 |
| `claim_quality` | `vague` / `specific` / `verifiable` | claim 本身是否清楚、具体、可验证 |
| `assessment` | `unverified` / `weak` / `plausible` / `supported` / `contradicted` | 由规则派生，供排序、review 和展示使用 |

`assessment` 由规则派生为主，模型只能给建议和理由。第一版不自动联网查证，不做外部事实核查。

示例规则：

- `evidence_state=contradicted` -> `assessment=contradicted`
- `claim_quality=vague` 或 `extraction_confidence=low` -> 最高为 `weak`
- `evidence_state=single_source` 且 claim 具体或可验证 -> `unverified` 或 `plausible`
- `evidence_state=corroborated` 且 extraction 不低 -> `supported`

## Source Envelope

RumorClaim 保存最小 `source_envelope`，不默认保存 raw material：

- `source_adapter`
- `source_item_id`，如果来源侧有稳定 ID
- `captured_at`
- `material_fingerprint`，可选，不可逆摘要，只用于审计和未来排查
- `source_summary`，极短摘要，可脱敏
- `raw_retention`：`none` / `temporary` / `user_saved`
- `processing_run_id`
- `review_pointer`，可选，仅在来源系统可回看时保存指针

`material_fingerprint` 属于 source envelope，不是 RumorClaim 主字段。第一版不做去重或合并，也不因为重复出现而提升可信度。

## Lifecycle

RumorClaim 使用薄状态机：

| 状态 | 含义 |
|---|---|
| `parked` | 通过最低初筛，保留为未验证线索 |
| `reviewed_parked` | 已人工检视并决定继续保留为未验证线索；默认复审列表跳过，但显式请求 rumor lead 时仍可进入 Bundle |
| `candidate_created` | 已生成 Knowledge Candidate，RumorClaim 只作来源线索 |
| `dismissed` | 用户或规则判定无价值，保留最小 tombstone 或统计 |
| `expired` | 到期未复核，默认不再检索或进入 Bundle |

默认过期：

- 普通 parked / reviewed_parked claim：60 天
- 高影响或用户订阅主题：180 天
- `candidate_created`：当前 MVP 仅保留本地 candidate link；完整 Candidate inbox 落地后跟随 Knowledge Candidate 生命周期
- 用户显式 pin/save：不自动过期，但仍是未验证线索

Review queue 使用三类：

- `general_review`
- `conflict_review`
- `sensitive_review`

## Bundle And Promotion

RumorClaim 默认不进入普通 Context Bundle。

只有在任务明确需要未验证线索时，例如用户询问“最近有什么流言、线索或不确定信号”，或调用契约显式设置 `include_unverified=true`，RumorClaim 才能以 `evidence_role=lead` 进入 Bundle。

硬规则：

- RumorClaim 不能作为 `fact` 或 `raw`。
- RumorClaim 不能支撑事实性结论。
- 回答必须标注未验证。
- `assessment=contradicted` 默认只进入 conflict report，不进入可用 slices，除非用户专门查看冲突。
- RumorClaim 只能 promote 到 Knowledge Candidate，不能直接到 Canonical Fact、Memory、Task、Event 或外部动作。当前本地 CLI MVP 的 promote 只创建 `rumor_candidate_links`；完整 Candidate inbox handoff 仍是后续工作。

当 RumorClaim 与 Canonical Fact 冲突时：

- 标记 `evidence_state=contradicted`
- 保存 `conflicts_with_fact_ids[]`
- 进入 `conflict_review`
- 不自动修改 Canonical Fact 的 `validity`
- 只有用户明确复核，或后续多个高质量来源支持，才触发正式 Fact Review

## Source Adapter Policy

后续自动 source adapter 如果要产出 RumorClaim，必须声明 `rumor_policy`：

- 是否允许产出 RumorClaim
- 支持的 material types：`text` / `screenshot` / `image`
- 默认 sensitivity
- `raw_retention`：`none` / `temporary` / `user_saved`
- 默认 relevance scope：项目、联系人、主题或全局
- 是否允许 sensitive auto-save
- 默认过期时间
- 是否允许 dashboard 摘要显示内容

核心 pipeline 统一，但每个来源的风险边界必须可配置。

## Consequences

正向影响：

- 防止自动源把低质材料直接污染 Manual Input、Knowledge Candidate 或 Canonical Fact。
- 保留了“未验证线索”的价值，又不把原始物料默认塞进长期仓库。
- 将多模态输入统一成 claim 级结构，便于后续 review、promote 和 Bundle 消费。
- 高敏流言可以被保留为受控 review 项，但不会默认进入普通 Bundle 或 dashboard 内容展示。

代价：

- 需要新增 RumorClaim 领域文档、CLI contract 和 dashboard 只读状态。
- 需要维护一套轻量 review queue 和过期策略。
- 自动源接入前必须补 `rumor_policy`，source adapter 设计成本增加。

## Alternatives Considered

1. **把 rumor 做成 Manual Input kind**
   - 未选择。`kind` 表达载体或录入类型，rumor 表达未验证材料状态，会污染 Manual Input 分类。

2. **新增完整 Rumor 层**
   - 未选择。会与 Candidate、Fact Review、Bundle lead 和 Source Reference 生命周期重复，第一版过重。

3. **默认保存原始物料**
   - 未选择。原始流言材料通常是污染源和隐私负担；默认只保存结构化抽取结果和最小 source envelope。

4. **RumorClaim 直接复用 Knowledge Candidate**
   - 未选择。自动源会产生大量低质 claim，只有通过初筛和规则门槛后才应该进入 Candidate inbox。

5. **自动联网核查可信度**
   - 未选择。外部事实核查会引入搜索、来源评级、时效和引用体系，第一版只基于 LifeMesh 内部材料判断。

## Implementation Notes And Follow-ups

- 本 ADR 已有本地结构化 CLI MVP：`rumor add/list/show/keep/dismiss/promote/expire`、Bundle lead 准入和 candidate promote 边界。
- 后续自动来源实现前仍必须先声明对应 `rumor_policy`。
- Dashboard 只读展示队列摘要、统计和风险状态，不写回。
- 第 2 阶段以后再评估外部通知、自动 fact-check、系统提醒、任务或日历同步。
