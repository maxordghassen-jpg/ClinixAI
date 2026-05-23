from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.agent_routes import router as agent_router
from app.db.mongo_client import close_mongo_connection, connect_to_mongo
from app.repositories.patient_profile_repo import PatientProfileRepository


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── startup ──────────────────────────────────────────────────────────────
    await connect_to_mongo()
    await PatientProfileRepository().create_indexes()
    yield
    # ── shutdown ─────────────────────────────────────────────────────────────
    await close_mongo_connection()


app = FastAPI(title="Agent Service", lifespan=lifespan)

app.include_router(agent_router)


@app.get("/")
async def root():
    return {"message": "Agent Service Running"}
