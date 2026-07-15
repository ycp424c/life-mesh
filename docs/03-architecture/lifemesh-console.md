# LifeMesh Console

状态：active
最后更新：2026-07-15
职责边界：定义用户侧 LifeMesh Console 的产品边界、读取架构和安全约束；不描述 Project Board，也不改变 Agent 的 CLI + Bundle 交付合同。

## 已确认边界

- LifeMesh Console 是用户查看个人来源、候选、复核项和 Context Bundle 的产品界面。
- `dashboard/` 继续作为 docs-derived Project Board；两者不合并。
- 第一版连接真实本地数据，但保持只读：允许 read、search、filter 和非持久化 Bundle assembly，不提供 add、update、dismiss、promote、revoke、delete 或 confirm。
- Console 使用按需启动的本地前台服务，只绑定 `127.0.0.1` 的随机可用端口；命令结束时服务关闭，不绑定 `0.0.0.0`、LAN 或公网，也不作为后台 daemon。
- Console Server 是 UI adapter，不是 Agent API。Agent 继续通过 CLI + JSON Bundle + skill 使用 LifeMesh。
- 浏览器不直接打开 `~/.lifemesh/lifemesh.db`；Console Server 复用 LifeMesh read-side application logic，并返回最小必要字段。
- 第一版不实现 session token 或登录流程；服务严格校验当前 `127.0.0.1:<port>` Host、不启用 CORS，需要请求体的端点只接受同源 Origin。该简化不得扩展到写操作、常驻服务或外部监听。
- Console 不因记录标记为 `sensitive` 而默认遮罩正文，也不增加二次点击解锁。列表可以因版面截断摘要，详情视图直接展示完整可读内容；所有记录仍必须持续显示敏感度标签，避免用户误判内容性质。
- Context Bundle Explorer 默认排除 `sensitive` 内容。用户可以在本次组装中主动勾选加入；该授权只作用于当前非持久化 Bundle，不保存为后续默认值。

## 当前运行时约束

Unified Write Model 尚未实现，当前 Manual Input、RumorClaim 和 Candidate 仍由各自 store 管理。Console 第一版只能读取当前 runtime truth；不得为了 UI 方便新增 legacy 写旁路或把 target schema 伪装成已实现。

## 当前实现

- 前端源码位于 `console/`，使用 React、TypeScript、Vite、Tailwind CSS 和 shadcn/ui；生产构建产物写入 `lifemesh/console_ui/`，因此运行 Console 时不依赖 Node.js。
- `lifemesh console` 启动 Python 标准库 `ThreadingHTTPServer`；默认使用随机端口，也可在本地开发时显式指定端口。进程只监听 `127.0.0.1`，`Ctrl-C` 后关闭。
- `lifemesh/console_service.py` 复用现有 Manual Input、RumorClaim、Candidate、Obsidian Retriever 和 BundleAssembler，提供总览、分域记录、详情、搜索、图谱、时间线和非持久化 Bundle 组装。
- Console Server 只提供 `GET /api/overview`、`GET /api/records`、`GET /api/records/<domain>/<id>`、`GET /api/search`、`GET /api/graph`、`GET /api/timeline` 和 `POST /api/bundles`；没有持久化写接口。
- HTTP 层已实现严格 Host、同源 Origin、无 CORS、64 KiB 请求体上限、`no-store`、CSP、禁止嵌入和不记录查询字符串。
- 自动化测试覆盖真实本地 store 读取、跨域搜索、真实关系图谱、时间线、Sensitive 直读与 Bundle 准入、静态资源、安全响应头、错误 Host/Origin 拒绝和同源 Bundle 请求。
- 视觉语言以暖琥珀表达人的活动与记忆、萌芽绿表达生长中的知识、深蓝紫表达未知边界、冷静灰蓝表达证据与理性；默认深色、宽屏侧栏、窄屏抽屉式导航。

## 首版能力

- 总览工作台作为默认首屏：提供跨领域全局搜索、数据源与索引健康、近期记录，以及 Manual Input、RumorClaim、Candidate 等队列摘要。
- Manual Input 浏览与搜索。
- RumorClaim 队列、状态和来源摘要。
- Candidate Inbox 浏览。
- Context Bundle Explorer：输入任务、选择来源和 sensitivity cap，查看 slices、引用、排除项与 assembly report；结果默认不落盘。
- 只读 provenance、audit 和 freshness 状态查看。
- Knowledge Graph 与 Timeline 是独立导航视图，不占据默认首屏。图谱只展示运行时已有的 source reference、entity/relation mention、promotion link 等真实关系；不得为了视觉连贯推断或补造边。

## 信息架构

```text
Overview Workbench
  - Global Search
  - Data / Index Health
  - Recent Records
  - Queue Summaries

Browse
  - Manual Inputs
  - RumorClaims
  - Candidates

Explore
  - Bundle Explorer
  - Knowledge Graph
  - Timeline
  - Provenance / Audit / Freshness
```

全局搜索是首屏和各领域页面的共同入口；结果必须标明所属领域、状态、敏感度和来源，不把不同运行时对象伪装成统一 schema。

## 后续边界

- 在 Unified Write Model 落地前，不增加 Candidate confirm、RumorClaim review 或任何其他持久化写操作。
- 如需常驻进程、LAN/public 监听、外部端口或写操作，必须重新评估认证、CSRF、会话生命周期和审计，而不是沿用当前无登录设计。
- 真实个人数据规模下的长期性能、图谱密度和信息分层仍需通过持续使用验证。

## 正式来源

- [ADR-0006 Context Bundle as Artifact, Not Server](../05-decisions/ADR-0006-bundle-as-artifact-not-server.md)
- [ADR-0011 Local Loopback Console Server](../05-decisions/ADR-0011-local-loopback-console-server.md)
- [Agent Access Layer](agent-access-layer.md)
