import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from app.core.security import decode_token
from app.schemas.medical_profile import (
    MedicalPatchRequest,
    PatientProfileOut,
    ProfileUpdateRequest,
)
from app.services.profile_service import ProfileService

router = APIRouter(tags=["profile"])
logger = logging.getLogger(__name__)
_bearer = HTTPBearer()


def _svc() -> ProfileService:
    return ProfileService()


def _patient_payload(credentials: HTTPAuthorizationCredentials) -> dict:
    try:
        payload = decode_token(credentials.credentials)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if payload.get("role") != "patient":
        raise HTTPException(status_code=403, detail="Patients only")
    return payload


def _doctor_payload(credentials: HTTPAuthorizationCredentials) -> dict:
    try:
        payload = decode_token(credentials.credentials)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if payload.get("role") != "doctor":
        raise HTTPException(status_code=403, detail="Doctors only")
    return payload


async def _resolve_patient(payload: dict, svc: ProfileService) -> str:
    """Extract and resolve patient_id from JWT payload with email fallback."""
    jwt_id = payload.get("patient_profile_id")
    email = payload.get("sub", "")
    if not jwt_id and not email:
        raise HTTPException(
            status_code=400, detail="No patient profile linked to this account"
        )
    resolved = await svc.resolve_patient_id(jwt_id, email)
    if not resolved:
        raise HTTPException(
            status_code=400, detail="Could not resolve patient profile identity"
        )
    return resolved


# ── Patient endpoints ─────────────────────────────────────────────────────────

@router.get("/profile", response_model=PatientProfileOut)
async def get_profile(credentials: HTTPAuthorizationCredentials = Depends(_bearer)):
    payload = _patient_payload(credentials)
    svc = _svc()
    patient_id = await _resolve_patient(payload, svc)
    profile = await svc.get_profile(patient_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.put("/profile", response_model=PatientProfileOut)
async def update_profile(
    body: ProfileUpdateRequest,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
):
    payload = _patient_payload(credentials)
    jwt_pid = payload.get("patient_profile_id")
    email   = payload.get("sub", "")
    logger.warning(
        "[WRITE_TRACE] PUT /profile | jwt_patient_profile_id=%r | email=%r",
        jwt_pid, email,
    )
    svc = _svc()
    patient_id = await _resolve_patient(payload, svc)
    logger.warning(
        "[WRITE_TRACE] PUT /profile | resolved_patient_id=%r | body=%r",
        patient_id, body.model_dump(exclude_none=True),
    )
    result = await svc.update_profile(patient_id, body)
    if result is None:
        raise HTTPException(
            status_code=409,
            detail="Profile update failed — phone number may already be in use by another account.",
        )
    return result


@router.patch("/profile/medical", response_model=PatientProfileOut)
async def patch_medical(
    body: MedicalPatchRequest,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
):
    payload = _patient_payload(credentials)
    jwt_pid = payload.get("patient_profile_id")
    email   = payload.get("sub", "")
    logger.warning(
        "[WRITE_TRACE] PATCH /profile/medical | jwt_patient_profile_id=%r | email=%r",
        jwt_pid, email,
    )
    svc = _svc()
    patient_id = await _resolve_patient(payload, svc)
    logger.warning(
        "[WRITE_TRACE] PATCH /profile/medical | resolved_patient_id=%r | body=%r",
        patient_id, body.model_dump(exclude_none=True),
    )
    result = await svc.patch_medical(patient_id, body)
    if not result:
        raise HTTPException(status_code=500, detail="Medical profile update failed")
    return result


# ── Doctor endpoint ───────────────────────────────────────────────────────────

@router.get("/patients/{patient_id}/profile", response_model=PatientProfileOut)
async def get_patient_profile_for_doctor(
    patient_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
):
    payload = _doctor_payload(credentials)
    doctor_id = payload.get("doctor_id")
    if not doctor_id:
        raise HTTPException(status_code=400, detail="No doctor ID linked to this account")

    svc = _svc()
    authorized = await svc.doctor_can_view(doctor_id, patient_id)
    if not authorized:
        raise HTTPException(
            status_code=403,
            detail="Access denied: no confirmed appointment with this patient",
        )

    profile = await svc.get_profile_for_doctor_view(patient_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Patient profile not found")
    return profile
