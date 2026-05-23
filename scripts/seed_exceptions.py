#!/usr/bin/env python3
"""
Seed availability exceptions (vacation / closure / override) for doctors that
already have templates in disponibility.disponibilites.

Distribution (of doctors with templates):
  ~20% → vacation      (date range, 5–10 days starting within next 30 days)
  ~10% → closure       (single day within next 14 days)
  ~8%  → override      (custom ranges, single day within next 14 days)

Usage
-----
    python scripts/seed_exceptions.py              # seed all eligible doctors
    python scripts/seed_exceptions.py --dry-run    # preview only
    python scripts/seed_exceptions.py --replace    # overwrite existing
    python scripts/seed_exceptions.py --limit 10   # cap at N exceptions
"""
from __future__ import annotations

import argparse
import random
import sys
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from pymongo import MongoClient
from scripts.utils.index_helpers import safe_create_index

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Config ────────────────────────────────────────────────────────────────────

MONGO_URI    = "mongodb+srv://admin:Admin3131@medical-cluster.qjwgdmm.mongodb.net/"
AVAIL_DB     = "disponibility"
AVAIL_COL    = "disponibilites"
EXCEPT_COL   = "availability_exceptions"

VACATION_PROB = 0.20
CLOSURE_PROB  = 0.10
OVERRIDE_PROB = 0.08

VACATION_REASONS = [
    "Congés annuels", "Vacances d'été", "Vacances de fin d'année",
    "Repos médical", "Formation continue", "Voyage professionnel",
    "Congé personnel",
]
CLOSURE_REASONS = [
    "Indisponibilité exceptionnelle", "Jour férié", "Conférence médicale",
    "Formation", "Obligation personnelle", "Maintenance du cabinet",
]
OVERRIDE_REASONS = [
    "Horaires réduits", "Disponibilité exceptionnelle", "Urgence planifiée",
    "Permanence de garde",
]

OVERRIDE_RANGE_OPTIONS = [
    [{"start": "09:00", "end": "12:00"}],
    [{"start": "14:00", "end": "18:00"}],
    [{"start": "08:00", "end": "11:00"}],
    [{"start": "10:00", "end": "13:00"}, {"start": "15:00", "end": "17:00"}],
    [{"start": "09:00", "end": "11:30"}],
]


# ── Core ──────────────────────────────────────────────────────────────────────

def _iso(d: date) -> str:
    return d.isoformat()


def build_exception(doctor_id: str, today: date) -> Optional[dict]:
    """
    Randomly decide whether this doctor gets an exception and build the document.
    Returns None if the doctor is not selected for any exception type.
    """
    roll = random.random()

    now = datetime.now(timezone.utc)

    if roll < VACATION_PROB:
        offset    = random.randint(2, 30)
        length    = random.randint(5, 10)
        start     = today + timedelta(days=offset)
        end       = start  + timedelta(days=length - 1)
        return {
            "doctorId":  doctor_id,
            "type":      "vacation",
            "date":      _iso(start),
            "endDate":   _iso(end),
            "reason":    random.choice(VACATION_REASONS),
            "overrideRanges": [],
            "createdAt": now,
            "updatedAt": now,
        }

    if roll < VACATION_PROB + CLOSURE_PROB:
        offset = random.randint(1, 14)
        day    = today + timedelta(days=offset)
        return {
            "doctorId":  doctor_id,
            "type":      "closure",
            "date":      _iso(day),
            "endDate":   None,
            "reason":    random.choice(CLOSURE_REASONS),
            "overrideRanges": [],
            "createdAt": now,
            "updatedAt": now,
        }

    if roll < VACATION_PROB + CLOSURE_PROB + OVERRIDE_PROB:
        offset = random.randint(1, 14)
        day    = today + timedelta(days=offset)
        return {
            "doctorId":      doctor_id,
            "type":          "override",
            "date":          _iso(day),
            "endDate":       None,
            "reason":        random.choice(OVERRIDE_REASONS),
            "overrideRanges": random.choice(OVERRIDE_RANGE_OPTIONS),
            "createdAt": now,
            "updatedAt": now,
        }

    return None


# ── Stats ─────────────────────────────────────────────────────────────────────

class Stats:
    def __init__(self) -> None:
        self.doctors_scanned = 0
        self.vacation_ins    = 0
        self.closure_ins     = 0
        self.override_ins    = 0
        self.skipped         = 0
        self.replaced        = 0
        self.errors          = 0

    @property
    def total_inserted(self) -> int:
        return self.vacation_ins + self.closure_ins + self.override_ins

    def report(self) -> None:
        w = 30
        print()
        print("=" * (w + 14))
        print("EXCEPTIONS SEEDING — STATISTICS")
        print("=" * (w + 14))
        print(f"  {'Doctors scanned':<{w}}: {self.doctors_scanned}")
        print(f"  {'Vacation exceptions inserted':<{w}}: {self.vacation_ins}")
        print(f"  {'Closure exceptions inserted':<{w}}: {self.closure_ins}")
        print(f"  {'Override exceptions inserted':<{w}}: {self.override_ins}")
        print(f"  {'Skipped (duplicate)':<{w}}: {self.skipped}")
        print(f"  {'Replaced':<{w}}: {self.replaced}")
        print(f"  {'Errors':<{w}}: {self.errors}")
        print("=" * (w + 14))


# ── Main ──────────────────────────────────────────────────────────────────────

def seed(
    *,
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

    avail_col  = client[AVAIL_DB][AVAIL_COL]
    except_col = client[AVAIL_DB][EXCEPT_COL]

    if not dry_run:
        safe_create_index(
            except_col,
            [("doctorId", 1), ("date", 1)],
            background=True,
        )

    # Collect unique doctor IDs from templates
    doctor_ids = avail_col.distinct("doctorId")
    random.shuffle(doctor_ids)
    if limit:
        # limit here limits the exceptions count, not doctors scanned — but
        # we stop early once we've inserted `limit` exceptions
        pass

    today = datetime.now(timezone.utc).date()

    print(f"\n[SEED] Source   : {AVAIL_DB}.{AVAIL_COL}")
    print(f"[SEED] Target   : {AVAIL_DB}.{EXCEPT_COL}")
    print(f"[SEED] Doctors  : {len(doctor_ids)} with templates")
    print(f"[SEED] dry_run  : {dry_run}")
    print(f"[SEED] replace  : {replace}")
    print()

    for doc_id in doctor_ids:
        if limit and stats.total_inserted >= limit:
            break

        stats.doctors_scanned += 1
        exc = build_exception(doc_id, today)
        if exc is None:
            continue

        exc_type = exc["type"]
        label = (
            f"doctor={doc_id[:12]}…  type={exc_type:<8}  "
            f"date={exc['date']}"
            + (f"→{exc['endDate']}" if exc.get("endDate") else "")
        )

        if dry_run:
            print(f"  [DRY] {label}  reason={exc['reason']!r}")
            if exc_type == "vacation":
                stats.vacation_ins += 1
            elif exc_type == "closure":
                stats.closure_ins += 1
            else:
                stats.override_ins += 1
            continue

        existing = except_col.find_one(
            {"doctorId": doc_id, "date": exc["date"]},
            projection={"_id": 1},
        )

        try:
            if existing and not replace:
                stats.skipped += 1
                print(f"  [DUP] {label}")
                continue

            if existing and replace:
                except_col.update_one(
                    {"doctorId": doc_id, "date": exc["date"]},
                    {"$set": exc},
                )
                stats.replaced += 1
                print(f"  [REP] {label}")
            else:
                except_col.insert_one(exc)
                print(f"  [INS] {label}  reason={exc['reason']!r}")

            if exc_type == "vacation":
                stats.vacation_ins += 1
            elif exc_type == "closure":
                stats.closure_ins += 1
            else:
                stats.override_ins += 1

        except Exception as e:
            stats.errors += 1
            print(f"  [ERR] {label}  — {e}")

    client.close()
    return stats


# ── CLI ───────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="seed_exceptions",
        description="Seed vacation/closure/override exceptions for doctors with availability templates.",
    )
    p.add_argument("--dry-run", action="store_true",
                   help="Preview only — no writes.")
    p.add_argument("--replace", action="store_true",
                   help="Overwrite existing exception for the same doctor+date.")
    p.add_argument("--limit", type=int, metavar="N",
                   help="Stop after inserting N exceptions.")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    stats = seed(dry_run=args.dry_run, replace=args.replace, limit=args.limit)
    stats.report()
    if args.dry_run:
        print("\n[DRY RUN] Nothing was written.")
    sys.exit(1 if stats.errors > 0 else 0)


if __name__ == "__main__":
    main()
