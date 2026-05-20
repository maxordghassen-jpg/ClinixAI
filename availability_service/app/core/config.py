from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    MONGODB_URI: str

    DATABASE_NAME: str = "disponibility"

    PORT: int = 8002

    LOG_DIR: str = "logs"

    LOG_FILE: str = "availability_service.log"

    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"


settings = Settings()
