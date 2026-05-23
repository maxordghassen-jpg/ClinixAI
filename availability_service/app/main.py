from fastapi import FastAPI

from app.database.connection import (
    connect_to_mongo,
    close_mongo_connection
)
from app.repositories.availability_repository import AvailabilityRepository
from app.repositories.exception_repository import ExceptionRepository

from app.api.routes.availability_routes import router as availability_router
from app.api.routes.exception_routes import router as exception_router

app = FastAPI()


@app.on_event("startup")
async def startup_db():
    await connect_to_mongo()
    await AvailabilityRepository().create_indexes()
    await ExceptionRepository().create_indexes()


@app.on_event("shutdown")
async def shutdown_db():
    await close_mongo_connection()


app.include_router(availability_router)
app.include_router(exception_router)

@app.get("/")
async def root():

    return {
        "message": "Availability Service Running"
    }
