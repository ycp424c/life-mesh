window.LIFEMESH_PROJECT_STATE = {
  lastUpdated: "2026-06-29",
  state: "Personal Context Layer",
  currentPhase: "第 1 阶段：Personal Context Layer",
  overallProgress: 28,
  summary:
    "LifeMesh 第 1 阶段已进入落地：lifemesh bundle 最小只读 CLI、Obsidian Source Adapter、JSON Context Bundle、fixture 测试和 agent skill 已有第一轮原型。",
  metrics: [
    { label: "文档基线", value: "active", detail: "35+ Markdown 文件", tone: "green" },
    { label: "Web 看板", value: "active", detail: "静态页面，无构建链", tone: "blue" },
    { label: "Context Layer", value: "phase 1", detail: "source-neutral validation", tone: "blue" },
    { label: "关键风险", value: "8", detail: "需持续跟踪", tone: "red" }
  ],
  work: [
    {
      lane: "Now",
      items: [
        "用真实 vault 完成 Q20 手工验收记录",
        "定义来源引用展示格式",
        "定义 frontmatter 结构化事实边界"
      ]
    },
    {
      lane: "Next",
      items: [
        "用 Q20 真实 vault 样例做手工验收",
        "定义 skill 安装与版本化方式",
        "补首批用户故事验收样例",
        "细化 Candidate inbox 确认体验"
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
      title: "Personal Context Layer",
      status: "active",
      progress: 64,
      focus: "只读 bundle CLI 原型、真实 vault 验收、来源引用展示、frontmatter 边界",
      docs: ["phase-1-delivery-plan.md", "cli-contract.md", "ADR-0005", "ADR-0006"]
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
      detail: "CLI + skill + 工具接口，最小权限返回上下文",
      tone: "agent"
    }
  ],
  systemMap: {
    lanes: [
      {
        title: "Source Adapters",
        subtitle: "source-neutral 接入边界",
        tone: "source",
        nodes: [
          { title: "Obsidian Adapter", detail: "首个验证适配器，只读 Markdown" },
          { title: "Calendar / Tasks", detail: "后续事件、承诺、截止日期来源" },
          { title: "Contacts / Mail / Files", detail: "后续关系、沟通、文件来源" }
        ]
      },
      {
        title: "Source Lifecycle",
        subtitle: "可编辑来源身份",
        tone: "vault",
        nodes: [
          { title: "Source Revision", detail: "path / mtime / size / hash / indexed_at" },
          { title: "Citation Status", detail: "current / stale / missing" },
          { title: "Tombstone", detail: "删除、排除、撤销后的失效标记" }
        ]
      },
      {
        title: "Indexes + Views",
        subtitle: "检索只是材料层",
        tone: "index",
        nodes: [
          { title: "Text / Semantic Index", detail: "关键词、全文、语义召回" },
          { title: "Graph View", detail: "link、tag、entity、relationship" },
          { title: "Timeline View", detail: "event、decision、revision history" }
        ]
      },
      {
        title: "Personal Context Layer",
        subtitle: "第一阶段核心能力",
        tone: "context",
        nodes: [
          { title: "Context Slice", detail: "带 evidence_role：fact / raw / context / lead" },
          { title: "Context Bundle", detail: "按来源优先级组装：Fact > Memory > Revision > Candidate" },
          { title: "Knowledge Candidate", detail: "fact / preference / relationship / task / decision" }
        ]
      },
      {
        title: "Canonical Knowledge",
        subtitle: "确认后可复用",
        tone: "store",
        nodes: [
          { title: "Canonical Fact", detail: "已核实、可追溯、可复核、可撤销事实" },
          { title: "Memory", detail: "偏好/语境，只影响排序语气，不作事实证据" },
          { title: "Decision Record", detail: "选择、理由、来源和时间" }
        ]
      },
      {
        title: "Agent Access",
        subtitle: "最小权限调用",
        tone: "agent",
        nodes: [
          { title: "CLI + Skill", detail: "bundle JSON、受限写入、fact review、agent 消费规则" },
          { title: "Source-Backed Answer", detail: "引用来源和 Citation Status" },
          { title: "User Confirmation", detail: "持久化或高风险写入前确认" }
        ]
      }
    ],
    rails: [
      { title: "Policy", detail: "classification / permission scope / sensitivity" },
      { title: "Audit", detail: "who used what, why, and under which revision" },
      { title: "Revocation", detail: "delete, exclude, expire, stale, tombstone" }
    ],
    feedback: [
      "User Confirmation -> Canonical Fact / Memory",
      "Source changes -> Source Revision -> Citation Status",
      "Revocation -> Tombstone -> Context Bundle cleanup"
    ]
  },
  docs: [
    { name: "Vision", path: "docs/00-vision/", status: "draft", signal: "方向已建立" },
    { name: "Governance", path: "docs/01-governance/", status: "draft", signal: "需细化删除和授权" },
    { name: "Domain", path: "docs/02-domain/", status: "draft", signal: "Obsidian 数据源已记录" },
    { name: "Architecture", path: "docs/03-architecture/", status: "draft", signal: "系统架构图已建立" },
    { name: "Roadmap", path: "docs/04-roadmap/", status: "active", signal: "Phase 1 落地计划已定义" },
    { name: "ADR", path: "docs/05-decisions/", status: "active", signal: "7 条 accepted" },
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
      control: "来源、置信度、确认、复核、过期、删除"
    },
    {
      title: "过期事实继续复用",
      severity: "high",
      control: "Fact Review、Source Tombstone、Fact Tombstone、Bundle 准入检查"
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
    },
    {
      id: "ADR-0003",
      title: "Vault Note Revision",
      status: "accepted",
      path: "../docs/05-decisions/ADR-0003-vault-note-revision.md"
    },
    {
      id: "ADR-0004",
      title: "Source-Neutral Core",
      status: "accepted",
      path: "../docs/05-decisions/ADR-0004-source-neutral-core.md"
    },
    {
      id: "ADR-0005",
      title: "Personal Context Layer",
      status: "accepted",
      path: "../docs/05-decisions/ADR-0005-personal-context-layer.md"
    },
    {
      id: "ADR-0006",
      title: "Context Bundle as Artifact, Not Server",
      status: "accepted",
      path: "../docs/05-decisions/ADR-0006-bundle-as-artifact-not-server.md"
    },
    {
      id: "ADR-0007",
      title: "Canonical Fact Review And Revocation",
      status: "accepted",
      path: "../docs/05-decisions/ADR-0007-canonical-fact-review-and-revocation.md"
    }
  ],
  dataSources: [
    {
      name: "Obsidian Vault",
      phase: "第 1 阶段",
      sensitivity: "Private",
      status: "prototype",
      next: "完成 Q20 真实 vault 手工验收记录"
    },
    {
      name: "Vault Note",
      phase: "第 1 阶段",
      sensitivity: "Private",
      status: "planned",
      next: "定义来源引用格式"
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
      status: "prototype",
      guardrail: "必须返回 note_path、line_range、citation_status"
    },
    {
      name: "摘要与事实抽取",
      phase: "第 1 阶段",
      risk: "medium",
      status: "planned",
      guardrail: "区分事实、摘要、推断"
    },
    {
      name: "受限写入（事实/待办/记忆/候选）",
      phase: "第 1 阶段",
      risk: "medium",
      status: "planned",
      guardrail: "agent 推断只能走 candidate，用户确认后升级；automation 仍 deferred"
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
      title: "来源引用格式",
      detail: "回答应如何展示 Vault Note Revision、heading、line range 和 current/stale/missing 状态？"
    },
    {
      title: "Obsidian 白名单目录",
      detail: "首批数据源已确认为 Obsidian Vault；仍需决定是否允许用户为归档或专题目录建立显式白名单。"
    },
    {
      title: "Agent skill 分发方式",
      detail: "CLI + skill 契约和实体文件已落地；仍需决定如何安装、版本化并暴露给不同 agent runtime。"
    },
    {
      title: "Candidate inbox 展示体验",
      detail: "dashboard 只读展示已定；仍需细化列表字段、排序、批量操作提示和风险解释。"
    },
    {
      title: "Frontmatter 结构化事实边界",
      detail: "需要决定哪些 frontmatter 字段可作为结构化事实、哪些只能作为 raw/source metadata。"
    },
    {
      title: "MCP 重新评估触发条件",
      detail: "第 1 阶段不采用 MCP 已决；后续仅在需要实时、有状态工具调用时重新评估。"
    }
  ],
  recentChanges: [
    {
      date: "2026-06-29",
      title: "落地第一轮只读 bundle CLI 原型",
      detail: "新增 bin/lifemesh 与 lifemesh/ Python 标准库实现，支持 Obsidian 只读扫描、Source Revision、raw slice JSON Bundle、显式 vault、路径排除、sensitivity cap、stale/missing state 检测；补 fixture vault 单测和 skills/lifemesh/SKILL.md。"
    },
    {
      date: "2026-06-29",
      title: "定义 Phase 1 落地计划",
      detail: "新增 phase-1-delivery-plan.md：第 1 阶段先实现 lifemesh bundle 最小只读链路、Obsidian Source Adapter、JSON Context Bundle、stale/missing 链路和 agent skill；验收通过后再推进 Candidate inbox、受限写入和 Canonical Fact 复核实现。"
    },
    {
      date: "2026-06-29",
      title: "确定 Canonical Fact 复核与撤销流程",
      detail: "新增 ADR-0007：只有 valid + active + current-supported 的 Canonical Fact 能作为 fact slice；stale/missing/revoked 来源触发 needs_review 和 tombstone 级联，用户可 revalidate、revise、invalidate 或 revoke。"
    },
    {
      date: "2026-06-29",
      title: "清理看板与文档状态漂移",
      detail: "移除已完成的 Obsidian 检索样例和 MCP 首选协议评估待办；Agent Access 改为 CLI + skill；MCP 保留为后续有状态工具调用时的重新评估项。"
    },
    {
      date: "2026-06-26",
      title: "定义 Obsidian 检索最小验收样例",
      detail: "用真实 vault 的 hot.md 定义可验收样例：bundle 产出带 note_path/revision_id/heading/line_range/citation_status 的 raw slice，agent 给 Source-Backed Answer，stale 链路生效。见 obsidian-retrieval-sample.md。"
    },
    {
      date: "2026-06-26",
      title: "定义 CLI 契约 + candidate 确认流程",
      detail: "CLI 读(bundle)+受限写(fact/task/remember/candidate)；agent 推断禁止直接 fact add，走 candidate 待确认。candidate 按 type 升级：fact→Canonical Fact、task→Task、preference/relationship/decision→Memory。低风险自动接受，不阻塞普通回答。见 cli-contract.md、ADR-0005/0006。"
    },
    {
      date: "2026-06-26",
      title: "确定 Bundle 产物格式为 JSON + CLI 搭配 skill",
      detail: "Context Bundle 序列化为 JSON（不用 Markdown）；交付靠薄 CLI + agent skill，skill 指导调用与 evidence_role 消费。见 ADR-0006。"
    },
    {
      date: "2026-06-26",
      title: "第 1 阶段不采用 MCP，Bundle 作为产物交付",
      detail: "Context Bundle 作为可序列化产物经薄 CLI/文件交付，agent 无关；MCP 降级为未来选项。见 ADR-0006。"
    },
    {
      date: "2026-06-26",
      title: "确定 Context Slice 的 evidence_role 与 Bundle 逻辑结构",
      detail: "evidence_role 挂在每个 Slice（fact/raw/context/lead）；事实回答只基于 fact+raw，偏好和线索不进事实陈述位。Bundle 逻辑结构为 task+permission_scope+slices+excluded_sources+freshness_report。"
    },
    {
      date: "2026-06-26",
      title: "确定 Memory 与 Canonical Fact 边界",
      detail: "Memory 只影响排序、语气和偏好，不作事实证据；需要当事实用必须走 Fact Acceptance 升级。推断记忆分两档：普通偏好直接写入，重要偏好/关系/决策类写入前需确认。"
    },
    {
      date: "2026-06-26",
      title: "确定 Context Bundle 来源优先级",
      detail: "组装优先级为 Canonical Fact > Memory > 当前任务相关 Source Revision > 当前任务生成的 Knowledge Candidate；失效来源只进入 excluded_sources / freshness_report。"
    },
    {
      date: "2026-06-26",
      title: "确定 Canonical Fact 生成路径",
      detail: "第一版只允许用户确认、用户手动创建、低风险策略接受三条路径生成 Canonical Fact。"
    },
    {
      date: "2026-06-26",
      title: "新增完整系统架构图",
      detail: "看板新增 Source Adapter 到 Agent Access 的完整架构图，并补 System Map 文档。"
    },
    {
      date: "2026-06-26",
      title: "确认 Canonical Fact 作为已核实事实层",
      detail: "Canonical Fact 可作为 Context Bundle 的高优先级来源，但必须可追溯、可撤销。"
    },
    {
      date: "2026-06-26",
      title: "确定 Knowledge Candidate 第一版类型",
      detail: "第一版类型为 fact、preference、relationship、task、decision，并要求 confidence、risk、lifecycle、source_revisions、why_suggested。"
    },
    {
      date: "2026-06-26",
      title: "确认 User Confirmation 不阻塞普通回答",
      detail: "确认只在候选知识持久化、高风险写入或外部动作前触发。"
    },
    {
      date: "2026-06-26",
      title: "确认第一阶段为 Personal Context Layer",
      detail: "第一阶段不做普通 RAG，也不做 Obsidian 知识地图，而是验证 source-neutral 上下文层。"
    },
    {
      date: "2026-06-26",
      title: "确认 Source-Neutral Core 边界",
      detail: "Obsidian 被降级为首个 Source Adapter，不能成为 LifeMesh 产品中心。"
    },
    {
      date: "2026-06-26",
      title: "确定旧回答来源状态策略",
      detail: "旧回答不自动重写，引用展示 current、stale 或 missing，并提供重新生成动作。"
    },
    {
      date: "2026-06-26",
      title: "接受 Vault Note Revision 模型",
      detail: "Obsidian 被建模为可编辑源，引用和派生事实指向具体索引版本。"
    },
    {
      date: "2026-06-26",
      title: "确定 Obsidian Vault 第一版索引范围",
      detail: "采用只读 Markdown 索引，默认排除 .git、.obsidian、_attachments 二进制、Trash、_archives、tmp。"
    },
    {
      date: "2026-06-26",
      title: "确认 Obsidian Vault 为首个验证数据源",
      detail: "只读扫描到本机 obsidian-default vault，约 1329 个 Markdown 文件。"
    },
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
