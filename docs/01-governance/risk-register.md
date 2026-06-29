# Risk Register

状态：draft
最后更新：2026-06-29
职责边界：记录 LifeMesh 的主要风险、影响、缓解策略和待决问题。

| 风险 | 影响 | 初始缓解策略 | 状态 |
|---|---|---|---|
| Agent 过度访问个人数据 | 隐私泄露、错误推断 | 最小权限、审计、按任务授权 | open |
| 推断记忆错误 | 长期行为偏移 | 置信度、确认、可编辑、可删除 | open |
| 高敏感数据过早接入 | 安全与合规风险 | 高敏数据源路线图后置；用户显式 Sensitive input 本地隔离、默认不进 Bundle | open |
| 原始数据和派生事实断链 | 无法解释来源 | 每个事实保存 provenance | open |
| 过期事实继续复用 | Agent 基于 stale、missing 或已撤销来源给出错误事实回答 | Fact Review、Source Tombstone、Fact Tombstone、Bundle 准入检查 | open |
| 自动执行不可逆动作 | 数据损失或外部承诺 | 风险分级、人工确认、撤销机制 | open |
| 只做向量库导致语义混乱 | Agent 找得到但不可信 | 多层数据模型：原始、结构化、索引、图谱、时间线 | open |
| Agent 自动捕获造成沉默记忆 | 用户不知道哪些对话内容被记录 | 每次自动捕获必须回复 id、kind、摘要、sensitivity、Bundle 可用性；默认仅进 Inbox | open |
| 本地模型误读截图 | VLM/OCR 抽取错误进入长期层 | extraction 带 provider/model/confidence；promote 必须用户确认 | open |
| 本地个人数据库泄露 | `~/.lifemesh` 被其他进程或备份读取 | 目录 0700、数据库和 raw asset 0600；后续评估加密 | open |
| 看板与文档状态漂移 | 误导规划、架构或治理判断 | AGENTS.md 强制同步，看板以 docs 和 ADR 为事实源 | open |
