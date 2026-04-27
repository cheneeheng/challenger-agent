from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://idealens:idealens@localhost:5432/idealens"

    # Auth
    JWT_SECRET: str = "change-me-generate-with-secrets-token-hex-64"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Encryption (Fernet key)
    API_KEY_ENCRYPTION_KEY: str = ""

    # App — list fields stored as raw strings, parsed via properties
    # to avoid pydantic-settings v2 JSON-decode attempt on list[str] fields
    FRONTEND_URLS_RAW: str = "http://localhost:5173"
    ENVIRONMENT: str = "development"

    # LLM
    ALLOWED_CLAUDE_MODELS_RAW: str = (
        "claude-haiku-4-5,claude-sonnet-4-6,claude-opus-4-6"
    )
    DEFAULT_MODEL: str = "claude-sonnet-4-6"
    CONTEXT_WINDOW_MAX_MESSAGES: int = 20

    # Test DB (only for pytest)
    TEST_DATABASE_URL: str = ""

    # Seed (optional)
    SEED_ANTHROPIC_API_KEY: str = ""

    model_config = SettingsConfigDict(
        # Root .env is canonical; fall back to .env in cwd for any tool
        # that runs directly from backend/ during local dev.
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    @property
    def FRONTEND_URLS(self) -> list[str]:
        return [u.strip() for u in self.FRONTEND_URLS_RAW.split(",") if u.strip()]

    @property
    def ALLOWED_CLAUDE_MODELS(self) -> list[str]:
        return [
            m.strip()
            for m in self.ALLOWED_CLAUDE_MODELS_RAW.split(",")
            if m.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
