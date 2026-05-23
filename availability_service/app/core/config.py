from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class Settings(BaseSettings):

    MONGODB_URI: str

    DATABASE_NAME: str

    APPOINTMENT_SERVICE_URL: str

    LOG_DIR: str = "logs"

    LOG_FILE: str = "availability.log"

    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()