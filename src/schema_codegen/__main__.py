"""Command line interface: ``python -m schema_codegen``."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

from ._errors import SchemaCodegenError
from ._graph import build_model_graph, parse_schema_bytes, read_schema_file
from ._render import render_pydantic, render_typescript


def _matches(path: Path, text: str) -> bool:
    try:
        return path.read_bytes() == text.encode("utf-8")
    except OSError:
        return False


def main(argv: list[str] | None = None) -> int:
    """Run the CLI. Returns 0 (written or up to date), 1 (stale) or 2 (invalid input)."""
    parser = argparse.ArgumentParser(
        prog="schema-codegen",
        description="Generate Pydantic and TypeScript types from a JSON Schema.",
    )
    parser.add_argument("schema", type=Path)
    parser.add_argument("--py", type=Path, default=None, help="Pydantic output file")
    parser.add_argument("--ts", type=Path, default=None, help="TypeScript output file")
    parser.add_argument("--root-name", default=None)
    parser.add_argument("--check", action="store_true", help="fail if outputs are stale")
    try:
        ns = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    if ns.py is None and ns.ts is None:
        print("error: provide --py and/or --ts", file=sys.stderr)
        return 2
    outputs: list[tuple[Path, str]] = []
    try:
        data = read_schema_file(ns.schema)
        defs = build_model_graph(parse_schema_bytes(data), root_name=ns.root_name)
        digest = hashlib.sha256(data).hexdigest()
        if ns.py is not None:
            outputs.append((ns.py, render_pydantic(defs, source_hash=digest)))
        if ns.ts is not None:
            outputs.append((ns.ts, render_typescript(defs, source_hash=digest)))
    except SchemaCodegenError as exc:
        where = f" at {exc.pointer}" if exc.pointer else ""
        print(f"error: {exc.code}{where}: {exc}", file=sys.stderr)
        return 2
    if ns.check:
        stale = [path for path, text in outputs if not _matches(path, text)]
        for path in stale:
            print(f"stale: {path}", file=sys.stderr)
        return 1 if stale else 0
    try:
        for path, text in outputs:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text.encode("utf-8"))
    except OSError:
        print("error: cannot write output", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
