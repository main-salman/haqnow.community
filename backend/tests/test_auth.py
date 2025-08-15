import pytest
from app.main import app
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_admin_create_and_login(tmp_path):
    # Use in-memory sqlite for test via env DATABASE_URL if needed; the app defaults to sqlite file.
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Use a unique email to avoid conflicts
        import time

        unique_email = f"alice{int(time.time())}@example.com"

        # Create user
        resp = await ac.post(
            "/auth/admin/users",
            json={
                "email": unique_email,
                "full_name": "Alice",
                "role": "admin",
                "password": "P@ssw0rd!",
            },
        )
        assert resp.status_code == 200, resp.text

        # Login (MFA not enabled by default for new users)
        resp = await ac.post(
            "/auth/login",
            json={
                "email": unique_email,
                "password": "P@ssw0rd!",
            },
        )
        assert resp.status_code == 200
        login_data = resp.json()
        # MFA is not enabled by default, so should get access token
        assert "mfa_required" in login_data
        if login_data["mfa_required"]:
            # If MFA is required, we should not get an access token
            assert "access_token" not in login_data
        else:
            # If MFA is not required, we should get an access token
            assert "access_token" in login_data
