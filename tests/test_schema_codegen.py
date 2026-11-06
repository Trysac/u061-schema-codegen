"""Tests for schema_codegen."""

from __future__ import annotations

import ast
import hashlib
import logging
from pathlib import Path
from typing import Any

import pytest

from schema_codegen import (
    MISSING,
    SchemaCodegenError,
    build_model_graph,
    load_schema,
    render_pydantic,
    render_typescript,
)
from schema_codegen.__main__ import main

H = "0" * 64
GOLD = Path(__file__).parent / "golden"
BS = chr(92)


def obj(props: dict[str, Any], required: tuple[str, ...] = (), **extra: Any) -> dict[str, Any]:
    body = {"type": "object", "properties": props, "required": list(required), **extra}
    return {"$defs": {"T": body}}


def py(schema: dict[str, Any]) -> str:
    return render_pydantic(build_model_graph(schema), source_hash=H)


def ts(schema: dict[str, Any]) -> str:
    return render_typescript(build_model_graph(schema), source_hash=H)


def err(schema: dict[str, Any]) -> SchemaCodegenError:
    with pytest.raises(SchemaCodegenError) as info:
        build_model_graph(schema)
    return info.value


def test_golden_files() -> None:
    defs = build_model_graph(load_schema(GOLD / "customer.schema.json"))
    py_out = render_pydantic(defs, source_hash=H)
    ts_out = render_typescript(defs, source_hash=H)
    assert py_out.encode() == (GOLD / "customer.py.golden").read_bytes()
    assert ts_out.encode() == (GOLD / "customer.ts.golden").read_bytes()
    ast.parse(py_out)
    assert "\r" not in py_out + ts_out
    assert [d.name for d in defs] == ["Address", "Customer", "Status"]


def test_required_optional_nullable() -> None:
    schema = obj(
        {
            "name": {"type": "string"},
            "nickname": {"type": "string"},
            "x": {"type": ["string", "null"]},
        },
        ("name", "x"),
    )
    p = py(schema)
    assert "    name: str\n" in p
    assert "    nickname: str | None = None\n" in p
    assert "    x: str | None\n" in p
    t = ts(schema)
    assert "  name: string;" in t
    assert "  nickname?: string;" in t
    assert "  x: string | null;" in t
    field = build_model_graph(schema)[0].fields[2]
    assert field.nullable
    assert field.type_ref == "string"


def test_enum_and_const() -> None:
    schema = {"$defs": {"E": {"enum": ["a", "b"]}, "C": {"const": "x"}}}
    assert "E = Literal['a', 'b']" in py(schema)
    assert "C = Literal['x']" in py(schema)
    assert 'export type E = "a" | "b";' in ts(schema)
    e = err({"$defs": {"E": {"enum": [1, 2]}}})
    assert e.code == "unsupported_keyword"
    assert e.pointer == "/$defs/E/enum"
    assert err({"$defs": {"E": {"enum": []}}}).code == "unsupported_keyword"
    assert err({"$defs": {"E": {"const": 1}}}).pointer == "/$defs/E/const"


def test_property_names() -> None:
    schema = obj({"first-name": {"type": "string"}}, ("first-name",))
    assert "first_name: str = Field(alias='first-name')" in py(schema)
    assert '  "first-name": string;' in ts(schema)
    schema = obj(
        {
            "class": {"type": "string"},
            "json": {"type": "string"},
            "model_config": {"type": "string"},
        },
        ("class", "json", "model_config"),
    )
    p = py(schema)
    assert "class_: str = Field(alias='class')" in p
    assert "json_: str = Field(alias='json')" in p
    assert "model_config_: str = Field(alias='model_config')" in p
    schema = obj(
        {"first-name": {"type": "string"}, "first_name": {"type": "string"}},
        ("first-name", "first_name"),
    )
    p = py(schema)
    assert "    first_name: str\n" in p
    assert "first_name_2: str = Field(alias='first-name')" in p
    p = py(obj({"2fast": {"type": "string"}, "---": {"type": "string"}, "fooBar!": {}}))
    assert "field_2fast" in p
    assert "field: " in p
    assert "foo_bar" in p


def test_self_reference() -> None:
    node = {
        "$defs": {
            "Node": {
                "type": "object",
                "properties": {"children": {"type": "array", "items": {"$ref": "#/$defs/Node"}}},
            }
        }
    }
    p = py(node)
    assert "children: list[Node] | None = None" in p
    assert p.rstrip().endswith("Node.model_rebuild()")
    assert "children?: Node[]" in ts(node)


def test_unsupported_and_unresolved() -> None:
    e = err({"$defs": {"Foo": {"type": "object", "patternProperties": {}}}})
    assert (e.code, e.pointer) == ("unsupported_keyword", "/$defs/Foo/patternProperties")
    e = err({"$defs": {"A": {"type": "object", "properties": {"x": {"$ref": "other.json#/x"}}}}})
    assert e.code == "unresolved_ref"
    assert e.pointer == "/$defs/A/properties/x/$ref"
    assert err({"$defs": {"A": {"$ref": "#/$defs/Nope"}}}).code == "unresolved_ref"
    assert err({"$defs": {}, "if": {}}).pointer == "/if"
    assert err(obj({"x": {"format": "date"}})).pointer == "/$defs/T/properties/x/format"
    assert err(obj({"x": True})).code == "unsupported_keyword"
    assert err(obj({"x": {"type": "foo"}})).pointer == "/$defs/T/properties/x/type"
    assert err(obj({"x": {"type": 5}})).code == "unsupported_keyword"
    assert err(obj({"x": {"type": "array", "items": []}})).code == "unsupported_keyword"
    assert err(obj({}, additionalProperties={"type": "string"})).code == "unsupported_keyword"
    assert err({"$defs": []}).code == "unsupported_keyword"
    assert err({"$defs": {"A": True}}).code == "unsupported_keyword"
    assert err({"$defs": {"A": {"type": "object", "properties": []}}}).code == "unsupported_keyword"
    assert err({"$defs": {"A": {"type": "object", "required": [1]}}}).code == "unsupported_keyword"
    assert err({"$defs": {"A": {"anyOf": []}}}).code == "unsupported_keyword"
    assert err({"$defs": {"A": {"$defs": {}, "type": "string"}}}).code == "unsupported_keyword"
    assert err([]).code == "invalid_json"  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "text",
    [
        '{"a": NaN}',
        '{"a": Infinity}',
        '{"a": -Infinity}',
        '{"a":1,"a":2}',
        '{"a": 1e999}',
        "{",
        "[]",
    ],
)
def test_invalid_json(tmp_path: Path, text: str) -> None:
    path = tmp_path / "s.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(SchemaCodegenError) as info:
        load_schema(path)
    assert info.value.code == "invalid_json"


def test_load_errors(tmp_path: Path) -> None:
    big = tmp_path / "big.json"
    big.write_bytes(b" " * 5_242_881)
    with pytest.raises(SchemaCodegenError) as info:
        load_schema(big)
    assert info.value.code == "too_large"
    small = tmp_path / "small.json"
    small.write_text('{"a": 1}', encoding="utf-8")
    assert load_schema(small) == {"a": 1}
    with pytest.raises(SchemaCodegenError) as info:
        load_schema(small, max_bytes=3)
    assert info.value.code == "too_large"
    bad = tmp_path / "bad.json"
    bad.write_bytes(b"\xff\xfe")
    with pytest.raises(SchemaCodegenError) as info:
        load_schema(bad)
    assert info.value.code == "invalid_json"
    with pytest.raises(SchemaCodegenError) as info:
        load_schema(tmp_path / "missing.json")
    assert info.value.code == "invalid_json"
    deep = tmp_path / "deep.json"
    deep.write_text("[" * 100_000 + "]" * 100_000, encoding="utf-8")
    with pytest.raises(SchemaCodegenError) as info:
        load_schema(deep)
    assert info.value.code == "too_deep"


def test_injection_safety() -> None:
    desc = 'a """ b ' + BS * 2 + " c */ d"
    schema = {
        "$defs": {
            "T": {
                "type": "object",
                "description": desc,
                "properties": {"x": {"type": "string", "description": desc}},
            }
        }
    }
    p = py(schema)
    tree = ast.parse(p)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
    assert ast.get_docstring(cls, clean=False) == desc
    t = ts(schema)
    assert "*" + BS + "/" in t
    assert t.replace("*" + BS + "/", "").count("*/") == 2
    multi = ts({"$defs": {"M": {"type": "string", "description": "l1\nl2 */"}}})
    assert " * l1\n" in multi
    assert multi.replace("*" + BS + "/", "").count("*/") == 1
    ast.parse(py({"$defs": {"E": {"enum": ["a\"'\n", "\u2028"]}}}))
    assert "\u2028" not in ts({"$defs": {"E": {"enum": ["\u2028"]}}})


def test_limits() -> None:
    inner: dict[str, Any] = {"type": "string"}
    for _ in range(10):
        inner = {"type": "array", "items": inner}
    build_model_graph({"$defs": {"D": inner}})
    for _ in range(70):
        inner = {"type": "array", "items": inner}
    assert err({"$defs": {"D": inner}}).code == "too_deep"
    many = {f"D{i}": {"type": "string"} for i in range(1001)}
    assert err({"$defs": many}).code == "too_large"
    assert err({"$defs": many, "definitions": {}}).code == "too_large"
    assert len(build_model_graph({"$defs": dict(list(many.items())[:1000])})) == 1000
    assert err({"$defs": dict(list(many.items())[:1000]), "type": "string"}).code == "too_large"


def test_naming_and_ordering() -> None:
    schema = {
        "$defs": {
            "my-type": {"type": "string"},
            "MyType": {"type": "string"},
            "Field": {"type": "string"},
            "9x": {"type": "string"},
            "!!": {"type": "string"},
        }
    }
    names = [d.name for d in build_model_graph(schema)]
    assert names == sorted(names)
    assert {"MyType", "MyType2", "Field2", "T9x", "Type"} == set(names)


def test_unions_and_aliases() -> None:
    schema = {
        "$defs": {
            "Pet": {"oneOf": [{"$ref": "#/$defs/Cat"}, {"type": "string"}]},
            "Cat": {"type": "object"},
            "Ids": {"type": "array", "items": {"$ref": "#/$defs/Id"}},
            "Id": {"type": "string"},
            "Ref": {"$ref": "#/$defs/Id"},
            "Any": {},
        }
    }
    p = py(schema)
    assert "Pet = Cat | str" in p
    assert p.index("class Cat") < p.index("Pet = ")
    assert "class Cat(BaseModel):\n    pass" in p
    assert p.index("Id = str") < p.index("Ids = list[Id]")
    assert "Ref = Id" in p
    t = ts(schema)
    assert "export type Pet = Cat | string;" in t
    assert "export interface Cat {}" in t
    assert "export type Ids = Id[];" in t
    assert "export type Any2 = unknown;" in t


def test_alias_cycle_terminates() -> None:
    schema = {"$defs": {"A": {"$ref": "#/$defs/B"}, "B": {"$ref": "#/$defs/A"}}}
    assert "A = B" in py(schema)


def test_closed_defaults_and_inline() -> None:
    schema = obj(
        {
            "n": {"type": "integer", "default": 1},
            "f": {"type": "number", "default": 1.0},
            "s": {"type": "string", "default": "q'"},
            "z": {"type": "string", "default": None, "description": "d"},
            "kind": {"enum": ["x", "y"]},
            "v": {"type": "array", "items": {"type": ["string", "integer"]}},
            "o": {"type": "object"},
            "nn": {"type": "null"},
            "inl": {"type": "object", "properties": {"a": {"type": "boolean"}}},
            "u": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        },
        ("u",),
        additionalProperties=False,
    )
    defs = build_model_graph(schema)
    assert [d.name for d in defs] == ["T", "TInl", "TKind"]
    fields = {f.name: f for f in defs[0].fields}
    assert fields["n"].default == 1
    assert type(fields["n"].default) is int
    assert type(fields["f"].default) is float
    assert fields["nn"].default is MISSING
    assert fields["u"].nullable
    p = py(schema)
    assert "model_config = ConfigDict(extra='forbid')" in p
    assert "    n: int = 1\n" in p
    assert "    f: float = 1.0\n" in p
    assert (
        '    s: str = "q\'"\n' in p
    )  # strings reach Python through repr(), which picks double quotes
    assert "z: str | None = Field(default=None, description='d')" in p
    assert "    v: list[str | int] | None = None\n" in p
    assert "    o: dict[str, Any] | None = None\n" in p
    assert "    nn: None\n" in p or "    nn: None = None\n" in p
    assert "    u: str | None\n" in p
    assert "    kind: TKind | None = None\n" in p
    assert "TKind = Literal['x', 'y']" in p
    t = ts(schema)
    assert "  v?: (string | number)[];" in t
    assert "  o?: Record<string, unknown>;" in t
    assert "  inl?: TInl;" in t
    assert repr(MISSING) == "MISSING"


def test_root_and_definitions() -> None:
    schema = {"title": "Event", "type": "object", "properties": {"id": {"type": "string"}}}
    assert [d.name for d in build_model_graph(schema)] == ["Event"]
    assert [d.name for d in build_model_graph(schema, root_name="Root X")] == ["RootX"]
    draft7 = {
        "definitions": {"A": {"type": "object", "properties": {"r": {"$ref": "#"}}}},
        "type": "string",
    }
    names = {d.name: d for d in build_model_graph(draft7)}
    assert set(names) == {"A", "Root"}
    assert names["A"].fields[0].type_ref == "Root"
    ref = {"definitions": {"A": {"type": "string"}}, "$ref": "#/definitions/A"}
    assert [d.target for d in build_model_graph(ref) if d.name == "Root"] == ["A"]


def test_render_hash_validation() -> None:
    with pytest.raises(ValueError, match="source_hash"):
        render_pydantic([], source_hash="x y")
    with pytest.raises(ValueError, match="source_hash"):
        render_typescript([], source_hash="\n" + H)
    assert render_typescript([], source_hash=H).endswith("\n")


def test_error_clipping_and_logging() -> None:
    e = SchemaCodegenError("invalid_json", "x" * 500, "/" + "y" * 500)
    assert len(str(e)) == 200
    assert e.pointer is not None
    assert len(e.pointer) == 200
    assert SchemaCodegenError("too_large", "m").pointer is None
    handlers = logging.getLogger("schema_codegen").handlers
    assert any(isinstance(h, logging.NullHandler) for h in handlers)


def test_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    schema = tmp_path / "s.json"
    schema.write_bytes((GOLD / "customer.schema.json").read_bytes())
    p = tmp_path / "out" / "m.py"
    t = tmp_path / "out" / "m.ts"
    base = [str(schema), "--py", str(p), "--ts", str(t)]
    assert main([str(schema)]) == 2
    assert main([*base, "--check"]) == 1
    assert not p.exists()
    assert not t.exists()
    assert main(base) == 0
    digest = hashlib.sha256(schema.read_bytes()).hexdigest()
    assert digest in p.read_text(encoding="utf-8")
    ast.parse(p.read_text(encoding="utf-8"))
    assert main([*base, "--check"]) == 0
    t.write_text("old\n", encoding="utf-8")
    assert main([*base, "--check"]) == 1
    assert t.read_text(encoding="utf-8") == "old\n"
    assert "stale" in capsys.readouterr().err
    assert main([str(schema), "--py", str(p), "--check"]) == 0
    assert main([str(schema), "--ts", str(t), "--root-name", "Z"]) == 0


def test_cli_errors(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text('{"$defs": {"Foo": {"patternProperties": {}}}}', encoding="utf-8")
    out = tmp_path / "o.py"
    assert main([str(bad), "--py", str(out)]) == 2
    assert "/$defs/Foo/patternProperties" in capsys.readouterr().err
    assert not out.exists()
    assert main([str(tmp_path / "missing.json"), "--py", str(out)]) == 2
    assert main(["--bogus"]) == 2
    assert main(["--help"]) == 0
    good = tmp_path / "g.json"
    good.write_bytes((GOLD / "customer.schema.json").read_bytes())
    assert main([str(good), "--py", str(tmp_path)]) == 2
    assert main([str(good), "--py", str(tmp_path), "--check"]) == 1
