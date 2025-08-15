import pytest
import time
from httpx import AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_full_document_processing_pipeline():
    """Test the complete document processing pipeline"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Create a document (which should enqueue processing jobs)
        resp = await ac.post("/documents/", json={
            "title": "Integration Test Document.pdf",
            "description": "A document to test the full processing pipeline",
            "source": "Integration Test",
            "language": "en",
        })
        assert resp.status_code == 200
        doc_data = resp.json()
        doc_id = doc_data["id"]
        assert doc_data["title"] == "Integration Test Document.pdf"
        assert doc_data["status"] == "new"
        
        # Get processing jobs for the document
        resp = await ac.get(f"/documents/{doc_id}/jobs")
        assert resp.status_code == 200
        jobs = resp.json()
        
        # Should have 3 jobs: tiling, thumbnails, ocr
        assert len(jobs) == 3
        job_types = {job["job_type"] for job in jobs}
        assert job_types == {"tiling", "thumbnails", "ocr"}
        
        # All jobs should be queued initially
        for job in jobs:
            assert job["status"] == "queued"
            assert job["progress"] == 0
            assert job["error_message"] is None
            assert job["celery_task_id"] is not None  # Should have task IDs
        
        print(f"✅ Document {doc_id} created with 3 processing jobs queued")


@pytest.mark.asyncio
async def test_api_key_workflow():
    """Test API key creation and management"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Create API key
        resp = await ac.post("/auth/admin/api-keys", json={
            "name": "Integration Test Key",
            "scopes": "ingest,search,export",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["api_key"].startswith("hc_")
        assert data["key_info"]["name"] == "Integration Test Key"
        assert data["key_info"]["scopes"] == "ingest,search,export"
        
        key_id = data["key_info"]["id"]
        api_key = data["api_key"]
        
        print(f"✅ API key created: {api_key[:10]}...")
        
        # List API keys
        resp = await ac.get("/auth/admin/api-keys")
        assert resp.status_code == 200
        keys = resp.json()
        assert len(keys) >= 1
        
        # Find our key
        our_key = next((k for k in keys if k["id"] == key_id), None)
        assert our_key is not None
        assert our_key["name"] == "Integration Test Key"
        
        print(f"✅ API key listed successfully")
        
        # Revoke API key
        resp = await ac.delete(f"/auth/admin/api-keys/{key_id}")
        assert resp.status_code == 200
        
        # Verify key is revoked
        resp = await ac.get("/auth/admin/api-keys")
        assert resp.status_code == 200
        keys = resp.json()
        revoked_key = next((k for k in keys if k["id"] == key_id), None)
        assert revoked_key is None  # Should not appear in active keys
        
        print(f"✅ API key revoked successfully")


@pytest.mark.asyncio
async def test_user_management():
    """Test user creation and management"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Create user
        resp = await ac.post("/auth/admin/users", json={
            "email": "integration@test.com",
            "full_name": "Integration Test User",
            "role": "contributor",
            "password": "TestP@ssw0rd123!",
        })
        # Note: This might fail if user already exists from previous tests
        if resp.status_code == 400 and "already exists" in resp.text:
            print("✅ User already exists (expected in repeated tests)")
        else:
            assert resp.status_code == 200
            user_data = resp.json()
            assert user_data["email"] == "integration@test.com"
            assert user_data["role"] == "contributor"
            assert user_data["is_active"] is True
            print(f"✅ User created: {user_data['email']}")
        
        # List users
        resp = await ac.get("/auth/admin/users")
        assert resp.status_code == 200
        users = resp.json()
        assert len(users) >= 1
        
        # Find our user
        our_user = next((u for u in users if u["email"] == "integration@test.com"), None)
        assert our_user is not None
        print(f"✅ User listed successfully")
        
        # Test login flow
        resp = await ac.post("/auth/login", json={
            "email": "integration@test.com",
            "password": "TestP@ssw0rd123!",
        })
        assert resp.status_code == 200
        login_data = resp.json()
        assert login_data["mfa_required"] is True
        print(f"✅ Login flow works (MFA required as expected)")


@pytest.mark.asyncio
async def test_document_listing_and_retrieval():
    """Test document listing and individual retrieval"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Create multiple documents
        doc_titles = ["Test Doc 1.pdf", "Test Doc 2.pdf", "Test Doc 3.pdf"]
        created_docs = []
        
        for title in doc_titles:
            resp = await ac.post("/documents/", json={
                "title": title,
                "description": f"Description for {title}",
                "source": "Test Suite",
                "language": "en",
            })
            assert resp.status_code == 200
            created_docs.append(resp.json())
        
        print(f"✅ Created {len(created_docs)} test documents")
        
        # List all documents
        resp = await ac.get("/documents/")
        assert resp.status_code == 200
        docs = resp.json()
        assert len(docs) >= len(doc_titles)
        
        # Verify recent-first ordering (newest first)
        for i in range(len(docs) - 1):
            assert docs[i]["created_at"] >= docs[i + 1]["created_at"]
        
        print(f"✅ Document listing works (found {len(docs)} total documents)")
        
        # Test individual document retrieval
        for doc in created_docs:
            resp = await ac.get(f"/documents/{doc['id']}")
            assert resp.status_code == 200
            retrieved_doc = resp.json()
            assert retrieved_doc["id"] == doc["id"]
            assert retrieved_doc["title"] == doc["title"]
        
        print(f"✅ Individual document retrieval works")


@pytest.mark.asyncio
async def test_health_and_system_endpoints():
    """Test system health and info endpoints"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Test health endpoint
        resp = await ac.get("/health")
        assert resp.status_code == 200
        health_data = resp.json()
        assert health_data["status"] == "ok"
        
        # Test root endpoint
        resp = await ac.get("/")
        assert resp.status_code == 200
        root_data = resp.json()
        assert root_data["service"] == "haqnow-community"
        assert "version" in root_data
        
        print(f"✅ System endpoints working")


@pytest.mark.asyncio
async def test_presigned_upload_endpoint():
    """Test presigned upload endpoint (will fail without S3 config, but tests structure)"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.post("/documents/presigned-upload", json={
            "filename": "test-upload.pdf",
            "content_type": "application/pdf",
            "size": 1024000,  # 1MB
        })
        
        # Expect 400 due to missing S3 config in test environment
        assert resp.status_code == 400
        assert "S3 credentials not configured" in resp.text
        
        print(f"✅ Presigned upload endpoint structure correct (S3 config missing as expected)")


if __name__ == "__main__":
    # Run tests manually for debugging
    import asyncio
    
    async def run_tests():
        print("🧪 Running integration tests...")
        await test_health_and_system_endpoints()
        await test_user_management()
        await test_api_key_workflow()
        await test_document_listing_and_retrieval()
        await test_full_document_processing_pipeline()
        await test_presigned_upload_endpoint()
        print("✅ All integration tests passed!")
    
    asyncio.run(run_tests())
