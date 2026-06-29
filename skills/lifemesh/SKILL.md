---
name: lifemesh
description: Use LifeMesh when a task needs the user's personal information across connected sources. The first implementation supports Obsidian-backed JSON Context Bundles through the local CLI.
---

# LifeMesh Agent Skill

Use this skill when the task needs the user's personal information or long-lived context across connected sources. Do not limit use to Obsidian; Obsidian is only the first Source Adapter.

## Current Capability

The current implementation supports the read-only bundle path:

```bash
bin/lifemesh bundle "<task>" --source obsidian --vault /path/to/vault --out /tmp/lifemesh-bundle.json
```

You can also set the vault path explicitly with an environment variable:

```bash
LIFEMESH_OBSIDIAN_VAULT=/path/to/vault bin/lifemesh bundle "<task>" --source obsidian --out /tmp/lifemesh-bundle.json
```

The command returns a JSON Context Bundle. It does not answer the user directly.

## How To Consume The Bundle

- Use only `slices[]` with `evidence_role: "raw"` or `"fact"` for factual claims.
- Cite `provenance.note_path`, `heading`, `line_range`, and `citation_status`.
- Treat `citation_status: "current"` as usable source-backed evidence.
- Treat `freshness_report` entries with `stale` or `missing` as warnings; do not use old content as evidence for a new factual answer.
- Do not treat `context` or `lead` slices as facts.

## Boundaries

- Do not call write-side commands unless the user explicitly asks. The first implementation is read-only.
- Do not use stale or missing sources as evidence.
- Do not hide uncertainty: if a bundle has no relevant slices, say that LifeMesh did not find source-backed context.
- Do not modify the Obsidian vault.
