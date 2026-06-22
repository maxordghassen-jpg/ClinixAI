"""
Temporary structured debug tracer.

All trace() calls use a consistent prefix so they can be grepped in one shot
and replaced with proper structured logging in Phase 4 without touching callers.

Usage:
    from graphs.shared.trace import trace
    trace("MEMORY", session_id, "loaded 5 keys")
    trace("WORKFLOW", session_id, "step: None → awaiting_date | intent=booking")

Output format:
    [MEMORY  ] session=abc123 | loaded 5 keys
    [WORKFLOW] session=abc123 | step: None → awaiting_date | intent=booking
"""

import os

# Set CLINIX_TRACE=0 to silence all trace output.
_ENABLED = os.getenv("CLINIX_TRACE", "1") != "0"


def trace(node: str, session_id: str, message: str) -> None:
    if not _ENABLED:
        return
    tag = f"[{node:<8}]"
    short_session = (session_id or "?")[:12]
    line = f"{tag} session={short_session} | {message}"
    try:
        print(line)
    except UnicodeEncodeError:
        # Windows cp1252 terminals can't print characters like →, é, etc.
        # Encode as ASCII, replacing non-ASCII with '?', then print safely.
        print(line.encode("ascii", errors="replace").decode("ascii"))
