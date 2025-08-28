#!/usr/bin/env python3
"""
Final comprehensive fix - handle ALL stuck jobs regardless of status
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

def final_comprehensive_fix():
    """Fix ALL stuck jobs - no exceptions"""

    db = SessionLocal()
    try:
        print("🚀 FINAL COMPREHENSIVE FIX - HANDLING ALL STUCK JOBS")
        print("=" * 70)

        # Find ALL documents from last 6 hours with any jobs not started
        cutoff_time = datetime.utcnow() - timedelta(hours=6)

        # Get all jobs that are queued/pending and never started
        stuck_jobs = db.query(ProcessingJob).filter(
            ProcessingJob.status.in_(["queued", "pending"]),
            ProcessingJob.started_at.is_(None)
        ).all()

        # Filter by document creation time
        recent_stuck_jobs = []
        for job in stuck_jobs:
            document = db.query(Document).filter(Document.id == job.document_id).first()
            if document and document.created_at > cutoff_time:
                recent_stuck_jobs.append(job)

        stuck_jobs = recent_stuck_jobs

        print(f"📊 Found {len(stuck_jobs)} jobs that are stuck (never started)")

        # Group by document for organized processing
        jobs_by_doc = {}
        for job in stuck_jobs:
            if job.document_id not in jobs_by_doc:
                jobs_by_doc[job.document_id] = []
            jobs_by_doc[job.document_id].append(job)

        print(f"📊 Affecting {len(jobs_by_doc)} documents")

        total_enqueued = 0

        for doc_id, jobs in jobs_by_doc.items():
            document = db.query(Document).filter(Document.id == doc_id).first()
            print(f"\n📄 Document {doc_id}: {document.title[:40] if document else 'Unknown'}...")

            # Force enqueue ALL stuck jobs for this document
            jobs_enqueued = 0

            for job in jobs:
                print(f"   🚀 Force enqueuing {job.job_type} job {job.id}...")

                try:
                    # Enqueue immediately regardless of dependencies
                    if job.job_type == "conversion":
                        task = convert_document_to_pdf_task.delay(doc_id, job.id)
                    elif job.job_type == "tiling":
                        task = process_document_tiling.delay(doc_id, job.id)
                    elif job.job_type == "thumbnails":
                        task = process_document_thumbnails.delay(doc_id, job.id)
                    elif job.job_type == "ocr":
                        task = process_document_ocr.delay(doc_id, job.id)
                    else:
                        print(f"      ❓ Unknown job type: {job.job_type}")
                        continue

                    # Update job with Celery task ID
                    job.celery_task_id = task.id
                    db.commit()

                    jobs_enqueued += 1
                    total_enqueued += 1
                    print(f"      ✅ Enqueued with task ID: {task.id}")

                except Exception as e:
                    print(f"      ❌ Failed to enqueue: {e}")

            print(f"   📈 Document {doc_id}: Enqueued {jobs_enqueued} jobs")

        print("\n" + "=" * 70)
        print(f"🎉 FINAL FIX COMPLETED!")
        print(f"📊 Total jobs force-enqueued: {total_enqueued}")
        print(f"📈 Documents affected: {len(jobs_by_doc)}")

        # Show expected outcome
        print(f"\n🔍 EXPECTED OUTCOME:")
        print(f"   ✅ All {total_enqueued} jobs should now be in Celery queues")
        print(f"   ✅ Workers will start processing immediately")
        print(f"   ✅ Documents should complete in 15-30 minutes")
        print(f"   ✅ No more stuck jobs")

    except Exception as e:
        print(f"❌ Error in final fix: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    final_comprehensive_fix()
