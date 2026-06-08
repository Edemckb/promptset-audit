from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .audit import audit_file, split_file


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="promptset-audit",
        description="Audit JSONL prompt datasets for image-generation experiments.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit = subparsers.add_parser("audit", help="Validate and summarise a JSONL dataset")
    audit.add_argument("path", type=Path)
    audit.add_argument("--max-prompt-length", type=int, default=1000)
    audit.add_argument("--json", action="store_true", dest="as_json")
    audit.add_argument("--strict", action="store_true", help="Treat warnings as failures")

    split = subparsers.add_parser("split", help="Create deterministic train and validation files")
    split.add_argument("path", type=Path)
    split.add_argument("output_dir", type=Path)
    split.add_argument("--validation-ratio", type=float, default=0.1)
    split.add_argument("--salt", default="promptset-audit")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "audit":
        report = audit_file(args.path, max_prompt_length=args.max_prompt_length)
        if args.as_json:
            print(json.dumps(report.to_dict(), indent=2))
        else:
            print(
                f"{report.path}: {report.valid_records} valid records, "
                f"{report.unique_prompts} unique prompts, "
                f"{report.errors} errors, {report.warnings} warnings"
            )
            for finding in report.findings:
                location = f" line {finding.line}" if finding.line else ""
                print(f"  {finding.severity.upper():7} {finding.code}{location} - {finding.message}")
        return int(report.errors > 0 or (args.strict and report.warnings > 0))

    train, validation, counts = split_file(
        args.path,
        args.output_dir,
        validation_ratio=args.validation_ratio,
        salt=args.salt,
    )
    print(
        f"Wrote {counts['train']} train and {counts['validation']} validation records "
        f"to {train.parent}. Skipped {counts['duplicates_skipped']} duplicates."
    )
    return 0

