# Architecture

## Purpose

`trysac-schema-codegen` is a small, dependency-free Python library (module `schema_codegen`) that generates Pydantic v2 models and TypeScript types from one JSON Schema model graph.

## Shape

```text
schema file --> _graph.py (load, validate, build TypeDef/FieldDef graph)
                    |
                    +--> _render.py (render_pydantic, render_typescript)
                    |
                    +--> __main__.py (CLI, reads and writes files, --check)
```

- **Public API**: the names listed in `__all__` of `src/schema_codegen/__init__.py`: `MISSING`, `ErrorCode`, `FieldDef`, `SchemaCodegenError`, `TypeDef`, `__version__`, `build_model_graph`, `load_schema`, `render_pydantic`, `render_typescript`.
- **Errors**: invalid input raises `SchemaCodegenError` with a stable `code` and an optional `pointer`. The library never exits the process.
- **Logging**: a module logger with a `NullHandler`; the library does not configure logging.
- **I/O**: confined to `load_schema` / `read_schema_file` and to the CLI, which is the only code that writes files.

## Naming and rendering

Names are PascalCase from definition keys or titles, with a numeric suffix on collision in sorted order. Output is sorted alphabetically by name. Python enums come first, then classes, then aliases and unions in dependency order, followed by one `model_rebuild()` call per class.

## Decisions

Architecture decisions are recorded in [decisions/](decisions/) as numbered ADRs.
