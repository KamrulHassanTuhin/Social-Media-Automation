from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    app_secret: str = "local-only-change-me"
    app_base_url: str = "http://localhost:3000"
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    supabase_jwt_secret: str | None = None
    allowed_origins: str = "http://localhost:3000"
    media_root: str = "var/media"
    max_upload_bytes: int = 10_000_000
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"
    nuelink_api_key: str | None = None
    nuelink_base_url: str = "https://api.nuelink.com"
    nuelink_destination_id: str | None = None
    slack_webhook_url: str | None = None
    email_api_key: str | None = None
    email_base_url: str = "https://api.resend.com"
    email_from: str = "AXIS OS <notifications@axisconsulting.com>"
    email_webhook_secret: str | None = None
    audit_retention_days: int = 365
    encryption_key: str | None = None
    provider_rate_limit_per_minute: int = 60

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
