from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXCLUDED_DIRS = {".git", ".obsidian", "_attachments", "Trash", "_archives", "tmp"}
SENSITIVITY_LEVELS = ["Public", "Internal", "Private", "Sensitive", "Restricted"]
SENSITIVITY_RANK = {name.lower(): index for index, name in enumerate(SENSITIVITY_LEVELS)}
DEFAULT_NOTE_SENSITIVITY = "Private"


@dataclass(frozen=True)
class SourceRevision:
    note_path: str
    mtime: str
    size: int
    content_hash: str
    indexed_at: str

    @property
    def revision_id(self) -> str:
        return f"rev#{self.content_hash}"


@dataclass(frozen=True)
class Section:
    note_path: str
    heading: str
    line_range: tuple[int, int]
    content: str
    sensitivity: str
    revision: SourceRevision


def build_bundle(
    *,
    task: str,
    vault_path: Path,
    max_slices: int,
    sensitivity_cap: str,
    state_path: Path | None = None,
) -> dict[str, Any]:
    if max_slices < 1:
        raise ValueError("--max-slices must be at least 1")
    normalized_cap = _normalize_sensitivity(sensitivity_cap)
    if normalized_cap is None:
        raise ValueError(f"Unknown sensitivity cap: {sensitivity_cap}")
    if not vault_path.exists():
        raise FileNotFoundError(f"Obsidian vault not found: {vault_path}")
    if not vault_path.is_dir():
        raise NotADirectoryError(f"Obsidian vault is not a directory: {vault_path}")

    assembled_at = _utc_now()
    previous_state = _load_state(state_path)
    sections, revisions, excluded_sources = _scan_vault(vault_path, assembled_at, normalized_cap)
    freshness_report = _build_freshness_report(previous_state, revisions)
    scored_sections = _rank_sections(task, sections)

    slices = [
        _section_to_slice(index, section)
        for index, section in enumerate(scored_sections[:max_slices], start=1)
    ]

    if state_path:
        _save_state(state_path, revisions, assembled_at)

    return {
        "schema_version": "1",
        "bundle_id": str(uuid.uuid4()),
        "task": {"description": task, "agent_capability": "search"},
        "permission_scope": {
            "allowed_sources": ["obsidian"],
            "sensitivity_cap": normalized_cap,
        },
        "assembled_at": assembled_at,
        "slices": slices,
        "excluded_sources": excluded_sources,
        "freshness_report": freshness_report,
    }


def _scan_vault(
    vault_path: Path,
    indexed_at: str,
    sensitivity_cap: str,
) -> tuple[list[Section], dict[str, SourceRevision], list[dict[str, str]]]:
    sections: list[Section] = []
    revisions: dict[str, SourceRevision] = {}
    excluded_sources: list[dict[str, str]] = []

    for root, dirs, files in os.walk(vault_path):
        root_path = Path(root)
        kept_dirs = []
        for dirname in sorted(dirs):
            if dirname in EXCLUDED_DIRS:
                excluded_sources.append({
                    "source": "obsidian",
                    "path": _relative_path(root_path / dirname, vault_path),
                    "reason": "index_scope_excluded",
                })
            else:
                kept_dirs.append(dirname)
        dirs[:] = kept_dirs

        for filename in sorted(files):
            path = root_path / filename
            if path.suffix.lower() != ".md":
                continue
            note_path = _relative_path(path, vault_path)
            text = path.read_text(encoding="utf-8", errors="replace")
            metadata, content_start = _parse_frontmatter(text)
            sensitivity = _normalize_sensitivity(metadata.get("sensitivity"))
            if sensitivity is None:
                excluded_sources.append({
                    "source": "obsidian",
                    "path": note_path,
                    "reason": "unknown_sensitivity",
                    "sensitivity": metadata.get("sensitivity", ""),
                })
                continue
            if _sensitivity_rank(sensitivity) > _sensitivity_rank(sensitivity_cap):
                excluded_sources.append({
                    "source": "obsidian",
                    "path": note_path,
                    "reason": "sensitivity_exceeds_cap",
                    "sensitivity": sensitivity,
                    "sensitivity_cap": sensitivity_cap,
                })
                continue
            revision = _source_revision(path, vault_path, indexed_at, text)
            revisions[note_path] = revision
            sections.extend(_extract_sections(note_path, text, revision, sensitivity, content_start))

    return sections, revisions, excluded_sources


def _source_revision(path: Path, vault_path: Path, indexed_at: str, text: str) -> SourceRevision:
    stat = path.stat()
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return SourceRevision(
        note_path=_relative_path(path, vault_path),
        mtime=_iso_from_timestamp(stat.st_mtime),
        size=stat.st_size,
        content_hash=f"sha256:{digest}",
        indexed_at=indexed_at,
    )


def _extract_sections(
    note_path: str,
    text: str,
    revision: SourceRevision,
    sensitivity: str,
    content_start: int,
) -> list[Section]:
    lines = text.splitlines()

    heading_positions: list[tuple[int, str]] = []
    for index in range(content_start, len(lines)):
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", lines[index])
        if match:
            heading_positions.append((index, lines[index].strip()))

    if not heading_positions:
        content = "\n".join(lines[content_start:]).strip()
        if not content:
            return []
        return [Section(note_path, "(document)", (content_start + 1, len(lines)), content, sensitivity, revision)]

    sections: list[Section] = []
    for position, (start, heading) in enumerate(heading_positions):
        end = heading_positions[position + 1][0] - 1 if position + 1 < len(heading_positions) else len(lines) - 1
        content_lines = lines[start : end + 1]
        content = "\n".join(content_lines).strip()
        if content:
            sections.append(Section(note_path, heading, (start + 1, end + 1), content, sensitivity, revision))
    return sections


def _rank_sections(task: str, sections: list[Section]) -> list[Section]:
    terms = _query_terms(task)
    ranked: list[tuple[float, str, int, Section]] = []
    for order, section in enumerate(sections):
        heading = section.heading.lower()
        haystack = f"{section.note_path}\n{section.heading}\n{section.content}".lower()
        matched_terms = [term for term in terms if term in haystack]
        score = (
            len(set(matched_terms)) * 100
            + sum(min(haystack.count(term), 2) for term in matched_terms) * 10
            + sum(1 for term in terms if term in heading) * 50
            - min(len(section.content) / 120, 80)
        )
        if score > 0:
            ranked.append((score, section.note_path, order, section))
    ranked.sort(key=lambda item: (-item[0], item[1], item[2]))
    return [item[3] for item in ranked]


def _query_terms(task: str) -> list[str]:
    lower = task.lower()
    terms: set[str] = set()
    for token in re.findall(r"[a-z0-9][a-z0-9_-]+", lower):
        terms.add(token)
    for run in re.findall(r"[\u4e00-\u9fff]+", task):
        if len(run) == 1:
            terms.add(run)
        else:
            for index in range(len(run) - 1):
                terms.add(run[index : index + 2].lower())
    return sorted(terms, key=len, reverse=True)


def _section_to_slice(index: int, section: Section) -> dict[str, Any]:
    revision = section.revision
    return {
        "slice_id": f"s{index}",
        "evidence_role": "raw",
        "provenance": {
            "source": "obsidian",
            "note_path": revision.note_path,
            "revision_id": revision.revision_id,
            "mtime": revision.mtime,
            "size": revision.size,
            "content_hash": revision.content_hash,
            "indexed_at": revision.indexed_at,
        },
        "citation_status": "current",
        "sensitivity": section.sensitivity,
        "heading": section.heading,
        "line_range": [section.line_range[0], section.line_range[1]],
        "content": section.content,
    }


def _parse_frontmatter(text: str) -> tuple[dict[str, str], int]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, 0

    metadata: dict[str, str] = {}
    for index in range(1, len(lines)):
        line = lines[index].strip()
        if line == "---":
            return metadata, index + 1
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip().lower()] = value.strip().strip("\"'")
    return {}, 0


def _normalize_sensitivity(value: str | None) -> str | None:
    if value is None or not value.strip():
        return DEFAULT_NOTE_SENSITIVITY
    rank = SENSITIVITY_RANK.get(value.strip().lower())
    if rank is None:
        return None
    return SENSITIVITY_LEVELS[rank]


def _sensitivity_rank(value: str) -> int:
    return SENSITIVITY_RANK[value.lower()]


def _load_state(state_path: Path | None) -> dict[str, Any]:
    if not state_path or not state_path.exists():
        return {"revisions": {}}
    return json.loads(state_path.read_text(encoding="utf-8"))


def _save_state(state_path: Path, revisions: dict[str, SourceRevision], indexed_at: str) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "schema_version": "1",
        "indexed_at": indexed_at,
        "revisions": {
            note_path: {
                "revision_id": revision.revision_id,
                "content_hash": revision.content_hash,
                "mtime": revision.mtime,
                "size": revision.size,
            }
            for note_path, revision in sorted(revisions.items())
        },
    }
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _build_freshness_report(
    previous_state: dict[str, Any],
    revisions: dict[str, SourceRevision],
) -> list[dict[str, str]]:
    report: list[dict[str, str]] = []
    previous_revisions = previous_state.get("revisions", {})
    for note_path, previous in sorted(previous_revisions.items()):
        current = revisions.get(note_path)
        previous_revision_id = str(previous.get("revision_id", ""))
        if current is None:
            report.append({
                "source": "obsidian",
                "note_path": note_path,
                "revision_id": previous_revision_id,
                "citation_status": "missing",
                "note": "Source is no longer available in the current index scope.",
            })
        elif current.revision_id != previous_revision_id:
            report.append({
                "source": "obsidian",
                "note_path": note_path,
                "revision_id": previous_revision_id,
                "current_revision_id": current.revision_id,
                "citation_status": "stale",
                "note": "Source changed since the previous index state; use the current revision for new answers.",
            })
    return report


def _relative_path(path: Path, vault_path: Path) -> str:
    return path.relative_to(vault_path).as_posix()


def _iso_from_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace("+00:00", "Z")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
