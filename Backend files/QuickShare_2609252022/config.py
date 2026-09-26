"""
Central configuration, loaded from environment variables / .env file.
Never hard-code secrets -- everything sensitive comes from here.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Security
    SECRET_KEY: str = "dev-secret-change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    ALGORITHM: str = "HS256"

    # Database
    DATABASE_URL: str = "sqlite:///./findback.db"

    # Storage
    STORAGE_BACKEND: str = "local"
    UPLOAD_DIR: str = "uploads"

    # AI
    TEXT_SIMILARITY_MODEL: str = "all-MiniLM-L6-v2"
    VISION_API_PROVIDER: str = "none"
    VISION_API_KEY: str = ""

    # Matching weights -- defaults mirror the product spec.
    # These are BASE weights; the engine re-normalizes them at match time
    # based on which factors actually have data on both sides.
    WEIGHT_TEXT: float = 0.30
    WEIGHT_CATEGORY: float = 0.15
    WEIGHT_BRAND: float = 0.15
    WEIGHT_COLOR: float = 0.10
    WEIGHT_FEATURES: float = 0.15
    WEIGHT_LOCATION: float = 0.10
    WEIGHT_DATE: float = 0.05

    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5500,http://localhost:5500,http://127.0.0.1:3000,http://127.0.0.1:5173,http://127.0.0.1:8080,http://localhost:8080"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
