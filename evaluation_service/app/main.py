import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api.routes.eval_routes import router as eval_router
from app.config.settings import settings

_DASHBOARD_PATH = os.path.join(os.path.dirname(__file__), "..", "dashboard.html")

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Validate scenario catalogue at startup ────────────────────────────
    try:
        from datasets.eval_scenarios import SCENARIOS
        from schemas.eval_schemas import EvalScenario
        ids_seen: set[str] = set()
        bad = 0
        for s in SCENARIOS:
            if s.id in ids_seen:
                logger.error("[Startup] Duplicate scenario ID: %s", s.id)
                bad += 1
            ids_seen.add(s.id)
            try:
                s.model_dump()
            except Exception as exc:
                logger.error("[Startup] Scenario %s fails serialization: %s", s.id, exc)
                bad += 1
        if bad:
            logger.warning("[Startup] %d scenario problem(s) detected — check logs above", bad)
        else:
            logger.info("[Startup] Scenario catalogue OK (%d scenarios)", len(SCENARIOS))
    except Exception as exc:
        logger.error("[Startup] Failed to validate scenario catalogue: %s", exc)

    # ── MongoDB ───────────────────────────────────────────────────────────
    if settings.ENABLE_MONGO:
        try:
            from app.db.mongo_client import connect
            await connect(settings.MONGODB_URI, settings.MONGODB_DB)
            logger.info("[Startup] MongoDB connected")
        except Exception as e:
            logger.warning("[Startup] MongoDB unavailable — running in stateless mode: %s", e)
    yield
    if settings.ENABLE_MONGO:
        try:
            from app.db.mongo_client import disconnect
            await disconnect()
        except Exception:
            pass


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)

app = FastAPI(
    title="ClinixAI Evaluation Service",
    description=(
        "LLM-as-a-Judge evaluation for ClinixAI. "
        "Covers workflow completion, safety, hallucination, answer quality, "
        "memory relevance, personalisation, and multilingual consistency."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(eval_router)


@app.get("/")
async def root():
    return {
        "service":   "ClinixAI Evaluation Service",
        "version":   "2.0.0",
        "docs":      "/docs",
        "dashboard": "/dashboard",
    }


@app.get("/dashboard", include_in_schema=False)
async def dashboard():
    return FileResponse(os.path.abspath(_DASHBOARD_PATH), media_type="text/html")
