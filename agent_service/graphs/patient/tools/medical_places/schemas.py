from typing import Any, Literal

from pydantic import BaseModel


MedicalPlacesAction = Literal[
    "search_nearby_hospitals",
    "search_nearby_pharmacies",
    "search_nearby_clinics",
    "search_doctors_by_specialty",
    "search_by_city",
]


class MedicalPlacesToolInput(BaseModel):
    action: MedicalPlacesAction
    category: str | None = None
    specialty: str | None = None
    city: str | None = None
    governorate: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    radius: float | None = None
    limit: int | None = None
    entities: dict[str, Any] = {}
