# Access Control

状态：draft
最后更新：2026-07-15
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
- 本机用户通过 LifeMesh Console 发起的短时请求

## Resource

- RawAsset
- ExtractedFact
- CanonicalFact
- SourceReference
- SourceRevision
- ManualInputRecord
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
- CanonicalFact 进入事实性回答前必须通过状态检查：`validity=valid`、`revocation_status=active`、且有 current supporting source reference。source reference 可以是 SourceRevision，也可以是 Manual Input record / extraction。
- 被 Source Tombstone 或 Fact Tombstone 标记的资源不得进入新检索、新 Bundle 或新事实回答。
- LifeMesh Console 第一版只允许 read、search 和非持久化 summarize/bundle assembly；不授予 write、update、delete、export、send 或 execute。
- Console Server 只绑定 `127.0.0.1` 随机端口。首版在只读、前台短时、无 CORS 的边界内不实现 session token；必须严格校验当前 Host 和同源 Origin，且不能把该简化扩展到写操作、常驻服务或外部监听。
- 本机用户在 Console 中拥有 `sensitive` 记录的直接 read 权限；UI 必须显示敏感度标签，但不默认遮罩正文。Sensitive 默认不进入 Bundle，只有用户对本次非持久化组装显式授权后才能加入，且该选择不保存为默认值；UI 直读权限也不代表日志或导出权限。
