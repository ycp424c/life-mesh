---
name: lifemesh
description: Use LifeMesh when a task needs the user's personal information across connected sources, or when personal context should be captured into the local LifeMesh inbox.
---

# LifeMesh Agent Skill

Use this skill when the task needs the user's personal information or long-lived context across connected sources. Do not limit use to Obsidian; Obsidian is only the first Source Adapter.

This is the global skill. It can be used from any working directory.

## Local Paths

- LifeMesh repo: `/Users/justynchen/Documents/code/life-mesh`
- CLI: `/Users/justynchen/Documents/code/life-mesh/bin/lifemesh`
- Runtime config: `/Users/justynchen/.lifemesh/config.json`
- Local DB: `/Users/justynchen/.lifemesh/lifemesh.db`
- Raw assets: `/Users/justynchen/.lifemesh/raw-assets/manual-input`

Current local config includes:

- `obsidian_vault`: `/Users/justynchen/Documents/docs/obsidian-default`
- `lmstudio_base_url`: `http://localhost:1234/v1`
- `embedding_model`: `text-embedding-qwen3-embedding-0.6b`
- `vlm_model`: `ornith-1.0-9b`
- `sqlite_vec_extension`: `/Users/justynchen/.lifemesh/extensions/sqlite-vec/0.1.9/vec0.dylib`

The Codex terminal should load Homebrew from `~/.zshenv`, so `python3` should be `/opt/homebrew/bin/python3`. If sqlite-vec reports `enable_load_extension` is missing, run `source ~/.zshenv` or prefix the command with `PATH=/opt/homebrew/bin:$PATH`.

## Current Capability

The implementation supports Obsidian Context Bundle:

```bash
/Users/justynchen/Documents/code/life-mesh/bin/lifemesh bundle "<task>" --source obsidian --out /tmp/lifemesh-bundle.json
```

The vault path is configured globally, so `--vault` is normally unnecessary. If a different vault is needed, pass `--vault /path/to/vault`.

It also supports Manual Input as a local inbox and retrieval source:

```bash
/Users/justynchen/Documents/code/life-mesh/bin/lifemesh input add --kind note --text "..."
/Users/justynchen/Documents/code/life-mesh/bin/lifemesh input search "<query>"
/Users/justynchen/Documents/code/life-mesh/bin/lifemesh input show <input-id>
/Users/justynchen/Documents/code/life-mesh/bin/lifemesh input update <input-id> ...
/Users/justynchen/Documents/code/life-mesh/bin/lifemesh input revoke <input-id>
/Users/justynchen/Documents/code/life-mesh/bin/lifemesh input delete <input-id>
/Users/justynchen/Documents/code/life-mesh/bin/lifemesh input promote <input-id> --to task|event|memory|fact|candidate ...
/Users/justynchen/Documents/code/life-mesh/bin/lifemesh bundle "<task>" --source all --out /tmp/lifemesh-bundle.json
```

Manual Input is backed by `~/.lifemesh/lifemesh.db`, SQLite FTS, sqlite-vec, local LM Studio embeddings, and local LM Studio VLM extraction for screenshots.

RumorClaim / UnverifiedClaim has a structured local CLI MVP:

```bash
/Users/justynchen/Documents/code/life-mesh/bin/lifemesh rumor add --claim-text "..." --claim-type factual_claim --user-relevance medium --impact medium
/Users/justynchen/Documents/code/life-mesh/bin/lifemesh rumor list
/Users/justynchen/Documents/code/life-mesh/bin/lifemesh rumor show <rumor-claim-id>
/Users/justynchen/Documents/code/life-mesh/bin/lifemesh rumor keep <rumor-claim-id> --reason "reviewed and kept"
/Users/justynchen/Documents/code/life-mesh/bin/lifemesh rumor dismiss <rumor-claim-id>
/Users/justynchen/Documents/code/life-mesh/bin/lifemesh rumor promote <rumor-claim-id> --to candidate --statement "..." --type fact
/Users/justynchen/Documents/code/life-mesh/bin/lifemesh bundle "<task>" --source rumor --out /tmp/lifemesh-bundle.json
/Users/justynchen/Documents/code/life-mesh/bin/lifemesh bundle "<task>" --source all --include-unverified --out /tmp/lifemesh-bundle.json
```

This CLI stores only structured claim fields, mentions, minimal source envelope, status, and audit events. It does not ingest raw rumor material or run automatic source adapters yet.

## Quick Checks

Use these before relying on LifeMesh in a task:

```bash
/Users/justynchen/.lmstudio/bin/lms server status
/Users/justynchen/.lmstudio/bin/lms ps
/Users/justynchen/Documents/code/life-mesh/bin/lifemesh input list
sqlite3 /Users/justynchen/.lifemesh/lifemesh.db "select key, value from lifemesh_meta where key like 'vector_%' order by key;"
```

Expected vector state:

```text
vector_error|
vector_status|ready
```

If LM Studio is stopped, start it:

```bash
/Users/justynchen/.lmstudio/bin/lms server start
```

## Manual Input Rules

- If config is missing, sqlite-vec cannot load, or LM Studio calls fail, Manual Input degrades to SQLite/FTS or metadata-only. Inspect `embedding_status`, `extraction_status`, audit payload, and Bundle result before claiming searchability.
- Agent may auto-capture non-sensitive personal data that is worth remembering into Inbox, but must use `--auto-captured`.
- After auto-capture, the response must state input id, kind, summary, sensitivity, and Bundle availability.
- `auto_captured` records are not facts. They may enter Bundle only as `lead`.
- Agent must not auto-promote any record to Task, Event, Memory, Canonical Fact, or Knowledge Candidate.
- Promote requires explicit user confirmation and explicit target fields.
- Agent must not auto-capture clearly sensitive information. User-explicit Sensitive information may be captured locally, but must be marked `Sensitive` and is excluded from normal Bundle use unless the user explicitly authorizes that sensitivity cap.

## RumorClaim Rules

- `rumor add` requires explicit `--user-relevance` and `--impact`; do not omit the triage fields.
- If credibility fields are not supplied, the CLI starts from `evidence_state=unknown` and `assessment=unverified`.
- RumorClaim is never factual evidence. It can enter Bundle only as an unverified `lead` via `--source rumor` or `--source all --include-unverified`.
- `rumor keep` marks a parked claim as `reviewed_parked`; it remains an unverified lead but is skipped by the default review list.
- `evidence_state=contradicted` must use `assessment=contradicted`; contradicted claims are excluded from usable Bundle slices.
- Expired, dismissed, Sensitive-over-cap, stale, missing, revoked, or deleted material must not be used as evidence.
- `rumor promote --to candidate` currently creates a local `rumor_candidate_links` handoff and marks the claim `candidate_created`; it is not a complete Candidate inbox lifecycle.

## How To Consume The Bundle

- Use only `slices[]` with `evidence_role: "raw"` or `"fact"` for factual claims.
- Prefer `slice.citation.label` when showing sources. If `citation.label` is absent, fall back to source-specific provenance.
- Cite source-specific provenance:
  - Obsidian: `provenance.note_path`, `heading`, `line_range`, and `citation_status`.
  - Manual Input: `provenance.input_id`, `kind`, `status`, `content_hash`, and `citation_status`.
- Treat `citation_status: "current"` as usable source-backed evidence.
- Treat `freshness_report` entries with `stale`, `missing`, `revoked`, or deleted tombstones as warnings; do not use old content as evidence for a new factual answer.
- Do not treat `context` or `lead` slices as facts.
- When a `lead` came from `auto_captured` Manual Input, explicitly say it is unreviewed.
- When a Manual Input slice has `retrieval.match_status: "weak"`, describe it as a weakly related lead only; do not call it an exact hit or use it as evidence.
- If a Bundle includes RumorClaim / UnverifiedClaim content, treat it only as `lead`, explicitly mark it unverified, and never use it as factual evidence.
- Do not print raw bundle content unless the user asks; summarize findings and cite provenance.

## Boundaries

- Do not call write-side commands unless the CLI supports them in the current checkout.
- Do not use `rumor` commands to store raw material. They require already-extracted structured claims and must not be treated as fact storage.
- Do not turn unverified rumor material directly into facts, memories, tasks, events, or external actions.
- Do not promote or revoke records unless the user explicitly asks.
- Do not use stale, missing, revoked, or deleted sources as evidence.
- Do not hide uncertainty: if a bundle has no relevant slices, say that LifeMesh did not find source-backed context.
- Do not modify the Obsidian vault.
- Do not send Manual Input content to remote embedding or vision providers by default; the implemented provider target is local LM Studio.
