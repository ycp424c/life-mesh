# ADR-0011：本机回环 LifeMesh Console Server

状态：accepted
日期：2026-07-15

## 背景

ADR-0006 将 Agent 的交付界面限定为 CLI + JSON Bundle，并拒绝 MCP 或长期运行的 Agent Server。实时 LifeMesh Console 仍需要一个可信进程读取本地 SQLite 状态、调用既有读侧应用逻辑，并组装临时 Context Bundle；静态快照无法提供实时搜索，而让浏览器直接打开 SQLite 会削弱文件和数据边界。

## 决策

LifeMesh 可以提供按需启动、只读的 Console Server；用户使用 LifeMesh Console 时，它只绑定 `127.0.0.1` 的随机可用端口，并以前台短时进程运行。它是用户界面适配器，不是 Agent API：不替代 CLI + Bundle，不暴露 MCP，不绑定局域网或公网地址，不作为后台守护进程运行，首版也不提供持久化写入接口。LifeMesh Console 与静态 Project Board 保持为两个独立界面。

首版不实现 session token 或登录流程。该取舍只在以下约束同时成立时有效：严格校验请求 `Host` 为当前 `127.0.0.1:<port>`、不启用 CORS、需要请求体的端点校验同源 `Origin`、响应和日志不泄露数据库路径或额外敏感字段。任一约束放宽，或 Console 增加写操作、后台常驻、LAN/public 监听时，必须重新设计身份认证与 CSRF 防护。

Console 对本机用户直接展示记录正文，不因 `sensitive` 分类增加默认遮罩或二次解锁；敏感度标签始终可见。列表因版面产生的普通文本截断不属于安全遮罩。

UI 直读权限不自动传递给 Agent：Context Bundle Explorer 默认排除 `sensitive` 内容，只有用户在本次组装中主动选择后才纳入，且不持久化这项选择。

## 影响

Console 可以查询当前本地状态并组装非持久化 Bundle，无需让浏览器直接打开私有数据库文件。首版省去 token 兑换、cookie 生命周期和内容解锁交互，降低实现与使用复杂度；代价是安全性依赖短时进程、严格回环监听、Host/Origin 校验、浏览器同源策略以及用户对本机屏幕环境的控制。Sensitive Bundle 必须逐次显式选择；实现不记录请求路径或查询字符串，前台进程在 `Ctrl-C` 后关闭。

## 备选方案

- 导出静态 HTML/JSON 快照：更安全、更简单，但不是实时数据，也无法支持面向任务的交互。
- 浏览器侧 SQLite/WASM：避免 HTTP 进程，但会把私有数据库访问移入浏览器代码，也无法清晰复用 LifeMesh 读侧逻辑。
