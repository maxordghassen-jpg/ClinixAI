from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    APP_NAME: str = "ClinixAI Evaluation Service"

    # LLM judge
    GROQ_API_KEY: str = ""
    JUDGE_MODEL:  str = "llama-3.3-70b-versatile"

    # Agent service URL — used by scenario runner
    AGENT_SERVICE_URL: str = "http://localhost:8004"

    # JWT (read-only — eval service never issues tokens)
    JWT_SECRET:    str = ""
    JWT_ALGORITHM: str = "HS256"

    # BERTScore
    ENABLE_BERT_SCORE: bool = True
    BERT_SCORE_MODEL:  str  = "bert-base-multilingual-cased"

    # MongoDB — evaluation result persistence
    MONGODB_URI:  str = "mongodb://localhost:27017"
    MONGODB_DB:   str = "clinix_eval"
    ENABLE_MONGO: bool = True   # set False to skip persistence (stateless mode)

    class Config:
        env_file = ".env"
        extra   = "ignore"   # tolerate unrecognised env vars without crashing


settings = Settings()
