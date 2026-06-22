from typing import Literal

from pydantic import BaseModel


class MedicalProfile(BaseModel):
    # Vitals
    weight: float | None = None
    height: float | None = None
    blood_type: Literal["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"] | None = None
    # Personal
    date_of_birth: str | None = None           # YYYY-MM-DD
    address: str | None = None
    city: str | None = None
    # Lifestyle
    smoking_status: Literal["never", "former", "current"] | None = None
    alcohol_consumption: Literal["never", "occasional", "moderate", "heavy"] | None = None
    # Medical history
    allergies: list[str] = []
    chronic_conditions: list[str] = []
    current_medications: list[str] = []
    past_surgeries: list[str] = []
    family_history: list[str] = []
    # Emergency contact
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    emergency_contact_relationship: str | None = None


class PatientProfileOut(BaseModel):
    patient_id: str
    name: str
    email: str | None = None
    phone: str | None = None
    gender: str | None = None
    preferences: dict | None = None
    medical: MedicalProfile = MedicalProfile()
    # AI behavioural signals — populated from patient_profiles document
    recurring_symptoms: list[str] = []
    preferred_specialties: list[str] = []
    preferred_doctors: list[dict] = []
    updated_at: str | None = None


class ProfileUpdateRequest(BaseModel):
    name: str | None = None
    phone: str | None = None
    gender: str | None = None
    preferences: dict | None = None
    medical: MedicalProfile | None = None


class MedicalPatchRequest(BaseModel):
    weight: float | None = None
    height: float | None = None
    blood_type: Literal["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"] | None = None
    date_of_birth: str | None = None
    address: str | None = None
    city: str | None = None
    smoking_status: Literal["never", "former", "current"] | None = None
    alcohol_consumption: Literal["never", "occasional", "moderate", "heavy"] | None = None
    allergies: list[str] | None = None
    chronic_conditions: list[str] | None = None
    current_medications: list[str] | None = None
    past_surgeries: list[str] | None = None
    family_history: list[str] | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    emergency_contact_relationship: str | None = None
