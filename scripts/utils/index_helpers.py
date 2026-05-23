"""
Safe MongoDB index creation utilities.

Prevents crashes when indexes already exist with the same key spec but a
different name or different options (e.g. unique vs non-unique conflict).

Functions
---------
index_exists(collection, keys)       → bool
safe_create_index(collection, keys)  → str | None
"""
from __future__ import annotations

from typing import Any


def _normalize_key_spec(keys: list | dict) -> list[tuple[str, int]]:
    """Convert any pymongo key spec form to a canonical list of (field, direction) tuples."""
    if isinstance(keys, list):
        return [(str(k), int(v)) for k, v in keys]
    if isinstance(keys, dict):
        return [(str(k), int(v)) for k, v in keys.items()]
    return []


def index_exists(collection: Any, keys: list | dict) -> bool:
    """
    Return True if an index whose key spec matches `keys` already exists
    on `collection`, regardless of index name or options.
    """
    target = _normalize_key_spec(keys)
    for name, info in collection.index_information().items():
        if name == "_id_":
            continue
        existing = [(str(k), int(v)) for k, v in info.get("key", [])]
        if existing == target:
            return True
    return False


def safe_create_index(
    collection: Any,
    keys: list | dict,
    **kwargs: Any,
) -> str | None:
    """
    Create an index only if no index with the same key spec already exists.

    - If a matching key spec is found (any name, any options): skip and return None.
    - If creation raises for any other reason: print a warning and return None.
    - Never raises.

    Returns the index name on success, None when skipped or on error.
    """
    key_label = str(keys)
    try:
        if index_exists(collection, keys):
            print(f"[IDX]  Index already exists for {key_label} — skipped")
            return None
        name = collection.create_index(keys, **kwargs)
        print(f"[IDX]  Created index {name!r} for {key_label}")
        return name
    except Exception as exc:
        print(f"[IDX]  Could not create index for {key_label} — {exc!r} — skipped")
        return None
