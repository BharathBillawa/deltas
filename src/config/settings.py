"""Application configuration using Pydantic Settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # LLM Configuration
    google_api_key: str = Field(..., description="Google Gemini API key")

    # Database
    database_url: str = Field(
        default="sqlite:///./deltas.db", description="Database connection URL"
    )

    # API Configuration
    api_host: str = Field(default="0.0.0.0", description="API server host")
    api_port: int = Field(default=8000, description="API server port")

    # Business Rules
    auto_approve_threshold: float = Field(
        default=500.0, description="Auto-approve threshold in EUR"
    )
    currency: str = Field(default="EUR", description="Default currency")

    # Environment
    environment: str = Field(default="development", description="Environment name")
    log_level: str = Field(default="INFO", description="Logging level")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


# Global settings instance
settings = Settings()
