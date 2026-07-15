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

Unified Write Model 已实现并完成真实库迁移。Manual Input、RumorClaim 保留来源领域 store，Candidate handoff、Acceptance、Canonical Object、review 与 provenance 由统一 database/workflow 管理。Console 已增加 Canonical Object 与 Open Review 只读专页；Review 详情组合触发来源和目标 Object/Candidate，但不得为了 UI 方便新增写旁路。

## 当前实现

- 前端源码位于 `console/`，使用 React、TypeScript、Vite、Tailwind CSS 和 shadcn/ui；生产构建产物写入 `lifemesh/console_ui/`，因此运行 Console 时不依赖 Node.js。
- `lifemesh console` 启动 Python 标准库 `ThreadingHTTPServer`；默认使用随机端口，也可在本地开发时显式指定端口。进程只监听 `127.0.0.1`，`Ctrl-C` 后关闭。
- `lifemesh/console_service.py` 复用现有 Manual Input、RumorClaim、Candidate、Canonical Store、Obsidian Retriever 和 BundleAssembler，提供总览、分域记录、详情、搜索、图谱、时间线和非持久化 Bundle 组装。
- Console 注入的领域 Store 统一使用数据库只读连接：SQLite 以 `mode=ro` 打开并启用 `query_only`，不执行 schema 初始化、migration、元数据更新或权限改写。未初始化的 `LIFEMESH_HOME` 返回空状态，不创建数据库和 `.database.lock`。
- `GET /api/records` 与详情路由支持 `inputs`、`rumors`、`candidates`、`objects`、`reviews` 五个运行时域；Review 列表只返回 open 状态，详情带目标和触发 Source Reference。
- Console Server 只提供 `GET /api/overview`、`GET /api/records`、`GET /api/records/<domain>/<id>`、`GET /api/search`、`GET /api/graph`、`GET /api/timeline` 和 `POST /api/bundles`；没有持久化写接口。
- 全局搜索走本地 FTS 与结构化文本匹配，不同步调用 embedding；语义检索仍由 Bundle Explorer 复用正式 retrieval path，避免浏览操作被本地模型延迟阻塞。
- HTTP 层已实现严格 Host、同源 Origin、无 CORS、64 KiB 请求体上限、`no-store`、CSP、禁止嵌入和不记录查询字符串。
- 自动化测试覆盖真实本地 store 读取、Canonical Object/Review 上下文、跨域搜索、真实关系图谱、时间线、Sensitive 直读与 Bundle 准入、静态资源、安全响应头、错误 Host/Origin 拒绝、同源 Bundle 请求，以及读取前后数据库 `data_version`/元数据不变和空 HOME 不产生数据库/锁文件。
- 2026-07-15 初始真实规模基线使用 141 条可见记录：180 次、8 并发混合读请求全部成功且数据库/总 FD 零增长；发现并移除全局搜索的同步 embedding 后，单用户搜索 p95 从约 3.96 秒降至 52.9ms，8 并发 p95 为 350.7ms。真实数据库一致性快照上的 Input → Fact → source stale → Open Review 级联与 integrity check 均通过，原库未写入测试记录。
- 视觉语言以暖琥珀表达人的活动与记忆、萌芽绿表达生长中的知识、深蓝紫表达未知边界、冷静灰蓝表达证据与理性；默认深色、宽屏侧栏、窄屏抽屉式导航。

## 首版能力

- 总览工作台作为默认首屏：提供跨领域全局搜索、数据源与索引健康、近期记录，以及 Manual Input、RumorClaim、Candidate 等队列摘要。
- Manual Input 浏览与搜索。
- RumorClaim 队列、状态和来源摘要。
- Candidate Inbox 浏览。
- Canonical Object 浏览：统一展示 Fact、Memory、Task 与 Event 的状态、Acceptance、provenance、review history 和 tombstone。
- Open Review 浏览：只列未关闭复核项，详情并列展示触发来源和目标 Object/Candidate；不提供 resolve 操作。
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
  - Canonical Objects
  - Open Reviews

Explore
  - Bundle Explorer
  - Knowledge Graph
  - Timeline
  - Provenance / Audit / Freshness
```

全局搜索是首屏和各领域页面的共同入口；结果必须标明所属领域、状态、敏感度和来源，不把不同运行时对象伪装成统一 schema。它以快速、确定的 FTS/结构化文本匹配为职责，不替代 Bundle Explorer 的语义 retrieval。

## 后续边界

- Unified Write Model 已落地，但 Console 仍不增加 Candidate confirm、RumorClaim review 或任何其他持久化写操作；写回能力需要独立产品与安全决策。
- 如需常驻进程、LAN/public 监听、外部端口或写操作，必须重新评估认证、CSRF、会话生命周期和审计，而不是沿用当前无登录设计。
- 已建立 141 条可见记录的首轮性能与连接基线；更长期的数据增长、图谱密度和详情信息分层仍需通过持续使用验证。

## 正式来源

- [ADR-0006 Context Bundle as Artifact, Not Server](../05-decisions/ADR-0006-bundle-as-artifact-not-server.md)
- [ADR-0011 Local Loopback Console Server](../05-decisions/ADR-0011-local-loopback-console-server.md)
- [Agent Access Layer](agent-access-layer.md)
