from typing import Literal

from pydantic import BaseModel, EmailStr


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: Literal["patient"] = "patient"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    name: str
    patient_profile_id: str | None = None
    doctor_id: str | None = None


class UserOut(BaseModel):
    email: str
    role: str
    name: str
    patient_profile_id: str | None = None
    doctor_id: str | None = None
    is_active: bool
