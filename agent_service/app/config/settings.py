from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    APP_NAME: str = "ClinixAI Agent Service"

    # Redis — short-term workflow memory
    redis_host: str
    redis_port: int
    redis_username: str
    redis_password: str

    # MongoDB — long-term patient intelligence
    MONGODB_URI: str = ""
    MONGO_DB_NAME: str = "clinix_agent"

    GROQ_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    MODEL_NAME: str = "gpt-4o"

    JWT_SECRET: str = ""
    JWT_ALGORITHM: str = "HS256"

    APPOINTMENT_SERVICE_URL: str = "http://localhost:8003"
    AVAILABILITY_SERVICE_URL: str = "http://localhost:8002"
    GEO_SERVICE_URL: str = "http://localhost:5000"

    # ── Semantic memory / embeddings ──────────────────────────────────────────
    # Provider: "sentence_transformer" (default, local, multilingual EN/FR/AR)
    #           "openai" (requires OPENAI_API_KEY, 1536-dim)
    EMBEDDING_PROVIDER: str = "sentence_transformer"
    OPENAI_API_KEY: str = ""

    # Top-K semantically similar memories to surface per turn
    SEMANTIC_MEMORY_TOP_K: int = 8

    # Minimum cosine similarity to include a memory in semantic results
    SEMANTIC_SIMILARITY_THRESHOLD: float = 0.30

    class Config:
        env_file = ".env"


settings = Settings()
