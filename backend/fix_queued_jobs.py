#!/usr/bin/env python3
"""
Script to fix queued jobs that weren't properly dispatched to Celery
"""

import os
import sys

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

from app.db import SessionLocal
from app.models import Document, ProcessingJob
from app.tasks import (
    convert_document_to_pdf_task,
    process_document_tiling,
    process_document_thumbnails,
    process_document_ocr,
)


def fix_queued_jobs():
    """Fix queued jobs that don't have Celery task IDs"""

    with SessionLocal() as db:
        try:
            print("🔄 Fixing queued jobs...")

            # Find all queued jobs without task IDs
            queued_jobs = (
                db.query(ProcessingJob)
                .filter(
                    ProcessingJob.status == "queued", ProcessingJob.celery_task_id.is_(None)
                )
                .order_by(ProcessingJob.document_id, ProcessingJob.job_type)
                .all()
            )

            print(f"📊 Found {len(queued_jobs)} jobs to fix")

            if len(queued_jobs) == 0:
                print("✅ No jobs to fix")
                return

            # Group jobs by document
            jobs_by_doc = {}
            for job in queued_jobs:
                if job.document_id not in jobs_by_doc:
                    jobs_by_doc[job.document_id] = []
                jobs_by_doc[job.document_id].append(job)

            print(f"📋 Processing {len(jobs_by_doc)} documents")

            # Dispatch tasks for each document
            for doc_id, jobs in jobs_by_doc.items():
                print(f"\n🔧 Fixing jobs for document {doc_id}")

                # Sort jobs to ensure proper order: conversion first, then others
                job_order = {"conversion": 0, "tiling": 1, "thumbnails": 2, "ocr": 3}
                jobs.sort(key=lambda x: job_order.get(x.job_type, 999))

                for i, job in enumerate(jobs):
                    try:
                        task_delay = 0
                        if job.job_type != "conversion":
                            # Non-conversion jobs wait for conversion to complete
                            task_delay = 5 + (i * 2)

                        print(f"  📤 Dispatching {job.job_type} job {job.id} with delay {task_delay}s")

                        # Dispatch the appropriate task
                        if job.job_type == "conversion":
                            if task_delay > 0:
                                task = convert_document_to_pdf_task.apply_async(
                                    args=[doc_id, job.id], countdown=task_delay
                                )
                            else:
                                task = convert_document_to_pdf_task.delay(doc_id, job.id)
                        elif job.job_type == "tiling":
                            task = process_document_tiling.apply_async(
                                args=[doc_id, job.id], countdown=task_delay
                            )
                        elif job.job_type == "thumbnails":
                            task = process_document_thumbnails.apply_async(
                                args=[doc_id, job.id], countdown=task_delay
                            )
                        elif job.job_type == "ocr":
                            task = process_document_ocr.apply_async(
                                args=[doc_id, job.id], countdown=task_delay
                            )

                        # Update job with task ID
                        job.celery_task_id = task.id
                        db.commit()

                        print(f"    ✅ Task dispatched: {task.id}")

                    except Exception as e:
                        print(f"    ❌ Failed to dispatch {job.job_type}: {e}")
                        job.status = "failed"
                        job.error_message = f"Failed to dispatch task: {str(e)}"
                        db.commit()

            print(f"\n🎉 Job fixing completed!")

        except Exception as e:
            print(f"❌ Error during job fixing: {str(e)}")
            db.rollback()
            raise

        finally:
            db.close()


if __name__ == "__main__":
    print("🔧 Queued Job Fixer")
    print("This will re-dispatch Celery tasks for jobs that are stuck in 'queued' status")
    print("===============================================================\n")

    fix_queued_jobs()