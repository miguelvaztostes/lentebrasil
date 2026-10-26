from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Lente Brasil API"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://lente:lente-local@localhost:5432/lente"
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://localhost",
    ]
    raw_data_dir: Path = Path("data/raw")
    export_ttl_hours: int = 24
    export_active_quota: int = 3
    export_hourly_quota: int = 10
    submission_captcha_secret: str = "development-only-change-me"
    submission_fingerprint_secret: str = "development-only-change-me"
    contact_encryption_key: str | None = None
    submission_hourly_quota: int = 5
    quarantine_max_bytes: int = 10 * 1024 * 1024
    quarantine_dir: Path = Path("data/quarantine")
    oidc_introspection_url: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: str | None = None
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_mfa_required: bool = True
    ckan_discovery_urls: Annotated[list[str], NoDecode] = []
    discovery_allowed_hosts: Annotated[list[str], NoDecode] = []
    discovery_interval_seconds: int = 86_400
    discovery_stale_days: int = 14
    clamav_host: str | None = None
    clamav_port: int = 3310

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @field_validator("ckan_discovery_urls", "discovery_allowed_hosts", mode="before")
    @classmethod
    def parse_csv_lists(cls, value: object) -> object:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @model_validator(mode="after")
    def production_secrets_are_explicit(self) -> Settings:
        if self.environment.lower() == "production":
            defaults = {"", "development-only-change-me"}
            if (
                self.submission_captcha_secret in defaults
                or self.submission_fingerprint_secret in defaults
            ):
                raise ValueError("Segredos de submissão devem ser configurados em produção")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
