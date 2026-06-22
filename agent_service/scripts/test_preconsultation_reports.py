"""
Pre-Consultation Report integration tests.

Tests:
  1. Report generation with full profile + preconsultation
  2. Report persistence — document exists in MongoDB after generation
  3. Appointment linkage — report.appointment_id matches booking
  4. GET /reports/appointment/{id} — doctor retrieves report (200)
  5. GET /reports/appointment/{id} — unknown appointment returns 404
  6. Missing preconsultation — report saved with empty clinical section
  7. Missing profile — report saved with empty patient_snapshot
  8. Doctor-only access — unauthenticated request returns 401

Requires a running agent_service (default http://localhost:8001)
and a reachable MongoDB.

Run from agent_service/ directory:
    python scripts/test_preconsultation_reports.py
"""

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

BASE     = os.getenv("AGENT_BASE_URL", "http://localhost:8001")
PASS_STR = "PASS"
FAIL_STR = "FAIL"

results: list[tuple[str, bool, str]] = []


# ── Helpers ────────────────────────────────────────────────────────────────────

import urllib.request
import urllib.error


def req(
    method: str,
    path: str,
    body: dict | None = None,
    token: str | None = None,
) -> tuple[int, dict]:
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body else None
    headers: dict = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {"error": str(e)}
    except Exception as e:
        return 0, {"error": str(e)}


def check(name: str, passed: bool, detail: str = "") -> None:
    results.append((name, passed, detail))
    icon = PASS_STR if passed else FAIL_STR
    print(f"  {icon}  {name}" + (f"  [{detail}]" if detail else ""))


# ── Direct MongoDB helpers ─────────────────────────────────────────────────────

async def _insert_test_data(
    patient_id: str,
    session_id: str,
    appointment_id: str,
    doctor_id: str,
) -> None:
    from app.db.mongo_client import connect_to_mongo, get_database
    await connect_to_mongo()
    db = get_database()
    if db is None:
        return

    now = datetime.now(timezone.utc)

    # patient_profiles stub
    await db["patient_profiles"].update_one(
        {"patient_id": patient_id},
        {"$set": {
            "patient_id":       patient_id,
            "name":             "Test Patient Report",
            "gender":           "female",
            "date_of_birth":    "1990-06-15",
            "phone":            "+21699000001",
            "email":            f"{patient_id}@test.com",
            "blood_type":       "B+",
            "weight":           65.0,
            "height":           170.0,
            "smoking_status":   "never",
            "alcohol_consumption": "never",
            "allergies":        ["Penicillin"],
            "chronic_conditions":  [],
            "current_medications": [],
            "updated_at":       now,
        }, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )

    # preconsultation_data stub
    await db["preconsultation_data"].update_one(
        {"patient_id": patient_id, "session_id": session_id},
        {"$set": {
            "patient_id":          patient_id,
            "session_id":          session_id,
            "appointment_id":      appointment_id,
            "chief_complaint":     "persistent headache",
            "duration":            "3 days",
            "severity":            6,
            "associated_symptoms": ["nausea", "light sensitivity"],
            "urgency":             "medium",
            "summary_text":        (
                "Patient presents with a persistent headache lasting 3 days, "
                "rated 6/10 in severity.  Associated symptoms include nausea "
                "and light sensitivity.  Urgency assessed as medium."
            ),
            "updated_at": now,
        }, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )


async def _cleanup_test_data(
    patient_id: str,
    appointment_id: str,
) -> None:
    from app.db.mongo_client import get_database
    db = get_database()
    if db is None:
        return
    await db["patient_profiles"].delete_one({"patient_id": patient_id})
    await db["preconsultation_data"].delete_many({"patient_id": patient_id})
    await db["preconsultation_reports"].delete_many({"appointment_id": appointment_id})


async def _fetch_report_from_mongo(appointment_id: str) -> dict | None:
    from app.db.mongo_client import get_database
    db = get_database()
    if db is None:
        return None
    return await db["preconsultation_reports"].find_one(
        {"appointment_id": appointment_id}, {"_id": 0}
    )


# ── Tests ──────────────────────────────────────────────────────────────────────

async def test_report_generation_and_persistence() -> str:
    """Generate a report with full profile+preconsultation and verify MongoDB."""
    from app.services.report_generation_service import generate_preconsultation_report

    patient_id     = f"test-report-patient-{uuid.uuid4().hex[:8]}"
    session_id     = f"patient:{patient_id}"
    appointment_id = f"test-appt-{uuid.uuid4().hex[:8]}"
    doctor_id      = f"test-doctor-{uuid.uuid4().hex[:8]}"

    await _insert_test_data(patient_id, session_id, appointment_id, doctor_id)

    print("\n-- Report generation (full data) --------------------------")
    doc_id = await generate_preconsultation_report(
        appointment_id=appointment_id,
        doctor_id=doctor_id,
        patient_id=patient_id,
        session_id=session_id,
    )
    check("generate_preconsultation_report returns doc_id", bool(doc_id), f"id={doc_id}")

    # ── Verify MongoDB ──────────────────────────────────────────────────────
    report = await _fetch_report_from_mongo(appointment_id)
    check("Report exists in preconsultation_reports", report is not None)
    if not report:
        return appointment_id

    check("appointment_id matches",    report.get("appointment_id") == appointment_id)
    check("doctor_id matches",         report.get("doctor_id")      == doctor_id)
    check("patient_id matches",        report.get("patient_id")     == patient_id)
    check("generated_by = clinixai",   report.get("generated_by")   == "clinixai")

    ps = report.get("patient_snapshot", {})
    check("snapshot.name = Test Patient Report",  ps.get("name") == "Test Patient Report")
    check("snapshot.blood_type = B+",             ps.get("blood_type") == "B+")
    check("snapshot.allergies = ['Penicillin']",  ps.get("allergies") == ["Penicillin"])

    pc = report.get("preconsultation_snapshot", {})
    check("preconsult.chief_complaint present",    bool(pc.get("chief_complaint")))
    check("preconsult.urgency = medium",           pc.get("urgency") == "medium")
    check("preconsult.severity = 6",               pc.get("severity") == 6)
    check("ai_summary non-empty",                  bool(report.get("ai_summary")))

    return appointment_id


async def test_missing_preconsultation() -> str:
    """Report generation gracefully handles a patient with no preconsultation."""
    from app.services.report_generation_service import generate_preconsultation_report

    patient_id     = f"test-nopreconsult-{uuid.uuid4().hex[:8]}"
    session_id     = f"patient:{patient_id}"
    appointment_id = f"test-appt-nopre-{uuid.uuid4().hex[:8]}"
    doctor_id      = f"test-doctor-{uuid.uuid4().hex[:8]}"

    # Insert ONLY profile, no preconsultation
    from app.db.mongo_client import get_database
    db = get_database()
    if db is not None:
        now = datetime.now(timezone.utc)
        await db["patient_profiles"].update_one(
            {"patient_id": patient_id},
            {"$set": {"patient_id": patient_id, "name": "No Preconsult", "updated_at": now},
             "$setOnInsert": {"created_at": now}},
            upsert=True,
        )

    print("\n-- Report generation (no preconsultation) -----------------")
    doc_id = await generate_preconsultation_report(
        appointment_id=appointment_id,
        doctor_id=doctor_id,
        patient_id=patient_id,
        session_id=session_id,
    )
    check("Report created despite missing preconsultation", bool(doc_id))

    report = await _fetch_report_from_mongo(appointment_id)
    check("Report persisted", report is not None)
    if report:
        pc = report.get("preconsultation_snapshot", {})
        check("chief_complaint is None",        pc.get("chief_complaint") is None)
        check("urgency is None",                pc.get("urgency") is None)
        check("ai_summary is empty string",     report.get("ai_summary") == "")

    # cleanup
    if db:
        await db["patient_profiles"].delete_one({"patient_id": patient_id})
        await db["preconsultation_reports"].delete_many({"appointment_id": appointment_id})

    return appointment_id


async def test_missing_profile() -> None:
    """Report generation gracefully handles a patient with no profile."""
    from app.services.report_generation_service import generate_preconsultation_report

    patient_id     = f"test-noprofile-{uuid.uuid4().hex[:8]}"
    session_id     = f"patient:{patient_id}"
    appointment_id = f"test-appt-noprof-{uuid.uuid4().hex[:8]}"
    doctor_id      = f"test-doctor-{uuid.uuid4().hex[:8]}"

    # Insert ONLY preconsultation, no profile
    from app.db.mongo_client import get_database
    db = get_database()
    if db is not None:
        now = datetime.now(timezone.utc)
        await db["preconsultation_data"].update_one(
            {"patient_id": patient_id, "session_id": session_id},
            {"$set": {"patient_id": patient_id, "session_id": session_id,
                      "chief_complaint": "headache", "severity": 4,
                      "urgency": "low", "updated_at": now},
             "$setOnInsert": {"created_at": now}},
            upsert=True,
        )

    print("\n-- Report generation (no profile) -------------------------")
    doc_id = await generate_preconsultation_report(
        appointment_id=appointment_id,
        doctor_id=doctor_id,
        patient_id=patient_id,
        session_id=session_id,
    )
    check("Report created despite missing profile", bool(doc_id))

    report = await _fetch_report_from_mongo(appointment_id)
    check("Report persisted", report is not None)
    if report:
        ps = report.get("patient_snapshot", {})
        check("patient_snapshot.name is None",  ps.get("name") is None)
        check("preconsult.urgency present",
              report.get("preconsultation_snapshot", {}).get("urgency") == "low")

    if db:
        await db["preconsultation_data"].delete_many({"patient_id": patient_id})
        await db["preconsultation_reports"].delete_many({"appointment_id": appointment_id})


def test_http_get_report(appointment_id: str, doctor_jwt: str) -> None:
    """GET /reports/appointment/{id} returns the report for a valid appointment."""
    print("\n-- HTTP: GET /reports/appointment/{id} --------------------")

    status, body = req("GET", f"/reports/appointment/{appointment_id}", token=doctor_jwt)
    check("GET report returns 200", status == 200, f"got {status}")
    if status == 200:
        check("appointment_id in response", body.get("appointment_id") == appointment_id)
        check("patient_snapshot present",  "patient_snapshot" in body)
        check("preconsultation_snapshot present", "preconsultation_snapshot" in body)
        check("ai_summary present",        "ai_summary" in body)


def test_http_report_not_found(doctor_jwt: str) -> None:
    """GET /reports/appointment/{id} returns 404 for an unknown appointment."""
    print("\n-- HTTP: 404 for unknown appointment ----------------------")
    status, _ = req("GET", f"/reports/appointment/nonexistent-id-{uuid.uuid4().hex}", token=doctor_jwt)
    check("Unknown appointment returns 404", status == 404, f"got {status}")


def test_http_unauthenticated() -> None:
    """GET /reports/appointment/{id} without token returns 401."""
    print("\n-- HTTP: 401 without token --------------------------------")
    status, _ = req("GET", "/reports/appointment/any-id")
    check("No token returns 401", status == 401, f"got {status}")


# ── Runner ─────────────────────────────────────────────────────────────────────

async def async_main() -> None:
    from app.db.mongo_client import connect_to_mongo, close_mongo_connection

    print(f"\nPre-Consultation Report Tests  ->  {BASE}\n")

    # Connectivity check
    import urllib.request as _ureq
    try:
        with _ureq.urlopen(f"{BASE}/", timeout=4) as r:
            print(f"  agent_service reachable  (GET / -> {r.status})\n")
    except Exception:
        print(f"\n{FAIL_STR}  agent_service unreachable at {BASE}")
        sys.exit(1)

    await connect_to_mongo()

    # ── Async tests (direct service calls) ──────────────────────────────────
    appointment_id = await test_report_generation_and_persistence()
    await test_missing_preconsultation()
    await test_missing_profile()

    # ── HTTP tests (require a running server) ────────────────────────────────
    # Build a minimal doctor JWT for HTTP tests.
    # The agent_service accepts any valid JWT — we build one using the same secret.
    import os
    jwt_secret = os.getenv("JWT_SECRET", "clinixai-jwt-secret-change-in-production-2026")
    try:
        from jose import jwt as _jwt
        doctor_jwt = _jwt.encode(
            {"sub": "test@doctor.com", "role": "doctor", "doctor_id": "test-doc-001"},
            jwt_secret,
            algorithm="HS256",
        )
    except Exception:
        doctor_jwt = ""

    if doctor_jwt:
        test_http_get_report(appointment_id, doctor_jwt)
        test_http_report_not_found(doctor_jwt)
    else:
        print("\n  Skipping HTTP auth tests (jose not available)")

    test_http_unauthenticated()

    # ── Cleanup ──────────────────────────────────────────────────────────────
    await _cleanup_test_data(
        patient_id=appointment_id.replace("test-appt-", "test-report-patient-"),
        appointment_id=appointment_id,
    )

    await close_mongo_connection()

    # ── Summary ──────────────────────────────────────────────────────────────
    passed = sum(1 for _, ok, _ in results if ok)
    total  = len(results)
    print(f"\n{'─' * 55}")
    print(f"  Result: {passed}/{total} passed")
    if passed < total:
        print("\n  Failed tests:")
        for name, ok, detail in results:
            if not ok:
                print(f"    {FAIL_STR}  {name}" + (f"  [{detail}]" if detail else ""))
    print()
    sys.exit(0 if passed == total else 1)


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
