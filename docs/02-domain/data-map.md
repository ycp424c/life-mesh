# Personal Data Map

状态：draft
最后更新：2026-06-30
职责边界：定义 LifeMesh 管理的个人数据类型、优先级和接入顺序。

## 数据类型

| 数据类型 | 例子 | 对 Agent 的价值 | 初始优先级 | 风险 |
|---|---|---:|---:|---:|
| 身份与偏好 | 个人资料、语言偏好、沟通风格、长期目标 | 让 Agent 更懂用户 | 高 | 中 |
| 时间与承诺 | 日历、任务、会议、DDL、约定 | 规划、提醒、排序 | 最高 | 中 |
| 手动输入 | 截图、手动日程、心情记录、活动记录、待办、临时备注 | 补齐自动数据源缺口，验证本地检索和 Bundle 使用闭环 | 最高 | 中到高 |
| 人际关系 | 联系人、家庭成员、同事、客户、关系备注 | 理解语境 | 高 | 高 |
| 知识资产 | 笔记、文档、邮件、合同、论文、项目资料 | 检索和复用知识 | 最高 | 中到高 |
| 行为与交易 | 消费、运动、浏览、出行、位置、健康数据 | 模式分析 | 中高 | 高 |
| 决策记录 | 购买、拒绝、选择方案的原因 | 学习判断标准 | 高 | 中 |

## 初始接入建议

首个验证适配器：

- Obsidian Vault：`/Users/justynchen/Documents/docs/obsidian-default`

定位：

- Obsidian Vault 用于验证可编辑静态知识源。
- 它不是 LifeMesh 的中心数据源，也不应决定核心领域模型。
- 从 Obsidian 学到的能力应抽象为 Source Adapter、Source Revision、Citation Status、删除级联和权限策略。

后续优先接入：

- 个人笔记
- 项目文档
- 常用文档
- 手动输入：截图、日程、心情、活动、待办、临时备注
- 日历
- 任务和提醒
- 联系人基础信息

后置接入：

- 金融
- 健康
- 位置
- 聊天全文
- 高敏家庭或人际信息

## Manual Input 状态

Manual Input 已进入第 1 阶段本地 CLI 原型，并已通过首次真实本机 LM Studio / sqlite-vec 验收。它直接验证：

- 用户和 Agent 能否安全写入个人上下文。
- 记录是否能通过本地 embedding + FTS 被检索。
- `lifemesh bundle` 是否能把 Obsidian 与 Manual Input 一起组装。
- 撤销、删除、敏感级别和 promote 是否能形成闭环。
- 强命中是否能作为 `raw` 证据，弱语义近邻是否只能作为 `lead` 线索。

Manual Input 不等同于系统日历、后台截屏或活动追踪器接入；这些仍需要后续独立 Source Adapter 评估。

## 接入前置条件

每个数据源接入前都应填写：

- 数据源名称
- 数据类型
- 敏感级别
- 接入目的
- 最小字段集合
- 保留周期
- 允许的 Agent 能力
- 审计要求

## 当前数据源评估

- [Obsidian Vault](data-sources/obsidian-vault.md)
- [Manual Input](data-sources/manual-input.md)

## 当前领域模型入口

- [Context Bundle](context-bundle.md)
- [Knowledge Candidates](knowledge-candidates.md)
- [Canonical Facts](canonical-facts.md)
