import pytest
from app.main import app
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_document_processing_jobs():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Create document (which should enqueue processing jobs)
        resp = await ac.post(
            "/documents/",
            json={
                "title": "Test Processing Document",
                "description": "A document to test processing",
                "source": "Test Source",
                "language": "en",
            },
        )
        assert resp.status_code == 200
        doc_data = resp.json()
        doc_id = doc_data["id"]

        # Get processing jobs for the document
        resp = await ac.get(f"/documents/{doc_id}/jobs")
        assert resp.status_code == 200
        jobs = resp.json()

        # Should have 3 jobs: tiling, thumbnails, ocr
        assert len(jobs) == 3
        job_types = {job["job_type"] for job in jobs}
        assert job_types == {"tiling", "thumbnails", "ocr"}

        # Jobs may be queued, running, or completed depending on timing
        for job in jobs:
            assert job["status"] in ["queued", "running", "completed", "failed"]
            assert job["progress"] >= 0
            # error_message can be None or a string
