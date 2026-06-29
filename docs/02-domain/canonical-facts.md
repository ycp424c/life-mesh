# Canonical Facts

状态：draft
最后更新：2026-06-29
职责边界：定义 Canonical Fact 的生成路径、必备字段和撤销边界。

## 定位

Canonical Fact 是 LifeMesh 已核实、可追溯、可撤销，并可在 Context Bundle 中复用的事实。

它不是：

- 未处理的 Knowledge Candidate
- 长期偏好或用户画像
- 普通搜索结果
- 不带来源的 LLM 总结

## 第一版生成路径

第一版只允许三条路径生成 Canonical Fact：

1. 用户显式确认 Knowledge Candidate。
2. 用户手动创建事实。
3. 低风险策略自动接受。

低风险策略自动接受只适用于非常明确、非画像、非关系推断的事实，例如：

- 某篇笔记标题是 X。
- 某个文件在某路径下。
- 某个 Source Revision 的 hash 是 Y。

以下内容第一版不得自动接受为 Canonical Fact：

- 用户偏好
- 人际关系
- 任务承诺
- 决策理由
- 健康、金融、位置等高敏事实

## 必备字段

每条 Canonical Fact 至少应包含：

- `statement`
- `source_revisions[]`
- `accepted_by`
- `accepted_at`
- `acceptance_path`
- `confidence`
- `risk`
- `validity`
- `revocation_status`
- `review_reason`，可选
- `review_started_at`，可选
- `reviewed_at`，可选
- `superseded_by`，可选

## 生命周期

```text
Knowledge Candidate
  -> transient / inbox / confirm_required / discard
  -> User Confirmation 或低风险策略接受
  -> Canonical Fact
```

用户手动创建的 Canonical Fact 可以没有 Knowledge Candidate 前身，但仍应尽量绑定来源或标记为 user_asserted。

## 进入 Context Bundle

Canonical Fact 可以作为 Context Bundle 的高优先级来源，但必须带上：

- provenance
- validity
- revocation_status
- risk
- source freshness

只有同时满足以下条件的 Canonical Fact 才能作为 `evidence_role=fact` 进入 `slices[]`：

- `validity=valid`
- `revocation_status=active`
- 至少有一个 current supporting Source Revision

其他状态只能进入 `freshness_report` 或 `excluded_sources`，不能作为事实证据。

## 复核与撤销

Source Revision 变为 stale / missing / revoked 时，Canonical Fact 不立即删除。默认处理为：

1. 如果必要来源失效且没有其他 current supporting revision，设置 `validity=needs_review`，保留 `revocation_status=active`。
2. 如果来源被删除、移出索引范围或授权撤销，生成 Source Tombstone，并触发依赖事实复核。
3. `needs_review` 的事实不进入可用 Bundle，只进入报告区，提示用户或后续策略复核。

复核动作：

| 动作 | 结果 |
|---|---|
| `revalidate` | 绑定 current Source Revision，恢复 `valid` |
| `revise` | 生成新的 Canonical Fact，旧 fact 标记 `superseded` |
| `invalidate` | 标记 `validity=invalid` |
| `revoke` | 设置 `revocation_status=revoked`，生成 Fact Tombstone |

撤销和失效都必须保留审计链，不直接删除历史 fact。Fact Tombstone 阻止旧事实进入新 Bundle，但仍允许旧回答解释当时使用过什么事实。
