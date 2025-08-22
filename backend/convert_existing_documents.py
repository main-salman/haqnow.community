#!/usr/bin/env python3
"""
Script to convert existing non-PDF documents to PDF format
"""

import os
import sys

from sqlalchemy.orm import sessionmaker

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

from app.db import SessionLocal, engine
from app.models import Document, ProcessingJob
from app.tasks import convert_document_to_pdf_task


def convert_existing_documents():
    """Convert all existing non-PDF documents to PDF"""

    with SessionLocal() as db:
        try:
            print("🔄 Starting conversion of existing documents...")

            # Find all non-PDF documents
            documents = db.query(Document).all()
            non_pdf_docs = []

            for doc in documents:
                if not doc.title.lower().endswith(".pdf"):
                    non_pdf_docs.append(doc)

            print(f"📊 Found {len(non_pdf_docs)} non-PDF documents to convert")

            if len(non_pdf_docs) == 0:
                print("✅ All documents are already PDFs")
                return

            # Show document types to convert
            extensions = {}
            for doc in non_pdf_docs:
                ext = doc.title.split(".")[-1].lower() if "." in doc.title else "no_ext"
                extensions[ext] = extensions.get(ext, 0) + 1

            print("📋 Document types to convert:")
            for ext, count in sorted(extensions.items()):
                print(f"   .{ext}: {count} documents")

            # Ask for confirmation
            response = input(
                f"\\nConvert {len(non_pdf_docs)} documents to PDF? (yes/no): "
            )
            if response.lower() != "yes":
                print("❌ Conversion cancelled")
                return

            # Create conversion jobs for each non-PDF document
            conversion_jobs = []
            for doc in non_pdf_docs:
                # Check if conversion job already exists
                existing_job = (
                    db.query(ProcessingJob)
                    .filter(
                        ProcessingJob.document_id == doc.id,
                        ProcessingJob.job_type == "conversion",
                    )
                    .first()
                )

                if existing_job and existing_job.status == "completed":
                    print(f"⏭️  Skipping {doc.title} - already converted")
                    continue
                elif existing_job and existing_job.status in ["queued", "running"]:
                    print(f"⏳ Skipping {doc.title} - conversion in progress")
                    continue

                # Create new conversion job
                job = ProcessingJob(
                    document_id=doc.id,
                    job_type="conversion",
                    status="queued",
                    progress=0,
                )
                db.add(job)
                db.commit()
                db.refresh(job)

                conversion_jobs.append((doc, job))
                print(f"📝 Queued conversion job for: {doc.title}")

            if len(conversion_jobs) == 0:
                print("✅ No new conversions needed")
                return

            print(f"\\n🚀 Starting conversion of {len(conversion_jobs)} documents...")

            # Dispatch Celery tasks
            for doc, job in conversion_jobs:
                try:
                    # Dispatch conversion task
                    task = convert_document_to_pdf_task.delay(doc.id, job.id)
                    job.celery_task_id = task.id
                    db.commit()
                    print(f"✅ Dispatched conversion task for: {doc.title}")
                except Exception as e:
                    print(f"❌ Failed to dispatch task for {doc.title}: {e}")
                    job.status = "failed"
                    job.error_message = str(e)
                    db.commit()

            print(
                f"\\n🎉 Conversion process initiated for {len([j for d, j in conversion_jobs if j.celery_task_id])} documents!"
            )
            print(
                "📊 Monitor progress in the worker logs or check document status in the web interface"
            )

        except Exception as e:
            print(f"❌ Error during conversion process: {str(e)}")
            db.rollback()
            raise

        finally:
            db.close()


if __name__ == "__main__":
    print("🔄 Document Conversion Script")
    print("This will convert all non-PDF documents in the database to PDF format")
    print("===============================================================\\n")

    convert_existing_documents()
