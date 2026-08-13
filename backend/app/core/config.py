from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import computed_field


class Settings(BaseSettings):
    """
    Application Settings configuration.
    Validates and loads environment variables from .env file or OS environment.
    """
    model_config = SettingsConfigDict(
        env_file=".env", env_ignore_empty=True, extra="ignore"
    )

    # App Settings
    APP_NAME: str = "BINOM AI"
    APP_ENV: str = "development"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Supabase Settings
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_KEY: str
    DATABASE_URL: str

    # Auth Settings
    SUPABASE_JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Redis Settings
    REDIS_URL: str
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

    # AI APIs
    GOOGLE_AI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    GOOGLE_CSE_API_KEY: Optional[str] = None
    GOOGLE_CSE_ID: Optional[str] = None
    PRIMARY_LLM_MODEL: str = "gemini-1.5-pro"
    FALLBACK_LLM_MODEL: str = "gpt-4o"
    LLM_MAX_RETRIES: int = 3
    LLM_TIMEOUT_SECONDS: int = 120

    # Storage
    STORAGE_BUCKET_TENDER_DOCS: str = "tender-documents"
    STORAGE_BUCKET_COMPANY_ASSETS: str = "company-assets"
    STORAGE_BUCKET_EXPORTS: str = "exported-documents"
    STORAGE_BUCKET_EXTRACTED_TEXT: str = "extracted-texts"
    STORAGE_SIGNED_URL_EXPIRY: int = 3600

    # Export (Gotenberg)
    GOTENBERG_URL: str = "http://gotenberg:3000"

    # File Upload
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_MIME_TYPES: str = "application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    # Access control
    LIMITED_PROJECTS_LIMIT: int = 2

    @computed_field
    @property
    def parsed_allowed_mime_types(self) -> List[str]:
        return [mime.strip() for mime in self.ALLOWED_MIME_TYPES.split(",")]

    # Monitoring
    SENTRY_DSN: Optional[str] = None
    SENTRY_ENVIRONMENT: Optional[str] = None

    # CORS
    CORS_ORIGINS: str = ""

    @computed_field
    @property
    def parsed_cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
