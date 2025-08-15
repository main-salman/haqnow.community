import pytest
from httpx import AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_admin_create_and_login(tmp_path):
    # Use in-memory sqlite for test via env DATABASE_URL if needed; the app defaults to sqlite file.
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Create user
        resp = await ac.post("/auth/admin/users", json={
            "email": "alice@example.com",
            "full_name": "Alice",
            "role": "admin",
            "password": "P@ssw0rd!",
        })
        assert resp.status_code == 200, resp.text

        # Login (expects MFA)
        resp = await ac.post("/auth/login", json={
            "email": "alice@example.com",
            "password": "P@ssw0rd!",
        })
        assert resp.status_code == 200
        assert resp.json()["mfa_required"] is True


