"""
Exception document resolution for scheduling.

Pure functions — no I/O.  Operates on already-fetched exception documents.

An exception document has at minimum:
  { "type": "closure" | "vacation" | "override", ... }

For override exceptions, overrideRanges contains [{start, end}, ...] dicts.
"""
from __future__ import annotations

from typing import Any

_BLOCKING_TYPES = frozenset({"closure", "vacation"})


def is_day_blocked(exception: dict[str, Any]) -> bool:
    """Return True if the exception blocks the day (closure or vacation)."""
    return exception.get("type") in _BLOCKING_TYPES


def get_override_ranges(exception: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Return override time ranges from an 'override' exception.

    Returns the 'overrideRanges' list, or [] if the exception is not an
    override or has no ranges defined.
    """
    if exception.get("type") != "override":
        return []
    return exception.get("overrideRanges") or []
