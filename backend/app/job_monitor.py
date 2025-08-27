"""
Job monitoring system to detect and fix stuck processing jobs
"""

import logging
from datetime import datetime, timedelta
from typing import List

from sqlalchemy.orm import Session

from .db import SessionLocal
from .models import Document, ProcessingJob
from .tasks import (
    convert_document_to_pdf_task,
    process_document_ocr,
    process_document_thumbnails,
    process_document_tiling,
)

logger = logging.getLogger(__name__)


def find_stuck_jobs(db: Session, max_runtime_minutes: int = 30) -> List[ProcessingJob]:
    """Find jobs that have been running for too long"""
    cutoff_time = datetime.utcnow() - timedelta(minutes=max_runtime_minutes)

    stuck_jobs = (
        db.query(ProcessingJob)
        .filter(
            ProcessingJob.status == "running", ProcessingJob.started_at < cutoff_time
        )
        .all()
    )

    return stuck_jobs


def find_orphaned_jobs(db: Session) -> List[ProcessingJob]:
    """Find jobs that are 'running' but have no active Celery task"""
    from celery import current_app

    running_jobs = (
        db.query(ProcessingJob)
        .filter(
            ProcessingJob.status == "running", ProcessingJob.celery_task_id.isnot(None)
        )
        .all()
    )

    orphaned_jobs = []
    active_tasks = current_app.control.inspect().active()

    if not active_tasks:
        # If we can't get active tasks, assume all running jobs are orphaned
        return running_jobs

    # Get all active task IDs across all workers
    active_task_ids = set()
    for worker_tasks in active_tasks.values():
        for task in worker_tasks:
            active_task_ids.add(task["id"])

    for job in running_jobs:
        if job.celery_task_id not in active_task_ids:
            orphaned_jobs.append(job)

    return orphaned_jobs


def recover_stuck_job(job: ProcessingJob, db: Session, retry: bool = True) -> bool:
    """Recover a stuck job by retrying or marking as failed"""
    logger.info(
        f"Recovering stuck job {job.id} for document {job.document_id} ({job.job_type})"
    )

    # Check if the document processing is actually complete despite the stuck job
    document = db.query(Document).filter(Document.id == job.document_id).first()
    if not document:
        logger.error(f"Document {job.document_id} not found for job {job.id}")
        return False

    # For OCR jobs, check if pages are already available (processing might be complete)
    if job.job_type == "ocr":
        try:
            from .config import get_settings
            from .s3_client import download_from_s3

            settings = get_settings()

            # Test if first page exists
            page_key = f"pages/{job.document_id}/page_0.webp"
            download_from_s3(settings.s3_bucket_tiles, page_key)

            # If page exists, mark job as completed
            logger.info(
                f"Pages found for document {job.document_id}, marking OCR job as completed"
            )
            job.status = "completed"
            job.completed_at = datetime.utcnow()
            job.error_message = "Auto-recovered: pages were already processed"
            db.commit()

            # Update document status if all jobs complete
            from .tasks import _update_document_status_if_complete

            _update_document_status_if_complete(job.document_id, db)

            return True

        except Exception as e:
            logger.warning(
                f"Could not verify pages for document {job.document_id}: {e}"
            )

    # If retry is enabled and we haven't exceeded max retries
    if retry and (job.error_message is None or "Retry" not in job.error_message):
        try:
            logger.info(f"Retrying stuck job {job.id}")

            # Reset job status
            job.status = "pending"
            job.started_at = None
            job.celery_task_id = None
            job.error_message = "Auto-retry: job was stuck"
            db.commit()

            # Re-enqueue the task
            if job.job_type == "ocr":
                task = process_document_ocr.delay(job.document_id, job.id)
            elif job.job_type == "tiling":
                task = process_document_tiling.delay(job.document_id, job.id)
            elif job.job_type == "thumbnails":
                task = process_document_thumbnails.delay(job.document_id, job.id)
            elif job.job_type == "conversion":
                task = convert_document_to_pdf_task.delay(job.document_id, job.id)
            else:
                logger.error(f"Unknown job type: {job.job_type}")
                return False

            job.celery_task_id = task.id
            db.commit()

            logger.info(f"Re-enqueued job {job.id} with task ID {task.id}")
            return True

        except Exception as e:
            logger.error(f"Failed to retry job {job.id}: {e}")

    # Mark as failed if retry is disabled or failed
    logger.warning(f"Marking job {job.id} as failed")
    job.status = "failed"
    job.completed_at = datetime.utcnow()
    job.error_message = f"Auto-failed: stuck for too long. Original error: {job.error_message or 'Unknown'}"
    db.commit()

    return False


def monitor_and_recover_jobs() -> dict:
    """Main monitoring function to detect and recover stuck jobs"""
    db = SessionLocal()
    results = {
        "stuck_jobs_found": 0,
        "orphaned_jobs_found": 0,
        "jobs_recovered": 0,
        "jobs_failed": 0,
    }

    try:
        # Find stuck jobs (running too long)
        stuck_jobs = find_stuck_jobs(db, max_runtime_minutes=20)  # 20 minute timeout
        results["stuck_jobs_found"] = len(stuck_jobs)

        # Find orphaned jobs (no active Celery task)
        orphaned_jobs = find_orphaned_jobs(db)
        results["orphaned_jobs_found"] = len(orphaned_jobs)

        # Combine all problematic jobs
        all_problematic_jobs = set(stuck_jobs + orphaned_jobs)

        for job in all_problematic_jobs:
            try:
                if recover_stuck_job(job, db, retry=True):
                    results["jobs_recovered"] += 1
                else:
                    results["jobs_failed"] += 1
            except Exception as e:
                logger.error(f"Error recovering job {job.id}: {e}")
                results["jobs_failed"] += 1

        logger.info(f"Job monitoring completed: {results}")

    except Exception as e:
        logger.error(f"Error in job monitoring: {e}")
    finally:
        db.close()

    return results


if __name__ == "__main__":
    # Allow running as standalone script
    import logging

    logging.basicConfig(level=logging.INFO)

    results = monitor_and_recover_jobs()
    print(f"Monitoring results: {results}")
