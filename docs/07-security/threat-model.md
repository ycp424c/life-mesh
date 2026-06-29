# Threat Model

状态：draft
最后更新：2026-06-29
职责边界：识别 LifeMesh 的主要安全威胁，并记录初始缓解策略。

## 主要威胁

| 威胁 | 说明 | 初始缓解策略 |
|---|---|---|
| 越权访问 | Agent 或连接器读取超出任务范围的数据 | 最小权限、按任务授权、审计 |
| Prompt Injection | 文档或网页内容诱导 Agent 泄露数据或调用工具 | 工具隔离、上下文标注、外部内容降权 |
| 记忆污染 | 错误、恶意或过期信息进入长期记忆 | 来源、置信度、确认、过期、可删除 |
| 工具滥用 | Agent 调用写入、外发或执行类工具造成损失 | 能力分级、人工确认、限流 |
| 敏感上下文外泄 | 高敏数据进入模型上下文或日志 | 分类隔离、本地优先、脱敏、审计 |
| 溯源断裂 | 派生事实无法追到来源 | provenance 必填、删除级联 |
| 授权遗留 | 已撤销授权仍被缓存或索引使用 | 授权状态检查、缓存清理、过期机制 |
| 过期事实复用 | 依赖 stale / missing / revoked 来源的 Canonical Fact 继续进入回答 | Fact Review、tombstone、Bundle 准入检查 |
| Agent 沉默记忆 | Agent 自动把对话内容写入 Inbox 而用户不知情 | 自动捕获后必须透明说明记录 id、kind、摘要、sensitivity 和 Bundle 可用性 |
| 本地 VLM 误读截图 | OCR/VLM 将截图误解为事实、日程或任务 | extraction 不等于 fact；promote 需要用户确认；记录 provider/model/confidence |
| 本地库文件泄露 | SQLite、raw assets 或 embeddings 被未授权读取 | `~/.lifemesh` 0700，数据库和 assets 0600；后续评估加密 |

## 早期默认防线

- 先只接入低风险高价值数据。
- 高敏感数据后置。
- Agent 只通过工具接口访问数据。
- 写入长期记忆需要来源。
- Agent 自动捕获只适用于非高敏信息，只进 Manual Input Inbox，不能自动 promote。
- Sensitive 可本地记录，但默认不进普通 Bundle。
- embedding 和截图 VLM 默认使用本机 LM Studio，不默认远程发送。
- 高风险动作必须确认。
- 所有工具调用都生成审计事件。

## 待建模场景

- 恶意 PDF 要求 Agent 忽略权限。
- 日历事件里嵌入外泄指令。
- 联系人备注被错误推断并长期影响 Agent。
- 撤销某个数据源后，旧向量索引仍返回相关片段。
- Source Revision stale 或 Manual Input revoked/deleted 后，旧 Canonical Fact 未进入复核而继续支撑新回答。
- Agent 自动捕获 Sensitive 内容后，被默认 Bundle 召回。
- LM Studio 未启动、模型未加载或 embedding 维度变化导致索引不一致。
- 多个 Agent 共享同一记忆导致权限混淆。
