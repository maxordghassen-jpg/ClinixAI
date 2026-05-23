#!/usr/bin/env python3
"""
Availability seeding script for ClinixAI.

Reads doctors from medical_data_tunisia.doctors, parses their opening_hours,
generates appointment slots, and writes weekly schedule templates to
disponibility.disponibilites.

How the data model works
------------------------
The disponibilites collection stores WEEKLY TEMPLATES, not per-date schedules.
Each document represents a repeating weekly pattern:
    { doctorId, day: "lundi", slots: [...] }

The availability_service.get_free_slots() receives a date, converts it to a
French day name (e.g. "2026-05-22" → "vendredi"), and looks up the template.
So one seed run covers all future weeks — no need to generate 30 days separately.

Opening hours parsing
---------------------
weekday_text strings (primary source, Google Maps French locale):
    "lundi: 08:30–17:00"         single range
    "lundi: 08:30–12:00, 14:00–17:00"  two ranges (lunch break)
    "dimanche: Fermé"            closed day

periods objects (fallback, Google Maps structured format):
    {"open": {"day": 1, "time": "0830"}, "close": {"day": 1, "time": "1700"}}
    day: 0=Sunday, 1=Monday, ..., 6=Saturday

Slot generation strategy
------------------------
Each range [open, close] is divided into fixed-duration slots:
    08:30–17:00, interval=30min
    → 08:30–09:00, 09:00–09:30, ..., 16:30–17:00   (17 slots)

Multi-range days produce slots for each sub-range independently:
    08:30–12:00, 14:00–17:00
    → 7 morning slots + 6 afternoon slots = 13 slots

Specialty-based intervals override --interval for known specialties.
All slots are seeded with status="available".

Usage
-----
    cd ClinixAI
    python scripts/seed_availability.py                    # seed all doctors
    python scripts/seed_availability.py --dry-run          # preview only
    python scripts/seed_availability.py --limit 5          # test first 5 doctors
    python scripts/seed_availability.py --interval 20      # 20-min slots
    python scripts/seed_availability.py --replace          # overwrite existing
    python scripts/seed_availability.py --doctor-id <id>   # single doctor
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from bson import ObjectId
from pymongo import MongoClient

# Allow importing pure scheduling-engine modules (no FastAPI/app context needed).
_AGENT_SERVICE = Path(__file__).parent.parent / "agent_service"
if str(_AGENT_SERVICE) not in sys.path:
    sys.path.insert(0, str(_AGENT_SERVICE))

from graphs.shared.scheduling_engine.slot_generator import (  # noqa: E402
    parse_hhmm as _parse_hhmm,
    minutes_to_hhmm as _minutes_to_hhmm,
    apply_lunch_split as _apply_lunch_split,
    generate_slot_dicts_from_ranges as _generate_slots_for_ranges,
)

# Force UTF-8 output on Windows consoles (handles French diacritics and
# Unicode dashes/spaces that appear in Google Maps opening_hours strings).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ── MongoDB connection ─────────────────────────────────────────────────────────

MONGO_URI = "mongodb+srv://admin:Admin3131@medical-cluster.qjwgdmm.mongodb.net/"

SOURCE_DB = "medical_data_tunisia"
SOURCE_COLLECTION = "doctors"

TARGET_DB = "disponibility"
TARGET_COLLECTION = "disponibilites"


# ── Slot configuration ─────────────────────────────────────────────────────────

DEFAULT_INTERVAL_MINUTES = 30

# Per-specialty slot duration overrides.
# Key: lowercase specialty substring; Value: slot duration in minutes.
# A doctor whose specialty contains the key (case-insensitive) uses that interval.
SPECIALTY_INTERVALS: dict[str, int] = {
    # Short consultations
    "généraliste":     15,
    "generaliste":     15,
    "ophtalmologue":   20,
    "ophthalmologue":  20,
    "radiologue":      20,
    "pédiatre":        20,
    "pediatre":        20,
    # Standard consultations
    "dentiste":        30,
    "cardiologue":     30,
    "dermatologue":    30,
    "gynécologue":     30,
    "gynecologue":     30,
    "urologue":        30,
    "gastro":          30,
    "endocrinologue":  30,
    "rhumatologue":    30,
    # Longer consultations
    "neurologue":      45,
    "psychiatre":      45,
    "psychologue":     45,
    "chirurgien":      45,
    "orthopédiste":    45,
    "orthopediste":    45,
}

# French day names used as the .day field in disponibilites
FRENCH_DAYS: frozenset[str] = frozenset({
    "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche",
})

# Strings that indicate a closed day (case-insensitive comparison)
CLOSED_MARKERS: frozenset[str] = frozenset({
    "fermé", "ferme", "closed", "close", "closed all day",
})

# Google Maps periods: day integer → French day name
_GMAPS_DAY: dict[int, str] = {
    0: "dimanche",
    1: "lundi",
    2: "mardi",
    3: "mercredi",
    4: "jeudi",
    5: "vendredi",
    6: "samedi",
}

# Regex: matches "HH:MM–HH:MM" or "HH:MM - HH:MM" (any dash variant, optional spaces)
_RANGE_RE = re.compile(
    r"(\d{1,2}[h:]\d{2})\s*[–—\-]+\s*(\d{1,2}[h:]\d{2})",
    re.UNICODE,
)

# Regex: splits "lundi: <time_content>" into (day, time_content)
_DAY_PREFIX_RE = re.compile(
    r"^([a-zàâéèêëîïôùûü]+)\s*:\s*(.+)$",
    re.IGNORECASE | re.UNICODE,
)


# ── Opening hours parsing ──────────────────────────────────────────────────────

def _parse_time_ranges_from_text(time_text: str) -> list[tuple[int, int]]:
    """
    Extract all (open_min, close_min) pairs from a time portion string.

    Handles:
        "08:30–17:00"
        "08:30–12:00, 14:00–17:00"   ← lunch-break schedule

    Returns empty list for closed / unparseable input.
    """
    ranges: list[tuple[int, int]] = []

    # Check for a closed marker before trying range parsing
    if time_text.strip().lower() in CLOSED_MARKERS:
        return []

    # Find all HH:MM–HH:MM patterns (a single comma-separated line may have several)
    for m in _RANGE_RE.finditer(time_text):
        open_min  = _parse_hhmm(m.group(1))
        close_min = _parse_hhmm(m.group(2))
        if open_min is None or close_min is None:
            continue
        if open_min >= close_min:
            continue        # skip overnight / malformed
        ranges.append((open_min, close_min))

    return ranges


def _parse_weekday_text(
    weekday_text: list,
) -> dict[str, list[tuple[int, int]]]:
    """
    Parse a weekday_text array into a day → [(open, close), ...] mapping.

    Each element is a string like "lundi: 08:30–17:00".
    Multi-range days ("lundi: 08:30–12:00, 14:00–17:00") produce multiple tuples.
    Closed days ("dimanche: Fermé") are excluded from the result.

    Returns only days that have at least one valid parseable range.
    """
    schedule: dict[str, list[tuple[int, int]]] = {}

    for line in weekday_text:
        if not isinstance(line, str) or not line.strip():
            continue

        m = _DAY_PREFIX_RE.match(line.strip())
        if not m:
            continue

        day_raw = m.group(1).strip().lower()
        time_text = m.group(2).strip()

        # Normalize to known French day name
        if day_raw not in FRENCH_DAYS:
            continue

        ranges = _parse_time_ranges_from_text(time_text)
        if ranges:
            schedule[day_raw] = ranges

    return schedule


def _parse_periods(periods: list) -> dict[str, list[tuple[int, int]]]:
    """
    Parse Google Maps API `periods` objects into a day schedule.

    Period format:
        {"open":  {"day": 1, "time": "0830"},
         "close": {"day": 1, "time": "1700"}}
    day: 0=Sunday … 6=Saturday

    Returns day → [(open, close)] mapping.
    """
    schedule: dict[str, list[tuple[int, int]]] = {}

    for period in periods:
        if not isinstance(period, dict):
            continue

        open_info  = period.get("open",  {})
        close_info = period.get("close", {})
        if not open_info:
            continue

        day_num = open_info.get("day")
        day = _GMAPS_DAY.get(day_num)
        if day is None:
            continue

        open_min  = _parse_hhmm(str(open_info.get("time",  "")))
        close_min = _parse_hhmm(str(close_info.get("time", "")))

        if open_min is None or close_min is None:
            continue
        if open_min >= close_min:
            continue        # overnight — skip

        schedule.setdefault(day, []).append((open_min, close_min))

    return schedule


def extract_schedule(doctor: dict) -> dict[str, list[tuple[int, int]]]:
    """
    Extract weekly schedule from a doctor document.

    Tries opening_hours.weekday_text first (richer, more reliable for our data).
    Falls back to opening_hours.periods if weekday_text is missing or yields nothing.

    Returns day → [(open_min, close_min), ...] or empty dict if nothing usable.
    """
    oh = doctor.get("opening_hours")
    if not isinstance(oh, dict):
        return {}

    # Primary: weekday_text
    weekday_text = oh.get("weekday_text")
    if isinstance(weekday_text, list) and weekday_text:
        schedule = _parse_weekday_text(weekday_text)
        if schedule:
            return schedule

    # Fallback: periods
    periods = oh.get("periods")
    if isinstance(periods, list) and periods:
        return _parse_periods(periods)

    return {}


# ── Specialty → slot interval ──────────────────────────────────────────────────

def infer_interval(specialty: Optional[str], default: int = DEFAULT_INTERVAL_MINUTES) -> int:
    """
    Return the appropriate slot interval for a specialty.

    Checks SPECIALTY_INTERVALS for an exact or substring match.
    Falls back to `default` when the specialty is unknown.
    """
    if not specialty:
        return default
    key = specialty.strip().lower()
    for pattern, minutes in SPECIALTY_INTERVALS.items():
        if pattern in key:
            return minutes
    return default


# ── Statistics ─────────────────────────────────────────────────────────────────

class Stats:
    """Accumulates counters for a single seeding run."""

    def __init__(self) -> None:
        self.doctors_read             = 0
        self.doctors_with_hours       = 0
        self.doctors_no_hours         = 0
        self.doctors_no_valid_days    = 0
        self.records_inserted         = 0
        self.records_replaced         = 0
        self.records_skipped_dup      = 0
        self.slots_generated          = 0
        self.days_no_slots            = 0     # range too short for even one slot
        self.errors                   = 0

    def report(self) -> None:
        w = 36
        print()
        print("=" * (w + 16))
        print("SEEDING COMPLETE — STATISTICS")
        print("=" * (w + 16))
        print(f"  {'Doctors read':<{w}}: {self.doctors_read}")
        print(f"  {'  with opening_hours':<{w}}: {self.doctors_with_hours}")
        print(f"  {'  skipped (no opening_hours)':<{w}}: {self.doctors_no_hours}")
        print(f"  {'  skipped (0 valid days)':<{w}}: {self.doctors_no_valid_days}")
        print()
        print(f"  {'Records inserted':<{w}}: {self.records_inserted}")
        print(f"  {'Records replaced':<{w}}: {self.records_replaced}")
        print(f"  {'Records skipped (duplicate)':<{w}}: {self.records_skipped_dup}")
        print()
        print(f"  {'Total slots generated':<{w}}: {self.slots_generated}")
        print(f"  {'Days skipped (range < interval)':<{w}}: {self.days_no_slots}")
        print(f"  {'Errors':<{w}}: {self.errors}")
        print("=" * (w + 16))


# ── Main seeder ────────────────────────────────────────────────────────────────

def seed(
    *,
    interval: int = DEFAULT_INTERVAL_MINUTES,
    dry_run: bool = False,
    doctor_id: Optional[str] = None,
    limit: Optional[int] = None,
    replace: bool = False,
) -> Stats:
    """
    Run the availability seeding pipeline.

    Parameters
    ----------
    interval  : Default slot duration in minutes.
    dry_run   : If True, parse and log but write nothing to MongoDB.
    doctor_id : Seed only this specific doctor (_id string).
    limit     : Process at most this many doctors.
    replace   : If True, update existing records instead of skipping them.

    Returns
    -------
    Stats object with counters from this run.
    """
    stats = Stats()

    # ── Connect ───────────────────────────────────────────────────────────────
    print(f"[CONN] Connecting to MongoDB Atlas …")
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10_000)
    try:
        client.admin.command("ping")
    except Exception as exc:
        print(f"[CONN] ERROR: cannot reach MongoDB: {exc}")
        sys.exit(1)
    print(f"[CONN] Connected")

    source_col = client[SOURCE_DB][SOURCE_COLLECTION]
    target_col = client[TARGET_DB][TARGET_COLLECTION]

    # ── Index ─────────────────────────────────────────────────────────────────
    if not dry_run:
        target_col.create_index(
            [("doctorId", 1), ("day", 1)],
            unique=True,
            background=True,
        )
        print(f"[IDX]  Ensured unique index on (doctorId, day)")

    # ── Summary header ────────────────────────────────────────────────────────
    print()
    print(f"[SEED] Source   : {SOURCE_DB}.{SOURCE_COLLECTION}")
    print(f"[SEED] Target   : {TARGET_DB}.{TARGET_COLLECTION}")
    print(f"[SEED] Interval : {interval} min (default; overridden by specialty map)")
    print(f"[SEED] dry_run  : {dry_run}")
    print(f"[SEED] replace  : {replace}")
    if doctor_id:
        print(f"[SEED] filter   : doctor_id={doctor_id!r}")
    if limit:
        print(f"[SEED] limit    : {limit}")
    print()

    # ── Query ─────────────────────────────────────────────────────────────────
    query: dict = {}
    if doctor_id:
        try:
            query["_id"] = ObjectId(doctor_id)
        except Exception:
            print(f"[ERR]  Invalid --doctor-id format: {doctor_id!r}")
            sys.exit(1)

    cursor = source_col.find(query)
    if limit:
        cursor = cursor.limit(limit)

    now = datetime.now(timezone.utc)

    # ── Process each doctor ───────────────────────────────────────────────────
    for doctor in cursor:
        stats.doctors_read += 1
        doc_id    = str(doctor["_id"])
        name      = doctor.get("name", "<unnamed>")
        specialty = doctor.get("specialty")

        # ── Parse opening hours ───────────────────────────────────────────────
        schedule = extract_schedule(doctor)

        if not schedule:
            stats.doctors_no_hours += 1
            print(f"  [SKIP] {name!r:<40}  id={doc_id}  — no opening_hours")
            continue

        stats.doctors_with_hours += 1

        slot_interval = infer_interval(specialty, default=interval)

        # Collect all weekday_text lines for the log if available
        raw_hours = doctor.get("opening_hours", {}).get("weekday_text", [])
        hours_preview = ", ".join(raw_hours[:2]) + ("…" if len(raw_hours) > 2 else "")

        print(
            f"  [DOC] {name!r:<40}  id={doc_id}"
            f"  specialty={specialty!r}"
            f"  interval={slot_interval}min"
            f"  days={sorted(schedule.keys())}"
        )
        if hours_preview:
            print(f"        hours_preview: {hours_preview}")

        days_written = 0

        for day, raw_ranges in sorted(schedule.items()):
            # Apply lunch break: any wide single range is split at 12:00–14:00
            ranges = _apply_lunch_split(raw_ranges)

            slots = _generate_slots_for_ranges(ranges, slot_interval)

            if not slots:
                stats.days_no_slots += 1
                ranges_str = ", ".join(
                    f"{_minutes_to_hhmm(o)}–{_minutes_to_hhmm(c)}" for o, c in ranges
                )
                print(
                    f"        [SKIP_DAY] {day}: range={ranges_str} "
                    f"too short for {slot_interval}-min slot"
                )
                continue

            stats.slots_generated += len(slots)

            # Build human-readable range display for the log
            ranges_display = " + ".join(
                f"{_minutes_to_hhmm(o)}–{_minutes_to_hhmm(c)}" for o, c in ranges
            )
            lunch_tag = " [lunch split]" if len(ranges) > len(raw_ranges) else ""
            print(
                f"        [DAY] {day:<12}  {ranges_display:<25}  "
                f"→ {len(slots):2d} slot(s)  "
                f"[{slots[0]['start']}…{slots[-1]['start']}]{lunch_tag}"
            )

            if dry_run:
                days_written += 1
                continue

            # ── Duplicate detection ───────────────────────────────────────────
            existing = target_col.find_one(
                {"doctorId": doc_id, "day": day},
                projection={"_id": 1},
            )

            # ranges field: lightweight representation of working time blocks
            ranges_docs = [
                {"start": _minutes_to_hhmm(o), "end": _minutes_to_hhmm(c)}
                for o, c in ranges
            ]

            document: dict = {
                "doctorId":                   doc_id,
                "day":                        day,
                "ranges":                     ranges_docs,
                "consultationDurationMinutes": slot_interval,
                "source":                     "google_opening_hours",
                "confidence":                 "low",
                "slots":                      slots,
                "updatedAt":                  now,
            }

            if existing and not replace:
                stats.records_skipped_dup += 1
                print(
                    f"              [DUP]  record exists "
                    f"(pass --replace to overwrite)"
                )
                continue

            if existing and replace:
                target_col.update_one(
                    {"doctorId": doc_id, "day": day},
                    {"$set": document},
                )
                stats.records_replaced += 1
                print(f"              [REP]  replaced → {len(slots)} slot(s)")
            else:
                document["createdAt"] = now
                target_col.insert_one(document)
                stats.records_inserted += 1
                print(f"              [INS]  inserted → {len(slots)} slot(s)")

            days_written += 1

        if days_written == 0 and not dry_run:
            stats.doctors_no_valid_days += 1

    client.close()
    return stats


# ── CLI entry point ────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="seed_availability",
        description=(
            "Seed disponibilites from medical_data_tunisia opening_hours.\n"
            "Generates weekly slot templates for every doctor with opening hours."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/seed_availability.py                 # seed all doctors\n"
            "  python scripts/seed_availability.py --dry-run       # preview only\n"
            "  python scripts/seed_availability.py --limit 3       # test 3 doctors\n"
            "  python scripts/seed_availability.py --replace       # overwrite existing\n"
            "  python scripts/seed_availability.py --interval 20   # 20-min slots\n"
            "  python scripts/seed_availability.py --doctor-id <ObjectId>\n"
        ),
    )
    p.add_argument(
        "--interval", type=int, default=DEFAULT_INTERVAL_MINUTES,
        metavar="MINUTES",
        help=(
            f"Default slot duration in minutes (default: {DEFAULT_INTERVAL_MINUTES}). "
            "Specialty-specific intervals from the built-in map override this."
        ),
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Parse and log but do NOT write anything to MongoDB.",
    )
    p.add_argument(
        "--doctor-id", metavar="ID",
        help="Process only the doctor with this MongoDB _id string.",
    )
    p.add_argument(
        "--limit", type=int, metavar="N",
        help="Process at most N doctors (useful for smoke-testing).",
    )
    p.add_argument(
        "--replace", action="store_true",
        help="Overwrite existing disponibilites records instead of skipping.",
    )
    return p


def main() -> None:
    args = _build_parser().parse_args()

    stats = seed(
        interval=args.interval,
        dry_run=args.dry_run,
        doctor_id=args.doctor_id,
        limit=args.limit,
        replace=args.replace,
    )

    stats.report()

    if args.dry_run:
        print(
            "\n[DRY RUN] Nothing was written. "
            "Remove --dry-run to persist the records."
        )

    sys.exit(1 if stats.errors > 0 else 0)


if __name__ == "__main__":
    main()
