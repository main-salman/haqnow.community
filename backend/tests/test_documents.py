import pytest
from app.main import app
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_document_creation():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Clean up existing documents first
        await ac.delete("/documents/")

        # Create document
        resp = await ac.post(
            "/documents/",
            json={
                "title": "Test Document",
                "description": "A test document",
                "source": "Test Source",
                "language": "en",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Test Document"
        assert data["status"] == "new"
        assert data["uploader_id"] == 1

        doc_id = data["id"]

        # Get document
        resp = await ac.get(f"/documents/{doc_id}")
        assert resp.status_code == 200
        doc = resp.json()
        assert doc["title"] == "Test Document"

        # List documents
        resp = await ac.get("/documents/")
        assert resp.status_code == 200
        docs = resp.json()
        assert len(docs) == 1
        assert docs[0]["title"] == "Test Document"


@pytest.mark.asyncio
async def test_presigned_upload():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Note: This will fail without S3 credentials, but tests the endpoint structure
        resp = await ac.post(
            "/documents/presigned-upload",
            json={
                "filename": "test.pdf",
                "content_type": "application/pdf",
                "size": 1024,
            },
        )
        # Expect 400 due to missing S3 config in test environment
        assert resp.status_code == 400
        assert "S3 credentials not configured" in resp.text
