# ClinixAI — Authentication & Authorization System

## 1. Service Overview

The authentication service (`auth_service/`) provides user identity management for ClinixAI. It is a focused FastAPI microservice responsible for:

- User registration (patients only — doctors are seeded by administrators)
- Login authentication with JWT token issuance
- JWT token validation for protected API routes
- Role-based identity (patient vs doctor) encoded in tokens

- **Port**: 8005
- **Framework**: FastAPI
- **Password hashing**: `bcrypt` (via `passlib`)
- **JWT library**: `python-jose` (JOSE standard, HS256 algorithm)
- **Storage**: MongoDB (`clinixai_db.users` collection)
- **CORS**: Restricted to `http://localhost:3000`

---

## 2. Security Implementation

### Password Hashing: `app/core/security.py`

```python
import bcrypt
from jose import jwt

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))

def create_access_token(data: dict) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {**data, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
```

**bcrypt** was chosen for password hashing because:
- Adaptive: the work factor can be increased as hardware improves
- Built-in salt: each hash is unique even for identical passwords
- Industry standard for authentication systems

**HS256** (HMAC-SHA256) for JWT signing provides:
- Symmetric signing (fast verification)
- Sufficient security for a single-server deployment
- Standard `exp` claim for automatic expiry

### JWT Payload

The access token payload carries:
```json
{
    "sub": "john.doe@example.com",
    "role": "patient",
    "patient_profile_id": "patient-john-doe",
    "doctor_id": null,
    "name": "John Doe",
    "exp": 1748476800
}
```

For doctors (seeded by admin):
```json
{
    "sub": "dr.ben.salah@clinixai.tn",
    "role": "doctor",
    "patient_profile_id": null,
    "doctor_id": "doc-ben-salah-123",
    "name": "Dr. Ben Salah",
    "exp": 1748476800
}
```

The `patient_profile_id` and `doctor_id` are critical — they link the JWT identity to the correct data records in MongoDB and Redis. The agent service extracts `patient_profile_id` from the request to know which patient's memories to load.

---

## 3. Authentication Service: `app/services/auth_service.py`

### Patient Signup

```python
async def signup_patient(self, email: str, password: str, name: str) -> dict | None:
    # 1. Check email uniqueness
    existing = await self.users.find_by_email(email)
    if existing:
        return None

    # 2. Generate patient_profile_id from email slug
    slug = re.sub(r"[^a-z0-9]", "-", email.lower().split("@")[0])
    patient_profile_id = f"patient-{slug}"
    # e.g., "john.doe@example.com" → "patient-john-doe"

    # 3. Create minimal patient_profiles document in MongoDB (for AI agent)
    await db["patient_profiles"].update_one(
        {"patient_id": patient_profile_id},
        {"$setOnInsert": {"patient_id": patient_profile_id, "name": name, ...}},
        upsert=True,
    )

    # 4. Create user document with bcrypt-hashed password
    user_doc = {
        "email": email.lower(),
        "password_hash": hash_password(password),
        "role": "patient",
        "name": name,
        "patient_profile_id": patient_profile_id,
        "doctor_id": None,
        "created_at": now,
        "is_active": True,
    }
    await self.users.create(user_doc)

    # 5. Issue JWT token
    token = create_access_token({
        "sub": email, "role": "patient",
        "patient_profile_id": patient_profile_id,
        "name": name,
    })
    return {"access_token": token, "role": "patient", ...}
```

**Design note**: The `$setOnInsert` operation on `patient_profiles` uses an upsert — it creates the document only if it doesn't exist, avoiding race conditions from concurrent signups with the same email.

### Login (Patients + Doctors)

```python
async def login(self, email: str, password: str) -> dict | None:
    user = await self.users.find_by_email(email)
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    if not user.get("is_active", True):
        return None

    token = create_access_token({
        "sub": user["email"],
        "role": user["role"],
        "patient_profile_id": user.get("patient_profile_id"),
        "doctor_id": user.get("doctor_id"),
        "name": user.get("name", ""),
    })
    return {"access_token": token, "role": user["role"], ...}
```

---

## 4. API Schema

### Pydantic Models: `app/schemas/auth.py`

```python
class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: Literal["patient"] = "patient"  # patients can only self-register

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token:       str
    token_type:         str = "bearer"
    role:               str           # "patient" | "doctor"
    name:               str
    patient_profile_id: str | None
    doctor_id:          str | None

class UserOut(BaseModel):
    email:              str
    role:               str
    name:               str
    patient_profile_id: str | None
    doctor_id:          str | None
    is_active:          bool
```

**Key design**: The `SignupRequest` hardcodes `role: Literal["patient"]`. Doctors are only created via the admin seed script (`scripts/seed_doctors.py`), not through the public API. This prevents unauthorized doctor account creation.

---

## 5. MongoDB User Collection

**Collection**: `users` in `clinixai_db`

```json
{
    "_id": ObjectId("..."),
    "email": "john.doe@example.com",
    "password_hash": "$2b$12$...",           // bcrypt hash
    "role": "patient",                        // or "doctor"
    "name": "John Doe",
    "patient_profile_id": "patient-john-doe", // null for doctors
    "doctor_id": null,                         // set for doctors
    "created_at": "2026-01-15T10:00:00Z",
    "is_active": true
}
```

**Index**: Unique index on `email` for fast O(1) lookup and uniqueness enforcement.

---

## 6. Frontend Auth Integration

### Token Storage

The frontend stores the JWT in localStorage (or a Zustand-persisted state):
```typescript
// On login success:
localStorage.setItem("access_token", response.access_token);
localStorage.setItem("role", response.role);
localStorage.setItem("patient_profile_id", response.patient_profile_id);
localStorage.setItem("doctor_id", response.doctor_id);
```

### Protected Route Middleware

Next.js middleware checks for a valid JWT on all protected routes:
- `/patient/**` — requires `role="patient"` token
- `/doctor/**` — requires `role="doctor"` token
- Unauthenticated requests are redirected to `/` (login page)

### API Request Authorization

All agent service requests include the JWT in the Authorization header:
```typescript
fetch("/api/agent", {
    method: "POST",
    headers: {
        "Authorization": `Bearer ${localStorage.getItem("access_token")}`,
        "Content-Type": "application/json",
    },
    body: JSON.stringify({ message, session_id, role, patient_id }),
})
```

The agent service extracts `patient_id` from the request body (sent by the frontend from the decoded JWT payload), not from a token validation step — keeping the agent service decoupled from the auth service.

---

## 7. Doctor Seeding: `scripts/seed_doctors.py`

Doctors are pre-populated by administrators running the seed script:

```python
# Creates user documents for doctors with:
# - role: "doctor"
# - doctor_id: linked to the MongoDB doctors collection in medical_data_tunisia
# - password_hash: bcrypt of a default password (must be changed on first login)
```

This administrative approach ensures doctors are only added through controlled processes, not public registration.

---

## 8. Settings

```python
class Settings(BaseSettings):
    JWT_SECRET: str           # Must be a strong random secret in production
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 10080  # 7 days default
    MONGODB_URI: str
    MONGODB_DB: str = "clinixai_db"
    
    class Config:
        env_file = ".env"
        extra = "ignore"
```

The 7-day token expiry is a balance between security (shorter = more secure) and UX (longer = fewer re-logins). In a production healthcare system, this would typically be reduced with refresh token rotation.
