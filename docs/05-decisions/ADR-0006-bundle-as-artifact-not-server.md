# ADR-0006: Context Bundle as Artifact, Not Server

状态：accepted
日期：2026-06-26

## Context

第 1 阶段需要把 Context Bundle 交付给 Agent。`mcp-and-tool-interface.md` 一直把 MCP 列为候选首个协议。但 MCP 要求维护长驻 server，协议分帧和结构较复杂，与 LifeMesh 既有立场冲突：`ADR-0001` 是 docs-first，`ADR-0002` 是静态看板无构建链，`ADR-0004` 要求核心 source-neutral 且协议无关。第 1 阶段只需要只读交付 Bundle，不需要实时、有状态的工具调用。

## Decision

第 1 阶段不采用 MCP。Context Bundle 作为**可序列化 JSON 产物**交付，通过**薄 CLI + skill** 的组合交付给 agent，agent 无关。

- Bundle 本质是 Q15 定义的逻辑结构（`task + permission_scope + slices + excluded_sources + freshness_report`）的 JSON 序列化结果，不是运行中的服务。不用 Markdown，因为这层需要的是供 agent 程序化消费的结构化字段，不是排版。
- 交付方式：薄 CLI 读取索引、按任务组装 JSON Bundle、输出到文件或 stdout；无长驻进程、无协议分帧、无 server 维护。
- 搭配一份 **skill**（agent 可读说明）：告诉 agent 如何调用 CLI，以及拿到 JSON Bundle 后按 `evidence_role` 消费（事实回答只用 `fact` + `raw`，`context` 只调语气，`lead` 标"未核实"）。Skill 把 Q15 的消费规则固化成 agent 可遵循的指令。
- Agent 通过 shell 调 CLI 或读文件拿到 JSON Bundle，按 skill 说明消费。任何能读 skill 的 agent 都能用，不绑定特定 client。
- 核心模型保持协议无关：CLI/文件/skill 只是交付通道，换通道不改动 Context Bundle / evidence_role / Source Revision 模型。
- 第 1 阶段只读交付，不暴露 `memory-write` 或 `automation`。

## Consequences

正向影响：

- 第 1 阶段不引入运行时服务，对齐 docs-first 和静态无构建链立场。
- Bundle 契约可以先定义、后实现，符合当前文档阶段。
- agent 无关，换 agent 不改 LifeMesh。

代价：

- 需要先定义 Bundle 产物格式（JSON 还是结构化 Markdown）和 CLI 契约，作为后续工作。
- 没有实时工具调用能力，`memory-write` / `automation` 推迟到后续阶段。

## Alternatives Considered

- 采用 MCP 作为首个协议：生态好、agent 接入方便，但要维护 server、结构复杂，与 docs-first 和静态无构建链立场冲突，第 1 阶段只读场景不需要。
- 自定义 RPC 协议：完全可控，但等于自己造协议生态，比 CLI/文件更重，无收益。

## Follow-ups

- 定义第 1 阶段 CLI 契约（命令、参数、JSON 输出 schema）。第 1 阶段可只定义不实现。
- 编写配套 skill（调用方式 + evidence_role 消费规则）。
- 后续阶段需要实时、有状态工具调用时，重新评估 MCP。
