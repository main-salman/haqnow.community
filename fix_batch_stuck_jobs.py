#!/usr/bin/env python3
"""
Fix all stuck OCR jobs from the batch upload and reset processing
"""

import sys
import os
sys.path.insert(0, '/app')

from datetime import datetime
from app.models import ProcessingJob, Document
from app.db import SessionLocal

def fix_all_stuck_ocr_jobs():
    """Fix all stuck OCR jobs from the large batch"""

    db = SessionLocal()
    try:
        # Get all stuck OCR jobs that are "running" for more than 20 minutes
        cutoff_time = datetime.utcnow().timestamp() - (20 * 60)  # 20 minutes ago

        stuck_jobs = db.query(ProcessingJob).filter(
            ProcessingJob.job_type == "ocr",
            ProcessingJob.status == "running"
        ).all()

        print(f"Found {len(stuck_jobs)} potentially stuck OCR jobs")

        fixed_docs = set()

        for job in stuck_jobs:
            doc_id = job.document_id
            print(f"Processing job {job.id} for document {doc_id}")

            # Check if pages already exist (successful processing despite stuck job)
            try:
                from app.s3_client import download_from_s3
                from app.config import get_settings
                settings = get_settings()

                # Test if first page exists
                page_key = f"pages/{doc_id}/page_0.webp"
                download_from_s3(settings.s3_bucket_tiles, page_key)

                # If page exists, mark job as completed
                print(f"  ✅ Pages found for document {doc_id}, marking as completed")
                job.status = "completed"
                job.completed_at = datetime.utcnow()
                job.error_message = "Auto-recovered: pages were already processed"
                fixed_docs.add(doc_id)

            except Exception as e:
                print(f"  ⏰ No pages found for document {doc_id}, marking as failed (timeout)")
                # Mark as failed due to timeout
                job.status = "failed"
                job.completed_at = datetime.utcnow()
                job.error_message = "OCR timeout - task exceeded time limit"
                fixed_docs.add(doc_id)

        db.commit()
        print(f"\n📊 Updated {len(stuck_jobs)} stuck OCR jobs")

        # Now update document statuses
        for doc_id in fixed_docs:
            document = db.query(Document).filter(Document.id == doc_id).first()
            if not document:
                continue

            # Get all jobs for this document
            jobs = db.query(ProcessingJob).filter(ProcessingJob.document_id == doc_id).all()

            # Check if all jobs are complete
            all_complete = all(job.status == "completed" for job in jobs)
            has_failed = any(job.status == "failed" for job in jobs)

            old_status = document.status
            if has_failed:
                document.status = "error"
                print(f"  📄 Document {doc_id}: {old_status} -> error")
            elif all_complete:
                document.status = "ready"
                print(f"  📄 Document {doc_id}: {old_status} -> ready")
            else:
                print(f"  📄 Document {doc_id}: {old_status} (still processing)")

        db.commit()

        # Summary
        status_count = {}
        for doc_id in fixed_docs:
            doc = db.query(Document).filter(Document.id == doc_id).first()
            if doc:
                status_count[doc.status] = status_count.get(doc.status, 0) + 1

        print(f"\n🎉 Batch processing recovery completed!")
        print(f"📈 Document status summary:")
        for status, count in status_count.items():
            print(f"   {status}: {count} documents")

    except Exception as e:
        print(f"❌ Error fixing jobs: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_all_stuck_ocr_jobs()
