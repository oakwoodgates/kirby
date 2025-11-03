"""
Application settings using Pydantic.
"""
from typing import Literal

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
        default="postgresql+asyncpg://kirby:kirby_password@localhost:5432/kirby",
        description="Database connection URL",
    )
    database_pool_size: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Database connection pool size",
    )
    database_max_overflow: int = Field(
        default=10,
        ge=0,
        le=50,
        description="Maximum overflow connections",
    )

    # TimescaleDB specific
    timescale_chunk_time_interval: str = Field(
        default="1 day",
        description="Chunk time interval for hypertables",
    )

    # Training Database Configuration (for ML/Backtesting with Binance, Bybit, etc.)
    training_db: str = Field(
        default="kirby_training",
        description="Training database name",
    )
    training_database_url: PostgresDsn | None = Field(
        default=None,
        description="Training database connection URL for ML/backtesting data",
    )
    training_database_pool_size: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Training database connection pool size",
    )

    # API Configuration
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, ge=1, le=65535, description="API port")
    api_workers: int = Field(default=4, ge=1, le=16, description="Number of API workers")
    api_reload: bool = Field(default=False, description="Enable auto-reload for development")
    api_log_level: Literal["debug", "info", "warning", "error", "critical"] = Field(
        default="info", description="API log level"
    )

    # CORS Configuration
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
        description="Allowed CORS origins",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Parse CORS origins from comma-separated string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    # Application Settings
    environment: Literal["development", "staging", "production"] = Field(
        default="development", description="Environment"
    )
    log_level: Literal["debug", "info", "warning", "error", "critical"] = Field(
        default="info", description="Application log level"
    )
    log_format: Literal["json", "text"] = Field(
        default="json", description="Log format (json or text)"
    )

    # Exchange API Keys (optional, for private endpoints)
    hyperliquid_api_key: str | None = Field(default=None, description="Hyperliquid API key")
    hyperliquid_api_secret: str | None = Field(
        default=None, description="Hyperliquid API secret"
    )

    # Collector Settings
    collector_restart_delay: int = Field(
        default=5,
        ge=1,
        le=300,
        description="Delay before restarting collector (seconds)",
    )
    collector_max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum collector restart retries",
    )
    collector_backfill_on_gap: bool = Field(
        default=True,
        description="Automatically backfill gaps after collector restart",
    )

    # Rate Limiting
    hyperliquid_rate_limit_per_second: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Hyperliquid rate limit per second",
    )

    # Monitoring & Health
    health_check_interval: int = Field(
        default=60,
        ge=10,
        le=3600,
        description="Health check interval (seconds)",
    )
    data_freshness_threshold: int = Field(
        default=300,
        ge=60,
        le=3600,
        description="Data freshness threshold for health checks (seconds)",
    )

    # Cache Settings (for future use)
    cache_enabled: bool = Field(default=False, description="Enable caching")
    cache_ttl: int = Field(
        default=300,
        ge=10,
        le=3600,
        description="Cache TTL (seconds)",
    )

    @property
    def database_url_str(self) -> str:
        """Get database URL as string."""
        return str(self.database_url)

    @property
    def asyncpg_url_str(self) -> str:
        """Get database URL for asyncpg (without the +asyncpg driver suffix)."""
        url_str = str(self.database_url)
        # asyncpg expects postgresql:// not postgresql+asyncpg://
        return url_str.replace("postgresql+asyncpg://", "postgresql://")

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"


# Global settings instance
settings = Settings()
