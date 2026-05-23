"""
Pure conflict detection for scheduling.

No I/O, no external dependencies.  All functions operate on in-memory sets
and lists of HH:MM time strings.
"""
from __future__ import annotations


def has_time_conflict(booked_times: set[str], candidate: str) -> bool:
    """Return True if candidate time string is already in booked_times."""
    return candidate in booked_times


def filter_free(all_times: list[str], booked_times: set[str]) -> list[str]:
    """Return only the time strings from all_times not present in booked_times."""
    return [t for t in all_times if t not in booked_times]
