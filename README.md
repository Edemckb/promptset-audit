# promptset-audit

[![CI](https://github.com/Edemckb/promptset-audit/actions/workflows/ci.yml/badge.svg)](https://github.com/Edemckb/promptset-audit/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

`promptset-audit` is a dependency-free command-line tool for reviewing JSONL prompt datasets used in image-generation experiments.

It validates records, identifies duplicate prompts, checks common generation fields, and creates deterministic train/validation splits without uploading the dataset.

This is an independent community project and is not affiliated with or endorsed by Hugging Face.

## Why this exists

Prompt datasets often grow from notebooks, manual edits, and generated batches. Small data-quality problems then become difficult to trace: malformed rows, empty prompts, near-identical duplicates, inconsistent dimensions, or changing splits between runs.

This project provides a transparent preflight step that can run locally or in CI.

## Expected format

```json
{"prompt":"A translucent DNA helix","negative_prompt":"text","width":1024,"height":1024,"seed":42}
```

Only `prompt` is required. `width`, `height`, and `seed` are validated when present.

## Install

```bash
python -m pip install .
```

## Audit a dataset

```bash
promptset-audit audit examples/prompts.jsonl
promptset-audit audit --strict --json examples/prompts.jsonl
```

The audit reports:

- invalid JSONL rows
- missing or empty prompts
- duplicate prompts after whitespace and case normalisation
- invalid or unaligned image dimensions
- non-integer seeds
- unusually long prompts

## Create deterministic splits

```bash
promptset-audit split examples/prompts.jsonl build/split \
  --validation-ratio 0.2 \
  --salt my-experiment
```

The same prompt and salt always produce the same split. Duplicate prompts are skipped.

## Development

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
```

## Roadmap

- optional similarity-based duplicate detection
- Dataset Card summary generation
- configurable schemas for additional modalities

## License

MIT
