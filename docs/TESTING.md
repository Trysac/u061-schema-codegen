# Testing

## Running

```sh
uv run pytest --cov=schema_codegen   # tests with coverage report
uv run python scripts/check.py      # every gate, as CI and the factory run it
```

## Policy

- Branch coverage of `src/schema_codegen` must stay at or above 80 %; the gate fails below it.
- Tests exercise the public API (`import schema_codegen`) and the CLI, asserting return values, raised exceptions and their codes.
- Golden files under `tests/golden` pin the Python and TypeScript output byte for byte.
- Tests are deterministic: no network, no wall clock, no dependence on test order.

## Layout

`tests/test_<module>.py` mirrors each module under `src/schema_codegen`. Shared fixtures go in `tests/conftest.py`.
