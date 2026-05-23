#!/usr/bin/env python3
"""
Seed realistic Tunisian patient profiles into clinix_agent.patient_profiles.

Usage
-----
    python scripts/seed_patients.py                # seed 80 patients
    python scripts/seed_patients.py --dry-run      # preview only
    python scripts/seed_patients.py --count 50     # seed N patients
    python scripts/seed_patients.py --replace      # overwrite by phone
"""
from __future__ import annotations

import argparse
import random
import re
import sys
import unicodedata
import uuid
from datetime import datetime, timezone
from typing import Optional

from pymongo import MongoClient
from scripts.utils.index_helpers import safe_create_index

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Config ────────────────────────────────────────────────────────────────────

MONGO_URI = "mongodb+srv://admin:Admin3131@medical-cluster.qjwgdmm.mongodb.net/"
TARGET_DB  = "clinix_agent"
TARGET_COL = "patient_profiles"
DEFAULT_COUNT = 80

# ── Name pools ────────────────────────────────────────────────────────────────

FIRST_NAMES_MALE = [
    "Mohamed", "Ahmed", "Youssef", "Karim", "Sami", "Amine", "Bilal", "Riadh",
    "Hichem", "Nabil", "Fares", "Skander", "Mehdi", "Walid", "Zied", "Tarek",
    "Oussama", "Anis", "Jawher", "Slim", "Maher", "Lotfi", "Khaled", "Hamza",
    "Wassim", "Wissem", "Aymen", "Seifeddine", "Chokri", "Mondher", "Fethi",
    "Habib", "Haithem", "Hatem", "Nadhir", "Houssem", "Ramzi", "Souhail",
]

FIRST_NAMES_FEMALE = [
    "Amira", "Fatma", "Nadia", "Sana", "Asma", "Mariem", "Ines", "Leila",
    "Rania", "Dhouha", "Emna", "Olfa", "Sirine", "Yosra", "Najwa", "Hana",
    "Salma", "Meriem", "Chaima", "Nesrine", "Rim", "Dorra", "Azza", "Manel",
    "Hajer", "Raja", "Hela", "Nour", "Wafa", "Houda", "Lobna", "Sonia",
    "Amal", "Souad", "Faten", "Abir", "Mouna", "Nadia", "Rahma",
]

LAST_NAMES = [
    "Ben Ali", "Ben Salah", "Ben Youssef", "Ben Ahmed", "Ben Amor",
    "Trabelsi", "Mejri", "Chaabane", "Ayari", "Gharbi", "Jebali",
    "Bouazizi", "Hammami", "Khelifi", "Maaloul", "Mansouri", "Hamdi",
    "Riahi", "Abidi", "Dridi", "Ferchichi", "Guesmi", "Hnid", "Jlassi",
    "Karray", "Letaief", "Mahjoub", "Nasri", "Ouali", "Selmi", "Souissi",
    "Tlili", "Turki", "Zairi", "Zouari", "Belhaj", "Belhadj", "Baccouche",
    "Chebbi", "Dali", "Elloumi", "Ferjani", "Guedria", "Hamrouni",
    "Jaziri", "Khalfallah", "Labidi", "Meddeb", "Nefzi", "Ouerghi",
]

# Tunisian mobile prefixes (operators: Ooredoo=2x/5x, Orange=9x, Tunisie Telecom=7x)
MOBILE_PREFIXES = ["20", "21", "22", "23", "25", "26", "27", "50", "52", "53",
                   "54", "55", "56", "58", "72", "74", "90", "92", "94", "95", "97", "98", "99"]

EMAIL_DOMAINS = ["gmail.com", "yahoo.fr", "outlook.com", "hotmail.fr", "icloud.com"]


# ── Generators ────────────────────────────────────────────────────────────────

def _ascii_slug(name: str) -> str:
    """Convert 'Ben Salah' → 'bensalah' for email generation."""
    normalized = unicodedata.normalize("NFD", name)
    ascii_str = normalized.encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", ascii_str.lower())


def _make_phone() -> str:
    prefix = random.choice(MOBILE_PREFIXES)
    suffix = "".join(str(random.randint(0, 9)) for _ in range(6))
    return f"+216{prefix}{suffix}"


def _make_email(first: str, last: str, used: set[str]) -> str:
    base_f = _ascii_slug(first)
    base_l = _ascii_slug(last)
    domain  = random.choice(EMAIL_DOMAINS)
    sep = random.choice([".", "_", ""])
    candidates = [
        f"{base_f}{sep}{base_l}@{domain}",
        f"{base_l}{sep}{base_f}@{domain}",
        f"{base_f[0]}{sep}{base_l}@{domain}",
        f"{base_f}{sep}{base_l}{random.randint(1, 99)}@{domain}",
    ]
    for c in candidates:
        if c not in used:
            return c
    return f"{base_f}{base_l}{random.randint(100, 999)}@{domain}"


def generate_patients(count: int) -> list[dict]:
    phones_used: set[str] = set()
    emails_used: set[str] = set()
    patients: list[dict] = []
    now = datetime.now(timezone.utc)

    attempts = 0
    while len(patients) < count and attempts < count * 10:
        attempts += 1
        gender = random.choice(["M", "F"])
        first = random.choice(FIRST_NAMES_MALE if gender == "M" else FIRST_NAMES_FEMALE)
        last  = random.choice(LAST_NAMES)
        full  = f"{first} {last}"

        phone = _make_phone()
        if phone in phones_used:
            continue
        phones_used.add(phone)

        email = _make_email(first, last, emails_used)
        emails_used.add(email)

        patients.append({
            "patient_id": str(uuid.uuid4()),
            "name":       full,
            "phone":      phone,
            "email":      email,
            "gender":     gender,
            "createdAt":  now,
            "updatedAt":  now,
        })

    return patients


# ── Stats ─────────────────────────────────────────────────────────────────────

class Stats:
    def __init__(self) -> None:
        self.generated = 0
        self.inserted  = 0
        self.replaced  = 0
        self.skipped   = 0
        self.errors    = 0

    def report(self) -> None:
        w = 30
        print()
        print("=" * (w + 14))
        print("PATIENTS SEEDING — STATISTICS")
        print("=" * (w + 14))
        print(f"  {'Generated':<{w}}: {self.generated}")
        print(f"  {'Inserted':<{w}}: {self.inserted}")
        print(f"  {'Replaced (phone match)':<{w}}: {self.replaced}")
        print(f"  {'Skipped (duplicate)':<{w}}: {self.skipped}")
        print(f"  {'Errors':<{w}}: {self.errors}")
        print("=" * (w + 14))


# ── Main ──────────────────────────────────────────────────────────────────────

def seed(
    *,
    count: int = DEFAULT_COUNT,
    dry_run: bool = False,
    replace: bool = False,
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

    col = client[TARGET_DB][TARGET_COL]

    if not dry_run:
        # Remove any documents left from a previous failed seed that have no patient_id.
        # These would block the unique index on patient_id with a null key clash.
        purged = col.delete_many({"patient_id": {"$in": [None, ""]}}).deleted_count
        if purged:
            print(f"[CLEAN] Removed {purged} document(s) with null/missing patient_id")

        safe_create_index(col, "phone",      unique=True, background=True)
        safe_create_index(col, "patient_id", unique=True, background=True)

    patients = generate_patients(count)
    stats.generated = len(patients)

    print(f"\n[SEED] Target : {TARGET_DB}.{TARGET_COL}")
    print(f"[SEED] Count  : {len(patients)}")
    print(f"[SEED] dry_run: {dry_run}")
    print(f"[SEED] replace: {replace}")
    print()

    for p in patients:
        label = f"{p['name']:<35}  {p['phone']}"
        if dry_run:
            print(f"  [DRY] {label}  {p['email']}")
            continue

        existing = col.find_one({"phone": p["phone"]}, projection={"_id": 1})
        if existing and not replace:
            stats.skipped += 1
            print(f"  [DUP] {label}")
            continue

        try:
            if existing and replace:
                col.update_one({"phone": p["phone"]}, {"$set": p})
                stats.replaced += 1
                print(f"  [REP] {label}")
            else:
                col.insert_one(p)
                stats.inserted += 1
                print(f"  [INS] {label}")
        except Exception as exc:
            stats.errors += 1
            print(f"  [ERR] {label}  — {exc}")

    client.close()
    return stats


# ── CLI ───────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="seed_patients",
        description="Seed realistic Tunisian patient profiles into clinix_agent.patient_profiles.",
    )
    p.add_argument("--count",   type=int, default=DEFAULT_COUNT, metavar="N",
                   help=f"Number of patients to generate (default: {DEFAULT_COUNT})")
    p.add_argument("--dry-run", action="store_true",
                   help="Preview only — no writes to MongoDB.")
    p.add_argument("--replace", action="store_true",
                   help="Overwrite existing records matched by phone number.")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    stats = seed(count=args.count, dry_run=args.dry_run, replace=args.replace)
    stats.report()
    if args.dry_run:
        print("\n[DRY RUN] Nothing was written.")
    sys.exit(1 if stats.errors > 0 else 0)


if __name__ == "__main__":
    main()
