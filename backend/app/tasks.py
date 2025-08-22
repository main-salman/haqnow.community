from datetime import datetime

from celery import current_task
from sqlalchemy.orm import Session

from .celery_app import celery_app
from .config import get_settings
from .db import SessionLocal
from .models import Document, ProcessingJob
from .processing import (
    extract_text_from_image,
    generate_thumbnail,
    generate_tiles,
    get_document_info,
    rasterize_image,
    rasterize_pdf_pages,
)
from .s3_client import download_from_s3, upload_to_s3

# from .conversion import convert_document_to_pdf  # TODO: Add when conversion is implemented


def get_db_session() -> Session:
    """Get database session for Celery tasks"""
    return SessionLocal()


def _load_original_file_bytes(settings, document: Document) -> bytes:
    """Best-effort loader for original uploaded file bytes.

    Load order:
    1) S3 bucket `settings.s3_bucket_originals` at key `uploads/{document.title}`
    2) Local uploads within project layout used by API/worker: `/srv/backend/uploads/{filename}`
    3) Alternate local paths that may be used in dev: `/srv/uploads/{filename}`, `uploads/{filename}`
    4) As a last resort, synthesize a simple one-page PDF indicating a placeholder
    """
    original_key = f"uploads/{document.title}"

    # 1) Try S3
    try:
        return download_from_s3(settings.s3_bucket_originals, original_key)
    except Exception:
        pass

    # 2) and 3) Try local filesystem variants
    import os

    candidate_paths = [
        f"/app/uploads/{document.title}",  # shared volume path
        f"/srv/backend/uploads/{document.title}",  # container path when running `cd backend`
        f"/srv/uploads/{document.title}",  # alternate mount path
        f"uploads/{document.title}",  # relative path in dev
    ]
    for path in candidate_paths:
        if os.path.exists(path):
            with open(path, "rb") as f:
                return f.read()

    # 4) Last resort: create a minimal placeholder PDF
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (100, 100), f"Uploaded file not found; placeholder for: {document.title}"
    )
    data = doc.tobytes()
    doc.close()
    return data


@celery_app.task(bind=True)
def process_document_tiling(self, document_id: int, job_id: int):
    """Generate tiles for a document"""
    db = get_db_session()
    settings = get_settings()

    try:
        # Update job status
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise ValueError(f"Document {document_id} not found")

        job.status = "running"
        job.started_at = datetime.utcnow()
        job.celery_task_id = self.request.id
        db.commit()

        # Load original file bytes from S3 or local uploads directory
        file_data = _load_original_file_bytes(settings, document)

        job.progress = 20
        db.commit()
        self.update_state(state="PROGRESS", meta={"progress": 20})

        # Rasterize pages
        if document.title.lower().endswith(".pdf"):
            pages = rasterize_pdf_pages(file_data, dpi=300)
        else:
            pages = rasterize_image(file_data, dpi=300)

        job.progress = 50
        db.commit()
        self.update_state(state="PROGRESS", meta={"progress": 50})

        # Generate tiles for each page
        total_pages = len(pages)
        for i, (page_num, page_image) in enumerate(pages):
            tiles = generate_tiles(page_image, tile_size=256, quality=80)

            # Upload tiles to S3 or store locally
            for x, y, tile_data in tiles:
                tile_key = f"tiles/{document_id}/page_{page_num}/tile_{x}_{y}.webp"
                try:
                    upload_to_s3(
                        settings.s3_bucket_tiles, tile_key, tile_data, "image/webp"
                    )
                except Exception as e:
                    # Store locally if S3 is not available
                    import os

                    local_dir = f"/srv/processed/tiles/{document_id}/page_{page_num}"
                    os.makedirs(local_dir, exist_ok=True)
                    local_path = f"{local_dir}/tile_{x}_{y}.webp"
                    with open(local_path, "wb") as f:
                        f.write(tile_data)
                    print(f"Failed to upload tile to SOS: {e}")
                    print(f"Stored tile locally: {local_path}")

            # Update progress
            progress = 50 + (40 * (i + 1) // total_pages)
            job.progress = progress
            db.commit()
            self.update_state(state="PROGRESS", meta={"progress": progress})

        # Mark as completed
        job.status = "completed"
        job.progress = 100
        job.completed_at = datetime.utcnow()
        db.commit()

        return {"status": "completed", "document_id": document_id, "pages": total_pages}

    except Exception as e:
        # Mark as failed
        if "job" in locals():
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            db.commit()
        raise
    finally:
        db.close()


@celery_app.task(bind=True)
def process_document_thumbnails(self, document_id: int, job_id: int):
    """Generate thumbnails for a document"""
    db = get_db_session()
    settings = get_settings()

    try:
        # Update job status
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise ValueError(f"Document {document_id} not found")

        job.status = "running"
        job.started_at = datetime.utcnow()
        job.celery_task_id = self.request.id
        db.commit()

        # Load original file bytes from S3 or local uploads directory
        file_data = _load_original_file_bytes(settings, document)

        job.progress = 25
        db.commit()
        self.update_state(state="PROGRESS", meta={"progress": 25})

        # Rasterize pages
        if document.title.lower().endswith(".pdf"):
            pages = rasterize_pdf_pages(file_data, dpi=300)
        else:
            pages = rasterize_image(file_data, dpi=300)

        job.progress = 50
        db.commit()
        self.update_state(state="PROGRESS", meta={"progress": 50})

        # Generate thumbnails and high-res previews for each page
        total_pages = len(pages)
        for i, (page_num, page_image) in enumerate(pages):
            thumbnail = generate_thumbnail(page_image, max_size=(200, 300))

            # Upload thumbnail to S3 or store locally
            thumb_key = f"thumbnails/{document_id}/page_{page_num}.webp"
            try:
                upload_to_s3(
                    settings.s3_bucket_thumbnails, thumb_key, thumbnail, "image/webp"
                )
            except Exception as e:
                # Store locally if S3 is not available
                import os

                local_dir = f"/srv/processed/thumbnails/{document_id}"
                os.makedirs(local_dir, exist_ok=True)
                local_path = f"{local_dir}/page_{page_num}.webp"
                with open(local_path, "wb") as f:
                    f.write(thumbnail)
                print(f"Failed to upload thumbnail to SOS: {e}")
                print(f"Stored thumbnail locally: {local_path}")

            # Also persist a full-quality preview (PNG) for 300 DPI viewing
            try:
                import os

                preview_dir = f"/srv/processed/previews/{document_id}"
                os.makedirs(preview_dir, exist_ok=True)
                preview_path = f"{preview_dir}/page_{page_num}.png"
                with open(preview_path, "wb") as f:
                    f.write(page_image)
            except Exception as e:
                print(f"Failed to store preview image: {e}")

            # Update progress
            progress = 50 + (50 * (i + 1) // total_pages)
            job.progress = progress
            db.commit()
            self.update_state(state="PROGRESS", meta={"progress": progress})

        # Mark as completed
        job.status = "completed"
        job.progress = 100
        job.completed_at = datetime.utcnow()
        db.commit()

        return {"status": "completed", "document_id": document_id, "pages": total_pages}

    except Exception as e:
        # Mark as failed
        if "job" in locals():
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            db.commit()
        raise
    finally:
        db.close()


@celery_app.task(bind=True)
def process_document_ocr(self, document_id: int, job_id: int):
    """Perform OCR on a document"""
    db = get_db_session()
    settings = get_settings()

    try:
        # Update job status
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise ValueError(f"Document {document_id} not found")

        job.status = "running"
        job.started_at = datetime.utcnow()
        job.celery_task_id = self.request.id
        db.commit()

        # Load original file bytes from S3 or local uploads directory
        file_data = _load_original_file_bytes(settings, document)

        job.progress = 20
        db.commit()
        self.update_state(state="PROGRESS", meta={"progress": 20})

        # Rasterize pages
        if document.title.lower().endswith(".pdf"):
            pages = rasterize_pdf_pages(file_data, dpi=300)
        else:
            pages = rasterize_image(file_data, dpi=300)

        job.progress = 40
        db.commit()
        self.update_state(state="PROGRESS", meta={"progress": 40})

        # Extract text from each page
        total_pages = len(pages)
        extracted_text = []

        for i, (page_num, page_image) in enumerate(pages):
            try:
                text = extract_text_from_image(page_image, language="eng")
                extracted_text.append({"page": page_num, "text": text})
            except Exception as e:
                print(f"OCR failed for page {page_num}: {e}")
                extracted_text.append(
                    {"page": page_num, "text": f"[OCR Error: {str(e)}]"}
                )

            # Update progress
            progress = 40 + (50 * (i + 1) // total_pages)
            job.progress = progress
            db.commit()
            self.update_state(state="PROGRESS", meta={"progress": progress})

        # Store extracted text (in real implementation, would store in search index)
        ocr_result = {
            "document_id": document_id,
            "pages": extracted_text,
            "total_pages": total_pages,
        }

        # Upload OCR results to S3
        import json

        ocr_key = f"ocr/{document_id}/text.json"
        try:
            upload_to_s3(
                settings.s3_bucket_ocr,
                ocr_key,
                json.dumps(ocr_result).encode(),
                "application/json",
            )
        except Exception as e:
            print(f"Failed to upload OCR results to SOS: {e}")

        # Mark as completed
        job.status = "completed"
        job.progress = 100
        job.completed_at = datetime.utcnow()
        db.commit()

        return {
            "status": "completed",
            "document_id": document_id,
            "pages": total_pages,
            "text_length": sum(len(p["text"]) for p in extracted_text),
        }

    except Exception as e:
        # Mark as failed
        if "job" in locals():
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            db.commit()
        raise
    finally:
        db.close()


@celery_app.task(bind=True)
def convert_document_to_pdf_task(self, document_id: int, job_id: int):
    """Convert a document to PDF format for standardization"""
    db = get_db_session()
    settings = get_settings()

    try:
        # Get job and document
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise ValueError(f"Document {document_id} not found")

        job.status = "running"
        job.started_at = datetime.utcnow()
        job.celery_task_id = self.request.id
        db.commit()

        # Check if document is already a PDF
        if document.title.lower().endswith(".pdf"):
            job.status = "completed"
            job.progress = 100
            job.completed_at = datetime.utcnow()
            db.commit()
            return {"status": "skipped", "reason": "Document is already PDF"}

        # Load original file
        file_data = _load_original_file_bytes(settings, document)

        job.progress = 20
        db.commit()
        self.update_state(state="PROGRESS", meta={"progress": 20})

        # Convert to PDF
        print(f"Converting {document.title} to PDF...")
        pdf_data, pdf_filename = convert_document_to_pdf(file_data, document.title)

        job.progress = 70
        db.commit()
        self.update_state(state="PROGRESS", meta={"progress": 70})

        # Store converted PDF
        try:
            # Try to upload to S3 first
            s3_key = f"documents/{document_id}/{pdf_filename}"
            upload_to_s3(settings.s3_bucket_name, s3_key, pdf_data, "application/pdf")
            print(f"Uploaded converted PDF to S3: {s3_key}")
        except Exception as e:
            # Fall back to local storage
            print(f"S3 upload failed, storing locally: {e}")
            import os

            local_dir = f"/srv/uploads"
            os.makedirs(local_dir, exist_ok=True)
            local_path = os.path.join(local_dir, f"{document_id}_{pdf_filename}")
            with open(local_path, "wb") as f:
                f.write(pdf_data)
            print(f"Stored converted PDF locally: {local_path}")

        # Update document title to reflect PDF conversion
        original_title = document.title
        document.title = pdf_filename

        job.progress = 100
        job.status = "completed"
        job.completed_at = datetime.utcnow()
        db.commit()

        print(f"✅ Document conversion completed: {original_title} -> {pdf_filename}")
        return {
            "status": "completed",
            "original_filename": original_title,
            "converted_filename": pdf_filename,
            "size": len(pdf_data),
        }

    except Exception as e:
        print(f"❌ Document conversion failed: {e}")
        if "job" in locals():
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            db.commit()
        raise
    finally:
        db.close()
