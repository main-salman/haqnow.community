import sys
sys.path.insert(0, '/app')
from app.models import ProcessingJob, Document
from app.db import SessionLocal
from app.tasks import convert_document_to_pdf_task, process_document_tiling, process_document_thumbnails, process_document_ocr

print("🚀 Emergency: Force-enqueuing jobs for documents 1-27...")

db = SessionLocal()
try:
    # Get all jobs for documents 1-27 that don't have celery_task_ids
    jobs = db.query(ProcessingJob).filter(
        ProcessingJob.document_id.between(1, 27),
        ProcessingJob.celery_task_id.is_(None)
    ).all()

    print(f"Found {len(jobs)} jobs to force-enqueue")

    submitted_count = 0
    for job in jobs:
        try:
            # Submit immediately with .delay()
            if job.job_type == "conversion":
                task = convert_document_to_pdf_task.delay(job.document_id, job.id)
            elif job.job_type == "tiling":
                task = process_document_tiling.delay(job.document_id, job.id)
            elif job.job_type == "thumbnails":
                task = process_document_thumbnails.delay(job.document_id, job.id)
            elif job.job_type == "ocr":
                task = process_document_ocr.delay(job.document_id, job.id)
            else:
                continue

            job.celery_task_id = task.id
            submitted_count += 1

            if submitted_count % 10 == 0:
                print(f"  Submitted {submitted_count} jobs...")

        except Exception as e:
            print(f"Error submitting {job.job_type} for doc {job.document_id}: {e}")

    db.commit()
    print(f"✅ Successfully submitted {submitted_count} jobs to Celery")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    db.rollback()
finally:
    db.close()
