# LifeMesh

LifeMesh is a Personal Data OS context for turning a user's long-lived personal knowledge, records, and decisions into controlled, source-backed context for AI agents.

## Language

**Obsidian Vault**:
A local Obsidian knowledge base selected as LifeMesh's first validation source adapter. It is not the center of the product and should not shape LifeMesh's core concepts beyond source-neutral lessons about editable knowledge sources.
_Avoid_: Obsidian data, notes folder, knowledge base

**Source Adapter**:
A boundary that connects LifeMesh to one external or local personal data source while preserving source-neutral lifecycle, permission, provenance, and audit semantics.
_Avoid_: integration, importer, connector

**Vault Note**:
A Markdown note inside the Obsidian Vault. It may contain frontmatter, headings, wikilinks, tasks, and links to attachments.
_Avoid_: document, file, page

**Vault Note Revision**:
A specific indexed version of a Vault Note, identified by its path, modification metadata, content hash, and index time. Source citations and derived facts point to revisions so that later note edits can be detected and handled.
_Avoid_: current note, latest file, imported document

**Source Revision**:
A versioned snapshot reference for one item from any editable source adapter. Vault Note Revision is the Obsidian-specific form of this broader concept.
_Avoid_: source file, current record

**Personal Context Layer**:
The source-neutral LifeMesh layer that turns personal data sources into task-scoped, permissioned, provenance-backed context for agents. It is the first product capability to validate, not a synonym for RAG or an Obsidian knowledge map.
_Avoid_: RAG layer, Obsidian intelligence map, knowledge base

**Context Slice**:
A small source-backed unit of context selected for a specific task. It carries provenance, source revision, citation status, sensitivity, freshness, and an `evidence_role` that tells the agent whether it is fact, raw material, context, or a lead.
_Avoid_: chunk, search hit

**Evidence Role**:
The per-slice tag on a Context Slice that decides how an agent may use it in a Context Bundle. Initial roles are `fact` (Canonical Fact, usable as evidence), `raw` (Source Revision, source material), `context` (Memory, tone and ranking only), and `lead` (Knowledge Candidate, unverified hint only).
_Avoid_: slice type, output type

**Bundle Artifact**:
The JSON serialization of a Context Bundle, produced by the LifeMesh CLI for an agent to consume. It is a structured file, not a running service, and not Markdown.
_Avoid_: prompt payload, server response, document

**Agent Skill**:
An agent-readable instruction file paired with the CLI that teaches an agent how to invoke the CLI and how to consume a Bundle Artifact by `evidence_role`. It replaces a protocol server as the delivery glue, keeping the interface agent-agnostic.
_Avoid_: plugin, server endpoint, client SDK

**Context Bundle**:
A task-scoped collection of Context Slices assembled for an agent under a specific permission boundary.
_Avoid_: prompt context, retrieval result

**Knowledge Candidate**:
A possible fact, preference, relationship, task, or decision inferred from source-backed context. It is not canonical knowledge until confirmed or otherwise accepted by policy.
_Avoid_: extracted fact, memory

**Knowledge Candidate Type**:
The category of a Knowledge Candidate. Initial types are fact, preference, relationship, task, and decision.
_Avoid_: tag, label, entity type

**Canonical Fact**:
A confirmed, source-backed, revocable fact that LifeMesh can reuse when assembling Context Bundles. It is more durable than a Knowledge Candidate and less identity-shaping than Memory.
_Avoid_: inbox item, accepted candidate, note summary

**Memory**:
Long-lived preference, goal, relational context, or situational context that influences how a Context Bundle is ranked, toned, and styled. It is never cited as factual evidence; when a Memory must be used as a fact, it must go through Fact Acceptance to become a Canonical Fact.
_Avoid_: fact, knowledge, profile, extracted preference

**Fact Acceptance**:
The act or policy path that turns a Knowledge Candidate or manual user statement into a Canonical Fact. Initial paths are user confirmation, manual creation, and low-risk policy acceptance.
_Avoid_: extraction, promotion

**User Confirmation**:
The user action required before a Knowledge Candidate or high-risk action is persisted into canonical facts, long-term memory, or external effects. Ordinary answers should not be blocked by confirmation.
_Avoid_: approval, feedback

**Candidate Lifecycle**:
The lifecycle state of a Knowledge Candidate before it becomes durable knowledge. Initial states are transient, inbox, confirm_required, and discard.
_Avoid_: confirmation status, review queue

**Candidate Inbox**:
A local store (phase 1: a JSON file) where Knowledge Candidates wait for user confirmation. Users confirm, edit, merge, defer, or discard candidates via CLI, asynchronously and in batches; the dashboard shows the inbox read-only and does not write back.
_Avoid_: approval queue, task list, notification center

**Source-Backed Answer**:
An answer that cites the Vault Notes or other source assets used to produce it. It must distinguish source facts from summaries and model inferences.
_Avoid_: AI answer, search result

**Vault Index Scope**:
The subset of an Obsidian Vault that LifeMesh is allowed to read for a given index run. The initial scope is read-only Markdown content with explicit exclusions for operational folders, trash, archives, temporary notes, and attachment binary content.
_Avoid_: full vault import, scan everything

**Stale Source**:
A previously indexed source revision that no longer matches the current Vault Note because the note was edited, moved, deleted, or excluded from the Vault Index Scope.
_Avoid_: outdated result, stale cache

**Citation Status**:
The freshness state of a source citation in a Source-Backed Answer. Initial statuses are current, stale, and missing.
_Avoid_: validity flag, citation health
