from fastapi import FastAPI

from app.api.routes.agent_routes import (
    router as agent_router
)

app = FastAPI(
    title="Agent Service"
)

app.include_router(
    agent_router
)


@app.get("/")
async def root():

    return {
        "message":
        "Agent Service Running"
    }