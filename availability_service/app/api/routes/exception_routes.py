from fastapi import APIRouter

from app.schemas.exception_schema import ExceptionCreate, ExceptionResponse
from app.services.exception_service import ExceptionService


router = APIRouter(prefix="/exceptions", tags=["exceptions"])


@router.post("", response_model=ExceptionResponse)
async def create_exception(payload: ExceptionCreate):
    return await ExceptionService().create_exception(payload)


@router.get("/{doctor_id}", response_model=list[ExceptionResponse])
async def list_doctor_exceptions(doctor_id: str):
    return await ExceptionService().list_doctor_exceptions(doctor_id)


@router.delete("/{exception_id}")
async def delete_exception(exception_id: str):
    return await ExceptionService().delete_exception(exception_id)
