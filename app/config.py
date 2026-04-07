"""OctaneLogic – application configuration (Pydantic Settings)."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application
    app_name: str = "OctaneLogic"
    app_version: str = "0.1.0"
    debug: bool = False

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://octane:octane@localhost:5432/octanelogic",
        alias="DATABASE_URL",
    )
    db_encryption_key: str = Field(
        default="changeme-32-byte-encryption-key!",
        alias="DB_ENCRYPTION_KEY",
        description="Key used for pgcrypto field-level encryption of coordinates",
    )

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # External APIs
    fuelcheck_api_key: str = Field(default="", alias="FUELCHECK_API_KEY")
    ocm_api_key: str = Field(default="", alias="OCM_API_KEY")

    # AEMO / NEM
    nem_region: str = Field(default="NSW1", alias="NEM_REGION")

    # Privacy
    time_value_per_hour_aud: float = Field(
        default=25.0,
        description="User's perceived cost of time (AUD/hour) for Detour Delta calculations",
    )

    # Physics defaults (can be overridden per vehicle)
    default_air_temp_c: float = 20.0


settings = Settings()
