import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.agent_routes import router as agent_router
from app.db.mongo_client import close_mongo_connection, connect_to_mongo
from app.repositories.chat_history_repo import ChatHistoryRepository
from app.repositories.memory_repo import MemoryRepository
from app.repositories.patient_profile_repo import PatientProfileRepository
from app.repositories.preconsultation_repo import PreconsultationRepository
from app.repositories.preconsultation_report_repo import PreconsultationReportRepository

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── startup ──────────────────────────────────────────────────────────────
    await connect_to_mongo()
    await PatientProfileRepository().create_indexes()
    await MemoryRepository().create_indexes()
    await PreconsultationRepository().create_indexes()
    await PreconsultationReportRepository().create_indexes()
    await ChatHistoryRepository().create_indexes()

    # Warm up embedding model — logs success or degraded-mode warning
    try:
        from app.embeddings.sentence_transformer_provider import check_available
        ok, detail = check_available()
        if ok:
            logger.info(f"[EMBED] Startup check passed: {detail}")
        else:
            logger.warning(f"[EMBED] Startup check FAILED — semantic features degraded: {detail}")
    except Exception as exc:
        logger.warning(f"[EMBED] Startup check raised unexpectedly: {exc}")

    yield
    # ── shutdown ─────────────────────────────────────────────────────────────
    await close_mongo_connection()


app = FastAPI(title="Agent Service", lifespan=lifespan)

app.include_router(agent_router)


@app.get("/")
async def root():
    return {"message": "Agent Service Running"}


@app.get("/health/embeddings")
async def health_embeddings():
    """
    Probe whether the sentence-transformer model is loaded and functional.
    Returns 200 in both states; callers should check the 'available' field.
    """
    from app.embeddings.sentence_transformer_provider import check_available, DIMENSIONS
    available, detail = check_available()
    return {
        "available":  available,
        "model":      "paraphrase-multilingual-MiniLM-L12-v2",
        "dimensions": DIMENSIONS if available else 0,
        "detail":     detail,
    }
