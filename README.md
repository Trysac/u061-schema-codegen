# schema-codegen

[![PyPI version](https://img.shields.io/pypi/v/trysac-schema-codegen)](https://pypi.org/project/trysac-schema-codegen/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-schema-codegen)](LICENSE)
[![CI](https://github.com/Trysac/u061-schema-codegen/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u061-schema-codegen/actions/workflows/ci.yml)

Generate Pydantic v2 models and TypeScript types from one JSON Schema model graph, injection-safe, with a CI check mode for stale outputs

## Problem

Describe in two or three sentences the concrete problem this utility solves, who hits it, and what
they do today without it. Replace this paragraph when the first real feature lands.

## Install

```sh
pip install trysac-schema-codegen
# or
uv add trysac-schema-codegen
```

Requires Python 3.10 or newer. No runtime dependencies.

## Usage

```python
import schema_codegen

# normalize() trims surrounding whitespace and lower-cases the text.
print(schema_codegen.normalize("  Hello World "))  # -> "hello world"

# Blank input is rejected explicitly instead of returning an empty string.
try:
    schema_codegen.normalize("   ")
except ValueError as exc:
    print(f"rejected: {exc}")
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [decisions](docs/decisions/)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)
- [Changelog](CHANGELOG.md) and [contributing guide](CONTRIBUTING.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez
