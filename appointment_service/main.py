from fastapi import FastAPI

from app.database.connection import (
    connect_to_mongo,
    close_mongo_connection
)
from app.api.routes.appointment_routes import (
    router as appointment_router
)
from app.repositories.appointment_repository import AppointmentRepository

app = FastAPI(
    title="Appointment Service"
)


@app.on_event("startup")
async def startup():

    await connect_to_mongo()
    await AppointmentRepository().create_indexes()


@app.on_event("shutdown")
async def shutdown():

    await close_mongo_connection()

app.include_router(
    appointment_router
)
@app.get("/")
async def root():

    return {
        "message":
        "Appointment Service Running"
    }
