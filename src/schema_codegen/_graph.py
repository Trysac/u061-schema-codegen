"""Load JSON Schema documents and build the language-neutral model graph."""

from __future__ import annotations

import json
import keyword
import logging
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from ._errors import SchemaCodegenError

logger = logging.getLogger(__name__)

DEFAULT_MAX_BYTES = 5_242_880
MAX_DEPTH = 64
MAX_DEFINITIONS = 1000

_NESTED_KEYS = frozenset(
    {
        "type",
        "properties",
        "required",
        "items",
        "enum",
        "const",
        "$ref",
        "anyOf",
        "oneOf",
        "additionalProperties",
        "default",
        "description",
        "title",
    }
)
_ROOT_KEYS = _NESTED_KEYS | {"$defs", "definitions", "$schema", "$id"}
_ROOT_TYPE_KEYS = ("type", "properties", "enum", "const", "anyOf", "oneOf", "$ref")
_PRIMS = frozenset({"string", "integer", "number", "boolean", "null"})
_RESERVED_TYPE_NAMES = ("BaseModel", "ConfigDict", "Field", "Any", "Literal", "Record", "Array")
_BASE_MEMBERS = frozenset({"copy", "dict", "json", "schema", "construct", "validate", "fields"})


class _Missing:
    """Type of the MISSING sentinel (no default declared)."""

    def __repr__(self) -> str:
        return "MISSING"


MISSING = _Missing()


@dataclass(frozen=True)
class FieldDef:
    """One property of an object type.

    ``type_ref`` is a neutral expression: primitives (``string``, ``integer``, ``number``,
    ``boolean``, ``null``, ``any``, ``object``), definition names, ``array<X>`` and ``A|B``.
    """

    name: str
    py_name: str
    type_ref: str
    required: bool
    nullable: bool
    default: object = MISSING
    description: str | None = None


@dataclass(frozen=True)
class TypeDef:
    """A named definition of the model graph."""

    name: str
    kind: Literal["object", "enum", "alias", "union"]
    fields: tuple[FieldDef, ...] = ()
    values: tuple[str, ...] = ()
    target: str | None = None
    members: tuple[str, ...] = ()
    description: str | None = None
    closed: bool = False


def _clip(text: str, limit: int = 40) -> str:
    return text if len(text) <= limit else text[:limit] + "..."


def _esc(key: str) -> str:
    return key.replace("~", "~0").replace("/", "~1")


def _reject_constant(name: str) -> Any:
    raise SchemaCodegenError("invalid_json", f"non-finite number {_clip(name)} is not allowed")


def _parse_float(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise SchemaCodegenError("invalid_json", "number is not finite")
    return value


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise SchemaCodegenError("invalid_json", f"duplicate key {_clip(key)!r}")
        out[key] = value
    return out


def read_schema_file(path: Path, max_bytes: int = DEFAULT_MAX_BYTES) -> bytes:
    """Read at most ``max_bytes`` bytes of ``path``; raise ``too_large`` when exceeded."""
    try:
        with path.open("rb") as handle:
            data = handle.read(max_bytes + 1)
    except OSError as exc:
        raise SchemaCodegenError("invalid_json", "cannot read schema file") from exc
    if len(data) > max_bytes:
        raise SchemaCodegenError("too_large", f"schema file exceeds {max_bytes} bytes")
    return data


def parse_schema_bytes(data: bytes, max_bytes: int = DEFAULT_MAX_BYTES) -> dict[str, Any]:
    """Strictly parse JSON bytes into a schema object."""
    if len(data) > max_bytes:
        raise SchemaCodegenError("too_large", f"schema exceeds {max_bytes} bytes")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SchemaCodegenError("invalid_json", "schema is not valid UTF-8") from exc
    try:
        value = json.loads(
            text,
            parse_constant=_reject_constant,
            parse_float=_parse_float,
            object_pairs_hook=_no_duplicates,
        )
    except RecursionError as exc:
        raise SchemaCodegenError("too_deep", "JSON nesting is too deep") from exc
    except ValueError as exc:
        raise SchemaCodegenError("invalid_json", "malformed JSON") from exc
    if not isinstance(value, dict):
        raise SchemaCodegenError("invalid_json", "schema must be a JSON object")
    return value


def load_schema(path: Path, *, max_bytes: int = DEFAULT_MAX_BYTES) -> dict[str, Any]:
    """Load a JSON Schema file (JSON only) with strict parsing and a size limit."""
    return parse_schema_bytes(read_schema_file(path, max_bytes), max_bytes)


class _Ctx:
    def __init__(self) -> None:
        self.out: dict[str, TypeDef] = {}
        self.used: set[str] = set(_RESERVED_TYPE_NAMES)
        self.refmap: dict[str, str] = {}

    def claim(self, base: str) -> str:
        name = base
        n = 2
        while name in self.used:
            name = f"{base}{n}"
            n += 1
        self.used.add(name)
        return name

    def add(self, td: TypeDef) -> None:
        if len(self.out) >= MAX_DEFINITIONS:
            raise SchemaCodegenError("too_large", f"more than {MAX_DEFINITIONS} definitions")
        self.out[td.name] = td


def _pascal(text: str, fallback: str = "Type") -> str:
    parts = re.split(r"[^0-9A-Za-z]+", text)
    name = "".join(p[:1].upper() + p[1:] for p in parts if p)[:100]
    if not name:
        name = fallback
    if name[0].isdigit():
        name = "T" + name
    return name


def _is_reserved(name: str) -> bool:
    return keyword.iskeyword(name) or name.startswith("model_") or name in _BASE_MEMBERS


def _is_plain(name: str) -> bool:
    return re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", name) is not None and not _is_reserved(name)


def _snake(key: str) -> str:
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key)
    text = re.sub(r"[^0-9A-Za-z]+", "_", text).strip("_").lower()[:100]
    if not text:
        text = "field"
    if text[0].isdigit():
        text = "field_" + text
    return text


def _py_names(keys: list[str]) -> list[str]:
    used: set[str] = set()
    names: dict[int, str] = {}
    for i, key in enumerate(keys):
        if _is_plain(key):
            names[i] = key
            used.add(key)
    for i, key in enumerate(keys):
        if i in names:
            continue
        base = _snake(key)
        if _is_reserved(base):
            base += "_"
        cand = base
        n = 2
        while cand in used:
            cand = f"{base}_{n}"
            n += 1
        used.add(cand)
        names[i] = cand
    return [names[i] for i in range(len(keys))]


def _unsupported(message: str, pointer: str) -> SchemaCodegenError:
    return SchemaCodegenError("unsupported_keyword", message, pointer)


def _check(schema: dict[str, Any], ptr: str, root: bool) -> None:
    allowed = _ROOT_KEYS if root else _NESTED_KEYS
    for key in schema:
        if key not in allowed:
            raise _unsupported(f"unsupported keyword {_clip(key)!r}", f"{ptr}/{_esc(key)}")


def _depth(depth: int, ptr: str) -> None:
    if depth > MAX_DEPTH:
        raise SchemaCodegenError("too_deep", f"schema nesting exceeds {MAX_DEPTH}", ptr)


def _desc(schema: dict[str, Any]) -> str | None:
    value = schema.get("description")
    return value if isinstance(value, str) else None


def _resolve(ref: object, ptr: str, ctx: _Ctx) -> str:
    if isinstance(ref, str) and ref.startswith("#") and ref[1:] in ctx.refmap:
        return ctx.refmap[ref[1:]]
    raise SchemaCodegenError(
        "unresolved_ref", f"cannot resolve reference {_clip(str(ref))!r}", f"{ptr}/$ref"
    )


def _make_enum(schema: dict[str, Any], ptr: str, name: str) -> TypeDef:
    if "enum" in schema:
        vals = schema["enum"]
        if not isinstance(vals, list) or not vals or not all(isinstance(v, str) for v in vals):
            raise _unsupported("enum must be a non-empty list of strings", f"{ptr}/enum")
        values = tuple(dict.fromkeys(vals))
    else:
        const = schema["const"]
        if not isinstance(const, str):
            raise _unsupported("const must be a string", f"{ptr}/const")
        values = (const,)
    return TypeDef(name, "enum", values=values, description=_desc(schema))


def _union_members(
    schema: dict[str, Any], ptr: str, kw: str, hint: str, depth: int, ctx: _Ctx
) -> list[str]:
    subs = schema[kw]
    if not isinstance(subs, list) or not subs:
        raise _unsupported(f"{kw} must be a non-empty list", f"{ptr}/{kw}")
    members: list[str] = []
    for i, sub in enumerate(subs):
        members.extend(_members(sub, f"{ptr}/{kw}/{i}", f"{hint}Option{i + 1}", depth + 1, ctx))
    return list(dict.fromkeys(members))


def _lift_object(schema: dict[str, Any], ptr: str, hint: str, depth: int, ctx: _Ctx) -> str:
    name = ctx.claim(hint)
    ctx.add(_make_object(schema, ptr, name, depth + 1, ctx))
    return name


def _array(schema: dict[str, Any], ptr: str, hint: str, depth: int, ctx: _Ctx) -> str:
    if "items" not in schema:
        return "array<any>"
    items = schema["items"]
    if not isinstance(items, dict):
        raise _unsupported("items must be a single schema", f"{ptr}/items")
    inner = "|".join(_members(items, f"{ptr}/items", hint + "Item", depth + 1, ctx))
    return f"array<{inner}>"


def _members(schema: Any, ptr: str, hint: str, depth: int, ctx: _Ctx) -> list[str]:
    if not isinstance(schema, dict):
        raise _unsupported("schema must be an object", ptr)
    _check(schema, ptr, False)
    return _members_body(schema, ptr, hint, depth, ctx)


def _members_body(schema: dict[str, Any], ptr: str, hint: str, depth: int, ctx: _Ctx) -> list[str]:
    _depth(depth, ptr)
    if "$ref" in schema:
        return [_resolve(schema["$ref"], ptr, ctx)]
    if "enum" in schema or "const" in schema:
        td = _make_enum(schema, ptr, ctx.claim(hint))
        ctx.add(td)
        return [td.name]
    for kw in ("anyOf", "oneOf"):
        if kw in schema:
            return _union_members(schema, ptr, kw, hint, depth, ctx)
    type_ = schema.get("type")
    if type_ is None:
        if "properties" in schema:
            return [_lift_object(schema, ptr, hint, depth, ctx)]
        return ["any"]
    types = type_ if isinstance(type_, list) else [type_]
    if not types or not all(isinstance(t, str) for t in types):
        raise _unsupported("type must be a string or a list of strings", f"{ptr}/type")
    out: list[str] = []
    for t in types:
        if t in _PRIMS:
            out.append(t)
        elif t == "array":
            out.append(_array(schema, ptr, hint, depth, ctx))
        elif t == "object":
            if "properties" in schema:
                out.append(_lift_object(schema, ptr, hint, depth, ctx))
            else:
                out.append("object")
        else:
            raise _unsupported(f"unsupported type {_clip(t)!r}", f"{ptr}/type")
    return list(dict.fromkeys(out))


def _make_object(schema: dict[str, Any], ptr: str, name: str, depth: int, ctx: _Ctx) -> TypeDef:
    _depth(depth, ptr)
    props = schema.get("properties", {})
    if not isinstance(props, dict):
        raise _unsupported("properties must be an object", f"{ptr}/properties")
    req = schema.get("required", [])
    if not isinstance(req, list) or not all(isinstance(r, str) for r in req):
        raise _unsupported("required must be a list of strings", f"{ptr}/required")
    required = set(req)
    extra = schema.get("additionalProperties", True)
    if extra is not True and extra is not False:
        raise _unsupported("additionalProperties must be a boolean", f"{ptr}/additionalProperties")
    keys = list(props)
    fields: list[FieldDef] = []
    for key, py_name in zip(keys, _py_names(keys), strict=True):
        sub = props[key]
        members = _members(
            sub, f"{ptr}/properties/{_esc(key)}", name + _pascal(key, "Field"), depth + 1, ctx
        )
        nullable = "null" in members and len(members) > 1
        kept = [m for m in members if m != "null"] or ["null"]
        fields.append(
            FieldDef(
                name=key,
                py_name=py_name,
                type_ref="|".join(kept),
                required=key in required,
                nullable=nullable,
                default=sub.get("default", MISSING),
                description=_desc(sub),
            )
        )
    return TypeDef(
        name, "object", fields=tuple(fields), description=_desc(schema), closed=extra is False
    )


def _make_def(
    schema: dict[str, Any], ptr: str, name: str, depth: int, ctx: _Ctx, root: bool = False
) -> TypeDef:
    _depth(depth, ptr)
    _check(schema, ptr, root)
    if "enum" in schema or "const" in schema:
        return _make_enum(schema, ptr, name)
    for kw in ("anyOf", "oneOf"):
        if kw in schema:
            members = _union_members(schema, ptr, kw, name, depth, ctx)
            return TypeDef(name, "union", members=tuple(members), description=_desc(schema))
    if "$ref" in schema:
        target = _resolve(schema["$ref"], ptr, ctx)
        return TypeDef(name, "alias", target=target, description=_desc(schema))
    type_ = schema.get("type")
    if type_ == "object" or (type_ is None and "properties" in schema):
        return _make_object(schema, ptr, name, depth, ctx)
    found = _members_body(schema, ptr, name, depth + 1, ctx)
    return TypeDef(name, "alias", target="|".join(found), description=_desc(schema))


def build_model_graph(schema: dict[str, Any], *, root_name: str | None = None) -> list[TypeDef]:
    """Build the sorted list of definitions from a parsed JSON Schema object."""
    if not isinstance(schema, dict):
        raise SchemaCodegenError("invalid_json", "schema must be a JSON object")
    _check(
        schema, "", True
    )  # root keywords are checked even when the root defines no type of its own
    ctx = _Ctx()
    entries: list[tuple[str, str, Any]] = []
    for container in ("$defs", "definitions"):
        defs = schema.get(container)
        if defs is None:
            continue
        if not isinstance(defs, dict):
            raise _unsupported(f"{container} must be an object", f"/{container}")
        if len(defs) > MAX_DEFINITIONS:
            raise SchemaCodegenError(
                "too_large", f"more than {MAX_DEFINITIONS} definitions", f"/{container}"
            )
        for key, value in defs.items():
            entries.append((key, f"/{container}/{_esc(key)}", value))
    entries.sort(key=lambda e: (e[0], e[1]))
    if len(entries) > MAX_DEFINITIONS:
        raise SchemaCodegenError("too_large", f"more than {MAX_DEFINITIONS} definitions")
    for key, pointer, _ in entries:
        ctx.refmap[pointer] = ctx.claim(_pascal(key))
    has_root = any(k in schema for k in _ROOT_TYPE_KEYS)
    if has_root:
        title = schema.get("title")
        base = root_name or (title if isinstance(title, str) and title else "Root")
        ctx.refmap[""] = ctx.claim(_pascal(base, "Root"))
    for _, pointer, value in entries:
        if not isinstance(value, dict):
            raise _unsupported("schema must be an object", pointer)
        ctx.add(_make_def(value, pointer, ctx.refmap[pointer], 1, ctx))
    if has_root:
        ctx.add(_make_def(schema, "", ctx.refmap[""], 0, ctx, root=True))
    logger.debug("built %d definitions", len(ctx.out))
    return sorted(ctx.out.values(), key=lambda t: t.name)
