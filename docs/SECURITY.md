# Security notes

## Threat model

`trysac-schema-codegen` reads one schema file and writes generated source files. It has no network access and no runtime dependencies.

**Defended**

- Malformed or hostile JSON: strict parsing rejects NaN, Infinity and duplicate keys with `invalid_json`; invalid UTF-8 is rejected.
- Oversized input: files above 5 MiB (5_242_880 bytes) raise `too_large`; reading stops after the limit plus one byte.
- Deep nesting: nesting above depth 64 raises `too_deep`; a `RecursionError` during parsing is also mapped to `too_deep`.
- Graph size: more than 1000 definitions raises `too_large`.
- Code injection through schema strings: strings reach Python only through `repr()` and reach TypeScript only through JSON-style quoting; `*/` in comments is written as `*\/`. The library never calls `eval`, `exec` or deserializes untrusted pickles.
- Unsupported or ambiguous input: unknown keywords raise `unsupported_keyword`; unresolvable references raise `unresolved_ref`. Only local `#` references are resolved.

**Not defended**

- Remote or external `$ref` targets are never fetched; they are rejected, not resolved.
- Errors from reading files are reported as `invalid_json` because the error code set has no I/O code; the underlying OS error is chained but its detail is not in the message.
- Generated code is not sandboxed; the output is plain source that the consuming project compiles and runs.
- Input size and depth limits are fixed constants; callers that raise `max_bytes` accept the larger memory use.
- The `--check` mode compares bytes only; it does not verify who produced the output.

## Publishing

Releases are published to PyPI with trusted publishing (OIDC) when available, never with a long-lived token stored in the repository.

To report a vulnerability, see [SECURITY.md](../SECURITY.md).
