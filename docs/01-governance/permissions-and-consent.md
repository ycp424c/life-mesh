# Permissions And Consent

状态：draft
最后更新：2026-06-29
职责边界：定义 Agent、工具、连接器访问数据和执行动作的授权模型。

## 授权应覆盖的范围

- 哪个主体：用户、Agent、连接器、外部服务。
- 哪类数据：文档、任务、日历、联系人、记忆、交易、健康等。
- 哪些动作：读取、搜索、摘要、写入、更新、删除、外部发送。
- 哪个时间范围：单次、会话、项目周期、长期。
- 哪个上下文：某项目、某任务、某人际关系、某数据源。

## 默认授权原则

- 默认拒绝，按任务授权。
- 读权限和写权限分开。
- 查询权限和批量导出权限分开。
- 高敏感数据只读也需要审计。
- 自动执行动作必须有单独授权。
- Agent 自动捕获非高敏个人相关信息到 Manual Input Inbox 是允许的，但必须透明说明，且不能自动 promote；明显高敏信息必须由用户明确提交。
- `auto_captured` 记录默认只作为未复核 lead，不能被当作事实、任务、日程或长期记忆。
- Promote 到 Task、Event、Memory、Canonical Fact 或 Knowledge Candidate 需要用户明确确认。

## 撤销与过期

每个授权都应能：

- 查看当前状态。
- 暂停或撤销。
- 到期自动失效。
- 解释最近一次使用记录。
- 关联产生的派生数据和长期记忆。
- 生成 Source Tombstone，使被撤销来源不再被新检索或 Context Bundle 使用。
- 触发依赖 Canonical Fact 的复核；不能让已撤销来源继续支撑事实回答。

## Manual Input 权限边界

- `input add --auto-captured` 可由 Agent 对非高敏信息自主调用，但回复必须包含 id、kind、摘要、sensitivity 和 Bundle 可用性。
- `input update`、`input revoke`、`input delete` 和 `input promote` 需要用户明确指令。
- `Sensitive` input 默认不进入 Bundle；只有用户显式提高 sensitivity cap 时才可用。
- 本地 embedding 和 VLM extraction 默认走本机 LM Studio；远程 provider 必须单独 opt-in。
