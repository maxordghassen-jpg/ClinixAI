from fastapi import APIRouter
from datetime import datetime
from app.schemas.availability_schema import (
    AvailabilityCreate,
    AvailabilityResponse,
    AvailabilityUpdate,
    Day,
    SlotSchema,
    SlotStatusUpdate,
)
from app.services.availability_service import AvailabilityService


router = APIRouter(prefix="/availability", tags=["availability"])


@router.post("", response_model=AvailabilityResponse)
async def create_availability(payload: AvailabilityCreate):
    return await AvailabilityService().create_availability(payload)


@router.put("/{availability_id}", response_model=AvailabilityResponse)
async def update_availability(availability_id: str, payload: AvailabilityUpdate):
    return await AvailabilityService().update_availability(availability_id, payload)


@router.post("/{availability_id}", response_model=AvailabilityResponse)
async def update_availability_with_post(availability_id: str, payload: AvailabilityUpdate):
    return await AvailabilityService().update_availability(availability_id, payload)


@router.delete("/{availability_id}")
async def delete_availability(availability_id: str):
    return await AvailabilityService().delete_availability(availability_id)


@router.post("/slots/block", response_model=AvailabilityResponse)
async def block_slot(payload: SlotStatusUpdate):
    return await AvailabilityService().block_slot(payload.doctor_id, payload.day, payload.start)


@router.post("/slots/unblock", response_model=AvailabilityResponse)
async def unblock_slot(payload: SlotStatusUpdate):
    return await AvailabilityService().unblock_slot(payload.doctor_id, payload.day, payload.start)


@router.post("/slots/book", response_model=AvailabilityResponse)
async def book_slot(payload: SlotStatusUpdate):
    return await AvailabilityService().book_slot(payload.doctor_id, payload.day, payload.start)


@router.post("/slots/release", response_model=AvailabilityResponse)
async def release_slot(payload: SlotStatusUpdate):
    return await AvailabilityService().release_slot(payload.doctor_id, payload.day, payload.start)


@router.get("/{doctor_id}", response_model=list[AvailabilityResponse])
async def view_doctor_availability(doctor_id: str):
    return await AvailabilityService().get_doctor_availability(doctor_id)


@router.get("/{doctor_id}/{day}", response_model=AvailabilityResponse)
async def view_day_availability(doctor_id: str, day: Day):
    return await AvailabilityService().get_day_availability(doctor_id, day)


from datetime import datetime

@router.get(
    "/{doctor_id}/{date}/free-slots",
    response_model=list[SlotSchema],
)
async def view_free_slots(
    doctor_id: str,
    date: str,
):

    parsed_date = datetime.strptime(
        date,
        "%Y-%m-%d",
    )

    english_day = (
        parsed_date
        .strftime("%A")
        .lower()
    )

    mapping = {
        "monday": "lundi",
        "tuesday": "mardi",
        "wednesday": "mercredi",
        "thursday": "jeudi",
        "friday": "vendredi",
        "saturday": "samedi",
        "sunday": "dimanche",
    }

    day = mapping[
        english_day
    ]

    return await (
        AvailabilityService()
        .get_free_slots(
            doctor_id,
            day,
            date,
        )
    )