#!/usr/bin/env python3
"""
Create MongoDB indexes for ClinixAI.

Safe to run multiple times — create_index is idempotent.

Usage
-----
    python scripts/create_indexes.py
"""
import sys

from pymongo import MongoClient, ASCENDING

MONGO_URI = "mongodb+srv://admin:Admin3131@medical-cluster.qjwgdmm.mongodb.net/"


def create_indexes() -> None:
    print("[CONN] Connecting to MongoDB Atlas …")
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10_000)
    try:
        client.admin.command("ping")
    except Exception as exc:
        print(f"[CONN] ERROR: cannot reach MongoDB: {exc}")
        sys.exit(1)
    print("[CONN] Connected\n")

    # ── disponibilites ─────────────────────────────────────────────────────────
    disponibilites = client["disponibility"]["disponibilites"]
    idx = disponibilites.create_index(
        [("doctorId", ASCENDING), ("day", ASCENDING)],
        unique=True,
        name="idx_doctorId_day_unique",
        background=True,
    )
    print(f"[IDX]  disponibilites — (doctorId, day) unique  →  {idx}")

    # ── availability_exceptions ────────────────────────────────────────────────
    exceptions = client["disponibility"]["availability_exceptions"]
    idx = exceptions.create_index(
        [("doctorId", ASCENDING), ("date", ASCENDING)],
        name="idx_doctorId_date",
        background=True,
    )
    print(f"[IDX]  availability_exceptions — (doctorId, date)  →  {idx}")

    # ── reservations ───────────────────────────────────────────────────────────
    reservations = client["appointment_reservation"]["reservations"]

    idx = reservations.create_index(
        [("doctorId", ASCENDING), ("date", ASCENDING), ("time", ASCENDING)],
        unique=True,
        name="idx_doctorId_date_time_unique",
        background=True,
    )
    print(f"[IDX]  reservations — (doctorId, date, time) unique  →  {idx}")

    idx = reservations.create_index(
        [("patientId", ASCENDING), ("date", ASCENDING)],
        name="idx_patientId_date",
        background=True,
    )
    print(f"[IDX]  reservations — (patientId, date)  →  {idx}")

    client.close()
    print("\n[DONE] All indexes ensured.")


if __name__ == "__main__":
    create_indexes()
