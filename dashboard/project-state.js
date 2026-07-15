window.LIFEMESH_PROJECT_STATE = {
  lastUpdated: "2026-07-15",
  state: "Personal Context Layer",
  currentPhase: "第 1 阶段：Personal Context Layer",
  overallProgress: 48,
  summary:
    "LifeMesh 第 1 阶段已进入本地原型。2026-07-15 已实现 ADR-0011 的只读 LifeMesh Console：React + shadcn/ui 界面与本 Project Board 分离，通过按需 127.0.0.1 服务读取真实本地数据；ADR-0010 的 Unified Write Model 仍是已接受但尚未实现的目标架构。",
  metrics: [
    { label: "文档基线", value: "active", detail: "Manual Input 实现已同步", tone: "green" },
    { label: "Web 看板", value: "active", detail: "静态页面，无构建链", tone: "blue" },
    { label: "Context Layer", value: "phase 1", detail: "只读 Console V1 已落地", tone: "blue" },
    { label: "关键风险", value: "16", detail: "含本地模型、流言、数据库迁移和 Console 暴露风险", tone: "red" }
  ],
  work: [
    {
      lane: "Now",
      items: [
        "用真实个人数据规模持续验证只读 LifeMesh Console 的可用性与性能",
        "实施 Unified Write Model、集中 schema migration 和事务边界",
        "统一 CLI、Manual Input、RumorClaim 的 Candidate handoff",
        "落地 Candidate confirm 与 Canonical Fact/Memory/Task/Event",
        "完成真实数据库备份、迁移、回滚和计数验收"
      ]
    },
    {
      lane: "Next",
      items: [
        "评估第一个自动 RumorClaim source adapter 和 rumor_policy",
        "补 Fact Review 对 Manual Input tombstone 的级联验收",
        "补 Manual Input 长期性能边界和真实任务场景验收"
      ]
    },
    {
      lane: "Later",
      items: [
        "完善 Candidate inbox 批量确认体验",
        "接入 RumorClaim 自动 source adapter 和 review UI",
        "接入系统日历和提醒事项 Source Adapter",
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
      progress: 90,
      focus: "既有读链路、受限采集和只读 LifeMesh Console 已落地；下一核心交付是 Unified Write Model",
      docs: ["phase-1-delivery-plan.md", "lifemesh-console.md", "write-model-and-migrations.md", "ADR-0006", "ADR-0010", "ADR-0011"]
    },
    {
      id: "2",
      title: "系统日历/任务同步与高级调度",
      status: "planned",
      progress: 8,
      focus: "系统日历、提醒事项、外部任务应用同步、冲突检测",
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
    },
    {
      title: "User Interface Layer",
      detail: "React + shadcn/ui LifeMesh Console 读取真实本地状态；Project Board 只展示项目状态",
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
          { title: "Manual Input Inbox", detail: "截图、日程、心情、活动、待办和备注的本地写入源" },
          { title: "Calendar / Tasks", detail: "后续系统同步来源" },
          { title: "Contacts / Mail / Files", detail: "后续关系、沟通、文件来源" }
        ]
      },
      {
        title: "Source Lifecycle",
        subtitle: "可编辑来源身份",
        tone: "vault",
        nodes: [
          { title: "Source Reference", detail: "SourceRevision 或 Manual Input record / extraction" },
          { title: "Source Envelope", detail: "RumorClaim 的最小来源外壳，不默认保存 raw material" },
          { title: "Manual Input State", detail: "active / auto_captured / promoted / revoked / deleted" },
          { title: "Citation Status", detail: "current / stale / missing" },
          { title: "Tombstone", detail: "Source / Manual Input / Fact 的失效标记" }
        ]
      },
      {
        title: "Indexes + Views",
        subtitle: "检索只是材料层",
        tone: "index",
        nodes: [
          { title: "Text / Semantic Index", detail: "FTS + 本地 embedding + SQLite 向量检索" },
          { title: "Graph View", detail: "link、tag、entity、relationship" },
          { title: "Timeline View", detail: "event、decision、revision history" }
        ]
      },
      {
        title: "Personal Context Layer",
        subtitle: "第一阶段核心能力",
        tone: "context",
        nodes: [
          { title: "ContextCandidate", detail: "adapter 返回 source-backed 候选材料" },
          { title: "BundleAssembler", detail: "准入、来源层级、去重、多样性、assembly_report" },
          { title: "Context Slice", detail: "带 evidence_role：fact / raw / context / lead" },
          { title: "Context Bundle", detail: "由 assembler 统一组装 candidates" },
          { title: "RumorClaim", detail: "未验证 claim，只能作为 lead 或 promote 到 Knowledge Candidate" },
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
          { title: "Promoted Object", detail: "由 input promote 创建 inbox-derived 最小对象" },
          { title: "Decision Record", detail: "选择、理由、来源和时间" }
        ]
      },
      {
        title: "Agent Access",
        subtitle: "最小权限调用",
        tone: "agent",
        nodes: [
          { title: "CLI + Skill", detail: "bundle JSON、assembly_report、受限写入、agent 消费规则" },
          { title: "Source-Backed Answer", detail: "引用来源和 Citation Status" },
          { title: "User Confirmation", detail: "持久化或高风险写入前确认" }
        ]
      },
      {
        title: "User Interfaces",
        subtitle: "个人数据与项目状态分离",
        tone: "agent",
        nodes: [
          { title: "LifeMesh Console", detail: "已实现：按需启动、仅 127.0.0.1；读取真实本地数据但不持久化写入" },
          { title: "Project Board", detail: "静态、文档派生；不读取或展示个人数据" }
        ]
      }
    ],
    rails: [
      { title: "Policy", detail: "classification / permission scope / sensitivity" },
      { title: "Audit", detail: "who used what, why, and under which source reference" },
      { title: "Revocation", detail: "delete, exclude, expire, stale, tombstone" }
    ],
    feedback: [
      "User Confirmation -> Canonical Fact / Memory",
      "Source changes -> Source Reference -> Citation Status",
      "Revocation -> Tombstone -> Context Bundle cleanup",
      "Unverified material -> RumorClaim -> Knowledge Candidate",
      "Local state -> read-side adapter -> LifeMesh Console"
    ]
  },
  docs: [
    { name: "Vision", path: "docs/00-vision/", status: "draft", signal: "方向已建立" },
    { name: "Governance", path: "docs/01-governance/", status: "draft", signal: "需细化删除和授权" },
    { name: "Domain", path: "docs/02-domain/", status: "draft", signal: "Candidate inbox MVP 已同步" },
    { name: "Architecture", path: "docs/03-architecture/", status: "draft", signal: "Console 实现与 Unified Write Model 边界已同步" },
    { name: "Roadmap", path: "docs/04-roadmap/", status: "active", signal: "只读 Console V1 已完成，统一写模型待实施" },
    { name: "ADR", path: "docs/05-decisions/", status: "active", signal: "11 条 accepted" },
    { name: "Security", path: "docs/07-security/", status: "draft", signal: "迁移恢复与 loopback Console 控制已同步" },
    { name: "Dashboard", path: "docs/08-dashboard/", status: "active", signal: "同步规则已落地" },
    { name: "Implementation Specs", path: "docs/superpowers/specs/", status: "active", signal: "Unified Write Model spec 已通过 written review" }
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
      title: "原始数据和派生事实断链",
      severity: "high",
      control: "每个事实保存 provenance，Manual Input 保留 derived_from_input_id"
    },
    {
      title: "过期事实继续复用",
      severity: "high",
      control: "Fact Review、Source Tombstone、Fact Tombstone、Bundle 准入检查"
    },
    {
      title: "自动执行不可逆动作",
      severity: "high",
      control: "风险分级、人工确认、撤销机制"
    },
    {
      title: "只做向量库导致语义混乱",
      severity: "medium",
      control: "原始、结构化、索引、图谱、时间线分层"
    },
    {
      title: "高敏数据过早接入",
      severity: "high",
      control: "阶段 5 前不正式接入高敏数据源，Sensitive input 默认隔离"
    },
    {
      title: "Agent 自动捕获造成沉默记忆",
      severity: "high",
      control: "每次记录必须说明 id、kind、摘要、sensitivity 和 Bundle 可用性"
    },
    {
      title: "本地 VLM 误读截图",
      severity: "medium",
      control: "extraction 不等于 fact，promote 必须确认"
    },
    {
      title: "本地个人数据库泄露",
      severity: "high",
      control: "~/.lifemesh 0700，数据库和 raw asset 0600，后续评估加密"
    },
    {
      title: "流言污染事实层",
      severity: "high",
      control: "RumorClaim 只能作为未验证 lead；只可 promote 到 Knowledge Candidate"
    },
    {
      title: "流言原始物料污染本地仓库",
      severity: "medium",
      control: "原始物料默认只进 temporary parsing sandbox，长期保留最小 source envelope"
    },
    {
      title: "真实数据库迁移或恢复损坏",
      severity: "high",
      control: "exclusive lock + online backup + 动态 preflight/postflight 守恒 + forensic restore"
    },
    {
      title: "本地 Console Server 暴露个人数据",
      severity: "high",
      control: "前台短时启动、仅 127.0.0.1 随机端口、首版只读、无 CORS、严格 Host/Origin 校验"
    },
    {
      title: "Console 未遮罩 Sensitive 正文",
      severity: "medium",
      control: "持续显示敏感度标签；用户控制本机屏幕环境；不把 UI 直读权限扩展到 Bundle、日志或导出"
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
    },
    {
      id: "ADR-0008",
      title: "Manual Input Inbox With Local Retrieval",
      status: "accepted",
      path: "../docs/05-decisions/ADR-0008-manual-input-inbox-local-retrieval.md"
    },
    {
      id: "ADR-0009",
      title: "Unverified Rumor Claims",
      status: "accepted",
      path: "../docs/05-decisions/ADR-0009-unverified-rumor-claims.md"
    },
    {
      id: "ADR-0010",
      title: "Unified Write Model, Transactional Acceptance And Database Migration",
      status: "accepted",
      path: "../docs/05-decisions/ADR-0010-unified-write-model-transactional-acceptance-and-database-migration.md"
    },
    {
      id: "ADR-0011",
      title: "Local Loopback Console Server",
      status: "accepted",
      path: "../docs/05-decisions/ADR-0011-local-loopback-console-server.md"
    }
  ],
  dataSources: [
    {
      name: "Obsidian Vault",
      phase: "第 1 阶段",
      sensitivity: "Private",
      status: "prototype",
      next: "保持 Q20 验收样例作为回归"
    },
    {
      name: "Vault Note",
      phase: "第 1 阶段",
      sensitivity: "Private",
      status: "prototype",
      next: "后续回答渲染层补基于当前来源重新生成动作"
    },
    {
      name: "Manual Input",
      phase: "第 1 阶段",
      sensitivity: "Private / Sensitive",
      status: "prototype",
      next: "补长期性能边界和真实任务场景验收"
    },
    {
      name: "RumorClaim",
      phase: "第 1 阶段 follow-on",
      sensitivity: "Private / Sensitive",
      status: "prototype",
      next: "决定首个允许自动产出 RumorClaim 的 source adapter 和 rumor_policy"
    },
    {
      name: "日历与任务",
      phase: "第 2 阶段",
      sensitivity: "Private",
      status: "planned",
      next: "Manual Input event/task 最小对象稳定后再接系统同步和高级调度"
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
      guardrail: "必须返回 citation.label、note_path、line_range、citation_status"
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
      status: "prototype",
      guardrail: "agent 推断只能走 candidate 或 auto_captured，用户确认后升级；automation 仍 deferred"
    },
    {
      name: "Manual Input Inbox",
      phase: "第 1 阶段",
      risk: "medium-high",
      status: "prototype",
      guardrail: "auto_captured 只能做 lead；promote 必须用户确认"
    },
    {
      name: "本地语义检索",
      phase: "第 1 阶段",
      risk: "medium",
      status: "prototype",
      guardrail: "LM Studio 本地 embedding，Sensitive 默认不进 Bundle"
    },
    {
      name: "截图 VLM extraction",
      phase: "第 1 阶段",
      risk: "medium-high",
      status: "prototype",
      guardrail: "extraction 带 provider/model/confidence，不直接成为 fact"
    },
    {
      name: "RumorClaim 未验证线索处理",
      phase: "第 1 阶段 follow-on",
      risk: "medium-high",
      status: "prototype",
      guardrail: "结构化 CLI MVP；默认不进普通 Bundle；只能作为 lead；promote 只到 Knowledge Candidate"
    },
    {
      name: "LifeMesh Console 只读界面",
      phase: "第 1 阶段",
      risk: "medium-high",
      status: "prototype",
      guardrail: "前台短时启动、仅 127.0.0.1、严格 Host/Origin、无 CORS、无持久化写接口"
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
  rumorReview: {
    status: "prototype",
    ruleVersion: "rumor-claim-v1.1",
    summary:
      "结构化 CLI MVP 已落地：RumorClaim 默认不进普通 Bundle，显式包含时只作为未验证 lead；静态看板不直接读取本机 ~/.lifemesh/lifemesh.db，实时数量必须由后续只读同步脚本填充。",
    queues: [
      {
        name: "general_review",
        count: "Needs live query",
        detail: "普通 parked claims；reviewed_parked 已人工检视并跳过默认复审；二者仅在 --source rumor 或 --include-unverified 时以 lead 展示。"
      },
      {
        name: "conflict_review",
        count: "Needs live query",
        detail: "contradicted evidence 默认排除出可用 slices；不自动触发正式 Fact Review。"
      },
      {
        name: "sensitive_review",
        count: "Needs live query",
        detail: "Sensitive / Restricted RumorClaim 默认受 sensitivity cap 隔离。"
      }
    ],
    stats: [
      {
        label: "最近高影响 claims",
        value: "Needs live query",
        detail: "静态数据不得伪造 claim 内容或数量。"
      },
      {
        label: "已检视 / 过期 / 丢弃",
        value: "Needs live query",
        detail: "reviewed_parked / expired / dismissed 只读统计待同步脚本填充。"
      },
      {
        label: "Promotion handoff",
        value: "local link",
        detail: "当前 rumor promote 仍只写 rumor_candidate_links；与 Candidate inbox 的正式 handoff 和 confirm lifecycle 待补。"
      }
    ],
    highImpact: [
      {
        title: "实时队列取数",
        detail: "下一步需要只读同步命令从 lifemesh rumor list 聚合 queue count、高影响 claim 摘要、reviewed_parked/expired/dismissed 统计和规则版本。"
      }
    ]
  },
  openQuestions: [
    {
      title: "LifeMesh Console 真实规模验收",
      detail: "React + shadcn/ui 首版已完成桌面与窄屏浏览器验收；仍需在长期真实个人数据规模下验证搜索响应、图谱密度、时间线长度和详情信息分层。"
    },
    {
      title: "stale / missing 引用交互",
      detail: "2026-07-09 已用真实 hot.md 的临时副本验证 CLI stale/missing freshness_report；UI 或回答渲染层仍需实现重新生成动作。"
    },
    {
      title: "Manual Input weak lead 真实样例",
      detail: "Q20 的 --source all 未选入 Manual Input candidates；weak lead 不作为事实的规则已有本机验收，仍可补一个独立真实任务样例。"
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
      title: "LM Studio 模型配置",
      detail: "首次真实本机验收已确认 embedding 模型 identifier、维度和 VLM 调用方式；当前截图 OCR/VLM 配置已切到 ornith-1.0-9b，仍需记录长期性能边界。"
    },
    {
      title: "RumorClaim 首个 source adapter",
      detail: "结构化 CLI MVP 已落地；自动来源实现前仍需决定第一个允许产出 RumorClaim 的 source adapter、rumor_policy，以及 dashboard 只读同步脚本。"
    },
    {
      title: "MCP 重新评估触发条件",
      detail: "第 1 阶段不采用 MCP 已决；后续仅在需要实时、有状态工具调用时重新评估。"
    }
  ],
  recentChanges: [
    {
      date: "2026-07-15",
      title: "实现 React + shadcn/ui LifeMesh Console V1",
      detail: "新增按需 127.0.0.1 Python Console Server、真实本地 read-side API、总览/搜索/分域浏览/详情/图谱/时间线/非持久化 Bundle Explorer，以及暖琥珀、萌芽绿、未知紫和理性灰蓝的响应式产品界面；完成 HTTP 安全测试和桌面/窄屏真实浏览器验收。"
    },
    {
      date: "2026-07-15",
      title: "确认 LifeMesh Console 信息架构",
      detail: "首屏采用总览工作台；跨领域全局搜索、数据健康、近期记录和队列摘要作为主入口，Knowledge Graph 与 Timeline 独立展示，图谱只使用真实运行时关系。"
    },
    {
      date: "2026-07-15",
      title: "确认独立只读 LifeMesh Console",
      detail: "新增 ADR-0011 和 lifemesh-console 架构文档：Console 与静态 Project Board 分离，第一版读取真实本地数据但只读，通过按需启动、仅绑定 127.0.0.1 的 Console Server 复用 read-side logic；Agent 继续使用 CLI + JSON Bundle + skill。"
    },
    {
      date: "2026-07-15",
      title: "完成 Unified Write Model written-spec review",
      detail: "新增 ADR-0010 和正式目标架构文档；把迁移验收改为动态 preflight/postflight 守恒，修正 Source Reference 外键回填顺序、legacy why_suggested/handoff_key 映射和 restore exclusive lock，并同步 README、roadmap、security 与文档健康区。当前仍只确认设计，未宣称实现或迁移完成。"
    },
    {
      date: "2026-07-10",
      title: "确认 Unified Write Model 完整设计",
      detail: "确定一次性交付集中 SQLite migration、统一 Candidate handoff、Acceptance、Canonical Fact/Memory/Task/Event、Fact Review、normalized provenance 和真实数据库 online backup/migration；当前仅设计已确认，尚未宣称实现完成。"
    },
    {
      date: "2026-07-09",
      title: "落地 Candidate inbox 最小 CLI",
      detail: "新增 lifemesh candidate add/list/show/discard，本地写入 lifemesh.db 的 knowledge_candidates 表；默认 lifecycle=confirm_required，list 按 risk/confidence 排序，discard 写 tombstone 不删除历史；confirm/merge/edit 仍是后续能力。"
    },
    {
      date: "2026-07-09",
      title: "完成 Q20 真实 vault 手工验收记录",
      detail: "运行 lifemesh bundle Q20 真实 vault 样例，返回 20 个 raw/current slices，命中专题归档页和 hot.md，保留 excluded_sources/freshness_report 字段；用真实 hot.md 的 /tmp 临时副本验证 stale 和 missing 只进入 freshness_report，新回答只能使用 current revision。"
    },
    {
      date: "2026-07-09",
      title: "新增 RumorClaim 已检视保留状态",
      detail: "新增 reviewed_parked 和 rumor keep：人工检视后仍保留为未验证 lead，但默认复审列表跳过；显式请求 rumor lead 时仍可进入 Bundle。"
    },
    {
      date: "2026-07-03",
      title: "收紧 RumorClaim 准入、过期和看板边界",
      detail: "RumorClaim add 现在要求显式 user_relevance 和 impact；默认可信度从 unknown/unverified 起步；contradicted 和 expired claims 不进入可用 Bundle slices；dashboard 新增 review queue 摘要区，并将本机实时数量标记为 Needs live query。"
    },
    {
      date: "2026-07-03",
      title: "落地 RumorClaim 本地结构化 CLI MVP",
      detail: "实现 rumor add/list/show/dismiss/expire/promote、持久化门槛、review queue、最小 source envelope、审计事件、bundle --source rumor 和 --include-unverified 的 lead-only 准入；自动 source adapter、截图/图片自动抽取和 review UI 仍未实现。"
    },
    {
      date: "2026-07-03",
      title: "定义 RumorClaim / UnverifiedClaim 契约",
      detail: "新增 ADR-0009 和 rumor-claims 领域文档：可信度未知的文本、截图和图片先抽取为 RumorClaim，不作为 Manual Input kind，不默认保存原始物料，默认不进普通 Bundle，只能作为 lead，并且只能 promote 到 Knowledge Candidate。"
    },
    {
      date: "2026-07-03",
      title: "切换本机截图 OCR/VLM 模型",
      detail: "将 ~/.lifemesh/config.json 和全局 LifeMesh skill 的 vlm_model 切换为 ornith-1.0-9b；模型输出仍按 provider/model/confidence 记录，2026-06-30 的 qwen/qwen3-vl-8b 首次验收记录保留为历史证据。"
    },
    {
      date: "2026-06-30",
      title: "落地 Source-Backed Answer 引用与检索命中策略",
      detail: "Bundle slice 新增 citation 字段：Obsidian 使用 obsidian-note-line-range-v1，Manual Input 使用 manual-input-v1；Manual Input search 返回 match_status、match_reason、evidence_eligible 和 score_breakdown。FTS 或 vector >= 0.75 为 strong，可作 raw；0.45 <= vector < 0.75 为 weak，只能作为 lead。"
    },
    {
      date: "2026-06-30",
      title: "完成 Manual Input 真实本机验收",
      detail: "使用真实本机 LM Studio 和 sqlite-vec 验证 note add/search/show/update/revoke/delete、candidate promote、截图 VLM extraction、auto_captured lead-only Bundle、bundle --source all；验收时 embedding 模型为 text-embedding-qwen3-embedding-0.6b（1024 维），截图 VLM 为 qwen/qwen3-vl-8b。后续需补长期性能边界。"
    },
    {
      date: "2026-06-29",
      title: "落地 source-neutral BundleAssembler",
      detail: "新增 ContextCandidate / BundleAssembler 实现：Obsidian 与 Manual Input 先返回 candidates，再统一执行准入、来源层级、去重、多样性选择和 assembly_report 诊断；bundle --source all 不再拼接两个已完成 Bundle。"
    },
    {
      date: "2026-06-29",
      title: "落地 Manual Input 本地 CLI 原型",
      detail: "新增 ~/.lifemesh 配置层、SQLite 主库、FTS、sqlite-vec 加载、LM Studio embedding/VLM 调用、input add/search/list/show/update/revoke/delete/promote，以及 bundle --source manual-input/all；后续由 BundleAssembler 统一跨源组装。"
    },
    {
      date: "2026-06-29",
      title: "收敛 Manual Input 与 Phase 1 边界",
      detail: "确认 Manual Input 不使用 SourceRevision，而作为 source reference 参与 Bundle 和 Fact Review；ADR-0008 是 Phase 1 后续 milestone；Phase 1 promote 只创建 inbox-derived 最小对象，第 2 阶段改为系统日历/任务同步与高级调度。"
    },
    {
      date: "2026-06-29",
      title: "确定 Manual Input Inbox + 本地检索规格",
      detail: "新增 ADR-0008 和 manual-input 数据源评估：作为 Phase 1 后续 milestone，契约定义 ~/.lifemesh SQLite 主库、Raw Vault managed assets、FTS、LM Studio 本地 embedding、qwen3-vl-8b 截图 extraction、SQLite 向量检索；规划 input add/search/show/list/update/revoke/delete/promote，并在实现后进入 bundle --source all。"
    },
    {
      date: "2026-06-29",
      title: "落地第一轮只读 bundle CLI 原型",
      detail: "新增 bin/lifemesh 与 lifemesh/ Python 标准库实现，支持 Obsidian 只读扫描、Source Revision、raw slice JSON Bundle、显式 vault、路径排除、sensitivity cap、stale/missing state 检测；补 fixture vault 单测和 skills/lifemesh/SKILL.md。"
    },
    {
      date: "2026-06-29",
      title: "定义 Phase 1 落地计划",
      detail: "新增 phase-1-delivery-plan.md：第 1 阶段先实现 lifemesh bundle 最小只读链路、Obsidian Source Adapter、JSON Context Bundle、stale/missing 链路和 agent skill；只读原型验收后，ADR-0008 作为 Manual Input 后续 milestone。"
    },
    {
      date: "2026-06-29",
      title: "确定 Canonical Fact 复核与撤销流程",
      detail: "新增 ADR-0007：只有 valid + active + current-supported 的 Canonical Fact 能作为 fact slice；Source Revision 或 Manual Input source reference 失效会触发 needs_review 和 tombstone 级联，用户可 revalidate、revise、invalidate 或 revoke。"
    },
    {
      date: "2026-06-29",
      title: "清理看板与文档状态漂移",
      detail: "移除已完成的 Obsidian 检索样例和 MCP 首选协议评估待办；Agent Access 改为 CLI + skill；MCP 保留为后续有状态工具调用时的重新评估项。"
    },
    {
      date: "2026-06-26",
      title: "定义 Obsidian 检索最小验收样例",
      detail: "用真实 vault 的 hot.md 定义可验收样例：bundle 产出带 note_path/revision_id/heading/line_range/citation_status/citation.label 的 raw slice，agent 给 Source-Backed Answer，stale 链路生效。见 obsidian-retrieval-sample.md。"
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
      detail: "组装优先级为 Canonical Fact > Memory > 当前任务相关 Source Reference > 当前任务生成的 Knowledge Candidate；失效来源只进入 excluded_sources / freshness_report；当前实现由 BundleAssembler 执行该优先级。"
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
      detail: "第一版类型为 fact、preference、relationship、task、decision，并要求 confidence、risk、lifecycle、source_refs、why_suggested。"
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
