import os
from functools import lru_cache


class Settings:
    """Environment-driven application settings.

    Values are read from the environment at instantiation time to allow tests
    and scripts to override via environment variables reliably.
    """

    app_name: str
    env: str
    jwt_secret: str
    jwt_issuer: str
    jwt_audience: str
    jwt_exp_minutes: int
    database_url: str

    s3_endpoint: str | None
    s3_region: str
    s3_access_key: str | None
    s3_secret_key: str | None
    s3_bucket_originals: str
    s3_bucket_thumbnails: str
    s3_bucket_tiles: str
    s3_bucket_ocr: str
    s3_bucket_exports: str

    redis_url: str
    celery_broker_url: str
    celery_result_backend: str

    def __init__(self) -> None:
        self.app_name = "Haqnow Community API"
        self.env = os.getenv("APP_ENV", "dev")
        self.jwt_secret = os.getenv("JWT_SECRET_KEY", "dev-secret-change")
        self.jwt_issuer = os.getenv("JWT_ISSUER", "haqnow.community")
        self.jwt_audience = os.getenv("JWT_AUDIENCE", "haqnow.clients")
        self.jwt_exp_minutes = int(os.getenv("JWT_EXP_MINUTES", "60"))
        self.database_url = os.getenv("DATABASE_URL", "sqlite+pysqlite:///./dev.db")

        self.s3_endpoint = os.getenv("S3_ENDPOINT")
        self.s3_region = os.getenv("S3_REGION", "ch-gva-2")
        self.s3_access_key = os.getenv("EXOSCALE_S3_ACCESS_KEY")
        self.s3_secret_key = os.getenv("EXOSCALE_S3_SECRET_KEY")
        self.s3_bucket_originals = os.getenv("S3_BUCKET_ORIGINALS", "originals")
        self.s3_bucket_thumbnails = os.getenv("S3_BUCKET_THUMBNAILS", "thumbnails")
        self.s3_bucket_tiles = os.getenv("S3_BUCKET_TILES", "tiles")
        self.s3_bucket_ocr = os.getenv("S3_BUCKET_OCR", "ocr")
        self.s3_bucket_exports = os.getenv("S3_BUCKET_EXPORTS", "exports")

        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.celery_broker_url = os.getenv(
            "CELERY_BROKER_URL", "redis://localhost:6379/0"
        )
        self.celery_result_backend = os.getenv(
            "CELERY_RESULT_BACKEND", "redis://localhost:6379/0"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
