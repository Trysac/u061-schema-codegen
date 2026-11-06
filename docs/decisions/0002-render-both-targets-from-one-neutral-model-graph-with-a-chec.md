# Render both targets from one neutral model graph with a check mode

Status: accepted (generated, pending human review)

## Context

Per-language generators disagree on naming, optionality and enums, and schema strings flow into generated source, which is an injection risk. CI also needs to detect stale generated files.

## Decision

Parse JSON Schema once into immutable TypeDef and FieldDef values whose type_ref is a neutral type expression. Two pure renderers produce Pydantic v2 and TypeScript from that graph. Schema text reaches Python only through ascii(), which is repr with non-ASCII escaped, and TypeScript only through json.dumps quoting, with */ rewritten to *\/ in comments. Unsupported keywords fail loudly with RFC 6901 pointers. The CLI --check compares expected bytes to files on disk and writes nothing. Output headers carry the schema SHA-256 and no timestamp, so output is deterministic.

## Consequences

Output is deterministic and byte-comparable, so golden tests and CI staleness checks are straightforward. The supported subset is small: no allOf, remote refs or constraints. oneOf exclusivity is not representable and is rendered as a plain union. Python output orders enums, then classes, then aliases, so alias expressions are valid at import time, and model_rebuild() resolves forward references.
