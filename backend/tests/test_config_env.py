from app.config import get_settings


def test_settings_reads_exoscale_env(monkeypatch):
    # Clear cached settings so env changes are reflected
    try:
        get_settings.cache_clear()  # type: ignore[attr-defined]
    except Exception:
        pass

    # Provide fake Exoscale/SOS env to ensure Settings picks them up
    monkeypatch.setenv("EXOSCALE_S3_ACCESS_KEY", "test-access")
    monkeypatch.setenv("EXOSCALE_S3_SECRET_KEY", "test-secret")
    monkeypatch.setenv("S3_ENDPOINT", "https://sos.exo.io")
    monkeypatch.setenv("S3_REGION", "ch-gva-2")
    monkeypatch.setenv("S3_BUCKET_ORIGINALS", "orig")

    settings = get_settings()
    assert settings.s3_access_key == "test-access"
    assert settings.s3_secret_key == "test-secret"
    assert settings.s3_endpoint == "https://sos.exo.io"
    assert settings.s3_region == "ch-gva-2"
    assert settings.s3_bucket_originals == "orig"
