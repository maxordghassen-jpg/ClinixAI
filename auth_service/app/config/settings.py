from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "ClinixAI Auth Service"

    MONGODB_URI: str = ""
    MONGO_DB_NAME: str = "clinix_agent"

    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440  # 24 hours

    class Config:
        env_file = ".env"


settings = Settings()
