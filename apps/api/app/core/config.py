from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "FDrive API"
    environment: str = "local"
    debug: bool = True
    api_prefix: str = "/api/v1"

    # CORS — comma-separated origins
    cors_origins: str = "http://localhost:5173"

    database_url: str = "postgresql+psycopg://fdrive:fdrive@localhost:5432/fdrive"
    redis_url: str = "redis://localhost:6379/0"

    s3_endpoint_url: str | None = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "fdrive"
    s3_region: str = "us-east-1"
    s3_presign_expire_seconds: int = 900  # 15 minutes

    # Auth
    jwt_secret: str = "dev-only-change-me-fdrive-jwt-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 14

    # Quota (Phase 04) — default free tier for new users
    default_bytes_limit: int = 5 * 1024 * 1024 * 1024  # 5 GiB

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
