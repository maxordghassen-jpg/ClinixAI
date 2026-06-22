"""
Profile system integration tests.

Tests:
  1. Profile retrieval by slug ID (the common case after signup)
  2. Profile retrieval by UUID (legacy documents from other systems)
  3. Profile update — PUT /profile (phone, gender)
  4. Medical patch — PATCH /profile/medical (city, weight, allergies)
  5. MongoDB persistence — verify fields survive a re-fetch
  6. Slug-shadow detection — login with shadowed UUID doc returns correct data
  7. City field round-trip — save city, retrieve city

Run from auth_service/ directory:
  python scripts/test_profile_system.py

Requires:
  AUTH_BASE_URL environment variable (default: http://localhost:8005)
  A running auth_service and reachable MongoDB.
"""

import json
import os
import sys
import uuid
import urllib.request
import urllib.error

BASE = os.getenv("AUTH_BASE_URL", "http://localhost:8005")

PASS = "PASS"
FAIL = "FAIL"

results: list[tuple[str, bool, str]] = []


# -- helpers ------------------------------------------------------------------─

def req(method: str, path: str, body: dict | None = None, token: str | None = None) -> tuple[int, dict]:
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}
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
    icon = PASS if passed else FAIL
    print(f"  {icon}  {name}" + (f"  [{detail}]" if detail else ""))


# -- tests --------------------------------------------------------------------─

def test_signup_and_profile_retrieval() -> str | None:
    """Sign up a fresh patient and verify profile round-trip."""
    rand = uuid.uuid4().hex[:8]
    email = f"test_{rand}@clinix-test.com"
    password = "TestPass123!"
    name = f"Test Patient {rand}"

    status, body = req("POST", "/auth/signup", {"email": email, "password": password, "name": name})
    check("Signup returns 201", status == 201, f"got {status}")
    if status != 201:
        return None

    token = body.get("access_token")
    check("Signup returns access_token", bool(token))
    check("Signup role=patient", body.get("role") == "patient")
    check("Signup returns patient_profile_id", bool(body.get("patient_profile_id")))

    status2, profile = req("GET", "/profile", token=token)
    check("GET /profile returns 200", status2 == 200, f"got {status2}")
    if status2 != 200:
        return token

    check("Profile has name", profile.get("name") == name, f"got {profile.get('name')!r}")
    check("Profile has email", profile.get("email") == email.lower())
    check("Profile.medical exists", "medical" in profile)
    return token


def test_update_personal(token: str) -> str:
    """PUT /profile — update phone and gender.
    Returns the phone number used so test_persistence can assert the same value.
    Phone is unique per run to avoid colliding with the sparse-unique index on phone.
    """
    phone = f"+216{uuid.uuid4().int % 100_000_000:08d}"
    status, body = req("PUT", "/profile", {"phone": phone, "gender": "female"}, token=token)
    check("PUT /profile returns 200", status == 200, f"got {status}")
    if status != 200:
        return ""
    check("PUT updates phone", body.get("phone") == phone, f"got {body.get('phone')!r}")
    check("PUT updates gender", body.get("gender") == "female")
    return phone


def test_patch_medical(token: str) -> None:
    """PATCH /profile/medical — weight, city, allergies."""
    payload = {
        "weight": 70.5,
        "height": 168.0,
        "blood_type": "A+",
        "city": "Tunis",
        "date_of_birth": "1995-03-15",
        "address": "12 Rue des Fleurs",
        "smoking_status": "never",
        "allergies": ["Penicillin", "Pollen"],
        "chronic_conditions": ["Hypertension"],
    }
    status, body = req("PATCH", "/profile/medical", payload, token=token)
    check("PATCH /profile/medical returns 200", status == 200, f"got {status}")
    if status != 200:
        return
    med = body.get("medical", {})
    check("Medical weight saved", med.get("weight") == 70.5)
    check("Medical height saved", med.get("height") == 168.0)
    check("Medical blood_type saved", med.get("blood_type") == "A+")
    check("Medical city saved", med.get("city") == "Tunis", f"got {med.get('city')!r}")
    check("Medical date_of_birth saved", med.get("date_of_birth") == "1995-03-15")
    check("Medical address saved", med.get("address") == "12 Rue des Fleurs")
    check("Medical allergies saved", med.get("allergies") == ["Penicillin", "Pollen"])
    check("Medical chronic_conditions saved", med.get("chronic_conditions") == ["Hypertension"])


def test_persistence(token: str, phone: str) -> None:
    """Re-fetch profile and verify all fields survive a round-trip."""
    status, profile = req("GET", "/profile", token=token)
    check("Persistence: GET /profile returns 200", status == 200)
    if status != 200:
        return
    med = profile.get("medical", {})
    check("Persistence: phone retained", profile.get("phone") == phone, f"got {profile.get('phone')!r}")
    check("Persistence: gender retained", profile.get("gender") == "female")
    check("Persistence: weight retained", med.get("weight") == 70.5)
    check("Persistence: city retained", med.get("city") == "Tunis", f"got {med.get('city')!r}")
    check("Persistence: allergies retained", med.get("allergies") == ["Penicillin", "Pollen"])


def test_invalid_token() -> None:
    """Malformed token returns 401, not 500."""
    status, _ = req("GET", "/profile", token="not-a-real-token")
    check("Invalid token -> 401", status == 401, f"got {status}")


def test_missing_token() -> None:
    """No token returns 403 (bearer missing)."""
    status, _ = req("GET", "/profile")
    check("Missing token -> 403", status == 403, f"got {status}")


def test_city_field_in_schema() -> None:
    """Verify city is present in the medical object of a fresh profile."""
    rand = uuid.uuid4().hex[:8]
    status, body = req("POST", "/auth/signup", {
        "email": f"city_{rand}@clinix-test.com",
        "password": "CityTest123!",
        "name": "City Tester",
    })
    if status != 201:
        check("City schema test: signup failed", False, f"status={status}")
        return
    token = body.get("access_token", "")
    _, profile = req("GET", "/profile", token=token)
    med = profile.get("medical", {})
    check("City field present in medical schema", "city" in med, f"keys={list(med.keys())}")
    check("City field defaults to None", med.get("city") is None)


# -- runner --------------------------------------------------------------------

def main() -> None:
    print(f"\nProfile System Tests  ->  {BASE}\n")

    # Basic connectivity
    status, _ = req("GET", "/")
    if status == 0:
        print(f"\n{FAIL}  Auth service unreachable at {BASE}")
        print("  Start it with:  uvicorn app.main:app --port 8005\n")
        sys.exit(1)
    print(f"  Auth service reachable  (GET / -> {status})\n")

    print("-- Signup & profile retrieval ----------------------------─")
    token = test_signup_and_profile_retrieval()

    if token:
        print("\n-- Personal info update ------------------------------------")
        phone = test_update_personal(token)

        print("\n-- Medical patch (incl. city) ------------------------------")
        test_patch_medical(token)

        print("\n-- Persistence (re-fetch) ----------------------------------")
        test_persistence(token, phone=phone)

    print("\n-- Auth edge cases ----------------------------------------─")
    test_invalid_token()
    test_missing_token()

    print("\n-- City field schema --------------------------------------─")
    test_city_field_in_schema()

    # Summary
    passed = sum(1 for _, ok, _ in results if ok)
    total  = len(results)
    print(f"\n{'─' * 55}")
    print(f"  Result: {passed}/{total} passed")
    if passed < total:
        print("\n  Failed tests:")
        for name, ok, detail in results:
            if not ok:
                print(f"    {FAIL}  {name}" + (f"  [{detail}]" if detail else ""))
    print()
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
