from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    message: str
    line: int | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class AuditReport:
    path: str
    total_lines: int
    valid_records: int
    unique_prompts: int
    findings: tuple[Finding, ...]

    @property
    def errors(self) -> int:
        return sum(item.severity == "error" for item in self.findings)

    @property
    def warnings(self) -> int:
        return sum(item.severity == "warning" for item in self.findings)

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "total_lines": self.total_lines,
            "valid_records": self.valid_records,
            "unique_prompts": self.unique_prompts,
            "errors": self.errors,
            "warnings": self.warnings,
            "findings": [item.to_dict() for item in self.findings],
        }


def normalise_prompt(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _read_records(path: Path) -> tuple[list[tuple[int, dict[str, Any]]], list[Finding], int]:
    records: list[tuple[int, dict[str, Any]]] = []
    findings: list[Finding] = []
    total = 0
    with path.open("r", encoding="utf-8") as stream:
        for line_number, raw_line in enumerate(stream, 1):
            total = line_number
            if not raw_line.strip():
                continue
            try:
                value = json.loads(raw_line)
            except json.JSONDecodeError as error:
                findings.append(
                    Finding("error", "invalid-json", f"Invalid JSON: {error.msg}.", line_number)
                )
                continue
            if not isinstance(value, dict):
                findings.append(Finding("error", "not-an-object", "Each JSONL row must be an object.", line_number))
                continue
            records.append((line_number, value))
    return records, findings, total


def audit_file(path: str | Path, *, max_prompt_length: int = 1000) -> AuditReport:
    dataset_path = Path(path)
    if not dataset_path.exists():
        finding = Finding("error", "file-not-found", "Dataset file does not exist.")
        return AuditReport(str(dataset_path), 0, 0, 0, (finding,))

    records, findings, total_lines = _read_records(dataset_path)
    prompt_lines: dict[str, list[int]] = {}

    for line_number, record in records:
        prompt = record.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            findings.append(Finding("error", "missing-prompt", "A non-empty string prompt is required.", line_number))
            continue

        canonical = normalise_prompt(prompt)
        prompt_lines.setdefault(canonical, []).append(line_number)
        if len(prompt) > max_prompt_length:
            findings.append(
                Finding(
                    "warning",
                    "long-prompt",
                    f"Prompt has {len(prompt)} characters; configured maximum is {max_prompt_length}.",
                    line_number,
                )
            )

        for dimension in ("width", "height"):
            value = record.get(dimension)
            if value is None:
                continue
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                findings.append(
                    Finding("error", f"invalid-{dimension}", f"{dimension} must be a positive integer.", line_number)
                )
            elif value % 8:
                findings.append(
                    Finding("warning", f"unaligned-{dimension}", f"{dimension} should be divisible by 8.", line_number)
                )

        seed = record.get("seed")
        if seed is not None and (not isinstance(seed, int) or isinstance(seed, bool)):
            findings.append(Finding("warning", "invalid-seed", "seed should be an integer.", line_number))

    for lines in prompt_lines.values():
        if len(lines) > 1:
            findings.append(
                Finding(
                    "warning",
                    "duplicate-prompt",
                    f"Duplicate prompt appears on lines {', '.join(map(str, lines))}.",
                    lines[1],
                )
            )

    valid_records = sum(
        isinstance(record.get("prompt"), str) and bool(record["prompt"].strip())
        for _, record in records
    )
    return AuditReport(
        str(dataset_path),
        total_lines,
        valid_records,
        len(prompt_lines),
        tuple(findings),
    )


def split_file(
    path: str | Path,
    output_dir: str | Path,
    *,
    validation_ratio: float = 0.1,
    salt: str = "promptset-audit",
) -> tuple[Path, Path, Counter[str]]:
    if not 0 < validation_ratio < 1:
        raise ValueError("validation_ratio must be between 0 and 1")

    dataset_path = Path(path)
    records, findings, _ = _read_records(dataset_path)
    if any(item.severity == "error" for item in findings):
        raise ValueError("Cannot split a dataset containing invalid JSON rows")

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    train_path = destination / "train.jsonl"
    validation_path = destination / "validation.jsonl"
    counts: Counter[str] = Counter()

    seen: set[str] = set()
    with train_path.open("w", encoding="utf-8") as train, validation_path.open("w", encoding="utf-8") as validation:
        for _, record in records:
            prompt = record.get("prompt")
            if not isinstance(prompt, str) or not prompt.strip():
                continue
            canonical = normalise_prompt(prompt)
            if canonical in seen:
                counts["duplicates_skipped"] += 1
                continue
            seen.add(canonical)
            digest = hashlib.sha256(f"{salt}:{canonical}".encode()).digest()
            bucket = int.from_bytes(digest[:8], "big") / 2**64
            target = validation if bucket < validation_ratio else train
            split = "validation" if target is validation else "train"
            target.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            counts[split] += 1
    return train_path, validation_path, counts
