window.LIFEMESH_PROJECT_STATE = {
  lastUpdated: "2026-06-26",
  state: "文档与看板基线",
  currentPhase: "第 0 阶段：个人数据宪法",
  overallProgress: 12,
  summary:
    "LifeMesh 已建立 Personal Data OS 的文档基线和静态 Web 看板。当前重点是把治理、安全、路线图和第一批数据源接入评估收敛到可执行范围。",
  metrics: [
    { label: "文档基线", value: "active", detail: "35+ Markdown 文件", tone: "green" },
    { label: "Web 看板", value: "active", detail: "静态页面，无构建链", tone: "blue" },
    { label: "业务代码", value: "none", detail: "尚未进入实现", tone: "amber" },
    { label: "关键风险", value: "7", detail: "需持续跟踪", tone: "red" }
  ],
  work: [
    {
      lane: "Now",
      items: [
        "固化项目看板同步规则",
        "补齐阶段 0 治理细节",
        "明确第一批数据源接入评估"
      ]
    },
    {
      lane: "Next",
      items: [
        "定义静态知识数字化最小范围",
        "补首批用户故事验收样例",
        "评估 MCP 是否作为首个 Agent 接口"
      ]
    },
    {
      lane: "Later",
      items: [
        "进入文档检索原型",
        "接入时间与任务对象",
        "建立长期记忆查看和删除流程"
      ]
    },
    {
      lane: "Guardrails",
      items: [
        "高敏数据后置",
        "Agent 只能通过受控工具访问数据",
        "重大变化必须同步 ADR、文档和看板"
      ]
    }
  ],
  phases: [
    {
      id: "0",
      title: "个人数据宪法",
      status: "active",
      progress: 55,
      focus: "安全边界、分类、授权、风险登记",
      docs: ["personal-data-constitution.md", "data-classification.md", "risk-register.md"]
    },
    {
      id: "1",
      title: "静态知识数字化",
      status: "planned",
      progress: 18,
      focus: "文档问答、来源引用、删除级联",
      docs: ["data-map.md", "provenance-and-lifecycle.md"]
    },
    {
      id: "2",
      title: "时间与任务",
      status: "planned",
      progress: 8,
      focus: "Event、Task、Commitment、Deadline",
      docs: ["canonical-objects.md", "user-stories.md"]
    },
    {
      id: "3",
      title: "人际上下文",
      status: "planned",
      progress: 6,
      focus: "关系事实而非聊天全文",
      docs: ["data-map.md", "permissions-and-consent.md"]
    },
    {
      id: "4",
      title: "长期记忆",
      status: "planned",
      progress: 12,
      focus: "显式、推断、情境记忆",
      docs: ["memory-model.md", "retention-and-deletion.md"]
    },
    {
      id: "5",
      title: "高敏感数据",
      status: "deferred",
      progress: 4,
      focus: "金融、健康、位置、本地优先",
      docs: ["data-classification.md", "threat-model.md"]
    },
    {
      id: "6",
      title: "可行动 Agent",
      status: "deferred",
      progress: 5,
      focus: "草稿、写入、外发、执行确认",
      docs: ["agent-access-layer.md", "sandboxing-and-tool-safety.md"]
    }
  ],
  architecture: [
    {
      title: "Personal Sources",
      detail: "文档、日历、任务、联系人、决策记录",
      tone: "source"
    },
    {
      title: "Raw Vault",
      detail: "原始数据保险库，可追溯、可备份、可删除",
      tone: "vault"
    },
    {
      title: "Canonical Store",
      detail: "规范化对象、事实、事件、承诺、记忆",
      tone: "store"
    },
    {
      title: "Index + Graph + Timeline",
      detail: "全文、语义、关系和时间线视图",
      tone: "index"
    },
    {
      title: "Policy + Audit",
      detail: "分类、授权、撤销、审计和风险确认",
      tone: "policy"
    },
    {
      title: "Agent Access Layer",
      detail: "MCP/工具接口，最小权限返回上下文",
      tone: "agent"
    }
  ],
  docs: [
    { name: "Vision", path: "docs/00-vision/", status: "draft", signal: "方向已建立" },
    { name: "Governance", path: "docs/01-governance/", status: "draft", signal: "需细化删除和授权" },
    { name: "Domain", path: "docs/02-domain/", status: "draft", signal: "核心对象已列出" },
    { name: "Architecture", path: "docs/03-architecture/", status: "draft", signal: "高层边界已建立" },
    { name: "Roadmap", path: "docs/04-roadmap/", status: "draft", signal: "阶段已定义" },
    { name: "ADR", path: "docs/05-decisions/", status: "active", signal: "2 条 accepted" },
    { name: "Security", path: "docs/07-security/", status: "draft", signal: "威胁模型初版" },
    { name: "Dashboard", path: "docs/08-dashboard/", status: "active", signal: "同步规则已落地" }
  ],
  risks: [
    {
      title: "看板与文档漂移",
      severity: "high",
      control: "AGENTS.md 强制同步 dashboard/project-state.js"
    },
    {
      title: "Agent 越权访问",
      severity: "high",
      control: "最小权限、按任务授权、审计"
    },
    {
      title: "长期记忆污染",
      severity: "medium",
      control: "来源、置信度、确认、过期、删除"
    },
    {
      title: "高敏数据过早接入",
      severity: "high",
      control: "阶段 5 前默认后置"
    }
  ],
  decisions: [
    {
      id: "ADR-0001",
      title: "文档先行初始化",
      status: "accepted",
      path: "../docs/05-decisions/ADR-0001-docs-first-initialization.md"
    },
    {
      id: "ADR-0002",
      title: "静态 Web 项目看板",
      status: "accepted",
      path: "../docs/05-decisions/ADR-0002-static-project-board.md"
    }
  ],
  dataSources: [
    {
      name: "个人笔记",
      phase: "第 1 阶段",
      sensitivity: "Private",
      status: "planned",
      next: "填写 data-source-intake"
    },
    {
      name: "项目文档",
      phase: "第 1 阶段",
      sensitivity: "Private",
      status: "planned",
      next: "定义最小字段和来源记录"
    },
    {
      name: "日历与任务",
      phase: "第 2 阶段",
      sensitivity: "Private",
      status: "planned",
      next: "确认 Event/Task/Commitment 语义"
    },
    {
      name: "金融、健康、位置",
      phase: "第 5 阶段",
      sensitivity: "Sensitive",
      status: "deferred",
      next: "阶段 0-4 完成前不接入"
    }
  ],
  capabilities: [
    {
      name: "文档搜索",
      phase: "第 1 阶段",
      risk: "low-medium",
      status: "planned",
      guardrail: "必须返回来源"
    },
    {
      name: "摘要与事实抽取",
      phase: "第 1 阶段",
      risk: "medium",
      status: "planned",
      guardrail: "区分事实、摘要、推断"
    },
    {
      name: "记忆写入",
      phase: "第 4 阶段",
      risk: "medium-high",
      status: "deferred",
      guardrail: "显式/推断/情境分级"
    },
    {
      name: "外部执行",
      phase: "第 6 阶段",
      risk: "high",
      status: "deferred",
      guardrail: "必须人工确认"
    }
  ],
  openQuestions: [
    {
      title: "首个用户场景",
      detail: "静态知识数字化应优先服务个人文档问答还是项目资料检索？"
    },
    {
      title: "首批数据源",
      detail: "需要确定第 1 阶段接入的最小数据源集合。"
    },
    {
      title: "MCP 接口",
      detail: "是否采用 MCP 作为首个 Agent Access Layer 协议仍待决。"
    },
    {
      title: "记忆确认",
      detail: "推断记忆是否默认需要用户确认后才生效？"
    }
  ],
  recentChanges: [
    {
      date: "2026-06-26",
      title: "初始化静态 Web 项目看板",
      detail: "新增 dashboard/、ADR-0002 和看板维护规则。"
    },
    {
      date: "2026-06-26",
      title: "建立文档基线",
      detail: "新增愿景、治理、领域、架构、路线图、安全和 ADR 文档结构。"
    }
  ],
  syncChecklist: [
    "路线图变化 -> 更新 docs/04-roadmap/ 和 phases",
    "架构变化 -> 更新 docs/03-architecture/ 和 architecture",
    "治理或安全变化 -> 更新 docs/01-governance/、docs/07-security/ 和 risks",
    "新增决策 -> 新增 ADR 并更新 decisions",
    "新增长期文档 -> 更新 docs/README.md 和 docs",
    "当前工作重点变化 -> 更新 work 和 summary"
  ]
};
