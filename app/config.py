"""
Application configuration.

All secrets/config come from environment variables (loaded from .env in
local development). Nothing is hardcoded so the same code works in any
environment as long as .env (or real env vars) are present.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Required: your Groq API key. Never commit a real value to git.
    groq_api_key: str = ""

    # Model used for the matching call. Overridable via env for easy swaps.
    groq_model: str = "openai/gpt-oss-20b"

    # Generic app metadata / toggles
    app_env: str = "development"
    request_timeout_seconds: float = 30.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
