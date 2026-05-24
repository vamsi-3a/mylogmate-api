"""Application settings loaded from environment variables via pydantic-settings."""

from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration — all values from environment / .env file."""

    # ── App ──────────────────────────────────────────────────────────────
    APP_ENV: str = "development"
    DEBUG: bool = False

    # ── Database ─────────────────────────────────────────────────────────
    DATABASE_URL: str  # postgresql+asyncpg://user:pass@host:port/db

    # ── Redis ─────────────────────────────────────────────────────────────
    REDIS_URL: str  # redis://host:port/db

    # ── Qdrant (Cloud Inference — no local embedding model) ───────────────
    QDRANT_URL: str  # https://xxx.qdrant.io or http://localhost:6333
    QDRANT_API_KEY: str = ""
    QDRANT_COLLECTION: str = "log_entries"

    # ── JWT ───────────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── Encryption (AES-256 via Fernet) ──────────────────────────────────
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    ENCRYPTION_KEY: str

    # ── LLM (Groq API) ────────────────────────────────────────────────────
    GROQ_API_KEY: str = ""
    LLM_PROVIDER: str = "groq"  # groq | ollama

    # ── Google OAuth 2.0 ──────────────────────────────────────────────────
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # ── Gmail SMTP ────────────────────────────────────────────────────────
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""

    # ── CORS ──────────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # ── Admin seed ────────────────────────────────────────────────────────
    ADMIN_EMAIL: str = ""
    ADMIN_PASSWORD: str = ""

    # ── Rate limiting ─────────────────────────────────────────────────────
    AI_QUERY_DAILY_LIMIT: int = 50
    AUTH_RATE_LIMIT: str = "5/minute"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        """Accept either a JSON array or a comma-separated string."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return list(v)  # pydantic-settings may pass a pre-parsed list

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Ensure asyncpg driver is specified."""
        if v.startswith("postgresql://") or v.startswith("postgres://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1).replace(
                "postgres://", "postgresql+asyncpg://", 1
            )
        return v

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_test(self) -> bool:
        return self.APP_ENV == "test"


# Singleton — import this everywhere instead of instantiating Settings()
settings = Settings()
