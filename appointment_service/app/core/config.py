from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict
)


class Settings(BaseSettings):

    MONGODB_URI: str
    DATABASE_NAME: str = "appointment_reservation"
    PORT: int = 8003
    AVAILABILITY_SERVICE_URL: str = "http://localhost:8002"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()
