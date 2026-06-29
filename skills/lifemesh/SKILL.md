---
name: lifemesh
description: Use LifeMesh when a task needs the user's personal information across connected sources, or when personal context should be captured into the local LifeMesh inbox.
---

# LifeMesh Agent Skill

Use this skill when the task needs the user's personal information or long-lived context across connected sources. Do not limit use to Obsidian; Obsidian is only the first Source Adapter.

## Current Capability

The current implementation supports the Obsidian bundle path:

```bash
bin/lifemesh bundle "<task>" --source obsidian --vault /path/to/vault --out /tmp/lifemesh-bundle.json
```

You can also set the vault path explicitly with an environment variable:

```bash
LIFEMESH_OBSIDIAN_VAULT=/path/to/vault bin/lifemesh bundle "<task>" --source obsidian --out /tmp/lifemesh-bundle.json
```

The command returns a JSON Context Bundle. It does not answer the user directly.

It also supports Manual Input as a local inbox and retrieval source:

```bash
bin/lifemesh input add --kind note --text "..."
bin/lifemesh input search "<query>"
bin/lifemesh input show <input-id>
bin/lifemesh input update <input-id> ...
bin/lifemesh input revoke <input-id>
bin/lifemesh input delete <input-id>
bin/lifemesh input promote <input-id> --to task|event|memory|fact|candidate ...
bin/lifemesh bundle "<task>" --source all --vault /path/to/vault
```

Manual Input is backed by `~/.lifemesh/lifemesh.db`, SQLite FTS, optional sqlite-vec, local LM Studio embeddings, and local LM Studio VLM extraction for screenshots. Local model/vector configuration lives in `~/.lifemesh/config.json`, environment variables, or CLI args:

```json
{
  "lmstudio_base_url": "http://localhost:1234/v1",
  "embedding_model": "<local-embedding-model>",
  "vlm_model": "<local-vlm-model>",
  "sqlite_vec_extension": "/path/to/vec0"
}
```

Manual Input rules:

- If config is missing, sqlite-vec cannot load, or LM Studio calls fail, Manual Input degrades to SQLite/FTS or metadata-only; inspect the returned `embedding_status`, `extraction_status`, audit payload, and Bundle result before claiming searchability.
- Agent may auto-capture non-sensitive personal data that is worth remembering into Inbox, but must use `--auto-captured`.
- After auto-capture, the response must state input id, kind, summary, sensitivity, and Bundle availability.
- `auto_captured` records are not facts. They may enter Bundle only as `lead`.
- Agent must not auto-promote any record to Task, Event, Memory, Canonical Fact, or Knowledge Candidate.
- Promote requires explicit user confirmation and explicit target fields.
- Agent must not auto-capture clearly sensitive information. User-explicit Sensitive information may be captured locally, but must be marked `Sensitive` and is excluded from normal Bundle use unless the user explicitly authorizes that sensitivity cap.

## How To Consume The Bundle

- Use only `slices[]` with `evidence_role: "raw"` or `"fact"` for factual claims.
- Cite source-specific provenance:
  - Obsidian: `provenance.note_path`, `heading`, `line_range`, and `citation_status`.
  - Manual Input: `provenance.input_id`, `kind`, `status`, `content_hash`, and `citation_status`.
- Treat `citation_status: "current"` as usable source-backed evidence.
- Treat `freshness_report` entries with `stale`, `missing`, `revoked`, or deleted tombstones as warnings; do not use old content as evidence for a new factual answer.
- Do not treat `context` or `lead` slices as facts.
- When a `lead` came from `auto_captured` Manual Input, explicitly say it is unreviewed.

## Boundaries

- Do not call write-side commands unless the CLI supports them in the current checkout.
- Do not promote or revoke records unless the user explicitly asks.
- Do not use stale, missing, revoked, or deleted sources as evidence.
- Do not hide uncertainty: if a bundle has no relevant slices, say that LifeMesh did not find source-backed context.
- Do not modify the Obsidian vault.
- Do not send Manual Input content to remote embedding or vision providers by default; the implemented provider target is local LM Studio.
