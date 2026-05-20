from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    APP_NAME: str = "ClinixAI Agent Service"

    GROQ_API_KEY: str = ""

    MODEL_NAME: str = "llama-3.3-70b-versatile"

    APPOINTMENT_SERVICE_URL: str = (
        "http://localhost:8003"
    )

    AVAILABILITY_SERVICE_URL: str = (
        "http://localhost:8002"
    )

    GEO_SERVICE_URL: str = (
        "http://localhost:5000"
    )

    class Config:

        env_file = ".env"


settings = Settings()
