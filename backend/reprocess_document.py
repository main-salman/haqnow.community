#!/usr/bin/env python3
"""
Re-queue processing jobs for a specific document to regenerate tiles with correct content
"""

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

from app.db import SessionLocal
from app.models import Document, ProcessingJob
from app.tasks import process_document_tiling

def reprocess_document(document_id: int):
    """Re-queue processing jobs for a document"""
    print(f"🔄 Reprocessing document {document_id}...")
    
    with SessionLocal() as db:
        # Get document
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            print(f"❌ Document {document_id} not found")
            return False
            
        print(f"📄 Document: {document.title}")
        print(f"📊 Current status: {document.status}")
        
        # Find existing tiling job
        tiling_job = db.query(ProcessingJob).filter(
            ProcessingJob.document_id == document_id,
            ProcessingJob.job_type == "tiling"
        ).first()
        
        if tiling_job:
            print(f"📋 Found existing tiling job: {tiling_job.id} (status: {tiling_job.status})")
            
            # Reset the job to queued
            tiling_job.status = "queued"
            tiling_job.progress = 0
            tiling_job.error_message = None
            tiling_job.celery_task_id = None
            tiling_job.started_at = None
            tiling_job.completed_at = None
            db.commit()
            
            print(f"✅ Reset tiling job to queued")
            
            # Dispatch new tiling task
            try:
                task = process_document_tiling.delay(document_id, tiling_job.id)
                tiling_job.celery_task_id = task.id
                db.commit()
                
                print(f"✅ Dispatched new tiling task: {task.id}")
                return True
                
            except Exception as e:
                print(f"❌ Failed to dispatch tiling task: {e}")
                tiling_job.status = "failed"
                tiling_job.error_message = f"Failed to dispatch: {str(e)}"
                db.commit()
                return False
        else:
            print("❌ No existing tiling job found")
            return False

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python reprocess_document.py <document_id>")
        sys.exit(1)
        
    document_id = int(sys.argv[1])
    success = reprocess_document(document_id)
    
    if success:
        print(f"\n🎉 Document {document_id} queued for reprocessing!")
    else:
        print(f"\n❌ Failed to reprocess document {document_id}")