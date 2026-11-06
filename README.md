# schema-codegen

[![PyPI version](https://img.shields.io/pypi/v/trysac-schema-codegen)](https://pypi.org/project/trysac-schema-codegen/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-schema-codegen)](LICENSE)
[![CI](https://github.com/Trysac/u061-schema-codegen/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u061-schema-codegen/actions/workflows/ci.yml)

Generate Pydantic v2 models and TypeScript types from one JSON Schema model graph, injection-safe, with a CI check mode for stale outputs.

## Problem

Services that share event or API payloads between Python and TypeScript maintain two hand-written type sets that drift apart. Separate generators for each language disagree on naming, optionality and enums. This library renders one model graph to both targets, and its `--check` mode fails CI when the generated files are stale.

## Install

```sh
pip install trysac-schema-codegen
# or
uv add trysac-schema-codegen
```

Requires Python 3.10 or newer. No runtime dependencies. Pydantic is not needed to run the generator.

## Usage

```python
from pathlib import Path
from schema_codegen import build_model_graph, load_schema, render_pydantic, render_typescript

defs = build_model_graph(load_schema(Path("schema.json")))
print(render_pydantic(defs, source_hash="0" * 64))
print(render_typescript(defs, source_hash="0" * 64))
```

Command line: `python -m schema_codegen schema.json --py out.py --ts out.ts [--root-name NAME] [--check]`. Exit codes: 0 written or up to date, 1 stale (with `--check`), 2 invalid input or usage.

## Public API

- `load_schema(path, *, max_bytes=5_242_880) -> dict`: strict JSON parsing; NaN, Infinity and duplicate keys are rejected.
- `build_model_graph(schema, *, root_name=None) -> list[TypeDef]`: builds the neutral graph from `$defs` (draft 2020-12) or `definitions` (draft-07).
- `render_pydantic(defs, *, source_hash) -> str` and `render_typescript(defs, *, source_hash) -> str`: render the graph. `source_hash` must be a 1-128 character alphanumeric string, otherwise `ValueError` is raised.
- `TypeDef` and `FieldDef`: frozen dataclasses describing the graph.
- `SchemaCodegenError`: raised for invalid input; carries `code` (`invalid_json`, `too_large`, `too_deep`, `unsupported_keyword`, `unresolved_ref`) and `pointer` (an RFC 6901 JSON Pointer, when known).

Supported keywords: `type`, `properties`, `required`, `items` (single schema), `enum` of strings, `const` string, local `$ref`, `anyOf` and `oneOf` (rendered as unions; `oneOf` exclusivity is not represented), `additionalProperties: false` (rendered as `extra='forbid'`), `default`, `description`, `title`, `$defs` or `definitions`. Any other keyword raises `unsupported_keyword`.

Limits: input file at most 5 MiB, nesting depth 64, at most 1000 definitions. Remote references, `allOf` merging, `if`/`then`/`else`, discriminators, constraint keywords and formats are not supported.

## Why not datamodel-code-generator?

Datamodel-code-generator and json-schema-to-typescript each target one language and name types differently. This library renders a single graph to both targets with the same names, optionality and enums.

## Security

See [docs/SECURITY.md](docs/SECURITY.md) for the threat model and its limits.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [decisions](docs/decisions/)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)
- [Changelog](CHANGELOG.md) and [contributing guide](CONTRIBUTING.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez
