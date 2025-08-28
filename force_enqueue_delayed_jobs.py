#!/usr/bin/env python3
"""
Force enqueue jobs that are stuck with delays for documents in 'new' status
"""

import sys
import os
sys.path.insert(0, '/app')

from datetime import datetime, timedelta
from app.models import ProcessingJob, Document
from app.db import SessionLocal
from app.tasks import (
    convert_document_to_pdf_task,
    process_document_tiling,
    process_document_thumbnails,
    process_document_ocr
)

def force_enqueue_delayed_jobs():
    """Find documents in 'new' status and force enqueue any delayed jobs"""

    db = SessionLocal()
    try:
        # Find documents in 'new' status from the last hour
        cutoff_time = datetime.utcnow() - timedelta(hours=1)

        stuck_docs = db.query(Document).filter(
            Document.status == "new",
            Document.created_at > cutoff_time
        ).all()

        print(f"Found {len(stuck_docs)} documents in 'new' status from last hour")

        total_enqueued = 0

        for doc in stuck_docs:
            print(f"\nProcessing document {doc.id}: {doc.title[:50]}...")

            # Get all jobs for this document
            jobs = db.query(ProcessingJob).filter(
                ProcessingJob.document_id == doc.id
            ).all()

            jobs_enqueued = 0

            for job in jobs:
                if job.status == "queued" and job.started_at is None:
                    print(f"  Enqueuing {job.job_type} job {job.id}...")

                    try:
                        # Enqueue the job immediately (no delay)
                        if job.job_type == "conversion":
                            task = convert_document_to_pdf_task.delay(doc.id, job.id)
                        elif job.job_type == "tiling":
                            task = process_document_tiling.delay(doc.id, job.id)
                        elif job.job_type == "thumbnails":
                            task = process_document_thumbnails.delay(doc.id, job.id)
                        elif job.job_type == "ocr":
                            task = process_document_ocr.delay(doc.id, job.id)
                        else:
                            print(f"    Unknown job type: {job.job_type}")
                            continue

                        # Update job with Celery task ID
                        job.celery_task_id = task.id
                        db.commit()

                        jobs_enqueued += 1
                        total_enqueued += 1
                        print(f"    ✅ Enqueued with task ID: {task.id}")

                    except Exception as e:
                        print(f"    ❌ Failed to enqueue: {e}")

            print(f"  📊 Enqueued {jobs_enqueued} jobs for document {doc.id}")

        print(f"\n🎉 Successfully enqueued {total_enqueued} delayed jobs!")
        print(f"📈 Processing should now proceed normally for all {len(stuck_docs)} documents")

    except Exception as e:
        print(f"❌ Error force enqueuing jobs: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    force_enqueue_delayed_jobs()
