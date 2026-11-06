# Project record

## Objective

Generate Pydantic v2 models and TypeScript types from one JSON Schema model graph, so that Python and TypeScript payload types cannot drift apart, with a `--check` mode that detects stale generated files in CI.

## Scope

- In scope: JSON Schema draft 2020-12 (`$defs`) and draft-07 (`definitions`) documents that use the supported keyword subset listed in the README; rendering to Pydantic v2 and TypeScript; a command line interface with `--check`.
- Out of scope: `allOf` merging, remote references, `if`/`then`/`else`, discriminators, constraint keywords (such as `minLength`), formats, and any runtime dependency.

## Timeline

| Date | Event |
|---|---|
| 2026 | Repository created from the factory utility template. |

## Effort metrics

Measured values only; a value that has not been measured stays "pending measurement".

| Metric | Value |
|---|---|
| Tokens (input / output) | 163753 / 321464 |
| Hours (human) | pending measurement |
| Cost (USD) | 1.6764 |

## Factory run u061 (measured from API usage)

| Phase | Model | Batch | Input | Output | Cache write | Cache read | Cost (USD) |
|---|---|---|---|---|---|---|---|
| generation | claude-sonnet-5-5 | yes | 2340 | 128000 | 0 | 4246 | 0.6428 |
| generation | claude-sonnet-5-5 | yes | 2340 | 128000 | 0 | 4246 | 0.6428 |
| generation | claude-sonnet-5-5 | yes | 2340 | 60970 | 0 | 4246 | 0.3076 |
| docs | claude-haiku-5-5 | no | 143995 | 4494 | 0 | 0 | 0.0832 |

Total: $1.6764. Prices: Anthropic list prices.
