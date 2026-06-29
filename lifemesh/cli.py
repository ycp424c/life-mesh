from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .obsidian import build_bundle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lifemesh")
    subparsers = parser.add_subparsers(dest="command", required=True)

    bundle_parser = subparsers.add_parser("bundle", help="Build a JSON Context Bundle")
    bundle_parser.add_argument("task", help="Natural language task")
    bundle_parser.add_argument("--source", default="obsidian", choices=["obsidian"])
    bundle_parser.add_argument("--out", help="Write bundle JSON to this path")
    bundle_parser.add_argument("--max-slices", type=int, default=20)
    bundle_parser.add_argument("--sensitivity-cap", default="Private")
    bundle_parser.add_argument(
        "--vault",
        default=os.environ.get("LIFEMESH_OBSIDIAN_VAULT"),
        help="Obsidian vault path; required unless LIFEMESH_OBSIDIAN_VAULT is set",
    )
    bundle_parser.add_argument(
        "--state",
        help="Optional index state file for stale/missing detection in the prototype",
    )

    args = parser.parse_args(argv)

    if args.command == "bundle":
        if not args.vault:
            bundle_parser.error("--vault is required unless LIFEMESH_OBSIDIAN_VAULT is set")
        bundle = build_bundle(
            task=args.task,
            vault_path=Path(args.vault),
            max_slices=args.max_slices,
            sensitivity_cap=args.sensitivity_cap,
            state_path=Path(args.state) if args.state else None,
        )
        output = json.dumps(bundle, ensure_ascii=False, indent=2) + "\n"
        if args.out:
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(output, encoding="utf-8")
        else:
            sys.stdout.write(output)
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2
