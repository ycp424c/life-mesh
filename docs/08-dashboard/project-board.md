# Project Board

状态：active
最后更新：2026-06-26
职责边界：定义 LifeMesh Web 项目看板的用途、数据来源和同步维护规则。

## 入口

- 页面：`dashboard/index.html`
- 数据：`dashboard/project-state.js`
- 样式：`dashboard/styles.css`
- 渲染逻辑：`dashboard/app.js`

当前看板是静态 Web 页面，可直接用浏览器打开，不需要构建工具或本地服务。

## 看板职责

看板用于持续可视化跟踪：

- 当前项目状态
- 当前工作重点
- 渐进式路线图
- 高层架构
- 数据源规划
- Agent 能力规划
- 文档健康度
- 风险和治理重点
- ADR 决策状态
- 开放问题和最近变更
- 下一步同步检查清单

## 数据来源

看板不应成为唯一事实来源。它应从这些文档提炼状态：

- 产品方向：`docs/00-vision/`
- 治理和风险：`docs/01-governance/`
- 领域模型：`docs/02-domain/`
- 架构：`docs/03-architecture/`
- 路线图：`docs/04-roadmap/`
- 决策：`docs/05-decisions/`
- 安全：`docs/07-security/`

## 必须同步更新的场景

- 路线图阶段状态变化。
- 新增或完成里程碑。
- 新增、修改或关闭风险。
- 新增 ADR。
- 架构层级、数据流或 Agent 接入边界变化。
- 文档新增、重命名、归档或状态变化。
- 当前工作重点变化。

## 维护原则

- 看板展示的是当前事实，不展示未确认愿望。
- 长期事实以 `docs/**` 和 ADR 为准；看板只是可视化入口。
- 不确定状态必须标记为 `Needs review`。
- 页面内容变化应优先改 `dashboard/project-state.js`，结构变化才改 HTML/CSS/JS。
- 每次交付前必须确认看板和文档没有冲突。
