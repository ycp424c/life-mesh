from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .assembler import BundleAssembler
from .config import load_config
from .manual_input import (
    MANUAL_KINDS,
    PROMOTE_TARGETS,
    VECTOR_EVIDENCE_THRESHOLD,
    VECTOR_LEAD_THRESHOLD,
    ManualInputError,
    ManualInputStore,
)
from .obsidian import build_bundle, retrieve_candidates as retrieve_obsidian_candidates
from .rumor_claims import (
    ASSESSMENTS,
    CANDIDATE_TYPES,
    CLAIM_QUALITIES,
    CLAIM_TYPES,
    EVIDENCE_STATES,
    EXTRACTION_CONFIDENCE_LEVELS,
    IMPACT_LEVELS,
    RAW_RETENTION_VALUES,
    REVIEW_QUEUES,
    RUMOR_STATUSES,
    USER_RELEVANCE_LEVELS,
    RumorClaimError,
    RumorClaimStore,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lifemesh")
    subparsers = parser.add_subparsers(dest="command", required=True)

    bundle_parser = subparsers.add_parser("bundle", help="Build a JSON Context Bundle")
    bundle_parser.add_argument("task", help="Natural language task")
    bundle_parser.add_argument("--source", default="obsidian", choices=["all", "obsidian", "manual-input", "rumor"])
    bundle_parser.add_argument("--out", help="Write bundle JSON to this path")
    bundle_parser.add_argument("--max-slices", type=int, default=20)
    bundle_parser.add_argument("--sensitivity-cap", default="Private")
    bundle_parser.add_argument(
        "--include-unverified",
        action="store_true",
        help="Allow unverified RumorClaim leads when source is all",
    )
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

    rumor_parser = subparsers.add_parser("rumor", help="Manage unverified RumorClaim records")
    _add_config_arguments(rumor_parser)
    rumor_subparsers = rumor_parser.add_subparsers(dest="rumor_command", required=True)
    _add_rumor_parsers(rumor_subparsers)

    args = parser.parse_args(argv)

    try:
        if args.command == "bundle":
            return _handle_bundle(args, bundle_parser)
        if args.command == "input":
            return _handle_input(args)
        if args.command == "rumor":
            return _handle_rumor(args)
    except (ManualInputError, RumorClaimError, ValueError, FileNotFoundError, NotADirectoryError) as exc:
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


def _add_rumor_parsers(rumor_subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    add_parser = rumor_subparsers.add_parser("add", help="Add a structured RumorClaim")
    add_parser.add_argument("--claim-text", required=True)
    add_parser.add_argument("--claim-type", required=True, choices=sorted(CLAIM_TYPES))
    add_parser.add_argument("--entity-mention", dest="entity_mentions", action="append", default=[])
    add_parser.add_argument("--relation-mention", dest="relation_mentions", action="append", default=[])
    add_parser.add_argument("--user-relevance", required=True, choices=USER_RELEVANCE_LEVELS)
    add_parser.add_argument("--relevance-reason", default="")
    add_parser.add_argument("--impact", required=True, choices=IMPACT_LEVELS)
    add_parser.add_argument("--impact-reason", default="")
    add_parser.add_argument("--extraction-confidence", default="medium", choices=sorted(EXTRACTION_CONFIDENCE_LEVELS))
    add_parser.add_argument("--evidence-state", default="unknown", choices=sorted(EVIDENCE_STATES))
    add_parser.add_argument("--claim-quality", default="specific", choices=sorted(CLAIM_QUALITIES))
    add_parser.add_argument("--assessment", choices=sorted(ASSESSMENTS))
    add_parser.add_argument("--sensitivity", default="Private")
    add_parser.add_argument("--review-queue", choices=sorted(REVIEW_QUEUES))
    add_parser.add_argument("--source-adapter", default="manual_cli")
    add_parser.add_argument("--source-item-id")
    add_parser.add_argument("--material-fingerprint")
    add_parser.add_argument("--source-summary")
    add_parser.add_argument("--raw-retention", default="none", choices=sorted(RAW_RETENTION_VALUES))
    add_parser.add_argument("--review-pointer")
    add_parser.add_argument("--expires-at")

    list_parser = rumor_subparsers.add_parser("list", help="List RumorClaims")
    list_parser.add_argument("--status", choices=sorted(RUMOR_STATUSES))
    list_parser.add_argument("--queue", choices=sorted(REVIEW_QUEUES))
    list_parser.add_argument("--sensitivity-cap", default="Private")
    list_parser.add_argument("--limit", type=int, default=20)

    show_parser = rumor_subparsers.add_parser("show", help="Show one RumorClaim")
    show_parser.add_argument("rumor_claim_id")

    dismiss_parser = rumor_subparsers.add_parser("dismiss", help="Dismiss a parked RumorClaim")
    dismiss_parser.add_argument("rumor_claim_id")
    dismiss_parser.add_argument("--reason")

    expire_parser = rumor_subparsers.add_parser("expire", help="Expire a parked RumorClaim")
    expire_parser.add_argument("rumor_claim_id")

    promote_parser = rumor_subparsers.add_parser("promote", help="Promote a RumorClaim into a Knowledge Candidate")
    promote_parser.add_argument("rumor_claim_id")
    promote_parser.add_argument("--to", dest="target_type", required=True, choices=["candidate"])
    promote_parser.add_argument("--statement", required=True)
    promote_parser.add_argument("--type", required=True, choices=sorted(CANDIDATE_TYPES))
    promote_parser.add_argument("--confidence")
    promote_parser.add_argument("--risk")
    promote_parser.add_argument("--source-ref", action="append", default=[])


def _handle_bundle(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.max_slices < 1:
        raise ValueError("--max-slices must be at least 1")
    config = _load_config_from_args(args, obsidian_vault=args.vault)
    if args.source == "obsidian":
        bundle = _build_obsidian_bundle(args, config, parser)
    elif args.source == "manual-input":
        bundle = _build_manual_bundle(args, config)
    elif args.source == "rumor":
        bundle = _build_rumor_bundle(args, config)
    else:
        candidate_limit = max(args.max_slices * 4, 20)
        obsidian_result = _retrieve_obsidian_candidates(args, config, parser, candidate_limit)
        manual_result = ManualInputStore(config).retrieve_candidates(
            task=args.task,
            max_candidates=candidate_limit,
            sensitivity_cap=args.sensitivity_cap,
        )
        candidates = [*obsidian_result.candidates, *manual_result.candidates]
        excluded_sources = [*obsidian_result.excluded_sources, *manual_result.excluded_sources]
        freshness_report = [*obsidian_result.freshness_report, *manual_result.freshness_report]
        allowed_sources = ["obsidian", "manual-input"]
        if args.include_unverified:
            rumor_result = RumorClaimStore(config).retrieve_candidates(
                task=args.task,
                max_candidates=candidate_limit,
                sensitivity_cap=args.sensitivity_cap,
            )
            candidates.extend(rumor_result.candidates)
            excluded_sources.extend(rumor_result.excluded_sources)
            freshness_report.extend(rumor_result.freshness_report)
            allowed_sources.append("rumor")
        bundle = BundleAssembler().assemble(
            task=args.task,
            allowed_sources=allowed_sources,
            sensitivity_cap=args.sensitivity_cap,
            max_slices=args.max_slices,
            candidates=candidates,
            excluded_sources=excluded_sources,
            freshness_report=freshness_report,
            include_unverified=args.include_unverified,
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


def _retrieve_obsidian_candidates(
    args: argparse.Namespace,
    config: Any,
    parser: argparse.ArgumentParser,
    max_candidates: int,
) -> Any:
    if config.obsidian_vault is None:
        parser.error("--vault is required unless LIFEMESH_OBSIDIAN_VAULT or config obsidian_vault is set")
    return retrieve_obsidian_candidates(
        task=args.task,
        vault_path=config.obsidian_vault,
        max_candidates=max_candidates,
        sensitivity_cap=args.sensitivity_cap,
        state_path=Path(args.state) if args.state else None,
    )


def _build_manual_bundle(args: argparse.Namespace, config: Any) -> dict[str, Any]:
    return ManualInputStore(config).bundle(
        task=args.task,
        max_slices=args.max_slices,
        sensitivity_cap=args.sensitivity_cap,
    )


def _build_rumor_bundle(args: argparse.Namespace, config: Any) -> dict[str, Any]:
    return RumorClaimStore(config).bundle(
        task=args.task,
        max_slices=args.max_slices,
        sensitivity_cap=args.sensitivity_cap,
    )


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
        result = [
            {
                "input_id": hit.input_id,
                "score": hit.score,
                "match_status": hit.match_status,
                "match_reason": hit.match_reason,
                "evidence_eligible": hit.evidence_eligible,
                "score_breakdown": {
                    "vector": hit.vector_score,
                    "fts": hit.fts_score,
                    "recency": hit.recency_score,
                    "kind": hit.kind_score,
                    "thresholds": {
                        "vector_evidence": VECTOR_EVIDENCE_THRESHOLD,
                        "vector_lead": VECTOR_LEAD_THRESHOLD,
                    },
                },
                "record": hit.record,
            }
            for hit in hits
        ]
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


def _handle_rumor(args: argparse.Namespace) -> int:
    store = RumorClaimStore(_load_config_from_args(args))
    command = args.rumor_command
    if command == "add":
        result = store.add(
            claim_text=args.claim_text,
            claim_type=args.claim_type,
            entity_mentions=args.entity_mentions,
            relation_mentions=args.relation_mentions,
            user_relevance=args.user_relevance,
            relevance_reason=args.relevance_reason,
            impact=args.impact,
            impact_reason=args.impact_reason,
            extraction_confidence=args.extraction_confidence,
            evidence_state=args.evidence_state,
            claim_quality=args.claim_quality,
            assessment=args.assessment,
            sensitivity=args.sensitivity,
            review_queue=args.review_queue,
            source_adapter=args.source_adapter,
            source_item_id=args.source_item_id,
            material_fingerprint=args.material_fingerprint,
            source_summary=args.source_summary,
            raw_retention=args.raw_retention,
            review_pointer=args.review_pointer,
            expires_at=args.expires_at,
        )
    elif command == "list":
        result = store.list_claims(
            status=args.status,
            queue=args.queue,
            sensitivity_cap=args.sensitivity_cap,
            limit=args.limit,
        )
    elif command == "show":
        result = store.show(args.rumor_claim_id)
    elif command == "dismiss":
        result = store.dismiss(args.rumor_claim_id, reason=args.reason)
    elif command == "expire":
        result = store.expire(args.rumor_claim_id)
    elif command == "promote":
        if args.target_type != "candidate":
            raise RumorClaimError(f"Unsupported rumor promote target: {args.target_type}")
        result = store.promote(args.rumor_claim_id, _rumor_promote_payload(args))
    else:
        raise RumorClaimError(f"Unsupported rumor command: {command}")
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


def _rumor_promote_payload(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "statement": args.statement,
        "type": args.type,
    }
    for key in ["confidence", "risk"]:
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
