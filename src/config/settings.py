"""
Application configuration using Pydantic Settings.
Loads configuration from environment variables and .env file.
"""

from functools import lru_cache
from typing import List

from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database Configuration
    database_url: PostgresDsn = Field(
        default="postgresql+asyncpg://kirby_user:password@localhost:5432/kirby",
        description="SQLAlchemy async database URL",
    )
    asyncpg_url: str = Field(
        default="postgresql://kirby_user:password@localhost:5432/kirby",
        description="asyncpg database URL for high-performance writes",
    )

    # Database Pool Configuration
    db_pool_min_size: int = Field(default=10, description="Minimum connection pool size")
    db_pool_max_size: int = Field(default=20, description="Maximum connection pool size")
    db_pool_timeout: int = Field(default=30, description="Connection pool timeout in seconds")

    # API Configuration
    api_host: str = Field(default="0.0.0.0", description="API server host")
    api_port: int = Field(default=8000, description="API server port")
    api_workers: int = Field(default=4, description="Number of Gunicorn workers")
    api_reload: bool = Field(default=False, description="Enable auto-reload (development only)")

    # CORS Configuration
    cors_origins: List[str] = Field(
        default=["http://localhost:3000"],
        description="Allowed CORS origins",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            # Handle JSON string format
            import json
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                # Handle comma-separated string
                return [origin.strip() for origin in v.split(",")]
        return v

    # Rate Limiting
    rate_limit_per_minute: int = Field(
        default=100,
        description="API rate limit per IP per minute",
    )

    # Logging Configuration
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format (json or text)")

    # Collector Configuration
    collector_heartbeat_interval: int = Field(
        default=30,
        description="Collector heartbeat interval in seconds",
    )
    collector_reconnect_delay: int = Field(
        default=5,
        description="Initial reconnect delay in seconds (exponential backoff)",
    )
    collector_max_reconnect_attempts: int = Field(
        default=10,
        description="Maximum reconnection attempts (0 = infinite)",
    )

    # Backfill Configuration
    backfill_batch_size: int = Field(
        default=1000,
        description="Number of candles to fetch per request during backfill",
    )
    backfill_rate_limit_delay: int = Field(
        default=1000,
        description="Delay between backfill requests in milliseconds",
    )

    # Application Environment
    environment: str = Field(
        default="development",
        description="Application environment (development, staging, production)",
    )

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment.lower() == "development"


@lru_cache
def get_settings() -> Settings:
    """
    Get cached application settings.
    This function is cached to avoid re-reading environment variables on every call.
    """
    return Settings()
