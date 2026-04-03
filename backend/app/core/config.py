from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "development"
    secret_key: str = "changeme"
    cors_origins: list[str] = ["http://localhost:5173"]

    model_config = {"env_file": ".env"}

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: object) -> list[str]:
        # Accepts either a JSON array or a comma-separated string.
        # CORS_ORIGINS=http://localhost:5173,https://example.com
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


settings = Settings()
