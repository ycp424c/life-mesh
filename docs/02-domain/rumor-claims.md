# Rumor Claims

状态：draft
最后更新：2026-07-09
职责边界：定义 LifeMesh 如何处理可信度未知的自动来源材料，尤其是文字片段、截图和图片中抽取出的未验证 claim。当前覆盖本地结构化 CLI MVP；不定义自动 source adapter、外部事实核查，不把原始流言材料默认长期保存。

## 定位

RumorClaim 是 source-neutral 的未验证 claim 契约。它不是新的架构层，也不是 Manual Input 的 `kind`。

```text
incoming material
  -> temporary parsing sandbox
  -> RumorClaim extraction
  -> relevance / impact / credibility triage
  -> parked / reviewed_parked / dismissed / expired
  -> optional Knowledge Candidate
```

RumorClaim 的主资产是从材料中抽取出的 claim、entity mentions 和 relation mentions。原始文本、截图或图片默认只作为临时处理输入，不长期保存；需要保留时必须由用户显式保存或由 source adapter 的 `rumor_policy` 声明允许。

## 非目标

- 不把 rumor 建成独立事实层。
- 不把 rumor 作为 Manual Input kind。
- 不把 RumorClaim 当作 Knowledge Candidate、Canonical Fact、Memory、Task 或 Event。
- 不默认保存完整原始物料。
- 不自动联网核查。
- 不自动触发外部提醒、任务、日历或执行动作。
- 不做第一版去重、合并或来源融合。

## 最小字段

| 字段 | 说明 |
|---|---|
| `claim_text` | 抽取出的未验证陈述 |
| `claim_type` | claim 形态 |
| `entity_mentions[]` | 从 claim 中识别出的实体 mention，不直接写正式图谱 |
| `relation_mentions[]` | 从 claim 中识别出的关系 mention，不直接写正式图谱 |
| `user_relevance` | 与用户、项目、联系人、计划或资产的相关性 |
| `relevance_reason` | 相关性判断的简短解释 |
| `impact` | 可能影响用户判断或行动的程度 |
| `impact_reason` | 影响判断的简短解释 |
| `extraction_confidence` | 系统是否读懂原始材料 |
| `evidence_state` | 基于 LifeMesh 内部材料的证据状态 |
| `claim_quality` | claim 是否清楚、具体、可验证 |
| `assessment` | 规则派生的展示和排序标签 |
| `status` | RumorClaim 生命周期状态 |
| `expires_at` | 过期时间 |
| `review_queue` | review 队列类型 |
| `sensitivity` | 敏感级别 |
| `source_envelope` | 最小来源外壳，不含默认 raw material |

## Claim Type

`claim_type` 不直接复用 Knowledge Candidate 类型，但保持可映射：

| claim_type | 说明 | 可映射到 |
|---|---|---|
| `factual_claim` | 事实性陈述 | `fact` |
| `relationship_claim` | 人、项目、组织、地点、资产之间的关系 | `relationship` |
| `intent_or_plan_claim` | 疑似计划、意图、安排或后续动作 | `task`、`decision` 或 `fact` |
| `risk_claim` | 潜在风险、异常、负面变化或预警 | `fact` 或 `task` |
| `preference_claim` | 疑似偏好、倾向或判断标准 | `preference` |
| `unknown_claim` | 暂时无法归类 | 不自动 promote |

## Mentions

第一版只保存 mentions，不写正式 Entity / Relation 图谱：

- `entity_mentions[]`：人、项目、组织、地点、产品、文件、资产等 mention。
- `relation_mentions[]`：例如 `person works_on project`、`project depends_on vendor`。
- `entity_link_candidates[]` 可作为后续扩展，指向已有 canonical entity 的候选链接。

只有通过确认或策略接受后，相关内容才进入正式 Entity / Relation / Canonical Fact 或 Memory。

## Relevance And Impact

`user_relevance` 取值：

- `none`
- `low`
- `medium`
- `high`

`impact` 取值：

- `low`
- `medium`
- `high`
- `critical`

默认持久化门槛：

```text
user_relevance >= medium OR impact >= high
```

相关性和潜在影响优先决定是否保存；可信度决定保存后的使用方式。

## Credibility

第一版可信度由三个维度和一个派生标签表达：

| 字段 | 取值 |
|---|---|
| `extraction_confidence` | `low` / `medium` / `high` |
| `evidence_state` | `unknown` / `single_source` / `corroborated` / `contradicted` |
| `claim_quality` | `vague` / `specific` / `verifiable` |
| `assessment` | `unverified` / `weak` / `plausible` / `supported` / `contradicted` |

`evidence_state` 第一版只基于 LifeMesh 内部材料判断，不自动联网查证。

`assessment` 由规则派生为主，模型只能给建议和理由。默认起点是 `unverified`。

## Source Envelope

`source_envelope` 是审计外壳，不是原始物料归档：

| 字段 | 说明 |
|---|---|
| `source_adapter` | 来源 adapter |
| `source_item_id` | 来源侧稳定 ID，如有 |
| `captured_at` | 捕获时间 |
| `material_fingerprint` | 可选不可逆摘要，不参与第一版去重策略 |
| `source_summary` | 极短脱敏摘要 |
| `raw_retention` | `none` / `temporary` / `user_saved` |
| `processing_run_id` | 本次处理运行 ID |
| `review_pointer` | 可选来源回看指针 |

`material_fingerprint` 属于 source envelope，不是 RumorClaim 主字段。第一版不做自动去重、合并或重复次数可信度提升。

## Lifecycle

| 状态 | 说明 |
|---|---|
| `parked` | 通过最低初筛，保留为未验证线索 |
| `reviewed_parked` | 已人工检视并决定继续保留为未验证线索；默认复审列表跳过，但显式请求 rumor lead 时仍可进入 Bundle |
| `candidate_created` | 已在统一 inbox 生成 Knowledge Candidate |
| `dismissed` | 用户或规则判定无价值 |
| `expired` | 到期未复核，默认不再检索或进入 Bundle |

默认过期：

- 普通 `parked` / `reviewed_parked`：60 天
- 高影响或用户订阅主题：180 天
- `candidate_created`：已生成统一 pending Candidate，后续跟随 Knowledge Candidate 生命周期
- 用户显式 pin/save：不自动过期，但仍是未验证线索

Review queue：

- `general_review`
- `conflict_review`
- `sensitive_review`

## Bundle Admission

RumorClaim 默认不进入普通 Context Bundle。只有任务明确请求未验证线索，或 CLI / contract 显式设置 `include_unverified=true` 时，才可作为 `evidence_role=lead` 进入。

约束：

- 不作为 `fact`。
- 不作为 `raw`。
- 不支撑事实性结论。
- 回答必须标注未验证。
- `assessment=contradicted` 默认只进 conflict report，除非用户专门查看冲突。
- 高敏 RumorClaim 默认不进入 Bundle；只有用户显式提高 sensitivity cap 或进入 sensitive review 时展示。

## Promotion

RumorClaim 只能 promote 到 Knowledge Candidate。当前 CLI 通过 `KnowledgeWorkflow` 创建统一 pending Candidate、normalized source link 和 audit，并把 RumorClaim 标记为 `candidate_created`；不再新增 legacy `rumor_candidate_links`。

```text
RumorClaim -> Knowledge Candidate -> User Confirmation / policy -> Canonical Fact / Memory / Task
```

不得直接 promote 到 Canonical Fact、Memory、Task、Event 或外部动作。用户明确要求把某条流言做成待办或记忆时，也应先创建 Knowledge Candidate，再走现有确认路径。

## Conflict Handling

如果 RumorClaim 与已有 Canonical Fact 冲突：

- 设置 `evidence_state=contradicted`
- 设置 `assessment=contradicted`
- 记录 `conflicts_with_fact_ids[]`
- 进入 `conflict_review`
- 不自动修改 Canonical Fact `validity`

只有用户明确复核，或后续多个高质量来源支持，才触发正式 Fact Review。

## Source Adapter Rumor Policy

每个可能产出 RumorClaim 的 source adapter 必须声明 `rumor_policy`：

- 是否允许产出 RumorClaim
- 支持的 material types：`text` / `screenshot` / `image`
- 默认 sensitivity
- `raw_retention`
- 默认 relevance scope
- 是否允许 sensitive auto-save
- 默认过期时间
- 是否允许 dashboard 摘要显示内容

## CLI And Dashboard Contract

当前 CLI 已实现结构化 RumorClaim MVP：

```bash
lifemesh rumor add \
  --claim-text "..." \
  --claim-type factual_claim|relationship_claim|intent_or_plan_claim|risk_claim|preference_claim|unknown_claim \
  --user-relevance none|low|medium|high \
  --impact low|medium|high|critical \
  [--entity-mention "..."] \
  [--relation-mention "..."] \
  [--source-adapter <name>] \
  [--raw-retention none|temporary|user_saved]

lifemesh rumor list \
  [--queue general_review|conflict_review|sensitive_review] \
  [--status parked|reviewed_parked|candidate_created|dismissed|expired]

lifemesh rumor show <rumor-claim-id>
lifemesh rumor keep <rumor-claim-id> [--reason "..."]
lifemesh rumor dismiss <rumor-claim-id>
lifemesh rumor promote <rumor-claim-id> --to candidate
lifemesh rumor expire <rumor-claim-id>

lifemesh bundle "<task>" --source rumor
lifemesh bundle "<task>" --source all --include-unverified
```

Dashboard 只读展示队列摘要、数量、最近高影响 claims、过期/丢弃统计和规则版本。Dashboard 不写回。

## Phase Boundary

RumorClaim 是 Phase 1 follow-on milestone。当前已实现本地结构化 CLI MVP：保存通过初筛的 claim、mentions、最小 source envelope 和审计事件；默认不进普通 Bundle，显式包含时只作为 `lead`；只允许 promote 到 Knowledge Candidate。

尚未实现：自动 source adapter、截图/图片自动抽取、来源融合、外部通知、系统提醒、任务/日历同步、review UI 和自动 fact-check。这些能力属于后续阶段或独立 ADR。
