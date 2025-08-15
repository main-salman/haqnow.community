import pytest
from httpx import AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_api_key_management():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Create API key
        resp = await ac.post("/auth/admin/api-keys", json={
            "name": "Test Key",
            "scopes": "ingest,search",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["api_key"].startswith("hc_")
        assert data["key_info"]["name"] == "Test Key"
        assert data["key_info"]["scopes"] == "ingest,search"
        
        key_id = data["key_info"]["id"]
        
        # List API keys
        resp = await ac.get("/auth/admin/api-keys")
        assert resp.status_code == 200
        keys = resp.json()
        assert len(keys) == 1
        assert keys[0]["name"] == "Test Key"
        
        # Revoke API key
        resp = await ac.delete(f"/auth/admin/api-keys/{key_id}")
        assert resp.status_code == 200
        
        # Verify key is revoked
        resp = await ac.get("/auth/admin/api-keys")
        assert resp.status_code == 200
        keys = resp.json()
        assert len(keys) == 0
