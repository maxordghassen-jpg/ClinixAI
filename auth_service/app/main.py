from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.auth_routes import router as auth_router
from app.api.routes.profile_routes import router as profile_router
from app.db.mongo_client import close_mongo_connection, connect_to_mongo
from app.repositories.profile_repository import ProfileRepository
from app.repositories.user_repository import UserRepository


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    await UserRepository().create_indexes()
    await ProfileRepository().create_indexes()
    yield
    await close_mongo_connection()


app = FastAPI(title="ClinixAI Auth Service", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(profile_router)


@app.get("/")
async def root():
    return {"message": "Auth Service Running"}
