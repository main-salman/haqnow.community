import os
from functools import lru_cache


class Settings:
    app_name: str = "Haqnow Community API"
    env: str = os.getenv("APP_ENV", "dev")
    jwt_secret: str = os.getenv("JWT_SECRET_KEY", "dev-secret-change")
    jwt_issuer: str = os.getenv("JWT_ISSUER", "haqnow.community")
    jwt_audience: str = os.getenv("JWT_AUDIENCE", "haqnow.clients")
    jwt_exp_minutes: int = int(os.getenv("JWT_EXP_MINUTES", "60"))
    database_url: str = os.getenv("DATABASE_URL", "sqlite+pysqlite:///./dev.db")

    s3_endpoint: str | None = os.getenv("S3_ENDPOINT")
    s3_region: str = os.getenv("S3_REGION", "ch-gva-2")
    s3_access_key: str | None = os.getenv("EXOSCALE_S3_ACCESS_KEY")
    s3_secret_key: str | None = os.getenv("EXOSCALE_S3_SECRET_KEY")
    s3_bucket_originals: str = os.getenv("S3_BUCKET_ORIGINALS", "originals")
    s3_bucket_thumbnails: str = os.getenv("S3_BUCKET_THUMBNAILS", "thumbnails")
    s3_bucket_tiles: str = os.getenv("S3_BUCKET_TILES", "tiles")
    s3_bucket_ocr: str = os.getenv("S3_BUCKET_OCR", "ocr")
    s3_bucket_exports: str = os.getenv("S3_BUCKET_EXPORTS", "exports")

    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    celery_broker_url: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    celery_result_backend: str = os.getenv(
        "CELERY_RESULT_BACKEND", "redis://localhost:6379/0"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
