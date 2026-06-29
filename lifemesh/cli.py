from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import sys
from pathlib import Path
from typing import Any

from .config import load_config
from .manual_input import MANUAL_KINDS, PROMOTE_TARGETS, ManualInputError, ManualInputStore
from .obsidian import build_bundle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lifemesh")
    subparsers = parser.add_subparsers(dest="command", required=True)

    bundle_parser = subparsers.add_parser("bundle", help="Build a JSON Context Bundle")
    bundle_parser.add_argument("task", help="Natural language task")
    bundle_parser.add_argument("--source", default="obsidian", choices=["all", "obsidian", "manual-input"])
    bundle_parser.add_argument("--out", help="Write bundle JSON to this path")
    bundle_parser.add_argument("--max-slices", type=int, default=20)
    bundle_parser.add_argument("--sensitivity-cap", default="Private")
    _add_config_arguments(bundle_parser)
    bundle_parser.add_argument(
        "--vault",
        help="Obsidian vault path; falls back to LIFEMESH_OBSIDIAN_VAULT or config obsidian_vault",
    )
    bundle_parser.add_argument(
        "--state",
        help="Optional index state file for stale/missing detection in the prototype",
    )

    input_parser = subparsers.add_parser("input", help="Manage local Manual Input records")
    _add_config_arguments(input_parser)
    input_subparsers = input_parser.add_subparsers(dest="input_command", required=True)
    _add_input_parsers(input_subparsers)

    args = parser.parse_args(argv)

    try:
        if args.command == "bundle":
            return _handle_bundle(args, bundle_parser)
        if args.command == "input":
            return _handle_input(args)
    except (ManualInputError, ValueError, FileNotFoundError, NotADirectoryError) as exc:
        sys.stderr.write(f"lifemesh: error: {exc}\n")
        return 2

    parser.error(f"Unsupported command: {args.command}")
    return 2


def _add_config_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--home", help="LifeMesh home; falls back to LIFEMESH_HOME or ~/.lifemesh")
    parser.add_argument("--lmstudio-base-url", help="LM Studio OpenAI-compatible base URL")
    parser.add_argument("--embedding-model", help="LM Studio embedding model name")
    parser.add_argument("--vlm-model", help="LM Studio VLM model name")
    parser.add_argument("--sqlite-vec-extension", help="Path to the sqlite-vec loadable extension")


def _add_input_parsers(input_subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    add_parser = input_subparsers.add_parser("add", help="Add a Manual Input record")
    add_parser.add_argument("--kind", required=True, choices=sorted(MANUAL_KINDS))
    add_parser.add_argument("--text")
    add_parser.add_argument("--file", type=Path)
    add_parser.add_argument("--occurred-at")
    add_parser.add_argument("--starts-at")
    add_parser.add_argument("--ends-at")
    add_parser.add_argument("--due-at")
    add_parser.add_argument("--timezone")
    add_parser.add_argument("--declared-kind")
    add_parser.add_argument("--sensitivity", default="Private")
    add_parser.add_argument("--tag", dest="tags", action="append", default=[])
    add_parser.add_argument("--tags", dest="tags_csv")
    add_parser.add_argument("--source-type", default="manual_cli")
    add_parser.add_argument("--auto-captured", action="store_true")
    add_parser.add_argument("--no-extract", action="store_true")
    add_parser.add_argument("--source-session-id")
    add_parser.add_argument("--source-message-id")
    add_parser.add_argument("--source-excerpt")
    add_parser.add_argument("--captured-reason")

    search_parser = input_subparsers.add_parser("search", help="Search Manual Input records")
    search_parser.add_argument("query")
    search_parser.add_argument("--kind", choices=sorted(MANUAL_KINDS))
    search_parser.add_argument("--status")
    search_parser.add_argument("--since")
    search_parser.add_argument("--until")
    search_parser.add_argument("--sensitivity-cap", default="Private")
    search_parser.add_argument("--limit", type=int, default=20)

    list_parser = input_subparsers.add_parser("list", help="List Manual Input records")
    list_parser.add_argument("--kind", choices=sorted(MANUAL_KINDS))
    list_parser.add_argument("--status")
    list_parser.add_argument("--since")

    show_parser = input_subparsers.add_parser("show", help="Show one Manual Input record")
    show_parser.add_argument("input_id")

    update_parser = input_subparsers.add_parser("update", help="Update and re-embed a Manual Input record")
    update_parser.add_argument("input_id")
    update_parser.add_argument("--kind", choices=sorted(MANUAL_KINDS))
    update_parser.add_argument("--text")
    update_parser.add_argument("--occurred-at")
    update_parser.add_argument("--declared-kind")
    update_parser.add_argument("--sensitivity")
    update_parser.add_argument("--tag", dest="tags", action="append", default=[])
    update_parser.add_argument("--tags", dest="tags_csv")

    revoke_parser = input_subparsers.add_parser("revoke", help="Revoke a Manual Input record")
    revoke_parser.add_argument("input_id")

    delete_parser = input_subparsers.add_parser("delete", help="Delete Manual Input content and managed assets")
    delete_parser.add_argument("input_id")

    promote_parser = input_subparsers.add_parser("promote", help="Promote an input into an inbox-derived object")
    promote_parser.add_argument("input_id")
    promote_parser.add_argument("--to", dest="target_type", required=True, choices=sorted(PROMOTE_TARGETS))
    promote_parser.add_argument("--title")
    promote_parser.add_argument("--due-at")
    promote_parser.add_argument("--status")
    promote_parser.add_argument("--starts-at")
    promote_parser.add_argument("--ends-at")
    promote_parser.add_argument("--timezone")
    promote_parser.add_argument("--text")
    promote_parser.add_argument("--scope")
    promote_parser.add_argument("--confidence")
    promote_parser.add_argument("--statement")
    promote_parser.add_argument("--source-ref", action="append", default=[])
    promote_parser.add_argument("--type")
    promote_parser.add_argument("--risk")


def _handle_bundle(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    config = _load_config_from_args(args, obsidian_vault=args.vault)
    if args.source == "obsidian":
        bundle = _build_obsidian_bundle(args, config, parser)
    elif args.source == "manual-input":
        bundle = _build_manual_bundle(args, config)
    else:
        obsidian_bundle = _build_obsidian_bundle(args, config, parser)
        manual_bundle = _build_manual_bundle(args, config)
        bundle = _merge_bundles(
            task=args.task,
            sensitivity_cap=args.sensitivity_cap,
            max_slices=args.max_slices,
            obsidian_bundle=obsidian_bundle,
            manual_bundle=manual_bundle,
        )
    _emit_json(bundle, Path(args.out) if args.out else None)
    return 0


def _build_obsidian_bundle(
    args: argparse.Namespace,
    config: Any,
    parser: argparse.ArgumentParser,
) -> dict[str, Any]:
    if config.obsidian_vault is None:
        parser.error("--vault is required unless LIFEMESH_OBSIDIAN_VAULT or config obsidian_vault is set")
    return build_bundle(
        task=args.task,
        vault_path=config.obsidian_vault,
        max_slices=args.max_slices,
        sensitivity_cap=args.sensitivity_cap,
        state_path=Path(args.state) if args.state else None,
    )


def _build_manual_bundle(args: argparse.Namespace, config: Any) -> dict[str, Any]:
    return ManualInputStore(config).bundle(
        task=args.task,
        max_slices=args.max_slices,
        sensitivity_cap=args.sensitivity_cap,
    )


def _merge_bundles(
    *,
    task: str,
    sensitivity_cap: str,
    max_slices: int,
    obsidian_bundle: dict[str, Any],
    manual_bundle: dict[str, Any],
) -> dict[str, Any]:
    scored_slices: list[dict[str, Any]] = []
    for index, item in enumerate(obsidian_bundle.get("slices", []), start=1):
        copied = dict(item)
        copied.setdefault("score", max(0.0, 1.0 - index / 1000))
        scored_slices.append(copied)
    scored_slices.extend(dict(item) for item in manual_bundle.get("slices", []))
    scored_slices.sort(key=lambda item: (-float(item.get("score", 0.0)), item.get("slice_id", "")))

    return {
        "schema_version": "1",
        "bundle_id": manual_bundle.get("bundle_id") or obsidian_bundle.get("bundle_id"),
        "task": {"description": task, "agent_capability": "search"},
        "permission_scope": {
            "allowed_sources": ["obsidian", "manual-input"],
            "sensitivity_cap": sensitivity_cap,
        },
        "assembled_at": _utc_now(),
        "slices": scored_slices[:max_slices],
        "excluded_sources": [
            *obsidian_bundle.get("excluded_sources", []),
            *manual_bundle.get("excluded_sources", []),
        ],
        "freshness_report": [
            *obsidian_bundle.get("freshness_report", []),
            *manual_bundle.get("freshness_report", []),
        ],
    }


def _handle_input(args: argparse.Namespace) -> int:
    store = ManualInputStore(_load_config_from_args(args))
    command = args.input_command
    if command == "add":
        result = store.add(
            kind=args.kind,
            text=args.text,
            file_path=args.file,
            occurred_at=args.occurred_at,
            starts_at=args.starts_at,
            ends_at=args.ends_at,
            due_at=args.due_at,
            timezone_name=args.timezone,
            declared_kind=args.declared_kind,
            sensitivity=args.sensitivity,
            tags=_parse_tags(args.tags, args.tags_csv),
            source_type=args.source_type,
            auto_captured=args.auto_captured,
            no_extract=args.no_extract,
            source_session_id=args.source_session_id,
            source_message_id=args.source_message_id,
            source_excerpt=args.source_excerpt,
            captured_reason=args.captured_reason,
        )
    elif command == "search":
        hits = store.search(
            args.query,
            kind=args.kind,
            status=args.status,
            since=args.since,
            until=args.until,
            sensitivity_cap=args.sensitivity_cap,
            limit=args.limit,
        )
        result = [{"input_id": hit.input_id, "score": hit.score, "record": hit.record} for hit in hits]
    elif command == "list":
        result = store.list_inputs(kind=args.kind, status=args.status, since=args.since)
    elif command == "show":
        result = store.show(args.input_id)
    elif command == "update":
        result = store.update(
            args.input_id,
            kind=args.kind,
            text=args.text,
            occurred_at=args.occurred_at,
            declared_kind=args.declared_kind,
            sensitivity=args.sensitivity,
            tags=_parse_tags(args.tags, args.tags_csv) if args.tags or args.tags_csv else None,
        )
    elif command == "revoke":
        result = store.revoke(args.input_id)
    elif command == "delete":
        result = store.delete(args.input_id)
    elif command == "promote":
        result = store.promote(args.input_id, args.target_type, _promote_payload(args))
    else:
        raise ManualInputError(f"Unsupported input command: {command}")
    _emit_json(result)
    return 0


def _load_config_from_args(args: argparse.Namespace, *, obsidian_vault: str | None = None) -> Any:
    return load_config(
        home=args.home,
        obsidian_vault=obsidian_vault,
        lmstudio_base_url=args.lmstudio_base_url,
        embedding_model=args.embedding_model,
        vlm_model=args.vlm_model,
        sqlite_vec_extension=args.sqlite_vec_extension,
    )


def _promote_payload(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key in [
        "title",
        "due_at",
        "status",
        "starts_at",
        "ends_at",
        "timezone",
        "text",
        "scope",
        "confidence",
        "statement",
        "type",
        "risk",
    ]:
        value = getattr(args, key)
        if value is not None:
            payload[key] = value
    if args.source_ref:
        payload["source_refs"] = args.source_ref
    return payload


def _parse_tags(values: list[str], csv: str | None) -> list[str]:
    tags: list[str] = []
    for value in values:
        tags.extend(part.strip() for part in value.split(",") if part.strip())
    if csv:
        tags.extend(part.strip() for part in csv.split(",") if part.strip())
    return tags


def _emit_json(data: Any, out_path: Path | None = None) -> None:
    output = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
