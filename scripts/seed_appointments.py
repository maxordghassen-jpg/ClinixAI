#!/usr/bin/env python3
"""
Seed realistic appointments for the next 14 days.

All appointments are generated from REAL free slots by:
  1. Reading availability templates from disponibilites
  2. Checking exceptions — skip closed/vacation days
  3. Generating slots dynamically from ranges (or falling back to slots array)
  4. Randomly selecting a subset based on per-doctor density tier
  5. Dedup-checking against existing reservations before inserting

Density tiers (assigned once per doctor):
  high   — 50–75% of available slots filled
  medium — 20–40%
  low    — 5–15%

Status distribution:
  ~60% confirmed, ~30% pending, ~10% cancelled

Date storage: datetime object (UTC midnight) — matches reservation service convention.
Time storage: "HH:MM" string in `time` field — matches get_free_slots cross-check.

Usage
-----
    python scripts/seed_appointments.py                 # seed next 14 days
    python scripts/seed_appointments.py --dry-run       # preview only
    python scripts/seed_appointments.py --days 7        # seed next N days
    python scripts/seed_appointments.py --replace       # replace duplicates
    python scripts/seed_appointments.py --limit 200     # cap total appointments
"""
from __future__ import annotations

import argparse
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from bson import ObjectId
from pymongo import MongoClient
from scripts.utils.index_helpers import safe_create_index

# Allow importing pure scheduling-engine modules (no FastAPI/app context needed).
_AGENT_SERVICE = Path(__file__).parent.parent / "agent_service"
if str(_AGENT_SERVICE) not in sys.path:
    sys.path.insert(0, str(_AGENT_SERVICE))

from graphs.shared.scheduling_engine.slot_generator import (  # noqa: E402
    generate_slots,
    generate_slots_from_ranges,
    end_time,
)
from graphs.shared.scheduling_engine.recurrence_engine import INT_TO_FRENCH_DAY  # noqa: E402
from graphs.shared.scheduling_engine.exception_resolver import (  # noqa: E402
    is_day_blocked,
    get_override_ranges,
)
from graphs.shared.scheduling_engine.conflict_detector import filter_free  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Config ────────────────────────────────────────────────────────────────────

MONGO_URI  = "mongodb+srv://admin:Admin3131@medical-cluster.qjwgdmm.mongodb.net/"
AVAIL_DB   = "disponibility"
AVAIL_COL  = "disponibilites"
EXCEPT_COL = "availability_exceptions"
APPT_DB    = "appointment_reservation"
APPT_COL   = "reservations"
PATIENT_DB = "clinix_agent"
PATIENT_COL = "patient_profiles"
DOCTOR_DB  = "medical_data_tunisia"
DOCTOR_COL = "doctors"

DEFAULT_DAYS = 14

STATUS_WEIGHTS = [
    ("confirmed", 0.60),
    ("pending",   0.30),
    ("cancelled", 0.10),
]

DENSITY_TIERS = [
    ("high",   0.25),   # 25% of doctors are high-density
    ("medium", 0.50),   # 50% medium
    ("low",    0.25),   # 25% low
]

DENSITY_FILL = {
    "high":   (0.50, 0.75),
    "medium": (0.20, 0.40),
    "low":    (0.05, 0.15),
}

# ── Exception check ───────────────────────────────────────────────────────────

def _get_exception_for_date(
    except_col: Any,
    doctor_id: str,
    iso_date: str,
) -> Optional[dict]:
    """Return the exception document covering iso_date for doctor_id, or None."""
    return except_col.find_one({
        "doctorId": doctor_id,
        "date":     {"$lte": iso_date},
        "$or": [
            {"endDate": {"$gte": iso_date}},
            {"endDate": None},
        ],
    })


# ── Status sampler ────────────────────────────────────────────────────────────

def _sample_status() -> str:
    r = random.random()
    cumulative = 0.0
    for status, prob in STATUS_WEIGHTS:
        cumulative += prob
        if r < cumulative:
            return status
    return "confirmed"


# ── Density tier sampler ──────────────────────────────────────────────────────

def _sample_tier() -> str:
    r = random.random()
    cumulative = 0.0
    for tier, prob in DENSITY_TIERS:
        cumulative += prob
        if r < cumulative:
            return tier
    return "medium"


# ── Stats ─────────────────────────────────────────────────────────────────────

class Stats:
    def __init__(self) -> None:
        self.doctors_processed = 0
        self.days_checked      = 0
        self.days_skipped_exc  = 0
        self.days_no_template  = 0
        self.slots_available   = 0
        self.appointments_ins  = 0
        self.appointments_dup  = 0
        self.appointments_rep  = 0
        self.errors            = 0

    def report(self) -> None:
        w = 34
        print()
        print("=" * (w + 14))
        print("APPOINTMENTS SEEDING — STATISTICS")
        print("=" * (w + 14))
        print(f"  {'Doctors processed':<{w}}: {self.doctors_processed}")
        print(f"  {'Days checked':<{w}}: {self.days_checked}")
        print(f"  {'  skipped (exception)':<{w}}: {self.days_skipped_exc}")
        print(f"  {'  skipped (no template)':<{w}}: {self.days_no_template}")
        print(f"  {'Total available slots seen':<{w}}: {self.slots_available}")
        print(f"  {'Appointments inserted':<{w}}: {self.appointments_ins}")
        print(f"  {'Appointments skipped (dup)':<{w}}: {self.appointments_dup}")
        print(f"  {'Appointments replaced':<{w}}: {self.appointments_rep}")
        print(f"  {'Errors':<{w}}: {self.errors}")
        print("=" * (w + 14))


# ── Main seeder ───────────────────────────────────────────────────────────────

def seed(
    *,
    days: int = DEFAULT_DAYS,
    dry_run: bool = False,
    replace: bool = False,
    limit: Optional[int] = None,
) -> Stats:
    stats = Stats()

    print("[CONN] Connecting to MongoDB Atlas …")
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10_000)
    try:
        client.admin.command("ping")
    except Exception as exc:
        print(f"[CONN] ERROR: {exc}")
        sys.exit(1)
    print("[CONN] Connected")

    avail_col   = client[AVAIL_DB][AVAIL_COL]
    except_col  = client[AVAIL_DB][EXCEPT_COL]
    appt_col    = client[APPT_DB][APPT_COL]
    patient_col = client[PATIENT_DB][PATIENT_COL]
    doctor_col  = client[DOCTOR_DB][DOCTOR_COL]

    if not dry_run:
        safe_create_index(
            appt_col,
            [("doctorId", 1), ("date", 1), ("time", 1)],
            unique=True,
            background=True,
        )

    # ── Load patients ─────────────────────────────────────────────────────────
    patients = list(patient_col.find({}, {"_id": 1, "name": 1}))
    if not patients:
        print("[WARN] No patients found in patient_profiles — run seed_patients.py first")
        sys.exit(1)
    print(f"[DATA] Loaded {len(patients)} patients")

    # ── Build doctor id → info map ─────────────────────────────────────────────
    doctor_ids_in_templates = avail_col.distinct("doctorId")
    doctors_info: dict[str, dict] = {}
    for template_doc_id in doctor_ids_in_templates:
        try:
            oid = ObjectId(template_doc_id)
            doc = doctor_col.find_one({"_id": oid}, {"name": 1, "specialty": 1})
        except Exception:
            doc = None
        if doc:
            doctors_info[template_doc_id] = {
                "name":      doc.get("name", "Dr. Unknown"),
                "specialty": doc.get("specialty", ""),
            }
        else:
            doctors_info[template_doc_id] = {"name": "Dr. Unknown", "specialty": ""}

    print(f"[DATA] Templates found for {len(doctor_ids_in_templates)} doctors")

    # ── Build template index: doctor_id → { day: template_doc } ──────────────
    templates_by_doctor: dict[str, dict[str, dict]] = {}
    for tmpl in avail_col.find({}):
        doc_id = tmpl.get("doctorId")
        day    = tmpl.get("day")
        if doc_id and day:
            templates_by_doctor.setdefault(doc_id, {})[day] = tmpl

    # ── Date range ────────────────────────────────────────────────────────────
    today     = datetime.now(timezone.utc).date()
    date_range = [today + timedelta(days=i) for i in range(1, days + 1)]

    print(f"\n[SEED] Scan window : next {days} days ({date_range[0]} → {date_range[-1]})")
    print(f"[SEED] dry_run     : {dry_run}")
    print(f"[SEED] replace     : {replace}")
    print()

    for doctor_id, day_templates in templates_by_doctor.items():
        if limit and stats.appointments_ins >= limit:
            break

        stats.doctors_processed += 1
        doc_info  = doctors_info.get(doctor_id, {"name": "Dr. Unknown", "specialty": ""})
        doc_name  = doc_info["name"]
        specialty = doc_info["specialty"]
        tier      = _sample_tier()
        fill_lo, fill_hi = DENSITY_FILL[tier]

        print(f"  [DOC] {doc_name!r:<40}  tier={tier}  specialty={specialty!r}")

        for candidate_date in date_range:
            if limit and stats.appointments_ins >= limit:
                break

            iso_date   = candidate_date.isoformat()
            french_day = INT_TO_FRENCH_DAY[candidate_date.weekday()]
            stats.days_checked += 1

            # ── Exception check ───────────────────────────────────────────────
            exception = _get_exception_for_date(except_col, doctor_id, iso_date)
            if exception:
                if is_day_blocked(exception):
                    stats.days_skipped_exc += 1
                    print(f"        [SKIP] {iso_date} — {exception.get('type', '')}")
                    continue
                override_ranges = get_override_ranges(exception)
                if override_ranges:
                    duration = 30
                    available_starts = generate_slots_from_ranges(override_ranges, duration)
                else:
                    stats.days_skipped_exc += 1
                    continue
            else:
                # ── Template lookup ───────────────────────────────────────────
                template = day_templates.get(french_day)
                if not template:
                    stats.days_no_template += 1
                    continue

                duration = template.get("consultationDurationMinutes", 30)
                available_starts = generate_slots(template, duration)

            if not available_starts:
                stats.days_no_template += 1
                continue

            stats.slots_available += len(available_starts)

            # ── Cross-check existing appointments to get TRUE free slots ──────
            if not dry_run:
                existing_times = {
                    a["time"]
                    for a in appt_col.find(
                        {
                            "doctorId": doctor_id,
                            "date":     datetime(
                                candidate_date.year, candidate_date.month,
                                candidate_date.day, 0, 0, 0, tzinfo=timezone.utc,
                            ),
                        },
                        {"time": 1},
                    )
                    if a.get("time")
                }
                free_starts = filter_free(available_starts, existing_times)
            else:
                free_starts = available_starts

            if not free_starts:
                continue

            # ── Random fill ───────────────────────────────────────────────────
            fill_rate  = random.uniform(fill_lo, fill_hi)
            n_to_book  = max(1, round(len(free_starts) * fill_rate))
            chosen     = random.sample(free_starts, min(n_to_book, len(free_starts)))

            for slot_start in chosen:
                if limit and stats.appointments_ins >= limit:
                    break

                patient     = random.choice(patients)
                patient_id  = str(patient["_id"])
                patient_name = patient.get("name", "")
                status      = _sample_status()
                end         = end_time(slot_start, duration)

                # date stored as UTC midnight datetime object
                date_dt = datetime(
                    candidate_date.year, candidate_date.month, candidate_date.day,
                    0, 0, 0, tzinfo=timezone.utc,
                )
                now = datetime.now(timezone.utc)

                doc = {
                    "doctorId":    doctor_id,
                    "doctorName":  doc_name,
                    "patientId":   patient_id,
                    "patientName": patient_name,
                    "specialty":   specialty,
                    "date":        date_dt,
                    "time":        slot_start,
                    "endTime":     end,
                    "status":      status,
                    "source":      "seed_data",
                    "notes":       "",
                    "createdAt":   now,
                    "updatedAt":   now,
                }

                label = (
                    f"{iso_date} {slot_start}  {doc_name[:25]:<25}  "
                    f"← {patient_name[:20]:<20}  [{status}]"
                )

                if dry_run:
                    print(f"        [DRY] {label}")
                    stats.appointments_ins += 1
                    continue

                existing_appt = appt_col.find_one(
                    {"doctorId": doctor_id, "date": date_dt, "time": slot_start},
                    {"_id": 1},
                )

                try:
                    if existing_appt and not replace:
                        stats.appointments_dup += 1
                        continue
                    if existing_appt and replace:
                        appt_col.update_one(
                            {"doctorId": doctor_id, "date": date_dt, "time": slot_start},
                            {"$set": doc},
                        )
                        stats.appointments_rep += 1
                        print(f"        [REP] {label}")
                    else:
                        appt_col.insert_one(doc)
                        stats.appointments_ins += 1
                        print(f"        [INS] {label}")
                except Exception as e:
                    stats.errors += 1
                    print(f"        [ERR] {label}  — {e}")

    client.close()
    return stats


# ── CLI ───────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="seed_appointments",
        description="Seed appointments from REAL free slots for the next N days.",
    )
    p.add_argument("--days",    type=int, default=DEFAULT_DAYS, metavar="N",
                   help=f"Number of days ahead to seed (default: {DEFAULT_DAYS})")
    p.add_argument("--dry-run", action="store_true",
                   help="Preview only — no writes.")
    p.add_argument("--replace", action="store_true",
                   help="Overwrite existing appointments (same doctor+date+time).")
    p.add_argument("--limit",   type=int, metavar="N",
                   help="Stop after inserting N appointments.")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    stats = seed(
        days=args.days,
        dry_run=args.dry_run,
        replace=args.replace,
        limit=args.limit,
    )
    stats.report()
    if args.dry_run:
        print("\n[DRY RUN] Nothing was written.")
    sys.exit(1 if stats.errors > 0 else 0)


if __name__ == "__main__":
    main()
