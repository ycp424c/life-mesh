# LifeMesh Project Board

静态 Web 项目看板，用于可视化跟踪 LifeMesh 的进度、规划、架构、文档健康、风险和决策。

它不是读取真实个人数据的 LifeMesh Console。两者的职责边界见 `docs/03-architecture/lifemesh-console.md`：Project Board 继续保持静态、文档派生；Console 是独立实现的本机只读产品界面。

## 打开方式

直接用浏览器打开：

```text
dashboard/index.html
```

## 维护方式

- 常规内容更新：修改 `dashboard/project-state.js`。
- 页面结构更新：修改 `dashboard/index.html` 和 `dashboard/app.js`。
- 视觉样式更新：修改 `dashboard/styles.css`。
- 规则变化：同步更新 `docs/08-dashboard/project-board.md` 和 `AGENTS.md`。
