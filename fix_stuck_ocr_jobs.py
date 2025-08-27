#!/usr/bin/env python3
"""
Fix the current stuck OCR jobs (Documents 1028-1032)
"""

import sys
import os

# Add the app directory to Python path
sys.path.insert(0, '/app')

from datetime import datetime
from app.models import ProcessingJob, Document
from app.db import SessionLocal

def fix_stuck_ocr_jobs():
    """Fix the specific stuck OCR jobs for documents 1028-1032"""

    db = SessionLocal()
    try:
        # Get stuck OCR jobs for documents 1028-1032
        stuck_jobs = db.query(ProcessingJob).filter(
            ProcessingJob.document_id.in_([1028, 1029, 1030, 1031, 1032]),
            ProcessingJob.job_type == "ocr",
            ProcessingJob.status == "running"
        ).all()

        print(f"Found {len(stuck_jobs)} stuck OCR jobs")

        for job in stuck_jobs:
            print(f"Fixing job {job.id} for document {job.document_id}")

            # Check if pages exist for this document
            try:
                from app.s3_client import download_from_s3
                from app.config import get_settings
                settings = get_settings()

                # Test if first page exists
                page_key = f"pages/{job.document_id}/page_0.webp"
                download_from_s3(settings.s3_bucket_tiles, page_key)

                # If page exists, mark job as completed
                print(f"  ✅ Pages found for document {job.document_id}, marking as completed")
                job.status = "completed"
                job.completed_at = datetime.utcnow()
                job.error_message = "Auto-recovered: pages were already processed"

            except Exception as e:
                print(f"  ❌ No pages found for document {job.document_id}: {e}")
                # Mark as failed due to timeout
                job.status = "failed"
                job.completed_at = datetime.utcnow()
                job.error_message = "OCR timeout - killed during processing"

        db.commit()

        # Now check and update document statuses
        for doc_id in [1028, 1029, 1030, 1031, 1032]:
            document = db.query(Document).filter(Document.id == doc_id).first()
            if not document:
                continue

            # Get all jobs for this document
            jobs = db.query(ProcessingJob).filter(ProcessingJob.document_id == doc_id).all()

            # Check if all jobs are complete
            all_complete = all(job.status == "completed" for job in jobs)
            has_failed = any(job.status == "failed" for job in jobs)

            if has_failed:
                document.status = "error"
                print(f"  📄 Document {doc_id}: marked as 'error' (has failed jobs)")
            elif all_complete:
                document.status = "ready"
                print(f"  📄 Document {doc_id}: marked as 'ready' (all jobs complete)")
            else:
                print(f"  📄 Document {doc_id}: still processing...")

        db.commit()
        print(f"\n🎉 Successfully fixed stuck OCR jobs!")

    except Exception as e:
        print(f"❌ Error fixing jobs: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_stuck_ocr_jobs()
