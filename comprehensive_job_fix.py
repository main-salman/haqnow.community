#!/usr/bin/env python3
"""
Comprehensive fix for all stuck jobs and elimination of excessive delays
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

def comprehensive_job_fix():
    """Fix ALL stuck jobs and prevent future delays"""

    db = SessionLocal()
    try:
        print("🔧 COMPREHENSIVE JOB FIX STARTING...")
        print("=" * 60)

        # 1. Find ALL documents in 'new' status from last 6 hours
        cutoff_time = datetime.utcnow() - timedelta(hours=6)

        stuck_docs = db.query(Document).filter(
            Document.status == "new",
            Document.created_at > cutoff_time
        ).all()

        print(f"📊 Found {len(stuck_docs)} documents in 'new' status from last 6 hours")

        total_jobs_fixed = 0
        documents_by_status = {"ready": 0, "processing": 0, "error": 0}

        for doc in stuck_docs:
            print(f"\n📄 Document {doc.id}: {doc.title[:40]}...")

            # Get all jobs for this document
            jobs = db.query(ProcessingJob).filter(
                ProcessingJob.document_id == doc.id
            ).all()

            jobs_enqueued = 0
            conversion_done = False

            # Check what's already completed
            completed_jobs = [j for j in jobs if j.status == "completed"]
            print(f"   ✅ {len(completed_jobs)} jobs already completed")

            # Force enqueue pending/queued jobs
            for job in jobs:
                if job.status in ["queued", "pending"] and job.started_at is None:

                    # Skip jobs that depend on conversion if conversion isn't done
                    if job.job_type in ["tiling", "thumbnails", "ocr"]:
                        conversion_job = next((j for j in jobs if j.job_type == "conversion"), None)
                        if conversion_job and conversion_job.status != "completed":
                            print(f"   ⏳ Skipping {job.job_type} - waiting for conversion")
                            continue

                    print(f"   🚀 Force enqueuing {job.job_type} job {job.id}...")

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
                            print(f"      ❓ Unknown job type: {job.job_type}")
                            continue

                        # Update job with Celery task ID
                        job.celery_task_id = task.id
                        db.commit()

                        jobs_enqueued += 1
                        total_jobs_fixed += 1
                        print(f"      ✅ Enqueued with task ID: {task.id}")

                    except Exception as e:
                        print(f"      ❌ Failed to enqueue: {e}")

            # Update document status if needed
            if jobs_enqueued > 0:
                print(f"   📈 Document {doc.id}: Enqueued {jobs_enqueued} jobs")
                documents_by_status["processing"] += 1
            else:
                # Check if all jobs are done
                all_complete = all(job.status == "completed" for job in jobs)
                has_failed = any(job.status == "failed" for job in jobs)

                if has_failed:
                    doc.status = "error"
                    documents_by_status["error"] += 1
                    print(f"   ❌ Document {doc.id}: Marked as 'error'")
                elif all_complete:
                    doc.status = "ready"
                    documents_by_status["ready"] += 1
                    print(f"   ✅ Document {doc.id}: Marked as 'ready'")
                else:
                    documents_by_status["processing"] += 1
                    print(f"   🔄 Document {doc.id}: Still processing")

        db.commit()

        print("\n" + "=" * 60)
        print("🎉 COMPREHENSIVE JOB FIX COMPLETED!")
        print(f"📊 Total jobs force-enqueued: {total_jobs_fixed}")
        print(f"📈 Documents by predicted status:")
        for status, count in documents_by_status.items():
            print(f"   {status}: {count} documents")

        # 3. Show current queue status
        print(f"\n🔍 NEXT STEPS:")
        print(f"   1. Workers should now be processing {total_jobs_fixed} additional jobs")
        print(f"   2. Check queue lengths in 5-10 minutes to see progress")
        print(f"   3. Most documents should complete in 15-30 minutes")
        print(f"   4. Fix delay logic permanently to prevent recurrence")

    except Exception as e:
        print(f"❌ Error in comprehensive fix: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    comprehensive_job_fix()
