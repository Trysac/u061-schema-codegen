"""Generate Pydantic v2 models and TypeScript types from one JSON Schema model graph."""

from __future__ import annotations

import logging

from ._errors import ErrorCode, SchemaCodegenError
from ._graph import MISSING, FieldDef, TypeDef, build_model_graph, load_schema
from ._render import render_pydantic, render_typescript

logging.getLogger(__name__).addHandler(logging.NullHandler())

__all__ = [
    "MISSING",
    "ErrorCode",
    "FieldDef",
    "SchemaCodegenError",
    "TypeDef",
    "__version__",
    "build_model_graph",
    "load_schema",
    "render_pydantic",
    "render_typescript",
]

__version__ = "0.1.0"
