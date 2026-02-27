"""Null-safe JSON decoder for msgspec structs.

Go serializes nil slices/maps as JSON null. This module preprocesses
raw JSON data to replace null collection fields with empty lists/dicts
before converting to typed msgspec structs.
"""

from __future__ import annotations

import types
import typing
from functools import lru_cache
from typing import Any, Type, TypeVar

import msgspec

T = TypeVar("T")

_UNION_TYPES = (typing.Union, types.UnionType)


def _struct_field_pairs(cls: type) -> list[tuple[str, str]]:
    """Return (field_name, encode_name) pairs for a msgspec Struct class."""
    fields: tuple[str, ...] = getattr(cls, "__struct_fields__", ())
    encode_fields: tuple[str, ...] = getattr(cls, "__struct_encode_fields__", ())
    return list(zip(fields, encode_fields))


def _is_union(origin: Any) -> bool:
    return origin is not None and origin in _UNION_TYPES


def _classify_collection(hint: Any) -> str | None:
    """Return 'list', 'dict', or None for a type hint."""
    origin = typing.get_origin(hint)
    if origin is list:
        return "list"
    if origin is dict:
        return "dict"
    # Unwrap Optional/Union: list[str] | None -> list[str]
    if _is_union(origin):
        for arg in typing.get_args(hint):
            if arg is type(None):
                continue
            inner_origin = typing.get_origin(arg)
            if inner_origin is list:
                return "list"
            if inner_origin is dict:
                return "dict"
    return None


@lru_cache(maxsize=None)
def _collection_fields(cls: type) -> dict[str, str]:
    """Return a mapping of encode-name -> 'list' or 'dict' for collection-typed fields."""
    pairs = _struct_field_pairs(cls)
    if not pairs:
        return {}
    hints = typing.get_type_hints(cls)
    result: dict[str, str] = {}
    for field_name, encode_name in pairs:
        hint = hints.get(field_name)
        if hint is None:
            continue
        kind = _classify_collection(hint)
        if kind is not None:
            result[encode_name] = kind
    return result


def _extract_struct_type(hint: Any) -> type | None:
    """Extract a msgspec.Struct subclass from a type hint, unwrapping Optional/Union."""
    origin = typing.get_origin(hint)
    # Handle Optional[X] / X | None (Union types)
    if _is_union(origin):
        args = typing.get_args(hint)
        for arg in args:
            if arg is type(None):
                continue
            if isinstance(arg, type) and issubclass(arg, msgspec.Struct):
                return arg
        return None
    # Direct struct type
    if isinstance(hint, type) and issubclass(hint, msgspec.Struct):
        return hint
    return None


def _extract_dict_value_type(hint: Any) -> Any | None:
    """Extract the inner type from dict[K, V] or dict[K, V] | None."""
    origin = typing.get_origin(hint)
    if origin is dict:
        args = typing.get_args(hint)
        return args[1] if len(args) == 2 else None
    if _is_union(origin):
        for arg in typing.get_args(hint):
            if arg is type(None):
                continue
            if typing.get_origin(arg) is dict:
                inner_args = typing.get_args(arg)
                return inner_args[1] if len(inner_args) == 2 else None
    return None


@lru_cache(maxsize=None)
def _struct_fields(cls: type) -> dict[str, type]:
    """Return a mapping of encode-name -> struct class for struct-typed fields."""
    pairs = _struct_field_pairs(cls)
    if not pairs:
        return {}
    hints = typing.get_type_hints(cls)
    result: dict[str, type] = {}
    for field_name, encode_name in pairs:
        hint = hints.get(field_name)
        if hint is None:
            continue
        struct_cls = _extract_struct_type(hint)
        if struct_cls is not None:
            result[encode_name] = struct_cls
    return result


@lru_cache(maxsize=None)
def _dict_value_struct_fields(cls: type) -> dict[str, type]:
    """Return a mapping of encode-name -> struct class for dict fields whose values are structs."""
    pairs = _struct_field_pairs(cls)
    if not pairs:
        return {}
    hints = typing.get_type_hints(cls)
    result: dict[str, type] = {}
    for field_name, encode_name in pairs:
        hint = hints.get(field_name)
        if hint is None:
            continue
        val_type = _extract_dict_value_type(hint)
        if val_type is not None:
            val_struct = _extract_struct_type(val_type)
            if val_struct is not None:
                result[encode_name] = val_struct
    return result


def _preprocess(raw: Any, cls: type) -> Any:
    """Recursively replace None with [] or {} for collection-typed fields."""
    if not isinstance(raw, dict):
        return raw

    collections = _collection_fields(cls)
    structs = _struct_fields(cls)
    dict_val_structs = _dict_value_struct_fields(cls)

    for key, kind in collections.items():
        if key in raw and raw[key] is None:
            raw[key] = [] if kind == "list" else {}

    # Recurse into nested struct fields
    for key, nested_cls in structs.items():
        val = raw.get(key)
        if isinstance(val, dict):
            _preprocess(val, nested_cls)

    # Recurse into dict-of-struct values
    for key, val_cls in dict_val_structs.items():
        val = raw.get(key)
        if isinstance(val, dict):
            for v in val.values():
                if isinstance(v, dict):
                    _preprocess(v, val_cls)

    return raw


def decode_json(data: bytes, type: Type[T]) -> T:
    """Decode JSON bytes into a typed msgspec struct, replacing null collections with empties."""
    raw = msgspec.json.decode(data)
    _preprocess(raw, type)
    return msgspec.convert(raw, type=type)
