from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Claim Cruncher"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    # Database
    database_url: str = "postgresql+asyncpg://claimcruncher:claimcruncher@localhost:5432/claimcruncher"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    jwt_secret: str = "change-me-in-production"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7

    # Storage
    storage_backend: str = "local"
    upload_dir: str = "./uploads"
    s3_endpoint: str = "http://localhost:9000"
    s3_bucket: str = "claim-documents"
    s3_access_key: str = ""
    s3_secret_key: str = ""

    # OCR
    ocr_confidence_threshold: float = 0.85
    ocr_cloud_provider: str = "none"

    # Cruncher AI
    anthropic_api_key: str = ""
    cruncher_model: str = "claude-sonnet-4-6"
    cruncher_flag_model: str = "claude-haiku-4-5-20251001"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
