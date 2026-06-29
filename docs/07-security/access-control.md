# Access Control

状态：draft
最后更新：2026-06-29
职责边界：定义 LifeMesh 权限判断所需的主体、资源、动作和上下文维度。

## 权限四元组

```text
subject + resource + action + context -> decision
```

## Subject

- 用户
- Agent
- 连接器
- 外部工具
- 自动化任务

## Resource

- RawAsset
- ExtractedFact
- CanonicalFact
- SourceRevision
- Memory
- Event
- Task
- Contact
- ConsentGrant
- AuditEvent

## Action

- read
- search
- summarize
- write
- update
- delete
- export
- send
- execute

## Context

- 当前任务
- 当前项目
- 数据敏感级别
- 授权时间范围
- Agent 类型
- 是否外发
- 是否可撤销

## 策略要求

- 写权限不继承读权限。
- 导出权限不继承搜索权限。
- 高敏资源需要额外确认。
- 自动化任务不能默认继承用户全量权限。
- 权限决策要能解释给用户。
- CanonicalFact 进入事实性回答前必须通过状态检查：`validity=valid`、`revocation_status=active`、且有 current supporting Source Revision。
- 被 Source Tombstone 或 Fact Tombstone 标记的资源不得进入新检索、新 Bundle 或新事实回答。
