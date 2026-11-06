"""Typed errors raised by the library."""

from __future__ import annotations

from typing import Literal

ErrorCode = Literal[
    "invalid_json",
    "too_large",
    "too_deep",
    "unsupported_keyword",
    "unresolved_ref",
]

_MAX_TEXT = 200


class SchemaCodegenError(Exception):
    """Base error of the library.

    Attributes:
        code: stable machine-readable error code.
        pointer: RFC 6901 JSON Pointer of the offending schema location, if known.
    """

    def __init__(self, code: ErrorCode, message: str, pointer: str | None = None) -> None:
        super().__init__(message[:_MAX_TEXT])
        self.code: ErrorCode = code
        self.pointer: str | None = pointer[:_MAX_TEXT] if pointer is not None else None
